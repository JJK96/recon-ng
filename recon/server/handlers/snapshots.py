"""
Handlers for snapshot commands
"""
from typing import Any, Dict, TYPE_CHECKING

from recon.shared.constants import Commands
from recon.server.context import RequestContext
from recon.server.engine import Engine, WorkspaceNotFoundError
from recon.server.dispatcher import ValidationError

if TYPE_CHECKING:
    from recon.server.dispatcher import Dispatcher


def handle_list(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """List snapshots for the current workspace"""
    try:
        snapshots = engine.list_snapshots(ctx.workspace)
        return {'snapshots': snapshots}
    except WorkspaceNotFoundError as e:
        raise ValidationError(str(e))


def handle_take(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Take a snapshot of the current workspace database"""
    name = params.get('name')  # Optional
    
    try:
        snapshot_name = engine.take_snapshot(ctx.workspace, name=name)
        return {'created': True, 'name': snapshot_name}
    except WorkspaceNotFoundError as e:
        raise ValidationError(str(e))


def handle_load(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Load a snapshot into the current workspace database"""
    name = params.get('name')
    if not name:
        raise ValidationError("Snapshot name is required")
    
    try:
        success = engine.load_snapshot(ctx.workspace, name)
        if not success:
            raise ValidationError(f"Snapshot '{name}' not found")
        return {'loaded': True, 'name': name}
    except WorkspaceNotFoundError as e:
        raise ValidationError(str(e))


def handle_delete(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Delete a snapshot"""
    name = params.get('name')
    if not name:
        raise ValidationError("Snapshot name is required")
    
    try:
        success = engine.delete_snapshot(ctx.workspace, name)
        if not success:
            raise ValidationError(f"Snapshot '{name}' not found")
        return {'deleted': True, 'name': name}
    except WorkspaceNotFoundError as e:
        raise ValidationError(str(e))


def register(dispatcher: 'Dispatcher'):
    """Register snapshot handlers with the dispatcher"""
    dispatcher.register(Commands.SNAPSHOTS_LIST, handle_list, requires_workspace=True)
    dispatcher.register(Commands.SNAPSHOTS_TAKE, handle_take, requires_workspace=True)
    dispatcher.register(Commands.SNAPSHOTS_LOAD, handle_load, requires_workspace=True)
    dispatcher.register(Commands.SNAPSHOTS_DELETE, handle_delete, requires_workspace=True)
