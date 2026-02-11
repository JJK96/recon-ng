"""
Request context for processing RPC requests
"""
import asyncio
import uuid
import logging
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
        self._pending_inputs: Dict[str, Dict] = {}
    
    def request_input(self, prompt: str = '') -> str:
        """
        Request input from the client and wait for response.
        This is called when a module uses input().
        
        Args:
            prompt: The prompt to display to the user
            
        Returns:
            The user's input string
            
        Raises:
            InputTimeoutError: If no response within timeout
        """
        input_id = str(uuid.uuid4())
        
        # Create event to wait on
        response_event = ThreadingEvent()
        self._pending_inputs[input_id] = {
            'event': response_event,
            'value': None
        }
        
        # Send input_required event to client
        self.events.input_required(input_id, prompt)
        
        # Wait for response
        try:
            if not response_event.wait(timeout=self.input_timeout):
                raise InputTimeoutError(
                    f"No input received from client within {self.input_timeout} seconds"
                )
            return self._pending_inputs[input_id]['value']
        finally:
            del self._pending_inputs[input_id]
    
    def provide_input(self, input_id: str, value: str):
        """
        Provide input value from client.
        Called when client sends input/response.
        """
        if input_id in self._pending_inputs:
            self._pending_inputs[input_id]['value'] = value
            self._pending_inputs[input_id]['event'].set()
        else:
            logger.warning(f"Received input for unknown input_id: {input_id}")


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
