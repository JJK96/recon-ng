"""
Command dispatcher - Routes RPC requests to appropriate handlers
"""
import asyncio
import logging
from typing import Any, Callable, Dict, Optional, Type

from recon.shared.constants import Commands
from recon.shared.schemas import RPCRequest, RPCResponse
from recon.server.engine import Engine
from recon.server.context import RequestContext, ExecutionContext

logger = logging.getLogger(__name__)


class HandlerError(Exception):
    """Base exception for handler errors"""
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class CommandNotFoundError(HandlerError):
    """Raised when a command is not registered"""
    def __init__(self, command: str):
        super().__init__('COMMAND_NOT_FOUND', f"Unknown command: {command}")


class ValidationError(HandlerError):
    """Raised when request parameters are invalid"""
    def __init__(self, message: str):
        super().__init__('VALIDATION_ERROR', message)


class HandlerFunc:
    """Wrapper for a handler function with metadata"""
    def __init__(
        self,
        func: Callable,
        requires_workspace: bool = True,
        requires_context: bool = False
    ):
        self.func = func
        self.requires_workspace = requires_workspace
        self.requires_context = requires_context


class Dispatcher:
    """
    Routes RPC commands to appropriate handler functions.
    
    The dispatcher maintains a registry of command handlers and routes
    incoming requests to the appropriate handler based on the command.
    """
    
    def __init__(self, engine: Engine, publish_func: Callable[[str, str], None], loop: asyncio.AbstractEventLoop = None):
        """
        Args:
            engine: The Engine instance for executing commands
            publish_func: Function to publish events to client queues
            loop: Event loop for async operations
        """
        self.engine = engine
        self.publish_func = publish_func
        self.loop = loop
        self._handlers: Dict[str, HandlerFunc] = {}
        
        # Register all handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Register all command handlers"""
        # Import handlers here to avoid circular imports
        from recon.server.handlers import (
            workspaces,
            modules,
            database,
            keys,
            marketplace,
            options,
            dashboard,
            snapshots,
        )
        
        # Register workspace handlers
        workspaces.register(self)
        
        # Register module handlers
        modules.register(self)
        
        # Register database handlers
        database.register(self)
        
        # Register keys handlers
        keys.register(self)
        
        # Register marketplace handlers
        marketplace.register(self)
        
        # Register options handlers
        options.register(self)
        
        # Register dashboard handlers
        dashboard.register(self)
        
        # Register snapshot handlers
        snapshots.register(self)
    
    def register(
        self,
        command: str,
        handler: Callable,
        requires_workspace: bool = True,
        requires_context: bool = False
    ):
        """
        Register a handler for a command.
        
        Args:
            command: The command string (e.g., 'workspaces/list')
            handler: The handler function
            requires_workspace: Whether the command requires a valid workspace
            requires_context: Whether the handler needs ExecutionContext
        """
        self._handlers[command] = HandlerFunc(
            func=handler,
            requires_workspace=requires_workspace,
            requires_context=requires_context
        )
        logger.debug(f"Registered handler for command: {command}")
    
    def get_handler(self, command: str) -> Optional[HandlerFunc]:
        """Get the handler for a command"""
        return self._handlers.get(command)
    
    def dispatch(self, request: RPCRequest) -> RPCResponse:
        """
        Dispatch an RPC request to the appropriate handler.
        
        Args:
            request: The RPC request to dispatch
            
        Returns:
            RPCResponse with the result or error
        """
        command = request.command
        
        # Look up handler
        handler = self.get_handler(command)
        if not handler:
            logger.warning(f"No handler for command: {command}")
            return RPCResponse.make_error(
                request.id,
                'COMMAND_NOT_FOUND',
                f"Unknown command: {command}"
            )
        
        # Validate workspace if required
        if handler.requires_workspace:
            if not request.workspace:
                return RPCResponse.make_error(
                    request.id,
                    'WORKSPACE_REQUIRED',
                    "This command requires a workspace"
                )
            # Note: We do lazy validation - workspace existence is checked
            # when the handler actually needs it
        
        # Create context
        ctx = RequestContext(
            request_id=request.id,
            client_id=request.client_id,
            workspace=request.workspace,
            global_options=request.global_options,
            publish_func=self.publish_func,
            loop=self.loop
        )
        
        try:
            # Call the handler
            if handler.requires_context:
                exec_ctx = ExecutionContext(ctx)
                result = handler.func(
                    self.engine,
                    request.params,
                    exec_ctx
                )
            else:
                result = handler.func(
                    self.engine,
                    request.params,
                    ctx
                )
            
            # Return success response
            return RPCResponse.make_success(request.id, result)
            
        except HandlerError as e:
            logger.warning(f"Handler error for {command}: {e.code} - {e.message}")
            return RPCResponse.make_error(request.id, e.code, e.message)
            
        except Exception as e:
            logger.exception(f"Unexpected error handling {command}")
            return RPCResponse.make_error(
                request.id,
                'INTERNAL_ERROR',
                str(e)
            )
    
    def handle_input_response(self, request: RPCRequest) -> RPCResponse:
        """
        Handle input/response command specially.
        This command provides input to a waiting handler.
        
        This is handled differently because it needs to find the
        RequestContext that's waiting for input, not create a new one.
        """
        # This will be implemented in the consumer where we track
        # active contexts. For now, return success.
        return RPCResponse.make_success(request.id, {})
