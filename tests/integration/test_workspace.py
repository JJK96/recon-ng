"""
Integration tests for workspace management.

Tests workspace operations:
- Workspace creation
- Workspace switching
- Workspace deletion
- Snapshot management
- Configuration loading/saving
"""
import pytest
import os
import shutil
from unittest.mock import patch, MagicMock

from recon.core.framework import Framework


@pytest.mark.integration
class TestWorkspaceCreation:
    """Tests for workspace creation."""
    
    def test_workspace_directory_created(self, mock_recon, temp_home_path):
        """Test workspace directory is created."""
        workspace_path = temp_home_path / "workspaces" / "new_workspace"
        
        # Ensure it doesn't exist
        if workspace_path.exists():
            shutil.rmtree(workspace_path)
        
        # Create workspace
        with patch.object(mock_recon, '_load_config'), \
             patch.object(mock_recon, '_load_modules'):
            mock_recon._init_workspace('new_workspace')
        
        assert workspace_path.exists()
        assert workspace_path.is_dir()
    
    def test_workspace_database_created(self, mock_recon, temp_home_path):
        """Test workspace database is created."""
        workspace_path = temp_home_path / "workspaces" / "db_test_workspace"
        
        with patch.object(mock_recon, '_load_config'), \
             patch.object(mock_recon, '_load_modules'):
            mock_recon._init_workspace('db_test_workspace')
        
        db_path = workspace_path / "data.db"
        assert db_path.exists()
    
    def test_workspace_has_all_tables(self, mock_recon, temp_home_path):
        """Test workspace database has all required tables."""
        with patch.object(mock_recon, '_load_config'), \
             patch.object(mock_recon, '_load_modules'):
            mock_recon._init_workspace('tables_test')
        
        tables = mock_recon.get_tables()
        
        expected_tables = [
            'domains', 'companies', 'tenants', 'netblocks',
            'locations', 'vulnerabilities', 'ports', 'hosts',
            'contacts', 'credentials', 'leaks', 'pushpins',
            'profiles', 'repositories'
        ]
        
        for table in expected_tables:
            assert table in tables, f"Missing table: {table}"
    
    def test_workspace_prompt_updated(self, mock_recon, temp_home_path):
        """Test workspace path is updated with workspace name."""
        with patch.object(mock_recon, '_load_config'), \
             patch.object(mock_recon, '_load_modules'):
            mock_recon._init_workspace('prompt_test')
        
        # Verify the workspace path contains the workspace name
        # (prompt is a CLI attribute, workspace is the core attribute)
        assert 'prompt_test' in mock_recon.workspace


@pytest.mark.integration
class TestWorkspaceSwitch:
    """Tests for workspace switching."""
    
    def test_switch_to_existing_workspace(self, mock_recon, temp_home_path):
        """Test switching to an existing workspace."""
        # Create first workspace
        with patch.object(mock_recon, '_load_config'), \
             patch.object(mock_recon, '_load_modules'):
            mock_recon._init_workspace('workspace_a')
        
        # Add data to first workspace
        mock_recon.insert_domains(domain='workspace-a.com', mute=True)
        
        # Create second workspace
        with patch.object(mock_recon, '_load_config'), \
             patch.object(mock_recon, '_load_modules'):
            mock_recon._init_workspace('workspace_b')
        
        # Second workspace should be empty
        result = mock_recon.query('SELECT COUNT(*) FROM domains')
        assert result[0][0] == 0
        
        # Switch back to first workspace
        with patch.object(mock_recon, '_load_config'), \
             patch.object(mock_recon, '_load_modules'):
            mock_recon._init_workspace('workspace_a')
        
        # First workspace should have data
        result = mock_recon.query('SELECT COUNT(*) FROM domains')
        assert result[0][0] == 1
    
    def test_switch_to_nonexistent_workspace_creates_it(self, mock_recon, temp_home_path):
        """Test switching to non-existent workspace creates it."""
        workspace_path = temp_home_path / "workspaces" / "auto_created"
        
        assert not workspace_path.exists()
        
        with patch.object(mock_recon, '_load_config'), \
             patch.object(mock_recon, '_load_modules'):
            mock_recon._init_workspace('auto_created')
        
        assert workspace_path.exists()


@pytest.mark.integration
class TestWorkspaceRemoval:
    """Tests for workspace removal."""
    
    def test_remove_workspace(self, mock_recon, temp_home_path):
        """Test removing a workspace."""
        # Create workspace
        workspace_path = temp_home_path / "workspaces" / "to_remove"
        
        with patch.object(mock_recon, '_load_config'), \
             patch.object(mock_recon, '_load_modules'):
            mock_recon._init_workspace('to_remove')
        
        assert workspace_path.exists()
        
        # Remove it
        result = mock_recon.remove_workspace('to_remove')
        
        assert result is True
        assert not workspace_path.exists()
    
    def test_remove_nonexistent_workspace(self, mock_recon):
        """Test removing non-existent workspace returns False."""
        result = mock_recon.remove_workspace('does_not_exist')
        assert result is False
    
    def test_remove_current_workspace_switches_to_default(self, mock_recon, temp_home_path):
        """Test removing current workspace switches to default."""
        # Create and switch to test workspace
        with patch.object(mock_recon, '_load_config'), \
             patch.object(mock_recon, '_load_modules'):
            mock_recon._init_workspace('current_ws')
        
        # Create default workspace if needed
        with patch.object(mock_recon, '_load_config'), \
             patch.object(mock_recon, '_load_modules'):
            # Switch back and remove
            mock_recon._init_workspace('current_ws')
            mock_recon.remove_workspace('current_ws')
        
        # Should be on default workspace now
        assert 'default' in mock_recon.workspace


@pytest.mark.integration
class TestWorkspaceListing:
    """Tests for workspace listing."""
    
    def test_get_workspaces(self, mock_recon, temp_home_path):
        """Test getting list of workspaces."""
        # Create some workspaces
        for ws_name in ['ws_list_a', 'ws_list_b', 'ws_list_c']:
            ws_path = temp_home_path / "workspaces" / ws_name
            ws_path.mkdir(parents=True, exist_ok=True)
        
        workspaces = mock_recon._get_workspaces()
        
        assert 'ws_list_a' in workspaces
        assert 'ws_list_b' in workspaces
        assert 'ws_list_c' in workspaces
    
    def test_get_workspaces_excludes_files(self, mock_recon, temp_home_path):
        """Test workspace listing excludes files."""
        # Create a file in workspaces directory
        file_path = temp_home_path / "workspaces" / "not_a_workspace.txt"
        file_path.write_text("test")
        
        workspaces = mock_recon._get_workspaces()
        
        assert 'not_a_workspace.txt' not in workspaces


@pytest.mark.integration
class TestDatabaseMigration:
    """Tests for database migration."""
    
    def test_migrate_db_preserves_data(self, mock_recon, temp_home_path):
        """Test database migration preserves existing data."""
        # Create workspace
        with patch.object(mock_recon, '_load_config'), \
             patch.object(mock_recon, '_load_modules'):
            mock_recon._init_workspace('migrate_test')
        
        # Add data
        mock_recon.insert_domains(domain='migrate.example.com', mute=True)
        
        # Run migration (should be no-op for current version)
        mock_recon._migrate_db()
        
        # Data should still exist
        result = mock_recon.query(
            "SELECT domain FROM domains WHERE domain = 'migrate.example.com'"
        )
        assert len(result) == 1
    
    def test_db_version_check(self, mock_recon, temp_home_path):
        """Test database version is set correctly."""
        with patch.object(mock_recon, '_load_config'), \
             patch.object(mock_recon, '_load_modules'):
            mock_recon._init_workspace('version_test')
        
        result = mock_recon.query('PRAGMA user_version')
        version = result[0][0]
        
        # Should be latest version (13 as of current codebase)
        assert version >= 13


@pytest.mark.integration
class TestWorkspaceSnapshot:
    """Tests for workspace snapshots."""
    
    def test_get_snapshots_empty(self, mock_recon, temp_workspace):
        """Test getting snapshots when none exist."""
        workspace_path, _ = temp_workspace
        mock_recon.workspace = str(workspace_path)
        
        snapshots = mock_recon._get_snapshots()
        assert snapshots == []
    
    def test_get_snapshots_finds_snapshots(self, mock_recon, temp_workspace):
        """Test getting snapshots finds them."""
        workspace_path, _ = temp_workspace
        mock_recon.workspace = str(workspace_path)
        
        # Create fake snapshot files
        snapshot_names = [
            'snapshot_20240115120000.db',
            'snapshot_20240116130000.db',
        ]
        for name in snapshot_names:
            (workspace_path / name).write_text('')
        
        snapshots = mock_recon._get_snapshots()
        
        assert len(snapshots) == 2
        for name in snapshot_names:
            assert name in snapshots
    
    def test_get_snapshots_ignores_other_files(self, mock_recon, temp_workspace):
        """Test getting snapshots ignores non-snapshot files."""
        workspace_path, _ = temp_workspace
        mock_recon.workspace = str(workspace_path)
        
        # Create snapshot and non-snapshot files
        (workspace_path / 'snapshot_20240115120000.db').write_text('')
        (workspace_path / 'not_a_snapshot.db').write_text('')
        (workspace_path / 'snapshot_invalid.db').write_text('')
        
        snapshots = mock_recon._get_snapshots()
        
        assert len(snapshots) == 1
        assert 'snapshot_20240115120000.db' in snapshots


@pytest.mark.integration
class TestHomeDirectoryInit:
    """Tests for home directory initialization."""
    
    def test_home_directory_structure(self, mock_recon, temp_home_path):
        """Test home directory has correct structure."""
        assert (temp_home_path / "modules").exists()
        assert (temp_home_path / "workspaces").exists()
        assert (temp_home_path / "data").exists()
    
    def test_keys_database_created(self, mock_recon, temp_home_path):
        """Test keys database is created."""
        keys_db = temp_home_path / "keys.db"
        assert keys_db.exists()


@pytest.mark.integration
class TestWorkspaceIsolation:
    """Tests for workspace data isolation."""
    
    def test_data_isolated_between_workspaces(self, mock_recon, temp_home_path):
        """Test data is isolated between workspaces."""
        # Create and populate workspace A
        with patch.object(mock_recon, '_load_config'), \
             patch.object(mock_recon, '_load_modules'):
            mock_recon._init_workspace('isolated_a')
        
        mock_recon.insert_domains(domain='isolated-a.com', mute=True)
        mock_recon.insert_hosts(host='www.isolated-a.com', ip_address='192.0.2.1', mute=True)
        
        # Create workspace B
        with patch.object(mock_recon, '_load_config'), \
             patch.object(mock_recon, '_load_modules'):
            mock_recon._init_workspace('isolated_b')
        
        # Workspace B should not have workspace A's data
        domains = mock_recon.query('SELECT COUNT(*) FROM domains')
        hosts = mock_recon.query('SELECT COUNT(*) FROM hosts')
        
        assert domains[0][0] == 0
        assert hosts[0][0] == 0
        
        # Add different data to workspace B
        mock_recon.insert_domains(domain='isolated-b.com', mute=True)
        
        # Switch back to workspace A
        with patch.object(mock_recon, '_load_config'), \
             patch.object(mock_recon, '_load_modules'):
            mock_recon._init_workspace('isolated_a')
        
        # Workspace A should have its original data
        result = mock_recon.query(
            "SELECT domain FROM domains WHERE domain = 'isolated-a.com'"
        )
        assert len(result) == 1
        
        # And not have workspace B's data
        result = mock_recon.query(
            "SELECT domain FROM domains WHERE domain = 'isolated-b.com'"
        )
        assert len(result) == 0
