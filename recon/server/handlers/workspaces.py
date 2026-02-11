"""
Handlers for workspace commands
"""
from typing import Any, Dict, TYPE_CHECKING

from recon.shared.constants import Commands
from recon.server.context import RequestContext
from recon.server.engine import Engine, WorkspaceNotFoundError
from recon.server.dispatcher import ValidationError

if TYPE_CHECKING:
    from recon.server.dispatcher import Dispatcher


def handle_list(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """List all workspaces"""
    workspaces = engine.list_workspaces()
    return {'workspaces': workspaces}


def handle_create(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Create a new workspace"""
    name = params.get('name')
    if not name:
        raise ValidationError("Workspace name is required")
    
    if engine.workspace_exists(name):
        raise ValidationError(f"Workspace '{name}' already exists")
    
    engine.create_workspace(name)
    return {'created': True, 'name': name}


def handle_delete(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Delete a workspace"""
    name = params.get('name')
    if not name:
        raise ValidationError("Workspace name is required")
    
    if not engine.workspace_exists(name):
        raise ValidationError(f"Workspace '{name}' does not exist")
    
    engine.delete_workspace(name)
    return {'deleted': True, 'name': name}


def handle_info(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Get information about the current workspace"""
    try:
        info = engine.get_workspace_info(ctx.workspace)
        return info
    except WorkspaceNotFoundError as e:
        raise ValidationError(str(e))


def register(dispatcher: 'Dispatcher'):
    """Register workspace handlers with the dispatcher"""
    dispatcher.register(Commands.WORKSPACES_LIST, handle_list, requires_workspace=False)
    dispatcher.register(Commands.WORKSPACES_CREATE, handle_create, requires_workspace=False)
    dispatcher.register(Commands.WORKSPACES_DELETE, handle_delete, requires_workspace=False)
    dispatcher.register(Commands.WORKSPACES_INFO, handle_info, requires_workspace=True)
