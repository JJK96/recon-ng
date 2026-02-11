"""
Handlers for API key commands
"""
from typing import Any, Dict, TYPE_CHECKING

from recon.shared.constants import Commands
from recon.server.context import RequestContext
from recon.server.engine import Engine
from recon.server.dispatcher import ValidationError

if TYPE_CHECKING:
    from recon.server.dispatcher import Dispatcher


def handle_list(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """List all API keys"""
    keys = engine.list_keys()
    return {'keys': keys}


def handle_get(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Get an API key value"""
    name = params.get('name')
    if not name:
        raise ValidationError("Key name is required")
    
    value = engine.get_key(name)
    if value is None:
        raise ValidationError(f"Key '{name}' not found")
    
    return {'name': name, 'value': value}


def handle_add(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Add or update an API key"""
    name = params.get('name')
    value = params.get('value')
    
    if not name:
        raise ValidationError("Key name is required")
    if value is None:
        raise ValidationError("Key value is required")
    
    engine.add_key(name, value)
    return {'added': True, 'name': name}


def handle_delete(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Delete an API key"""
    name = params.get('name')
    if not name:
        raise ValidationError("Key name is required")
    
    engine.delete_key(name)
    return {'deleted': True, 'name': name}


def register(dispatcher: 'Dispatcher'):
    """Register key handlers with the dispatcher"""
    dispatcher.register(Commands.KEYS_LIST, handle_list, requires_workspace=False)
    dispatcher.register(Commands.KEYS_GET, handle_get, requires_workspace=False)
    dispatcher.register(Commands.KEYS_ADD, handle_add, requires_workspace=False)
    dispatcher.register(Commands.KEYS_DELETE, handle_delete, requires_workspace=False)
