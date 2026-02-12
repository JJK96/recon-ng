"""
Integration tests for the recon-ng Flask REST API.

Tests the following API endpoints:
- /api/tasks/ - Task management
- /api/modules/ - Module listing and configuration
- /api/workspaces/ - Workspace management
- /api/dashboard - Dashboard summary
- /api/tables/ - Table data access
- /api/exports - Export formats
- /api/reports/ - Report generation

Uses mocked Redis to avoid external dependencies.

Note: These tests require Flask to be installed.
"""
import json
import os
import sys
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Check if Flask is available - skip entire module if not
flask_available = True
try:
    import flask
except ImportError:
    flask_available = False

pytestmark = pytest.mark.skipif(
    not flask_available,
    reason="Flask not installed - API tests require Flask"
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def api_test_setup(tmp_path):
    """Setup an isolated test environment for API testing.
    
    This fixture creates a complete isolated environment with:
    - Temporary home directory with proper structure
    - Test workspace with database (using actual migrations)
    - Mocked Redis and RQ
    - Flask test client
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


@pytest.fixture
def flask_client(api_test_setup):
    """Create a Flask test client with properly mocked dependencies."""
    from recon.core import framework
    from recon.core.framework import Framework, Options
    
    setup = api_test_setup
    
    # Store original state
    original_state = {
        'home_path': Framework.home_path,
        'mod_path': Framework.mod_path,
        'data_path': Framework.data_path,
        'spaces_path': Framework.spaces_path,
        'workspace': Framework.workspace,
        '_loaded_modules': Framework._loaded_modules.copy(),
        '_global_options': Framework._global_options,
    }
    
    # Create a mock recon object
    mock_recon = MagicMock()
    mock_recon.workspace = setup['workspace_path']
    mock_recon._loaded_modules = {}
    mock_recon.options = Options()
    mock_recon.options.init_option('nameserver', '8.8.8.8', True, 'default nameserver')
    mock_recon.options.init_option('threads', 10, True, 'number of threads')
    
    # Setup query method to work with real database
    def mock_query(query, include_header=False, values=()):
        conn = sqlite3.connect(setup['db_path'])
        cursor = conn.cursor()
        cursor.execute(query, values)
        
        if query.strip().upper().startswith('SELECT'):
            rows = cursor.fetchall()
            if include_header:
                columns = [desc[0] for desc in cursor.description]
                result = [columns] + list(rows)
            else:
                result = list(rows)
        else:
            conn.commit()
            result = []
        
        conn.close()
        return result
    
    mock_recon.query = mock_query
    
    def mock_get_tables():
        conn = sqlite3.connect(setup['db_path'])
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tables
    
    mock_recon.get_tables = mock_get_tables
    mock_recon._get_workspaces = MagicMock(return_value=[setup['workspace_name']])
    
    # Create mock tasks
    mock_tasks = MagicMock()
    mock_tasks.get_tasks.return_value = []
    mock_tasks.get_ids.return_value = []
    
    # Mock Redis and RQ
    mock_redis = MagicMock()
    mock_queue = MagicMock()
    
    # Patch the web module globals
    with patch.dict('sys.modules', {'redis': MagicMock(), 'rq': MagicMock()}):
        with patch('recon.core.web.recon', mock_recon), \
             patch('recon.core.web.tasks', mock_tasks), \
             patch('recon.core.web.Redis') as redis_patch, \
             patch('recon.core.web.rq.Queue') as queue_patch, \
             patch('recon.core.web.api.recon', mock_recon), \
             patch('recon.core.web.api.tasks', mock_tasks):
            
            redis_patch.from_url.return_value = mock_redis
            queue_patch.return_value = mock_queue
            
            # Import and create app after patching
            from flask import Flask
            from flasgger import Swagger
            from recon.core.web.api import resources
            
            app = Flask(__name__, static_url_path='')
            app.config['TESTING'] = True
            app.config['DEBUG'] = False
            app.config['SECRET_KEY'] = 'test-secret-key'
            app.config['JSON_SORT_KEYS'] = False
            app.config['WORKSPACE'] = setup['workspace_name']
            app.config['REDIS_URL'] = 'redis://'
            
            app.redis = mock_redis
            app.task_queue = mock_queue
            
            app.register_blueprint(resources)
            
            with app.test_client() as client:
                # Store additional context
                client._mock_recon = mock_recon
                client._mock_tasks = mock_tasks
                client._mock_queue = mock_queue
                client._setup = setup
                yield client
    
    # Restore original state
    Framework.home_path = original_state['home_path']
    Framework.mod_path = original_state['mod_path']
    Framework.data_path = original_state['data_path']
    Framework.spaces_path = original_state['spaces_path']
    Framework.workspace = original_state['workspace']
    Framework._loaded_modules = original_state['_loaded_modules']
    Framework._global_options = original_state['_global_options']


# =============================================================================
# WORKSPACE ENDPOINT TESTS
# =============================================================================

@pytest.mark.api
class TestWorkspaceAPI:
    """Tests for /api/workspaces/ endpoints."""
    
    def test_get_workspaces_list(self, flask_client):
        """Test GET /api/workspaces/ returns list of workspaces."""
        response = flask_client.get('/api/workspaces/')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'workspaces' in data
        assert isinstance(data['workspaces'], list)
        assert 'test_workspace' in data['workspaces']
    
    def test_get_workspace_info(self, flask_client):
        """Test GET /api/workspaces/<name> returns workspace info."""
        response = flask_client.get('/api/workspaces/test_workspace')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['name'] == 'test_workspace'
        assert data['status'] == 'active'
        assert 'options' in data
    
    def test_get_nonexistent_workspace_returns_404(self, flask_client):
        """Test GET /api/workspaces/<name> returns 404 for unknown workspace."""
        response = flask_client.get('/api/workspaces/nonexistent')
        assert response.status_code == 404
    
    def test_patch_workspace_activate(self, flask_client):
        """Test PATCH /api/workspaces/<name> can activate workspace."""
        # Add another workspace
        flask_client._mock_recon._get_workspaces.return_value = ['test_workspace', 'other_workspace']
        
        response = flask_client.patch(
            '/api/workspaces/test_workspace',
            data=json.dumps({'status': 'active'}),
            content_type='application/json'
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['name'] == 'test_workspace'


# =============================================================================
# MODULE ENDPOINT TESTS
# =============================================================================

@pytest.mark.api
class TestModuleAPI:
    """Tests for /api/modules/ endpoints."""
    
    def test_get_modules_list_empty(self, flask_client):
        """Test GET /api/modules/ returns empty list when no modules loaded."""
        response = flask_client.get('/api/modules/')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'modules' in data
        assert data['modules'] == []
    
    def test_get_modules_list_with_modules(self, flask_client):
        """Test GET /api/modules/ returns module list when modules are loaded."""
        # Add mock modules
        mock_module = MagicMock()
        mock_module.meta = {'name': 'Test Module', 'description': 'A test'}
        mock_module.options = MagicMock()
        mock_module.options.serialize.return_value = []
        
        flask_client._mock_recon._loaded_modules = {
            'recon/test/test_module': mock_module,
            'recon/domains/find_domains': mock_module,
        }
        
        response = flask_client.get('/api/modules/')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'modules' in data
        assert len(data['modules']) == 2
        assert 'recon/domains/find_domains' in data['modules']
        assert 'recon/test/test_module' in data['modules']
    
    def test_get_module_info(self, flask_client):
        """Test GET /api/modules/<path> returns module info."""
        mock_module = MagicMock()
        mock_module.meta = {
            'name': 'Test Module',
            'author': 'Test Author',
            'version': '1.0',
            'description': 'A test module',
        }
        mock_options = MagicMock()
        mock_options.serialize.return_value = [
            {'name': 'SOURCE', 'value': 'default', 'required': True}
        ]
        mock_module.options = mock_options
        
        flask_client._mock_recon._loaded_modules = {
            'recon/test/test_module': mock_module
        }
        
        response = flask_client.get('/api/modules/recon/test/test_module')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['name'] == 'Test Module'
        assert data['author'] == 'Test Author'
        assert 'options' in data
    
    def test_get_nonexistent_module_returns_404(self, flask_client):
        """Test GET /api/modules/<path> returns 404 for unknown module."""
        flask_client._mock_recon._loaded_modules = {}
        
        response = flask_client.get('/api/modules/recon/nonexistent/module')
        assert response.status_code == 404
    
    def test_patch_module_options(self, flask_client):
        """Test PATCH /api/modules/<path> updates module options."""
        mock_module = MagicMock()
        mock_module.meta = {'name': 'Test Module'}
        mock_module._modulename = 'recon/test/test_module'
        mock_options = Options()
        mock_options.init_option('SOURCE', 'default', True, 'Source query')
        mock_module.options = mock_options
        mock_module._save_config = MagicMock()
        
        flask_client._mock_recon._loaded_modules = {
            'recon/test/test_module': mock_module
        }
        
        response = flask_client.patch(
            '/api/modules/recon/test/test_module',
            data=json.dumps({
                'options': [{'name': 'SOURCE', 'value': 'example.com'}]
            }),
            content_type='application/json'
        )
        assert response.status_code == 200


# Import Options for the test above
from recon.core.framework import Options


# =============================================================================
# TABLE ENDPOINT TESTS
# =============================================================================

@pytest.mark.api
class TestTableAPI:
    """Tests for /api/tables/ endpoints."""
    
    def test_get_tables_list(self, flask_client):
        """Test GET /api/tables/ returns list of tables."""
        response = flask_client.get('/api/tables/')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'tables' in data
        assert 'workspace' in data
        assert 'domains' in data['tables']
        assert 'hosts' in data['tables']
        assert 'contacts' in data['tables']
    
    def test_get_table_contents(self, flask_client):
        """Test GET /api/tables/<table> returns table data."""
        response = flask_client.get('/api/tables/domains')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'workspace' in data
        assert 'table' in data
        assert 'columns' in data
        assert 'rows' in data
        assert data['table'] == 'domains'
        assert len(data['rows']) >= 1
    
    def test_get_table_with_specific_columns(self, flask_client):
        """Test GET /api/tables/<table>?columns= filters columns."""
        response = flask_client.get('/api/tables/domains?columns=domain')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'rows' in data
        # Each row should only have the 'domain' key
        for row in data['rows']:
            assert 'domain' in row
    
    def test_get_nonexistent_table_returns_404(self, flask_client):
        """Test GET /api/tables/<table> returns 404 for unknown table."""
        response = flask_client.get('/api/tables/nonexistent_table')
        assert response.status_code == 404
    
    def test_get_table_csv_format(self, flask_client):
        """Test GET /api/tables/<table>?format=csv returns CSV."""
        response = flask_client.get('/api/tables/domains?format=csv')
        assert response.status_code == 200
        assert response.content_type == 'text/csv; charset=utf-8'
    
    def test_get_table_json_format(self, flask_client):
        """Test GET /api/tables/<table>?format=json returns JSON."""
        response = flask_client.get('/api/tables/domains?format=json')
        assert response.status_code == 200
        # JSON format returns a jsonified response
        data = json.loads(response.data)
        assert 'rows' in data
    
    def test_get_table_xml_format(self, flask_client):
        """Test GET /api/tables/<table>?format=xml returns XML."""
        response = flask_client.get('/api/tables/domains?format=xml')
        assert response.status_code == 200
        assert 'xml' in response.content_type
    
    def test_get_table_list_format(self, flask_client):
        """Test GET /api/tables/<table>?format=list returns plain text list."""
        response = flask_client.get('/api/tables/domains?format=list')
        assert response.status_code == 200
        assert response.content_type == 'text/plain; charset=utf-8'


# =============================================================================
# DASHBOARD ENDPOINT TESTS
# =============================================================================

@pytest.mark.api
class TestDashboardAPI:
    """Tests for /api/dashboard endpoint."""
    
    def test_get_dashboard(self, flask_client):
        """Test GET /api/dashboard returns summary info."""
        response = flask_client.get('/api/dashboard')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'workspace' in data
        assert 'records' in data
        assert 'activity' in data
        assert data['workspace'] == 'test_workspace'
    
    def test_dashboard_records_structure(self, flask_client):
        """Test dashboard records have correct structure."""
        response = flask_client.get('/api/dashboard')
        data = json.loads(response.data)
        
        # Records should be list of {name, count} objects
        for record in data['records']:
            assert 'name' in record
            assert 'count' in record
            assert isinstance(record['count'], int)
    
    def test_dashboard_activity_structure(self, flask_client):
        """Test dashboard activity has correct structure."""
        response = flask_client.get('/api/dashboard')
        data = json.loads(response.data)
        
        # Activity should be list of module run data
        if data['activity']:
            for activity in data['activity']:
                assert 'module' in activity
                assert 'runs' in activity


# =============================================================================
# TASK ENDPOINT TESTS
# =============================================================================

@pytest.mark.api
class TestTaskAPI:
    """Tests for /api/tasks/ endpoints."""
    
    def test_get_tasks_list_empty(self, flask_client):
        """Test GET /api/tasks/ returns empty list when no tasks."""
        flask_client._mock_tasks.get_tasks.return_value = []
        
        response = flask_client.get('/api/tasks/')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'tasks' in data
        assert data['tasks'] == []
    
    def test_get_tasks_list_with_tasks(self, flask_client):
        """Test GET /api/tasks/ returns task list when tasks exist."""
        flask_client._mock_tasks.get_tasks.return_value = [
            {'id': 'task-123', 'status': 'completed', 'result': None},
            {'id': 'task-456', 'status': 'running', 'result': None},
        ]
        
        response = flask_client.get('/api/tasks/')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'tasks' in data
        assert len(data['tasks']) == 2
    
    def test_post_task_creates_job(self, flask_client):
        """Test POST /api/tasks/ creates a background job."""
        # Setup mock module
        mock_module = MagicMock()
        flask_client._mock_recon._loaded_modules = {
            'recon/test/module': mock_module
        }
        
        # Setup mock job
        mock_job = MagicMock()
        mock_job.get_id.return_value = 'new-task-id'
        mock_job.get_status.return_value = 'queued'
        flask_client._mock_queue.enqueue.return_value = mock_job
        
        response = flask_client.post(
            '/api/tasks/',
            data=json.dumps({'path': 'recon/test/module'}),
            content_type='application/json'
        )
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert 'task' in data
        assert data['task'] == 'new-task-id'
    
    def test_post_task_invalid_module_returns_404(self, flask_client):
        """Test POST /api/tasks/ with invalid module returns 404."""
        flask_client._mock_recon._loaded_modules = {}
        
        response = flask_client.post(
            '/api/tasks/',
            data=json.dumps({'path': 'recon/nonexistent/module'}),
            content_type='application/json'
        )
        assert response.status_code == 404
    
    def test_post_task_no_path_returns_404(self, flask_client):
        """Test POST /api/tasks/ without path returns 404."""
        response = flask_client.post(
            '/api/tasks/',
            data=json.dumps({}),
            content_type='application/json'
        )
        assert response.status_code == 404
    
    def test_get_task_by_id(self, flask_client):
        """Test GET /api/tasks/<tid> returns task info."""
        flask_client._mock_tasks.get_ids.return_value = ['task-123']
        flask_client._mock_tasks.get_task.return_value = {
            'id': 'task-123',
            'status': 'completed',
            'result': {'records': 5}
        }
        
        response = flask_client.get('/api/tasks/task-123')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['id'] == 'task-123'
        assert data['status'] == 'completed'
    
    def test_get_task_nonexistent_returns_404(self, flask_client):
        """Test GET /api/tasks/<tid> returns 404 for unknown task."""
        flask_client._mock_tasks.get_ids.return_value = []
        
        response = flask_client.get('/api/tasks/nonexistent-task')
        assert response.status_code == 404
    
    def test_get_task_live_status(self, flask_client):
        """Test GET /api/tasks/<tid>?live= queries Redis."""
        flask_client._mock_tasks.get_ids.return_value = ['task-123']
        
        mock_job = MagicMock()
        mock_job.get_status.return_value = 'finished'
        mock_job.result = {'records': 10}
        flask_client._mock_queue.fetch_job.return_value = mock_job
        
        response = flask_client.get('/api/tasks/task-123?live=1')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['status'] == 'finished'


# =============================================================================
# EXPORT ENDPOINT TESTS
# =============================================================================

@pytest.mark.api
class TestExportAPI:
    """Tests for /api/exports endpoint."""
    
    def test_get_exports_list(self, flask_client):
        """Test GET /api/exports returns list of export formats."""
        response = flask_client.get('/api/exports')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'exports' in data
        assert 'json' in data['exports']
        assert 'csv' in data['exports']
        assert 'xml' in data['exports']
        assert 'list' in data['exports']


# =============================================================================
# REPORT ENDPOINT TESTS
# =============================================================================

@pytest.mark.api
class TestReportAPI:
    """Tests for /api/reports/ endpoints."""
    
    def test_get_reports_list(self, flask_client):
        """Test GET /api/reports/ returns list of report types."""
        response = flask_client.get('/api/reports/')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'reports' in data
        assert isinstance(data['reports'], list)
    
    def test_get_nonexistent_report_returns_404(self, flask_client):
        """Test GET /api/reports/<report> returns 404 for unknown report."""
        response = flask_client.get('/api/reports/nonexistent_report')
        assert response.status_code == 404


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================

@pytest.mark.api
class TestAPIErrorHandling:
    """Tests for API error handling."""
    
    def test_invalid_json_body(self, flask_client):
        """Test POST with invalid JSON returns error."""
        response = flask_client.post(
            '/api/tasks/',
            data='not valid json',
            content_type='application/json'
        )
        # Should return 400 or 500 depending on Flask version
        assert response.status_code in [400, 415, 500]
    
    def test_missing_content_type(self, flask_client):
        """Test POST without content-type header."""
        flask_client._mock_recon._loaded_modules = {
            'recon/test/module': MagicMock()
        }
        
        response = flask_client.post(
            '/api/tasks/',
            data='{"path": "recon/test/module"}'
        )
        # Without proper content-type, request.json will be None
        assert response.status_code in [404, 415]


# =============================================================================
# CONTENT TYPE TESTS
# =============================================================================

@pytest.mark.api
class TestAPIContentTypes:
    """Tests for API content type handling."""
    
    def test_json_response_content_type(self, flask_client):
        """Test JSON endpoints return proper content type."""
        response = flask_client.get('/api/workspaces/')
        assert 'application/json' in response.content_type
    
    def test_csv_response_content_type(self, flask_client):
        """Test CSV export returns proper content type."""
        response = flask_client.get('/api/tables/domains?format=csv')
        assert 'text/csv' in response.content_type
    
    def test_xml_response_content_type(self, flask_client):
        """Test XML export returns proper content type."""
        response = flask_client.get('/api/tables/domains?format=xml')
        assert 'xml' in response.content_type


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

@pytest.mark.api
class TestAPIIntegration:
    """Integration tests for multi-endpoint workflows."""
    
    def test_workflow_list_tables_then_query(self, flask_client):
        """Test workflow: list tables, then query specific table."""
        # List tables
        response = flask_client.get('/api/tables/')
        assert response.status_code == 200
        data = json.loads(response.data)
        
        # Get first table's contents
        if data['tables']:
            table_name = data['tables'][0]
            response = flask_client.get(f'/api/tables/{table_name}')
            assert response.status_code == 200
    
    def test_workflow_dashboard_overview(self, flask_client):
        """Test workflow: get dashboard for overview."""
        response = flask_client.get('/api/dashboard')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        
        # Verify we can query each table from records
        for record in data['records'][:3]:  # Check first 3
            table_name = record['name']
            response = flask_client.get(f'/api/tables/{table_name}')
            assert response.status_code == 200
