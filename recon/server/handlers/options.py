"""
Handlers for global options commands
"""
from typing import Any, Dict, TYPE_CHECKING

from recon.shared.constants import Commands
from recon.server.context import RequestContext
from recon.server.engine import Engine

if TYPE_CHECKING:
    from recon.server.dispatcher import Dispatcher


def handle_list(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """List all global options with their current values"""
    options = engine.get_global_options()
    return {'options': options}


def handle_defaults(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Get global option defaults (for client initialization)"""
    options = engine.get_global_options()
    # Return just the values for defaults
    defaults = {name: info['value'] for name, info in options.items()}
    return {'defaults': defaults}


def handle_goptions_list(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """List all global options with their current values"""
    options = engine.get_global_options()
    # Format as list for table display
    options_list = [
        {
            'name': name,
            'value': info['value'],
            'required': info['required'],
            'description': info['description']
        }
        for name, info in options.items()
    ]
    return {'options': options_list}


def handle_goptions_set(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Set a global option value"""
    from recon.server.dispatcher import ValidationError
    
    name = params.get('name')
    value = params.get('value')
    
    if not name:
        raise ValidationError("Option name is required")
    
    if engine.set_global_option(name, value):
        return {'success': True, 'name': name.upper(), 'value': value}
    else:
        raise ValidationError(f"Unknown option: {name}")


def handle_goptions_unset(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Unset (reset to default) a global option"""
    from recon.server.dispatcher import ValidationError
    
    name = params.get('name')
    
    if not name:
        raise ValidationError("Option name is required")
    
    if engine.unset_global_option(name):
        return {'success': True, 'name': name.upper()}
    else:
        raise ValidationError(f"Unknown option: {name}")


def register(dispatcher: 'Dispatcher'):
    """Register options handlers with the dispatcher"""
    dispatcher.register(Commands.OPTIONS_LIST, handle_list, requires_workspace=False)
    dispatcher.register(Commands.OPTIONS_DEFAULTS, handle_defaults, requires_workspace=False)
    
    # Global options commands
    dispatcher.register(Commands.GOPTIONS_LIST, handle_goptions_list, requires_workspace=False)
    dispatcher.register(Commands.GOPTIONS_SET, handle_goptions_set, requires_workspace=False)
    dispatcher.register(Commands.GOPTIONS_UNSET, handle_goptions_unset, requires_workspace=False)
