"""
Extended unit tests for the recon-ng Recon class (base.py).

These tests cover additional functionality not covered by test_base.py:
- do_index command
- Marketplace commands (do_marketplace, subcommands)
- Help methods for marketplace, workspaces, snapshots
- Complete methods
- Module loading with reload logic
"""
import os
import sys
import sqlite3
import tempfile
import shutil
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock, call

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from recon.core import framework
from recon.core.framework import Framework, Options


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def recon_test_env(tmp_path):
    """Create an isolated environment for Recon testing."""
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
    
    Framework.home_path = str(home_path)
    Framework.spaces_path = str(home_path / "workspaces")
    Framework.workspace = str(default_workspace)
    
    with patch.object(Recon, '_check_version'), \
         patch.object(Recon, '_fetch_module_index'), \
         patch.object(Recon, '_load_modules'), \
         patch.object(Recon, '_send_analytics'), \
         patch.object(Recon, '_init_workspace'):
        
        temp_recon = Recon(check=False, analytics=False, marketplace=False)
        temp_recon.workspace = str(default_workspace)
        temp_recon._init_global_options()
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
        'tmp_path': tmp_path,
        'home_path': str(home_path),
        'modules_path': str(home_path / "modules"),
        'spaces_path': str(home_path / "workspaces"),
        'data_path': str(home_path / "data"),
        'default_workspace': str(default_workspace),
        'db_path': str(db_path),
        'keys_db_path': str(keys_db_path),
    }


@pytest.fixture
def isolated_recon(recon_test_env):
    """Create an isolated Recon instance with no external dependencies."""
    from recon.core.base import Recon
    from recon.core.framework import Framework
    
    original_state = {
        'home_path': Framework.home_path,
        'mod_path': Framework.mod_path,
        'data_path': Framework.data_path,
        'spaces_path': Framework.spaces_path,
        'workspace': Framework.workspace,
        '_global_options': Framework._global_options,
        '_loaded_modules': Framework._loaded_modules.copy() if hasattr(Framework, '_loaded_modules') else {},
    }
    
    with patch.object(Recon, '_check_version'), \
         patch.object(Recon, '_fetch_module_index'), \
         patch.object(Recon, '_load_modules'), \
         patch.object(Recon, '_send_analytics'), \
         patch.object(Recon, '_init_workspace'):
        
        recon = Recon(check=False, analytics=False, marketplace=False)
        
        # Configure paths
        recon.home_path = recon_test_env['home_path']
        recon.mod_path = recon_test_env['modules_path']
        recon.data_path = recon_test_env['data_path']
        recon.spaces_path = recon_test_env['spaces_path']
        recon.workspace = recon_test_env['default_workspace']
        
        Framework.home_path = recon_test_env['home_path']
        Framework.mod_path = recon_test_env['modules_path']
        Framework.data_path = recon_test_env['data_path']
        Framework.spaces_path = recon_test_env['spaces_path']
        Framework.workspace = recon_test_env['default_workspace']
        
        recon._init_global_options()
        
        # Initialize module data structures
        recon._loaded_modules = {}
        recon._loaded_category = {}
        recon._module_index = []
    
    yield recon
    
    # Restore original Framework state
    Framework.home_path = original_state['home_path']
    Framework.mod_path = original_state['mod_path']
    Framework.data_path = original_state['data_path']
    Framework.spaces_path = original_state['spaces_path']
    Framework.workspace = original_state['workspace']
    Framework._global_options = original_state['_global_options']
    Framework._loaded_modules = original_state['_loaded_modules']


# =============================================================================
# DO_INDEX COMMAND TESTS
# =============================================================================

@pytest.mark.unit
class TestDoIndexCommand:
    """Tests for the do_index command."""
    
    def test_do_index_no_params_shows_help(self, isolated_recon):
        """Test do_index with no params shows help."""
        with patch.object(isolated_recon, 'help_index') as mock_help:
            isolated_recon.do_index('')
            mock_help.assert_called_once()
    
    def test_do_index_builds_yaml_for_all_modules(self, isolated_recon):
        """Test do_index builds YAML markup for all modules."""
        # Create mock modules
        mock_module = MagicMock()
        mock_module.meta = {
            'name': 'Test Module',
            'author': 'Test Author',
            'description': 'Test Description',
            'version': '1.0',
            'dependencies': ['requests'],
            'files': [],
            'required_keys': ['api_key'],
        }
        isolated_recon._loaded_modules = {
            'recon/domains-hosts/test': mock_module,
        }
        
        with patch.object(isolated_recon, 'output') as mock_output, \
             patch('builtins.print') as mock_print:
            isolated_recon.do_index('all')
            
            mock_output.assert_any_call('Building index markup...')
            # YAML should be printed
            assert mock_print.called
    
    def test_do_index_specific_module(self, isolated_recon):
        """Test do_index with specific module path."""
        mock_module = MagicMock()
        mock_module.meta = {
            'name': 'Test Module',
            'author': 'Test Author',
            'description': 'Test Description',
            'version': '1.0',
        }
        isolated_recon._loaded_modules = {
            'recon/domains-hosts/test': mock_module,
            'recon/hosts-domains/other': mock_module,
        }
        
        with patch.object(isolated_recon, 'output'), \
             patch('builtins.print') as mock_print:
            isolated_recon.do_index('domains-hosts')
            
            assert mock_print.called
    
    def test_do_index_no_modules_found(self, isolated_recon):
        """Test do_index when no modules match."""
        isolated_recon._loaded_modules = {}
        
        with patch.object(isolated_recon, 'output') as mock_output:
            isolated_recon.do_index('nonexistent')
            
            mock_output.assert_any_call('No modules found.')
    
    def test_do_index_writes_to_file(self, isolated_recon, tmp_path):
        """Test do_index writes to file when filename provided."""
        mock_module = MagicMock()
        mock_module.meta = {
            'name': 'Test Module',
            'author': 'Test',
            'description': 'Test',
            'version': '1.0',
        }
        isolated_recon._loaded_modules = {'recon/test/module': mock_module}
        
        output_file = tmp_path / "index.yml"
        
        with patch.object(isolated_recon, 'output') as mock_output, \
             patch('builtins.print'):
            isolated_recon.do_index(f'all {output_file}')
            
            # Should write to file
            mock_output.assert_any_call('Module index created.')
        
        assert output_file.exists()


# =============================================================================
# DO_MARKETPLACE COMMAND TESTS
# =============================================================================

@pytest.mark.unit
class TestDoMarketplaceCommand:
    """Tests for the do_marketplace command."""
    
    def test_do_marketplace_disabled(self, isolated_recon):
        """Test marketplace command when disabled."""
        isolated_recon._marketplace = False
        
        with patch.object(isolated_recon, 'alert') as mock_alert:
            isolated_recon.do_marketplace('search')
            mock_alert.assert_called_with('Marketplace disabled.')
    
    def test_do_marketplace_no_params_shows_help(self, isolated_recon):
        """Test marketplace with no params shows help."""
        isolated_recon._marketplace = True
        
        with patch.object(isolated_recon, 'help_marketplace') as mock_help:
            isolated_recon.do_marketplace('')
            mock_help.assert_called_once()
    
    def test_do_marketplace_invalid_subcommand(self, isolated_recon):
        """Test marketplace with invalid subcommand."""
        isolated_recon._marketplace = True
        
        with patch.object(isolated_recon, 'help_marketplace') as mock_help:
            isolated_recon.do_marketplace('invalid')
            mock_help.assert_called()


@pytest.mark.unit
class TestMarketplaceRefresh:
    """Tests for marketplace refresh subcommand."""
    
    def test_marketplace_refresh(self, isolated_recon):
        """Test marketplace refresh fetches and updates index."""
        isolated_recon._marketplace = True
        
        with patch.object(isolated_recon, '_fetch_module_index') as mock_fetch, \
             patch.object(isolated_recon, '_update_module_index') as mock_update, \
             patch.object(isolated_recon, 'output') as mock_output:
            isolated_recon.do_marketplace('refresh')
            
            mock_fetch.assert_called_once()
            mock_update.assert_called_once()
            mock_output.assert_called_with('Marketplace index refreshed.')


@pytest.mark.unit
class TestMarketplaceSearch:
    """Tests for marketplace search subcommand."""
    
    def test_marketplace_search_no_params(self, isolated_recon):
        """Test marketplace search lists all modules."""
        isolated_recon._marketplace = True
        isolated_recon._module_index = [
            {
                'path': 'recon/domains-hosts/test',
                'version': '1.0',
                'status': 'not installed',
                'last_updated': '2024-01-01',
                'dependencies': [],
                'required_keys': [],
            }
        ]
        
        with patch.object(isolated_recon, 'table') as mock_table, \
             patch('builtins.print'):
            isolated_recon.do_marketplace('search')
            mock_table.assert_called_once()
    
    def test_marketplace_search_with_filter(self, isolated_recon):
        """Test marketplace search with regex filter."""
        isolated_recon._marketplace = True
        isolated_recon._module_index = [
            {'path': 'recon/domains-hosts/test', 'version': '1.0', 'status': 'installed',
             'last_updated': '2024-01-01', 'dependencies': ['dep1'], 'required_keys': ['key1']},
            {'path': 'recon/hosts-domains/other', 'version': '1.0', 'status': 'not installed',
             'last_updated': '2024-01-01', 'dependencies': [], 'required_keys': []},
        ]
        
        with patch.object(isolated_recon, '_search_module_index', return_value=[isolated_recon._module_index[0]]) as mock_search, \
             patch.object(isolated_recon, 'output'), \
             patch.object(isolated_recon, 'table') as mock_table, \
             patch('builtins.print'):
            isolated_recon.do_marketplace('search domains')
            
            mock_search.assert_called_with('domains')
            mock_table.assert_called_once()
    
    def test_marketplace_search_no_results(self, isolated_recon):
        """Test marketplace search with no results."""
        isolated_recon._marketplace = True
        isolated_recon._module_index = []
        
        with patch.object(isolated_recon, 'error') as mock_error, \
             patch.object(isolated_recon, '_help_marketplace_search') as mock_help:
            isolated_recon.do_marketplace('search nonexistent')
            
            mock_error.assert_called_with('No modules found.')
            mock_help.assert_called()


@pytest.mark.unit
class TestMarketplaceInfo:
    """Tests for marketplace info subcommand."""
    
    def test_marketplace_info_no_params(self, isolated_recon):
        """Test marketplace info without params shows help."""
        isolated_recon._marketplace = True
        
        with patch.object(isolated_recon, '_help_marketplace_info') as mock_help:
            isolated_recon.do_marketplace('info')
            mock_help.assert_called_once()
    
    def test_marketplace_info_displays_module(self, isolated_recon):
        """Test marketplace info displays module details."""
        isolated_recon._marketplace = True
        isolated_recon._module_index = [
            {
                'path': 'recon/domains-hosts/test',
                'name': 'Test Module',
                'author': 'Test Author',
                'version': '1.0',
                'last_updated': '2024-01-01',
                'description': 'A test module',
                'required_keys': ['api_key'],
                'dependencies': ['requests'],
                'files': [],
                'status': 'not installed',
            }
        ]
        
        with patch.object(isolated_recon, 'table') as mock_table:
            isolated_recon.do_marketplace('info recon/domains-hosts/test')
            mock_table.assert_called_once()
    
    def test_marketplace_info_invalid_path(self, isolated_recon):
        """Test marketplace info with invalid path."""
        isolated_recon._marketplace = True
        isolated_recon._module_index = []
        
        with patch.object(isolated_recon, 'error') as mock_error:
            isolated_recon.do_marketplace('info nonexistent')
            mock_error.assert_called_with('Invalid module path.')


@pytest.mark.unit
class TestMarketplaceInstall:
    """Tests for marketplace install subcommand."""
    
    def test_marketplace_install_no_params(self, isolated_recon):
        """Test marketplace install without params shows help."""
        isolated_recon._marketplace = True
        
        with patch.object(isolated_recon, '_help_marketplace_install') as mock_help:
            isolated_recon.do_marketplace('install')
            mock_help.assert_called_once()
    
    def test_marketplace_install_module(self, isolated_recon):
        """Test marketplace install installs a module."""
        isolated_recon._marketplace = True
        isolated_recon._module_index = [
            {'path': 'recon/domains-hosts/test', 'status': 'not installed'}
        ]
        
        with patch.object(isolated_recon, '_install_module') as mock_install, \
             patch.object(isolated_recon, '_do_modules_reload') as mock_reload:
            isolated_recon.do_marketplace('install recon/domains-hosts/test')
            
            mock_install.assert_called_with('recon/domains-hosts/test')
            mock_reload.assert_called_once()
    
    def test_marketplace_install_invalid_path(self, isolated_recon):
        """Test marketplace install with invalid path."""
        isolated_recon._marketplace = True
        isolated_recon._module_index = []
        
        with patch.object(isolated_recon, 'error') as mock_error:
            isolated_recon.do_marketplace('install nonexistent')
            mock_error.assert_called_with('Invalid module path.')


@pytest.mark.unit
class TestMarketplaceRemove:
    """Tests for marketplace remove subcommand."""
    
    def test_marketplace_remove_no_params(self, isolated_recon):
        """Test marketplace remove without params shows help."""
        isolated_recon._marketplace = True
        
        with patch.object(isolated_recon, '_help_marketplace_remove') as mock_help:
            isolated_recon.do_marketplace('remove')
            mock_help.assert_called_once()
    
    def test_marketplace_remove_module(self, isolated_recon):
        """Test marketplace remove removes a module."""
        isolated_recon._marketplace = True
        isolated_recon._module_index = [
            {'path': 'recon/domains-hosts/test', 'status': 'installed'}
        ]
        
        with patch.object(isolated_recon, '_remove_module') as mock_remove, \
             patch.object(isolated_recon, '_do_modules_reload') as mock_reload:
            isolated_recon.do_marketplace('remove recon/domains-hosts/test')
            
            mock_remove.assert_called_with('recon/domains-hosts/test')
            mock_reload.assert_called_once()
    
    def test_marketplace_remove_invalid_path(self, isolated_recon):
        """Test marketplace remove with invalid path."""
        isolated_recon._marketplace = True
        isolated_recon._module_index = []
        
        with patch.object(isolated_recon, 'error') as mock_error:
            isolated_recon.do_marketplace('remove nonexistent')
            mock_error.assert_called_with('Invalid module path.')
    
    def test_marketplace_remove_disabled_module(self, isolated_recon):
        """Test marketplace remove can remove disabled module."""
        isolated_recon._marketplace = True
        isolated_recon._module_index = [
            {'path': 'recon/domains-hosts/disabled', 'status': 'disabled'}
        ]
        
        with patch.object(isolated_recon, '_remove_module') as mock_remove, \
             patch.object(isolated_recon, '_do_modules_reload'):
            isolated_recon.do_marketplace('remove recon/domains-hosts/disabled')
            
            mock_remove.assert_called_once()


# =============================================================================
# HELP METHODS TESTS
# =============================================================================

@pytest.mark.unit
class TestHelpMethods:
    """Tests for help methods."""
    
    def test_help_index(self, isolated_recon):
        """Test help_index prints help."""
        with patch('builtins.print') as mock_print:
            isolated_recon.help_index()
            assert mock_print.called
    
    def test_help_marketplace(self, isolated_recon):
        """Test help_marketplace prints help."""
        with patch('builtins.print') as mock_print:
            isolated_recon.help_marketplace()
            assert mock_print.called
    
    def test_help_marketplace_search(self, isolated_recon):
        """Test _help_marketplace_search prints help."""
        with patch('builtins.print') as mock_print:
            isolated_recon._help_marketplace_search()
            assert mock_print.called
    
    def test_help_marketplace_info(self, isolated_recon):
        """Test _help_marketplace_info prints help."""
        with patch('builtins.print') as mock_print:
            isolated_recon._help_marketplace_info()
            assert mock_print.called
    
    def test_help_marketplace_install(self, isolated_recon):
        """Test _help_marketplace_install prints help."""
        with patch('builtins.print') as mock_print:
            isolated_recon._help_marketplace_install()
            assert mock_print.called
    
    def test_help_marketplace_remove(self, isolated_recon):
        """Test _help_marketplace_remove prints help."""
        with patch('builtins.print') as mock_print:
            isolated_recon._help_marketplace_remove()
            assert mock_print.called
    
    def test_help_workspaces_create(self, isolated_recon):
        """Test _help_workspaces_create prints help."""
        with patch('builtins.print') as mock_print:
            isolated_recon._help_workspaces_create()
            assert mock_print.called
    
    def test_help_workspaces_load(self, isolated_recon):
        """Test _help_workspaces_load prints help."""
        with patch('builtins.print') as mock_print:
            isolated_recon._help_workspaces_load()
            assert mock_print.called
    
    def test_help_workspaces_remove(self, isolated_recon):
        """Test _help_workspaces_remove prints help."""
        with patch('builtins.print') as mock_print:
            isolated_recon._help_workspaces_remove()
            assert mock_print.called
    
    def test_help_snapshots_load(self, isolated_recon):
        """Test _help_snapshots_load prints help."""
        with patch('builtins.print') as mock_print:
            isolated_recon._help_snapshots_load()
            assert mock_print.called
    
    def test_help_snapshots_remove(self, isolated_recon):
        """Test _help_snapshots_remove prints help."""
        with patch('builtins.print') as mock_print:
            isolated_recon._help_snapshots_remove()
            assert mock_print.called


# =============================================================================
# COMPLETE METHODS TESTS
# =============================================================================

@pytest.mark.unit
class TestCompleteMethodsExtended:
    """Extended tests for tab completion methods."""
    
    def test_complete_index_returns_modules(self, isolated_recon):
        """Test complete_index returns loaded modules."""
        isolated_recon._loaded_modules = {
            'recon/domains-hosts/test': MagicMock(),
            'recon/hosts-domains/other': MagicMock(),
        }
        
        result = isolated_recon.complete_index('recon', 'index recon', 0, 0)
        assert 'recon/domains-hosts/test' in result
        assert 'recon/hosts-domains/other' in result
    
    def test_complete_index_filters_by_prefix(self, isolated_recon):
        """Test complete_index filters by prefix."""
        isolated_recon._loaded_modules = {
            'recon/domains-hosts/test': MagicMock(),
            'recon/hosts-domains/other': MagicMock(),
        }
        
        result = isolated_recon.complete_index('recon/domains', 'index recon/domains', 0, 0)
        assert 'recon/domains-hosts/test' in result
        assert 'recon/hosts-domains/other' not in result
    
    def test_complete_index_third_arg_returns_empty(self, isolated_recon):
        """Test complete_index returns empty for third arg."""
        isolated_recon._loaded_modules = {'test': MagicMock()}
        
        result = isolated_recon.complete_index('', 'index all output.yml', 0, 0)
        assert result == []
    
    def test_complete_marketplace_returns_subcommands(self, isolated_recon):
        """Test complete_marketplace returns subcommands."""
        result = isolated_recon.complete_marketplace('', 'marketplace ', 0, 0)
        assert 'refresh' in result
        assert 'search' in result
        assert 'info' in result
        assert 'install' in result
        assert 'remove' in result
    
    def test_complete_marketplace_refresh(self, isolated_recon):
        """Test _complete_marketplace_refresh returns empty."""
        result = isolated_recon._complete_marketplace_refresh('', '')
        assert result == []
    
    def test_complete_marketplace_info_returns_paths(self, isolated_recon):
        """Test _complete_marketplace_info returns module paths."""
        isolated_recon._module_index = [
            {'path': 'recon/domains-hosts/test'},
            {'path': 'recon/hosts-domains/other'},
        ]
        
        result = isolated_recon._complete_marketplace_info('recon', '')
        assert 'recon/domains-hosts/test' in result
        assert 'recon/hosts-domains/other' in result
    
    def test_complete_marketplace_remove_returns_installed(self, isolated_recon):
        """Test _complete_marketplace_remove returns only installed modules."""
        isolated_recon._module_index = [
            {'path': 'recon/domains-hosts/test', 'status': 'installed'},
            {'path': 'recon/hosts-domains/other', 'status': 'not installed'},
        ]
        
        result = isolated_recon._complete_marketplace_remove('', '')
        assert 'recon/domains-hosts/test' in result
        assert 'recon/hosts-domains/other' not in result
    
    def test_complete_workspaces_returns_subcommands(self, isolated_recon):
        """Test complete_workspaces returns subcommands."""
        result = isolated_recon.complete_workspaces('', 'workspaces ', 0, 0)
        assert 'list' in result
        assert 'create' in result
        assert 'load' in result
        assert 'remove' in result
    
    def test_complete_workspaces_list_returns_empty(self, isolated_recon):
        """Test _complete_workspaces_list returns empty."""
        result = isolated_recon._complete_workspaces_list('', '')
        assert result == []
    
    def test_complete_workspaces_load_with_subcommand(self, isolated_recon, recon_test_env):
        """Test complete_workspaces for load subcommand."""
        # Create a test workspace
        test_ws = os.path.join(recon_test_env['spaces_path'], 'testws')
        os.makedirs(test_ws)
        
        result = isolated_recon.complete_workspaces('', 'workspaces load ', 0, 0)
        assert 'testws' in result
    
    def test_complete_snapshots_returns_subcommands(self, isolated_recon):
        """Test complete_snapshots returns subcommands."""
        result = isolated_recon.complete_snapshots('', 'snapshots ', 0, 0)
        assert 'list' in result
        assert 'take' in result
        assert 'load' in result
        assert 'remove' in result
    
    def test_complete_snapshots_list_returns_empty(self, isolated_recon):
        """Test _complete_snapshots_list returns empty."""
        result = isolated_recon._complete_snapshots_list('', '')
        assert result == []
    
    def test_complete_snapshots_load_returns_snapshots(self, isolated_recon, recon_test_env):
        """Test _complete_snapshots_load returns snapshot names."""
        isolated_recon.workspace = recon_test_env['default_workspace']
        
        # Take a snapshot first
        with patch.object(isolated_recon, 'output'):
            isolated_recon._do_snapshots_take('')
        
        snapshots = isolated_recon._get_snapshots()
        result = isolated_recon._complete_snapshots_load('', '')
        
        assert len(result) >= 1
        assert result[0] in snapshots
    
    def test_complete_modules_reload_returns_empty(self, isolated_recon):
        """Test _complete_modules_reload returns empty."""
        result = isolated_recon._complete_modules_reload('', '')
        assert result == []


# =============================================================================
# WORKSPACES EDGE CASES
# =============================================================================

@pytest.mark.unit
class TestWorkspacesEdgeCases:
    """Edge case tests for workspace commands."""
    
    def test_do_workspaces_invalid_subcommand(self, isolated_recon):
        """Test workspaces with invalid subcommand shows help."""
        with patch.object(isolated_recon, 'help_workspaces') as mock_help:
            isolated_recon.do_workspaces('invalid_subcommand')
            mock_help.assert_called()
    
    def test_workspaces_create_no_params(self, isolated_recon):
        """Test workspaces create without name shows help."""
        with patch.object(isolated_recon, '_help_workspaces_create') as mock_help:
            isolated_recon._do_workspaces_create('')
            mock_help.assert_called_once()
    
    def test_workspaces_create_failure(self, isolated_recon):
        """Test workspaces create handles init failure."""
        with patch.object(isolated_recon, '_init_workspace', return_value=False), \
             patch.object(isolated_recon, 'output') as mock_output:
            isolated_recon._do_workspaces_create('failing_ws')
            mock_output.assert_called_with("Unable to create 'failing_ws' workspace.")
    
    def test_workspaces_load_no_params(self, isolated_recon):
        """Test workspaces load without name shows help."""
        with patch.object(isolated_recon, '_help_workspaces_load') as mock_help:
            isolated_recon._do_workspaces_load('')
            mock_help.assert_called_once()
    
    def test_workspaces_load_invalid_name(self, isolated_recon):
        """Test workspaces load with invalid name."""
        with patch.object(isolated_recon, '_get_workspaces', return_value=['default']), \
             patch.object(isolated_recon, 'output') as mock_output:
            isolated_recon._do_workspaces_load('nonexistent')
            mock_output.assert_called_with('Invalid workspace name.')
    
    def test_workspaces_load_init_failure(self, isolated_recon):
        """Test workspaces load handles init failure."""
        with patch.object(isolated_recon, '_get_workspaces', return_value=['test_ws']), \
             patch.object(isolated_recon, '_init_workspace', return_value=False), \
             patch.object(isolated_recon, 'output') as mock_output:
            isolated_recon._do_workspaces_load('test_ws')
            mock_output.assert_called_with("Unable to initialize 'test_ws' workspace.")
    
    def test_workspaces_remove_no_params(self, isolated_recon):
        """Test workspaces remove without name shows help."""
        with patch.object(isolated_recon, '_help_workspaces_remove') as mock_help:
            isolated_recon._do_workspaces_remove('')
            mock_help.assert_called_once()
    
    def test_workspaces_remove_failure(self, isolated_recon):
        """Test workspaces remove handles removal failure."""
        with patch.object(isolated_recon, 'remove_workspace', return_value=False), \
             patch.object(isolated_recon, 'output') as mock_output:
            isolated_recon._do_workspaces_remove('some_ws')
            mock_output.assert_called_with("Unable to remove 'some_ws' workspace.")


# =============================================================================
# SNAPSHOTS EDGE CASES
# =============================================================================

@pytest.mark.unit
class TestSnapshotsEdgeCases:
    """Edge case tests for snapshot commands."""
    
    def test_do_snapshots_invalid_subcommand(self, isolated_recon):
        """Test snapshots with invalid subcommand shows help."""
        with patch.object(isolated_recon, 'help_snapshots') as mock_help:
            isolated_recon.do_snapshots('invalid_subcommand')
            mock_help.assert_called()


# =============================================================================
# INSTALL/REMOVE MODULE TESTS
# =============================================================================

@pytest.mark.unit
class TestInstallRemoveModule:
    """Tests for module installation and removal."""
    
    def test_install_module_success(self, isolated_recon, recon_test_env):
        """Test successful module installation."""
        isolated_recon._module_index = [
            {
                'path': 'recon/domains-hosts/test',
                'files': [],
            }
        ]
        
        mock_response = MagicMock()
        mock_response.text = '# module code'
        
        with patch.object(isolated_recon, '_get_module_from_index', return_value={'files': []}), \
             patch.object(isolated_recon, '_request_file_from_repo', return_value=mock_response), \
             patch.object(isolated_recon, '_write_local_file') as mock_write, \
             patch.object(isolated_recon, 'output') as mock_output:
            isolated_recon._install_module('recon/domains-hosts/test')
            
            mock_write.assert_called_once()
            mock_output.assert_called_with('Module installed: recon/domains-hosts/test')
    
    def test_install_module_with_files(self, isolated_recon, recon_test_env):
        """Test module installation with supporting files."""
        mock_response = MagicMock()
        mock_response.text = '# content'
        
        with patch.object(isolated_recon, '_get_module_from_index', return_value={'files': ['data.txt']}), \
             patch.object(isolated_recon, '_request_file_from_repo', return_value=mock_response), \
             patch.object(isolated_recon, '_write_local_file') as mock_write, \
             patch.object(isolated_recon, 'output'):
            isolated_recon._install_module('recon/test/module')
            
            # Should write both the data file and module file
            assert mock_write.call_count == 2
    
    def test_install_module_file_download_failure(self, isolated_recon):
        """Test module installation handles file download failure."""
        with patch.object(isolated_recon, '_get_module_from_index', return_value={'files': ['data.txt']}), \
             patch.object(isolated_recon, '_request_file_from_repo', side_effect=Exception('Download failed')), \
             patch.object(isolated_recon, 'error') as mock_error:
            
            with pytest.raises(Exception):
                isolated_recon._install_module('recon/test/module')
            
            mock_error.assert_any_call('Module installation aborted.')
    
    def test_remove_module_success(self, isolated_recon, recon_test_env):
        """Test successful module removal."""
        # Create a fake module file
        mod_dir = os.path.join(recon_test_env['modules_path'], 'recon', 'test')
        os.makedirs(mod_dir)
        mod_file = os.path.join(mod_dir, 'module.py')
        with open(mod_file, 'w') as f:
            f.write('# module')
        
        with patch.object(isolated_recon, '_get_module_from_index', return_value={'files': []}), \
             patch.object(isolated_recon, 'output') as mock_output:
            isolated_recon._remove_module('recon/test/module')
            
            mock_output.assert_called_with('Module removed: recon/test/module')
            assert not os.path.exists(mod_file)
    
    def test_remove_module_with_files(self, isolated_recon, recon_test_env):
        """Test module removal with data files."""
        # Create module file
        mod_dir = os.path.join(recon_test_env['modules_path'], 'recon', 'test')
        os.makedirs(mod_dir)
        mod_file = os.path.join(mod_dir, 'module.py')
        with open(mod_file, 'w') as f:
            f.write('# module')
        
        # Create data file
        data_file = os.path.join(recon_test_env['data_path'], 'test_data.txt')
        with open(data_file, 'w') as f:
            f.write('data')
        
        with patch.object(isolated_recon, '_get_module_from_index', return_value={'files': ['test_data.txt']}), \
             patch.object(isolated_recon, 'output'):
            isolated_recon._remove_module('recon/test/module')
            
            assert not os.path.exists(mod_file)
            assert not os.path.exists(data_file)


# =============================================================================
# MODULES LOAD TESTS
# =============================================================================

@pytest.mark.unit
class TestModulesLoad:
    """Tests for module loading functionality."""
    
    def test_modules_load_no_params(self, isolated_recon):
        """Test modules load without params shows help."""
        isolated_recon._global_options = Options()
        
        with patch.object(isolated_recon, '_help_modules_load') as mock_help:
            isolated_recon._do_modules_load('')
            mock_help.assert_called_once()
    
    def test_modules_load_invalid_module(self, isolated_recon):
        """Test modules load with invalid module name."""
        isolated_recon._global_options = Options()
        isolated_recon._loaded_modules = {}
        
        with patch.object(isolated_recon, '_match_modules', return_value=[]), \
             patch.object(isolated_recon, 'error') as mock_error:
            isolated_recon._do_modules_load('nonexistent')
            mock_error.assert_called_with('Invalid module name.')
    
    def test_modules_load_multiple_matches(self, isolated_recon):
        """Test modules load with multiple matching modules."""
        isolated_recon._global_options = Options()
        
        with patch.object(isolated_recon, '_match_modules', return_value=['mod1', 'mod2']), \
             patch.object(isolated_recon, 'output') as mock_output, \
             patch.object(isolated_recon, '_list_modules'):
            isolated_recon._do_modules_load('mod')
            mock_output.assert_called_with("Multiple modules match 'mod'.")
    
    def test_modules_load_validation_error(self, isolated_recon):
        """Test modules load handles validation error."""
        isolated_recon._global_options = Options()
        
        with patch.object(isolated_recon, '_validate_options', side_effect=framework.FrameworkException('Validation failed')), \
             patch.object(isolated_recon, 'error') as mock_error:
            isolated_recon._do_modules_load('test')
            mock_error.assert_called()
    
    def test_modules_reload(self, isolated_recon):
        """Test modules reload command."""
        with patch.object(isolated_recon, 'output') as mock_output, \
             patch.object(isolated_recon, '_load_modules') as mock_load:
            isolated_recon._do_modules_reload('')
            
            mock_output.assert_called_with('Reloading modules...')
            mock_load.assert_called_once()


# =============================================================================
# LOAD MODULES INTERNAL
# =============================================================================

@pytest.mark.unit
class TestLoadModulesInternal:
    """Tests for internal module loading."""
    
    def test_load_modules_crawls_directory(self, isolated_recon, recon_test_env):
        """Test _load_modules crawls module directory."""
        with patch.object(isolated_recon, '_load_module') as mock_load, \
             patch.object(isolated_recon, '_remove_empty_dirs'), \
             patch.object(isolated_recon, '_update_module_index'):
            isolated_recon._load_modules()
            # Should initialize the module structures
            assert isolated_recon._loaded_category == {}
    
    def test_load_module_import_error(self, isolated_recon, recon_test_env):
        """Test _load_module handles import error."""
        # Create a module with missing dependency
        mod_dir = os.path.join(recon_test_env['modules_path'], 'recon', 'test')
        os.makedirs(mod_dir)
        mod_file = os.path.join(mod_dir, 'badmodule.py')
        with open(mod_file, 'w') as f:
            f.write('import nonexistent_module_xyz\nclass Module: pass')
        
        with patch.object(isolated_recon, 'error') as mock_error:
            result = isolated_recon._load_module(mod_dir, 'badmodule.py')
            
            # Should return None/False on failure
            assert result is None
            # Should log the error
            mock_error.assert_called()


# =============================================================================
# COMPLETE MARKETPLACE WITH SUBCOMMAND
# =============================================================================

@pytest.mark.unit
class TestCompleteMarketplaceWithSubcommand:
    """Test complete_marketplace when subcommand is already entered."""
    
    def test_complete_marketplace_with_search_subcommand(self, isolated_recon):
        """Test complete_marketplace with search subcommand."""
        result = isolated_recon.complete_marketplace('', 'marketplace search ', 0, 0)
        # search returns empty list
        assert result == []
    
    def test_complete_marketplace_with_info_subcommand(self, isolated_recon):
        """Test complete_marketplace with info subcommand."""
        isolated_recon._module_index = [
            {'path': 'recon/test/module'},
        ]
        result = isolated_recon.complete_marketplace('recon', 'marketplace info recon', 0, 0)
        assert 'recon/test/module' in result
    
    def test_complete_marketplace_with_install_subcommand(self, isolated_recon):
        """Test complete_marketplace with install subcommand."""
        isolated_recon._module_index = [
            {'path': 'recon/test/module'},
        ]
        result = isolated_recon.complete_marketplace('', 'marketplace install ', 0, 0)
        assert 'recon/test/module' in result
    
    def test_complete_marketplace_with_remove_subcommand(self, isolated_recon):
        """Test complete_marketplace with remove subcommand."""
        isolated_recon._module_index = [
            {'path': 'recon/test/installed', 'status': 'installed'},
            {'path': 'recon/test/not_installed', 'status': 'not installed'},
        ]
        result = isolated_recon.complete_marketplace('', 'marketplace remove ', 0, 0)
        assert 'recon/test/installed' in result
        assert 'recon/test/not_installed' not in result
