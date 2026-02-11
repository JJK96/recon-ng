"""
Handlers for database commands
"""
from typing import Any, Dict, TYPE_CHECKING

from recon.shared.constants import Commands
from recon.server.context import RequestContext
from recon.server.engine import Engine, WorkspaceNotFoundError
from recon.server.dispatcher import ValidationError

if TYPE_CHECKING:
    from recon.server.dispatcher import Dispatcher


def handle_tables(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """List tables in the workspace database"""
    try:
        tables = engine.get_tables(ctx.workspace)
        return {'tables': tables}
    except WorkspaceNotFoundError as e:
        raise ValidationError(str(e))


def handle_schema(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Get schema for a table"""
    table = params.get('table')
    if not table:
        raise ValidationError("Table name is required")
    
    try:
        columns = engine.get_columns(ctx.workspace, table)
        return {'table': table, 'columns': columns}
    except WorkspaceNotFoundError as e:
        raise ValidationError(str(e))


def handle_query(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Execute a SQL query"""
    sql = params.get('sql')
    if not sql:
        raise ValidationError("SQL query is required")
    
    try:
        result = engine.query(ctx.workspace, sql)
        return result
    except WorkspaceNotFoundError as e:
        raise ValidationError(str(e))
    except Exception as e:
        raise ValidationError(f"Query error: {e}")


def handle_insert(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Insert a record into a table"""
    table = params.get('table')
    data = params.get('data')
    
    if not table:
        raise ValidationError("Table name is required")
    if not data:
        raise ValidationError("Data is required")
    
    try:
        rowid = engine.insert(ctx.workspace, table, data)
        return {'affected': 1, 'rowid': rowid}
    except WorkspaceNotFoundError as e:
        raise ValidationError(str(e))
    except Exception as e:
        raise ValidationError(f"Insert error: {e}")


def handle_delete(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Delete records from a table"""
    table = params.get('table')
    rowids = params.get('rowids')
    
    if not table:
        raise ValidationError("Table name is required")
    if not rowids:
        raise ValidationError("Row IDs are required")
    
    try:
        count = engine.delete(ctx.workspace, table, rowids)
        return {'affected': count}
    except WorkspaceNotFoundError as e:
        raise ValidationError(str(e))
    except Exception as e:
        raise ValidationError(f"Delete error: {e}")


def handle_export(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Export table data"""
    table = params.get('table')
    if not table:
        raise ValidationError("Table name is required")
    
    format = params.get('format', 'list')
    column = params.get('column')
    unique = params.get('unique', True)
    include_nulls = params.get('include_nulls', False)
    
    try:
        result = engine.export_table(
            ctx.workspace,
            table,
            format=format,
            column=column,
            unique=unique,
            include_nulls=include_nulls
        )
        return result
    except WorkspaceNotFoundError as e:
        raise ValidationError(str(e))
    except Exception as e:
        raise ValidationError(f"Export error: {e}")


def handle_notes(engine: Engine, params: Dict[str, Any], ctx: RequestContext) -> Dict[str, Any]:
    """Update notes for rows in a table"""
    table = params.get('table')
    rowids = params.get('rowids', [])
    note = params.get('note', '')
    
    if not table:
        raise ValidationError("Table name is required")
    if not rowids:
        raise ValidationError("Row ID(s) required")
    
    try:
        count = engine.update_notes(ctx.workspace, table, rowids, note)
        return {'affected': count}
    except WorkspaceNotFoundError as e:
        raise ValidationError(str(e))
    except Exception as e:
        raise ValidationError(f"Notes update error: {e}")


def register(dispatcher: 'Dispatcher'):
    """Register database handlers with the dispatcher"""
    dispatcher.register(Commands.DB_TABLES, handle_tables, requires_workspace=True)
    dispatcher.register(Commands.DB_SCHEMA, handle_schema, requires_workspace=True)
    dispatcher.register(Commands.DB_QUERY, handle_query, requires_workspace=True)
    dispatcher.register(Commands.DB_INSERT, handle_insert, requires_workspace=True)
    dispatcher.register(Commands.DB_DELETE, handle_delete, requires_workspace=True)
    dispatcher.register(Commands.DB_NOTES, handle_notes, requires_workspace=True)
    dispatcher.register(Commands.DB_EXPORT, handle_export, requires_workspace=True)
