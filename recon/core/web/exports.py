"""
Export formatters for the Recon-ng web interface.

Each export function takes a Sanic request and rows data, and returns
an appropriate Sanic response.
"""
import os
from io import BytesIO, StringIO

from dicttoxml import dicttoxml
from sanic.response import json as sanic_json, raw, ResponseStream
import requests
import unicodecsv as csv
import xlsxwriter

from recon.core.web.utils import add_worksheet, is_url


async def jsonify(request, rows):
    """Returns rows as JSON response."""
    return sanic_json({'rows': [dict(r) for r in rows]})


async def csvify(request, rows):
    """Expects a list of dictionaries and returns a CSV response."""
    if not rows:
        csv_bytes = b''
    else:
        s = BytesIO()
        keys = rows[0].keys()
        dw = csv.DictWriter(s, keys)
        dw.writeheader()
        dw.writerows([dict(r) for r in rows])
        csv_bytes = s.getvalue()
    return raw(csv_bytes, content_type='text/csv')


async def xmlify(request, rows):
    """Expects a list of dictionaries and returns an XML response."""
    xml = dicttoxml([dict(r) for r in rows])
    return raw(xml, content_type='text/xml')


async def listify(request, rows):
    """Expects a list of dictionaries and returns a continuous list of
    values from all of the provided columns."""
    columns = {}
    for row in rows:
        for column in row.keys():
            if column not in columns:
                columns[column] = []
            columns[column].append(row[column])
    s = StringIO()
    for column in columns:
        s.write('# ' + column + os.linesep)
        for value in columns[column]:
            if type(value) != str:
                value = str(value)
            s.write(value + os.linesep)
    list_str = s.getvalue()
    return raw(list_str.encode('utf-8'), content_type='text/plain')


async def xlsxify(request, rows):
    """Expects a list of dictionaries and returns an xlsx response."""
    sfp = BytesIO()
    with xlsxwriter.Workbook(sfp) as workbook:
        # Create a single worksheet for the provided rows
        add_worksheet(workbook, 'worksheet', rows)
    sfp.seek(0)
    
    return raw(
        sfp.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={
            'Content-Disposition': 'attachment; filename="export.xlsx"'
        }
    )


async def proxify(request, rows):
    """Expects a list of dictionaries containing URLs and requests them
    through a configured proxy. Returns a streaming response."""
    
    async def generate(response):
        """Async generator for streaming proxy results."""
        # Don't bother setting up if there's nothing to process
        if not rows:
            await response.write('Nothing to send to proxy.\n')
            return
        
        # Disable TLS validation warning
        requests.packages.urllib3.disable_warnings(
            requests.packages.urllib3.exceptions.InsecureRequestWarning
        )
        
        # Set static request options
        kwargs = {
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.95 Safari/537.36',
            },
            'proxies': {
                'http': 'http://127.0.0.1:8080',
                'https': 'http://127.0.0.1:8080',
            },
            'allow_redirects': False,
            'verify': False,
        }
        
        # Process the rows
        for row in [dict(r) for r in rows]:
            for key in row:
                url = row[key]
                msg = f"URL: {url}{os.linesep}Status: "
                if is_url(url):
                    try:
                        resp = requests.request('GET', url, **kwargs)
                        msg += f"HTTP {resp.status_code}: Successfully proxied."
                    except Exception as e:
                        msg += str(e)
                else:
                    msg += 'Error: Failed URL validation.'
                msg += os.linesep * 2
                await response.write(msg)
    
    return ResponseStream(generate, content_type='text/plain')
