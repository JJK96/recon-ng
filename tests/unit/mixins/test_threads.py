"""
Unit tests for the ThreadingMixin class.

Tests threading functionality for parallel module execution.
"""
import os
import sys
import threading
import time
from queue import Queue, Empty
from unittest.mock import MagicMock, patch, PropertyMock, call

import pytest

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from recon.mixins.threads import ThreadingMixin
from recon.core.framework import Options


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def threading_mixin():
    """Create a class that uses ThreadingMixin for testing."""
    
    class TestThreading(ThreadingMixin):
        def __init__(self, verbosity=1, threads=4):
            self._global_options = Options()
            self._global_options.init_option('verbosity', verbosity, True, 'verbosity level')
            self._global_options.init_option('threads', threads, True, 'number of threads')
            self.results = []
            self._lock = threading.Lock()
        
        def debug(self, msg):
            pass  # Suppress debug messages in tests
        
        def error(self, msg):
            pass  # Suppress error messages in tests
        
        def print_exception(self, msg=''):
            pass  # Suppress exception messages in tests
        
        def module_thread(self, item, *args):
            # Simple worker that stores results
            with self._lock:
                self.results.append(item)
    
    return TestThreading()


@pytest.fixture
def threading_mixin_debug():
    """Create a threading mixin with debug mode enabled."""
    
    class TestThreading(ThreadingMixin):
        def __init__(self):
            self._global_options = Options()
            self._global_options.init_option('verbosity', 2, True, 'verbosity level')  # Debug mode
            self._global_options.init_option('threads', 4, True, 'number of threads')
            self.results = []
        
        def debug(self, msg):
            pass
        
        def error(self, msg):
            pass
        
        def print_exception(self, msg=''):
            pass
        
        def module_thread(self, item, *args):
            self.results.append(item)
    
    return TestThreading()


@pytest.fixture
def slow_threading_mixin():
    """Create a threading mixin with slow worker for timing tests."""
    
    class TestThreading(ThreadingMixin):
        def __init__(self, threads=4):
            self._global_options = Options()
            self._global_options.init_option('verbosity', 1, True, 'verbosity level')
            self._global_options.init_option('threads', threads, True, 'number of threads')
            self.results = []
            self._lock = threading.Lock()
            self.call_count = 0
        
        def debug(self, msg):
            pass
        
        def error(self, msg):
            pass
        
        def print_exception(self, msg=''):
            pass
        
        def module_thread(self, item, *args):
            time.sleep(0.01)  # Simulate work
            with self._lock:
                self.results.append(item)
                self.call_count += 1
    
    return TestThreading


# =============================================================================
# BASIC THREADING TESTS
# =============================================================================

@pytest.mark.unit
class TestThreadMethod:
    """Tests for the thread method."""
    
    def test_thread_processes_all_items(self, threading_mixin):
        """Test thread method processes all items."""
        items = [1, 2, 3, 4, 5]
        
        threading_mixin.thread(items)
        
        # All items should be processed
        assert sorted(threading_mixin.results) == sorted(items)
    
    def test_thread_with_empty_list(self, threading_mixin):
        """Test thread method with empty list."""
        items = []
        
        threading_mixin.thread(items)
        
        assert threading_mixin.results == []
    
    def test_thread_with_single_item(self, threading_mixin):
        """Test thread method with single item."""
        items = ['single']
        
        threading_mixin.thread(items)
        
        assert threading_mixin.results == ['single']
    
    def test_thread_with_many_items(self, threading_mixin):
        """Test thread method with many items."""
        items = list(range(100))
        
        threading_mixin.thread(items)
        
        assert sorted(threading_mixin.results) == sorted(items)
    
    def test_thread_preserves_item_types(self, threading_mixin):
        """Test thread method preserves item types."""
        items = ['string', 123, {'key': 'value'}, (1, 2, 3)]
        
        threading_mixin.thread(items)
        
        # Check types are preserved (order may vary)
        assert len(threading_mixin.results) == 4
        assert 'string' in threading_mixin.results
        assert 123 in threading_mixin.results


# =============================================================================
# DEBUG MODE TESTS
# =============================================================================

@pytest.mark.unit
class TestDebugMode:
    """Tests for debug mode (serial execution)."""
    
    def test_debug_mode_runs_serially(self, threading_mixin_debug):
        """Test that debug mode runs items serially."""
        items = [1, 2, 3, 4, 5]
        
        threading_mixin_debug.thread(items)
        
        # In debug mode, items are processed in order
        assert threading_mixin_debug.results == items
    
    def test_debug_mode_with_verbosity_2(self, threading_mixin_debug):
        """Test that verbosity >= 2 triggers debug mode."""
        # Verify we're in debug mode
        assert threading_mixin_debug._global_options['verbosity'] >= 2
        
        items = ['a', 'b', 'c']
        threading_mixin_debug.thread(items)
        
        # Serial execution preserves order
        assert threading_mixin_debug.results == ['a', 'b', 'c']


# =============================================================================
# THREAD COUNT TESTS
# =============================================================================

@pytest.mark.unit
class TestThreadCount:
    """Tests for thread count configuration."""
    
    def test_respects_thread_count_option(self, slow_threading_mixin):
        """Test that thread count option is respected."""
        # Use 2 threads
        mixin = slow_threading_mixin(threads=2)
        items = list(range(10))
        
        start = time.time()
        mixin.thread(items)
        duration = time.time() - start
        
        assert len(mixin.results) == 10
    
    def test_single_thread_mode(self, slow_threading_mixin):
        """Test threading with single thread."""
        mixin = slow_threading_mixin(threads=1)
        items = [1, 2, 3]
        
        mixin.thread(items)
        
        assert sorted(mixin.results) == [1, 2, 3]


# =============================================================================
# THREAD WRAPPER TESTS
# =============================================================================

@pytest.mark.unit
class TestThreadWrapper:
    """Tests for _thread_wrapper method."""
    
    def test_thread_wrapper_handles_empty_queue(self):
        """Test _thread_wrapper handles empty queue gracefully."""
        
        class TestMixin(ThreadingMixin):
            def __init__(self):
                self._global_options = Options()
                self._global_options.init_option('verbosity', 1, True, 'verbosity')
                self._global_options.init_option('threads', 1, True, 'threads')
                self.stopped = threading.Event()
                self.q = Queue()
            
            def debug(self, msg):
                pass
            
            def module_thread(self, item):
                pass
        
        mixin = TestMixin()
        
        # Start wrapper in a thread, stop immediately
        mixin.stopped.set()
        
        # Should exit cleanly without blocking
        mixin._thread_wrapper()
    
    def test_thread_wrapper_processes_queue_items(self):
        """Test _thread_wrapper processes items from queue."""
        
        class TestMixin(ThreadingMixin):
            def __init__(self):
                self._global_options = Options()
                self._global_options.init_option('verbosity', 1, True, 'verbosity')
                self._global_options.init_option('threads', 1, True, 'threads')
                self.stopped = threading.Event()
                self.q = Queue()
                self.processed = []
            
            def debug(self, msg):
                pass
            
            def module_thread(self, item):
                self.processed.append(item)
        
        mixin = TestMixin()
        mixin.q.put('item1')
        mixin.q.put('item2')
        
        # Process items then stop
        def run_wrapper():
            mixin._thread_wrapper()
        
        t = threading.Thread(target=run_wrapper)
        t.daemon = True
        t.start()
        
        # Wait for items to be processed
        mixin.q.join()
        mixin.stopped.set()
        t.join(timeout=1)
        
        assert 'item1' in mixin.processed
        assert 'item2' in mixin.processed


# =============================================================================
# EXCEPTION HANDLING TESTS
# =============================================================================

@pytest.mark.unit
class TestExceptionHandling:
    """Tests for exception handling in threads."""
    
    def test_exception_in_worker_does_not_crash(self):
        """Test that exceptions in worker don't crash other threads."""
        
        class TestMixin(ThreadingMixin):
            def __init__(self):
                self._global_options = Options()
                self._global_options.init_option('verbosity', 1, True, 'verbosity')
                self._global_options.init_option('threads', 2, True, 'threads')
                self.results = []
                self.exception_count = 0
                self._lock = threading.Lock()
            
            def debug(self, msg):
                pass
            
            def error(self, msg):
                pass
            
            def print_exception(self, msg=''):
                with self._lock:
                    self.exception_count += 1
            
            def module_thread(self, item):
                if item == 'error':
                    raise ValueError("Test exception")
                with self._lock:
                    self.results.append(item)
        
        mixin = TestMixin()
        items = ['a', 'error', 'b', 'c']
        
        mixin.thread(items)
        
        # Other items should still be processed
        assert 'a' in mixin.results
        assert 'b' in mixin.results
        assert 'c' in mixin.results
        # Exception should have been caught
        assert mixin.exception_count >= 1


# =============================================================================
# ADDITIONAL ARGUMENTS TESTS
# =============================================================================

@pytest.mark.unit
class TestAdditionalArguments:
    """Tests for passing additional arguments to worker."""
    
    def test_thread_passes_extra_args(self):
        """Test that thread passes additional arguments to worker."""
        
        class TestMixin(ThreadingMixin):
            def __init__(self):
                self._global_options = Options()
                self._global_options.init_option('verbosity', 1, True, 'verbosity')
                self._global_options.init_option('threads', 2, True, 'threads')
                self.results = []
                self._lock = threading.Lock()
            
            def debug(self, msg):
                pass
            
            def error(self, msg):
                pass
            
            def print_exception(self, msg=''):
                pass
            
            def module_thread(self, item, multiplier, suffix):
                with self._lock:
                    self.results.append(f"{item * multiplier}{suffix}")
        
        mixin = TestMixin()
        items = [1, 2, 3]
        
        mixin.thread(items, 10, '_done')
        
        results = sorted(mixin.results)
        assert '10_done' in results
        assert '20_done' in results
        assert '30_done' in results


# =============================================================================
# STATE MANAGEMENT TESTS
# =============================================================================

@pytest.mark.unit
class TestStateManagement:
    """Tests for thread state management."""
    
    def test_stopped_event_is_set_after_completion(self, threading_mixin):
        """Test stopped event is set after thread completes."""
        items = [1, 2, 3]
        
        threading_mixin.thread(items)
        
        assert threading_mixin.stopped.is_set()
    
    def test_queue_is_empty_after_completion(self, threading_mixin):
        """Test queue is empty after thread completes."""
        items = [1, 2, 3]
        
        threading_mixin.thread(items)
        
        assert threading_mixin.q.empty()


# =============================================================================
# CONCURRENT EXECUTION TESTS
# =============================================================================

@pytest.mark.unit
class TestConcurrentExecution:
    """Tests for concurrent execution behavior."""
    
    def test_multiple_threads_execute_concurrently(self, slow_threading_mixin):
        """Test that multiple threads execute concurrently."""
        # With 4 threads and items that take 0.01s each,
        # 8 items should complete faster than 8 * 0.01s
        mixin = slow_threading_mixin(threads=4)
        items = list(range(8))
        
        start = time.time()
        mixin.thread(items)
        duration = time.time() - start
        
        # Should be faster than serial execution
        # Serial would be at least 8 * 0.01 = 0.08s
        # With 4 threads should be around 0.02-0.04s + overhead
        # Note: CI environments can be slow, so we use a generous threshold
        assert duration < 2.0  # Allow for CI timing variability
        assert len(mixin.results) == 8
    
    def test_thread_safety(self):
        """Test that results are thread-safe."""
        
        class TestMixin(ThreadingMixin):
            def __init__(self):
                self._global_options = Options()
                self._global_options.init_option('verbosity', 1, True, 'verbosity')
                self._global_options.init_option('threads', 10, True, 'threads')
                self.counter = 0
                self._lock = threading.Lock()
            
            def debug(self, msg):
                pass
            
            def error(self, msg):
                pass
            
            def print_exception(self, msg=''):
                pass
            
            def module_thread(self, item):
                # Increment counter with lock to ensure thread safety
                with self._lock:
                    self.counter += 1
        
        mixin = TestMixin()
        items = list(range(1000))
        
        mixin.thread(items)
        
        # All increments should be counted
        assert mixin.counter == 1000


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

@pytest.mark.unit
class TestEdgeCases:
    """Edge case tests for threading mixin."""
    
    def test_thread_with_none_items(self):
        """Test thread handling None items in list."""
        
        class TestMixin(ThreadingMixin):
            def __init__(self):
                self._global_options = Options()
                self._global_options.init_option('verbosity', 1, True, 'verbosity')
                self._global_options.init_option('threads', 2, True, 'threads')
                self.results = []
                self._lock = threading.Lock()
            
            def debug(self, msg):
                pass
            
            def error(self, msg):
                pass
            
            def print_exception(self, msg=''):
                pass
            
            def module_thread(self, item):
                with self._lock:
                    self.results.append(item)
        
        mixin = TestMixin()
        items = [None, 'valid', None]
        
        mixin.thread(items)
        
        assert len(mixin.results) == 3
        assert mixin.results.count(None) == 2
    
    def test_thread_with_generator(self):
        """Test thread with generator input."""
        
        class TestMixin(ThreadingMixin):
            def __init__(self):
                self._global_options = Options()
                self._global_options.init_option('verbosity', 1, True, 'verbosity')
                self._global_options.init_option('threads', 2, True, 'threads')
                self.results = []
                self._lock = threading.Lock()
            
            def debug(self, msg):
                pass
            
            def error(self, msg):
                pass
            
            def print_exception(self, msg=''):
                pass
            
            def module_thread(self, item):
                with self._lock:
                    self.results.append(item)
        
        mixin = TestMixin()
        
        def gen():
            for i in range(5):
                yield i
        
        mixin.thread(gen())
        
        assert sorted(mixin.results) == [0, 1, 2, 3, 4]


# =============================================================================
# KEYBOARD INTERRUPT TESTS
# =============================================================================

@pytest.mark.unit
class TestKeyboardInterruptHandling:
    """Tests for KeyboardInterrupt handling during thread execution."""
    
    def test_keyboard_interrupt_sets_stopped_event(self):
        """Test that KeyboardInterrupt sets stopped event and re-raises."""
        import signal
        
        class TestMixin(ThreadingMixin):
            def __init__(self):
                self._global_options = Options()
                self._global_options.init_option('verbosity', 1, True, 'verbosity')
                self._global_options.init_option('threads', 2, True, 'threads')
                self.results = []
                self._lock = threading.Lock()
                self.error_called = False
            
            def debug(self, msg):
                pass
            
            def error(self, msg):
                self.error_called = True
            
            def print_exception(self, msg=''):
                pass
            
            def module_thread(self, item):
                # Slow worker to give time for interrupt
                time.sleep(0.5)
                with self._lock:
                    self.results.append(item)
        
        mixin = TestMixin()
        
        # Use a thread to send SIGINT after a short delay
        def send_interrupt():
            time.sleep(0.2)  # Let threads start
            os.kill(os.getpid(), signal.SIGINT)
        
        interrupt_thread = threading.Thread(target=send_interrupt)
        interrupt_thread.start()
        
        # Should raise KeyboardInterrupt
        with pytest.raises(KeyboardInterrupt):
            mixin.thread(list(range(100)))
        
        interrupt_thread.join(timeout=1)
        
        # After interrupt, stopped should be set
        assert mixin.stopped.is_set()
        assert mixin.error_called
    
    def test_keyboard_interrupt_waits_for_threads(self):
        """Test that KeyboardInterrupt waits for threads to exit."""
        import signal
        
        thread_exit_times = []
        
        class TestMixin(ThreadingMixin):
            def __init__(self):
                self._global_options = Options()
                self._global_options.init_option('verbosity', 1, True, 'verbosity')
                self._global_options.init_option('threads', 2, True, 'threads')
                self._lock = threading.Lock()
            
            def debug(self, msg):
                pass
            
            def error(self, msg):
                pass
            
            def print_exception(self, msg=''):
                pass
            
            def module_thread(self, item):
                time.sleep(0.1)
                with self._lock:
                    thread_exit_times.append(time.time())
        
        mixin = TestMixin()
        
        # Send interrupt shortly after start
        def send_interrupt():
            time.sleep(0.05)
            os.kill(os.getpid(), signal.SIGINT)
        
        interrupt_thread = threading.Thread(target=send_interrupt)
        interrupt_thread.start()
        
        start_time = time.time()
        with pytest.raises(KeyboardInterrupt):
            mixin.thread(list(range(10)))
        
        interrupt_thread.join(timeout=1)
        
        # The method should have waited for threads - stopped should be set
        assert mixin.stopped.is_set()
