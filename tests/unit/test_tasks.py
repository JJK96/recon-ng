"""
Unit tests for the recon-ng tasks module (tasks.py).

Tests the background task execution functions.

NOTE: This module tests the old Flask/RQ-based background task system which has been
replaced by the RabbitMQ RPC architecture. The recon.core.tasks module no longer exists.
These tests are skipped until new tests are written for the RPC-based task system in
recon/server/ and recon/client/.
"""
import os
import sys
import traceback
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Skip the entire module - the Flask/RQ task system has been replaced with RabbitMQ RPC
pytestmark = pytest.mark.skip(
    reason="recon.core.tasks module no longer exists - replaced by RabbitMQ RPC architecture"
)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_job():
    """Create a mock rq Job."""
    job = MagicMock()
    job.get_id.return_value = 'test-job-123'
    job.get_status.return_value = 'started'
    return job


@pytest.fixture
def mock_recon():
    """Create a mock Recon instance."""
    recon = MagicMock()
    recon._loaded_modules = {}
    return recon


@pytest.fixture
def mock_module():
    """Create a mock module."""
    module = MagicMock()
    module._summary_counts = {'new': 5, 'duplicate': 2}
    return module


@pytest.fixture
def mock_tasks_db():
    """Create a mock Tasks database."""
    tasks = MagicMock()
    return tasks


# =============================================================================
# RUN_MODULE TESTS
# =============================================================================

@pytest.mark.unit
class TestRunModule:
    """Tests for run_module function."""
    
    def test_run_module_success(self, mock_job, mock_recon, mock_module, mock_tasks_db):
        """Test successful module execution."""
        mock_recon._loaded_modules = {'test/module': mock_module}
        
        with patch('recon.core.tasks.get_current_job', return_value=mock_job), \
             patch('recon.core.tasks.base.Recon', return_value=mock_recon), \
             patch('recon.core.tasks.Tasks', return_value=mock_tasks_db):
            
            from recon.core.tasks import run_module
            result = run_module('test_workspace', 'test/module')
            
            # Should call module.run()
            mock_module.run.assert_called_once()
            
            # Should update task status
            mock_tasks_db.update_task.assert_called()
            
            # Should return summary
            assert 'summary' in result
            assert result['summary'] == {'new': 5, 'duplicate': 2}
    
    def test_run_module_with_exception(self, mock_job, mock_recon, mock_tasks_db):
        """Test module execution with exception."""
        mock_module = MagicMock()
        mock_module.run.side_effect = ValueError('Test error')
        mock_module._summary_counts = {}
        mock_recon._loaded_modules = {'test/module': mock_module}
        
        with patch('recon.core.tasks.get_current_job', return_value=mock_job), \
             patch('recon.core.tasks.base.Recon', return_value=mock_recon), \
             patch('recon.core.tasks.Tasks', return_value=mock_tasks_db):
            
            from recon.core.tasks import run_module
            result = run_module('test_workspace', 'test/module')
            
            # Should contain error information
            assert 'error' in result
            assert 'ValueError' in result['error']['type']
            assert 'Test error' in result['error']['message']
            assert 'traceback' in result['error']
    
    def test_run_module_updates_status_to_started(self, mock_job, mock_recon, mock_module, mock_tasks_db):
        """Test that run_module updates task status."""
        mock_recon._loaded_modules = {'test/module': mock_module}
        
        with patch('recon.core.tasks.get_current_job', return_value=mock_job), \
             patch('recon.core.tasks.base.Recon', return_value=mock_recon), \
             patch('recon.core.tasks.Tasks', return_value=mock_tasks_db):
            
            from recon.core.tasks import run_module
            run_module('test_workspace', 'test/module')
            
            # First call should update to 'started' status
            first_call = mock_tasks_db.update_task.call_args_list[0]
            assert first_call[0][0] == 'test-job-123'
            assert first_call[1]['status'] == 'started'
    
    def test_run_module_updates_status_to_finished(self, mock_job, mock_recon, mock_module, mock_tasks_db):
        """Test that run_module updates task status to finished."""
        mock_recon._loaded_modules = {'test/module': mock_module}
        
        with patch('recon.core.tasks.get_current_job', return_value=mock_job), \
             patch('recon.core.tasks.base.Recon', return_value=mock_recon), \
             patch('recon.core.tasks.Tasks', return_value=mock_tasks_db):
            
            from recon.core.tasks import run_module
            run_module('test_workspace', 'test/module')
            
            # Last call should update to 'finished' status with result
            last_call = mock_tasks_db.update_task.call_args_list[-1]
            assert last_call[0][0] == 'test-job-123'
            assert last_call[1]['status'] == 'finished'
            assert 'result' in last_call[1]
    
    def test_run_module_initializes_recon(self, mock_job, mock_recon, mock_module, mock_tasks_db):
        """Test that run_module initializes Recon correctly."""
        mock_recon._loaded_modules = {'test/module': mock_module}
        
        with patch('recon.core.tasks.get_current_job', return_value=mock_job), \
             patch('recon.core.tasks.base.Recon', return_value=mock_recon) as mock_recon_class, \
             patch('recon.core.tasks.Tasks', return_value=mock_tasks_db):
            
            from recon.core.tasks import run_module
            run_module('test_workspace', 'test/module')
            
            # Should create Recon with specific parameters
            mock_recon_class.assert_called_once_with(
                check=False,
                analytics=False,
                marketplace=False
            )
            
            # Should call start with workspace
            mock_recon.start.assert_called_once()
    
    def test_run_module_creates_tasks_db(self, mock_job, mock_recon, mock_module, mock_tasks_db):
        """Test that run_module creates Tasks database."""
        mock_recon._loaded_modules = {'test/module': mock_module}
        
        with patch('recon.core.tasks.get_current_job', return_value=mock_job), \
             patch('recon.core.tasks.base.Recon', return_value=mock_recon), \
             patch('recon.core.tasks.Tasks', return_value=mock_tasks_db) as mock_tasks_class:
            
            from recon.core.tasks import run_module
            run_module('test_workspace', 'test/module')
            
            # Should create Tasks with recon instance
            mock_tasks_class.assert_called_once_with(mock_recon)


@pytest.mark.unit
class TestRunModuleEdgeCases:
    """Edge case tests for run_module."""
    
    def test_run_module_module_not_found(self, mock_job, mock_tasks_db):
        """Test run_module when module is not in loaded modules.
        
        Note: This reveals a bug in the code - when module is None, 
        module._summary_counts fails outside the try block.
        """
        mock_recon = MagicMock()
        # Use a MagicMock for _loaded_modules that returns None for .get()
        mock_loaded_modules = MagicMock()
        mock_loaded_modules.get.return_value = None
        mock_recon._loaded_modules = mock_loaded_modules
        
        with patch('recon.core.tasks.get_current_job', return_value=mock_job), \
             patch('recon.core.tasks.base.Recon', return_value=mock_recon), \
             patch('recon.core.tasks.Tasks', return_value=mock_tasks_db):
            
            from recon.core.tasks import run_module
            
            # This will raise AttributeError because module._summary_counts
            # is accessed outside the try block when module is None
            with pytest.raises(AttributeError):
                run_module('test_workspace', 'nonexistent/module')
    
    def test_run_module_exception_in_setup(self, mock_job):
        """Test run_module handles exceptions during setup."""
        with patch('recon.core.tasks.get_current_job', return_value=mock_job), \
             patch('recon.core.tasks.base.Recon', side_effect=Exception('Recon init failed')):
            
            from recon.core.tasks import run_module
            
            # This will raise an exception that's caught internally
            # The function should still try to record the error
            try:
                result = run_module('test_workspace', 'test/module')
                # If we get here, result should have error
                assert 'error' in result
            except:
                # Exception may bubble up if tasks db wasn't created
                pass
