"""
Extended unit tests for BaseModule class.

Tests additional module functionality:
- goptions commands
- module execution (run, do_run)
- input validation
- key handling
- do_info, do_input, do_reload commands
"""
import pytest
import io
import os
import sys
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime

from recon.core.module import BaseModule
from recon.core.framework import Framework, Options, FrameworkException
from recon.utils.validators import ValidationException
from tests.fixtures.cli_test_framework import TestModuleMixin


class MockModuleWithKeys(TestModuleMixin, BaseModule):
    """Mock module that requires API keys."""
    
    meta = {
        'name': 'Mock Key Module',
        'author': 'Test Author',
        'version': '1.0',
        'description': 'A mock module requiring keys',
        'required_keys': ['shodan_api', 'twitter_api'],
    }
    
    def __init__(self, *args, **kwargs):
        with patch.object(BaseModule, '_parse_frontmatter', return_value={}):
            super().__init__(*args, **kwargs)


class MockModuleWithOptions(TestModuleMixin, BaseModule):
    """Mock module with custom options."""
    
    meta = {
        'name': 'Mock Options Module',
        'author': 'Test Author',
        'version': '1.0',
        'description': 'A mock module with options',
        'options': [
            ('target', None, True, 'target domain'),
            ('threads', 5, False, 'thread count'),
        ],
    }
    
    def __init__(self, *args, **kwargs):
        with patch.object(BaseModule, '_parse_frontmatter', return_value={}):
            super().__init__(*args, **kwargs)


class MockModuleWithQuery(TestModuleMixin, BaseModule):
    """Mock module with query and validator."""
    
    meta = {
        'name': 'Mock Query Module',
        'author': 'Test Author',
        'version': '1.0',
        'description': 'A mock module with query',
        'query': 'SELECT domain FROM domains WHERE domain IS NOT NULL',
        'validator': 'domain',
    }
    
    def __init__(self, *args, **kwargs):
        with patch.object(BaseModule, '_parse_frontmatter', return_value={}):
            super().__init__(*args, **kwargs)
        self.module_run_called = False
        self.run_inputs = []
    
    def module_pre(self):
        return {'config': 'test_config'}
    
    def module_run(self, inputs, config=None):
        self.module_run_called = True
        self.run_inputs = inputs
    
    def module_post(self):
        pass


class MockModuleWithComments(TestModuleMixin, BaseModule):
    """Mock module with comments in meta."""
    
    meta = {
        'name': 'Mock Comments Module',
        'author': 'Test Author',
        'version': '1.0',
        'description': 'A mock module with comments',
        'query': 'SELECT host FROM hosts WHERE host IS NOT NULL',
        'comments': [
            'This is a comment',
            '\tThis is an indented comment',
            'Another regular comment',
        ],
    }
    
    def __init__(self, *args, **kwargs):
        with patch.object(BaseModule, '_parse_frontmatter', return_value={}):
            super().__init__(*args, **kwargs)


# =============================================================================
# GOPTIONS COMMAND TESTS
# =============================================================================

@pytest.mark.unit
class TestGooptionsCommand:
    """Tests for goptions command."""
    
    @pytest.fixture
    def module(self, mock_framework):
        return MockModuleWithOptions('test/module')
    
    def test_do_goptions_no_params(self, module, capsys):
        """Test goptions with no params shows help."""
        module.do_goptions('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out or 'goptions' in captured.out.lower()
    
    def test_do_goptions_invalid_subcommand(self, module, capsys):
        """Test goptions with invalid subcommand."""
        module.do_goptions('invalid')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out or 'goptions' in captured.out.lower()
    
    def test_do_goptions_list(self, module, capsys):
        """Test goptions list shows global options."""
        module._do_goptions_list('')
        captured = capsys.readouterr()
        # Global options should be listed
        assert 'NAMESERVER' in captured.out or 'VERBOSITY' in captured.out or 'Name' in captured.out
    
    def test_do_goptions_set_valid(self, module, capsys):
        """Test goptions set with valid option."""
        with patch.object(module, '_save_config'):
            module._do_goptions_set('VERBOSITY 2')
        captured = capsys.readouterr()
        assert 'VERBOSITY' in captured.out
        assert module._global_options['VERBOSITY'] == 2
    
    def test_do_goptions_set_no_value(self, module, capsys):
        """Test goptions set without value shows help."""
        module._do_goptions_set('VERBOSITY')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out
    
    def test_do_goptions_set_invalid_option(self, module, capsys):
        """Test goptions set with invalid option."""
        module._do_goptions_set('INVALID_OPT value')
        captured = capsys.readouterr()
        assert 'Invalid' in captured.out
    
    def test_do_goptions_unset(self, module, capsys):
        """Test goptions unset."""
        module._global_options['VERBOSITY'] = 2
        with patch.object(module, '_save_config'):
            module._do_goptions_unset('VERBOSITY')
        assert module._global_options['VERBOSITY'] is None
    
    def test_do_goptions_unset_no_option(self, module, capsys):
        """Test goptions unset without option shows help."""
        module._do_goptions_unset('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out
    
    def test_do_goptions_unset_invalid(self, module, capsys):
        """Test goptions unset with invalid option."""
        module._do_goptions_unset('INVALID_OPT')
        captured = capsys.readouterr()
        assert 'Invalid' in captured.out


# =============================================================================
# MODULE INFO COMMAND TESTS
# =============================================================================

@pytest.mark.unit
class TestInfoCommand:
    """Tests for do_info command."""
    
    def test_do_info_basic(self, mock_framework, capsys):
        """Test do_info shows module information."""
        module = MockModuleWithOptions('test/module')
        module.do_info('')
        captured = capsys.readouterr()
        
        assert 'Mock Options Module' in captured.out
        assert 'Test Author' in captured.out
        assert '1.0' in captured.out
        assert 'Description' in captured.out
    
    def test_do_info_with_keys(self, mock_framework, capsys, temp_home_path):
        """Test do_info shows required keys."""
        import sqlite3
        
        # Create keys database
        keys_db = os.path.join(str(temp_home_path), 'keys.db')
        conn = sqlite3.connect(keys_db)
        conn.execute('CREATE TABLE IF NOT EXISTS keys (name TEXT PRIMARY KEY, value TEXT)')
        conn.commit()
        conn.close()
        
        mock_framework.home_path = str(temp_home_path)
        Framework.home_path = str(temp_home_path)
        
        module = MockModuleWithKeys('test/module')
        module.do_info('')
        captured = capsys.readouterr()
        
        assert 'Keys' in captured.out or 'shodan_api' in captured.out or 'twitter_api' in captured.out
    
    def test_do_info_with_source(self, mock_framework, capsys):
        """Test do_info shows source options for query modules."""
        module = MockModuleWithQuery('test/module')
        module.do_info('')
        captured = capsys.readouterr()
        
        assert 'Source Options' in captured.out
        assert 'default' in captured.out
    
    def test_do_info_with_comments(self, mock_framework, capsys):
        """Test do_info shows comments."""
        module = MockModuleWithComments('test/module')
        module.do_info('')
        captured = capsys.readouterr()
        
        assert 'Comments' in captured.out
        assert 'This is a comment' in captured.out


# =============================================================================
# MODULE INPUT COMMAND TESTS
# =============================================================================

@pytest.mark.unit
class TestInputCommand:
    """Tests for do_input command."""
    
    def test_do_input_with_source(self, mock_framework, capsys):
        """Test do_input shows inputs for modules with source."""
        module = MockModuleWithQuery('test/module')
        
        # Insert test data
        mock_framework.insert_domains(domain='input-test.com', mute=True)
        
        module.do_input('')
        captured = capsys.readouterr()
        
        assert 'input-test.com' in captured.out or 'Module Inputs' in captured.out
    
    def test_do_input_no_source(self, mock_framework, capsys):
        """Test do_input for modules without source."""
        module = MockModuleWithOptions('test/module')
        module.do_input('')
        captured = capsys.readouterr()
        
        assert 'not available' in captured.out.lower()
    
    def test_do_input_empty_source(self, mock_framework, capsys):
        """Test do_input when source returns no data."""
        module = MockModuleWithQuery('test/module')
        # Don't insert any data
        module.do_input('')
        captured = capsys.readouterr()
        # Should show error message
        assert 'no input' in captured.out.lower() or 'Source contains' in captured.out


# =============================================================================
# MODULE RELOAD COMMAND TESTS
# =============================================================================

@pytest.mark.unit
class TestReloadCommand:
    """Tests for do_reload command."""
    
    def test_do_reload_sets_flag(self, mock_framework):
        """Test do_reload sets reload flag."""
        module = MockModuleWithOptions('test/module')
        result = module.do_reload('')
        
        assert module._reload == 1
        assert result is True


# =============================================================================
# MODULE RUN TESTS
# =============================================================================

@pytest.mark.unit
class TestModuleRun:
    """Tests for module run method."""
    
    def test_run_calls_lifecycle_hooks(self, mock_framework):
        """Test run calls pre/run/post hooks."""
        module = MockModuleWithQuery('test/module')
        
        # Insert test data
        mock_framework.insert_domains(domain='run-test.com', mute=True)
        
        module.run()
        
        assert module.module_run_called
        assert 'run-test.com' in module.run_inputs
    
    def test_run_validates_options(self, mock_framework):
        """Test run validates required options."""
        module = MockModuleWithOptions('test/module')
        # TARGET is required but not set
        
        with pytest.raises(FrameworkException) as exc_info:
            module.run()
        assert 'required' in str(exc_info.value).lower()
    
    def test_run_updates_dashboard(self, mock_framework):
        """Test run updates dashboard."""
        module = MockModuleWithQuery('test/module')
        mock_framework.insert_domains(domain='dashboard-test.com', mute=True)
        
        module.run()
        
        # Check dashboard was updated
        result = mock_framework.query("SELECT runs FROM dashboard WHERE module='test/module'")
        assert len(result) > 0
        assert result[0][0] >= 1


@pytest.mark.unit
class TestDoRunCommand:
    """Tests for do_run command with exception handling."""
    
    def test_do_run_keyboard_interrupt(self, mock_framework, capsys):
        """Test do_run handles KeyboardInterrupt."""
        module = MockModuleWithQuery('test/module')
        
        with patch.object(module, 'run', side_effect=KeyboardInterrupt()):
            module.do_run('')
        # Should not raise, just print newline
    
    def test_do_run_timeout_error(self, mock_framework, capsys):
        """Test do_run handles timeout errors."""
        from requests.exceptions import Timeout
        
        module = MockModuleWithQuery('test/module')
        module._global_options['VERBOSITY'] = 1
        
        with patch.object(module, 'run', side_effect=Timeout()):
            module.do_run('')
        
        captured = capsys.readouterr()
        # Should show timeout-related message
        assert 'took too long' in captured.out.lower() or '[!' in captured.out
    
    def test_do_run_framework_exception(self, mock_framework, capsys):
        """Test do_run handles FrameworkException."""
        module = MockModuleWithQuery('test/module')
        module._global_options['VERBOSITY'] = 1
        
        with patch.object(module, 'run', side_effect=FrameworkException('Test error')):
            module.do_run('')
        
        captured = capsys.readouterr()
        # Should show error message
        assert '[!' in captured.out or 'error' in captured.out.lower()
    
    def test_do_run_validation_exception(self, mock_framework, capsys):
        """Test do_run handles ValidationException."""
        from recon.utils.validators import DomainValidator
        
        module = MockModuleWithQuery('test/module')
        module._global_options['VERBOSITY'] = 1
        
        # Create a proper ValidationException
        validator = DomainValidator()
        exc = ValidationException('invalid_domain', validator)
        
        with patch.object(module, 'run', side_effect=exc):
            module.do_run('')
        
        captured = capsys.readouterr()
        assert '[!' in captured.out or 'invalid' in captured.out.lower()
    
    def test_do_run_generic_exception(self, mock_framework, capsys):
        """Test do_run handles generic exceptions."""
        module = MockModuleWithQuery('test/module')
        module._global_options['VERBOSITY'] = 1
        
        with patch.object(module, 'run', side_effect=ValueError('Unexpected error')):
            module.do_run('')
        
        captured = capsys.readouterr()
        # Should show troubleshooting message
        assert 'Something broken' in captured.out or '[!' in captured.out
    
    def test_do_run_shows_summary(self, mock_framework, capsys):
        """Test do_run shows summary counts."""
        module = MockModuleWithQuery('test/module')
        mock_framework.insert_domains(domain='summary-test.com', mute=True)
        
        # Set up summary counts
        module._summary_counts = {
            'hosts': {'count': 5, 'new': 3},
            'domains': {'count': 2, 'new': 0},
        }
        
        def mock_run():
            pass  # Don't actually run
        
        with patch.object(module, 'run', mock_run):
            module.do_run('')
        
        captured = capsys.readouterr()
        # Summary appears in uppercase
        assert 'SUMMARY' in captured.out
        assert 'hosts' in captured.out
        assert 'domains' in captured.out


# =============================================================================
# MODULE LOAD COMMAND TESTS
# =============================================================================

@pytest.mark.unit
class TestModulesLoadCommand:
    """Tests for _do_modules_load command in BaseModule."""
    
    def test_modules_load_no_params(self, mock_framework, capsys):
        """Test modules load without params shows help."""
        module = MockModuleWithOptions('test/module')
        module._do_modules_load('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out
    
    def test_modules_load_no_match(self, mock_framework, capsys):
        """Test modules load with no matching module."""
        module = MockModuleWithOptions('test/module')
        Framework._loaded_modules = {}
        
        module._do_modules_load('nonexistent_module')
        captured = capsys.readouterr()
        assert 'Invalid' in captured.out
    
    def test_modules_load_multiple_matches(self, mock_framework, capsys):
        """Test modules load with multiple matches."""
        module = MockModuleWithOptions('test/module')
        Framework._loaded_modules = {
            'recon/test/module1': MagicMock(),
            'recon/test/module2': MagicMock(),
        }
        
        module._do_modules_load('test')
        captured = capsys.readouterr()
        assert 'Multiple' in captured.out
    
    def test_modules_load_single_match(self, mock_framework, capsys):
        """Test modules load with single match."""
        module = MockModuleWithOptions('test/module')
        Framework._loaded_modules = {
            'recon/test/exact_module': MagicMock(),
        }
        
        # Should return True to indicate transition
        result = module._do_modules_load('recon/test/exact_module')
        assert result is True


# =============================================================================
# COMPLETE METHODS TESTS
# =============================================================================

@pytest.mark.unit
class TestModuleCompleteMethods:
    """Tests for module completion methods."""
    
    def test_complete_goptions(self, mock_framework):
        """Test complete_goptions returns subcommands."""
        module = MockModuleWithOptions('test/module')
        result = module.complete_goptions('l', 'goptions l', 0, 0)
        assert 'list' in result
    
    def test_complete_goptions_set(self, mock_framework):
        """Test _complete_goptions_set returns global option names."""
        module = MockModuleWithOptions('test/module')
        result = module._complete_goptions_set('V')
        assert 'VERBOSITY' in result
    
    def test_complete_goptions_list(self, mock_framework):
        """Test _complete_goptions_list returns empty."""
        module = MockModuleWithOptions('test/module')
        result = module._complete_goptions_list('')
        assert result == []
    
    def test_complete_reload(self, mock_framework):
        """Test complete_reload returns empty."""
        module = MockModuleWithOptions('test/module')
        result = module.complete_reload('', '', 0, 0)
        assert result == []
    
    def test_complete_info(self, mock_framework):
        """Test complete_info returns empty."""
        module = MockModuleWithOptions('test/module')
        result = module.complete_info('', '', 0, 0)
        assert result == []
    
    def test_complete_input(self, mock_framework):
        """Test complete_input returns empty."""
        module = MockModuleWithQuery('test/module')
        result = module.complete_input('', '', 0, 0)
        assert result == []
    
    def test_complete_run(self, mock_framework):
        """Test complete_run returns empty."""
        module = MockModuleWithQuery('test/module')
        result = module.complete_run('', '', 0, 0)
        assert result == []


# =============================================================================
# HELP METHODS TESTS
# =============================================================================

@pytest.mark.unit
class TestModuleHelpMethods:
    """Tests for module help methods."""
    
    def test_help_goptions(self, mock_framework, capsys):
        """Test help_goptions output."""
        module = MockModuleWithOptions('test/module')
        module.help_goptions()
        captured = capsys.readouterr()
        assert 'goptions' in captured.out.lower()
        assert 'Usage:' in captured.out
    
    def test_help_goptions_set(self, mock_framework, capsys):
        """Test _help_goptions_set output."""
        module = MockModuleWithOptions('test/module')
        module._help_goptions_set()
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out
        assert 'set' in captured.out.lower()
    
    def test_help_goptions_unset(self, mock_framework, capsys):
        """Test _help_goptions_unset output."""
        module = MockModuleWithOptions('test/module')
        module._help_goptions_unset()
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out
        assert 'unset' in captured.out.lower()


# =============================================================================
# SOURCE METHODS TESTS
# =============================================================================

@pytest.mark.unit
class TestSourceMethods:
    """Tests for _get_source method."""
    
    def test_get_source_from_file(self, mock_framework, tmp_path):
        """Test _get_source reads from file."""
        module = MockModuleWithQuery('test/module')
        
        # Create a file with inputs
        input_file = tmp_path / "inputs.txt"
        input_file.write_text("domain1.com\ndomain2.com\ndomain3.com")
        
        sources = module._get_source(str(input_file), None)
        
        assert 'domain1.com' in sources
        assert 'domain2.com' in sources
        assert 'domain3.com' in sources
    
    def test_get_source_multiple_columns(self, mock_framework):
        """Test _get_source with multiple column query."""
        module = MockModuleWithQuery('test/module')
        
        mock_framework.insert_hosts(host='multi-col.com', ip_address='192.0.2.1', mute=True)
        
        # Query that returns multiple columns
        sources = module._get_source('query SELECT host, ip_address FROM hosts', None)
        
        # Should return tuples
        assert len(sources) >= 1
    
    def test_get_source_invalid_query(self, mock_framework):
        """Test _get_source with invalid SQL."""
        module = MockModuleWithQuery('test/module')
        
        with pytest.raises(FrameworkException) as exc_info:
            module._get_source('query INVALID SQL', None)
        
        assert 'Invalid' in str(exc_info.value) or 'query' in str(exc_info.value).lower()


# =============================================================================
# UTILITY METHODS TESTS
# =============================================================================

@pytest.mark.unit
class TestModuleUtilityMethods:
    """Tests for module utility methods."""
    
    def test_merge_dicts_basic(self, mock_framework):
        """Test _merge_dicts merges correctly."""
        module = MockModuleWithOptions('test/module')
        
        dict1 = {'a': 1, 'b': 2}
        dict2 = {'c': 3, 'd': 4}
        
        result = module._merge_dicts(dict1, dict2)
        
        assert result['a'] == 1
        assert result['b'] == 2
        assert result['c'] == 3
        assert result['d'] == 4
    
    def test_merge_dicts_override(self, mock_framework):
        """Test _merge_dicts overrides values."""
        module = MockModuleWithOptions('test/module')
        
        dict1 = {'a': 1, 'b': 2}
        dict2 = {'b': 'overridden', 'c': 3}
        
        result = module._merge_dicts(dict1, dict2)
        
        assert result['b'] == 'overridden'
    
    def test_html_escape_special_chars(self, mock_framework):
        """Test html_escape handles all special chars."""
        module = MockModuleWithOptions('test/module')
        
        result = module.html_escape('<script>alert("xss" & \'test\')</script>')
        
        assert '&lt;' in result
        assert '&gt;' in result
        assert '&quot;' in result
        assert '&apos;' in result
        assert '&amp;' in result
    
    def test_cidr_to_list_small_network(self, mock_framework):
        """Test cidr_to_list with small network."""
        module = MockModuleWithOptions('test/module')
        
        result = module.cidr_to_list('10.0.0.0/30')
        
        assert len(result) == 4
        assert '10.0.0.0' in result
        assert '10.0.0.3' in result
    
    def test_cidr_to_list_single_host(self, mock_framework):
        """Test cidr_to_list with /32."""
        module = MockModuleWithOptions('test/module')
        
        result = module.cidr_to_list('192.168.1.1/32')
        
        assert len(result) == 1
        assert '192.168.1.1' in result
    
    def test_hosts_to_domains_complex(self, mock_framework):
        """Test hosts_to_domains with complex hierarchy."""
        module = MockModuleWithOptions('test/module')
        
        hosts = [
            'www.app.corp.example.com',
            'api.corp.example.com',
            'mail.example.org',
        ]
        
        result = module.hosts_to_domains(hosts)
        
        assert 'corp.example.com' in result
        assert 'example.com' in result
        assert 'example.org' in result
    
    def test_make_cookie_attributes(self, mock_framework):
        """Test make_cookie sets all attributes."""
        module = MockModuleWithOptions('test/module')
        
        cookie = module.make_cookie(
            name='test_cookie',
            value='test_value',
            domain='example.com',
            path='/api/v1'
        )
        
        assert cookie.name == 'test_cookie'
        assert cookie.value == 'test_value'
        assert cookie.domain == 'example.com'
        assert cookie.path == '/api/v1'
        assert cookie.secure is False
        assert cookie.version == 0


# =============================================================================
# KEY HANDLING TESTS
# =============================================================================

@pytest.mark.unit
class TestModuleKeyHandling:
    """Tests for module key handling."""
    
    def test_module_missing_key_warning(self, mock_framework, capsys, temp_home_path):
        """Test module warns about missing keys."""
        import sqlite3
        
        # Create keys database (empty)
        keys_db = os.path.join(str(temp_home_path), 'keys.db')
        conn = sqlite3.connect(keys_db)
        conn.execute('CREATE TABLE IF NOT EXISTS keys (name TEXT PRIMARY KEY, value TEXT)')
        conn.commit()
        conn.close()
        
        mock_framework.home_path = str(temp_home_path)
        Framework.home_path = str(temp_home_path)
        
        # Don't add the keys - this should warn
        module = MockModuleWithKeys('test/module')
        captured = capsys.readouterr()
        
        # Should warn about missing keys
        assert 'not set' in captured.out.lower() or 'likely fail' in captured.out.lower()
    
    def test_module_with_keys_set(self, mock_framework, capsys, temp_home_path):
        """Test module with keys properly set."""
        import sqlite3
        
        # Create keys database and add keys
        keys_db = os.path.join(str(temp_home_path), 'keys.db')
        conn = sqlite3.connect(keys_db)
        conn.execute('CREATE TABLE IF NOT EXISTS keys (name TEXT PRIMARY KEY, value TEXT)')
        conn.execute("INSERT OR REPLACE INTO keys VALUES ('shodan_api', 'test_key_1')")
        conn.execute("INSERT OR REPLACE INTO keys VALUES ('twitter_api', 'test_key_2')")
        conn.commit()
        conn.close()
        
        mock_framework.home_path = str(temp_home_path)
        Framework.home_path = str(temp_home_path)
        
        module = MockModuleWithKeys('test/module')
        
        # Keys should be loaded
        assert module.keys.get('shodan_api') == 'test_key_1'
        assert module.keys.get('twitter_api') == 'test_key_2'
