"""
Module Context class for CLI client.

This is used when a module is loaded. It provides module-specific commands
like info, run, input, reload, and options management.
"""
import os
import textwrap

# Import base framework class
from recon.client.framework import AsyncFramework, Colors, Options, FrameworkException
from recon.client.rpc import CLIRPCClient, RPCClientError
from recon.shared.constants import Commands


class ModuleContext(AsyncFramework):
    """
    Context for when a module is loaded.
    
    Provides module-specific commands: info, run, input, reload, goptions.
    Options are stored client-side but module execution is via RPC.
    """
    
    def __init__(self, rpc_client: CLIRPCClient, module_path: str, 
                 module_info: dict, parent=None):
        AsyncFramework.__init__(self, rpc_client)
        self._modulename = module_path
        self.module_path = module_path
        self.module_info = module_info
        self.parent = parent  # Reference to AsyncRecon
        
        # Module-specific state
        self._reload = 0
        self._exit = 0
        
        # Initialize module options from server-provided defaults
        self._init_options()
    
    def _init_options(self):
        """Initialize module options from module info."""
        self.options = Options()
        
        # Get options from module info
        options_info = self.module_info.get('options', [])
        for opt in options_info:
            name = opt.get('name', '').upper()
            value = opt.get('value')
            required = opt.get('required', True)
            description = opt.get('description', '')
            
            self.options[name] = value
            self.options.required[name] = required
            self.options.description[name] = description
        
        # If module has a query (source-based module), add SOURCE option
        if self.module_info.get('query'):
            if 'SOURCE' not in self.options:
                self.options['SOURCE'] = 'default'
                self.options.required['SOURCE'] = True
                self.options.description['SOURCE'] = "source of input (see 'info' for details)"
    
    #==================================================
    # COMMAND METHODS
    #==================================================
    
    def do_info(self, params):
        '''Shows details about the loaded module'''
        print('')
        
        # Meta info
        for item in ['name', 'author', 'version']:
            value = self.module_info.get(item, '')
            print(f"{item.title().rjust(10)}: {value}")
        
        # Required keys
        if self.module_info.get('required_keys'):
            keys_str = ', '.join(self.module_info.get('required_keys', []))
            print(f"{'keys'.title().rjust(10)}: {keys_str}")
        
        print('')
        
        # Description
        print('Description:')
        description = self.module_info.get('description', '')
        print(f"{self.spacer}{textwrap.fill(description, 100, subsequent_indent=self.spacer)}")
        print('')
        
        # Options
        print('Options:', end='')
        self._list_options()
        
        # Sources
        if self.module_info.get('query'):
            print('Source Options:')
            print(f"{self.spacer}{'default'.ljust(15)}{self.module_info.get('query')}")
            print(f"{self.spacer}{'<string>'.ljust(15)}string representing a single input")
            print(f"{self.spacer}{'<path>'.ljust(15)}path to a file containing a list of inputs")
            print(f"{self.spacer}{'query <sql>'.ljust(15)}database query returning one column of inputs")
            print('')
        
        # Comments
        if self.module_info.get('comments'):
            print('Comments:')
            for comment in self.module_info.get('comments', []):
                prefix = '* '
                if comment.startswith('\t'):
                    prefix = self.spacer + '- '
                    comment = comment[1:]
                print(f"{self.spacer}{textwrap.fill(prefix + comment, 100, subsequent_indent=self.spacer)}")
            print('')
    
    async def do_input(self, params):
        '''Shows inputs based on the source option'''
        if not self.module_info.get('query'):
            self.output('Source option not available for this module.')
            return
        
        try:
            # Get inputs from server
            result = await self._call(Commands.MODULES_INPUT, {
                'path': self.module_path,
                'options': dict(self.options),
                'global_options': dict(self._global_options)
            })
            
            if result.get('error'):
                self.output(result['error'])
                return
            
            inputs = result.get('inputs', [])
            if inputs:
                # Format as table
                rows = [[x] if not isinstance(x, (list, tuple)) else list(x) for x in inputs]
                self.table(rows, header=['Module Inputs'])
            else:
                self.output('No inputs found.')
        except RPCClientError:
            pass
    
    async def do_run(self, params):
        '''Runs the loaded module'''
        try:
            # Stream events during module execution
            async for event in self.rpc.call_with_events(
                Commands.MODULES_RUN,
                workspace=self.workspace,
                params={
                    'path': self.module_path,
                    'options': dict(self.options),
                },
                global_options=dict(self._global_options),
                timeout=600.0
            ):
                self._handle_event(event)
        except RPCClientError:
            pass
        except KeyboardInterrupt:
            print('')
            self.output('Module execution interrupted.')
    
    def do_reload(self, params):
        '''Reloads the loaded module'''
        self._reload = 1
        return True
    
    def do_goptions(self, params):
        '''Manages the global context options'''
        if not params:
            self.help_goptions()
            return
        arg, params = self._parse_params(params)
        if arg in self._parse_subcommands('goptions'):
            return getattr(self, '_do_goptions_'+arg)(params)
        else:
            self.help_goptions()
    
    def _do_goptions_list(self, params):
        '''Shows the global context options'''
        self._list_options(self._global_options)
    
    def _do_goptions_set(self, params):
        '''Sets a global context option'''
        option, value = self._parse_params(params)
        if not (option and value):
            self._help_goptions_set()
            return
        name = option.upper()
        if name in self._global_options:
            self._global_options[name] = value
            print(f"{name} => {value}")
            self._save_config(name, 'base', self._global_options)
        else:
            self.error('Invalid option name.')
    
    def _do_goptions_unset(self, params):
        '''Unsets a global context option'''
        option, value = self._parse_params(params)
        if not option:
            self._help_goptions_unset()
            return
        name = option.upper()
        if name in self._global_options:
            self._do_goptions_set(' '.join([name, 'None']))
        else:
            self.error('Invalid option name.')
    
    def _do_modules_load(self, params):
        '''Loads a different module (exits current and loads new)'''
        if not params:
            self._help_modules_load()
            return
        # Return to parent and let it handle the load
        # This is handled by setting a flag and returning True
        if self.parent:
            self.parent._pending_module_load = params
        return True
    
    #==================================================
    # HELP METHODS
    #==================================================
    
    def help_goptions(self):
        print(getattr(self, 'do_goptions').__doc__)
        print(f"{os.linesep}Usage: goptions <{'|'.join(self._parse_subcommands('goptions'))}> [...]{os.linesep}")
    
    def _help_goptions_set(self):
        print("Sets a global context option")
        print(f"{os.linesep}Usage: goptions set <option> <value>{os.linesep}")
    
    def _help_goptions_unset(self):
        print("Unsets a global context option")
        print(f"{os.linesep}Usage: goptions unset <option>{os.linesep}")
    
    def help_info(self):
        print(getattr(self, 'do_info').__doc__)
        print(f"{os.linesep}Usage: info{os.linesep}")
    
    def help_input(self):
        print(getattr(self, 'do_input').__doc__)
        print(f"{os.linesep}Usage: input{os.linesep}")
    
    def help_run(self):
        print(getattr(self, 'do_run').__doc__)
        print(f"{os.linesep}Usage: run{os.linesep}")
    
    def help_reload(self):
        print(getattr(self, 'do_reload').__doc__)
        print(f"{os.linesep}Usage: reload{os.linesep}")
    
    #==================================================
    # COMPLETE METHODS
    #==================================================
    
    def complete_goptions(self, text, line, *ignored):
        arg, params = self._parse_params(line.split(' ', 1)[1])
        subs = self._parse_subcommands('goptions')
        if arg in subs:
            return getattr(self, '_complete_goptions_'+arg)(text, params)
        return [sub for sub in subs if sub.startswith(text)]
    
    def _complete_goptions_list(self, text, *ignored):
        return []
    
    def _complete_goptions_set(self, text, *ignored):
        return [x for x in self._global_options if x.startswith(text.upper())]
    _complete_goptions_unset = _complete_goptions_set
    
    def complete_reload(self, text, *ignored):
        return []
    complete_info = complete_input = complete_run = complete_reload
