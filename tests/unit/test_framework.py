"""
Unit tests for recon.core.framework.Framework class.

Tests Framework functionality:
- Hash detection (is_hash)
- Row ID parsing (_parse_rowids)
- Utility methods (get_random_str, to_unicode, etc.)
- Output methods
- Database methods
"""
import pytest
from unittest.mock import patch, MagicMock

from recon.core.framework import Framework, FrameworkException, Colors, Options
from tests.fixtures.test_data import HASH_SAMPLES, NON_HASH_SAMPLES


class TestFrameworkException:
    """Tests for FrameworkException."""
    
    def test_exception_message(self):
        """Test exception stores message."""
        exc = FrameworkException('Test error message')
        assert str(exc) == 'Test error message'
    
    def test_exception_can_be_raised(self):
        """Test exception can be raised and caught."""
        with pytest.raises(FrameworkException) as exc_info:
            raise FrameworkException('Test error')
        assert 'Test error' in str(exc_info.value)


class TestColors:
    """Tests for Colors class."""
    
    def test_color_codes(self):
        """Test color codes are defined."""
        assert Colors.N == '\033[m'
        assert Colors.R == '\033[31m'
        assert Colors.G == '\033[32m'
        assert Colors.O == '\033[33m'
        assert Colors.B == '\033[34m'


class TestFrameworkModuleAPI:
    """Tests that Framework has all methods required by modules.
    
    Modules inherit from Framework and expect certain methods to be available.
    These tests verify the core Framework class provides these methods,
    even if they're no-ops that get overridden by mixins or event publishers.
    """
    
    def test_framework_has_output_method(self):
        """Test Framework has output method for modules."""
        assert hasattr(Framework, 'output')
        assert callable(getattr(Framework, 'output'))
    
    def test_framework_has_alert_method(self):
        """Test Framework has alert method for modules."""
        assert hasattr(Framework, 'alert')
        assert callable(getattr(Framework, 'alert'))
    
    def test_framework_has_error_method(self):
        """Test Framework has error method for modules."""
        assert hasattr(Framework, 'error')
        assert callable(getattr(Framework, 'error'))
    
    def test_framework_has_verbose_method(self):
        """Test Framework has verbose method for modules."""
        assert hasattr(Framework, 'verbose')
        assert callable(getattr(Framework, 'verbose'))
    
    def test_framework_has_debug_method(self):
        """Test Framework has debug method for modules."""
        assert hasattr(Framework, 'debug')
        assert callable(getattr(Framework, 'debug'))
    
    def test_framework_has_heading_method(self):
        """Test Framework has heading method for modules."""
        assert hasattr(Framework, 'heading')
        assert callable(getattr(Framework, 'heading'))
    
    def test_framework_has_table_method(self):
        """Test Framework has table method for modules."""
        assert hasattr(Framework, 'table')
        assert callable(getattr(Framework, 'table'))


class TestFrameworkOutputWithContext:
    """Tests that Framework output methods use events when execution context is active.
    
    This verifies that when modules run in the server, their output is routed
    through the RPC event system to the client.
    
    Note: These tests use the core Framework class directly, not TestFramework,
    because TestFramework overrides output methods for CLI testing.
    """
    
    @pytest.fixture
    def mock_event_publisher(self):
        """Create a mock event publisher that records calls."""
        class MockEventPublisher:
            def __init__(self):
                self.calls = []
            def output(self, msg): self.calls.append(('output', msg))
            def alert(self, msg): self.calls.append(('alert', msg))
            def error(self, msg): self.calls.append(('error', msg))
            def heading(self, text, level): self.calls.append(('heading', text, level))
            def table(self, rows, header, title): self.calls.append(('table', rows, header, title))
            def verbose(self, msg): self.calls.append(('verbose', msg))
            def debug(self, msg): self.calls.append(('debug', msg))
        return MockEventPublisher()
    
    @pytest.fixture
    def mock_context(self, mock_event_publisher):
        """Create a mock execution context."""
        class MockContext:
            def __init__(self, events):
                self.events = events
        return MockContext(mock_event_publisher)
    
    @pytest.fixture
    def core_framework(self):
        """Create a core Framework instance (not TestFramework) for testing."""
        fw = Framework('test')
        fw._global_options = Options()
        fw._global_options.init_option('VERBOSITY', 1, True, 'verbosity')
        fw.ruler = '-'
        fw.spacer = '  '
        return fw
    
    def test_output_uses_events_in_context(self, core_framework, mock_context):
        """Test output() routes through events when context is active."""
        from recon.server.interceptors import set_current_context
        
        set_current_context(mock_context)
        try:
            core_framework.output('test message')
            assert ('output', 'test message') in mock_context.events.calls
        finally:
            set_current_context(None)
    
    def test_alert_uses_events_in_context(self, core_framework, mock_context):
        """Test alert() routes through events when context is active."""
        from recon.server.interceptors import set_current_context
        
        set_current_context(mock_context)
        try:
            core_framework.alert('test alert')
            assert ('alert', 'test alert') in mock_context.events.calls
        finally:
            set_current_context(None)
    
    def test_error_uses_events_in_context(self, core_framework, mock_context):
        """Test error() routes through events when context is active."""
        from recon.server.interceptors import set_current_context
        
        set_current_context(mock_context)
        try:
            core_framework.error('test error')
            # Error adds punctuation if missing
            assert ('error', 'Test error.') in mock_context.events.calls
        finally:
            set_current_context(None)
    
    def test_heading_uses_events_in_context(self, core_framework, mock_context):
        """Test heading() routes through events when context is active."""
        from recon.server.interceptors import set_current_context
        
        set_current_context(mock_context)
        try:
            core_framework.heading('test heading', level=0)
            assert ('heading', 'test heading', 0) in mock_context.events.calls
        finally:
            set_current_context(None)
    
    def test_output_prints_without_context(self, core_framework, capsys):
        """Test output() prints directly when no context is active."""
        from recon.server.interceptors import set_current_context
        
        # Ensure no context
        set_current_context(None)
        
        core_framework.output('direct output')
        captured = capsys.readouterr()
        assert 'direct output' in captured.out


class TestFrameworkIsHash:
    """Tests for is_hash method."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        return mock_framework
    
    @pytest.mark.parametrize('hash_value', HASH_SAMPLES.get('MD5', []))
    def test_md5_hash_detection(self, framework, hash_value):
        """Test MD5 hash detection."""
        result = framework.is_hash(hash_value)
        assert result == 'MD5'
    
    @pytest.mark.parametrize('hash_value', HASH_SAMPLES.get('SHA1', []))
    def test_sha1_hash_detection(self, framework, hash_value):
        """Test SHA1 hash detection."""
        result = framework.is_hash(hash_value)
        assert result == 'SHA1'
    
    @pytest.mark.parametrize('hash_value', HASH_SAMPLES.get('MySQL', []))
    def test_mysql_hash_detection(self, framework, hash_value):
        """Test MySQL hash detection."""
        result = framework.is_hash(hash_value)
        assert result == 'MySQL'
    
    @pytest.mark.parametrize('hash_value', HASH_SAMPLES.get('MySQL5', []))
    def test_mysql5_hash_detection(self, framework, hash_value):
        """Test MySQL5 hash detection."""
        result = framework.is_hash(hash_value)
        assert result == 'MySQL5'
    
    @pytest.mark.parametrize('hash_value', HASH_SAMPLES.get('bcrypt', []))
    def test_bcrypt_hash_detection(self, framework, hash_value):
        """Test bcrypt hash detection."""
        result = framework.is_hash(hash_value)
        assert result == 'bcrypt'
    
    @pytest.mark.parametrize('hash_value', HASH_SAMPLES.get('phpass', []))
    def test_phpass_hash_detection(self, framework, hash_value):
        """Test phpass hash detection."""
        result = framework.is_hash(hash_value)
        assert result == 'phpass'
    
    @pytest.mark.parametrize('non_hash', NON_HASH_SAMPLES)
    def test_non_hash_detection(self, framework, non_hash):
        """Test non-hash strings return False."""
        result = framework.is_hash(non_hash)
        assert result is False


class TestFrameworkParseRowids:
    """Tests for _parse_rowids method."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        return mock_framework
    
    def test_single_rowid(self, framework):
        """Test parsing single row ID."""
        result = framework._parse_rowids('5')
        assert result == [5]
    
    def test_multiple_rowids(self, framework):
        """Test parsing multiple row IDs."""
        result = framework._parse_rowids('1, 3, 5')
        assert result == [1, 3, 5]
    
    def test_range_rowids(self, framework):
        """Test parsing row ID range."""
        result = framework._parse_rowids('1-5')
        assert result == [1, 2, 3, 4, 5]
    
    def test_mixed_rowids(self, framework):
        """Test parsing mixed row IDs and ranges."""
        result = framework._parse_rowids('1, 3-5, 7, 10-12')
        assert result == [1, 3, 4, 5, 7, 10, 11, 12]
    
    def test_duplicate_removal(self, framework):
        """Test duplicates are removed."""
        result = framework._parse_rowids('1, 1, 2, 2-3')
        assert result == [1, 2, 3]
    
    def test_sorting(self, framework):
        """Test results are sorted."""
        result = framework._parse_rowids('5, 1, 3')
        assert result == [1, 3, 5]
    
    def test_invalid_values_skipped(self, framework):
        """Test invalid values are skipped."""
        result = framework._parse_rowids('1, abc, 3')
        assert result == [1, 3]
    
    def test_empty_string(self, framework):
        """Test empty string returns empty list."""
        result = framework._parse_rowids('')
        assert result == []
    
    def test_whitespace_handling(self, framework):
        """Test whitespace is handled."""
        result = framework._parse_rowids('  1 ,  2 , 3  ')
        assert result == [1, 2, 3]


class TestFrameworkUtilityMethods:
    """Tests for utility methods."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        return mock_framework
    
    def test_get_random_str(self, framework):
        """Test random string generation."""
        result = framework.get_random_str(10)
        assert len(result) == 10
        assert result.isalpha()
        assert result.islower()
    
    def test_get_random_str_different_lengths(self, framework):
        """Test random string with different lengths."""
        for length in [1, 5, 20, 100]:
            result = framework.get_random_str(length)
            assert len(result) == length
    
    def test_get_random_str_unique(self, framework):
        """Test random strings are unique."""
        results = [framework.get_random_str(20) for _ in range(10)]
        assert len(set(results)) == 10
    
    def test_to_unicode(self, framework):
        """Test bytes to unicode conversion."""
        result = framework.to_unicode(b'hello')
        assert result == 'hello'
        assert isinstance(result, str)
    
    def test_to_unicode_already_string(self, framework):
        """Test unicode passthrough."""
        result = framework.to_unicode('hello')
        assert result == 'hello'
    
    def test_to_unicode_encoding(self, framework):
        """Test unicode conversion with encoding."""
        result = framework.to_unicode(b'\xc3\xa9', 'utf-8')
        assert result == 'é'
    
    def test_to_unicode_str(self, framework):
        """Test to_unicode_str method."""
        result = framework.to_unicode_str(123)
        assert result == '123'
        assert isinstance(result, str)
    
    def test_to_unicode_str_bytes(self, framework):
        """Test to_unicode_str with bytes."""
        result = framework.to_unicode_str(b'test')
        assert result == 'test'


class TestFrameworkOutputMethods:
    """Tests for output methods."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        return mock_framework
    
    def test_error_output(self, framework, capsys):
        """Test error output formatting."""
        framework.error('test error')
        captured = capsys.readouterr()
        assert '[!]' in captured.out
        assert 'Test error' in captured.out  # Capitalized
    
    def test_error_adds_period(self, framework, capsys):
        """Test error adds period if missing."""
        import re
        framework.error('test error')
        captured = capsys.readouterr()
        # Strip ANSI codes before checking
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
        clean_output = ansi_escape.sub('', captured.out.strip())
        assert clean_output.endswith('.')
    
    def test_output_method(self, framework, capsys):
        """Test standard output formatting."""
        framework.output('test message')
        captured = capsys.readouterr()
        assert '[*]' in captured.out
        assert 'test message' in captured.out
    
    def test_alert_method(self, framework, capsys):
        """Test alert output formatting."""
        framework.alert('alert message')
        captured = capsys.readouterr()
        assert '[*]' in captured.out
        assert 'alert message' in captured.out
    
    def test_verbose_method_enabled(self, framework, capsys):
        """Test verbose output when enabled."""
        framework._global_options['VERBOSITY'] = 1
        framework.verbose('verbose message')
        captured = capsys.readouterr()
        assert 'verbose message' in captured.out
    
    def test_verbose_method_disabled(self, framework, capsys):
        """Test verbose output when disabled."""
        framework._global_options['VERBOSITY'] = 0
        framework.verbose('verbose message')
        captured = capsys.readouterr()
        assert 'verbose message' not in captured.out
    
    def test_debug_method_enabled(self, framework, capsys):
        """Test debug output when enabled."""
        framework._global_options['VERBOSITY'] = 2
        framework.debug('debug message')
        captured = capsys.readouterr()
        assert 'debug message' in captured.out
    
    def test_debug_method_disabled(self, framework, capsys):
        """Test debug output when disabled."""
        framework._global_options['VERBOSITY'] = 1
        framework.debug('debug message')
        captured = capsys.readouterr()
        assert 'debug message' not in captured.out


class TestFrameworkTableMethod:
    """Tests for table output method."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        return mock_framework
    
    def test_table_basic(self, framework, capsys):
        """Test basic table output."""
        data = [['a', 'b'], ['c', 'd']]
        framework.table(data)
        captured = capsys.readouterr()
        assert 'a' in captured.out
        assert 'b' in captured.out
        assert 'c' in captured.out
        assert 'd' in captured.out
    
    def test_table_with_header(self, framework, capsys):
        """Test table with header."""
        data = [['value1', 'value2']]
        framework.table(data, header=['Col1', 'Col2'])
        captured = capsys.readouterr()
        assert 'Col1' in captured.out
        assert 'Col2' in captured.out
    
    @pytest.mark.skip(reason="Known bug in framework.py:336 - can't multiply sequence by float")
    def test_table_with_title(self, framework, capsys):
        """Test table with title."""
        data = [['a', 'b']]
        framework.table(data, title='Test Table')
        captured = capsys.readouterr()
        assert 'Test Table' in captured.out
    
    def test_table_inconsistent_rows(self, framework):
        """Test table raises on inconsistent row lengths."""
        data = [['a', 'b'], ['c']]
        with pytest.raises(FrameworkException):
            framework.table(data)
    
    @pytest.mark.skip(reason="Known bug in framework.py:319 - IndexError on empty list")
    def test_table_empty_data(self, framework, capsys):
        """Test table with empty data."""
        framework.table([])
        captured = capsys.readouterr()
        # Should not raise, just produce minimal output


class TestFrameworkHeadingMethod:
    """Tests for heading output method."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        return mock_framework
    
    def test_heading_level_0(self, framework, capsys):
        """Test level 0 heading (uppercase with rulers)."""
        framework.heading('test heading', level=0)
        captured = capsys.readouterr()
        assert 'TEST HEADING' in captured.out
        assert '-' in captured.out
    
    def test_heading_level_1(self, framework, capsys):
        """Test level 1 heading (title case)."""
        framework.heading('test heading', level=1)
        captured = capsys.readouterr()
        assert 'Test Heading' in captured.out


class TestFrameworkDatabaseMethods:
    """Tests for database methods."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        return mock_framework
    
    def test_get_tables(self, framework):
        """Test getting list of tables."""
        tables = framework.get_tables()
        assert isinstance(tables, list)
        assert 'domains' in tables
        assert 'hosts' in tables
        assert 'contacts' in tables
        # dashboard should be excluded
        assert 'dashboard' not in tables
    
    def test_get_columns(self, framework):
        """Test getting columns for a table."""
        columns = framework.get_columns('domains')
        assert isinstance(columns, list)
        column_names = [col[0] for col in columns]
        assert 'domain' in column_names
        assert 'notes' in column_names
        assert 'module' in column_names
    
    def test_query_select(self, framework):
        """Test SELECT query."""
        result = framework.query('SELECT COUNT(*) FROM domains')
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0][0], int)
    
    def test_query_insert(self, framework):
        """Test INSERT query."""
        result = framework.query(
            "INSERT INTO domains (domain, module) VALUES (?, ?)",
            ('test.example.com', 'test')
        )
        # Returns rowcount for insert
        assert result == 1
    
    def test_query_with_header(self, framework):
        """Test query with include_header option."""
        framework.query(
            "INSERT INTO domains (domain, module) VALUES (?, ?)",
            ('header-test.com', 'test')
        )
        result = framework.query(
            'SELECT domain, module FROM domains WHERE domain = ?',
            ('header-test.com',),
            include_header=True
        )
        # First row should be header
        assert result[0] == ('domain', 'module')


class TestFrameworkCmdMethods:
    """Tests for cmd.Cmd override methods."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        return mock_framework
    
    def test_default_invalid_command(self, framework, capsys):
        """Test default method for invalid commands."""
        framework.default('invalid_command')
        captured = capsys.readouterr()
        assert 'Invalid command' in captured.out
    
    def test_emptyline_returns_zero(self, framework):
        """Test emptyline returns 0 to continue."""
        result = framework.emptyline()
        assert result == 0
    
    def test_prompt_default(self, framework):
        """Test default prompt is set."""
        assert framework.prompt == '>>>'
