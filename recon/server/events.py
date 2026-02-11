"""
Event publisher for sending events to clients during module execution
"""
import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union

from recon.shared.constants import EventType, Queues
from recon.shared.schemas import RPCEvent

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Publishes events to a client during RPC request processing.
    Used to stream output, progress, and input requests to the client.
    """
    
    def __init__(
        self, 
        client_id: str, 
        request_id: str, 
        publish_func: Callable[[str, str], Union[None, Coroutine]],
        loop: asyncio.AbstractEventLoop = None
    ):
        """
        Args:
            client_id: The client's unique ID for routing
            request_id: The current request ID
            publish_func: Function to publish message to queue (queue_name, message_body)
                         Can be sync or async
            loop: Event loop for scheduling async publishes (required if publish_func is async)
        """
        self.client_id = client_id
        self.request_id = request_id
        self._publish_func = publish_func
        self._loop = loop
    
    def _emit(self, event_type: str, data: Dict[str, Any]):
        """Emit an event to the client"""
        event = RPCEvent(
            id=self.request_id,
            type=event_type,
            data=data
        )
        queue = Queues.events(self.client_id)
        message = event.model_dump_json()
        
        logger.debug(f"Emitting event {event_type} to queue {queue}")
        
        try:
            result = self._publish_func(queue, message)
            # If the publish function returns a coroutine, schedule it
            if asyncio.iscoroutine(result):
                logger.debug(f"Got coroutine from publish_func, loop={self._loop}, running={self._loop.is_running() if self._loop else 'N/A'}")
                if self._loop and self._loop.is_running():
                    # Schedule the coroutine on the event loop
                    future = asyncio.run_coroutine_threadsafe(result, self._loop)
                    try:
                        # Wait for publish to complete (with timeout)
                        # Note: We don't hold the lock during this wait to avoid
                        # blocking other threads that may want to publish events
                        future.result(timeout=5.0)
                        logger.debug(f"Event {event_type} published successfully")
                    except Exception as e:
                        logger.error(f"Failed to publish event: {type(e).__name__}: {e}")
                else:
                    # No running loop, try to run directly
                    try:
                        asyncio.get_event_loop().run_until_complete(result)
                    except Exception as e:
                        logger.error(f"Failed to publish event (no loop): {type(e).__name__}: {e}")
        except Exception as e:
            logger.error(f"Exception in _emit: {type(e).__name__}: {e}")
    
    # Output methods - these mirror the Framework output methods
    def output(self, message: str, level: str = 'info'):
        """Normal output message"""
        self._emit(EventType.OUTPUT, {'message': message, 'level': level})
    
    def alert(self, message: str):
        """Important/success message"""
        self._emit(EventType.ALERT, {'message': message})
    
    def error(self, message: str):
        """Error message"""
        self._emit(EventType.ERROR, {'message': message})
    
    def verbose(self, message: str):
        """Verbose output"""
        self._emit(EventType.VERBOSE, {'message': message})
    
    def debug(self, message: str):
        """Debug output"""
        self._emit(EventType.DEBUG, {'message': message})
    
    def table(self, rows: List[List[Any]], header: List[str] = None, title: str = None):
        """Tabular data"""
        self._emit(EventType.TABLE, {
            'rows': rows,
            'header': header or [],
            'title': title
        })
    
    def heading(self, text: str, level: int = 0):
        """Section heading"""
        self._emit(EventType.HEADING, {'text': text, 'level': level})
    
    def progress(self, current: int, total: int, message: str = None):
        """Progress update"""
        self._emit(EventType.PROGRESS, {
            'current': current,
            'total': total,
            'message': message
        })
    
    def input_required(self, input_id: str, prompt: str = ''):
        """Request input from client"""
        self._emit(EventType.INPUT_REQUIRED, {
            'input_id': input_id,
            'prompt': prompt
        })
    
    def file_required(self, file_id: str, filepath: str):
        """Request file content from client"""
        self._emit(EventType.FILE_REQUIRED, {
            'file_id': file_id,
            'filepath': filepath
        })
    
    def file_output(self, filename: str, content: str, encoding: str = 'utf-8', binary: bool = False):
        """Send file content to client for local writing"""
        self._emit(EventType.FILE_OUTPUT, {
            'filename': filename,
            'content': content,
            'encoding': encoding,
            'binary': binary
        })
    
    def exception(self, exc_type: str, message: str, traceback: str = None):
        """Exception information"""
        self._emit(EventType.EXCEPTION, {
            'type': exc_type,
            'message': message,
            'traceback': traceback
        })


class NullEventPublisher(EventPublisher):
    """A no-op event publisher for testing or when no client is connected"""
    
    def __init__(self):
        self.client_id = 'null'
        self.request_id = 'null'
    
    def _emit(self, event_type: str, data: Dict[str, Any]):
        """Do nothing"""
        pass
