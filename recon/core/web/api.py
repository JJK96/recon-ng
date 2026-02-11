"""
REST API endpoints for the Recon-ng web interface.

All operations are delegated to the RPC server. The web API acts as a thin
HTTP-to-RPC translation layer using native async I/O.
"""
from sanic import Blueprint
from sanic.response import json
from sanic.exceptions import NotFound, BadRequest, ServerError
from sanic_ext import openapi

from recon.core.web import get_workspace, set_workspace, task_tracker
from recon.core.web.rpc import RPCClientError
from recon.core.web.utils import columnize
from recon.core.web.exports import jsonify, csvify, xmlify, listify, xlsxify, proxify

# Create API blueprint
api_blueprint = Blueprint('api', url_prefix='/api')

# Export formats
EXPORTS = {
    'json': jsonify,
    'xml': xmlify,
    'csv': csvify,
    'list': listify,
    'xlsx': xlsxify,
    'proxy': proxify,
}


async def rpc_call(request, command: str, params: dict = None, workspace: str = None, timeout: float = 30.0):
    """
    Helper to make async RPC calls with error handling.
    
    Returns the result dict on success, or raises appropriate HTTP exception on error.
    """
    try:
        return await request.app.ctx.rpc.call(
            command=command,
            workspace=workspace or get_workspace(),
            params=params or {},
            timeout=timeout
        )
    except RPCClientError as e:
        error_str = str(e)
        if 'NOT_FOUND' in error_str:
            raise NotFound(error_str)
        elif 'INVALID_PARAMS' in error_str:
            raise BadRequest(error_str)
        else:
            raise ServerError(error_str)


# =============================================================================
# Tasks
# =============================================================================

@api_blueprint.get('/tasks/')
@openapi.summary("Get all tasks")
@openapi.description("Gets all tasks for the current workspace")
async def get_tasks(request):
    tasks = await task_tracker.get_tasks()
    return json({'tasks': tasks})


@api_blueprint.post('/tasks/')
@openapi.summary("Run a module as a background task")
@openapi.description("For real-time event streaming, use the WebSocket endpoint instead")
async def create_task(request):
    body = request.json or {}
    path = body.get('path')
    if not path:
        raise BadRequest("Module path required")
    
    # Verify module exists via RPC
    try:
        await rpc_call(request, 'modules/info', {'module': path})
    except NotFound:
        raise NotFound(f"Module not found: {path}")
    
    workspace = get_workspace()
    
    # Create task - for REST API, we use a placeholder session
    task_id = await task_tracker.create_task('rest-api', workspace, path)
    
    # Run module in background
    async def run_module_task():
        try:
            await task_tracker.update_task(task_id, status='running')
            
            result = await request.app.ctx.rpc.call(
                'modules/run',
                workspace=workspace,
                params={'module': path},
                timeout=300.0
            )
            
            await task_tracker.update_task(task_id, status='finished', result=result)
        except Exception as e:
            await task_tracker.update_task(
                task_id,
                status='failed',
                result={'error': str(e)}
            )
    
    # Start background task
    request.app.add_task(run_module_task())
    
    return json({'task': task_id}, status=201)


@api_blueprint.get('/tasks/<tid:str>')
@openapi.summary("Get a specific task")
@openapi.parameter("tid", str, "path", description="Task ID")
async def get_task(request, tid: str):
    task = await task_tracker.get_task(tid)
    if not task:
        raise NotFound(f"Task not found: {tid}")
    return json(task)


# =============================================================================
# Modules
# =============================================================================

@api_blueprint.get('/modules/')
@openapi.summary("Get all modules")
@openapi.description("Gets all module names from the framework")
async def get_modules(request):
    result = await rpc_call(request, 'modules/list')
    return json({'modules': sorted(result.get('modules', []))})


@api_blueprint.get('/modules/<module:path>')
@openapi.summary("Get module information")
@openapi.parameter("module", str, "path", description="Module path")
async def get_module(request, module: str):
    result = await rpc_call(request, 'modules/info', {'module': module})
    return json(result.get('module', {}))


@api_blueprint.patch('/modules/<module:path>')
@openapi.summary("Update module options")
@openapi.parameter("module", str, "path", description="Module path")
async def update_module(request, module: str):
    body = request.json or {}
    options = body.get('options', [])
    
    # Convert options list to dict for RPC
    options_dict = {opt['name']: opt['value'] for opt in options if 'name' in opt and 'value' in opt}
    
    if options_dict:
        await rpc_call(request, 'modules/load', {'module': module, 'options': options_dict})
    
    # Return updated module info
    result = await rpc_call(request, 'modules/info', {'module': module})
    return json(result.get('module', {}))


# =============================================================================
# Workspaces
# =============================================================================

@api_blueprint.get('/workspaces/')
@openapi.summary("Get all workspaces")
@openapi.description("Gets all workspace names from the framework")
async def get_workspaces(request):
    result = await rpc_call(request, 'workspaces/list')
    return json({'workspaces': sorted(result.get('workspaces', []))})


@api_blueprint.get('/workspaces/<workspace:str>')
@openapi.summary("Get workspace information")
@openapi.parameter("workspace", str, "path", description="Workspace name")
async def get_workspace_info(request, workspace: str):
    result = await rpc_call(request, 'workspaces/info', {'workspace': workspace})
    
    current_workspace = get_workspace()
    status = 'active' if workspace == current_workspace else 'inactive'
    
    # Get options if this is the active workspace
    options = []
    if workspace == current_workspace:
        opts_result = await rpc_call(request, 'options/list')
        options = opts_result.get('options', [])
    
    return json({
        'name': workspace,
        'status': status,
        'options': options,
    })


@api_blueprint.patch('/workspaces/<workspace:str>')
@openapi.summary("Update workspace")
@openapi.description("Activating a workspace deactivates the currently activated workspace")
@openapi.parameter("workspace", str, "path", description="Workspace name")
async def update_workspace(request, workspace: str):
    # Verify workspace exists
    await rpc_call(request, 'workspaces/info', {'workspace': workspace})
    
    body = request.json or {}
    status = body.get('status')
    
    # Process status (activation)
    if status == 'active':
        set_workspace(workspace)
        request.app.ctx.workspace = workspace
    
    # Return updated workspace info
    return await get_workspace_info(request, workspace)


# =============================================================================
# Dashboard
# =============================================================================

@api_blueprint.get('/dashboard')
@openapi.summary("Get dashboard")
@openapi.description("Gets summary information about the current workspace")
async def get_dashboard(request):
    result = await rpc_call(request, 'dashboard/show')
    dashboard = result.get('dashboard', {})
    
    return json({
        'workspace': get_workspace(),
        'records': dashboard.get('records', []),
        'activity': dashboard.get('activity', []),
    })


# =============================================================================
# Reports
# =============================================================================

@api_blueprint.get('/reports/')
@openapi.summary("Get all report types")
async def get_reports(request):
    # Import here to avoid circular imports
    from recon.core.web.reports import REPORTS
    return json({'reports': sorted(list(REPORTS.keys()))})


@api_blueprint.get('/reports/<report:str>')
@openapi.summary("Run a report")
@openapi.parameter("report", str, "path", description="Report type")
async def get_report(request, report: str):
    from recon.core.web.reports import REPORTS
    
    if report not in REPORTS:
        raise NotFound(f"Report not found: {report}")
    
    # Reports need data from the database - fetch via RPC
    tables_result = await rpc_call(request, 'db/tables')
    tables = tables_result.get('tables', [])
    
    # Build data dict for report
    data = {}
    for table in tables:
        query_result = await rpc_call(request, 'db/query', {'sql': f"SELECT * FROM {table}"})
        columns = query_result.get('columns', [])
        rows = query_result.get('rows', [])
        data[table] = columnize(columns, rows)
    
    return await REPORTS[report](request, data=data)


# =============================================================================
# Tables
# =============================================================================

@api_blueprint.get('/tables/')
@openapi.summary("Get all tables")
@openapi.description("Gets all table names for the current workspace")
async def get_tables(request):
    result = await rpc_call(request, 'db/tables')
    return json({
        'workspace': get_workspace(),
        'tables': sorted(result.get('tables', [])),
    })


@api_blueprint.get('/tables/<table:str>')
@openapi.summary("Get table contents")
@openapi.parameter("table", str, "path", description="Table name")
@openapi.parameter("format", str, "query", description="Export format (json, csv, xml, list, xlsx, proxy)")
@openapi.parameter("columns", str, "query", description="Columns to select")
async def get_table(request, table: str):
    # Verify table exists
    tables_result = await rpc_call(request, 'db/tables')
    tables = tables_result.get('tables', [])
    if table not in tables:
        raise NotFound(f"Table not found: {table}")
    
    # Build query
    columns = request.args.get('columns')
    if columns:
        sql = f"SELECT {columns} FROM {table}"
    else:
        sql = f"SELECT * FROM {table}"
    
    # Query via RPC
    result = await rpc_call(request, 'db/query', {'sql': sql})
    columns = result.get('columns', [])
    rows = result.get('rows', [])
    
    # Convert to list of dicts
    rows_dicts = columnize(columns, rows)
    
    # Handle export format
    export_format = request.args.get('format')
    if export_format and export_format in EXPORTS:
        return await EXPORTS[export_format](request, rows=rows_dicts)
    
    return json({
        'workspace': get_workspace(),
        'table': table,
        'columns': columns,
        'rows': rows_dicts,
    })


# =============================================================================
# Exports
# =============================================================================

@api_blueprint.get('/exports')
@openapi.summary("Get all export types")
async def get_exports(request):
    return json({'exports': sorted(list(EXPORTS.keys()))})


# =============================================================================
# Marketplace
# =============================================================================

@api_blueprint.get('/marketplace/')
@openapi.summary("Get marketplace modules")
@openapi.description("Gets all available modules from the marketplace")
async def get_marketplace(request):
    result = await rpc_call(request, 'marketplace/search')
    return json({'modules': result.get('modules', [])})


@api_blueprint.post('/marketplace/')
@openapi.summary("Refresh marketplace")
@openapi.description("Refreshes the marketplace index")
async def refresh_marketplace(request):
    await rpc_call(request, 'marketplace/refresh')
    return json({'status': 'refreshed'})


@api_blueprint.get('/marketplace/<module:path>')
@openapi.summary("Get marketplace module info")
@openapi.parameter("module", str, "path", description="Module path")
async def get_marketplace_module(request, module: str):
    result = await rpc_call(request, 'marketplace/info', {'module': module})
    return json(result.get('module', {}))


@api_blueprint.post('/marketplace/<module:path>')
@openapi.summary("Install marketplace module")
@openapi.parameter("module", str, "path", description="Module path")
async def install_marketplace_module(request, module: str):
    await rpc_call(request, 'marketplace/install', {'module': module})
    return json({'status': 'installed', 'module': module}, status=201)


@api_blueprint.delete('/marketplace/<module:path>')
@openapi.summary("Remove marketplace module")
@openapi.parameter("module", str, "path", description="Module path")
async def remove_marketplace_module(request, module: str):
    await rpc_call(request, 'marketplace/remove', {'module': module})
    return json({'status': 'removed', 'module': module})


# =============================================================================
# Keys
# =============================================================================

@api_blueprint.get('/keys/')
@openapi.summary("Get all API keys")
async def get_keys(request):
    result = await rpc_call(request, 'keys/list')
    return json({'keys': result.get('keys', [])})


@api_blueprint.get('/keys/<name:str>')
@openapi.summary("Get a specific API key")
@openapi.parameter("name", str, "path", description="API key name")
async def get_key(request, name: str):
    result = await rpc_call(request, 'keys/get', {'name': name})
    return json(result.get('key', {}))


@api_blueprint.put('/keys/<name:str>')
@openapi.summary("Set an API key")
@openapi.parameter("name", str, "path", description="API key name")
async def set_key(request, name: str):
    body = request.json or {}
    value = body.get('value', '')
    await rpc_call(request, 'keys/add', {'name': name, 'value': value})
    return json({'status': 'set', 'name': name})


@api_blueprint.delete('/keys/<name:str>')
@openapi.summary("Delete an API key")
@openapi.parameter("name", str, "path", description="API key name")
async def delete_key(request, name: str):
    await rpc_call(request, 'keys/delete', {'name': name})
    return json({'status': 'deleted', 'name': name})


# =============================================================================
# Snapshots
# =============================================================================

@api_blueprint.get('/snapshots/')
@openapi.summary("Get all snapshots")
@openapi.description("Gets all snapshots for the current workspace")
async def get_snapshots(request):
    result = await rpc_call(request, 'snapshots/list')
    return json({
        'workspace': get_workspace(),
        'snapshots': result.get('snapshots', []),
    })


@api_blueprint.post('/snapshots/')
@openapi.summary("Create a snapshot")
async def create_snapshot(request):
    result = await rpc_call(request, 'snapshots/take')
    return json({'status': 'created', 'snapshot': result.get('snapshot')}, status=201)


@api_blueprint.post('/snapshots/<snapshot:str>')
@openapi.summary("Load a snapshot")
@openapi.parameter("snapshot", str, "path", description="Snapshot name")
async def load_snapshot(request, snapshot: str):
    await rpc_call(request, 'snapshots/load', {'snapshot': snapshot})
    return json({'status': 'loaded', 'snapshot': snapshot})


@api_blueprint.delete('/snapshots/<snapshot:str>')
@openapi.summary("Delete a snapshot")
@openapi.parameter("snapshot", str, "path", description="Snapshot name")
async def delete_snapshot(request, snapshot: str):
    await rpc_call(request, 'snapshots/delete', {'snapshot': snapshot})
    return json({'status': 'deleted', 'snapshot': snapshot})
