"""
RabbitMQ consumer for processing RPC requests using aio_pika (async)
"""
import asyncio
import json
import logging
from typing import Callable, Dict, Optional

import aio_pika
from aio_pika import IncomingMessage, Message, ExchangeType
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractQueue

from recon.shared.constants import Commands, Queues
from recon.shared.schemas import RPCRequest, RPCResponse
from recon.server.engine import Engine
from recon.server.dispatcher import Dispatcher
from recon.server.context import RequestContext

logger = logging.getLogger(__name__)


class RPCConsumer:
    """
    Async RabbitMQ consumer that processes RPC requests.
    
    This consumer:
    - Listens on the rpc.requests queue for incoming requests
    - Dispatches requests to the appropriate handlers via the Dispatcher
    - Publishes events to client-specific queues during execution
    - Sends responses back to client-specific response queues
    
    For input handling:
    - Tracks active request contexts that are waiting for input
    - Routes input/response commands to the appropriate waiting context
    """
    
    def __init__(
        self,
        amqp_url: str,
        engine: Engine,
        prefetch_count: int = 10
    ):
        """
        Args:
            amqp_url: RabbitMQ connection URL
            engine: The Engine instance
            prefetch_count: Number of messages to prefetch
        """
        self.amqp_url = amqp_url
        self.engine = engine
        self.prefetch_count = prefetch_count
        
        self._connection: Optional[AbstractConnection] = None
        self._channel: Optional[AbstractChannel] = None
        self._queue: Optional[AbstractQueue] = None
        self._consuming = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Track active contexts waiting for input, keyed by request_id
        self._active_contexts: Dict[str, RequestContext] = {}
        self._contexts_lock = asyncio.Lock()
        
        # Cache for declared client queues to avoid re-declaring on every publish
        self._declared_queues: set = set()
        
        # Dispatcher will be created when we connect (need the event loop)
        self.dispatcher: Optional[Dispatcher] = None
    
    async def connect(self):
        """Establish connection to RabbitMQ"""
        logger.info(f"Connecting to RabbitMQ at {self.amqp_url}")
        
        # Get the current event loop
        self._loop = asyncio.get_running_loop()
        
        # Create dispatcher with publish function and event loop
        self.dispatcher = Dispatcher(self.engine, self._publish_message, loop=self._loop)
        
        self._connection = await aio_pika.connect_robust(self.amqp_url)
        self._channel = await self._connection.channel()
        
        # Set prefetch count for fair dispatch
        await self._channel.set_qos(prefetch_count=self.prefetch_count)
        
        # Declare the requests queue
        self._queue = await self._channel.declare_queue(
            Queues.RPC_REQUESTS,
            durable=True
        )
        
        logger.info("Connected to RabbitMQ")
    
    async def _publish_message(self, queue: str, body: str):
        """
        Publish a message to a queue.
        
        This is passed to the Dispatcher and EventPublisher for sending
        events and responses back to clients.
        """
        if not self._channel:
            logger.error("Cannot publish: channel not connected")
            return
        
        # Declare the queue only if we haven't seen it before
        if queue not in self._declared_queues:
            await self._channel.declare_queue(
                queue,
                durable=False,  # Client queues are transient
                auto_delete=True  # Delete when client disconnects
            )
            self._declared_queues.add(queue)
        
        await self._channel.default_exchange.publish(
            Message(
                body=body.encode('utf-8'),
                content_type='application/json',
                delivery_mode=aio_pika.DeliveryMode.NOT_PERSISTENT
            ),
            routing_key=queue
        )
    
    async def _on_request(self, message: IncomingMessage):
        """Handle an incoming RPC request"""
        async with message.process():
            try:
                # Parse the request
                data = json.loads(message.body.decode('utf-8'))
                request = RPCRequest(**data)
                
                logger.debug(f"Received request: {request.command} from {request.client_id}")
                
                # Handle input/response specially
                if request.command == Commands.INPUT_RESPONSE:
                    await self._handle_input_response(request)
                    return
                
                # Handle file/response specially
                if request.command == Commands.FILE_RESPONSE:
                    await self._handle_file_response(request)
                    return
                
                # Check if handler requires execution context (e.g., module runs)
                handler = self.dispatcher.get_handler(request.command)
                requires_context = handler and handler.requires_context
                
                if requires_context:
                    # Track context for commands that might need input
                    ctx = RequestContext(
                        request_id=request.id,
                        client_id=request.client_id,
                        workspace=request.workspace,
                        global_options=request.global_options,
                        publish_func=self._publish_message,
                        loop=self._loop
                    )
                    async with self._contexts_lock:
                        self._active_contexts[request.id] = ctx
                    
                    try:
                        # Dispatch in thread pool for handlers that need context
                        # (module execution is synchronous but needs async event publishing)
                        # Pass the context we created so dispatcher uses the same one
                        response = await self._loop.run_in_executor(
                            None,  # Use default ThreadPoolExecutor
                            self.dispatcher.dispatch,
                            request,
                            ctx  # Pass context to dispatcher
                        )
                    finally:
                        # Clean up context tracking
                        async with self._contexts_lock:
                            self._active_contexts.pop(request.id, None)
                else:
                    # Simple handlers can run directly without thread pool overhead
                    response = self.dispatcher.dispatch(request)
                
                # Send response to client
                response_queue = Queues.responses(request.client_id)
                response_json = response.model_dump_json()
                await self._publish_message(response_queue, response_json)
                
            except json.JSONDecodeError as e:
                # Malformed messages should NOT be retried - log and discard
                logger.error(f"Failed to parse request JSON (discarding): {e}")
                # Don't re-raise - the message.process() context manager will ack
                # the message since we didn't raise an exception
                
            except Exception as e:
                logger.exception(f"Error processing request: {e}")
                
                # Try to send error response if we have enough info
                try:
                    if 'request' in locals():
                        response = RPCResponse.make_error(
                            request.id,
                            'INTERNAL_ERROR',
                            str(e)
                        )
                        response_queue = Queues.responses(request.client_id)
                        await self._publish_message(response_queue, response.model_dump_json())
                except Exception:
                    pass
                
                # Don't re-raise for most errors - we've sent an error response
                # Only re-raise for truly unrecoverable infrastructure errors
    
    async def _handle_input_response(self, request: RPCRequest):
        """
        Handle an input/response command.
        
        This finds the waiting context and provides the input value.
        """
        input_id = request.params.get('input_id')
        value = request.params.get('value', '')
        
        if not input_id:
            logger.warning("input/response missing input_id")
            return
        
        # Find the context that's waiting for this input
        # Check each active context to see if it has this pending input_id
        async with self._contexts_lock:
            for ctx in self._active_contexts.values():
                if ctx.has_pending_input(input_id):
                    ctx.provide_input(input_id, value)
                    return
            logger.warning(f"No context found waiting for input_id: {input_id}")
    
    async def _handle_file_response(self, request: RPCRequest):
        """
        Handle a file/response command.
        
        This finds the waiting context and provides the file content.
        """
        file_id = request.params.get('file_id')
        content = request.params.get('content')
        error = request.params.get('error')
        
        if not file_id:
            logger.warning("file/response missing file_id")
            return
        
        # Find the context that's waiting for this file
        # Check each active context to see if it has this pending file_id
        async with self._contexts_lock:
            for ctx in self._active_contexts.values():
                if ctx.has_pending_file(file_id):
                    ctx.provide_file(file_id, content, error)
                    return
            logger.warning(f"No context found waiting for file_id: {file_id}")
    
    async def start_consuming(self):
        """Start consuming messages from the requests queue"""
        if not self._queue:
            raise RuntimeError("Not connected. Call connect() first.")
        
        logger.info(f"Starting to consume from {Queues.RPC_REQUESTS}")
        
        self._consuming = True
        
        async with self._queue.iterator() as queue_iter:
            async for message in queue_iter:
                if not self._consuming:
                    break
                # Process messages concurrently by spawning tasks
                asyncio.create_task(self._on_request(message))
    
    async def stop_consuming(self):
        """Stop consuming messages"""
        logger.info("Stopping consumer")
        self._consuming = False
    
    async def close(self):
        """Close the connection"""
        await self.stop_consuming()
        
        if self._connection and not self._connection.is_closed:
            logger.info("Closing RabbitMQ connection")
            await self._connection.close()
        
        self._connection = None
        self._channel = None
        self._queue = None


async def run_consumer(amqp_url: str, engine: Engine):
    """
    Convenience function to run the consumer.
    
    This sets up signal handlers and runs until interrupted.
    """
    consumer = RPCConsumer(amqp_url, engine)
    
    try:
        await consumer.connect()
        await consumer.start_consuming()
    except asyncio.CancelledError:
        logger.info("Consumer cancelled")
    finally:
        await consumer.close()
