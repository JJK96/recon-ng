"""
Handlers for dashboard commands
"""
from typing import Any, Dict, TYPE_CHECKING

from recon.shared.constants import Commands
from recon.server.context import RequestContext
from recon.server.engine import Engine, WorkspaceNotFoundError
from recon.server.dispatcher import ValidationError

if TYPE_CHECKING:
    from recon.server.dispatcher import Dispatcher


def handle_show(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Get dashboard data for the current workspace"""
    try:
        dashboard = engine.get_dashboard(ctx.workspace)
        return dashboard
    except WorkspaceNotFoundError as e:
        raise ValidationError(str(e))


def register(dispatcher: 'Dispatcher'):
    """Register dashboard handlers with the dispatcher"""
    dispatcher.register(Commands.DASHBOARD_SHOW, handle_show, requires_workspace=True)
