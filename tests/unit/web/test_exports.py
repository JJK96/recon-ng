"""
Unit tests for web export functions.

Tests export functionality for various formats:
- JSON (_jsonify)
- CSV (csvify)
- XML (xmlify)
- List (listify)
- XLSX (xlsxify)
- Proxy (proxify)

Note: These tests require Flask to be installed.
"""
import os
import sys
import json
from io import BytesIO, StringIO
from unittest.mock import MagicMock, patch

import pytest

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# Check if Flask is available - skip entire module if not
flask_available = True
try:
    import flask
except ImportError:
    flask_available = False

pytestmark = pytest.mark.skipif(
    not flask_available,
    reason="Flask not installed - web tests require Flask"
)


# =============================================================================
# SAMPLE DATA
# =============================================================================

SAMPLE_ROWS = [
    {'domain': 'example.com', 'notes': 'Primary domain', 'module': 'test'},
    {'domain': 'example.org', 'notes': 'Secondary domain', 'module': 'test'},
    {'domain': 'test.com', 'notes': 'Test domain', 'module': 'other'},
]

SAMPLE_HOSTS = [
    {'host': 'www.example.com', 'ip': '192.0.2.1', 'country': 'US'},
    {'host': 'mail.example.com', 'ip': '192.0.2.2', 'country': 'US'},
]

SAMPLE_URLS = [
    {'url': 'https://example.com/page1', 'status': '200'},
    {'url': 'https://example.org/page2', 'status': '301'},
    {'url': 'not-a-valid-url', 'status': 'N/A'},
]


# =============================================================================
# JSON EXPORT TESTS
# =============================================================================

@pytest.mark.unit
class TestJsonify:
    """Tests for JSON export function."""
    
    def test_jsonify_returns_json_response(self):
        """Test _jsonify returns JSON response."""
        from recon.core.web.exports import _jsonify
        
        with patch('recon.core.web.exports.jsonify') as mock_jsonify:
            mock_jsonify.return_value = MagicMock()
            
            result = _jsonify(SAMPLE_ROWS)
            
            mock_jsonify.assert_called_once()
    
    def test_jsonify_converts_rows_to_dicts(self):
        """Test _jsonify converts rows to dictionaries."""
        from recon.core.web.exports import _jsonify
        
        with patch('recon.core.web.exports.jsonify') as mock_jsonify:
            mock_response = MagicMock()
            mock_jsonify.return_value = mock_response
            
            result = _jsonify(SAMPLE_ROWS)
            
            # Check the call was made with rows key
            call_kwargs = mock_jsonify.call_args
            assert 'rows' in call_kwargs.kwargs or 'rows' in str(call_kwargs)
    
    def test_jsonify_empty_rows(self):
        """Test _jsonify handles empty rows list."""
        from recon.core.web.exports import _jsonify
        
        with patch('recon.core.web.exports.jsonify') as mock_jsonify:
            mock_jsonify.return_value = MagicMock()
            
            result = _jsonify([])
            
            mock_jsonify.assert_called_once()


# =============================================================================
# CSV EXPORT TESTS
# =============================================================================

@pytest.mark.unit
class TestCsvify:
    """Tests for CSV export function."""
    
    def test_csvify_returns_response(self):
        """Test csvify returns a Flask Response."""
        from recon.core.web.exports import csvify
        
        with patch('recon.core.web.exports.Response') as mock_response:
            mock_response.return_value = MagicMock()
            
            result = csvify(SAMPLE_ROWS)
            
            mock_response.assert_called_once()
    
    def test_csvify_sets_csv_mimetype(self):
        """Test csvify sets correct MIME type."""
        from recon.core.web.exports import csvify
        
        with patch('recon.core.web.exports.Response') as mock_response:
            mock_response.return_value = MagicMock()
            
            result = csvify(SAMPLE_ROWS)
            
            call_kwargs = mock_response.call_args
            assert call_kwargs.kwargs.get('mimetype') == 'text/csv'
    
    def test_csvify_empty_rows(self):
        """Test csvify handles empty rows list."""
        from recon.core.web.exports import csvify
        
        with patch('recon.core.web.exports.Response') as mock_response:
            mock_response.return_value = MagicMock()
            
            result = csvify([])
            
            # Should be called with empty string
            call_args = mock_response.call_args
            assert call_args.args[0] == ''
    
    def test_csvify_includes_header(self):
        """Test csvify includes header row."""
        from recon.core.web.exports import csvify
        
        with patch('recon.core.web.exports.Response') as mock_response:
            mock_response.return_value = MagicMock()
            
            result = csvify(SAMPLE_ROWS)
            
            call_args = mock_response.call_args
            csv_content = call_args.args[0]
            
            # Content should include column names
            assert b'domain' in csv_content or 'domain' in str(csv_content)


# =============================================================================
# XML EXPORT TESTS
# =============================================================================

@pytest.mark.unit
class TestXmlify:
    """Tests for XML export function."""
    
    def test_xmlify_returns_response(self):
        """Test xmlify returns a Flask Response."""
        from recon.core.web.exports import xmlify
        
        with patch('recon.core.web.exports.Response') as mock_response, \
             patch('recon.core.web.exports.dicttoxml') as mock_dicttoxml:
            mock_response.return_value = MagicMock()
            mock_dicttoxml.return_value = b'<xml></xml>'
            
            result = xmlify(SAMPLE_ROWS)
            
            mock_response.assert_called_once()
    
    def test_xmlify_sets_xml_mimetype(self):
        """Test xmlify sets correct MIME type."""
        from recon.core.web.exports import xmlify
        
        with patch('recon.core.web.exports.Response') as mock_response, \
             patch('recon.core.web.exports.dicttoxml') as mock_dicttoxml:
            mock_response.return_value = MagicMock()
            mock_dicttoxml.return_value = b'<xml></xml>'
            
            result = xmlify(SAMPLE_ROWS)
            
            call_kwargs = mock_response.call_args
            assert call_kwargs.kwargs.get('mimetype') == 'text/xml'
    
    def test_xmlify_uses_dicttoxml(self):
        """Test xmlify uses dicttoxml library."""
        from recon.core.web.exports import xmlify
        
        with patch('recon.core.web.exports.Response') as mock_response, \
             patch('recon.core.web.exports.dicttoxml') as mock_dicttoxml:
            mock_response.return_value = MagicMock()
            mock_dicttoxml.return_value = b'<xml></xml>'
            
            result = xmlify(SAMPLE_ROWS)
            
            mock_dicttoxml.assert_called_once()


# =============================================================================
# LIST EXPORT TESTS
# =============================================================================

@pytest.mark.unit
class TestListify:
    """Tests for list export function."""
    
    def test_listify_returns_response(self):
        """Test listify returns a Flask Response."""
        from recon.core.web.exports import listify
        
        with patch('recon.core.web.exports.Response') as mock_response:
            mock_response.return_value = MagicMock()
            
            result = listify(SAMPLE_ROWS)
            
            mock_response.assert_called_once()
    
    def test_listify_sets_plain_mimetype(self):
        """Test listify sets plain text MIME type."""
        from recon.core.web.exports import listify
        
        with patch('recon.core.web.exports.Response') as mock_response:
            mock_response.return_value = MagicMock()
            
            result = listify(SAMPLE_ROWS)
            
            call_kwargs = mock_response.call_args
            assert call_kwargs.kwargs.get('mimetype') == 'text/plain'
    
    def test_listify_groups_by_column(self):
        """Test listify groups values by column."""
        from recon.core.web.exports import listify
        
        with patch('recon.core.web.exports.Response') as mock_response:
            mock_response.return_value = MagicMock()
            
            result = listify(SAMPLE_ROWS)
            
            call_args = mock_response.call_args
            content = call_args.args[0]
            
            # Should contain column headers
            assert '# domain' in content or 'domain' in content
    
    def test_listify_empty_rows(self):
        """Test listify handles empty rows list."""
        from recon.core.web.exports import listify
        
        with patch('recon.core.web.exports.Response') as mock_response:
            mock_response.return_value = MagicMock()
            
            result = listify([])
            
            # Should be called with empty content
            call_args = mock_response.call_args
            assert call_args.args[0] == ''


# =============================================================================
# XLSX EXPORT TESTS
# =============================================================================

@pytest.mark.unit
class TestXlsxify:
    """Tests for XLSX export function."""
    
    def test_xlsxify_returns_file_response(self):
        """Test xlsxify returns send_file response."""
        from recon.core.web.exports import xlsxify
        
        with patch('recon.core.web.exports.send_file') as mock_send, \
             patch('recon.core.web.exports.xlsxwriter.Workbook') as mock_workbook:
            mock_send.return_value = MagicMock()
            mock_wb_instance = MagicMock()
            mock_workbook.return_value.__enter__ = MagicMock(return_value=mock_wb_instance)
            mock_workbook.return_value.__exit__ = MagicMock(return_value=False)
            
            result = xlsxify(SAMPLE_ROWS)
            
            mock_send.assert_called_once()
    
    def test_xlsxify_sets_correct_mimetype(self):
        """Test xlsxify sets XLSX MIME type."""
        from recon.core.web.exports import xlsxify
        
        with patch('recon.core.web.exports.send_file') as mock_send, \
             patch('recon.core.web.exports.xlsxwriter.Workbook') as mock_workbook:
            mock_send.return_value = MagicMock()
            mock_wb_instance = MagicMock()
            mock_workbook.return_value.__enter__ = MagicMock(return_value=mock_wb_instance)
            mock_workbook.return_value.__exit__ = MagicMock(return_value=False)
            
            result = xlsxify(SAMPLE_ROWS)
            
            call_kwargs = mock_send.call_args
            assert 'spreadsheetml' in call_kwargs.kwargs.get('mimetype', '')
    
    def test_xlsxify_creates_workbook(self):
        """Test xlsxify creates an xlsxwriter workbook."""
        from recon.core.web.exports import xlsxify
        
        with patch('recon.core.web.exports.send_file') as mock_send, \
             patch('recon.core.web.exports.xlsxwriter.Workbook') as mock_workbook:
            mock_send.return_value = MagicMock()
            mock_wb_instance = MagicMock()
            mock_workbook.return_value.__enter__ = MagicMock(return_value=mock_wb_instance)
            mock_workbook.return_value.__exit__ = MagicMock(return_value=False)
            
            result = xlsxify(SAMPLE_ROWS)
            
            mock_workbook.assert_called_once()
    
    def test_xlsxify_uses_add_worksheet_helper(self):
        """Test xlsxify uses add_worksheet helper function."""
        from recon.core.web.exports import xlsxify
        
        with patch('recon.core.web.exports.send_file') as mock_send, \
             patch('recon.core.web.exports.xlsxwriter.Workbook') as mock_workbook, \
             patch('recon.core.web.exports.add_worksheet') as mock_add_ws:
            mock_send.return_value = MagicMock()
            mock_wb_instance = MagicMock()
            mock_workbook.return_value.__enter__ = MagicMock(return_value=mock_wb_instance)
            mock_workbook.return_value.__exit__ = MagicMock(return_value=False)
            
            result = xlsxify(SAMPLE_ROWS)
            
            mock_add_ws.assert_called_once()


# =============================================================================
# PROXIFY TESTS
# =============================================================================

@pytest.mark.unit
class TestProxify:
    """Tests for proxy export function."""
    
    def test_proxify_returns_response(self):
        """Test proxify returns a Flask Response."""
        from recon.core.web.exports import proxify
        
        with patch('recon.core.web.exports.Response') as mock_response, \
             patch('recon.core.web.exports.stream_with_context') as mock_stream:
            mock_response.return_value = MagicMock()
            mock_stream.return_value = MagicMock()
            
            result = proxify([])
            
            mock_response.assert_called_once()
    
    def test_proxify_sets_plain_mimetype(self):
        """Test proxify sets plain text MIME type."""
        from recon.core.web.exports import proxify
        
        with patch('recon.core.web.exports.Response') as mock_response, \
             patch('recon.core.web.exports.stream_with_context') as mock_stream:
            mock_response.return_value = MagicMock()
            mock_stream.return_value = MagicMock()
            
            result = proxify([])
            
            call_kwargs = mock_response.call_args
            assert call_kwargs.kwargs.get('mimetype') == 'text/plain'
    
    def test_proxify_empty_rows_message(self):
        """Test proxify handles empty rows with appropriate message."""
        from recon.core.web.exports import proxify
        
        # The generate function inside proxify yields a message for empty rows
        with patch('recon.core.web.exports.Response') as mock_response, \
             patch('recon.core.web.exports.stream_with_context') as mock_stream:
            mock_response.return_value = MagicMock()
            
            # Capture the generator
            def capture_stream(gen):
                return gen
            
            mock_stream.side_effect = capture_stream
            
            result = proxify([])
            
            # The generator is passed to Response
            mock_response.assert_called_once()


# =============================================================================
# UTILITY FUNCTION TESTS
# =============================================================================

@pytest.mark.unit
class TestColumnize:
    """Tests for columnize utility function."""
    
    def test_columnize_converts_rows(self):
        """Test columnize converts tuple rows to dicts."""
        from recon.core.web.utils import columnize
        
        columns = ['domain', 'notes', 'module']
        rows = [
            ('example.com', 'Test domain', 'test_module'),
            ('example.org', 'Another domain', 'test_module'),
        ]
        
        result = columnize(columns, rows)
        
        assert len(result) == 2
        assert result[0]['domain'] == 'example.com'
        assert result[0]['notes'] == 'Test domain'
        assert result[1]['domain'] == 'example.org'
    
    def test_columnize_empty_rows(self):
        """Test columnize handles empty rows."""
        from recon.core.web.utils import columnize
        
        columns = ['domain', 'notes']
        rows = []
        
        result = columnize(columns, rows)
        
        assert result == []
    
    def test_columnize_single_column(self):
        """Test columnize with single column."""
        from recon.core.web.utils import columnize
        
        columns = ['domain']
        rows = [('example.com',), ('example.org',)]
        
        result = columnize(columns, rows)
        
        assert len(result) == 2
        assert result[0] == {'domain': 'example.com'}


@pytest.mark.unit
class TestAddWorksheet:
    """Tests for add_worksheet utility function."""
    
    def test_add_worksheet_creates_worksheet(self):
        """Test add_worksheet creates a worksheet."""
        from recon.core.web.utils import add_worksheet
        
        mock_workbook = MagicMock()
        mock_worksheet = MagicMock()
        mock_workbook.add_worksheet.return_value = mock_worksheet
        
        rows = [
            {'domain': 'example.com', 'notes': 'Test'},
        ]
        
        add_worksheet(mock_workbook, 'test_sheet', rows)
        
        mock_workbook.add_worksheet.assert_called_once_with('test_sheet')
    
    def test_add_worksheet_writes_header(self):
        """Test add_worksheet writes header row."""
        from recon.core.web.utils import add_worksheet
        
        mock_workbook = MagicMock()
        mock_worksheet = MagicMock()
        mock_workbook.add_worksheet.return_value = mock_worksheet
        
        rows = [
            {'domain': 'example.com', 'notes': 'Test'},
        ]
        
        add_worksheet(mock_workbook, 'test_sheet', rows)
        
        # Should have written header and data
        assert mock_worksheet.write.call_count >= 2
    
    def test_add_worksheet_empty_rows(self):
        """Test add_worksheet handles empty rows."""
        from recon.core.web.utils import add_worksheet
        
        mock_workbook = MagicMock()
        mock_worksheet = MagicMock()
        mock_workbook.add_worksheet.return_value = mock_worksheet
        
        add_worksheet(mock_workbook, 'test_sheet', [])
        
        mock_workbook.add_worksheet.assert_called_once()
        # Should not write anything for empty rows
        mock_worksheet.write.assert_not_called()


@pytest.mark.unit
class TestIsUrl:
    """Tests for is_url utility function."""
    
    def test_is_url_valid_http(self):
        """Test is_url validates HTTP URLs."""
        from recon.core.web.utils import is_url
        
        assert is_url('http://example.com') is True
        assert is_url('http://www.example.com') is True
        assert is_url('http://example.com/path') is True
    
    def test_is_url_valid_https(self):
        """Test is_url validates HTTPS URLs."""
        from recon.core.web.utils import is_url
        
        assert is_url('https://example.com') is True
        assert is_url('https://secure.example.com') is True
    
    def test_is_url_valid_ftp(self):
        """Test is_url validates FTP URLs."""
        from recon.core.web.utils import is_url
        
        assert is_url('ftp://ftp.example.com') is True
    
    def test_is_url_with_port(self):
        """Test is_url validates URLs with port."""
        from recon.core.web.utils import is_url
        
        assert is_url('http://example.com:8080') is True
        assert is_url('https://example.com:443') is True
    
    def test_is_url_with_path_and_query(self):
        """Test is_url validates URLs with path and query string."""
        from recon.core.web.utils import is_url
        
        assert is_url('http://example.com/path/to/page') is True
        assert is_url('http://example.com/page?key=value') is True
    
    def test_is_url_invalid_strings(self):
        """Test is_url rejects invalid strings."""
        from recon.core.web.utils import is_url
        
        assert is_url('not a url') is False
        assert is_url('example.com') is False  # No protocol
        assert is_url('') is False
    
    def test_is_url_non_string(self):
        """Test is_url handles non-string input."""
        from recon.core.web.utils import is_url
        
        assert is_url(None) is False
        assert is_url(123) is False
        assert is_url(['http://example.com']) is False
    
    def test_is_url_ip_address(self):
        """Test is_url validates URLs with IP addresses."""
        from recon.core.web.utils import is_url
        
        # Public IP addresses should work
        assert is_url('http://93.184.216.34') is True
        assert is_url('http://192.0.2.1:8080') is True


# =============================================================================
# CONSTANTS TESTS
# =============================================================================

@pytest.mark.unit
class TestExportsConstants:
    """Tests for export constants."""
    
    def test_exports_dict_contains_formats(self):
        """Test EXPORTS dict contains all expected formats."""
        from recon.core.web.constants import EXPORTS
        
        assert 'json' in EXPORTS
        assert 'csv' in EXPORTS
        assert 'xml' in EXPORTS
        assert 'list' in EXPORTS
        assert 'xlsx' in EXPORTS
        assert 'proxy' in EXPORTS
    
    def test_exports_values_are_callable(self):
        """Test EXPORTS values are callable functions."""
        from recon.core.web.constants import EXPORTS
        
        for format_name, func in EXPORTS.items():
            assert callable(func), f"EXPORTS['{format_name}'] is not callable"
    
    def test_reports_dict_contains_formats(self):
        """Test REPORTS dict contains expected report types."""
        from recon.core.web.constants import REPORTS
        
        assert 'xlsx' in REPORTS
        assert 'pushpin' in REPORTS
    
    def test_reports_values_are_callable(self):
        """Test REPORTS values are callable functions."""
        from recon.core.web.constants import REPORTS
        
        for report_name, func in REPORTS.items():
            assert callable(func), f"REPORTS['{report_name}'] is not callable"
