"""
Request context for processing RPC requests
"""
import asyncio
import uuid
import logging
import threading
from typing import Any, Callable, Dict, Optional
from dataclasses import dataclass, field
from threading import Event as ThreadingEvent

from recon.shared.constants import DEFAULT_INPUT_TIMEOUT
from recon.server.events import EventPublisher

logger = logging.getLogger(__name__)


class InputTimeoutError(Exception):
    """Raised when waiting for client input times out"""
    pass


class RequestContext:
    """
    Context for processing a single RPC request.
    Provides event publishing and input handling.
    """
    
    def __init__(
        self,
        request_id: str,
        client_id: str,
        workspace: str,
        global_options: Dict[str, Any],
        publish_func: Callable[[str, str], None],
        loop: asyncio.AbstractEventLoop = None,
        input_timeout: float = DEFAULT_INPUT_TIMEOUT
    ):
        self.request_id = request_id
        self.client_id = client_id
        self.workspace = workspace
        self.global_options = global_options
        self.input_timeout = input_timeout
        
        # Create event publisher with event loop for async publishing
        self.events = EventPublisher(client_id, request_id, publish_func, loop=loop)
        
        # Input handling - maps input_id to (Event, value)
        # Protected by lock for thread-safe access from async and executor threads
        self._pending_inputs: Dict[str, Dict] = {}
        self._inputs_lock = threading.Lock()
        
        # File request handling - maps file_id to (Event, content, error)
        # Protected by lock for thread-safe access
        self._pending_files: Dict[str, Dict] = {}
        self._files_lock = threading.Lock()
    
    def has_pending_input(self, input_id: str) -> bool:
        """Check if this context is waiting for the given input_id"""
        with self._inputs_lock:
            return input_id in self._pending_inputs
    
    def request_input(self, prompt: str = '') -> str:
        """
        Request input from client and wait for response.
        Sends INPUT_REQUIRED event and blocks until client responds.
        """
        input_id = str(uuid.uuid4())
        response_event = ThreadingEvent()
        
        with self._inputs_lock:
            self._pending_inputs[input_id] = {'event': response_event, 'value': None}
        
        # Send event to client requesting input
        self.events.input_required(input_id, prompt)
        
        try:
            if not response_event.wait(timeout=self.input_timeout):
                raise InputTimeoutError(f"No input response within {self.input_timeout}s")
            with self._inputs_lock:
                return self._pending_inputs[input_id]['value']
        finally:
            with self._inputs_lock:
                self._pending_inputs.pop(input_id, None)
    
    def provide_input(self, input_id: str, value: str):
        """
        Provide input value from client.
        Called when client sends input/response.
        """
        with self._inputs_lock:
            if input_id in self._pending_inputs:
                self._pending_inputs[input_id]['value'] = value
                self._pending_inputs[input_id]['event'].set()
            else:
                logger.warning(f"Received input for unknown input_id: {input_id}")
    
    def has_pending_file(self, file_id: str) -> bool:
        """Check if this context is waiting for the given file_id"""
        with self._files_lock:
            return file_id in self._pending_files
    
    def request_file(self, filepath: str, timeout: float = None) -> Optional[str]:
        """
        Request file content from client and wait for response.
        Sends FILE_REQUIRED event and blocks until client responds.
        
        Returns file content as string, or None if file not found on client.
        """
        file_id = str(uuid.uuid4())
        response_event = ThreadingEvent()
        
        with self._files_lock:
            self._pending_files[file_id] = {'event': response_event, 'content': None, 'error': None}
        
        # Send event to client requesting file
        self.events.file_required(file_id, filepath)
        
        timeout = timeout or self.input_timeout
        try:
            if not response_event.wait(timeout=timeout):
                raise InputTimeoutError(f"No file response within {timeout}s")
            with self._files_lock:
                result = self._pending_files[file_id]
                if result.get('error'):
                    return None  # File not found or error on client
                return result['content']
        finally:
            with self._files_lock:
                self._pending_files.pop(file_id, None)
    
    def provide_file(self, file_id: str, content: Optional[str], error: str = None):
        """
        Provide file content from client.
        Called when client sends file/response.
        """
        with self._files_lock:
            if file_id in self._pending_files:
                self._pending_files[file_id]['content'] = content
                self._pending_files[file_id]['error'] = error
                self._pending_files[file_id]['event'].set()
            else:
                logger.warning(f"Received file content for unknown file_id: {file_id}")


@dataclass
class TempFileInfo:
    """Information about a temporary file created for module execution"""
    original_name: str
    temp_path: str
    content: str


class ExecutionContext:
    """
    Extended context for module execution.
    Includes temp file management and other execution state.
    """
    
    def __init__(self, request_context: RequestContext):
        self.request = request_context
        self.temp_files: Dict[str, TempFileInfo] = {}
        self._content_store: Dict[str, str] = {}
    
    @property
    def events(self) -> EventPublisher:
        return self.request.events
    
    @property
    def workspace(self) -> str:
        return self.request.workspace
    
    @property
    def global_options(self) -> Dict[str, Any]:
        return self.request.global_options
    
    def store_content(self, content: str) -> str:
        """
        Store content and return an ID for retrieval.
        Used for injecting file content into modules.
        """
        content_id = str(uuid.uuid4())
        self._content_store[content_id] = content
        return content_id
    
    def get_content(self, content_id: str) -> Optional[str]:
        """Retrieve stored content by ID"""
        return self._content_store.get(content_id)
    
    def clear_content(self, content_id: str):
        """Remove stored content"""
        self._content_store.pop(content_id, None)
    
    def request_input(self, prompt: str = '') -> str:
        """Proxy to request context"""
        return self.request.request_input(prompt)
    
    def request_file(self, filepath: str, timeout: float = None) -> Optional[str]:
        """Proxy to request context"""
        return self.request.request_file(filepath, timeout)
