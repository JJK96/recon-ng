"""
Unit tests for the recon-ng web database module (web/db.py).

Tests the Tasks class which manages background task persistence.

NOTE: The web module has been rewritten from Flask to Sanic with RabbitMQ RPC.
The Tasks database class (recon.core.web.db.Tasks) no longer exists. Task tracking
is now handled by the TaskTracker class in recon/core/web/__init__.py which uses
in-memory storage. These tests are skipped until new tests are written for the
new task tracking system.
"""
import os
import sys
import json
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Skip the entire module - Flask/SQLite task DB has been replaced
pytestmark = pytest.mark.skip(
    reason="recon.core.web.db.Tasks no longer exists - replaced by in-memory TaskTracker"
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_recon(tmp_path):
    """Create a mock recon instance with workspace path."""
    mock = MagicMock()
    mock.workspace = str(tmp_path / "workspace")
    os.makedirs(mock.workspace)
    
    # Setup the _query method to actually use SQLite
    def _query(path, query, values=None, include_header=False):
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        if values:
            cursor.execute(query, values)
        else:
            cursor.execute(query)
        
        if query.strip().upper().startswith('SELECT'):
            rows = cursor.fetchall()
            if include_header:
                columns = [desc[0] for desc in cursor.description]
                rows.insert(0, columns)
            conn.close()
            return rows
        else:
            conn.commit()
            conn.close()
            return None
    
    mock._query = _query
    return mock


@pytest.fixture
def tasks_db(mock_recon):
    """Create a Tasks instance with a real database."""
    from recon.core.web.db import Tasks
    return Tasks(mock_recon)


# =============================================================================
# TASKS CLASS TESTS
# =============================================================================

@pytest.mark.unit
class TestTasksInit:
    """Tests for Tasks class initialization."""
    
    def test_tasks_creates_db_if_not_exists(self, mock_recon):
        """Test Tasks creates database if it doesn't exist."""
        from recon.core.web.db import Tasks
        
        db_path = os.path.join(mock_recon.workspace, 'tasks.db')
        assert not os.path.exists(db_path)
        
        tasks = Tasks(mock_recon)
        
        assert os.path.exists(db_path)
    
    def test_tasks_uses_existing_db(self, mock_recon):
        """Test Tasks uses existing database."""
        from recon.core.web.db import Tasks
        
        # Create db first
        db_path = os.path.join(mock_recon.workspace, 'tasks.db')
        conn = sqlite3.connect(db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT,
                PRIMARY KEY (id)
            )
        ''')
        conn.execute("INSERT INTO tasks (id, status) VALUES ('existing', 'done')")
        conn.commit()
        conn.close()
        
        tasks = Tasks(mock_recon)
        
        # Should find the existing task
        task_ids = [x[0] for x in tasks.query('SELECT id FROM tasks')]
        assert 'existing' in task_ids
    
    def test_tasks_path_set_correctly(self, mock_recon):
        """Test tasks.path is set correctly."""
        from recon.core.web.db import Tasks
        
        tasks = Tasks(mock_recon)
        
        expected_path = os.path.join(mock_recon.workspace, 'tasks.db')
        assert tasks.path == expected_path


@pytest.mark.unit
class TestTasksQuery:
    """Tests for Tasks.query method."""
    
    def test_query_delegates_to_recon(self, tasks_db, mock_recon):
        """Test query method calls recon._query."""
        tasks_db.query('SELECT 1')
        
        # The mock_recon._query should have been called
        assert tasks_db.recon == mock_recon


@pytest.mark.unit
class TestTasksCRUD:
    """Tests for Tasks CRUD operations."""
    
    def test_add_task_simple(self, tasks_db):
        """Test adding a simple task."""
        tasks_db.add_task('task1', 'pending')
        
        result = tasks_db.query('SELECT id, status FROM tasks WHERE id=?', values=('task1',))
        assert len(result) == 1
        assert result[0][0] == 'task1'
        assert result[0][1] == 'pending'
    
    def test_add_task_with_result(self, tasks_db):
        """Test adding a task with result."""
        result_data = {'key': 'value', 'count': 42}
        tasks_db.add_task('task2', 'finished', result=result_data)
        
        result = tasks_db.query('SELECT result FROM tasks WHERE id=?', values=('task2',))
        assert len(result) == 1
        # Result should be JSON encoded
        stored_result = json.loads(result[0][0])
        assert stored_result == result_data
    
    def test_get_task(self, tasks_db):
        """Test getting a single task."""
        tasks_db.add_task('task3', 'running')
        
        task = tasks_db.get_task('task3')
        
        assert task['id'] == 'task3'
        assert task['status'] == 'running'
        assert task['result'] is None
    
    def test_get_task_with_result(self, tasks_db):
        """Test getting a task with result."""
        result_data = {'data': [1, 2, 3]}
        tasks_db.add_task('task4', 'finished', result=result_data)
        
        task = tasks_db.get_task('task4')
        
        assert task['id'] == 'task4'
        assert task['status'] == 'finished'
        assert task['result'] == result_data
    
    def test_get_tasks(self, tasks_db):
        """Test getting all tasks."""
        tasks_db.add_task('task5', 'pending')
        tasks_db.add_task('task6', 'running')
        tasks_db.add_task('task7', 'finished')
        
        tasks = tasks_db.get_tasks()
        
        assert len(tasks) == 3
        task_ids = [t['id'] for t in tasks]
        assert 'task5' in task_ids
        assert 'task6' in task_ids
        assert 'task7' in task_ids
    
    def test_get_ids(self, tasks_db):
        """Test getting all task IDs."""
        tasks_db.add_task('task8', 'pending')
        tasks_db.add_task('task9', 'running')
        
        ids = tasks_db.get_ids()
        
        assert 'task8' in ids
        assert 'task9' in ids
    
    def test_update_task_status(self, tasks_db):
        """Test updating task status."""
        tasks_db.add_task('task10', 'pending')
        
        tasks_db.update_task('task10', status='finished')
        
        task = tasks_db.get_task('task10')
        assert task['status'] == 'finished'
    
    def test_update_task_result(self, tasks_db):
        """Test updating task result."""
        tasks_db.add_task('task11', 'running')
        
        result_data = {'summary': 'done', 'count': 100}
        tasks_db.update_task('task11', result=result_data)
        
        task = tasks_db.get_task('task11')
        assert task['result'] == result_data
    
    def test_update_task_multiple_fields(self, tasks_db):
        """Test updating multiple task fields."""
        tasks_db.add_task('task12', 'pending')
        
        result_data = {'completed': True}
        tasks_db.update_task('task12', status='finished', result=result_data)
        
        task = tasks_db.get_task('task12')
        assert task['status'] == 'finished'
        assert task['result'] == result_data


@pytest.mark.unit
class TestTasksEdgeCases:
    """Edge case tests for Tasks."""
    
    def test_get_tasks_empty_db(self, tasks_db):
        """Test get_tasks on empty database."""
        tasks = tasks_db.get_tasks()
        assert tasks == []
    
    def test_get_ids_empty_db(self, tasks_db):
        """Test get_ids on empty database."""
        ids = tasks_db.get_ids()
        assert ids == []
    
    def test_add_task_none_result(self, tasks_db):
        """Test adding task with None result."""
        tasks_db.add_task('task_none', 'pending', result=None)
        
        task = tasks_db.get_task('task_none')
        assert task['result'] is None
    
    def test_update_task_empty_kwargs_raises_error(self, tasks_db):
        """Test update_task with no fields raises SQLite error.
        
        Note: This is a known edge case in the code - calling update_task
        without any fields to update produces an invalid SQL query.
        """
        tasks_db.add_task('task_empty', 'pending')
        
        # This raises an error due to invalid SQL (UPDATE tasks SET WHERE id=?)
        import sqlite3
        with pytest.raises(sqlite3.OperationalError):
            tasks_db.update_task('task_empty')
    
    def test_update_task_with_none_value(self, tasks_db):
        """Test update_task skips None values."""
        tasks_db.add_task('task_skip', 'pending')
        
        # Should only update status, not result (None)
        tasks_db.update_task('task_skip', status='finished', result=None)
        
        task = tasks_db.get_task('task_skip')
        assert task['status'] == 'finished'
    
    def test_complex_result_json(self, tasks_db):
        """Test handling complex JSON result."""
        complex_result = {
            'nested': {
                'array': [1, 2, {'key': 'value'}],
                'string': 'test',
                'number': 123.456,
                'bool': True,
                'null': None,
            },
            'list': ['a', 'b', 'c'],
        }
        
        tasks_db.add_task('complex', 'finished', result=complex_result)
        
        task = tasks_db.get_task('complex')
        assert task['result'] == complex_result
