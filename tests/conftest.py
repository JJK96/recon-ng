"""
Shared pytest fixtures for recon-ng test suite.

This module provides fixtures for:
- Temporary home directory isolation
- Workspace management
- Framework/Recon instance creation
- Flask test client
- Sample test data
"""
import os
import sys
import shutil
import tempfile
import sqlite3
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from recon.core import framework
from recon.core.framework import Framework, Options, FrameworkException


# =============================================================================
# FRAMEWORK STATE MANAGEMENT
# =============================================================================

@pytest.fixture(autouse=True)
def reset_framework_state():
    """Reset Framework class-level state before each test.
    
    The Framework class uses class-level variables that persist between tests.
    This fixture ensures a clean state for each test.
    """
    # Store original values
    original_state = {
        '_script': Framework._script,
        '_load': Framework._load,
        '_mode': Framework._mode,
        '_global_options': Framework._global_options,
        '_loaded_modules': Framework._loaded_modules.copy(),
        'app_path': Framework.app_path,
        'data_path': Framework.data_path,
        'core_path': Framework.core_path,
        'home_path': Framework.home_path,
        'mod_path': Framework.mod_path,
        'spaces_path': Framework.spaces_path,
        'workspace': Framework.workspace,
        '_record': Framework._record,
        '_spool': Framework._spool,
        '_summary_counts': Framework._summary_counts.copy(),
    }
    
    yield
    
    # Restore original values
    Framework._script = original_state['_script']
    Framework._load = original_state['_load']
    Framework._mode = original_state['_mode']
    Framework._global_options = original_state['_global_options']
    Framework._loaded_modules = original_state['_loaded_modules']
    Framework.app_path = original_state['app_path']
    Framework.data_path = original_state['data_path']
    Framework.core_path = original_state['core_path']
    Framework.home_path = original_state['home_path']
    Framework.mod_path = original_state['mod_path']
    Framework.spaces_path = original_state['spaces_path']
    Framework.workspace = original_state['workspace']
    Framework._record = original_state['_record']
    Framework._spool = original_state['_spool']
    Framework._summary_counts = original_state['_summary_counts']


# =============================================================================
# TEMPORARY DIRECTORY FIXTURES
# =============================================================================

@pytest.fixture
def temp_home_path(tmp_path):
    """Create an isolated ~/.recon-ng directory for testing.
    
    This fixture creates a temporary directory structure that mimics
    the real recon-ng home directory.
    
    Returns:
        Path: Path to temporary home directory
    """
    home_path = tmp_path / ".recon-ng"
    home_path.mkdir(parents=True)
    
    # Create subdirectories
    (home_path / "modules").mkdir()
    (home_path / "workspaces").mkdir()
    (home_path / "data").mkdir()
    
    return home_path


@pytest.fixture
def temp_workspace(temp_home_path):
    """Create a fresh workspace with a clean database.
    
    Returns:
        tuple: (workspace_path, workspace_name)
    """
    workspace_name = "test_workspace"
    workspace_path = temp_home_path / "workspaces" / workspace_name
    workspace_path.mkdir(parents=True)
    
    # Create the database schema
    db_path = workspace_path / "data.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Create all tables (matching _create_db in base.py)
    cursor.execute('CREATE TABLE IF NOT EXISTS domains (domain TEXT, notes TEXT, module TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS companies (company TEXT, description TEXT, notes TEXT, module TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS tenants (brand TEXT, name TEXT, id TEXT, region TEXT, subregion TEXT, domain TEXT, desktopSSOEnabled BOOLEAN, CBAEnabled BOOLEAN, usesCloudSync BOOLEAN, module TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS netblocks (netblock TEXT, notes TEXT, module TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS locations (latitude TEXT, longitude TEXT, street_address TEXT, notes TEXT, module TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS vulnerabilities (host TEXT, reference TEXT, example TEXT, publish_date TEXT, category TEXT, status TEXT, notes TEXT, module TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS ports (ip_address TEXT, host TEXT, port TEXT, protocol TEXT, banner TEXT, notes TEXT, module TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS hosts (host TEXT, cname TEXT, ip_address TEXT, region TEXT, country TEXT, latitude TEXT, longitude TEXT, organization TEXT, notes TEXT, module TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS contacts (first_name TEXT, middle_name TEXT, last_name TEXT, email TEXT, title TEXT, region TEXT, country TEXT, phone TEXT, notes TEXT, module TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS credentials (username TEXT, password TEXT, hash TEXT, type TEXT, leak TEXT, notes TEXT, module TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS leaks (leak_id TEXT, description TEXT, source_refs TEXT, leak_type TEXT, title TEXT, import_date TEXT, leak_date TEXT, attackers TEXT, num_entries TEXT, score TEXT, num_domains_affected TEXT, attack_method TEXT, target_industries TEXT, password_hash TEXT, password_type TEXT, targets TEXT, media_refs TEXT, notes TEXT, module TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS pushpins (source TEXT, screen_name TEXT, profile_name TEXT, profile_url TEXT, media_url TEXT, thumb_url TEXT, message TEXT, latitude TEXT, longitude TEXT, time TEXT, notes TEXT, module TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS profiles (username TEXT, resource TEXT, url TEXT, category TEXT, contact_id INTEGER, notes TEXT, module TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS repositories (name TEXT, owner TEXT, description TEXT, resource TEXT, category TEXT, url TEXT, notes TEXT, module TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS dashboard (module TEXT PRIMARY KEY, runs INT)')
    cursor.execute('PRAGMA user_version = 13')
    
    conn.commit()
    conn.close()
    
    return workspace_path, workspace_name


# =============================================================================
# FRAMEWORK INSTANCE FIXTURES
# =============================================================================

@pytest.fixture
def mock_framework(temp_home_path, temp_workspace):
    """Create a Framework instance with paths overridden for testing.
    
    Returns:
        Framework: Configured Framework instance
    """
    workspace_path, workspace_name = temp_workspace
    
    # Override class-level paths
    Framework.home_path = str(temp_home_path)
    Framework.mod_path = str(temp_home_path / "modules")
    Framework.data_path = str(temp_home_path / "data")
    Framework.spaces_path = str(temp_home_path / "workspaces")
    Framework.workspace = str(workspace_path)
    Framework.app_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    Framework.core_path = os.path.join(Framework.app_path, 'recon', 'core')
    
    # Initialize global options
    Framework._global_options = Options()
    Framework._global_options.init_option('nameserver', '8.8.8.8', True, 'default nameserver')
    Framework._global_options.init_option('proxy', None, False, 'proxy server')
    Framework._global_options.init_option('threads', 10, True, 'number of threads')
    Framework._global_options.init_option('timeout', 10, True, 'socket timeout')
    Framework._global_options.init_option('user-agent', 'Recon-ng/test', True, 'user-agent')
    Framework._global_options.init_option('verbosity', 1, True, 'verbosity level')
    
    # Create Framework instance
    fw = Framework('test')
    fw.options = Framework._global_options
    
    return fw


@pytest.fixture
def mock_recon(temp_home_path, temp_workspace):
    """Create a Recon instance with paths overridden for testing.
    
    This fixture avoids network calls and filesystem side effects.
    
    Returns:
        Recon: Configured Recon instance
    """
    from recon.core.base import Recon, Mode
    
    workspace_path, workspace_name = temp_workspace
    
    # Create keys database
    keys_db_path = temp_home_path / "keys.db"
    conn = sqlite3.connect(str(keys_db_path))
    conn.execute('CREATE TABLE IF NOT EXISTS keys (name TEXT PRIMARY KEY, value TEXT)')
    conn.commit()
    conn.close()
    
    # Patch to avoid network and other side effects
    with patch.object(Recon, '_check_version'), \
         patch.object(Recon, '_fetch_module_index'), \
         patch.object(Recon, '_load_modules'), \
         patch.object(Recon, '_load_config'), \
         patch.object(Recon, '_send_analytics'):
        
        # Create Recon instance without checks
        recon = Recon(check=False, analytics=False, marketplace=False)
        
        # Override paths
        recon.home_path = Framework.home_path = str(temp_home_path)
        recon.mod_path = Framework.mod_path = str(temp_home_path / "modules")
        recon.data_path = Framework.data_path = str(temp_home_path / "data")
        recon.spaces_path = Framework.spaces_path = str(temp_home_path / "workspaces")
        recon.workspace = Framework.workspace = str(workspace_path)
        recon.app_path = Framework.app_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        recon.core_path = Framework.core_path = os.path.join(recon.app_path, 'recon', 'core')
        
        # Initialize options
        recon._init_global_options()
        
        return recon


# =============================================================================
# DATABASE FIXTURES
# =============================================================================

@pytest.fixture
def populated_database(mock_framework):
    """Populate the test database with sample data for all entity types.
    
    Uses example.com and related test domains.
    
    Returns:
        Framework: Framework instance with populated database
    """
    from tests.fixtures.test_data import (
        SAMPLE_DOMAINS, SAMPLE_HOSTS, SAMPLE_CONTACTS,
        SAMPLE_CREDENTIALS, SAMPLE_COMPANIES, SAMPLE_NETBLOCKS,
        SAMPLE_LOCATIONS, SAMPLE_VULNERABILITIES, SAMPLE_PORTS,
        SAMPLE_LEAKS, SAMPLE_PUSHPINS, SAMPLE_PROFILES,
        SAMPLE_REPOSITORIES, SAMPLE_TENANTS
    )
    
    # Insert sample data
    for domain in SAMPLE_DOMAINS:
        mock_framework.insert_domains(**domain, mute=True)
    
    for host in SAMPLE_HOSTS:
        mock_framework.insert_hosts(**host, mute=True)
    
    for contact in SAMPLE_CONTACTS:
        mock_framework.insert_contacts(**contact, mute=True)
    
    for cred in SAMPLE_CREDENTIALS:
        mock_framework.insert_credentials(**cred, mute=True)
    
    for company in SAMPLE_COMPANIES:
        mock_framework.insert_companies(**company, mute=True)
    
    for netblock in SAMPLE_NETBLOCKS:
        mock_framework.insert_netblocks(**netblock, mute=True)
    
    for location in SAMPLE_LOCATIONS:
        mock_framework.insert_locations(**location, mute=True)
    
    for vuln in SAMPLE_VULNERABILITIES:
        mock_framework.insert_vulnerabilities(**vuln, mute=True)
    
    for port in SAMPLE_PORTS:
        mock_framework.insert_ports(**port, mute=True)
    
    for leak in SAMPLE_LEAKS:
        mock_framework.insert_leaks(**leak, mute=True)
    
    for pushpin in SAMPLE_PUSHPINS:
        mock_framework.insert_pushpins(**pushpin, mute=True)
    
    for profile in SAMPLE_PROFILES:
        mock_framework.insert_profiles(**profile, mute=True)
    
    for repo in SAMPLE_REPOSITORIES:
        mock_framework.insert_repositories(**repo, mute=True)
    
    for tenant in SAMPLE_TENANTS:
        mock_framework.insert_tenants(**tenant, mute=True)
    
    return mock_framework


# =============================================================================
# FLASK/API FIXTURES
# =============================================================================

@pytest.fixture
def flask_test_client(mock_recon, temp_workspace):
    """Create a Flask test client with mocked Redis.
    
    Returns:
        FlaskClient: Flask test client
    """
    # Import here to avoid circular imports
    from recon.core.web import create_app
    
    workspace_path, workspace_name = temp_workspace
    
    # Mock Redis
    with patch('recon.core.web.Redis') as mock_redis, \
         patch('recon.core.web.rq.Queue') as mock_queue:
        
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        
        mock_queue_instance = MagicMock()
        mock_queue.return_value = mock_queue_instance
        
        # Create app with test config
        app = create_app(workspace=str(workspace_path))
        app.config['TESTING'] = True
        app.config['DEBUG'] = False
        
        with app.test_client() as client:
            yield client


# =============================================================================
# MODULE FIXTURES
# =============================================================================

@pytest.fixture
def sample_module_path(temp_home_path):
    """Create a sample test module file.
    
    Returns:
        Path: Path to the test module
    """
    # Create the module directory structure
    module_dir = temp_home_path / "modules" / "recon" / "test"
    module_dir.mkdir(parents=True)
    
    # Copy the sample module
    sample_module_src = os.path.join(
        os.path.dirname(__file__),
        'fixtures',
        'sample_module.py'
    )
    
    module_path = module_dir / "sample_module.py"
    
    # If the source doesn't exist yet, create a minimal module
    if os.path.exists(sample_module_src):
        shutil.copy(sample_module_src, module_path)
    else:
        module_content = '''"""
---
name: Sample Test Module
author: Test Author
version: 1.0
description: A test module for framework testing
query: SELECT domain FROM domains WHERE domain IS NOT NULL
---
"""
from recon.core.module import BaseModule

class Module(BaseModule):
    meta = {
        'name': 'Sample Test Module',
        'author': 'Test Author',
        'version': '1.0',
        'description': 'A test module for framework testing',
        'query': 'SELECT domain FROM domains WHERE domain IS NOT NULL',
    }

    def module_run(self, domains):
        for domain in domains:
            self.output(f"Processing: {domain}")
'''
        module_path.write_text(module_content)
    
    return module_path


# =============================================================================
# UTILITY FIXTURES
# =============================================================================

@pytest.fixture
def capture_output(capsys):
    """Capture stdout/stderr output.
    
    Returns:
        Callable: Function to get captured output
    """
    def get_output():
        captured = capsys.readouterr()
        return captured.out, captured.err
    return get_output


@pytest.fixture
def mock_http_response():
    """Create a mock HTTP response for testing request methods.
    
    Returns:
        Callable: Factory function for creating mock responses
    """
    def create_response(status_code=200, text='', json_data=None, headers=None):
        response = MagicMock()
        response.status_code = status_code
        response.text = text
        response.json.return_value = json_data or {}
        response.headers = headers or {}
        response.content = text.encode() if isinstance(text, str) else text
        response.ok = 200 <= status_code < 300
        return response
    
    return create_response


@pytest.fixture
def freeze_time():
    """Fixture for freezing time in tests.
    
    Returns:
        datetime: Frozen datetime object
    """
    from freezegun import freeze_time as ft
    
    frozen_time = datetime(2024, 1, 15, 12, 0, 0)
    with ft(frozen_time):
        yield frozen_time


# =============================================================================
# MARKER-BASED FIXTURES
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "integration: Integration tests (real db/fs)")
    config.addinivalue_line("markers", "slow: Slow tests (>1s)")
    config.addinivalue_line("markers", "api: Flask API tests")


def pytest_collection_modifyitems(config, items):
    """Automatically add markers based on test location."""
    for item in items:
        # Add markers based on test path
        if '/unit/' in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif '/integration/' in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        # Add api marker for API tests
        if 'test_api' in str(item.fspath):
            item.add_marker(pytest.mark.api)
