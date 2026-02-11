"""
Handlers for marketplace commands
"""
from typing import Any, Dict, TYPE_CHECKING

from recon.shared.constants import Commands
from recon.server.context import RequestContext
from recon.server.engine import Engine, ModuleNotFoundError
from recon.server.dispatcher import ValidationError

if TYPE_CHECKING:
    from recon.server.dispatcher import Dispatcher


def handle_search(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Search the marketplace"""
    term = params.get('term', '')
    
    modules = engine.marketplace_search(term)
    return {'modules': modules}


def handle_info(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Get information about a marketplace module"""
    path = params.get('path')
    if not path:
        raise ValidationError("Module path is required")
    
    try:
        info = engine.marketplace_info(path)
        return info
    except ModuleNotFoundError as e:
        raise ValidationError(str(e))


def handle_install(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Install a module from the marketplace"""
    path = params.get('path')
    if not path:
        raise ValidationError("Module path is required")
    
    try:
        engine.marketplace_install(path)
        return {'installed': True, 'path': path}
    except Exception as e:
        raise ValidationError(f"Failed to install module: {e}")


def handle_install_all(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Install all modules from the marketplace"""
    try:
        result = engine.marketplace_install_all()
        return result
    except Exception as e:
        raise ValidationError(f"Failed to install modules: {e}")


def handle_remove(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Remove an installed module"""
    path = params.get('path')
    if not path:
        raise ValidationError("Module path is required")
    
    try:
        engine.marketplace_remove(path)
        return {'removed': True, 'path': path}
    except Exception as e:
        raise ValidationError(f"Failed to remove module: {e}")


def handle_refresh(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Refresh the module index from the repository"""
    try:
        engine.marketplace_refresh()
        return {'refreshed': True}
    except Exception as e:
        raise ValidationError(f"Failed to refresh marketplace: {e}")


def register(dispatcher: 'Dispatcher'):
    """Register marketplace handlers with the dispatcher"""
    dispatcher.register(Commands.MARKETPLACE_SEARCH, handle_search, requires_workspace=False)
    dispatcher.register(Commands.MARKETPLACE_INFO, handle_info, requires_workspace=False)
    dispatcher.register(Commands.MARKETPLACE_INSTALL, handle_install, requires_workspace=False)
    dispatcher.register(Commands.MARKETPLACE_INSTALL_ALL, handle_install_all, requires_workspace=False)
    dispatcher.register(Commands.MARKETPLACE_REMOVE, handle_remove, requires_workspace=False)
    dispatcher.register(Commands.MARKETPLACE_REFRESH, handle_refresh, requires_workspace=False)
