#!/usr/bin/env python3
"""
Recon-ng Web Server Entry Point

This module provides the entry point for the `recon-web` console command
when installed via pip.

The web server uses Sanic + python-socketio with uvicorn as the ASGI server.
It communicates with the recon-ng RPC server via RabbitMQ.
"""
import argparse


def main():
    """Main entry point for the recon-web server."""
    parser = argparse.ArgumentParser(description='Recon-ng Web Server')
    parser.add_argument('--host', default='0.0.0.0', 
                        help="IP address to listen on (default: 0.0.0.0)")
    parser.add_argument('--port', default=5000, type=int, 
                        help="Port to bind the web server to (default: 5000)")
    parser.add_argument('--debug', action='store_true', 
                        help="Enable debug mode")
    parser.add_argument('--reload', action='store_true', 
                        help="Enable auto-reload on code changes")

    args = parser.parse_args()

    # Import uvicorn here to make it an optional dependency
    # Only needed when actually running the web server
    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is not installed.")
        print("Install web dependencies with: pip install 'recon-ng[web]'")
        return 1

    print(f" * Starting web server on http://{args.host}:{args.port}")
    print(" * WebSocket support enabled")
    print(" * Press Ctrl+C to quit")
    
    # Run the ASGI app (Sanic + python-socketio combined)
    # We use the asgi_app which wraps both Sanic and SocketIO
    uvicorn.run(
        "recon.core.web:asgi_app",
        host=args.host,
        port=args.port,
        reload=args.reload or args.debug,
        log_level="debug" if args.debug else "info",
    )


if __name__ == '__main__':
    main()
