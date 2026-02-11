"""
Report generators for the Recon-ng web interface.

Reports generate formatted output from workspace data.
Each report function is async and takes a Sanic request plus optional pre-fetched data.
"""
from io import BytesIO

from sanic.response import raw, html
import xlsxwriter

from recon.core.web import get_workspace
from recon.core.web.rpc import RPCClientError
from recon.core.web.utils import columnize, add_worksheet


# Report registry
REPORTS = {}


def register_report(name):
    """Decorator to register a report function"""
    def decorator(func):
        REPORTS[name] = func
        return func
    return decorator


@register_report('xlsx')
async def xlsx(request, data=None):
    """Returns an xlsx file containing the entire dataset for the current
    workspace.
    
    Args:
        request: Sanic request object
        data: Optional dict of {table_name: rows} pre-fetched data.
              If not provided, data will be fetched via RPC.
    """
    sfp = BytesIO()
    
    if data is None:
        # Fetch data via RPC
        data = {}
        try:
            rpc = request.app.ctx.rpc
            tables_result = await rpc.call('db/tables')
            tables = tables_result.get('tables', [])
            
            for table in tables:
                query_result = await rpc.call('db/query', params={'sql': f"SELECT * FROM {table}"})
                columns = query_result.get('columns', [])
                rows = query_result.get('rows', [])
                data[table] = columnize(columns, rows)
        except RPCClientError:
            # Return empty workbook on error
            pass
    
    with xlsxwriter.Workbook(sfp) as workbook:
        # Create a worksheet for each table in the data
        for table, rows in data.items():
            add_worksheet(workbook, table, rows)
    
    sfp.seek(0)
    
    workspace = get_workspace()
    return raw(
        sfp.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={
            'Content-Disposition': f'attachment; filename="{workspace}.xlsx"'
        }
    )


@register_report('pushpin')
async def pushpin(request, data=None):
    """Returns a pushpin map visualization.
    
    Args:
        request: Sanic request object
        data: Optional dict (not used, key is fetched via RPC).
    """
    # Get Google API key via RPC
    google_api_key = ''
    try:
        rpc = request.app.ctx.rpc
        result = await rpc.call('keys/get', params={'name': 'google_api'})
        key_info = result.get('key', {})
        google_api_key = key_info.get('value', '')
    except RPCClientError:
        pass
    
    # Render template using Sanic's Jinja2 extension
    rendered = await request.app.ext.render(
        'pushpin.html',
        context={'api_key': google_api_key}
    )
    return rendered
