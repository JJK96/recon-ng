"""
Server entry point
"""
import argparse
import asyncio
import logging
import os
import signal
import sys

from recon.shared.constants import DEFAULT_SERVER_URL
from recon.server.engine import Engine
from recon.server.consumer import RPCConsumer, run_consumer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_server(amqp_url: str, engine: Engine, prefetch_count: int):
    """Run the RPC server"""
    consumer = RPCConsumer(
        amqp_url=amqp_url,
        engine=engine,
        prefetch_count=prefetch_count
    )
    
    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    
    def signal_handler():
        logger.info("Received shutdown signal, stopping...")
        asyncio.create_task(consumer.stop_consuming())
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        await consumer.connect()
        logger.info("Connected to RabbitMQ, starting to consume requests...")
        await consumer.start_consuming()
    finally:
        await consumer.close()
        logger.info("Server stopped")


def main():
    """Main entry point for the recon-ng server"""
    parser = argparse.ArgumentParser(
        description='Recon-ng RPC Server',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        '--amqp-url',
        default=os.environ.get('AMQP_URL', DEFAULT_SERVER_URL),
        help='RabbitMQ connection URL'
    )
    
    parser.add_argument(
        '--home',
        default=os.environ.get('RECON_HOME', os.path.expanduser('~/.recon-ng')),
        help='Recon-ng home directory'
    )
    
    parser.add_argument(
        '--prefetch',
        type=int,
        default=int(os.environ.get('PREFETCH_COUNT', '10')),
        help='Number of messages to prefetch'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        default=os.environ.get('DEBUG', '').lower() in ('1', 'true', 'yes'),
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    # Set log level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    logger.info("Starting Recon-ng RPC Server")
    logger.info(f"Home directory: {args.home}")
    logger.info(f"AMQP URL: {args.amqp_url}")
    
    # Create engine
    try:
        engine = Engine(home_path=args.home)
        logger.info("Engine initialized")
    except Exception as e:
        import traceback
        logger.error(f"Failed to initialize engine: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
    
    # Run the async server
    try:
        asyncio.run(run_server(args.amqp_url, engine, args.prefetch))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
