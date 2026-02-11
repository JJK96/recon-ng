"""
Async Recon main class for CLI client.

This is a transformed version of recon/core/base.py that:
- Uses async/await for RPC operations
- Inherits from AsyncFramework
- Handles workspaces, marketplace, snapshots, and module loading
"""
import asyncio
import os
import random
import re
import sys
from pathlib import Path

# Import base framework class
from recon.client.framework import AsyncFramework, Colors, Options, FrameworkException
from recon.client.rpc import CLIRPCClient, RPCClientError, RPCConnectionError
from recon.shared.constants import Commands

# Import banner
from recon.core.constants import BANNER, BANNER_SMALL

# Get version
VERSION_FILE = os.path.join(Path(os.path.abspath(__file__)).parents[2], 'VERSION')
try:
    with open(VERSION_FILE) as f:
        exec(f.read())
except:
    __version__ = '5.1.3'

__author__ = 'Tim Tomes (@lanmaster53)'


class AsyncRecon(AsyncFramework):
    """
    Main Recon-ng CLI client class.
    
    Provides workspace management, marketplace access, snapshots,
    and module loading functionality via RPC.
    """
    
    def __init__(self, rpc_client: CLIRPCClient = None, check=True, analytics=True, 
                 marketplace=True, accessible=False):
        AsyncFramework.__init__(self, rpc_client)
        self._name = 'recon-ng'
        self._prompt_template = '{}[{}] > '
        self._base_prompt = self._prompt_template.format('', self._name)
        
        # Set toggle flags
        self._check = check
        self._analytics = analytics
        self._marketplace = marketplace
        self._accessible = accessible
        
        # Path variables (for client-side operations)
        self.home_path = os.path.join(os.path.expanduser('~'), '.recon-ng')
        
        # Current module (None when at base prompt)
        self.current_module = None
        self._module_context = None
        
        # Cached data
        self._workspaces_cache = []
        self._snapshots_cache = []
        self._module_index = []
        self._loaded_category = {}
        
        # Initialize options to global options
        self.options = self._global_options
        
    def start(self, workspace='default'):
        """Initialize and start the command loop."""
        # Initialize global options
        self._init_global_options()
        
        # Connect to RPC server (async)
        if self.rpc:
            try:
                self._run_async(self.rpc.connect())
                self.alert('Connected to RPC server.')
            except RPCConnectionError as e:
                self.error(f"Failed to connect to RPC server: {e}")
                self.error('Make sure the recon-ng server is running.')
                return
        
        # Initialize workspace (async)
        self._run_async(self._init_workspace(workspace))
        
        # Print banner (async)
        self._run_async(self._print_banner())
        
        # Start synchronous command loop
        self.cmdloop()
    
    #==================================================
    # SUPPORT METHODS
    #==================================================
    
    def _init_global_options(self):
        """Initialize default global options."""
        self.options = self._global_options
        self._register_option('nameserver', '8.8.8.8', True, 'default nameserver for the resolver mixin')
        self._register_option('proxy', None, False, 'proxy server (address:port)')
        self._register_option('threads', 10, True, 'number of threads (where applicable)')
        self._register_option('timeout', 10, True, 'socket timeout (seconds)')
        self._register_option('user-agent', f"Recon-ng/v{__version__.split('.')[0]}", True, 'user-agent string')
        self._register_option('verbosity', 1, True, 'verbosity level (0 = minimal, 1 = verbose, 2 = debug)')
    
    def _register_option(self, name, value, required, description):
        """Register a global option."""
        self._global_options[name.upper()] = value
        self._global_options.required[name.upper()] = required
        self._global_options.description[name.upper()] = description
    
    async def _init_workspace(self, workspace):
        """Initialize or switch to a workspace."""
        if not workspace:
            return
        
        self.workspace = workspace
        
        # Ensure workspace exists on server
        try:
            result = await self._call(Commands.WORKSPACES_LIST)
            workspaces = result.get('workspaces', [])
            if workspace not in workspaces:
                await self._call(Commands.WORKSPACES_CREATE, {'name': workspace})
                self.output(f"Workspace '{workspace}' created.")
        except RPCClientError as e:
            self.error(f"Failed to initialize workspace: {e}")
            return False
        
        # Set workspace prompt
        self.prompt = self._prompt_template.format(self._base_prompt[:-3], workspace)
        
        # Clear cached data
        self._clear_tables_cache()
        self._snapshots_cache = []
        
        # Load modules list from server
        await self._load_modules()
        
        return True
    
    async def _load_modules(self):
        """Load module list from server."""
        try:
            result = await self._call(Commands.MODULES_LIST)
            modules = result.get('modules', [])
            
            # Build loaded modules and categories
            self._loaded_modules = {}
            self._loaded_category = {}
            
            for mod in modules:
                path = mod.get('path', mod) if isinstance(mod, dict) else mod
                self._loaded_modules[path] = mod
                
                # Categorize
                category = path.split('/')[0] if '/' in path else 'misc'
                if category not in self._loaded_category:
                    self._loaded_category[category] = []
                self._loaded_category[category].append(path)
            
            # Update class-level cache for tab completion
            AsyncFramework._loaded_modules = self._loaded_modules
            
        except RPCClientError as e:
            self.debug(f"Failed to load modules: {e}")
    
    async def _print_banner(self):
        """Print the startup banner."""
        banner = BANNER
        banner_len = len(max(banner.split(os.linesep), key=len))
        author = '{0:^{1}}'.format(f"{Colors.O}[{self._name} v{__version__}, {__author__}]{Colors.N}", banner_len + 8)
        
        if self._accessible:
            banner = BANNER_SMALL
            author = f"{Colors.O}{self._name}, version {__version__}, by {__author__}{Colors.N}"
        
        print(banner)
        print(author)
        print('')
        
        # Print module counts
        counts = [(len(self._loaded_category.get(x, [])), x) for x in self._loaded_category]
        if counts:
            count_len = len(max([self.to_unicode_str(x[0]) for x in counts], key=len))
            for count in sorted(counts, reverse=True):
                cnt = f"[{count[0]}]"
                print(f"{Colors.B}{cnt.ljust(count_len+2)} {count[1].title()} modules{Colors.N}")
                # Create dynamic easter egg command based on counts
                setattr(self, f"do_{count[0]}", self._menu_egg)
        else:
            self.alert('No modules enabled/installed.')
        print('')
    
    def _menu_egg(self, params):
        """Easter egg command."""
        eggs = [
            'Really? A menu option? Try again.',
            'You clearly need \'help\'.',
            'That makes no sense to me.',
            '*grunt* *grunt* Nope. I got nothin\'.',
            'Wait for it...',
            'This is not the Social Engineering Toolkit.',
            'Don\'t you think if that worked the numbers would at least be in order?',
            'Reserving that option for the next-NEXT generation of the framework.',
            'You\'ve clearly got the wrong framework. Attempting to start SET...',
            '1980 called. They want their menu driven UI back.',
        ]
        print(random.choice(eggs))
    
    def _match_modules(self, params):
        """Match module names by partial string."""
        return [x for x in self._loaded_modules if params in x]
    
    async def _get_workspaces(self):
        """Get list of workspaces from server."""
        try:
            result = await self._call(Commands.WORKSPACES_LIST)
            self._workspaces_cache = result.get('workspaces', [])
        except RPCClientError:
            pass
        return self._workspaces_cache
    
    async def _get_snapshots(self):
        """Get list of snapshots for current workspace."""
        try:
            result = await self._call(Commands.SNAPSHOTS_LIST)
            self._snapshots_cache = result.get('snapshots', [])
        except RPCClientError:
            pass
        return self._snapshots_cache
    
    #==================================================
    # COMMAND METHODS
    #==================================================
    
    async def do_workspaces(self, params):
        '''Manages workspaces'''
        if not params:
            self.help_workspaces()
            return
        arg, params = self._parse_params(params)
        if arg in self._parse_subcommands('workspaces'):
            return await getattr(self, '_do_workspaces_'+arg)(params)
        else:
            self.help_workspaces()
    
    async def _do_workspaces_list(self, params):
        '''Lists existing workspaces'''
        try:
            result = await self._call(Commands.WORKSPACES_LIST)
            workspaces = result.get('workspaces', [])
            if workspaces:
                rows = []
                for ws in sorted(workspaces):
                    # Try to get workspace info
                    try:
                        info = await self._call(Commands.WORKSPACES_INFO, {'name': ws})
                        modified = info.get('modified', 'N/A')
                    except:
                        modified = 'N/A'
                    rows.append((ws, modified))
                self.table(rows, header=['Workspaces', 'Modified'])
            else:
                self.output('No workspaces found.')
        except RPCClientError:
            pass
    
    async def _do_workspaces_create(self, params):
        '''Creates a new workspace'''
        if not params:
            self._help_workspaces_create()
            return
        try:
            await self._call(Commands.WORKSPACES_CREATE, {'name': params})
            await self._init_workspace(params)
        except RPCClientError as e:
            self.output(f"Unable to create '{params}' workspace.")
    
    async def _do_workspaces_load(self, params):
        '''Loads an existing workspace'''
        if not params:
            self._help_workspaces_load()
            return
        workspaces = await self._get_workspaces()
        if params in workspaces:
            if not await self._init_workspace(params):
                self.output(f"Unable to initialize '{params}' workspace.")
        else:
            self.output('Invalid workspace name.')
    
    async def _do_workspaces_remove(self, params):
        '''Removes an existing workspace'''
        if not params:
            self._help_workspaces_remove()
            return
        try:
            await self._call(Commands.WORKSPACES_DELETE, {'name': params})
            self.output(f"Workspace '{params}' removed.")
            # If we deleted current workspace, switch to default
            if params == self.workspace:
                await self._init_workspace('default')
        except RPCClientError as e:
            self.output(f"Unable to remove '{params}' workspace.")
    
    async def do_snapshots(self, params):
        '''Manages workspace snapshots'''
        if not params:
            self.help_snapshots()
            return
        arg, params = self._parse_params(params)
        if arg in self._parse_subcommands('snapshots'):
            return await getattr(self, '_do_snapshots_'+arg)(params)
        else:
            self.help_snapshots()
    
    async def _do_snapshots_list(self, params):
        '''Lists existing database snapshots'''
        try:
            result = await self._call(Commands.SNAPSHOTS_LIST)
            snapshots = result.get('snapshots', [])
            if snapshots:
                self.table([[x] for x in snapshots], header=['Snapshots'])
            else:
                self.output('This workspace has no snapshots.')
        except RPCClientError:
            pass
    
    async def _do_snapshots_take(self, params):
        '''Takes a snapshot of the current database'''
        try:
            result = await self._call(Commands.SNAPSHOTS_TAKE)
            snapshot = result.get('snapshot', 'snapshot')
            self.output(f"Snapshot created: {snapshot}")
        except RPCClientError:
            pass
    
    async def _do_snapshots_load(self, params):
        '''Loads an existing database snapshot'''
        if not params:
            self._help_snapshots_load()
            return
        try:
            result = await self._call(Commands.SNAPSHOTS_LIST)
            snapshots = result.get('snapshots', [])
            if params in snapshots:
                await self._call(Commands.SNAPSHOTS_LOAD, {'name': params})
                self.output(f"Snapshot loaded: {params}")
            else:
                self.error(f"No snapshot named '{params}'.")
        except RPCClientError:
            pass
    
    async def _do_snapshots_remove(self, params):
        '''Removes an existing snapshot'''
        if not params:
            self._help_snapshots_remove()
            return
        try:
            result = await self._call(Commands.SNAPSHOTS_LIST)
            snapshots = result.get('snapshots', [])
            if params in snapshots:
                await self._call(Commands.SNAPSHOTS_DELETE, {'name': params})
                self.output(f"Snapshot removed: {params}")
            else:
                self.error(f"No snapshot named '{params}'.")
        except RPCClientError:
            pass
    
    async def do_marketplace(self, params):
        '''Interfaces with the module marketplace'''
        if not self._marketplace:
            self.alert('Marketplace disabled.')
            return
        if not params:
            self.help_marketplace()
            return
        arg, params = self._parse_params(params)
        if arg in self._parse_subcommands('marketplace'):
            return await getattr(self, '_do_marketplace_'+arg)(params)
        else:
            self.help_marketplace()
    
    async def _do_marketplace_refresh(self, params):
        '''Refreshes the marketplace index'''
        try:
            await self._call(Commands.MARKETPLACE_REFRESH)
            self.output('Marketplace index refreshed.')
            # Update module index
            await self._update_module_index()
        except RPCClientError:
            pass
    
    async def _update_module_index(self):
        """Update the local module index from server."""
        try:
            result = await self._call(Commands.MARKETPLACE_SEARCH, {'term': ''})
            self._module_index = result.get('modules', [])
        except RPCClientError:
            self._module_index = []
    
    async def _do_marketplace_search(self, params):
        '''Searches marketplace modules'''
        try:
            result = await self._call(Commands.MARKETPLACE_SEARCH, {'term': params or ''})
            modules = result.get('modules', [])
            if modules:
                rows = []
                for module in sorted(modules, key=lambda m: m.get('path', '')):
                    row = [
                        module.get('path', ''),
                        module.get('version', ''),
                        module.get('status', ''),
                        module.get('last_updated', ''),
                        '*' if module.get('dependencies') else '',
                        '*' if module.get('required_keys') else ''
                    ]
                    rows.append(row)
                header = ('Path', 'Version', 'Status', 'Updated', 'D', 'K')
                self.table(rows, header=header)
                print(f"{self.spacer}D = Has dependencies. See info for details.")
                print(f"{self.spacer}K = Requires keys. See info for details.{os.linesep}")
            else:
                self.error('No modules found.')
                self._help_marketplace_search()
        except RPCClientError:
            pass
    
    async def _do_marketplace_info(self, params):
        '''Shows detailed information about available modules'''
        if not params:
            self._help_marketplace_info()
            return
        try:
            result = await self._call(Commands.MARKETPLACE_INFO, {'path': params})
            modules = result.get('modules', [])
            if modules:
                for module in modules:
                    rows = []
                    for key in ('path', 'name', 'author', 'version', 'last_updated', 'description', 'required_keys', 'dependencies', 'files', 'status'):
                        row = (key, module.get(key, ''))
                        rows.append(row)
                    self.table(rows)
            else:
                self.error('Invalid module path.')
        except RPCClientError:
            pass
    
    async def _do_marketplace_install(self, params):
        '''Installs modules from the marketplace'''
        if not params:
            self._help_marketplace_install()
            return
        try:
            result = await self._call(Commands.MARKETPLACE_INSTALL, {'path': params})
            installed = result.get('installed', [])
            for path in installed:
                self.output(f"Module installed: {path}")
            # Reload modules
            await self._load_modules()
        except RPCClientError:
            pass
    
    async def _do_marketplace_remove(self, params):
        '''Removes marketplace modules from the framework'''
        if not params:
            self._help_marketplace_remove()
            return
        try:
            result = await self._call(Commands.MARKETPLACE_REMOVE, {'path': params})
            removed = result.get('removed', [])
            for path in removed:
                self.output(f"Module removed: {path}")
            # Reload modules
            await self._load_modules()
        except RPCClientError:
            pass
    
    def _do_modules_load(self, params):
        '''Loads a module'''
        if not params:
            self._help_modules_load()
            return
        
        # Find matching modules
        modules = self._match_modules(params)
        
        # Notify the user if none or multiple modules are found
        if len(modules) != 1:
            if not modules:
                self.error('Invalid module name.')
            else:
                self.output(f"Multiple modules match '{params}'.")
                self._list_modules(modules)
            return
        
        # Load the module
        mod_path = modules[0]
        
        # Get module info from server (async call)
        try:
            result = self._run_async(self._call(Commands.MODULES_INFO, {'path': mod_path}))
            module_info = result
        except RPCClientError:
            return
        
        # Import and create module context
        from recon.client.module import ModuleContext
        
        # Create module context
        self._module_context = ModuleContext(
            rpc_client=self.rpc,
            module_path=mod_path,
            module_info=module_info,
            parent=self
        )
        self._module_context.set_event_loop(self.loop)
        self._module_context.workspace = self.workspace
        
        # Set prompt
        self._module_context.prompt = self._prompt_template.format(self.prompt[:-3], mod_path.split('/')[-1])
        
        # Enter module command loop (synchronous)
        while True:
            try:
                self._module_context.cmdloop()
            except KeyboardInterrupt:
                print('')
            
            if self._module_context._exit == 1:
                # User wants to exit framework
                self._exit = 1
                self._module_context = None
                self.current_module = None
                return True
            
            if self._module_context._reload == 1:
                self.output('Reloading module...')
                try:
                    self._run_async(self._call(Commands.MODULES_RELOAD, {'path': mod_path}))
                    # Refresh module info
                    result = self._run_async(self._call(Commands.MODULES_INFO, {'path': mod_path}))
                    self._module_context.module_info = result
                    self._module_context._init_options()
                    self._module_context._reload = 0
                    continue
                except RPCClientError:
                    pass
            
            # Check if user requested to load a different module
            if hasattr(self, '_pending_module_load') and self._pending_module_load:
                next_module = self._pending_module_load
                self._pending_module_load = None
                self._module_context = None
                self.current_module = None
                # Recursively load the new module
                return self._do_modules_load(next_module)
            
            break
        
        self._module_context = None
        self.current_module = None
    
    async def _do_modules_reload(self, params):
        '''Reloads installed modules'''
        self.output('Reloading modules...')
        try:
            await self._call(Commands.MODULES_RELOAD, {'path': params or None})
            await self._load_modules()
        except RPCClientError:
            pass
    
    def do_index(self, params):
        '''Creates a module index (dev only)'''
        mod_path, file_name = self._parse_params(params)
        if not mod_path:
            self.help_index()
            return
        self.output('This command requires server-side implementation.')
    
    #==================================================
    # HELP METHODS
    #==================================================
    
    def help_index(self):
        print(getattr(self, 'do_index').__doc__)
        print(f"{os.linesep}Usage: index <module|all> <index>{os.linesep}")
    
    def help_marketplace(self):
        print(getattr(self, 'do_marketplace').__doc__)
        print(f"{os.linesep}Usage: marketplace <{'|'.join(self._parse_subcommands('marketplace'))}> [...]{os.linesep}")
    
    def _help_marketplace_search(self):
        print("Searches marketplace modules")
        print(f"{os.linesep}Usage: marketplace search [<regex>]{os.linesep}")
    
    def _help_marketplace_info(self):
        print("Shows detailed information about available modules")
        print(f"{os.linesep}Usage: marketplace info <<path>|<prefix>|all>{os.linesep}")
    
    def _help_marketplace_install(self):
        print("Installs modules from the marketplace")
        print(f"{os.linesep}Usage: marketplace install <<path>|<prefix>|all>{os.linesep}")
    
    def _help_marketplace_remove(self):
        print("Removes marketplace modules from the framework")
        print(f"{os.linesep}Usage: marketplace remove <<path>|<prefix>|all>{os.linesep}")
    
    def help_workspaces(self):
        print(getattr(self, 'do_workspaces').__doc__)
        print(f"{os.linesep}Usage: workspaces <{'|'.join(self._parse_subcommands('workspaces'))}> [...]{os.linesep}")
    
    def _help_workspaces_create(self):
        print("Creates a new workspace")
        print(f"{os.linesep}Usage: workspace create <name>{os.linesep}")
    
    def _help_workspaces_load(self):
        print("Loads an existing workspace")
        print(f"{os.linesep}Usage: workspace load <name>{os.linesep}")
    
    def _help_workspaces_remove(self):
        print("Removes an existing workspace")
        print(f"{os.linesep}Usage: workspace remove <name>{os.linesep}")
    
    def help_snapshots(self):
        print(getattr(self, 'do_snapshots').__doc__)
        print(f"{os.linesep}Usage: snapshots <{'|'.join(self._parse_subcommands('snapshots'))}> [...]{os.linesep}")
    
    def _help_snapshots_load(self):
        print("Loads an existing database snapshot")
        print(f"{os.linesep}Usage: snapshots load <name>{os.linesep}")
    
    def _help_snapshots_remove(self):
        print("Removes an existing snapshot")
        print(f"{os.linesep}Usage: snapshots remove <name>{os.linesep}")
    
    #==================================================
    # COMPLETE METHODS
    #==================================================
    
    def complete_index(self, text, line, *ignored):
        if len(line.split(' ')) == 2:
            return [x for x in self._loaded_modules if x.startswith(text)]
        return []
    
    def complete_marketplace(self, text, line, *ignored):
        arg, params = self._parse_params(line.split(' ', 1)[1])
        subs = self._parse_subcommands('marketplace')
        if arg in subs:
            return getattr(self, '_complete_marketplace_'+arg)(text, params)
        return [sub for sub in subs if sub.startswith(text)]
    
    def _complete_marketplace_refresh(self, text, *ignored):
        return []
    _complete_marketplace_search = _complete_marketplace_refresh
    
    def _complete_marketplace_info(self, text, *ignored):
        return [x.get('path', '') for x in self._module_index if x.get('path', '').startswith(text)]
    _complete_marketplace_install = _complete_marketplace_info
    
    def _complete_marketplace_remove(self, text, *ignored):
        return [x.get('path', '') for x in self._module_index if x.get('status') == 'installed' and x.get('path', '').startswith(text)]
    
    def complete_workspaces(self, text, line, *ignored):
        arg, params = self._parse_params(line.split(' ', 1)[1])
        subs = self._parse_subcommands('workspaces')
        if arg in subs:
            return getattr(self, '_complete_workspaces_'+arg)(text, params)
        return [sub for sub in subs if sub.startswith(text)]
    
    def _complete_workspaces_list(self, text, *ignored):
        return []
    _complete_workspaces_create = _complete_workspaces_list
    
    def _complete_workspaces_load(self, text, *ignored):
        return [x for x in self._workspaces_cache if x.startswith(text)]
    _complete_workspaces_remove = _complete_workspaces_load
    
    def complete_snapshots(self, text, line, *ignored):
        arg, params = self._parse_params(line.split(' ', 1)[1])
        subs = self._parse_subcommands('snapshots')
        if arg in subs:
            return getattr(self, '_complete_snapshots_'+arg)(text, params)
        return [sub for sub in subs if sub.startswith(text)]
    
    def _complete_snapshots_list(self, text, *ignored):
        return []
    _complete_snapshots_take = _complete_snapshots_list
    
    def _complete_snapshots_load(self, text, *ignored):
        return [x for x in self._snapshots_cache if x.startswith(text)]
    _complete_snapshots_remove = _complete_snapshots_load
    
    def _complete_modules_reload(self, text, *ignored):
        return []
