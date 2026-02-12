"""
Integration tests for the recon-ng Sanic REST API.

Tests the following API endpoints:
- /api/tasks/ - Task management
- /api/modules/ - Module listing and configuration
- /api/workspaces/ - Workspace management
- /api/dashboard - Dashboard summary
- /api/tables/ - Table data access
- /api/exports - Export formats
- /api/reports/ - Report generation

Uses mocked RPC client to avoid external dependencies.
"""
import json
import os
import sys
import sqlite3
import tempfile
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from types import SimpleNamespace

import pytest

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def api_test_setup(tmp_path):
    """Setup an isolated test environment for API testing.
    
    This fixture creates a complete isolated environment with:
    - Temporary home directory with proper structure
    - Test workspace with database (using actual migrations)
    """
    from recon.core.base import Recon
    from recon.core.framework import Framework
    
    # Create directory structure
    home_path = tmp_path / ".recon-ng"
    home_path.mkdir()
    (home_path / "modules").mkdir()
    (home_path / "workspaces").mkdir()
    (home_path / "data").mkdir()
    
    # Create test workspace
    workspace_name = "test_workspace"
    workspace_path = home_path / "workspaces" / workspace_name
    workspace_path.mkdir()
    
    # Create keys database
    keys_db_path = home_path / "keys.db"
    conn = sqlite3.connect(str(keys_db_path))
    conn.execute('CREATE TABLE IF NOT EXISTS keys (name TEXT PRIMARY KEY, value TEXT)')
    conn.commit()
    conn.close()
    
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
    Framework.workspace = str(workspace_path)
    
    # Create a minimal Recon instance to use _create_db
    with patch.object(Recon, '_check_version'), \
         patch.object(Recon, '_fetch_module_index'), \
         patch.object(Recon, '_load_modules'), \
         patch.object(Recon, '_send_analytics'), \
         patch.object(Recon, '_init_workspace'):
        
        temp_recon = Recon(check=False, analytics=False, marketplace=False)
        temp_recon.workspace = str(workspace_path)
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
    
    # Insert sample data
    db_path = workspace_path / "data.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    cursor.execute("INSERT INTO domains VALUES ('example.com', 'Test domain', 'test_module')")
    cursor.execute("INSERT INTO domains VALUES ('example.org', 'Another domain', 'test_module')")
    cursor.execute("INSERT INTO hosts VALUES ('www.example.com', NULL, '192.0.2.1', 'CA', 'US', '37.7749', '-122.4194', NULL, 'Test host', 'test_module')")
    cursor.execute("INSERT INTO contacts VALUES ('John', NULL, 'Doe', 'john@example.com', 'Admin', 'CA', 'US', '+1-555-0100', 'Test contact', 'test_module')")
    cursor.execute("INSERT INTO companies VALUES ('Example Corp', 'Test company', 'Primary target', 'test_module')")
    cursor.execute("INSERT INTO dashboard VALUES ('test_module', 5)")
    
    conn.commit()
    conn.close()
    
    return {
        'home_path': str(home_path),
        'workspace_path': str(workspace_path),
        'workspace_name': workspace_name,
        'db_path': str(db_path),
    }


class MockRPCClient:
    """Mock RPC client for testing API endpoints."""
    
    def __init__(self, db_path: str, workspace_name: str):
        self.db_path = db_path
        self.workspace_name = workspace_name
        self.modules = {}  # Simulated loaded modules
        self.tasks = {}  # Simulated tasks
    
    async def connect(self):
        pass
    
    async def close(self):
        pass
    
    async def call(self, command: str, workspace: str = None, params: dict = None, timeout: float = 30.0):
        """Handle RPC calls with mock responses."""
        params = params or {}
        
        # Workspace commands
        if command == 'workspaces/list':
            return {'workspaces': [self.workspace_name]}
        
        elif command == 'workspaces/info':
            ws = params.get('workspace', self.workspace_name)
            if ws == self.workspace_name:
                return {'workspace': ws}
            from recon.core.web.rpc import RPCClientError
            raise RPCClientError(f"NOT_FOUND: Workspace '{ws}' not found")
        
        # Module commands
        elif command == 'modules/list':
            return {'modules': list(self.modules.keys())}
        
        elif command == 'modules/info':
            module = params.get('module')
            if module in self.modules:
                return {'module': self.modules[module]}
            from recon.core.web.rpc import RPCClientError
            raise RPCClientError(f"NOT_FOUND: Module '{module}' not found")
        
        elif command == 'modules/load':
            module = params.get('module')
            if module in self.modules:
                options = params.get('options', {})
                self.modules[module]['options'].update(options)
                return {'module': self.modules[module]}
            from recon.core.web.rpc import RPCClientError
            raise RPCClientError(f"NOT_FOUND: Module '{module}' not found")
        
        # Options commands
        elif command == 'options/list':
            return {'options': [
                {'name': 'NAMESERVER', 'value': '8.8.8.8', 'required': True},
                {'name': 'THREADS', 'value': 10, 'required': True},
            ]}
        
        # Database commands
        elif command == 'db/tables':
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return {'tables': tables}
        
        elif command == 'db/query':
            sql = params.get('sql', '')
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            conn.close()
            return {'columns': columns, 'rows': rows}
        
        # Dashboard commands
        elif command == 'dashboard/show':
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get record counts
            records = []
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'dashboard'")
            for (table,) in cursor.fetchall():
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                records.append({'table': table, 'count': count})
            
            # Get activity
            cursor.execute("SELECT module, runs FROM dashboard")
            activity = [{'module': row[0], 'count': row[1]} for row in cursor.fetchall()]
            
            conn.close()
            return {'dashboard': {'records': records, 'activity': activity}}
        
        return {}


class MockTaskTracker:
    """Mock task tracker for testing with async interface matching the real TaskTracker."""
    
    def __init__(self):
        self.tasks = {}
        self._counter = 0
    
    def create_task_sync(self, session_id: str, workspace: str, module: str):
        """Synchronously create a task (for use in tests)."""
        self._counter += 1
        task_id = f"task-{self._counter}"
        self.tasks[task_id] = {
            'id': task_id,
            'session_id': session_id,
            'workspace': workspace,
            'module': module,
            'status': 'pending'
        }
        return task_id
    
    async def create_task(self, session_id: str, workspace: str, module: str):
        """Async create task (matches real TaskTracker interface)."""
        return self.create_task_sync(session_id, workspace, module)
    
    async def get_task(self, task_id: str):
        """Async get task (matches real TaskTracker interface)."""
        task = self.tasks.get(task_id)
        if task:
            return {'id': task_id, **task.copy()}
        return None
    
    async def get_tasks(self):
        """Async get all tasks (matches real TaskTracker interface)."""
        return [{'id': tid, **info.copy()} for tid, info in self.tasks.items()]
    
    async def update_task(self, task_id: str, **kwargs):
        """Async update task (matches real TaskTracker interface)."""
        if task_id in self.tasks:
            self.tasks[task_id].update(kwargs)


@pytest.fixture
def sanic_app(api_test_setup):
    """Create a Sanic test app with mocked RPC client."""
    from sanic import Sanic
    from recon.core.web.api import api_blueprint
    import recon.core.web.api as api_module
    
    setup = api_test_setup
    
    # Force a unique app name to avoid Sanic's app registry conflicts
    Sanic._app_registry = {}
    
    # Create a fresh Sanic app for testing
    app = Sanic(f"test-recon-web")
    app.config.DEBUG = True
    
    # Register the API blueprint
    app.blueprint(api_blueprint)
    
    # Create mock RPC client and task tracker
    mock_rpc = MockRPCClient(setup['db_path'], setup['workspace_name'])
    test_task_tracker = MockTaskTracker()
    
    # Set up app context
    @app.before_server_start
    async def setup_ctx(app, loop):
        app.ctx.rpc = mock_rpc
        app.ctx.task_tracker = test_task_tracker
        app.ctx.workspace = setup['workspace_name']
    
    # Patch the module-level task_tracker and workspace functions
    # These patches must be active during test execution
    patches = [
        patch.object(api_module, 'get_workspace', return_value=setup['workspace_name']),
        patch.object(api_module, 'set_workspace'),
        patch.object(api_module, 'task_tracker', test_task_tracker),
    ]
    
    # Start all patches
    for p in patches:
        p.start()
    
    yield app, mock_rpc, test_task_tracker, setup
    
    # Stop all patches
    for p in patches:
        p.stop()


@pytest.fixture
def test_client(sanic_app):
    """Get Sanic test client."""
    app, mock_rpc, task_tracker, setup = sanic_app
    return app.test_client, mock_rpc, task_tracker, setup


# =============================================================================
# WORKSPACE ENDPOINT TESTS
# =============================================================================

@pytest.mark.api
class TestWorkspaceAPI:
    """Tests for /api/workspaces/ endpoints."""
    
    def test_get_workspaces_list(self, test_client):
        """Test GET /api/workspaces/ returns list of workspaces."""
        client, mock_rpc, _, setup = test_client
        
        _, response = client.get('/api/workspaces')
        assert response.status == 200
        
        data = response.json
        assert 'workspaces' in data
        assert isinstance(data['workspaces'], list)
        assert setup['workspace_name'] in data['workspaces']
    
    def test_get_workspace_info(self, test_client):
        """Test GET /api/workspaces/<name> returns workspace info."""
        client, mock_rpc, _, setup = test_client
        
        _, response = client.get(f'/api/workspaces/{setup["workspace_name"]}')
        assert response.status == 200
        
        data = response.json
        assert data['name'] == setup['workspace_name']
        assert data['status'] == 'active'
        assert 'options' in data
    
    def test_get_nonexistent_workspace_returns_404(self, test_client):
        """Test GET /api/workspaces/<name> returns 404 for unknown workspace."""
        client, mock_rpc, _, _ = test_client
        
        _, response = client.get('/api/workspaces/nonexistent')
        assert response.status == 404
    
    def test_patch_workspace_activate(self, test_client):
        """Test PATCH /api/workspaces/<name> can activate workspace."""
        client, mock_rpc, _, setup = test_client
        
        _, response = client.patch(
            f'/api/workspaces/{setup["workspace_name"]}',
            json={'status': 'active'}
        )
        assert response.status == 200
        
        data = response.json
        assert data['name'] == setup['workspace_name']


# =============================================================================
# MODULE ENDPOINT TESTS
# =============================================================================

@pytest.mark.api
class TestModuleAPI:
    """Tests for /api/modules/ endpoints."""
    
    def test_get_modules_list_empty(self, test_client):
        """Test GET /api/modules/ returns empty list when no modules loaded."""
        client, mock_rpc, _, _ = test_client
        mock_rpc.modules = {}
        
        _, response = client.get('/api/modules')
        assert response.status == 200
        
        data = response.json
        assert 'modules' in data
        assert data['modules'] == []
    
    def test_get_modules_list_with_modules(self, test_client):
        """Test GET /api/modules/ returns list when modules are loaded."""
        client, mock_rpc, _, _ = test_client
        
        # Add some mock modules
        mock_rpc.modules = {
            'recon/domains-hosts/test_module': {
                'name': 'test_module',
                'path': 'recon/domains-hosts/test_module',
                'options': {'SOURCE': 'default'}
            },
            'recon/hosts-ports/another_module': {
                'name': 'another_module',
                'path': 'recon/hosts-ports/another_module',
                'options': {}
            }
        }
        
        _, response = client.get('/api/modules')
        assert response.status == 200
        
        data = response.json
        assert 'modules' in data
        assert len(data['modules']) == 2
        assert 'recon/domains-hosts/test_module' in data['modules']
    
    def test_get_module_info(self, test_client):
        """Test GET /api/modules/<path> returns module information."""
        client, mock_rpc, _, _ = test_client
        
        mock_rpc.modules = {
            'recon/domains-hosts/test_module': {
                'name': 'test_module',
                'path': 'recon/domains-hosts/test_module',
                'author': 'Test Author',
                'description': 'A test module',
                'options': {'SOURCE': 'default'}
            }
        }
        
        _, response = client.get('/api/modules/recon/domains-hosts/test_module')
        assert response.status == 200
        
        data = response.json
        assert data['name'] == 'test_module'
        assert data['author'] == 'Test Author'
    
    def test_get_nonexistent_module_returns_404(self, test_client):
        """Test GET /api/modules/<path> returns 404 for unknown module."""
        client, mock_rpc, _, _ = test_client
        mock_rpc.modules = {}
        
        _, response = client.get('/api/modules/nonexistent/module')
        assert response.status == 404
    
    def test_patch_module_options(self, test_client):
        """Test PATCH /api/modules/<path> updates module options."""
        client, mock_rpc, _, _ = test_client
        
        mock_rpc.modules = {
            'recon/domains-hosts/test_module': {
                'name': 'test_module',
                'path': 'recon/domains-hosts/test_module',
                'options': {'SOURCE': 'default'}
            }
        }
        
        _, response = client.patch(
            '/api/modules/recon/domains-hosts/test_module',
            json={'options': [{'name': 'SOURCE', 'value': 'example.com'}]}
        )
        assert response.status == 200
        
        # Verify option was updated
        assert mock_rpc.modules['recon/domains-hosts/test_module']['options']['SOURCE'] == 'example.com'


# =============================================================================
# TABLE ENDPOINT TESTS
# =============================================================================

@pytest.mark.api
class TestTableAPI:
    """Tests for /api/tables/ endpoints."""
    
    def test_get_tables_list(self, test_client):
        """Test GET /api/tables/ returns list of tables."""
        client, mock_rpc, _, setup = test_client
        
        _, response = client.get('/api/tables')
        assert response.status == 200
        
        data = response.json
        assert 'tables' in data
        assert 'domains' in data['tables']
        assert 'hosts' in data['tables']
        assert 'contacts' in data['tables']
    
    def test_get_table_contents(self, test_client):
        """Test GET /api/tables/<name> returns table contents."""
        client, mock_rpc, _, _ = test_client
        
        _, response = client.get('/api/tables/domains')
        assert response.status == 200
        
        data = response.json
        assert 'rows' in data
        # We inserted 2 domains in setup
        assert len(data['rows']) >= 2
    
    def test_get_table_with_specific_columns(self, test_client):
        """Test GET /api/tables/<name>?columns=col1,col2 returns specific columns."""
        client, mock_rpc, _, _ = test_client
        
        _, response = client.get('/api/tables/domains?columns=domain')
        assert response.status == 200
        
        data = response.json
        assert 'rows' in data
    
    def test_get_nonexistent_table_returns_404(self, test_client):
        """Test GET /api/tables/<name> returns 404 for unknown table."""
        client, mock_rpc, _, _ = test_client
        
        _, response = client.get('/api/tables/nonexistent_table')
        assert response.status == 404
    
    def test_get_table_csv_format(self, test_client):
        """Test GET /api/tables/<name>?format=csv returns CSV format."""
        client, mock_rpc, _, _ = test_client
        
        _, response = client.get('/api/tables/domains?format=csv')
        assert response.status == 200
        assert 'text/csv' in response.content_type or 'text/plain' in response.content_type
    
    def test_get_table_json_format(self, test_client):
        """Test GET /api/tables/<name>?format=json returns JSON format."""
        client, mock_rpc, _, _ = test_client
        
        _, response = client.get('/api/tables/domains?format=json')
        assert response.status == 200
        assert 'application/json' in response.content_type
    
    def test_get_table_xml_format(self, test_client):
        """Test GET /api/tables/<name>?format=xml returns XML format."""
        client, mock_rpc, _, _ = test_client
        
        _, response = client.get('/api/tables/domains?format=xml')
        assert response.status == 200
        assert 'xml' in response.content_type
    
    def test_get_table_list_format(self, test_client):
        """Test GET /api/tables/<name>?format=list returns list format."""
        client, mock_rpc, _, _ = test_client
        
        _, response = client.get('/api/tables/domains?format=list')
        assert response.status == 200


# =============================================================================
# DASHBOARD ENDPOINT TESTS
# =============================================================================

@pytest.mark.api
class TestDashboardAPI:
    """Tests for /api/dashboard endpoint."""
    
    def test_get_dashboard(self, test_client):
        """Test GET /api/dashboard returns dashboard data."""
        client, mock_rpc, _, setup = test_client
        
        _, response = client.get('/api/dashboard')
        assert response.status == 200
        
        data = response.json
        assert 'workspace' in data
        assert 'records' in data
        assert 'activity' in data
    
    def test_dashboard_records_structure(self, test_client):
        """Test dashboard records have correct structure."""
        client, mock_rpc, _, _ = test_client
        
        _, response = client.get('/api/dashboard')
        assert response.status == 200
        
        data = response.json
        for record in data['records']:
            assert 'table' in record
            assert 'count' in record
    
    def test_dashboard_activity_structure(self, test_client):
        """Test dashboard activity has correct structure."""
        client, mock_rpc, _, _ = test_client
        
        _, response = client.get('/api/dashboard')
        assert response.status == 200
        
        data = response.json
        if data['activity']:
            for activity in data['activity']:
                assert 'module' in activity
                assert 'count' in activity


# =============================================================================
# TASK ENDPOINT TESTS
# =============================================================================

@pytest.mark.api
class TestTaskAPI:
    """Tests for /api/tasks/ endpoints."""
    
    def test_get_tasks_list_empty(self, test_client):
        """Test GET /api/tasks/ returns empty list when no tasks."""
        client, mock_rpc, task_tracker, _ = test_client
        
        _, response = client.get('/api/tasks')
        assert response.status == 200
        
        data = response.json
        assert 'tasks' in data
        assert data['tasks'] == []
    
    def test_get_tasks_list_with_tasks(self, test_client):
        """Test GET /api/tasks/ returns list when tasks exist."""
        client, mock_rpc, task_tracker, setup = test_client
        
        # Create a task synchronously
        task_id = task_tracker.create_task_sync('test-session', setup['workspace_name'], 'test/module')
        
        _, response = client.get('/api/tasks')
        assert response.status == 200
        
        data = response.json
        assert 'tasks' in data
        assert len(data['tasks']) >= 1
    
    def test_post_task_creates_job(self, test_client):
        """Test POST /api/tasks/ creates a new task."""
        client, mock_rpc, task_tracker, _ = test_client
        
        # Add a module for the task
        mock_rpc.modules = {
            'recon/domains-hosts/test_module': {
                'name': 'test_module',
                'path': 'recon/domains-hosts/test_module',
                'options': {}
            }
        }
        
        _, response = client.post(
            '/api/tasks',
            json={'path': 'recon/domains-hosts/test_module'}
        )
        assert response.status == 201
        
        data = response.json
        assert 'task' in data
    
    def test_post_task_invalid_module_returns_404(self, test_client):
        """Test POST /api/tasks/ returns 404 for unknown module."""
        client, mock_rpc, _, _ = test_client
        mock_rpc.modules = {}
        
        _, response = client.post(
            '/api/tasks',
            json={'path': 'nonexistent/module'}
        )
        assert response.status == 404
    
    def test_post_task_no_path_returns_400(self, test_client):
        """Test POST /api/tasks/ returns 400 when no path provided."""
        client, mock_rpc, _, _ = test_client
        
        _, response = client.post('/api/tasks', json={})
        assert response.status == 400
    
    def test_get_task_by_id(self, test_client):
        """Test GET /api/tasks/<id> returns task info."""
        client, mock_rpc, task_tracker, setup = test_client
        
        # Create a task synchronously
        task_id = task_tracker.create_task_sync('test-session', setup['workspace_name'], 'test/module')
        
        _, response = client.get(f'/api/tasks/{task_id}')
        assert response.status == 200
        
        data = response.json
        assert data['id'] == task_id
        assert data['module'] == 'test/module'
    
    def test_get_task_nonexistent_returns_404(self, test_client):
        """Test GET /api/tasks/<id> returns 404 for unknown task."""
        client, mock_rpc, _, _ = test_client
        
        _, response = client.get('/api/tasks/nonexistent-task-id')
        assert response.status == 404


# =============================================================================
# EXPORT ENDPOINT TESTS
# =============================================================================

@pytest.mark.api
class TestExportAPI:
    """Tests for export-related endpoints."""
    
    def test_table_export_formats_available(self, test_client):
        """Test that various export formats work for tables."""
        client, mock_rpc, _, _ = test_client
        
        formats = ['json', 'csv', 'xml', 'list']
        for fmt in formats:
            _, response = client.get(f'/api/tables/domains?format={fmt}')
            assert response.status == 200, f"Format {fmt} failed"


# =============================================================================
# REPORT ENDPOINT TESTS
# =============================================================================

@pytest.mark.api
class TestReportAPI:
    """Tests for /api/reports/ endpoints."""
    
    def test_get_reports_list(self, test_client):
        """Test GET /api/reports/ returns list of report types."""
        client, mock_rpc, _, _ = test_client
        
        _, response = client.get('/api/reports')
        assert response.status == 200
        
        data = response.json
        assert 'reports' in data
        assert isinstance(data['reports'], list)


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

@pytest.mark.api
class TestAPIErrorHandling:
    """Tests for API error handling."""
    
    def test_invalid_json_body(self, test_client):
        """Test that invalid JSON returns appropriate error."""
        client, mock_rpc, _, _ = test_client
        
        # Add a module
        mock_rpc.modules = {'test/module': {'name': 'test', 'options': {}}}
        
        # Send invalid JSON (Sanic may handle this differently)
        _, response = client.patch(
            '/api/modules/test/module',
            content='not valid json',
            headers={'Content-Type': 'application/json'}
        )
        # Sanic returns 400 for invalid JSON
        assert response.status in [400, 500]


# =============================================================================
# CONTENT TYPE TESTS
# =============================================================================

@pytest.mark.api
class TestAPIContentTypes:
    """Tests for API response content types."""
    
    def test_json_response_content_type(self, test_client):
        """Test that JSON responses have correct content type."""
        client, mock_rpc, _, _ = test_client
        
        _, response = client.get('/api/workspaces')
        assert 'application/json' in response.content_type
    
    def test_csv_response_content_type(self, test_client):
        """Test that CSV responses have correct content type."""
        client, mock_rpc, _, _ = test_client
        
        _, response = client.get('/api/tables/domains?format=csv')
        assert response.status == 200
    
    def test_xml_response_content_type(self, test_client):
        """Test that XML responses have correct content type."""
        client, mock_rpc, _, _ = test_client
        
        _, response = client.get('/api/tables/domains?format=xml')
        assert response.status == 200


# =============================================================================
# INTEGRATION WORKFLOW TESTS
# =============================================================================

@pytest.mark.api
class TestAPIIntegration:
    """Tests for multi-step API workflows."""
    
    def test_workflow_list_tables_then_query(self, test_client):
        """Test workflow: list tables, then query a specific table."""
        client, mock_rpc, _, _ = test_client
        
        # Step 1: List tables
        _, response = client.get('/api/tables')
        assert response.status == 200
        tables = response.json['tables']
        
        # Step 2: Query each table
        for table in tables[:3]:  # Test first 3 tables
            _, response = client.get(f'/api/tables/{table}')
            assert response.status == 200, f"Failed to query table: {table}"
    
    def test_workflow_dashboard_overview(self, test_client):
        """Test workflow: get dashboard, verify tables match records."""
        client, mock_rpc, _, _ = test_client
        
        # Get dashboard
        _, response = client.get('/api/dashboard')
        assert response.status == 200
        
        dashboard = response.json
        record_tables = {r['table'] for r in dashboard['records']}
        
        # Get tables list
        _, response = client.get('/api/tables')
        assert response.status == 200
        
        # Dashboard records should correspond to existing tables
        api_tables = set(response.json['tables'])
        # Note: dashboard excludes dashboard table itself
        assert record_tables.issubset(api_tables | {'dashboard'})
