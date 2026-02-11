"""
Handlers for module commands
"""
from typing import Any, Dict, TYPE_CHECKING

from recon.shared.constants import Commands
from recon.server.context import RequestContext, ExecutionContext
from recon.server.engine import Engine, ModuleNotFoundError, WorkspaceNotFoundError
from recon.server.dispatcher import ValidationError

if TYPE_CHECKING:
    from recon.server.dispatcher import Dispatcher


def handle_list(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """List available modules"""
    category = params.get('category')
    modules = engine.list_modules(category=category)
    return {'modules': modules}


def handle_search(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Search modules by term"""
    term = params.get('term')
    if not term:
        raise ValidationError("Search term is required")
    
    modules = engine.search_modules(term)
    return {'modules': modules}


def handle_load(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Load/get info for a module (prepares it for use)"""
    path = params.get('path')
    if not path:
        raise ValidationError("Module path is required")
    
    try:
        info = engine.get_module_info(path)
        return {'module': info}
    except ModuleNotFoundError as e:
        raise ValidationError(str(e))


def handle_info(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Get detailed information about a module"""
    path = params.get('path')
    if not path:
        raise ValidationError("Module path is required")
    
    try:
        info = engine.get_module_info(path)
        return info
    except ModuleNotFoundError as e:
        raise ValidationError(str(e))


def handle_run(engine: Engine, params: Dict[str, Any], ctx: ExecutionContext) -> Dict[str, Any]:
    """Run a module"""
    path = params.get('path')
    if not path:
        raise ValidationError("Module path is required")
    
    options = params.get('options', {})
    file_content = params.get('file_content')
    file_name = params.get('file_name')
    
    try:
        result = engine.run_module(
            workspace=ctx.workspace,
            path=path,
            options=options,
            global_options=ctx.global_options,
            ctx=ctx,
            file_content=file_content,
            file_name=file_name
        )
        return result
    except WorkspaceNotFoundError as e:
        raise ValidationError(str(e))
    except ModuleNotFoundError as e:
        raise ValidationError(str(e))


def handle_reload(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Reload modules"""
    path = params.get('path')  # Optional - None means reload all
    
    modules = engine.reload_modules(path=path)
    return {'reloaded': modules}


def handle_input(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Get input preview for a module based on SOURCE option"""
    path = params.get('path')
    if not path:
        raise ValidationError("Module path is required")
    
    options = params.get('options', {})
    
    try:
        result = engine.get_module_inputs(ctx.workspace, path, options)
        return result
    except WorkspaceNotFoundError as e:
        raise ValidationError(str(e))
    except ModuleNotFoundError as e:
        raise ValidationError(str(e))


def register(dispatcher: 'Dispatcher'):
    """Register module handlers with the dispatcher"""
    dispatcher.register(Commands.MODULES_LIST, handle_list, requires_workspace=False)
    dispatcher.register(Commands.MODULES_SEARCH, handle_search, requires_workspace=False)
    dispatcher.register(Commands.MODULES_LOAD, handle_load, requires_workspace=False)
    dispatcher.register(Commands.MODULES_INFO, handle_info, requires_workspace=False)
    dispatcher.register(Commands.MODULES_RUN, handle_run, requires_workspace=True, requires_context=True)
    dispatcher.register(Commands.MODULES_RELOAD, handle_reload, requires_workspace=False)
    dispatcher.register(Commands.MODULES_INPUT, handle_input, requires_workspace=True)
