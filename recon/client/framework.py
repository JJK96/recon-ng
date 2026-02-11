"""
Async Framework base class for CLI client.

This is a transformed version of recon/core/framework.py that:
- Uses async/await for RPC operations
- Keeps all output formatting client-side
- Keeps client-only commands (shell, script, spool, pdb)
- Transforms data commands to use RPC
"""
import asyncio
import cmd
import codecs
import json
import os
import random
import re
import string
import subprocess
import sys
import traceback

# Import shared utilities from core (NO duplication)
from recon.core.framework import Colors, Options, FrameworkException

# Import RPC client and shared constants
from recon.client.rpc import CLIRPCClient, RPCClientError, RPCConnectionError
from recon.shared.constants import Commands, EventType, OutputLevel
from recon.shared.schemas import RPCEvent


class AsyncFramework(cmd.Cmd):
    """
    Async-compatible Framework base class.
    
    This provides the same interface as recon/core/framework.py but uses
    RPC calls for data operations while keeping output formatting client-side.
    """
    prompt = '>>>'
    # mode flags
    _script = 0
    _load = 0
    # framework variables
    _global_options = Options()
    _loaded_modules = {}  # Cache of module paths from server
    _record = None
    _spool = None
    
    def __init__(self, rpc_client: CLIRPCClient = None):
        cmd.Cmd.__init__(self)
        self._modulename = 'base'
        self.ruler = '-'
        self.spacer = '  '
        self.time_format = '%Y-%m-%d %H:%M:%S'
        self.nohelp = f"{Colors.R}[!] No help on %s{Colors.N}"
        self.do_help.__func__.__doc__ = '''Displays this menu'''
        self.doc_header = 'Commands (type [help|?] <topic>):'
        self._exit = 0
        
        # RPC client
        self.rpc = rpc_client
        self.loop = None
        
        # Current context options (for module context)
        self.options = Options()
        
        # Workspace (set by subclass)
        self.workspace = 'default'
        
        # Tables cache (populated on first query)
        self._tables_cache = None

    #==================================================
    # ASYNC SUPPORT
    #==================================================
    
    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        """Set the event loop for async operations."""
        self.loop = loop
    
    def _run_async(self, coro):
        """Run an async coroutine from sync context."""
        return self.loop.run_until_complete(coro)
    
    async def _call(self, command: str, params: dict = None) -> dict:
        """Make an RPC call to the server."""
        if params is None:
            params = {}
        try:
            return await self.rpc.call(
                command,
                workspace=self.workspace,
                params=params,
                global_options=dict(self._global_options)
            )
        except RPCClientError as e:
            self.error(str(e))
            raise
    
    async def _call_with_events(self, command: str, params: dict = None, timeout: float = 300.0):
        """Make an RPC call that streams events."""
        if params is None:
            params = {}
        
        async for event in self.rpc.call_with_events(
            command,
            workspace=self.workspace,
            params=params,
            global_options=dict(self._global_options),
            timeout=timeout
        ):
            self._handle_event(event)
    
    def _handle_event(self, event: RPCEvent):
        """Handle an event from the server during streaming operations."""
        data = event.data or {}
        
        if event.type == EventType.OUTPUT:
            # Message is already formatted by the server's intercepted print
            # (includes [*] prefix and colors), so just print directly
            message = data.get('message', '')
            print(message)
        
        elif event.type == EventType.ALERT:
            # Already formatted by server
            print(data.get('message', ''))
        
        elif event.type == EventType.ERROR:
            # Already formatted by server
            print(data.get('message', 'Unknown error'))
        
        elif event.type == EventType.VERBOSE:
            # Already formatted by server
            print(data.get('message', ''))
        
        elif event.type == EventType.DEBUG:
            # Already formatted by server
            print(data.get('message', ''))
        
        elif event.type == EventType.TABLE:
            self.table(
                data.get('rows', []),
                header=data.get('header', []),
                title=data.get('title', '')
            )
        
        elif event.type == EventType.HEADING:
            self.heading(data.get('text', ''), level=data.get('level', 1))
        
        elif event.type == EventType.PROGRESS:
            current = data.get('current', 0)
            total = data.get('total', 100)
            message = data.get('message', '')
            pct = (current / total * 100) if total > 0 else 0
            print(f'\r[{pct:5.1f}%] {message}', end='', flush=True)
            if current >= total:
                print()
        
        elif event.type == EventType.INPUT_REQUIRED:
            # Handle input prompt from server - this is handled by rpc client
            pass
        
        elif event.type == EventType.EXCEPTION:
            self.print_exception()

    #==================================================
    # CMD OVERRIDE METHODS
    #==================================================

    def default(self, line):
        self.error(f"Invalid command: {line}")

    def emptyline(self):
        return 0

    def precmd(self, line):
        if AsyncFramework._load:
            print('\r', end='')
        if AsyncFramework._script:
            print(f"{line}")
        if AsyncFramework._record:
            recorder = codecs.open(AsyncFramework._record, 'ab', encoding='utf-8')
            recorder.write(f"{line}{os.linesep}")
            recorder.flush()
            recorder.close()
        if AsyncFramework._spool:
            AsyncFramework._spool.write(f"{self.prompt}{line}{os.linesep}")
            AsyncFramework._spool.flush()
        return line

    def onecmd(self, line):
        """Command handler that supports async commands."""
        cmd_word, arg, line = self.parseline(line)
        if not line:
            return self.emptyline()
        if line == 'EOF':
            sys.stdin = sys.__stdin__
            AsyncFramework._script = 0
            AsyncFramework._load = 0
            print('')
            return
        if cmd_word is None:
            return self.default(line)
        self.lastcmd = line
        if cmd_word == '':
            return self.default(line)
        # Handle '!' prefix for shell
        if line.startswith('!'):
            cmd_word = 'shell'
            arg = line[1:]
        
        # Execute command (sync or async)
        try:
            func = getattr(self, 'do_' + cmd_word)
        except AttributeError:
            self.default(f"{cmd_word} {arg}".strip())
            return
        try:
            if asyncio.iscoroutinefunction(func):
                return self._run_async(func(arg))
            else:
                return func(arg)
        except RPCClientError:
            # Error already displayed by _call
            pass
        except Exception:
            self.print_exception()

    def print_topics(self, header, cmds, cmdlen, maxcol):
        if cmds:
            self.stdout.write(f"{header}{os.linesep}")
            if self.ruler:
                self.stdout.write(f"{self.ruler * len(header)}{os.linesep}")
            for cmd_name in cmds:
                self.stdout.write(f"{cmd_name.ljust(15)} {getattr(self, 'do_' + cmd_name).__doc__}{os.linesep}")
            self.stdout.write(os.linesep)

    #==================================================
    # SUPPORT METHODS
    #==================================================

    def to_unicode_str(self, obj, encoding='utf-8'):
        if type(obj) not in (str, bytes):
            obj = str(obj)
        obj = self.to_unicode(obj, encoding)
        return obj

    def to_unicode(self, obj, encoding='utf-8'):
        if isinstance(obj, bytes):
            obj = obj.decode(encoding)
        return obj

    def is_hash(self, hashstr):
        hashdict = [
            {'pattern': r'^[a-fA-F0-9]{32}$', 'type': 'MD5'},
            {'pattern': r'^[a-fA-F0-9]{16}$', 'type': 'MySQL'},
            {'pattern': r'^\*[a-fA-F0-9]{40}$', 'type': 'MySQL5'},
            {'pattern': r'^[a-fA-F0-9]{40}$', 'type': 'SHA1'},
            {'pattern': r'^[a-fA-F0-9]{56}$', 'type': 'SHA224'},
            {'pattern': r'^[a-fA-F0-9]{64}$', 'type': 'SHA256'},
            {'pattern': r'^[a-fA-F0-9]{96}$', 'type': 'SHA384'},
            {'pattern': r'^[a-fA-F0-9]{128}$', 'type': 'SHA512'},
            {'pattern': r'^\$[PH]{1}\$.{31}$', 'type': 'phpass'},
            {'pattern': r'^\$2[ya]?\$.{56}$', 'type': 'bcrypt'},
        ]
        for hashitem in hashdict:
            if re.match(hashitem['pattern'], hashstr):
                return hashitem['type']
        return False

    def get_random_str(self, length):
        return ''.join(random.choice(string.ascii_lowercase) for i in range(length))

    def _is_writeable(self, filename):
        try:
            fp = open(filename, 'a')
            fp.close()
            return True
        except IOError:
            return False

    def _parse_rowids(self, rowids):
        xploded = []
        rowids = [x.strip() for x in rowids.split(',')]
        for rowid in rowids:
            try:
                if '-' in rowid:
                    start = int(rowid.split('-')[0].strip())
                    end = int(rowid.split('-')[-1].strip())
                    xploded += range(start, end+1)
                else:
                    xploded.append(int(rowid))
            except ValueError:
                continue
        return sorted(list(set(xploded)))

    def _parse_subcommands(self, command):
        subcommands = []
        for method in dir(self):
            if f"_do_{command}_" in method:
                subcommands.append(method.split('_')[-1])
        return subcommands

    def _parse_params(self, params):
        params = params.split()
        arg = ''
        if params:
            arg = params.pop(0)
        params = ' '.join(params)
        return arg, params

    #==================================================
    # OUTPUT METHODS
    #==================================================

    def print_exception(self, line=''):
        stack_list = [x.strip() for x in traceback.format_exc().strip().splitlines()]
        message = stack_list[-1].split(':', 1)[-1].strip()
        if self._global_options.get('VERBOSITY', 1) == 0:
            return
        elif self._global_options.get('VERBOSITY', 1) == 1:
            line = ' '.join([x for x in [message, line] if x])
            self.error(line)
        elif self._global_options.get('VERBOSITY', 1) >= 2:
            print(f"{Colors.R}{'-'*60}")
            traceback.print_exc()
            print(f"{'-'*60}{Colors.N}")

    def error(self, line):
        '''Formats and presents errors.'''
        line = str(line)
        if not re.search('[.,;!?]$', line):
            line += '.'
        line = line[:1].upper() + line[1:]
        print(f"{Colors.R}[!] {line}{Colors.N}")

    def output(self, line):
        '''Formats and presents normal output.'''
        print(f"{Colors.B}[*]{Colors.N} {line}")

    def alert(self, line):
        '''Formats and presents important output.'''
        print(f"{Colors.G}[*]{Colors.N} {line}")

    def verbose(self, line):
        '''Formats and presents output if in verbose mode.'''
        if self._global_options.get('VERBOSITY', 1) >= 1:
            self.output(line)

    def debug(self, line):
        '''Formats and presents output if in debug mode (very verbose).'''
        if self._global_options.get('VERBOSITY', 1) >= 2:
            self.output(line)

    def heading(self, line, level=1):
        '''Formats and presents styled header text'''
        print('')
        if level == 0:
            print(self.ruler*len(line))
            print(line.upper())
            print(self.ruler*len(line))
        if level == 1:
            print(f"{self.spacer}{line.title()}")
            print(f"{self.spacer}{self.ruler*len(line)}")

    def table(self, data, header=[], title=''):
        '''Accepts a list of rows and outputs a table.'''
        tdata = list(data)
        if header:
            tdata.insert(0, header)
        if not tdata:
            return
        if len(set([len(x) for x in tdata])) > 1:
            raise FrameworkException('Row lengths not consistent.')
        lens = []
        cols = len(tdata[0])
        for i in range(0, cols):
            lens.append(len(max([self.to_unicode_str(x[i]) if x[i] != None else '' for x in tdata], key=len)))
        title_len = len(title)
        tdata_len = sum(lens) + (3*(cols-1))
        diff = title_len - tdata_len
        if diff > 0:
            diff_per = diff / cols
            lens = [x+diff_per for x in lens]
            diff_mod = diff % cols
            for x in range(0, diff_mod):
                lens[x] += 1
        if len(tdata) > 0:
            separator_str = f"{self.spacer}+-{'%s---'*(cols-1)}%s-+"
            separator_sub = tuple(['-'*int(x) for x in lens])
            separator = separator_str % separator_sub
            data_str = f"{self.spacer}| {'%s | '*(cols-1)}%s |"
            print('')
            print(separator)
            if title:
                print(f"{self.spacer}| {title.center(tdata_len)} |")
                print(separator)
            if header:
                rdata = tdata.pop(0)
                data_sub = tuple([rdata[i].center(int(lens[i])) for i in range(0, cols)])
                print(data_str % data_sub)
                print(separator)
            for rdata in tdata:
                data_sub = tuple([self.to_unicode_str(rdata[i]).ljust(int(lens[i])) if rdata[i] != None else ''.ljust(int(lens[i])) for i in range(0, cols)])
                print(data_str % data_sub)
            print(separator)
            print('')

    def _list_options(self, options=None):
        '''Lists options'''
        if options is None:
            options = self.options
        if options:
            pattern = f"{self.spacer}%s  %s  %s  %s"
            key_len = len(max(options, key=len))
            if key_len < 4: key_len = 4
            val_len = len(max([self.to_unicode_str(options[x]) for x in options], key=len))
            if val_len < 13: val_len = 13
            print('')
            print(pattern % ('Name'.ljust(key_len), 'Current Value'.ljust(val_len), 'Required', 'Description'))
            print(pattern % (self.ruler*key_len, (self.ruler*13).ljust(val_len), self.ruler*8, self.ruler*11))
            for key in sorted(options):
                value = options[key] if options[key] != None else ''
                reqd = 'no' if options.required.get(key) is False else 'yes'
                desc = options.description.get(key, '')
                print(pattern % (key.ljust(key_len), self.to_unicode_str(value).ljust(val_len), self.to_unicode_str(reqd).ljust(8), desc))
            print('')
        else:
            print('')
            print(f"{self.spacer}No options available for this context.")
            print('')

    def _list_modules(self, modules):
        '''Lists modules in a formatted way'''
        if modules:
            key_len = len(max(modules, key=len)) + len(self.spacer)
            last_category = ''
            for module in sorted(modules):
                category = module.split('/')[0]
                if category != last_category:
                    last_category = category
                    self.heading(last_category)
                print(f"{self.spacer*2}{module}")
        else:
            print('')
            self.alert('No modules enabled/installed.')
        print('')

    #==================================================
    # CONFIG METHODS (client-side storage)
    #==================================================
    
    def _get_config_path(self):
        """Get path to config file in workspace."""
        # For client, we store config locally
        home = os.path.join(os.path.expanduser('~'), '.recon-ng')
        os.makedirs(home, exist_ok=True)
        return os.path.join(home, 'config.dat')
    
    def _load_config(self):
        """Load options from config file."""
        config_path = self._get_config_path()
        if os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    config_data = json.loads(f.read())
                for key in self.options:
                    try:
                        self.options[key] = config_data.get(self._modulename, {}).get(key)
                    except KeyError:
                        continue
            except (ValueError, IOError):
                pass
    
    def _save_config(self, name, module=None, options=None):
        """Save an option to config file."""
        config_path = self._get_config_path()
        try:
            with open(config_path) as f:
                config_data = json.loads(f.read())
        except (ValueError, IOError, FileNotFoundError):
            config_data = {}
        
        module = module or self._modulename
        options = options or self.options
        
        if module not in config_data:
            config_data[module] = {}
        config_data[module][name] = options[name]
        if config_data[module][name] is None:
            del config_data[module][name]
        if not config_data[module]:
            del config_data[module]
        
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=4)

    #==================================================
    # COMMAND METHODS
    #==================================================

    def do_exit(self, params):
        '''Exits the framework'''
        self._exit = 1
        return True

    def do_back(self, params):
        '''Exits the current context'''
        return True

    def do_options(self, params):
        '''Manages the current context options'''
        if not params:
            self.help_options()
            return
        arg, params = self._parse_params(params)
        if arg in self._parse_subcommands('options'):
            return getattr(self, '_do_options_'+arg)(params)
        else:
            self.help_options()

    def _do_options_list(self, params):
        '''Shows the current context options'''
        self._list_options()

    def _do_options_set(self, params):
        '''Sets a current context option'''
        option, value = self._parse_params(params)
        if not (option and value):
            self._help_options_set()
            return
        name = option.upper()
        if name in self.options:
            self.options[name] = value
            print(f"{name} => {value}")
            self._save_config(name)
        else:
            self.error('Invalid option name.')

    def _do_options_unset(self, params):
        '''Unsets a current context option'''
        option, value = self._parse_params(params)
        if not option:
            self._help_options_unset()
            return
        name = option.upper()
        if name in self.options:
            self._do_options_set(' '.join([name, 'None']))
        else:
            self.error('Invalid option name.')

    async def do_keys(self, params):
        '''Manages third party resource credentials'''
        if not params:
            self.help_keys()
            return
        arg, params = self._parse_params(params)
        if arg in self._parse_subcommands('keys'):
            return await getattr(self, '_do_keys_'+arg)(params)
        else:
            self.help_keys()

    async def _do_keys_list(self, params):
        '''Lists third party resource credentials'''
        result = await self._call(Commands.KEYS_LIST)
        keys = result.get('keys', [])
        if keys:
            tdata = [[k['name'], k['value'] or ''] for k in keys]
            self.table(tdata, header=['Name', 'Value'])
        else:
            self.output('No keys found.')

    async def _do_keys_add(self, params):
        '''Adds/Updates a third party resource credential'''
        key, value = self._parse_params(params)
        if not (key and value):
            self._help_keys_add()
            return
        await self._call(Commands.KEYS_ADD, {'name': key, 'value': value})
        self.output(f"Key '{key}' added.")

    async def _do_keys_remove(self, params):
        '''Removes a third party resource credential'''
        key, value = self._parse_params(params)
        if not key:
            self._help_keys_remove()
            return
        result = await self._call(Commands.KEYS_GET, {'name': key})
        if result.get('value') is not None:
            await self._call(Commands.KEYS_DELETE, {'name': key})
            self.output(f"Key '{key}' removed.")
        else:
            self.error('Invalid key name.')

    def do_modules(self, params):
        '''Interfaces with installed modules'''
        if not params:
            self.help_modules()
            return
        arg, params = self._parse_params(params)
        if arg in self._parse_subcommands('modules'):
            func = getattr(self, '_do_modules_'+arg)
            if asyncio.iscoroutinefunction(func):
                return self._run_async(func(params))
            else:
                return func(params)
        else:
            self.help_modules()

    async def _do_modules_search(self, params):
        '''Searches installed modules'''
        result = await self._call(Commands.MODULES_LIST)
        modules = [m['path'] for m in result.get('modules', [])]
        if params:
            self.output(f"Searching installed modules for '{params}'...")
            modules = [x for x in modules if re.search(params, x)]
        if modules:
            self._list_modules(modules)
        else:
            self.error('No modules found.')
            self._help_modules_search()

    def _do_modules_load(self, params):
        '''Loads a module'''
        # This is overridden in base.py to handle module context
        raise NotImplementedError

    async def do_show(self, params):
        '''Shows various framework items'''
        if not params:
            self.help_show()
            return
        arg, params = self._parse_params(params)
        show_names = self._get_show_names()
        tables = await self._get_tables()
        if arg in show_names:
            getattr(self, 'show_' + arg)()
        elif arg in tables:
            await self.do_db(f"query SELECT ROWID, * FROM `{arg}`")
        else:
            self.help_show()

    def _get_show_names(self):
        prefix = 'show_'
        return [x[len(prefix):] for x in self.get_names() if x.startswith(prefix)]

    async def _get_tables(self):
        """Get list of tables from server."""
        if self._tables_cache is None:
            try:
                result = await self._call(Commands.DB_TABLES)
                self._tables_cache = result.get('tables', [])
            except RPCClientError:
                self._tables_cache = []
        return self._tables_cache

    def _clear_tables_cache(self):
        """Clear tables cache (e.g., when workspace changes)."""
        self._tables_cache = None

    async def do_db(self, params):
        '''Interfaces with the workspace's database'''
        if not params:
            self.help_db()
            return
        arg, params = self._parse_params(params)
        if arg in self._parse_subcommands('db'):
            return await getattr(self, '_do_db_'+arg)(params)
        else:
            self.help_db()

    async def _do_db_notes(self, params):
        '''Adds notes to rows in the database'''
        table, params = self._parse_params(params)
        if not table:
            self._help_db_notes()
            return
        tables = await self._get_tables()
        if table in tables:
            if params:
                arg, note = self._parse_params(params)
                rowids = self._parse_rowids(arg)
            else:
                try:
                    params = input('rowid(s) (INT): ')
                    rowids = self._parse_rowids(params)
                    note = input('note (TXT): ')
                except KeyboardInterrupt:
                    print('')
                    return
                finally:
                    if AsyncFramework._script:
                        print(f"{params}")
            result = await self._call(Commands.DB_NOTES, {
                'table': table,
                'rowids': rowids,
                'note': note
            })
            self.output(f"{result.get('affected', 0)} rows affected.")
        else:
            self.output('Invalid table name.')

    async def _do_db_insert(self, params):
        '''Inserts a row into the database'''
        table, params = self._parse_params(params)
        if not table:
            self._help_db_insert()
            return
        tables = await self._get_tables()
        if table in tables:
            # Get columns from server
            result = await self._call(Commands.DB_SCHEMA, {'table': table})
            columns = [(c['name'], c['type']) for c in result.get('columns', []) if c['name'] != 'module']
            if not columns:
                self.error('Cannot add records to this table.')
                return
            
            record = {}
            if params:
                values = params.split('~')
                if len(columns) == len(values):
                    for i in range(0, len(columns)):
                        col_name = columns[i][0]
                        if col_name in ['hash', 'type']:
                            col_name = '_' + col_name
                        record[col_name] = values[i]
                else:
                    self.error('Columns and values length mismatch.')
                    return
            else:
                for column in columns:
                    try:
                        value = input(f"{column[0]} ({column[1]}): ")
                        col_name = column[0]
                        if col_name in ['hash', 'type']:
                            col_name = '_' + col_name
                        record[col_name] = value
                    except KeyboardInterrupt:
                        print('')
                        return
                    finally:
                        if AsyncFramework._script:
                            print(f"{value}")
            
            result = await self._call(Commands.DB_INSERT, {
                'table': table,
                'data': record
            })
            self.output(f"{result.get('affected', 0)} rows affected.")
        else:
            self.output('Invalid table name.')

    async def _do_db_delete(self, params):
        '''Deletes a row from the database'''
        table, params = self._parse_params(params)
        if not table:
            self._help_db_delete()
            return
        tables = await self._get_tables()
        if table in tables:
            if params:
                rowids = self._parse_rowids(params)
            else:
                try:
                    params = input('rowid(s) (INT): ')
                    rowids = self._parse_rowids(params)
                except KeyboardInterrupt:
                    print('')
                    return
                finally:
                    if AsyncFramework._script:
                        print(f"{params}")
            result = await self._call(Commands.DB_DELETE, {
                'table': table,
                'rowids': rowids
            })
            self.output(f"{result.get('affected', 0)} rows affected.")
        else:
            self.output('Invalid table name.')

    async def _do_db_query(self, params):
        '''Queries the database with custom SQL'''
        if not params:
            self._help_db_query()
            return
        try:
            result = await self._call(Commands.DB_QUERY, {'sql': params})
            if 'rows' in result:
                rows = result['rows']
                header = result.get('header', [])
                if not rows:
                    self.output('No data returned.')
                else:
                    self.table(rows, header=header)
                    self.output(f"{len(rows)} rows returned")
            else:
                self.output(f"{result.get('affected', 0)} rows affected.")
        except RPCClientError as e:
            self.error(f"Invalid query. {e}")

    async def _do_db_schema(self, params):
        '''Displays the database schema'''
        tables = await self._get_tables()
        for table in tables:
            result = await self._call(Commands.DB_SCHEMA, {'table': table})
            columns = [(c['name'], c['type']) for c in result.get('columns', [])]
            self.table(columns, title=table)

    def do_script(self, params):
        '''Records and executes command scripts'''
        if not params:
            self.help_script()
            return
        arg, params = self._parse_params(params)
        if arg in self._parse_subcommands('script'):
            return getattr(self, '_do_script_'+arg)(params)
        else:
            self.help_script()

    def _do_script_record(self, params):
        '''Records commands in a script file'''
        if not AsyncFramework._record:
            filename, params = self._parse_params(params)
            if not filename:
                self._help_script_record()
                return
            if not self._is_writeable(filename):
                self.output(f"Cannot record commands to '{filename}'.")
            else:
                AsyncFramework._record = filename
                self.output(f"Recording commands to '{AsyncFramework._record}'.")
        else:
            self.output('Recording is already started.')

    def _do_script_stop(self, params):
        '''Stops command recording'''
        if AsyncFramework._record:
            self.output(f"Recording stopped. Commands saved to '{AsyncFramework._record}'.")
            AsyncFramework._record = None
        else:
            self.output('Recording is already stopped.')

    def _do_script_status(self, params):
        '''Provides the status of command recording'''
        status = 'started' if AsyncFramework._record else 'stopped'
        self.output(f"Command recording is {status}.")

    def _do_script_execute(self, params):
        '''Executes commands from a script file'''
        if not params:
            self._help_script_execute()
            return
        if os.path.exists(params):
            sys.stdin = open(params)
            AsyncFramework._script = 1
        else:
            self.error(f"Script file '{params}' not found.")

    def do_spool(self, params):
        '''Spools output to a file'''
        if not params:
            self.help_spool()
            return
        arg, params = self._parse_params(params)
        if arg in self._parse_subcommands('spool'):
            return getattr(self, '_do_spool_'+arg)(params)
        else:
            self.help_spool()

    def _do_spool_start(self, params):
        '''Starts output spooling'''
        if not AsyncFramework._spool:
            filename, params = self._parse_params(params)
            if not filename:
                self._help_spool_start()
                return
            if not self._is_writeable(filename):
                self.output(f"Cannot spool output to '{filename}'.")
            else:
                AsyncFramework._spool = codecs.open(filename, 'ab', encoding='utf-8')
                self.output(f"Spooling output to '{AsyncFramework._spool.name}'.")
        else:
            self.output('Spooling is already started.')

    def _do_spool_stop(self, params):
        '''Stops output spooling'''
        if AsyncFramework._spool:
            self.output(f"Spooling stopped. Output saved to '{AsyncFramework._spool.name}'.")
            AsyncFramework._spool = None
        else:
            self.output('Spooling is already stopped.')

    def _do_spool_status(self, params):
        '''Provides the status of output spooling'''
        status = 'started' if AsyncFramework._spool else 'stopped'
        self.output(f"Output spooling is {status}.")

    def do_shell(self, params):
        '''Executes shell commands'''
        if not params:
            self.help_shell()
            return
        proc = subprocess.Popen(params, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        self.output(f"Command: {params}")
        stdout = proc.stdout.read()
        stderr = proc.stderr.read()
        if stdout: print(f"{Colors.O}{self.to_unicode(stdout)}{Colors.N}", end='')
        if stderr: print(f"{Colors.R}{self.to_unicode(stderr)}{Colors.N}", end='')

    async def do_dashboard(self, params):
        '''Displays a summary of activity'''
        try:
            result = await self._call(Commands.DASHBOARD_SHOW)
            activity = result.get('activity', [])
            summary = result.get('summary', [])
            
            if activity:
                self.table(activity, header=['Module', 'Runs'], title='Activity Summary')
                self.table(summary, header=['Category', 'Quantity'], title='Results Summary')
            else:
                self.output('This workspace has no record of activity.')
        except RPCClientError:
            pass

    def do_pdb(self, params):
        '''Starts a Python Debugger session (dev only)'''
        import pdb
        pdb.set_trace()

    #==================================================
    # HELP METHODS
    #==================================================

    def help_options(self):
        print(getattr(self, 'do_options').__doc__)
        print(f"{os.linesep}Usage: options <{'|'.join(self._parse_subcommands('options'))}> [...]{os.linesep}")

    def _help_options_set(self):
        print(getattr(self, '_do_options_set').__doc__)
        print(f"{os.linesep}Usage: options set <option> <value>{os.linesep}")

    def _help_options_unset(self):
        print(getattr(self, '_do_options_unset').__doc__)
        print(f"{os.linesep}Usage: options unset <option>{os.linesep}")

    def help_keys(self):
        print(getattr(self, 'do_keys').__doc__)
        print(f"{os.linesep}Usage: keys <{'|'.join(self._parse_subcommands('keys'))}> [...]{os.linesep}")

    def _help_keys_add(self):
        print(getattr(self, '_do_keys_add').__doc__)
        print(f"{os.linesep}Usage: keys add <name> <value>{os.linesep}")

    def _help_keys_remove(self):
        print(getattr(self, '_do_keys_remove').__doc__)
        print(f"{os.linesep}Usage: keys remove <name>{os.linesep}")

    def help_modules(self):
        print(getattr(self, 'do_modules').__doc__)
        print(f"{os.linesep}Usage: modules <{'|'.join(self._parse_subcommands('modules'))}> [...]{os.linesep}")

    def _help_modules_search(self):
        print(getattr(self, '_do_modules_search').__doc__)
        print(f"{os.linesep}Usage: modules search [<regex>]{os.linesep}")

    def _help_modules_load(self):
        print("Loads a module")
        print(f"{os.linesep}Usage: modules load <path>{os.linesep}")

    async def help_show(self):
        tables = await self._get_tables()
        options = sorted(self._get_show_names() + tables)
        print(getattr(self, 'do_show').__doc__)
        print(f"{os.linesep}Usage: show <{'|'.join(options)}>{os.linesep}")

    def help_db(self):
        print(getattr(self, 'do_db').__doc__)
        print(f"{os.linesep}Usage: db <{'|'.join(self._parse_subcommands('db'))}> [...]{os.linesep}")

    def _help_db_notes(self):
        print(getattr(self, '_do_db_notes').__doc__)
        print(f"{os.linesep}Usage: db notes <table> [<rowid(s)> <note>]{os.linesep}")
        print(f"rowid(s) => ',' delimited values or '-' delimited ranges representing rowids{os.linesep}")

    def _help_db_insert(self):
        print(getattr(self, '_do_db_insert').__doc__)
        print(f"{os.linesep}Usage: db insert <table> [<values>]{os.linesep}")
        print(f"values => '~' delimited string representing column values (exclude rowid, module){os.linesep}")

    def _help_db_delete(self):
        print(getattr(self, '_do_db_delete').__doc__)
        print(f"{os.linesep}Usage: db delete <table> [<rowid(s)>]{os.linesep}")
        print(f"rowid(s) => ',' delimited values or '-' delimited ranges representing rowids{os.linesep}")

    def _help_db_query(self):
        print(getattr(self, '_do_db_query').__doc__)
        print(f"{os.linesep}Usage: db query <sql>{os.linesep}")

    def help_script(self):
        print(getattr(self, 'do_script').__doc__)
        print(f"{os.linesep}Usage: script <{'|'.join(self._parse_subcommands('script'))}> [...]{os.linesep}")

    def _help_script_record(self):
        print(getattr(self, '_do_script_record').__doc__)
        print(f"{os.linesep}Usage: script record <filename>{os.linesep}")

    def _help_script_execute(self):
        print(getattr(self, '_do_script_execute').__doc__)
        print(f"{os.linesep}Usage: script execute <filename>{os.linesep}")

    def help_spool(self):
        print(getattr(self, 'do_spool').__doc__)
        print(f"{os.linesep}Usage: spool <{'|'.join(self._parse_subcommands('spool'))}> [...]{os.linesep}")

    def _help_spool_start(self):
        print(getattr(self, '_do_spool_start').__doc__)
        print(f"{os.linesep}Usage: spool start <filename>{os.linesep}")

    def help_shell(self):
        print(getattr(self, 'do_shell').__doc__)
        print(f"{os.linesep}Usage: [shell|!] <command>{os.linesep}")

    #==================================================
    # COMPLETE METHODS
    #==================================================

    def complete_options(self, text, line, *ignored):
        arg, params = self._parse_params(line.split(' ', 1)[1])
        subs = self._parse_subcommands('options')
        if arg in subs:
            return getattr(self, '_complete_options_'+arg)(text, params)
        return [sub for sub in subs if sub.startswith(text)]

    def _complete_options_list(self, text, *ignored):
        return []

    def _complete_options_set(self, text, *ignored):
        return [x for x in self.options if x.startswith(text.upper())]
    _complete_options_unset = _complete_options_set

    def complete_keys(self, text, line, *ignored):
        arg, params = self._parse_params(line.split(' ', 1)[1])
        subs = self._parse_subcommands('keys')
        if arg in subs:
            return getattr(self, '_complete_keys_'+arg)(text, params)
        return [sub for sub in subs if sub.startswith(text)]

    def _complete_keys_list(self, text, *ignored):
        return []

    def _complete_keys_add(self, text, *ignored):
        # Would need to cache keys list for completion
        return []
    _complete_keys_remove = _complete_keys_add

    def complete_modules(self, text, line, *ignored):
        arg, params = self._parse_params(line.split(' ', 1)[1])
        subs = self._parse_subcommands('modules')
        if arg in subs:
            return getattr(self, '_complete_modules_'+arg)(text, params)
        return [sub for sub in subs if sub.startswith(text)]

    def _complete_modules_search(self, text, *ignored):
        return []

    def _complete_modules_load(self, text, *ignored):
        return [x for x in AsyncFramework._loaded_modules if x.startswith(text)]

    def complete_show(self, text, line, *ignored):
        # Can't do async completion, use cached tables
        tables = self._tables_cache or []
        options = sorted(self._get_show_names() + tables)
        return [x for x in options if x.startswith(text)]

    def complete_db(self, text, line, *ignored):
        arg, params = self._parse_params(line.split(' ', 1)[1])
        subs = self._parse_subcommands('db')
        if arg in subs:
            return getattr(self, '_complete_db_'+arg)(text, params)
        return [sub for sub in subs if sub.startswith(text)]

    def _complete_db_insert(self, text, *ignored):
        return [x for x in sorted(self._tables_cache or []) if x.startswith(text)]
    _complete_db_notes = _complete_db_delete = _complete_db_insert

    def _complete_db_query(self, text, *ignored):
        return []
    _complete_db_schema = _complete_db_query

    def complete_script(self, text, line, *ignored):
        arg, params = self._parse_params(line.split(' ', 1)[1])
        subs = self._parse_subcommands('script')
        if arg in subs:
            return getattr(self, '_complete_script_'+arg)(text, params)
        return [sub for sub in subs if sub.startswith(text)]

    def _complete_script_record(self, text, *ignored):
        return []
    _complete_script_execute = _complete_script_status = _complete_script_stop = _complete_script_record

    def complete_spool(self, text, line, *ignored):
        arg, params = self._parse_params(line.split(' ', 1)[1])
        subs = self._parse_subcommands('spool')
        if arg in subs:
            return getattr(self, '_complete_spool_'+arg)(text, params)
        return [sub for sub in subs if sub.startswith(text)]

    def _complete_spool_start(self, text, *ignored):
        return []
    _complete_spool_status = _complete_spool_stop = _complete_spool_start
