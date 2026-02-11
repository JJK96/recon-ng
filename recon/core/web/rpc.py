"""
Async RPC Client for the web API to communicate with the RPC server.

This client uses aio-pika for async RabbitMQ communication and supports
real-time event streaming to WebSocket clients.
"""
import asyncio
import json
import logging
import os
import uuid
from typing import Any, AsyncIterator, Callable, Dict, Optional

import aio_pika
from aio_pika import Message, connect_robust
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractQueue

from recon.shared.constants import Queues, DEFAULT_SERVER_URL, EventType
from recon.shared.schemas import RPCRequest, RPCResponse, RPCEvent

logger = logging.getLogger(__name__)


class RPCClientError(Exception):
    """Error from RPC client"""
    pass


class AsyncRPCClient:
    """
    Async RPC client for sending requests to the recon-ng server.
    
    Features:
    - Async request/response pattern
    - Real-time event streaming via async iterators
    - Connection pooling and auto-reconnect
    
    Usage:
        client = AsyncRPCClient(amqp_url)
        await client.connect()
        
        # Simple call
        result = await client.call('modules/list', workspace='default')
        
        # Call with event streaming
        async for event in client.call_with_events('modules/run', ...):
            print(event)
        
        await client.close()
    """
    
    def __init__(self, amqp_url: str = None):
        """
        Args:
            amqp_url: RabbitMQ connection URL
        """
        self.amqp_url = amqp_url or os.environ.get('AMQP_URL', DEFAULT_SERVER_URL)
        self.client_id = f"web-{uuid.uuid4().hex[:8]}"
        
        self._connection: Optional[AbstractConnection] = None
        self._channel: Optional[AbstractChannel] = None
        self._response_queue: Optional[AbstractQueue] = None
        self._events_queue: Optional[AbstractQueue] = None
        
        # Pending requests waiting for responses
        self._pending: Dict[str, asyncio.Future] = {}
        
        # Event callbacks: request_id -> callback function
        self._event_callbacks: Dict[str, Callable[[RPCEvent], None]] = {}
        
        self._consuming = False
    
    async def connect(self):
        """Establish connection to RabbitMQ"""
        if self._connection and not self._connection.is_closed:
            return
        
        logger.info(f"Connecting to RabbitMQ at {self.amqp_url}")
        
        self._connection = await connect_robust(self.amqp_url)
        self._channel = await self._connection.channel()
        
        # Declare response queue
        response_queue_name = Queues.responses(self.client_id)
        self._response_queue = await self._channel.declare_queue(
            response_queue_name,
            durable=False,
            auto_delete=True
        )
        
        # Declare events queue
        events_queue_name = Queues.events(self.client_id)
        self._events_queue = await self._channel.declare_queue(
            events_queue_name,
            durable=False,
            auto_delete=True
        )
        
        # Start consuming responses and events
        await self._start_consuming()
        
        logger.info(f"Connected as client {self.client_id}")
    
    async def _start_consuming(self):
        """Start consuming from response and event queues"""
        if self._consuming:
            return
        
        # Consume responses
        await self._response_queue.consume(self._on_response)
        
        # Consume events
        await self._events_queue.consume(self._on_event)
        
        self._consuming = True
    
    async def _on_response(self, message: aio_pika.IncomingMessage):
        """Handle incoming response"""
        async with message.process():
            try:
                data = json.loads(message.body.decode('utf-8'))
                response = RPCResponse(**data)
                
                # Find and resolve the pending future
                future = self._pending.pop(response.id, None)
                if future and not future.done():
                    future.set_result(response)
                else:
                    logger.warning(f"Received response for unknown request: {response.id}")
                    
            except Exception as e:
                logger.error(f"Error processing response: {e}")
    
    async def _on_event(self, message: aio_pika.IncomingMessage):
        """Handle incoming event"""
        async with message.process():
            try:
                data = json.loads(message.body.decode('utf-8'))
                event = RPCEvent(**data)
                
                # Find and call the event callback
                callback = self._event_callbacks.get(event.id)
                if callback:
                    try:
                        # Handle both sync and async callbacks
                        result = callback(event)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"Error in event callback: {e}")
                else:
                    logger.debug(f"Received event for unknown request: {event.id}")
                    
            except Exception as e:
                logger.error(f"Error processing event: {e}")
    
    async def close(self):
        """Close the connection"""
        self._consuming = False
        self._pending.clear()
        self._event_callbacks.clear()
        
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
        
        self._connection = None
        self._channel = None
    
    async def call(
        self,
        command: str,
        workspace: str = 'default',
        params: Dict[str, Any] = None,
        global_options: Dict[str, Any] = None,
        timeout: float = 30.0,
        event_callback: Callable[[RPCEvent], None] = None
    ) -> Dict[str, Any]:
        """
        Make an RPC call and wait for the response.
        
        Args:
            command: The command to execute
            workspace: The workspace name
            params: Command parameters
            global_options: Global option overrides
            timeout: Response timeout in seconds
            event_callback: Optional callback for real-time events
            
        Returns:
            The result dictionary from the response
            
        Raises:
            RPCClientError: If the request fails or times out
        """
        await self.connect()
        
        # Create request
        request = RPCRequest(
            client_id=self.client_id,
            command=command,
            workspace=workspace,
            params=params or {},
            global_options=global_options or {}
        )
        
        # Set up response future
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[request.id] = future
        
        # Set up event callback if provided
        if event_callback:
            self._event_callbacks[request.id] = event_callback
        
        try:
            # Publish request
            await self._channel.default_exchange.publish(
                Message(
                    body=request.model_dump_json().encode('utf-8'),
                    content_type='application/json'
                ),
                routing_key=Queues.RPC_REQUESTS
            )
            
            # Wait for response with timeout
            try:
                response = await asyncio.wait_for(future, timeout=timeout)
            except asyncio.TimeoutError:
                raise RPCClientError(f"Request timed out after {timeout}s")
            
            if response.status == 'error':
                error = response.error or {}
                raise RPCClientError(
                    f"{error.get('code', 'UNKNOWN')}: {error.get('message', 'Unknown error')}"
                )
            
            return response.result or {}
            
        finally:
            # Clean up
            self._pending.pop(request.id, None)
            self._event_callbacks.pop(request.id, None)
    
    def call_with_events(
        self,
        command: str,
        workspace: str = 'default',
        params: Dict[str, Any] = None,
        global_options: Dict[str, Any] = None,
        timeout: float = 300.0  # Longer timeout for module runs
    ) -> '_EventStreamingCall':
        """
        Make an RPC call that yields events as they arrive.
        
        This returns an async iterator that yields RPCEvent objects until
        the response is received.
        
        Args:
            command: The command to execute
            workspace: The workspace name
            params: Command parameters
            global_options: Global option overrides
            timeout: Response timeout in seconds
            
        Returns:
            An async iterator that yields RPCEvent objects
            
        Example:
            stream = client.call_with_events('modules/run', ...)
            async for event in stream:
                handle_event(event)
            result = stream.result  # Available after iteration
        """
        return _EventStreamingCall(
            self, command, workspace, params, global_options, timeout
        )


class _EventStreamingCall:
    """
    Async iterator for streaming events during an RPC call.
    
    Usage:
        stream = client.call_with_events(...)
        async for event in stream:
            handle_event(event)
        # After iteration completes, result is available
        print(stream.result)
    """
    
    def __init__(
        self,
        client: AsyncRPCClient,
        command: str,
        workspace: str,
        params: Dict[str, Any],
        global_options: Dict[str, Any],
        timeout: float
    ):
        self.client = client
        self.command = command
        self.workspace = workspace
        self.params = params or {}
        self.global_options = global_options or {}
        self.timeout = timeout
        
        self._request_id: Optional[str] = None
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._response_future: Optional[asyncio.Future] = None
        self._started = False
        self._cleanup_done = False
        self.result: Optional[Dict[str, Any]] = None
    
    def __aiter__(self):
        return self
    
    async def __anext__(self) -> RPCEvent:
        if not self._started:
            await self._start()
        
        # Check if we have a response (meaning we're done)
        if self._response_future.done():
            # Drain any remaining events
            try:
                return self._event_queue.get_nowait()
            except asyncio.QueueEmpty:
                # Process the response and clean up
                await self._finish()
                raise StopAsyncIteration
        
        # Wait for either an event or the response
        try:
            # Use a short timeout to check response periodically
            event = await asyncio.wait_for(self._event_queue.get(), timeout=0.1)
            return event
        except asyncio.TimeoutError:
            # Check if response arrived
            if self._response_future.done():
                return await self.__anext__()
            # Continue waiting
            return await self.__anext__()
    
    async def _start(self):
        """Start the RPC call"""
        await self.client.connect()
        
        # Create request
        request = RPCRequest(
            client_id=self.client.client_id,
            command=self.command,
            workspace=self.workspace,
            params=self.params,
            global_options=self.global_options
        )
        self._request_id = request.id
        
        # Set up response future
        loop = asyncio.get_running_loop()
        self._response_future = loop.create_future()
        self.client._pending[request.id] = self._response_future
        
        # Set up event callback to queue events
        def queue_event(event: RPCEvent):
            self._event_queue.put_nowait(event)
        
        self.client._event_callbacks[request.id] = queue_event
        
        # Publish request
        await self.client._channel.default_exchange.publish(
            Message(
                body=request.model_dump_json().encode('utf-8'),
                content_type='application/json'
            ),
            routing_key=Queues.RPC_REQUESTS
        )
        
        self._started = True
    
    async def _finish(self):
        """Process the response and clean up"""
        if self._cleanup_done:
            return
        
        self._cleanup_done = True
        
        # Process the response
        response = self._response_future.result()
        if response.status == 'error':
            error = response.error or {}
            raise RPCClientError(
                f"{error.get('code', 'UNKNOWN')}: {error.get('message', 'Unknown error')}"
            )
        self.result = response.result or {}
        
        # Clean up
        if self._request_id:
            self.client._pending.pop(self._request_id, None)
            self.client._event_callbacks.pop(self._request_id, None)
