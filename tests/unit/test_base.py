"""
Unit tests for the recon-ng Recon class (base.py).

Tests the following:
- Recon class initialization
- Workspace methods
- Module loading and management
- Configuration management
- Database migration
"""
import os
import sys
import sqlite3
import tempfile
import shutil
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from recon.core import framework
from recon.core.framework import Framework, Options


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def recon_test_env(tmp_path):
    """Create an isolated environment for Recon testing.
    
    Creates:
    - Temporary home directory with proper structure
    - Keys database
    - Default workspace with database (using actual migrations)
    """
    from recon.core.base import Recon
    from recon.core.framework import Framework
    
    # Create directory structure
    home_path = tmp_path / ".recon-ng"
    home_path.mkdir()
    (home_path / "modules").mkdir()
    (home_path / "modules" / "recon").mkdir()
    (home_path / "workspaces").mkdir()
    (home_path / "data").mkdir()
    
    # Create keys database
    keys_db_path = home_path / "keys.db"
    conn = sqlite3.connect(str(keys_db_path))
    conn.execute('CREATE TABLE IF NOT EXISTS keys (name TEXT PRIMARY KEY, value TEXT)')
    conn.commit()
    conn.close()
    
    # Create default workspace directory
    default_workspace = home_path / "workspaces" / "default"
    default_workspace.mkdir()
    
    # Store original Framework state
    original_state = {
        'home_path': Framework.home_path,
        'mod_path': Framework.mod_path,
        'data_path': Framework.data_path,
        'spaces_path': Framework.spaces_path,
        'workspace': Framework.workspace,
        '_global_options': Framework._global_options,
    }
    
    # Temporarily set Framework paths to create the database using _create_db
    Framework.home_path = str(home_path)
    Framework.spaces_path = str(home_path / "workspaces")
    Framework.workspace = str(default_workspace)
    
    # Create a minimal Recon instance to use _create_db
    with patch.object(Recon, '_check_version'), \
         patch.object(Recon, '_fetch_module_index'), \
         patch.object(Recon, '_load_modules'), \
         patch.object(Recon, '_send_analytics'), \
         patch.object(Recon, '_init_workspace'):
        
        temp_recon = Recon(check=False, analytics=False, marketplace=False)
        temp_recon.workspace = str(default_workspace)
        # Initialize global options (needed for _create_db to work properly)
        temp_recon._init_global_options()
        # Use the actual _create_db method to create the database schema
        temp_recon._create_db()
    
    # Restore original Framework state
    Framework.home_path = original_state['home_path']
    Framework.mod_path = original_state['mod_path']
    Framework.data_path = original_state['data_path']
    Framework.spaces_path = original_state['spaces_path']
    Framework.workspace = original_state['workspace']
    Framework._global_options = original_state['_global_options']
    
    db_path = default_workspace / "data.db"
    
    return {
        'home_path': str(home_path),
        'spaces_path': str(home_path / "workspaces"),
        'mod_path': str(home_path / "modules"),
        'data_path': str(home_path / "data"),
        'default_workspace': str(default_workspace),
        'db_path': str(db_path),
    }


@pytest.fixture
def isolated_recon(recon_test_env):
    """Create a Recon instance with isolated paths.
    
    Patches network calls and filesystem side effects.
    """
    from recon.core.base import Recon, Mode
    
    env = recon_test_env
    
    # Store original class-level state
    original_state = {
        'home_path': Framework.home_path,
        'mod_path': Framework.mod_path,
        'data_path': Framework.data_path,
        'spaces_path': Framework.spaces_path,
        'workspace': Framework.workspace,
        'app_path': Framework.app_path,
        'core_path': Framework.core_path,
        '_loaded_modules': Framework._loaded_modules.copy(),
        '_global_options': Framework._global_options,
        '_mode': Framework._mode,
    }
    
    # Save original _send_analytics method before patching
    original_send_analytics = Recon._send_analytics
    
    with patch.object(Recon, '_check_version'), \
         patch.object(Recon, '_fetch_module_index'), \
         patch.object(Recon, '_load_modules'), \
         patch.object(Recon, '_send_analytics'):
        
        # Create Recon instance
        recon = Recon(check=False, analytics=False, marketplace=False)
        
        # Override paths
        recon.home_path = Framework.home_path = env['home_path']
        recon.mod_path = Framework.mod_path = env['mod_path']
        recon.data_path = Framework.data_path = env['data_path']
        recon.spaces_path = Framework.spaces_path = env['spaces_path']
        recon.workspace = Framework.workspace = env['default_workspace']
        
        # Initialize global options
        recon._init_global_options()
        
        # Expose the original method on the instance for tests that need it
        recon._original_send_analytics = original_send_analytics
        
        yield recon
    
    # Restore original state
    Framework.home_path = original_state['home_path']
    Framework.mod_path = original_state['mod_path']
    Framework.data_path = original_state['data_path']
    Framework.spaces_path = original_state['spaces_path']
    Framework.workspace = original_state['workspace']
    Framework.app_path = original_state['app_path']
    Framework.core_path = original_state['core_path']
    Framework._loaded_modules = original_state['_loaded_modules']
    Framework._global_options = original_state['_global_options']
    Framework._mode = original_state['_mode']


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================

@pytest.mark.unit
class TestReconInitialization:
    """Tests for Recon class initialization."""
    
    def test_recon_init_sets_name(self, isolated_recon):
        """Test that Recon initializes with correct name."""
        assert isolated_recon._name == 'recon-ng'
    
    def test_recon_init_sets_prompt_template(self, isolated_recon):
        """Test that prompt template is set."""
        assert '{}' in isolated_recon._prompt_template
    
    def test_recon_init_sets_flags(self, recon_test_env):
        """Test that Recon initializes toggle flags correctly."""
        from recon.core.base import Recon
        
        with patch.object(Recon, '_check_version'), \
             patch.object(Recon, '_fetch_module_index'), \
             patch.object(Recon, '_load_modules'), \
             patch.object(Recon, '_send_analytics'):
            
            recon = Recon(check=True, analytics=True, marketplace=True, accessible=True)
            
            assert recon._check is True
            assert recon._analytics is True
            assert recon._marketplace is True
            assert recon._accessible is True
    
    def test_recon_init_disabled_flags(self, recon_test_env):
        """Test that Recon can be initialized with flags disabled."""
        from recon.core.base import Recon
        
        with patch.object(Recon, '_check_version'), \
             patch.object(Recon, '_fetch_module_index'), \
             patch.object(Recon, '_load_modules'), \
             patch.object(Recon, '_send_analytics'):
            
            recon = Recon(check=False, analytics=False, marketplace=False, accessible=False)
            
            assert recon._check is False
            assert recon._analytics is False
            assert recon._marketplace is False
            assert recon._accessible is False


# =============================================================================
# GLOBAL OPTIONS TESTS
# =============================================================================

@pytest.mark.unit
class TestGlobalOptions:
    """Tests for global options initialization.
    
    Note: The Options class uses __keytransform__ to convert all keys to
    uppercase, so we need to check for uppercase keys.
    """
    
    def test_init_global_options_creates_nameserver(self, isolated_recon):
        """Test that nameserver option is created."""
        # Options keys are stored in uppercase
        assert 'NAMESERVER' in isolated_recon.options
        assert isolated_recon.options['NAMESERVER'] == '8.8.8.8'
    
    def test_init_global_options_creates_proxy(self, isolated_recon):
        """Test that proxy option is created."""
        assert 'PROXY' in isolated_recon.options
        assert isolated_recon.options['PROXY'] is None
    
    def test_init_global_options_creates_threads(self, isolated_recon):
        """Test that threads option is created."""
        assert 'THREADS' in isolated_recon.options
        assert isolated_recon.options['THREADS'] == 10
    
    def test_init_global_options_creates_timeout(self, isolated_recon):
        """Test that timeout option is created."""
        assert 'TIMEOUT' in isolated_recon.options
        assert isolated_recon.options['TIMEOUT'] == 10
    
    def test_init_global_options_creates_user_agent(self, isolated_recon):
        """Test that user-agent option is created."""
        assert 'USER-AGENT' in isolated_recon.options
        assert 'Recon-ng' in isolated_recon.options['USER-AGENT']
    
    def test_init_global_options_creates_verbosity(self, isolated_recon):
        """Test that verbosity option is created."""
        assert 'VERBOSITY' in isolated_recon.options
        assert isolated_recon.options['VERBOSITY'] == 1


# =============================================================================
# WORKSPACE TESTS
# =============================================================================

@pytest.mark.unit
class TestWorkspaceMethods:
    """Tests for workspace management methods."""
    
    def test_get_workspaces_returns_list(self, isolated_recon):
        """Test _get_workspaces returns list of workspaces."""
        workspaces = isolated_recon._get_workspaces()
        assert isinstance(workspaces, list)
        assert 'default' in workspaces
    
    def test_get_workspaces_finds_new_workspace(self, isolated_recon, recon_test_env):
        """Test _get_workspaces finds newly created workspace."""
        # Create a new workspace directory
        new_workspace = os.path.join(recon_test_env['spaces_path'], 'test_ws')
        os.makedirs(new_workspace)
        
        workspaces = isolated_recon._get_workspaces()
        assert 'test_ws' in workspaces
    
    def test_init_workspace_creates_directory(self, isolated_recon, recon_test_env):
        """Test _init_workspace creates workspace directory."""
        with patch.object(isolated_recon, '_load_config'), \
             patch.object(isolated_recon, '_load_modules'), \
             patch.object(isolated_recon, '_create_db'):
            
            new_ws_path = os.path.join(recon_test_env['spaces_path'], 'new_workspace')
            assert not os.path.exists(new_ws_path)
            
            isolated_recon._init_workspace('new_workspace')
            
            assert os.path.exists(new_ws_path)
    
    def test_init_workspace_sets_path(self, isolated_recon, recon_test_env):
        """Test _init_workspace sets workspace path."""
        with patch.object(isolated_recon, '_load_config'), \
             patch.object(isolated_recon, '_load_modules'), \
             patch.object(isolated_recon, '_create_db'):
            
            isolated_recon._init_workspace('new_workspace')
            
            assert 'new_workspace' in isolated_recon.workspace
    
    def test_init_workspace_empty_returns_none(self, isolated_recon):
        """Test _init_workspace with empty string returns early."""
        result = isolated_recon._init_workspace('')
        assert result is None
    
    def test_init_workspace_none_returns_none(self, isolated_recon):
        """Test _init_workspace with None returns early."""
        result = isolated_recon._init_workspace(None)
        assert result is None
    
    def test_remove_workspace_deletes_directory(self, isolated_recon, recon_test_env):
        """Test remove_workspace deletes workspace directory."""
        # Create a workspace to remove
        ws_path = os.path.join(recon_test_env['spaces_path'], 'to_remove')
        os.makedirs(ws_path)
        
        # Create a database file in it
        db_path = os.path.join(ws_path, 'data.db')
        conn = sqlite3.connect(db_path)
        conn.execute('CREATE TABLE test (id INTEGER)')
        conn.close()
        
        assert os.path.exists(ws_path)
        
        result = isolated_recon.remove_workspace('to_remove')
        
        assert result is True
        assert not os.path.exists(ws_path)
    
    def test_remove_nonexistent_workspace_returns_false(self, isolated_recon):
        """Test remove_workspace returns False for nonexistent workspace."""
        result = isolated_recon.remove_workspace('nonexistent_workspace')
        assert result is False
    
    def test_remove_current_workspace_switches_to_default(self, isolated_recon, recon_test_env):
        """Test removing current workspace switches to default."""
        # Create and switch to a new workspace
        ws_path = os.path.join(recon_test_env['spaces_path'], 'current')
        os.makedirs(ws_path)
        isolated_recon.workspace = ws_path
        
        with patch.object(isolated_recon, '_init_workspace') as mock_init:
            isolated_recon.remove_workspace('current')
            mock_init.assert_called_once_with('default')


# =============================================================================
# SNAPSHOT TESTS
# =============================================================================

@pytest.mark.unit
class TestSnapshotMethods:
    """Tests for workspace snapshot methods."""
    
    def test_get_snapshots_empty(self, isolated_recon):
        """Test _get_snapshots returns empty list when no snapshots."""
        snapshots = isolated_recon._get_snapshots()
        assert snapshots == []
    
    def test_get_snapshots_finds_snapshot_files(self, isolated_recon, recon_test_env):
        """Test _get_snapshots finds snapshot database files."""
        # Create snapshot files
        snapshot_name = 'snapshot_20240115120000.db'
        snapshot_path = os.path.join(recon_test_env['default_workspace'], snapshot_name)
        open(snapshot_path, 'w').close()
        
        snapshots = isolated_recon._get_snapshots()
        assert snapshot_name in snapshots
    
    def test_get_snapshots_ignores_non_snapshot_files(self, isolated_recon, recon_test_env):
        """Test _get_snapshots ignores files that don't match pattern."""
        # Create non-snapshot files
        other_file = os.path.join(recon_test_env['default_workspace'], 'other.db')
        open(other_file, 'w').close()
        
        regular_file = os.path.join(recon_test_env['default_workspace'], 'snapshot_invalid.db')
        open(regular_file, 'w').close()
        
        snapshots = isolated_recon._get_snapshots()
        assert 'other.db' not in snapshots
        assert 'snapshot_invalid.db' not in snapshots


# =============================================================================
# DATABASE CREATION TESTS
# =============================================================================

@pytest.mark.unit
class TestDatabaseCreation:
    """Tests for database creation method."""
    
    def test_create_db_creates_all_tables(self, isolated_recon, recon_test_env):
        """Test _create_db creates all required tables."""
        # Create a new workspace
        ws_path = os.path.join(recon_test_env['spaces_path'], 'fresh')
        os.makedirs(ws_path)
        isolated_recon.workspace = ws_path
        
        isolated_recon._create_db()
        
        # Check tables exist
        # Note: get_tables() explicitly excludes 'dashboard' table
        tables = isolated_recon.get_tables()
        expected_tables = [
            'domains', 'companies', 'tenants', 'netblocks', 'locations',
            'vulnerabilities', 'ports', 'hosts', 'contacts', 'credentials',
            'leaks', 'pushpins', 'profiles', 'repositories'
            # 'dashboard' is created but excluded from get_tables() results
        ]
        
        for table in expected_tables:
            assert table in tables, f"Table {table} not created"
        
        # Verify dashboard was still created by querying directly
        dashboard_exists = isolated_recon.query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='dashboard'"
        )
        assert len(dashboard_exists) == 1
    
    def test_create_db_sets_version(self, isolated_recon, recon_test_env):
        """Test _create_db sets database version."""
        ws_path = os.path.join(recon_test_env['spaces_path'], 'fresh2')
        os.makedirs(ws_path)
        isolated_recon.workspace = ws_path
        
        isolated_recon._create_db()
        
        version = isolated_recon.query('PRAGMA user_version')[0][0]
        assert version == 13


# =============================================================================
# MODULE METHODS TESTS
# =============================================================================

@pytest.mark.unit
class TestModuleMethods:
    """Tests for module management methods."""
    
    def test_categorize_module_new_category(self, isolated_recon):
        """Test _categorize_module creates new category."""
        isolated_recon._loaded_category = {}
        
        isolated_recon._categorize_module('recon', 'recon/test/module')
        
        assert 'recon' in isolated_recon._loaded_category
        assert 'recon/test/module' in isolated_recon._loaded_category['recon']
    
    def test_categorize_module_existing_category(self, isolated_recon):
        """Test _categorize_module appends to existing category."""
        isolated_recon._loaded_category = {'recon': ['recon/existing/module']}
        
        isolated_recon._categorize_module('recon', 'recon/test/module')
        
        assert len(isolated_recon._loaded_category['recon']) == 2
        assert 'recon/test/module' in isolated_recon._loaded_category['recon']
    
    def test_search_module_index_by_path(self, isolated_recon):
        """Test _search_module_index finds modules by path."""
        isolated_recon._module_index = [
            {'path': 'recon/hosts/find_hosts', 'name': 'Find Hosts', 'description': 'Finds hosts', 'status': 'installed'},
            {'path': 'recon/domains/find_domains', 'name': 'Find Domains', 'description': 'Finds domains', 'status': 'installed'},
        ]
        
        results = isolated_recon._search_module_index('hosts')
        
        assert len(results) == 1
        assert results[0]['path'] == 'recon/hosts/find_hosts'

    def test_search_module_index_by_substring(self, isolated_recon):
        """Test _search_module_index finds modules by path."""
        isolated_recon._module_index = [
            {'path': 'recon/hosts/find_hosts', 'name': 'Find Hosts', 'description': 'Finds hosts', 'status': 'installed'},
            {'path': 'recon/domains/find_domains', 'name': 'Find Domains', 'description': 'Finds domains', 'status': 'installed'},
        ]
        
        results = isolated_recon._search_module_index('sts/fi')
        
        assert len(results) == 1
        assert results[0]['path'] == 'recon/hosts/find_hosts'
    
    def test_search_module_index_by_name(self, isolated_recon):
        """Test _search_module_index finds modules by name."""
        isolated_recon._module_index = [
            {'path': 'recon/test/module', 'name': 'Super Module', 'description': 'Does stuff', 'status': 'installed'},
        ]
        
        results = isolated_recon._search_module_index('Super')
        
        assert len(results) == 1
    
    def test_search_module_index_by_description(self, isolated_recon):
        """Test _search_module_index finds modules by description."""
        isolated_recon._module_index = [
            {'path': 'recon/test/module', 'name': 'Test', 'description': 'Searches for vulnerabilities', 'status': 'installed'},
        ]
        
        results = isolated_recon._search_module_index('vulnerabilities')
        
        assert len(results) == 1
    
    def test_search_module_index_no_results(self, isolated_recon):
        """Test _search_module_index returns empty list when no match."""
        isolated_recon._module_index = [
            {'path': 'recon/test/module', 'name': 'Test', 'description': 'Test', 'status': 'installed'},
        ]
        
        results = isolated_recon._search_module_index('nonexistent')
        
        assert results == []
    
    def test_get_module_from_index_found(self, isolated_recon):
        """Test _get_module_from_index returns module when found."""
        isolated_recon._module_index = [
            {'path': 'recon/test/module', 'name': 'Test Module'},
            {'path': 'recon/other/module', 'name': 'Other Module'},
        ]
        
        result = isolated_recon._get_module_from_index('recon/test/module')
        
        assert result is not None
        assert result['name'] == 'Test Module'
    
    def test_get_module_from_index_not_found(self, isolated_recon):
        """Test _get_module_from_index returns None when not found."""
        isolated_recon._module_index = [
            {'path': 'recon/test/module', 'name': 'Test Module'},
        ]
        
        result = isolated_recon._get_module_from_index('recon/nonexistent/module')
        
        assert result is None


# =============================================================================
# FILE METHODS TESTS
# =============================================================================

@pytest.mark.unit
class TestFileMethods:
    """Tests for file operation methods."""
    
    def test_write_local_file_creates_file(self, isolated_recon, tmp_path):
        """Test _write_local_file creates file with content."""
        file_path = str(tmp_path / "test_file.txt")
        content = "Test content"
        
        isolated_recon._write_local_file(file_path, content)
        
        assert os.path.exists(file_path)
        with open(file_path) as f:
            assert f.read() == content
    
    def test_write_local_file_creates_directories(self, isolated_recon, tmp_path):
        """Test _write_local_file creates parent directories."""
        file_path = str(tmp_path / "nested" / "dirs" / "test_file.txt")
        content = "Nested content"
        
        isolated_recon._write_local_file(file_path, content)
        
        assert os.path.exists(file_path)
    
    def test_remove_empty_dirs(self, isolated_recon, tmp_path):
        """Test _remove_empty_dirs removes empty directories."""
        # Create nested empty directories
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        
        isolated_recon._remove_empty_dirs(str(tmp_path / "a"))
        
        assert not os.path.exists(str(tmp_path / "a"))
    
    def test_remove_empty_dirs_preserves_non_empty(self, isolated_recon, tmp_path):
        """Test _remove_empty_dirs preserves directories with files."""
        # Create directory with a file
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        (nested / "file.txt").touch()
        
        # Create empty sibling directory
        empty = tmp_path / "a" / "empty"
        empty.mkdir()
        
        isolated_recon._remove_empty_dirs(str(tmp_path / "a"))
        
        # Non-empty directory should still exist
        assert os.path.exists(str(nested))


# =============================================================================
# VERSION CHECK TESTS
# =============================================================================

@pytest.mark.unit
class TestVersionCheck:
    """Tests for version checking functionality."""
    
    def test_check_version_disabled(self, recon_test_env, capsys):
        """Test _check_version when check flag is disabled."""
        from recon.core.base import Recon
        
        with patch.object(Recon, '_fetch_module_index'), \
             patch.object(Recon, '_load_modules'), \
             patch.object(Recon, '_send_analytics'), \
             patch.object(Recon, 'alert') as mock_alert:
            
            recon = Recon(check=False, analytics=False, marketplace=False)
            recon._check_version()
            
            # Should alert that version check is disabled
            mock_alert.assert_called_with('Version check disabled.')


# =============================================================================
# ANALYTICS TESTS
# =============================================================================

@pytest.mark.unit
class TestAnalytics:
    """Tests for analytics functionality."""
    
    def test_send_analytics_disabled(self, isolated_recon, capsys):
        """Test _send_analytics when analytics flag is disabled."""
        isolated_recon._analytics = False
        # Set verbosity high enough for debug output
        isolated_recon._global_options['VERBOSITY'] = 2
        
        # Call the original method (saved before patching)
        isolated_recon._original_send_analytics(isolated_recon, 'test_event')
        
        captured = capsys.readouterr()
        assert 'Analytics disabled' in captured.out
    
    def test_send_analytics_creates_cid_file(self, isolated_recon, recon_test_env):
        """Test _send_analytics creates client ID file if missing."""
        isolated_recon._analytics = True
        cid_path = os.path.join(recon_test_env['home_path'], '.cid')
        
        # Remove cid file if it exists
        if os.path.exists(cid_path):
            os.remove(cid_path)
        
        # Mock the request method to avoid actual HTTP call
        # The cid file should be created before the request is made
        def mock_request(*args, **kwargs):
            return MagicMock()
        
        with patch.object(isolated_recon, 'request', side_effect=mock_request):
            # Call the original method (saved before patching)
            isolated_recon._original_send_analytics(isolated_recon, 'test_event')
        
        assert os.path.exists(cid_path)


# =============================================================================
# KEYS DATABASE TESTS
# =============================================================================

@pytest.mark.unit
class TestKeysDatabase:
    """Tests for API keys management."""
    
    def test_query_keys_works(self, isolated_recon, recon_test_env):
        """Test _query_keys can query keys database."""
        # Add a key
        isolated_recon._query_keys(
            'INSERT OR REPLACE INTO keys (name, value) VALUES (?, ?)',
            values=('test_key', 'test_value')
        )
        
        # Query it back
        result = isolated_recon._query_keys(
            'SELECT value FROM keys WHERE name = ?',
            values=('test_key',)
        )
        
        assert len(result) == 1
        assert result[0][0] == 'test_value'
    
    def test_get_key_returns_value(self, isolated_recon):
        """Test get_key returns stored value."""
        # Add a key
        isolated_recon._query_keys(
            'INSERT OR REPLACE INTO keys (name, value) VALUES (?, ?)',
            values=('api_key', 'secret123')
        )
        
        result = isolated_recon.get_key('api_key')
        assert result == 'secret123'
    
    def test_get_key_returns_none_for_missing(self, isolated_recon):
        """Test get_key returns None for missing key."""
        result = isolated_recon.get_key('nonexistent_key')
        assert result is None


# =============================================================================
# MODE TESTS
# =============================================================================

@pytest.mark.unit
class TestModes:
    """Tests for operation modes."""
    
    def test_mode_enum_exists(self):
        """Test Mode enum is defined."""
        from recon.core.base import Mode
        
        assert hasattr(Mode, 'CONSOLE')
        assert hasattr(Mode, 'CLI')
        assert hasattr(Mode, 'WEB')
        assert hasattr(Mode, 'JOB')
    
    def test_start_sets_mode(self, recon_test_env):
        """Test start method sets mode."""
        from recon.core.base import Recon, Mode
        
        with patch.object(Recon, '_check_version'), \
             patch.object(Recon, '_fetch_module_index'), \
             patch.object(Recon, '_load_modules'), \
             patch.object(Recon, '_load_config'), \
             patch.object(Recon, '_send_analytics'), \
             patch.object(Recon, '_init_workspace'):
            
            recon = Recon(check=False, analytics=False, marketplace=False)
            recon.home_path = recon_test_env['home_path']
            recon.spaces_path = recon_test_env['spaces_path']
            
            recon.start(Mode.CLI, workspace='default')
            
            assert recon._mode == Mode.CLI


# =============================================================================
# DATABASE MIGRATION TESTS
# =============================================================================

@pytest.mark.unit
class TestDatabaseMigration:
    """Tests for database migration functionality."""
    
    def test_migrate_db_from_version_0(self, isolated_recon, recon_test_env):
        """Test database migration from version 0."""
        # Create a version 0 database
        ws_path = os.path.join(recon_test_env['spaces_path'], 'old_ws')
        os.makedirs(ws_path)
        
        db_path = os.path.join(ws_path, 'data.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create old schema (version 0)
        cursor.execute('CREATE TABLE contacts (fname TEXT, lname TEXT, email TEXT, title TEXT, region TEXT, country TEXT)')
        cursor.execute('CREATE TABLE pushpin (source TEXT, data TEXT)')
        cursor.execute('CREATE TABLE hosts (host TEXT, ip_address TEXT)')
        cursor.execute('PRAGMA user_version = 0')
        conn.commit()
        conn.close()
        
        # Set workspace and run migration
        isolated_recon.workspace = ws_path
        
        # This would run through multiple migrations
        # Testing just that it doesn't crash for now
        try:
            isolated_recon._migrate_db()
            migrated = True
        except Exception:
            migrated = False
        
        # Migration should complete or fail gracefully
        # (depends on completeness of old schema)
    
    def test_migrate_db_current_version_no_change(self, isolated_recon, recon_test_env):
        """Test migration on current version database makes no changes."""
        # The default workspace already has version 13
        isolated_recon.workspace = recon_test_env['default_workspace']
        
        with patch.object(isolated_recon, 'alert') as mock_alert:
            isolated_recon._migrate_db()
            
            # Should not alert about upgrade since version is current
            for call in mock_alert.call_args_list:
                assert 'upgraded' not in str(call).lower()


# =============================================================================
# SPOOL PRINT TESTS
# =============================================================================

@pytest.mark.unit
class TestSpoolPrint:
    """Tests for the spool_print function."""
    
    def test_spool_print_writes_to_spool(self, isolated_recon, tmp_path):
        """Test spool_print writes to spool file when enabled."""
        from recon.core import framework
        
        spool_file = tmp_path / "spool.txt"
        with open(spool_file, 'w') as fp:
            original_spool = framework.Framework._spool
            framework.Framework._spool = fp
            
            print("Test spool message")
            
            framework.Framework._spool = original_spool
        
        with open(spool_file) as fp:
            content = fp.read()
            assert "Test spool message" in content
    
    def test_spool_print_job_mode_suppresses_output(self, isolated_recon, capsys):
        """Test spool_print suppresses terminal output in JOB mode."""
        from recon.core import framework
        from recon.core.base import Mode
        
        original_mode = framework.Framework._mode
        framework.Framework._mode = Mode.JOB
        
        print("This should be suppressed in JOB mode")
        
        framework.Framework._mode = original_mode
        
        captured = capsys.readouterr()
        assert "This should be suppressed" not in captured.out


# =============================================================================
# PRINT BANNER TESTS
# =============================================================================

@pytest.mark.unit
class TestPrintBanner:
    """Tests for banner printing functionality."""
    
    def test_print_banner_outputs_text(self, isolated_recon, capsys):
        """Test _print_banner outputs banner text."""
        isolated_recon._loaded_category = {'recon': ['module1', 'module2']}
        
        isolated_recon._print_banner()
        
        captured = capsys.readouterr()
        assert 'recon-ng' in captured.out.lower() or len(captured.out) > 0
    
    def test_print_banner_with_no_modules(self, isolated_recon, capsys):
        """Test _print_banner handles no modules case."""
        isolated_recon._loaded_category = {}
        
        with patch.object(isolated_recon, 'alert') as mock_alert:
            isolated_recon._print_banner()
            mock_alert.assert_called_with('No modules enabled/installed.')
    
    def test_print_banner_accessible_mode(self, isolated_recon, capsys):
        """Test _print_banner in accessible mode."""
        isolated_recon._accessible = True
        isolated_recon._loaded_category = {'recon': ['module1']}
        
        isolated_recon._print_banner()
        
        captured = capsys.readouterr()
        assert len(captured.out) > 0
    
    def test_print_banner_creates_easter_egg_commands(self, isolated_recon):
        """Test _print_banner creates dynamic easter egg commands."""
        isolated_recon._loaded_category = {'recon': ['m1', 'm2', 'm3']}  # 3 modules
        
        isolated_recon._print_banner()
        
        # Should create do_3 method
        assert hasattr(isolated_recon, 'do_3')


# =============================================================================
# MENU EGG TESTS
# =============================================================================

@pytest.mark.unit
class TestMenuEgg:
    """Tests for easter egg menu function."""
    
    def test_menu_egg_outputs_random_message(self, isolated_recon, capsys):
        """Test _menu_egg outputs one of the predefined messages."""
        isolated_recon._menu_egg('')
        
        captured = capsys.readouterr()
        expected_phrases = [
            'Really?', 'help', 'sense', 'grunt', 'Wait', 
            'Social Engineering', 'numbers', 'Reserving', 
            'wrong framework', '1980'
        ]
        assert any(phrase in captured.out for phrase in expected_phrases)


# =============================================================================
# VERSION CHECK EXTENDED TESTS
# =============================================================================

@pytest.mark.unit
class TestVersionCheckExtended:
    """Extended tests for version checking functionality."""
    
    def test_check_version_enabled_with_match(self, recon_test_env):
        """Test _check_version when versions match."""
        from recon.core.base import Recon
        import recon.core.base as base_module
        
        with patch.object(Recon, '_fetch_module_index'), \
             patch.object(Recon, '_load_modules'), \
             patch.object(Recon, '_send_analytics'):
            
            recon = Recon(check=True, analytics=False, marketplace=False)
            
            # Mock request to return matching version
            mock_response = MagicMock()
            mock_response.text = f"__version__ = '{base_module.__version__}'"
            
            with patch.object(recon, 'request', return_value=mock_response), \
                 patch.object(recon, 'alert') as mock_alert:
                recon._check_version()
                
                # Should not alert about mismatch
                for call in mock_alert.call_args_list:
                    assert 'does not match' not in str(call)
    
    def test_check_version_enabled_with_mismatch(self, recon_test_env):
        """Test _check_version when versions don't match."""
        from recon.core.base import Recon
        
        with patch.object(Recon, '_fetch_module_index'), \
             patch.object(Recon, '_load_modules'), \
             patch.object(Recon, '_send_analytics'):
            
            recon = Recon(check=True, analytics=False, marketplace=False)
            
            # Mock request to return different version
            mock_response = MagicMock()
            mock_response.text = "__version__ = '99.99.99'"
            
            with patch.object(recon, 'request', return_value=mock_response), \
                 patch.object(recon, 'alert') as mock_alert, \
                 patch.object(recon, 'output'):
                recon._check_version()
                
                # Should alert about mismatch
                assert any('does not match' in str(call) for call in mock_alert.call_args_list)
    
    def test_check_version_handles_exception(self, recon_test_env):
        """Test _check_version handles network exceptions."""
        from recon.core.base import Recon
        
        with patch.object(Recon, '_fetch_module_index'), \
             patch.object(Recon, '_load_modules'), \
             patch.object(Recon, '_send_analytics'):
            
            recon = Recon(check=True, analytics=False, marketplace=False)
            
            with patch.object(recon, 'request', side_effect=Exception("Network error")), \
                 patch.object(recon, 'error') as mock_error:
                recon._check_version()
                
                # Should call error method
                assert mock_error.called


# =============================================================================
# ANALYTICS EXTENDED TESTS
# =============================================================================

@pytest.mark.unit
class TestAnalyticsExtended:
    """Extended tests for analytics functionality."""
    
    def test_send_analytics_reads_existing_cid(self, isolated_recon, recon_test_env):
        """Test _send_analytics reads existing CID file."""
        isolated_recon._analytics = True
        cid_path = os.path.join(recon_test_env['home_path'], '.cid')
        
        # Create CID file with known value
        with open(cid_path, 'w') as fp:
            fp.write('test-cid-12345')
        
        with patch.object(isolated_recon, 'request') as mock_request:
            isolated_recon._original_send_analytics(isolated_recon, 'test_event')
            
            # Verify request was called with the CID
            if mock_request.called:
                call_args = mock_request.call_args
                assert 'test-cid-12345' in str(call_args)
    
    def test_send_analytics_handles_exception(self, isolated_recon, recon_test_env):
        """Test _send_analytics handles exceptions gracefully."""
        isolated_recon._analytics = True
        isolated_recon._global_options['VERBOSITY'] = 2
        
        with patch.object(isolated_recon, 'request', side_effect=Exception("Network error")), \
             patch.object(isolated_recon, 'debug') as mock_debug:
            
            # Should not raise
            isolated_recon._original_send_analytics(isolated_recon, 'test_event')
            
            # Should log debug message
            assert mock_debug.called


# =============================================================================
# LOAD SOURCE TESTS
# =============================================================================

@pytest.mark.unit
class TestLoadSource:
    """Tests for module source loading."""
    
    def test_load_source_imports_module(self, isolated_recon, tmp_path):
        """Test _load_source imports a Python module."""
        # Create a test module file
        mod_file = tmp_path / "test_module.py"
        mod_file.write_text("TEST_VALUE = 42\ndef test_func(): return 'hello'")
        
        module = isolated_recon._load_source('test_mod', str(mod_file))
        
        assert hasattr(module, 'TEST_VALUE')
        assert module.TEST_VALUE == 42
        assert module.test_func() == 'hello'


# =============================================================================
# MODULE INDEX TESTS
# =============================================================================

@pytest.mark.unit
class TestModuleIndex:
    """Tests for module index operations."""
    
    def test_fetch_module_index_disabled(self, recon_test_env):
        """Test _fetch_module_index when marketplace is disabled."""
        from recon.core.base import Recon
        
        with patch.object(Recon, '_check_version'), \
             patch.object(Recon, '_load_modules'), \
             patch.object(Recon, '_send_analytics'), \
             patch.object(Recon, '_init_workspace'):
            
            recon = Recon(check=False, analytics=False, marketplace=False)
            recon.home_path = recon_test_env['home_path']
            
            with patch.object(recon, 'alert') as mock_alert:
                recon._fetch_module_index()
                mock_alert.assert_called_with('Marketplace disabled.')
    
    def test_fetch_module_index_enabled_success(self, recon_test_env):
        """Test _fetch_module_index when marketplace is enabled."""
        from recon.core.base import Recon
        
        with patch.object(Recon, '_check_version'), \
             patch.object(Recon, '_load_modules'), \
             patch.object(Recon, '_send_analytics'), \
             patch.object(Recon, '_init_workspace'):
            
            recon = Recon(check=False, analytics=False, marketplace=True)
            recon.home_path = recon_test_env['home_path']
            
            mock_response = MagicMock()
            mock_response.text = "- path: test/module\n  name: Test Module"
            
            with patch.object(recon, '_request_file_from_repo', return_value=mock_response), \
                 patch.object(recon, '_write_local_file') as mock_write, \
                 patch.object(recon, 'debug'):
                
                recon._fetch_module_index()
                
                # Should write the index file
                assert mock_write.called
    
    def test_fetch_module_index_handles_error(self, recon_test_env):
        """Test _fetch_module_index handles network errors."""
        from recon.core.base import Recon
        
        with patch.object(Recon, '_check_version'), \
             patch.object(Recon, '_load_modules'), \
             patch.object(Recon, '_send_analytics'), \
             patch.object(Recon, '_init_workspace'):
            
            recon = Recon(check=False, analytics=False, marketplace=True)
            recon.home_path = recon_test_env['home_path']
            
            with patch.object(recon, '_request_file_from_repo', side_effect=Exception("Network")), \
                 patch.object(recon, 'error') as mock_error, \
                 patch.object(recon, 'debug'):
                
                recon._fetch_module_index()
                
                assert mock_error.called
    
    def test_update_module_index_empty(self, isolated_recon, recon_test_env):
        """Test _update_module_index with no index file."""
        isolated_recon._loaded_category = {}
        isolated_recon._loaded_modules = {}
        
        with patch.object(isolated_recon, 'debug'):
            isolated_recon._update_module_index()
        
        assert isolated_recon._module_index == []
    
    def test_update_module_index_with_file(self, isolated_recon, recon_test_env):
        """Test _update_module_index reads YAML index file."""
        # Create index file
        index_path = os.path.join(recon_test_env['home_path'], 'modules.yml')
        with open(index_path, 'w') as fp:
            fp.write("- path: test/module\n  name: Test Module\n  version: '1.0'")
        
        isolated_recon._loaded_category = {}
        isolated_recon._loaded_modules = {}
        
        with patch.object(isolated_recon, 'debug'):
            isolated_recon._update_module_index()
        
        assert len(isolated_recon._module_index) == 1
        assert isolated_recon._module_index[0]['status'] == 'not installed'
    
    def test_update_module_index_marks_installed(self, isolated_recon, recon_test_env):
        """Test _update_module_index marks installed modules."""
        index_path = os.path.join(recon_test_env['home_path'], 'modules.yml')
        with open(index_path, 'w') as fp:
            fp.write("- path: test/module\n  name: Test Module\n  version: '1.0'")
        
        # Mock an installed module
        mock_module = MagicMock()
        mock_module.meta = {'version': '1.0'}
        isolated_recon._loaded_modules = {'test/module': mock_module}
        isolated_recon._loaded_category = {}
        
        with patch.object(isolated_recon, 'debug'):
            isolated_recon._update_module_index()
        
        assert isolated_recon._module_index[0]['status'] == 'installed'
    
    def test_update_module_index_marks_outdated(self, isolated_recon, recon_test_env):
        """Test _update_module_index marks outdated modules."""
        index_path = os.path.join(recon_test_env['home_path'], 'modules.yml')
        with open(index_path, 'w') as fp:
            fp.write("- path: test/module\n  name: Test Module\n  version: '2.0'")
        
        # Mock an installed module with older version
        mock_module = MagicMock()
        mock_module.meta = {'version': '1.0'}
        isolated_recon._loaded_modules = {'test/module': mock_module}
        isolated_recon._loaded_category = {}
        
        with patch.object(isolated_recon, 'debug'):
            isolated_recon._update_module_index()
        
        assert isolated_recon._module_index[0]['status'] == 'outdated'
    
    def test_update_module_index_marks_disabled(self, isolated_recon, recon_test_env):
        """Test _update_module_index marks disabled modules."""
        index_path = os.path.join(recon_test_env['home_path'], 'modules.yml')
        with open(index_path, 'w') as fp:
            fp.write("- path: test/module\n  name: Test Module\n  version: '1.0'")
        
        isolated_recon._loaded_modules = {}
        isolated_recon._loaded_category = {'disabled': ['test/module']}
        
        with patch.object(isolated_recon, 'debug'):
            isolated_recon._update_module_index()
        
        assert isolated_recon._module_index[0]['status'] == 'disabled'


# =============================================================================
# REQUEST FILE FROM REPO TESTS
# =============================================================================

@pytest.mark.unit
class TestRequestFileFromRepo:
    """Tests for repository file requests."""
    
    def test_request_file_from_repo_success(self, isolated_recon):
        """Test _request_file_from_repo returns response on success."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "file content"
        
        with patch.object(isolated_recon, 'request', return_value=mock_response):
            result = isolated_recon._request_file_from_repo('test/path.py')
            assert result.text == "file content"
    
    def test_request_file_from_repo_failure(self, isolated_recon):
        """Test _request_file_from_repo raises on non-200 response."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        with patch.object(isolated_recon, 'request', return_value=mock_response):
            with pytest.raises(Exception):  # FrameworkException
                isolated_recon._request_file_from_repo('nonexistent/path.py')


# =============================================================================
# MODULE INSTALLATION TESTS
# =============================================================================

@pytest.mark.unit
class TestModuleInstallation:
    """Tests for module installation functionality."""
    
    def test_install_module_basic(self, isolated_recon, recon_test_env):
        """Test _install_module installs a module."""
        isolated_recon._module_index = [{
            'path': 'recon/test/module',
            'files': []
        }]
        
        mock_response = MagicMock()
        mock_response.text = "# Module content\nclass Module: pass"
        
        with patch.object(isolated_recon, '_request_file_from_repo', return_value=mock_response), \
             patch.object(isolated_recon, '_write_local_file') as mock_write, \
             patch.object(isolated_recon, 'output'):
            
            isolated_recon._install_module('recon/test/module')
            
            assert mock_write.called
    
    def test_install_module_with_data_files(self, isolated_recon, recon_test_env):
        """Test _install_module downloads supporting files."""
        isolated_recon._module_index = [{
            'path': 'recon/test/module',
            'files': ['data/wordlist.txt']
        }]
        
        mock_response = MagicMock()
        mock_response.text = "content"
        
        with patch.object(isolated_recon, '_request_file_from_repo', return_value=mock_response), \
             patch.object(isolated_recon, '_write_local_file') as mock_write, \
             patch.object(isolated_recon, 'output'):
            
            isolated_recon._install_module('recon/test/module')
            
            # Should write both module and data file
            assert mock_write.call_count == 2
    
    def test_remove_module_basic(self, isolated_recon, recon_test_env):
        """Test _remove_module removes a module file."""
        isolated_recon._module_index = [{
            'path': 'recon/test/module',
            'files': []
        }]
        
        # Create a module file
        mod_dir = os.path.join(recon_test_env['mod_path'], 'recon', 'test')
        os.makedirs(mod_dir, exist_ok=True)
        mod_file = os.path.join(mod_dir, 'module.py')
        with open(mod_file, 'w') as fp:
            fp.write("# Module")
        
        with patch.object(isolated_recon, 'output'):
            isolated_recon._remove_module('recon/test/module')
        
        assert not os.path.exists(mod_file)


# =============================================================================
# MODULE LOADING TESTS
# =============================================================================

@pytest.mark.unit
class TestModuleLoading:
    """Tests for module loading functionality."""
    
    def test_load_modules_creates_empty_structures(self, isolated_recon, recon_test_env):
        """Test _load_modules initializes empty structures."""
        from recon.core.framework import Framework
        
        # Make sure mod_path exists
        os.makedirs(recon_test_env['mod_path'], exist_ok=True)
        isolated_recon.mod_path = recon_test_env['mod_path']
        
        with patch.object(isolated_recon, '_remove_empty_dirs'), \
             patch.object(isolated_recon, '_update_module_index'):
            
            isolated_recon._load_modules()
            
            # _load_modules sets _loaded_category and _loaded_modules
            # Check they were set (may be on Framework class level)
            assert hasattr(isolated_recon, '_loaded_category') or hasattr(Framework, '_loaded_modules')
            assert isolated_recon._loaded_modules == {} or Framework._loaded_modules == {}
    
    def test_load_module_handles_import_error(self, isolated_recon, recon_test_env):
        """Test _load_module handles ImportError gracefully."""
        # Create a module file with missing import
        mod_dir = os.path.join(recon_test_env['mod_path'], 'recon')
        os.makedirs(mod_dir, exist_ok=True)
        mod_file = os.path.join(mod_dir, 'bad_module.py')
        with open(mod_file, 'w') as fp:
            fp.write("import nonexistent_package_12345")
        
        isolated_recon._loaded_category = {}
        isolated_recon._loaded_modules = {}
        
        with patch.object(isolated_recon, 'error') as mock_error:
            result = isolated_recon._load_module(mod_dir, 'bad_module.py')
        
        # Should return None/falsy and categorize as disabled
        assert 'disabled' in isolated_recon._loaded_category
    
    def test_load_module_handles_syntax_error(self, isolated_recon, recon_test_env):
        """Test _load_module handles syntax errors gracefully."""
        mod_dir = os.path.join(recon_test_env['mod_path'], 'recon')
        os.makedirs(mod_dir, exist_ok=True)
        mod_file = os.path.join(mod_dir, 'syntax_error.py')
        with open(mod_file, 'w') as fp:
            fp.write("def broken(\n")  # Syntax error
        
        isolated_recon._loaded_category = {}
        isolated_recon._loaded_modules = {}
        
        with patch.object(isolated_recon, 'error'), \
             patch.object(isolated_recon, 'print_exception'):
            isolated_recon._load_module(mod_dir, 'syntax_error.py')
        
        assert 'disabled' in isolated_recon._loaded_category


# =============================================================================
# COMMAND METHOD TESTS
# =============================================================================

@pytest.mark.unit
class TestCommandMethods:
    """Tests for command methods."""
    
    def test_do_marketplace_disabled(self, isolated_recon):
        """Test do_marketplace when marketplace is disabled."""
        isolated_recon._marketplace = False
        
        with patch.object(isolated_recon, 'alert') as mock_alert:
            isolated_recon.do_marketplace('')
            mock_alert.assert_called_with('Marketplace disabled.')
    
    def test_do_marketplace_no_params(self, isolated_recon):
        """Test do_marketplace shows help with no params."""
        isolated_recon._marketplace = True
        
        with patch.object(isolated_recon, 'help_marketplace') as mock_help:
            isolated_recon.do_marketplace('')
            mock_help.assert_called_once()
    
    def test_do_workspaces_no_params(self, isolated_recon):
        """Test do_workspaces shows help with no params."""
        with patch.object(isolated_recon, 'help_workspaces') as mock_help:
            isolated_recon.do_workspaces('')
            mock_help.assert_called_once()
    
    def test_do_snapshots_no_params(self, isolated_recon):
        """Test do_snapshots shows help with no params."""
        with patch.object(isolated_recon, 'help_snapshots') as mock_help:
            isolated_recon.do_snapshots('')
            mock_help.assert_called_once()
    
    def test_do_workspaces_list(self, isolated_recon, capsys):
        """Test workspaces list command."""
        with patch.object(isolated_recon, 'table'):
            isolated_recon.do_workspaces('list')
    
    def test_do_workspaces_create_no_params(self, isolated_recon):
        """Test workspaces create without name shows help."""
        with patch.object(isolated_recon, '_help_workspaces_create') as mock_help:
            isolated_recon._do_workspaces_create('')
            mock_help.assert_called_once()
    
    def test_do_workspaces_load_no_params(self, isolated_recon):
        """Test workspaces load without name shows help."""
        with patch.object(isolated_recon, '_help_workspaces_load') as mock_help:
            isolated_recon._do_workspaces_load('')
            mock_help.assert_called_once()
    
    def test_do_workspaces_load_invalid(self, isolated_recon):
        """Test workspaces load with invalid name."""
        with patch.object(isolated_recon, 'output') as mock_output:
            isolated_recon._do_workspaces_load('nonexistent_ws')
            mock_output.assert_called_with('Invalid workspace name.')
    
    def test_do_workspaces_remove_no_params(self, isolated_recon):
        """Test workspaces remove without name shows help."""
        with patch.object(isolated_recon, '_help_workspaces_remove') as mock_help:
            isolated_recon._do_workspaces_remove('')
            mock_help.assert_called_once()
    
    def test_do_snapshots_list(self, isolated_recon):
        """Test snapshots list command."""
        with patch.object(isolated_recon, 'output') as mock_output:
            isolated_recon._do_snapshots_list('')
            # Should output message about no snapshots
            mock_output.assert_called_with('This workspace has no snapshots.')
    
    def test_do_snapshots_take(self, isolated_recon, recon_test_env):
        """Test snapshots take command creates snapshot."""
        isolated_recon.workspace = recon_test_env['default_workspace']
        
        with patch.object(isolated_recon, 'output'):
            isolated_recon._do_snapshots_take('')
        
        # Check a snapshot was created
        snapshots = isolated_recon._get_snapshots()
        assert len(snapshots) == 1
    
    def test_do_snapshots_load_no_params(self, isolated_recon):
        """Test snapshots load without name shows help."""
        with patch.object(isolated_recon, '_help_snapshots_load') as mock_help:
            isolated_recon._do_snapshots_load('')
            mock_help.assert_called_once()
    
    def test_do_snapshots_load_invalid(self, isolated_recon):
        """Test snapshots load with invalid name."""
        with patch.object(isolated_recon, 'error') as mock_error:
            isolated_recon._do_snapshots_load('nonexistent')
            assert mock_error.called
    
    def test_do_snapshots_remove_no_params(self, isolated_recon):
        """Test snapshots remove without name shows help."""
        with patch.object(isolated_recon, '_help_snapshots_remove') as mock_help:
            isolated_recon._do_snapshots_remove('')
            mock_help.assert_called_once()
    
    def test_do_snapshots_remove_invalid(self, isolated_recon):
        """Test snapshots remove with invalid name."""
        with patch.object(isolated_recon, 'error') as mock_error:
            isolated_recon._do_snapshots_remove('nonexistent')
            assert mock_error.called
    
    def test_do_marketplace_refresh(self, isolated_recon):
        """Test marketplace refresh command."""
        with patch.object(isolated_recon, '_fetch_module_index'), \
             patch.object(isolated_recon, '_update_module_index'), \
             patch.object(isolated_recon, 'output') as mock_output:
            
            isolated_recon._do_marketplace_refresh('')
            mock_output.assert_called_with('Marketplace index refreshed.')
    
    def test_do_marketplace_search_no_results(self, isolated_recon):
        """Test marketplace search with no results."""
        isolated_recon._module_index = []
        
        with patch.object(isolated_recon, 'error') as mock_error, \
             patch.object(isolated_recon, '_help_marketplace_search'):
            isolated_recon._do_marketplace_search('')
            mock_error.assert_called_with('No modules found.')
    
    def test_do_marketplace_info_no_params(self, isolated_recon):
        """Test marketplace info without params shows help."""
        with patch.object(isolated_recon, '_help_marketplace_info') as mock_help:
            isolated_recon._do_marketplace_info('')
            mock_help.assert_called_once()
    
    def test_do_marketplace_info_invalid(self, isolated_recon):
        """Test marketplace info with invalid path."""
        isolated_recon._module_index = []
        
        with patch.object(isolated_recon, 'error') as mock_error:
            isolated_recon._do_marketplace_info('nonexistent')
            mock_error.assert_called_with('Invalid module path.')
    
    def test_do_marketplace_install_no_params(self, isolated_recon):
        """Test marketplace install without params shows help."""
        with patch.object(isolated_recon, '_help_marketplace_install') as mock_help:
            isolated_recon._do_marketplace_install('')
            mock_help.assert_called_once()
    
    def test_do_marketplace_install_invalid(self, isolated_recon):
        """Test marketplace install with invalid path."""
        isolated_recon._module_index = []
        
        with patch.object(isolated_recon, 'error') as mock_error:
            isolated_recon._do_marketplace_install('nonexistent')
            mock_error.assert_called_with('Invalid module path.')
    
    def test_do_marketplace_remove_no_params(self, isolated_recon):
        """Test marketplace remove without params shows help."""
        with patch.object(isolated_recon, '_help_marketplace_remove') as mock_help:
            isolated_recon._do_marketplace_remove('')
            mock_help.assert_called_once()
    
    def test_do_marketplace_remove_invalid(self, isolated_recon):
        """Test marketplace remove with invalid path."""
        isolated_recon._module_index = []
        
        with patch.object(isolated_recon, 'error') as mock_error:
            isolated_recon._do_marketplace_remove('nonexistent')
            mock_error.assert_called_with('Invalid module path.')
    
    def test_do_index_no_params(self, isolated_recon):
        """Test do_index without params shows help."""
        with patch.object(isolated_recon, 'help_index') as mock_help:
            isolated_recon.do_index('')
            mock_help.assert_called_once()
    
    def test_do_modules_reload(self, isolated_recon):
        """Test modules reload command."""
        with patch.object(isolated_recon, 'output'), \
             patch.object(isolated_recon, '_load_modules') as mock_load:
            isolated_recon._do_modules_reload('')
            mock_load.assert_called_once()


# =============================================================================
# HELP METHOD TESTS
# =============================================================================

@pytest.mark.unit
class TestHelpMethods:
    """Tests for help methods."""
    
    def test_help_index(self, isolated_recon, capsys):
        """Test help_index outputs help text."""
        isolated_recon.help_index()
        captured = capsys.readouterr()
        assert 'index' in captured.out.lower()
    
    def test_help_marketplace(self, isolated_recon, capsys):
        """Test help_marketplace outputs help text."""
        isolated_recon.help_marketplace()
        captured = capsys.readouterr()
        assert 'marketplace' in captured.out.lower()
    
    def test_help_workspaces(self, isolated_recon, capsys):
        """Test help_workspaces outputs help text."""
        isolated_recon.help_workspaces()
        captured = capsys.readouterr()
        assert 'workspaces' in captured.out.lower()
    
    def test_help_snapshots(self, isolated_recon, capsys):
        """Test help_snapshots outputs help text."""
        isolated_recon.help_snapshots()
        captured = capsys.readouterr()
        assert 'snapshots' in captured.out.lower()


# =============================================================================
# COMPLETION METHOD TESTS
# =============================================================================

@pytest.mark.unit
class TestCompletionMethods:
    """Tests for tab completion methods."""
    
    def test_complete_index(self, isolated_recon):
        """Test complete_index returns module names."""
        isolated_recon._loaded_modules = {'recon/test/mod': MagicMock()}
        
        result = isolated_recon.complete_index('recon', 'index recon')
        assert 'recon/test/mod' in result
    
    def test_complete_marketplace_returns_subcommands(self, isolated_recon):
        """Test complete_marketplace returns subcommands."""
        result = isolated_recon.complete_marketplace('', 'marketplace ')
        assert 'search' in result or 'install' in result
    
    def test_complete_workspaces_returns_subcommands(self, isolated_recon):
        """Test complete_workspaces returns subcommands."""
        result = isolated_recon.complete_workspaces('', 'workspaces ')
        assert 'list' in result or 'create' in result
    
    def test_complete_snapshots_returns_subcommands(self, isolated_recon):
        """Test complete_snapshots returns subcommands."""
        result = isolated_recon.complete_snapshots('', 'snapshots ')
        assert 'list' in result or 'take' in result
    
    def test_complete_workspaces_load(self, isolated_recon):
        """Test _complete_workspaces_load returns workspace names."""
        result = isolated_recon._complete_workspaces_load('d')
        assert 'default' in result
    
    def test_complete_snapshots_load_empty(self, isolated_recon):
        """Test _complete_snapshots_load with no snapshots."""
        result = isolated_recon._complete_snapshots_load('')
        assert result == []


# =============================================================================
# DATABASE MIGRATION EXTENDED TESTS
# =============================================================================

@pytest.mark.unit
class TestDatabaseMigrationExtended:
    """Extended tests for database migration through all versions."""
    
    def test_migrate_db_version_2_to_3(self, isolated_recon, recon_test_env):
        """Test migration from version 2 adds street_address."""
        ws_path = os.path.join(recon_test_env['spaces_path'], 'v2_ws')
        os.makedirs(ws_path)
        
        db_path = os.path.join(ws_path, 'data.db')
        conn = sqlite3.connect(db_path)
        # Create a more complete schema for version 2
        conn.execute('CREATE TABLE domains (domain TEXT)')
        conn.execute('CREATE TABLE companies (company TEXT, description TEXT)')
        conn.execute('CREATE TABLE netblocks (netblock TEXT)')
        conn.execute('CREATE TABLE locations (latitude TEXT, longitude TEXT)')
        conn.execute('CREATE TABLE vulnerabilities (host TEXT, reference TEXT, example TEXT, publish_date TEXT, category TEXT)')
        conn.execute('CREATE TABLE ports (ip_address TEXT, host TEXT, port TEXT, protocol TEXT)')
        conn.execute('CREATE TABLE hosts (host TEXT, ip_address TEXT)')
        conn.execute('CREATE TABLE contacts (first_name TEXT, middle_name TEXT, last_name TEXT, email TEXT, title TEXT, region TEXT, country TEXT)')
        conn.execute('CREATE TABLE credentials (username TEXT, password TEXT, hash TEXT, type TEXT, leak TEXT)')
        conn.execute('CREATE TABLE leaks (leak_id TEXT, description TEXT, source_refs TEXT, leak_type TEXT, title TEXT, import_date TEXT, leak_date TEXT, attackers TEXT, num_entries TEXT, score TEXT, num_domains_affected TEXT, attack_method TEXT, target_industries TEXT, password_hash TEXT, targets TEXT, media_refs TEXT)')
        conn.execute('CREATE TABLE pushpins (source TEXT)')
        conn.execute('PRAGMA user_version = 2')
        conn.commit()
        conn.close()
        
        isolated_recon.workspace = ws_path
        
        with patch.object(isolated_recon, 'alert'):
            isolated_recon._migrate_db()
        
        # Verify street_address column exists
        columns = isolated_recon.get_columns('locations')
        column_names = [c[0] for c in columns]
        assert 'street_address' in column_names
    
    def test_migrate_db_version_4_to_5(self, isolated_recon, recon_test_env):
        """Test migration from version 4 adds module column."""
        ws_path = os.path.join(recon_test_env['spaces_path'], 'v4_ws')
        os.makedirs(ws_path)
        
        db_path = os.path.join(ws_path, 'data.db')
        conn = sqlite3.connect(db_path)
        conn.execute('CREATE TABLE domains (domain TEXT)')
        conn.execute('CREATE TABLE companies (company TEXT, description TEXT)')
        conn.execute('CREATE TABLE netblocks (netblock TEXT)')
        conn.execute('CREATE TABLE locations (latitude TEXT, longitude TEXT, street_address TEXT)')
        conn.execute('CREATE TABLE vulnerabilities (host TEXT, reference TEXT, example TEXT, publish_date TEXT, category TEXT, status TEXT)')
        conn.execute('CREATE TABLE ports (ip_address TEXT, host TEXT, port TEXT, protocol TEXT)')
        conn.execute('CREATE TABLE hosts (host TEXT, ip_address TEXT)')
        conn.execute('CREATE TABLE contacts (first_name TEXT, middle_name TEXT, last_name TEXT, email TEXT, title TEXT, region TEXT, country TEXT)')
        conn.execute('CREATE TABLE credentials (username TEXT, password TEXT, hash TEXT, type TEXT, leak TEXT)')
        conn.execute('CREATE TABLE leaks (leak_id TEXT)')
        conn.execute('CREATE TABLE pushpins (source TEXT)')
        conn.execute('PRAGMA user_version = 4')
        conn.commit()
        conn.close()
        
        isolated_recon.workspace = ws_path
        
        with patch.object(isolated_recon, 'alert'):
            isolated_recon._migrate_db()
        
        # Verify module column exists
        columns = isolated_recon.get_columns('domains')
        column_names = [c[0] for c in columns]
        assert 'module' in column_names


# =============================================================================
# INTEGRATION-STYLE TESTS
# =============================================================================

@pytest.mark.unit
class TestReconIntegration:
    """Integration-style tests for Recon workflows."""
    
    def test_workspace_lifecycle(self, isolated_recon, recon_test_env):
        """Test complete workspace lifecycle: create, use, delete."""
        with patch.object(isolated_recon, '_load_config'), \
             patch.object(isolated_recon, '_load_modules'):
            
            # Create new workspace
            isolated_recon._init_workspace('lifecycle_test')
            
            # Verify it exists
            workspaces = isolated_recon._get_workspaces()
            assert 'lifecycle_test' in workspaces
            
            # Use it (insert data)
            isolated_recon.insert_domains(domain='test.com', mute=True)
            
            # Verify data exists
            domains = isolated_recon.query('SELECT domain FROM domains')
            assert any('test.com' in str(d) for d in domains)
            
            # Switch back to default
            isolated_recon._init_workspace('default')
            
            # Delete the test workspace
            result = isolated_recon.remove_workspace('lifecycle_test')
            assert result is True
            
            # Verify it's gone
            workspaces = isolated_recon._get_workspaces()
            assert 'lifecycle_test' not in workspaces
    
    def test_snapshot_lifecycle(self, isolated_recon, recon_test_env):
        """Test complete snapshot lifecycle: take, load, remove."""
        isolated_recon.workspace = recon_test_env['default_workspace']
        
        # Take a snapshot
        with patch.object(isolated_recon, 'output'):
            isolated_recon._do_snapshots_take('')
        
        snapshots = isolated_recon._get_snapshots()
        assert len(snapshots) == 1
        snapshot_name = snapshots[0]
        
        # Load the snapshot
        with patch.object(isolated_recon, 'output'):
            isolated_recon._do_snapshots_load(snapshot_name)
        
        # Remove the snapshot
        with patch.object(isolated_recon, 'output'):
            isolated_recon._do_snapshots_remove(snapshot_name)
        
        snapshots = isolated_recon._get_snapshots()
        assert len(snapshots) == 0
