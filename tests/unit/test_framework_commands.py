"""
Unit tests for recon.core.framework.Framework command methods.

Tests the do_* command methods, help methods, and complete methods.
"""
import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock, mock_open
from io import StringIO

from recon.core.framework import Framework, FrameworkException, Colors, Options


# =============================================================================
# OPTIONS COMMAND TESTS
# =============================================================================

class TestOptionsCommand:
    """Tests for do_options and related methods."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        # Add module options
        mock_framework.options = Options()
        mock_framework.options.init_option('SOURCE', 'default', True, 'data source')
        mock_framework.options.init_option('THREADS', 10, False, 'thread count')
        mock_framework.options.init_option('VERBOSE', False, False, 'verbose output')
        return mock_framework
    
    def test_do_options_no_params(self, framework, capsys):
        """Test do_options with no params shows help."""
        framework.do_options('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out or 'options' in captured.out.lower()
    
    def test_do_options_invalid_subcommand(self, framework, capsys):
        """Test do_options with invalid subcommand."""
        framework.do_options('invalid')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out or 'options' in captured.out.lower()
    
    def test_do_options_list(self, framework, capsys):
        """Test options list subcommand."""
        framework._do_options_list('')
        captured = capsys.readouterr()
        assert 'SOURCE' in captured.out
        assert 'THREADS' in captured.out
    
    def test_do_options_set_valid(self, framework, capsys):
        """Test options set with valid option."""
        with patch.object(framework, '_save_config'):
            framework._do_options_set('SOURCE custom_value')
        captured = capsys.readouterr()
        assert 'SOURCE' in captured.out
        assert 'custom_value' in captured.out
        assert framework.options['SOURCE'] == 'custom_value'
    
    def test_do_options_set_no_value(self, framework, capsys):
        """Test options set without value shows help."""
        framework._do_options_set('SOURCE')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out
    
    def test_do_options_set_invalid_option(self, framework, capsys):
        """Test options set with invalid option name."""
        framework._do_options_set('INVALID value')
        captured = capsys.readouterr()
        assert 'Invalid' in captured.out
    
    def test_do_options_unset(self, framework, capsys):
        """Test options unset."""
        framework.options['SOURCE'] = 'test_value'
        with patch.object(framework, '_save_config'):
            framework._do_options_unset('SOURCE')
        assert framework.options['SOURCE'] is None
    
    def test_do_options_unset_no_option(self, framework, capsys):
        """Test options unset without option shows help."""
        framework._do_options_unset('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out
    
    def test_do_options_unset_invalid(self, framework, capsys):
        """Test options unset with invalid option."""
        framework._do_options_unset('INVALID')
        captured = capsys.readouterr()
        assert 'Invalid' in captured.out


# =============================================================================
# KEYS COMMAND TESTS
# =============================================================================

class TestKeysCommand:
    """Tests for do_keys and related methods."""
    
    @pytest.fixture
    def framework(self, mock_framework, temp_home_path):
        # Create keys database
        import sqlite3
        keys_db = os.path.join(str(temp_home_path), 'keys.db')
        conn = sqlite3.connect(keys_db)
        conn.execute('CREATE TABLE IF NOT EXISTS keys (name TEXT PRIMARY KEY, value TEXT)')
        conn.commit()
        conn.close()
        mock_framework.home_path = str(temp_home_path)
        Framework.home_path = str(temp_home_path)
        return mock_framework
    
    def test_do_keys_no_params(self, framework, capsys):
        """Test do_keys with no params shows help."""
        framework.do_keys('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out or 'keys' in captured.out.lower()
    
    def test_do_keys_invalid_subcommand(self, framework, capsys):
        """Test do_keys with invalid subcommand."""
        framework.do_keys('invalid')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out or 'keys' in captured.out.lower()
    
    def test_do_keys_list_empty(self, framework, capsys):
        """Test keys list when no keys exist."""
        framework._do_keys_list('')
        # Should not raise, just show nothing or empty
    
    def test_do_keys_add(self, framework, capsys):
        """Test keys add."""
        framework._do_keys_add('test_api_key abc123')
        captured = capsys.readouterr()
        assert 'added' in captured.out.lower()
    
    def test_do_keys_add_no_value(self, framework, capsys):
        """Test keys add without value shows help."""
        framework._do_keys_add('test_key')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out
    
    def test_do_keys_remove(self, framework, capsys):
        """Test keys remove."""
        # First add a key
        framework.add_key('test_remove_key', 'value123')
        framework._do_keys_remove('test_remove_key')
        captured = capsys.readouterr()
        assert 'removed' in captured.out.lower()
    
    def test_do_keys_remove_no_key(self, framework, capsys):
        """Test keys remove without key shows help."""
        framework._do_keys_remove('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out
    
    def test_do_keys_remove_invalid(self, framework, capsys):
        """Test keys remove with invalid key."""
        framework._do_keys_remove('nonexistent_key')
        captured = capsys.readouterr()
        assert 'Invalid' in captured.out
    
    def test_keys_list_with_data(self, framework, capsys):
        """Test keys list with actual keys."""
        framework.add_key('shodan_api', 'test123')
        framework.add_key('twitter_api', 'test456')
        framework._do_keys_list('')
        captured = capsys.readouterr()
        assert 'shodan_api' in captured.out
        assert 'twitter_api' in captured.out


# =============================================================================
# MODULES COMMAND TESTS
# =============================================================================

class TestModulesCommand:
    """Tests for do_modules and related methods."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        # Add some test modules
        Framework._loaded_modules = {
            'recon/domains-hosts/test_module': MagicMock(),
            'recon/hosts-contacts/another_module': MagicMock(),
            'discovery/info_disclosure/test': MagicMock(),
        }
        return mock_framework
    
    def test_do_modules_no_params(self, framework, capsys):
        """Test do_modules with no params shows help."""
        framework.do_modules('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out or 'modules' in captured.out.lower()
    
    def test_do_modules_invalid_subcommand(self, framework, capsys):
        """Test do_modules with invalid subcommand."""
        framework.do_modules('invalid')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out or 'modules' in captured.out.lower()
    
    def test_do_modules_search_all(self, framework, capsys):
        """Test modules search without params lists all."""
        framework._do_modules_search('')
        captured = capsys.readouterr()
        assert 'test_module' in captured.out or 'recon' in captured.out
    
    def test_do_modules_search_with_pattern(self, framework, capsys):
        """Test modules search with pattern."""
        framework._do_modules_search('host')
        captured = capsys.readouterr()
        assert 'hosts' in captured.out
    
    def test_do_modules_search_no_match(self, framework, capsys):
        """Test modules search with no matches."""
        framework._do_modules_search('nonexistent_xyz123')
        captured = capsys.readouterr()
        assert 'No modules found' in captured.out
    
    def test_do_modules_load_not_implemented(self, framework):
        """Test modules load raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            framework._do_modules_load('recon/test/module')
    
    def test_match_modules_exact(self, framework):
        """Test _match_modules with exact match."""
        modules = framework._match_modules('recon/domains-hosts/test_module')
        assert modules == ['recon/domains-hosts/test_module']
    
    def test_match_modules_partial(self, framework):
        """Test _match_modules with partial match."""
        modules = framework._match_modules('test')
        assert len(modules) >= 1
    
    def test_match_modules_no_match(self, framework):
        """Test _match_modules with no match."""
        modules = framework._match_modules('nonexistent_xyz')
        assert modules == []
    
    def test_list_modules(self, framework, capsys):
        """Test _list_modules output."""
        modules = list(Framework._loaded_modules.keys())
        framework._list_modules(modules)
        captured = capsys.readouterr()
        assert 'recon' in captured.out.lower() or 'discovery' in captured.out.lower()
    
    def test_list_modules_empty(self, framework, capsys):
        """Test _list_modules with empty list."""
        framework._list_modules([])
        captured = capsys.readouterr()
        assert 'No modules' in captured.out


# =============================================================================
# SHOW COMMAND TESTS
# =============================================================================

class TestShowCommand:
    """Tests for do_show and related methods."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        return mock_framework
    
    def test_do_show_no_params(self, framework, capsys):
        """Test do_show with no params shows help."""
        framework.do_show('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out or 'show' in captured.out.lower()
    
    def test_do_show_invalid(self, framework, capsys):
        """Test do_show with invalid argument."""
        framework.do_show('invalid_xyz')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out or 'show' in captured.out.lower()
    
    def test_do_show_table(self, framework, capsys):
        """Test do_show with table name queries the table."""
        # Insert test data
        framework.insert_domains(domain='show-test.com', mute=True)
        framework.do_show('domains')
        captured = capsys.readouterr()
        assert 'show-test.com' in captured.out
    
    def test_get_show_names(self, framework):
        """Test _get_show_names returns show methods."""
        names = framework._get_show_names()
        # The framework should have at least some show methods
        assert isinstance(names, list)


# =============================================================================
# DB COMMAND TESTS
# =============================================================================

class TestDbCommand:
    """Tests for do_db and related methods."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        return mock_framework
    
    def test_do_db_no_params(self, framework, capsys):
        """Test do_db with no params shows help."""
        framework.do_db('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out or 'db' in captured.out.lower()
    
    def test_do_db_invalid_subcommand(self, framework, capsys):
        """Test do_db with invalid subcommand."""
        framework.do_db('invalid')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out or 'db' in captured.out.lower()
    
    def test_do_db_query_select(self, framework, capsys):
        """Test db query with SELECT."""
        framework.insert_domains(domain='query-test.com', mute=True)
        framework._do_db_query('SELECT * FROM domains')
        captured = capsys.readouterr()
        assert 'query-test.com' in captured.out
    
    def test_do_db_query_no_params(self, framework, capsys):
        """Test db query without params shows help."""
        framework._do_db_query('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out
    
    def test_do_db_query_invalid_sql(self, framework, capsys):
        """Test db query with invalid SQL."""
        framework._do_db_query('INVALID SQL QUERY')
        captured = capsys.readouterr()
        assert 'Invalid query' in captured.out
    
    def test_do_db_query_no_results(self, framework, capsys):
        """Test db query with no results."""
        framework._do_db_query('SELECT * FROM domains WHERE domain = "nonexistent"')
        captured = capsys.readouterr()
        assert 'No data' in captured.out
    
    def test_do_db_query_update(self, framework, capsys):
        """Test db query with UPDATE statement."""
        framework.insert_domains(domain='update-test.com', mute=True)
        framework._do_db_query('UPDATE domains SET notes = "updated" WHERE domain = "update-test.com"')
        captured = capsys.readouterr()
        assert 'rows affected' in captured.out
    
    def test_do_db_schema(self, framework, capsys):
        """Test db schema command."""
        framework._do_db_schema('')
        captured = capsys.readouterr()
        assert 'domain' in captured.out.lower() or 'domains' in captured.out.lower()
    
    def test_do_db_delete_with_params(self, framework, capsys):
        """Test db delete with row IDs."""
        framework.insert_domains(domain='delete-test.com', mute=True)
        framework._do_db_delete('domains 1')
        captured = capsys.readouterr()
        assert 'rows affected' in captured.out
    
    def test_do_db_delete_no_table(self, framework, capsys):
        """Test db delete without table shows help."""
        framework._do_db_delete('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out
    
    def test_do_db_delete_invalid_table(self, framework, capsys):
        """Test db delete with invalid table."""
        framework._do_db_delete('invalid_table 1')
        captured = capsys.readouterr()
        assert 'Invalid' in captured.out
    
    def test_do_db_notes_no_table(self, framework, capsys):
        """Test db notes without table shows help."""
        framework._do_db_notes('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out
    
    def test_do_db_notes_with_params(self, framework, capsys):
        """Test db notes with parameters."""
        framework.insert_domains(domain='notes-test.com', mute=True)
        framework._do_db_notes('domains 1 Test note here')
        captured = capsys.readouterr()
        assert 'rows affected' in captured.out
    
    def test_do_db_notes_invalid_table(self, framework, capsys):
        """Test db notes with invalid table."""
        framework._do_db_notes('invalid_table')
        captured = capsys.readouterr()
        assert 'Invalid' in captured.out
    
    def test_do_db_insert_no_table(self, framework, capsys):
        """Test db insert without table shows help."""
        framework._do_db_insert('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out
    
    def test_do_db_insert_invalid_table(self, framework, capsys):
        """Test db insert with invalid table."""
        framework._do_db_insert('invalid_table')
        captured = capsys.readouterr()
        assert 'Invalid' in captured.out


# =============================================================================
# SCRIPT COMMAND TESTS
# =============================================================================

class TestScriptCommand:
    """Tests for do_script and related methods."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        Framework._record = None
        return mock_framework
    
    def test_do_script_no_params(self, framework, capsys):
        """Test do_script with no params shows help."""
        framework.do_script('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out or 'script' in captured.out.lower()
    
    def test_do_script_invalid_subcommand(self, framework, capsys):
        """Test do_script with invalid subcommand."""
        framework.do_script('invalid')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out or 'script' in captured.out.lower()
    
    def test_do_script_record_start(self, framework, capsys, tmp_path):
        """Test starting script recording."""
        script_file = tmp_path / "test_script.rc"
        framework._do_script_record(str(script_file))
        captured = capsys.readouterr()
        assert 'Recording' in captured.out
        assert Framework._record == str(script_file)
    
    def test_do_script_record_no_filename(self, framework, capsys):
        """Test script record without filename shows help."""
        framework._do_script_record('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out
    
    def test_do_script_record_already_started(self, framework, capsys, tmp_path):
        """Test script record when already recording."""
        script_file = tmp_path / "test_script.rc"
        Framework._record = str(script_file)
        framework._do_script_record(str(tmp_path / "another.rc"))
        captured = capsys.readouterr()
        assert 'already started' in captured.out.lower()
    
    def test_do_script_stop(self, framework, capsys, tmp_path):
        """Test stopping script recording."""
        script_file = tmp_path / "test_script.rc"
        Framework._record = str(script_file)
        framework._do_script_stop('')
        captured = capsys.readouterr()
        assert 'stopped' in captured.out.lower()
        assert Framework._record is None
    
    def test_do_script_stop_not_recording(self, framework, capsys):
        """Test script stop when not recording."""
        Framework._record = None
        framework._do_script_stop('')
        captured = capsys.readouterr()
        assert 'already stopped' in captured.out.lower()
    
    def test_do_script_status_started(self, framework, capsys, tmp_path):
        """Test script status when recording."""
        Framework._record = str(tmp_path / "test.rc")
        framework._do_script_status('')
        captured = capsys.readouterr()
        assert 'started' in captured.out.lower()
    
    def test_do_script_status_stopped(self, framework, capsys):
        """Test script status when not recording."""
        Framework._record = None
        framework._do_script_status('')
        captured = capsys.readouterr()
        assert 'stopped' in captured.out.lower()
    
    def test_do_script_execute_file_not_found(self, framework, capsys):
        """Test script execute with missing file."""
        framework._do_script_execute('/nonexistent/file.rc')
        captured = capsys.readouterr()
        assert 'not found' in captured.out.lower()
    
    def test_do_script_execute_no_filename(self, framework, capsys):
        """Test script execute without filename shows help."""
        framework._do_script_execute('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out


# =============================================================================
# SPOOL COMMAND TESTS
# =============================================================================

class TestSpoolCommand:
    """Tests for do_spool and related methods."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        Framework._spool = None
        return mock_framework
    
    def test_do_spool_no_params(self, framework, capsys):
        """Test do_spool with no params shows help."""
        framework.do_spool('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out or 'spool' in captured.out.lower()
    
    def test_do_spool_invalid_subcommand(self, framework, capsys):
        """Test do_spool with invalid subcommand."""
        framework.do_spool('invalid')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out or 'spool' in captured.out.lower()
    
    def test_do_spool_start(self, framework, capsys, tmp_path):
        """Test starting output spooling."""
        spool_file = tmp_path / "test_spool.txt"
        framework._do_spool_start(str(spool_file))
        captured = capsys.readouterr()
        assert 'Spooling output' in captured.out
        assert Framework._spool is not None
        # Cleanup
        if Framework._spool:
            Framework._spool.close()
            Framework._spool = None
    
    def test_do_spool_start_no_filename(self, framework, capsys):
        """Test spool start without filename shows help."""
        framework._do_spool_start('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out
    
    def test_do_spool_start_already_started(self, framework, capsys, tmp_path):
        """Test spool start when already spooling."""
        spool_file = tmp_path / "test_spool.txt"
        Framework._spool = open(str(spool_file), 'w')
        framework._do_spool_start(str(tmp_path / "another.txt"))
        captured = capsys.readouterr()
        assert 'already started' in captured.out.lower()
        # Cleanup
        Framework._spool.close()
        Framework._spool = None
    
    def test_do_spool_stop(self, framework, capsys, tmp_path):
        """Test stopping output spooling."""
        spool_file = tmp_path / "test_spool.txt"
        Framework._spool = open(str(spool_file), 'w')
        framework._do_spool_stop('')
        captured = capsys.readouterr()
        assert 'stopped' in captured.out.lower()
        assert Framework._spool is None
    
    def test_do_spool_stop_not_spooling(self, framework, capsys):
        """Test spool stop when not spooling."""
        Framework._spool = None
        framework._do_spool_stop('')
        captured = capsys.readouterr()
        assert 'already stopped' in captured.out.lower()
    
    def test_do_spool_status_started(self, framework, capsys, tmp_path):
        """Test spool status when spooling."""
        spool_file = tmp_path / "test_spool.txt"
        Framework._spool = open(str(spool_file), 'w')
        framework._do_spool_status('')
        captured = capsys.readouterr()
        assert 'started' in captured.out.lower()
        # Cleanup
        Framework._spool.close()
        Framework._spool = None
    
    def test_do_spool_status_stopped(self, framework, capsys):
        """Test spool status when not spooling."""
        Framework._spool = None
        framework._do_spool_status('')
        captured = capsys.readouterr()
        assert 'stopped' in captured.out.lower()


# =============================================================================
# SHELL COMMAND TESTS
# =============================================================================

class TestShellCommand:
    """Tests for do_shell command."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        return mock_framework
    
    def test_do_shell_no_params(self, framework, capsys):
        """Test do_shell with no params shows help."""
        framework.do_shell('')
        captured = capsys.readouterr()
        assert 'Usage:' in captured.out or 'shell' in captured.out.lower()
    
    def test_do_shell_echo(self, framework, capsys):
        """Test do_shell with echo command."""
        framework.do_shell('echo test_output')
        captured = capsys.readouterr()
        assert 'Command: echo test_output' in captured.out
        assert 'test_output' in captured.out
    
    def test_do_shell_command_error(self, framework, capsys):
        """Test do_shell with command that produces stderr."""
        framework.do_shell('ls /nonexistent_directory_xyz')
        captured = capsys.readouterr()
        # Should show command and some error
        assert 'Command:' in captured.out


# =============================================================================
# EXIT/BACK COMMAND TESTS
# =============================================================================

class TestExitBackCommands:
    """Tests for do_exit and do_back commands."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        return mock_framework
    
    def test_do_exit(self, framework):
        """Test do_exit sets exit flag and returns True."""
        result = framework.do_exit('')
        assert result is True
        assert framework._exit == 1
    
    def test_do_back(self, framework):
        """Test do_back returns True."""
        result = framework.do_back('')
        assert result is True


# =============================================================================
# DASHBOARD COMMAND TESTS
# =============================================================================

class TestDashboardCommand:
    """Tests for do_dashboard command."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        return mock_framework
    
    def test_do_dashboard_empty(self, framework, capsys):
        """Test dashboard with no activity."""
        framework.do_dashboard('')
        captured = capsys.readouterr()
        assert 'no record' in captured.out.lower()
    
    def test_do_dashboard_with_activity(self, framework, capsys):
        """Test dashboard with recorded activity."""
        # Insert some activity
        framework.query("INSERT INTO dashboard (module, runs) VALUES ('test/module', 5)")
        framework.insert_domains(domain='dashboard-test.com', mute=True)
        framework.do_dashboard('')
        captured = capsys.readouterr()
        assert 'Activity' in captured.out or 'Summary' in captured.out


# =============================================================================
# PDB COMMAND TESTS
# =============================================================================

class TestPdbCommand:
    """Tests for do_pdb command."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        return mock_framework
    
    def test_do_pdb_imports_pdb(self, framework):
        """Test do_pdb imports pdb module."""
        with patch('pdb.set_trace') as mock_trace:
            framework.do_pdb('')
            mock_trace.assert_called_once()


# =============================================================================
# COMPLETE METHODS TESTS
# =============================================================================

class TestCompleteMethods:
    """Tests for tab completion methods."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        mock_framework.options = Options()
        mock_framework.options.init_option('SOURCE', 'default', True, 'source')
        mock_framework.options.init_option('THREADS', 10, False, 'threads')
        Framework._loaded_modules = {
            'recon/test/module': MagicMock(),
            'recon/test/other': MagicMock(),
        }
        return mock_framework
    
    def test_complete_options_subcommands(self, framework):
        """Test complete_options returns subcommands."""
        result = framework.complete_options('l', 'options l', 0, 0)
        assert 'list' in result
    
    def test_complete_options_set(self, framework):
        """Test _complete_options_set returns option names."""
        result = framework._complete_options_set('S')
        assert 'SOURCE' in result
    
    def test_complete_options_list(self, framework):
        """Test _complete_options_list returns empty."""
        result = framework._complete_options_list('')
        assert result == []
    
    def test_complete_modules(self, framework):
        """Test complete_modules returns subcommands."""
        result = framework.complete_modules('l', 'modules l', 0, 0)
        assert 'load' in result
    
    def test_complete_modules_load(self, framework):
        """Test _complete_modules_load returns module names."""
        result = framework._complete_modules_load('recon')
        assert len(result) >= 1
    
    def test_complete_modules_search(self, framework):
        """Test _complete_modules_search returns empty."""
        result = framework._complete_modules_search('')
        assert result == []
    
    def test_complete_show(self, framework):
        """Test complete_show returns options and tables."""
        result = framework.complete_show('d', 'show d', 0, 0)
        assert 'domains' in result
    
    def test_complete_db_subcommands(self, framework):
        """Test complete_db returns subcommands."""
        result = framework.complete_db('q', 'db q', 0, 0)
        assert 'query' in result
    
    def test_complete_db_insert(self, framework):
        """Test _complete_db_insert returns table names."""
        result = framework._complete_db_insert('d')
        assert 'domains' in result
    
    def test_complete_db_query(self, framework):
        """Test _complete_db_query returns empty."""
        result = framework._complete_db_query('')
        assert result == []
    
    def test_complete_script_subcommands(self, framework):
        """Test complete_script returns subcommands."""
        result = framework.complete_script('r', 'script r', 0, 0)
        assert 'record' in result
    
    def test_complete_spool_subcommands(self, framework):
        """Test complete_spool returns subcommands."""
        result = framework.complete_spool('s', 'spool s', 0, 0)
        assert 'start' in result or 'stop' in result or 'status' in result


# =============================================================================
# HELP METHODS TESTS
# =============================================================================

class TestHelpMethods:
    """Tests for help methods."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        return mock_framework
    
    def test_help_options(self, framework, capsys):
        """Test help_options output."""
        framework.help_options()
        captured = capsys.readouterr()
        assert 'options' in captured.out.lower()
        assert 'Usage:' in captured.out
    
    def test_help_keys(self, framework, capsys):
        """Test help_keys output."""
        framework.help_keys()
        captured = capsys.readouterr()
        assert 'keys' in captured.out.lower()
        assert 'Usage:' in captured.out
    
    def test_help_modules(self, framework, capsys):
        """Test help_modules output."""
        framework.help_modules()
        captured = capsys.readouterr()
        assert 'modules' in captured.out.lower()
        assert 'Usage:' in captured.out
    
    def test_help_show(self, framework, capsys):
        """Test help_show output."""
        framework.help_show()
        captured = capsys.readouterr()
        assert 'show' in captured.out.lower()
        assert 'Usage:' in captured.out
    
    def test_help_db(self, framework, capsys):
        """Test help_db output."""
        framework.help_db()
        captured = capsys.readouterr()
        assert 'db' in captured.out.lower()
        assert 'Usage:' in captured.out
    
    def test_help_script(self, framework, capsys):
        """Test help_script output."""
        framework.help_script()
        captured = capsys.readouterr()
        assert 'script' in captured.out.lower()
        assert 'Usage:' in captured.out
    
    def test_help_spool(self, framework, capsys):
        """Test help_spool output."""
        framework.help_spool()
        captured = capsys.readouterr()
        assert 'spool' in captured.out.lower()
        assert 'Usage:' in captured.out
    
    def test_help_shell(self, framework, capsys):
        """Test help_shell output."""
        framework.help_shell()
        captured = capsys.readouterr()
        assert 'shell' in captured.out.lower()
        assert 'Usage:' in captured.out


# =============================================================================
# PRECMD/ONECMD TESTS
# =============================================================================

class TestCmdOverrides:
    """Tests for cmd.Cmd override methods."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        return mock_framework
    
    def test_precmd_normal(self, framework):
        """Test precmd returns the line."""
        result = framework.precmd('test command')
        assert result == 'test command'
    
    def test_precmd_with_script(self, framework, capsys):
        """Test precmd with script mode prints line."""
        Framework._script = 1
        result = framework.precmd('test command')
        captured = capsys.readouterr()
        assert 'test command' in captured.out
        Framework._script = 0
    
    def test_precmd_with_record(self, framework, tmp_path):
        """Test precmd with recording writes to file."""
        record_file = tmp_path / "record.rc"
        Framework._record = str(record_file)
        framework.precmd('test command')
        assert 'test command' in record_file.read_text()
        Framework._record = None
    
    def test_precmd_with_spool(self, framework, tmp_path):
        """Test precmd with spooling writes to file."""
        import codecs
        spool_file = tmp_path / "spool.txt"
        Framework._spool = codecs.open(str(spool_file), 'ab', encoding='utf-8')
        framework.precmd('test command')
        Framework._spool.close()
        assert 'test command' in spool_file.read_text()
        Framework._spool = None
    
    def test_onecmd_empty_line(self, framework):
        """Test onecmd with empty line calls emptyline."""
        result = framework.onecmd('')
        assert result == 0
    
    def test_onecmd_eof(self, framework, capsys):
        """Test onecmd with EOF."""
        original_stdin = sys.stdin
        result = framework.onecmd('EOF')
        sys.stdin = original_stdin
        assert result is None
    
    def test_onecmd_valid_command(self, framework, capsys):
        """Test onecmd with valid command."""
        # Use a simple command that outputs via print
        framework.onecmd('options')
        captured = capsys.readouterr()
        # Options shows help when called without subcommand
        assert 'Usage:' in captured.out or 'options' in captured.out.lower()
    
    def test_onecmd_exception_handling(self, framework, capsys):
        """Test onecmd handles exceptions in commands."""
        def failing_cmd(arg):
            raise ValueError("Test exception")
        framework.do_failing = failing_cmd
        framework._global_options['VERBOSITY'] = 1
        framework.onecmd('failing test')
        # Should not raise, exception is caught
    
    def test_print_topics(self, framework, capsys):
        """Test print_topics output."""
        # print_topics uses self.stdout which might be different
        # The framework uses cmd.Cmd's stdout attribute
        framework.stdout = sys.stdout  # Ensure stdout is set to sys.stdout
        framework.print_topics('Test Commands', ['back', 'exit'], 15, 80)
        captured = capsys.readouterr()
        assert 'Test Commands' in captured.out


# =============================================================================
# REQUEST METHOD TESTS
# =============================================================================

class TestRequestMethod:
    """Tests for the request method."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        return mock_framework
    
    @patch('requests.get')
    def test_request_basic(self, mock_get, framework):
        """Test basic request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = framework.request('GET', 'http://example.com')
        
        assert result.status_code == 200
        mock_get.assert_called_once()
    
    @patch('requests.post')
    def test_request_with_proxy(self, mock_post, framework):
        """Test request with proxy."""
        mock_response = MagicMock()
        mock_post.return_value = mock_response
        
        framework._global_options['PROXY'] = '127.0.0.1:8080'
        framework.request('POST', 'http://example.com', data={'key': 'value'})
        
        call_kwargs = mock_post.call_args[1]
        assert 'proxies' in call_kwargs
    
    @patch('requests.get')
    def test_request_sets_user_agent(self, mock_get, framework):
        """Test request sets User-Agent header."""
        mock_response = MagicMock()
        mock_get.return_value = mock_response
        
        framework.request('GET', 'http://example.com')
        
        call_kwargs = mock_get.call_args[1]
        assert 'User-Agent' in call_kwargs['headers']


# =============================================================================
# CONFIG METHODS TESTS
# =============================================================================

class TestConfigMethods:
    """Tests for configuration methods."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        mock_framework.options = Options()
        mock_framework.options.init_option('TEST_OPT', 'default', True, 'test')
        return mock_framework
    
    def test_save_config(self, framework, tmp_path):
        """Test _save_config saves to file."""
        config_file = tmp_path / "config.dat"
        framework.workspace = str(tmp_path)
        Framework.workspace = str(tmp_path)
        
        framework.options['TEST_OPT'] = 'new_value'
        framework._save_config('TEST_OPT')
        
        import json
        with open(config_file) as f:
            data = json.load(f)
        assert 'test' in data
        assert data['test']['TEST_OPT'] == 'new_value'
    
    def test_load_config(self, framework, tmp_path):
        """Test _load_config loads from file."""
        import json
        config_file = tmp_path / "config.dat"
        config_file.write_text(json.dumps({'test': {'TEST_OPT': 'loaded_value'}}))
        
        framework.workspace = str(tmp_path)
        Framework.workspace = str(tmp_path)
        framework._load_config()
        
        assert framework.options['TEST_OPT'] == 'loaded_value'
    
    def test_load_config_no_file(self, framework, tmp_path):
        """Test _load_config handles missing file."""
        framework.workspace = str(tmp_path)
        Framework.workspace = str(tmp_path)
        # Should not raise
        framework._load_config()
    
    def test_load_config_corrupt_file(self, framework, tmp_path):
        """Test _load_config handles corrupt file."""
        config_file = tmp_path / "config.dat"
        config_file.write_text("not valid json {{{")
        
        framework.workspace = str(tmp_path)
        Framework.workspace = str(tmp_path)
        # Should not raise
        framework._load_config()


# =============================================================================
# VALIDATE OPTIONS TESTS
# =============================================================================

class TestValidateOptions:
    """Tests for options validation."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        mock_framework.options = Options()
        mock_framework.options.init_option('REQUIRED_OPT', None, True, 'required')
        mock_framework.options.init_option('OPTIONAL_OPT', None, False, 'optional')
        return mock_framework
    
    def test_validate_options_missing_required(self, framework):
        """Test validation fails for missing required option."""
        with pytest.raises(FrameworkException) as exc_info:
            framework._validate_options()
        assert 'required' in str(exc_info.value).lower()
    
    def test_validate_options_with_required(self, framework):
        """Test validation passes with required option set."""
        framework.options['REQUIRED_OPT'] = 'value'
        # Should not raise
        framework._validate_options()
    
    def test_validate_options_bool_required(self, framework):
        """Test bool values are considered set."""
        framework.options['REQUIRED_OPT'] = False
        # Should not raise - bool is considered "set"
        framework._validate_options()


# =============================================================================
# LIST OPTIONS TESTS
# =============================================================================

class TestListOptions:
    """Tests for _list_options method."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        mock_framework.options = Options()
        return mock_framework
    
    def test_list_options_empty(self, framework, capsys):
        """Test _list_options with no options."""
        framework._list_options()
        captured = capsys.readouterr()
        assert 'No options' in captured.out
    
    def test_list_options_with_data(self, framework, capsys):
        """Test _list_options with options."""
        framework.options.init_option('OPT1', 'value1', True, 'First option')
        framework.options.init_option('OPT2', 'value2', False, 'Second option')
        
        framework._list_options()
        captured = capsys.readouterr()
        
        assert 'OPT1' in captured.out
        assert 'OPT2' in captured.out
        assert 'value1' in captured.out


# =============================================================================
# IS_WRITEABLE TESTS
# =============================================================================

class TestIsWriteable:
    """Tests for _is_writeable method."""
    
    @pytest.fixture
    def framework(self, mock_framework):
        return mock_framework
    
    def test_is_writeable_valid_file(self, framework, tmp_path):
        """Test _is_writeable returns True for writeable file."""
        test_file = tmp_path / "test.txt"
        assert framework._is_writeable(str(test_file)) is True
    
    def test_is_writeable_invalid_path(self, framework):
        """Test _is_writeable returns False for invalid path."""
        assert framework._is_writeable('/nonexistent_dir/test.txt') is False
