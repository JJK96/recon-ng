"""
Recon-ng Web Interface

This module provides a Sanic-based web interface that communicates with the
recon-ng RPC server via RabbitMQ. Real-time updates are pushed to browser
clients via WebSocket using python-socketio.

Architecture:
    Browser <--WebSocket--> python-socketio <--> Sanic ASGI App
                                                    |
                                               AsyncRPCClient
                                                    |
                                                aio-pika
                                                    |
                                                RabbitMQ
"""
import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Dict, Optional, Any

from sanic import Sanic
from sanic.response import html
from sanic_ext import Extend
from jinja2 import Environment, FileSystemLoader
import socketio

from recon.core.constants import BANNER_WEB
from recon.core.web.rpc import AsyncRPCClient, RPCClientError
from recon.shared.schemas import RPCEvent

logger = logging.getLogger(__name__)

# Print banner
print(BANNER_WEB)

# Configuration from environment
DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
AMQP_URL = os.environ.get('AMQP_URL', 'amqp://recon:recon@localhost:5672/')

# Global workspace state
_workspace = os.environ.get('WORKSPACE', 'default')
print(f" * Workspace initialized: {_workspace}")

# Configure Jinja2 templates directory
TEMPLATES_DIR = Path(__file__).parent / 'templates'
jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True
)


def url_for(name: str, **kwargs) -> str:
    """
    Generate URL for a named route or static file.
    Mimics Flask/Sanic url_for behavior for templates.
    """
    if name == 'static':
        filename = kwargs.get('filename', '')
        return f'/static/{filename}'
    elif name == 'index':
        return '/'
    else:
        # For other routes, just return the name as a path
        return f'/{name}'


# Add url_for to Jinja2 globals
jinja_env.globals['url_for'] = url_for

# Global workspace state
_workspace = os.environ.get('WORKSPACE', 'default')
print(f" * Workspace initialized: {_workspace}")


def render_template(template_name: str, **context) -> html:
    """Render a Jinja2 template and return a Sanic HTML response"""
    # Add config object with current workspace for templates
    context.setdefault('config', type('Config', (), {'WORKSPACE': _workspace})())
    template = jinja_env.get_template(template_name)
    return html(template.render(**context))


def get_workspace() -> str:
    """Get the current active workspace"""
    return _workspace


def set_workspace(workspace: str):
    """Set the active workspace"""
    global _workspace
    _workspace = workspace
    print(f" * Workspace initialized: {workspace}")


# =============================================================================
# Task Tracker
# =============================================================================

class TaskTracker:
    """
    Tracks active tasks and their associated WebSocket sessions.
    
    When a module is run, we create a task and associate it with a
    WebSocket session so events can be streamed back to the correct client.
    
    Uses asyncio.Lock for thread-safe access in async context.
    """
    
    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
    
    async def create_task(self, session_id: str, workspace: str, module: str) -> str:
        """Create a new task and return its ID"""
        task_id = str(uuid.uuid4())
        async with self._lock:
            self._tasks[task_id] = {
                'session_id': session_id,
                'workspace': workspace,
                'module': module,
                'status': 'queued',
                'result': None,
            }
        return task_id
    
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task info by ID"""
        async with self._lock:
            task = self._tasks.get(task_id)
            if task:
                return {'id': task_id, **task.copy()}
            return None
    
    async def get_tasks(self) -> list:
        """Get all tasks"""
        async with self._lock:
            return [
                {'id': tid, **info.copy()}
                for tid, info in self._tasks.items()
            ]
    
    async def update_task(self, task_id: str, **kwargs):
        """Update task properties"""
        async with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].update(kwargs)
    
    async def get_session_for_task(self, task_id: str) -> Optional[str]:
        """Get the session ID associated with a task"""
        async with self._lock:
            task = self._tasks.get(task_id)
            return task['session_id'] if task else None
    
    async def remove_task(self, task_id: str):
        """Remove a task"""
        async with self._lock:
            self._tasks.pop(task_id, None)


# Global task tracker
task_tracker = TaskTracker()


# =============================================================================
# Sanic Application
# =============================================================================

# Create Sanic app
app = Sanic("recon-web")

# Configure Sanic
app.config.DEBUG = DEBUG
app.config.SECRET = os.environ.get('SECRET_KEY', 'we keep no secrets here.')
app.config.OAS = True  # Enable OpenAPI
app.config.OAS_UI_DEFAULT = "swagger"
app.config.OAS_URL_PREFIX = "/api/docs"

# Initialize sanic-ext (provides OpenAPI)
Extend(app)

# Serve static files from /static URL path, mapped to ./static directory
STATIC_DIR = Path(__file__).parent / 'static'
app.static('/static', str(STATIC_DIR), name='static')


# =============================================================================
# Socket.IO Server
# =============================================================================

# Create async Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=DEBUG,
    engineio_logger=DEBUG
)

# Wrap Sanic app with Socket.IO ASGI middleware
# This is the app that should be run by uvicorn
asgi_app = socketio.ASGIApp(sio, app)


# =============================================================================
# App Context & Lifecycle
# =============================================================================

@app.before_server_start
async def setup_rpc(app, loop):
    """Initialize RPC client before server starts"""
    logger.info(f"Connecting to RabbitMQ at {AMQP_URL}")
    app.ctx.rpc = AsyncRPCClient(AMQP_URL)
    await app.ctx.rpc.connect()
    app.ctx.task_tracker = task_tracker
    app.ctx.workspace = _workspace
    logger.info("RPC client connected")


@app.after_server_stop
async def cleanup_rpc(app, loop):
    """Clean up RPC client after server stops"""
    if hasattr(app.ctx, 'rpc') and app.ctx.rpc:
        await app.ctx.rpc.close()
        logger.info("RPC client disconnected")


# =============================================================================
# Routes
# =============================================================================

@app.get('/')
async def index(request):
    """Render the main index page"""
    # Get workspaces via RPC
    try:
        result = await request.app.ctx.rpc.call('workspaces/list')
        workspaces = result.get('workspaces', [])
    except RPCClientError as e:
        logger.error(f"Failed to get workspaces: {e}")
        workspaces = []
    
    return render_template('index.html', workspaces=workspaces)


# =============================================================================
# Socket.IO Event Handlers
# =============================================================================

@sio.on('connect')
async def handle_connect(sid, environ):
    """Handle client connection"""
    logger.info(f"Client connected: {sid}")
    await sio.emit('connected', {'session_id': sid}, room=sid)


@sio.on('disconnect')
async def handle_disconnect(sid):
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {sid}")


@sio.on('run_module')
async def handle_run_module(sid, data):
    """
    Run a module and stream events back to the client.
    
    Expected data: {module: str, options: dict}
    """
    module_path = data.get('module')
    options = data.get('options', {})
    workspace = get_workspace()
    
    if not module_path:
        await sio.emit('error', {'message': 'Module path required'}, room=sid)
        return
    
    # Create task
    task_id = await task_tracker.create_task(sid, workspace, module_path)
    await sio.emit('task_created', {'task_id': task_id, 'module': module_path}, room=sid)
    
    # Run module as background task
    async def run_module_task():
        try:
            await task_tracker.update_task(task_id, status='running')
            await sio.emit('task_status', {'task_id': task_id, 'status': 'running'}, room=sid)
            
            # Get RPC client from the app context
            # Note: We need to access the app through sio's eio.app
            rpc = app.ctx.rpc
            
            # Stream events from RPC to WebSocket
            stream = rpc.call_with_events(
                command='modules/run',
                workspace=workspace,
                params={'module': module_path, 'options': options},
                timeout=300.0
            )
            
            async for event in stream:
                event_data = {
                    'task_id': task_id,
                    'type': event.type,
                    'data': event.data,
                }
                await sio.emit('task_event', event_data, room=sid)
            
            result = stream.result
            
            # Update task with result
            await task_tracker.update_task(task_id, status='finished', result=result)
            await sio.emit('task_completed', {
                'task_id': task_id,
                'status': 'finished',
                'result': result
            }, room=sid)
            
        except RPCClientError as e:
            logger.error(f"Module run failed: {e}")
            await task_tracker.update_task(task_id, status='failed', result={'error': str(e)})
            await sio.emit('task_failed', {
                'task_id': task_id,
                'status': 'failed',
                'error': str(e)
            }, room=sid)
        except Exception as e:
            logger.exception(f"Unexpected error running module: {e}")
            await task_tracker.update_task(task_id, status='failed', result={'error': str(e)})
            await sio.emit('task_failed', {
                'task_id': task_id,
                'status': 'failed',
                'error': str(e)
            }, room=sid)
    
    # Start background task
    sio.start_background_task(run_module_task)


@sio.on('switch_workspace')
async def handle_switch_workspace(sid, data):
    """Switch to a different workspace"""
    workspace = data.get('workspace')
    if not workspace:
        await sio.emit('error', {'message': 'Workspace name required'}, room=sid)
        return
    
    try:
        # Verify workspace exists via RPC
        rpc = app.ctx.rpc
        await rpc.call('workspaces/info', params={'workspace': workspace})
        set_workspace(workspace)
        app.ctx.workspace = workspace
        await sio.emit('workspace_changed', {'workspace': workspace}, room=sid)
    except RPCClientError as e:
        await sio.emit('error', {'message': f'Failed to switch workspace: {e}'}, room=sid)


@sio.on('input_response')
async def handle_input_response(sid, data):
    """Handle response to an input_required event"""
    request_id = data.get('request_id')
    value = data.get('value')
    
    if not request_id:
        await sio.emit('error', {'message': 'Request ID required'}, room=sid)
        return
    
    try:
        # Send input response via RPC
        rpc = app.ctx.rpc
        await rpc.call(
            'input/response',
            params={'request_id': request_id, 'value': value}
        )
        await sio.emit('input_accepted', {'request_id': request_id}, room=sid)
    except RPCClientError as e:
        await sio.emit('error', {'message': f'Failed to send input: {e}'}, room=sid)


# =============================================================================
# Register API Blueprint
# =============================================================================

# Import and register API blueprint (must be after app creation)
from recon.core.web.api import api_blueprint
app.blueprint(api_blueprint)


# =============================================================================
# Exports for external use
# =============================================================================

__all__ = [
    'app',
    'asgi_app',
    'sio',
    'task_tracker',
    'get_workspace',
    'set_workspace',
    'AMQP_URL',
]
