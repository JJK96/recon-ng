#!/usr/bin/env python3
"""
Recon-ng CLI Entry Point

This module provides the entry point for the `recon-ng` console command
when installed via pip.
"""
import argparse
import asyncio
import os
import re
import sys

from recon.client import AsyncRecon, __version__, __author__
from recon.client.rpc import CLIRPCClient
from recon.core.framework import Colors
from recon.shared.constants import DEFAULT_SERVER_URL


def main():
    """Main entry point for the recon-ng CLI."""
    # Prevent creation of compiled bytecode files
    sys.dont_write_bytecode = True
    
    description = f"recon-ng - {__author__}"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('-w', help='load/create a workspace', metavar='workspace', 
                        dest='workspace', action='store')
    parser.add_argument('-r', help='load commands from a resource file', metavar='filename', 
                        dest='script_file', action='store')
    parser.add_argument('--no-version', help='disable version check', 
                        dest='check', default=True, action='store_false')
    parser.add_argument('--no-analytics', help='disable analytics reporting', 
                        dest='analytics', default=True, action='store_false')
    parser.add_argument('--no-marketplace', help='disable remote module management', 
                        dest='marketplace', default=True, action='store_false')
    parser.add_argument('--stealth', help='disable all passive requests (--no-*)', 
                        dest='stealth', default=False, action='store_true')
    parser.add_argument('--accessible', help='Use accessible outputs when available', 
                        dest='accessible', default=False, action='store_true')
    parser.add_argument('--amqp-url', 
                        help='RabbitMQ URL (default: from AMQP_URL env or amqp://recon:recon@localhost:5672/)',
                        dest='amqp_url', default=None)
    parser.add_argument('--version', help='displays the current version', 
                        action='version', version=__version__)

    args = parser.parse_args()

    # Set up readline for command completion
    try:
        import readline
    except ImportError:
        print(f"{Colors.R}[!] Module 'readline' not available. Tab complete disabled.{Colors.N}")
    else:
        import rlcompleter
        if readline.__doc__ and 'libedit' in readline.__doc__:
            readline.parse_and_bind('bind ^I rl_complete')
        else:
            readline.parse_and_bind('tab: complete')
        readline.set_completer_delims(re.sub('[/-]', '', readline.get_completer_delims()))
    
    # Process toggle flag arguments
    flags = {
        'check': args.check if not args.stealth else False,
        'analytics': args.analytics if not args.stealth else False,
        'marketplace': args.marketplace if not args.stealth else False,
        'accessible': args.accessible,
    }
    
    # Get AMQP URL from args or environment
    amqp_url = args.amqp_url or os.environ.get('AMQP_URL', DEFAULT_SERVER_URL)
    
    # Create event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Create RPC client and AsyncRecon instance
    rpc_client = CLIRPCClient(amqp_url)
    client = AsyncRecon(rpc_client=rpc_client, **flags)
    client.set_event_loop(loop)
    
    # Handle script file
    workspace = args.workspace or 'default'
    
    try:
        # Start the client (synchronous cmdloop with async RPC calls)
        client.start(workspace=workspace)
    except KeyboardInterrupt:
        print('')
    finally:
        # Cleanup
        if rpc_client:
            try:
                loop.run_until_complete(rpc_client.close())
            except:
                pass
        loop.close()


if __name__ == '__main__':
    main()
