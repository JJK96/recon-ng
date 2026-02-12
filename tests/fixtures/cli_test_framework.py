"""
Test Framework with CLI Methods

This module provides a TestFramework class that combines:
- The business logic from recon.core.framework.Framework
- The CLI interface from cmd.Cmd
- All do_*, help_*, complete_* methods for testing

This allows CLI command tests to work synchronously without RPC/server.
"""
import cmd
import codecs
import json
import os
import re
import subprocess
import sys
import traceback

from recon.core.framework import Framework, Colors, Options, FrameworkException


class TestFramework(Framework, cmd.Cmd):
    """
    Test-friendly Framework class that combines CLI with direct business logic.
    
    This class is used for unit testing CLI commands without needing
    async operations or an RPC server.
    """
    prompt = '>>>'
    
    def __init__(self, params='test'):
        # Initialize Framework (business logic)
        Framework.__init__(self, params)
        # Initialize cmd.Cmd (CLI interface)
        cmd.Cmd.__init__(self)
        
        self.ruler = '-'
        self.spacer = '  '
        self.nohelp = f"{Colors.R}[!] No help on %s{Colors.N}"
        self.do_help.__func__.__doc__ = '''Displays this menu'''
        self.doc_header = 'Commands (type [help|?] <topic>):'
        
        # Context options
        self.options = Options()
    
    #==================================================
    # SUPPORT METHODS
    #==================================================
    
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
    # CMD.CMD OVERRIDE METHODS
    #==================================================

    def default(self, line):
        self.error(f"Invalid command: {line}")

    def emptyline(self):
        return 0

    def precmd(self, line):
        if Framework._load:
            print('\r', end='')
        if Framework._script:
            print(f"{line}")
        if Framework._record:
            recorder = codecs.open(Framework._record, 'ab', encoding='utf-8')
            recorder.write(f"{line}{os.linesep}")
            recorder.flush()
            recorder.close()
        if Framework._spool:
            Framework._spool.write(f"{self.prompt}{line}{os.linesep}")
            Framework._spool.flush()
        return line

    def onecmd(self, line):
        """Command handler that handles exceptions."""
        cmd_word, arg, line = self.parseline(line)
        if not line:
            return self.emptyline()
        if line == 'EOF':
            sys.stdin = sys.__stdin__
            Framework._script = 0
            Framework._load = 0
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
        
        # Execute command
        try:
            func = getattr(self, 'do_' + cmd_word)
        except AttributeError:
            self.default(f"{cmd_word} {arg}".strip())
            return
        try:
            return func(arg)
        except Exception:
            self.print_exception()

    #==================================================
    # OUTPUT METHODS (Print to stdout for tests)
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
    # CONFIG METHODS
    #==================================================
    
    def _get_config_path(self):
        """Get path to config file in workspace."""
        return os.path.join(self.workspace, 'config.dat')
    
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
    
    def _save_config(self, name=None, module=None, options=None):
        """Save an option to config file."""
        if name is None:
            return
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

    def do_keys(self, params):
        '''Manages third party resource credentials'''
        if not params:
            self.help_keys()
            return
        arg, params = self._parse_params(params)
        if arg in self._parse_subcommands('keys'):
            return getattr(self, '_do_keys_'+arg)(params)
        else:
            self.help_keys()

    def _do_keys_list(self, params):
        '''Lists third party resource credentials'''
        keys = self.get_keys()
        if keys:
            tdata = [[k['name'], k['value'] or ''] for k in keys]
            self.table(tdata, header=['Name', 'Value'])
        else:
            self.output('No keys found.')
    
    def get_keys(self):
        '''Returns all API keys as list of dicts with name and value.'''
        rows = self._query_keys('SELECT name, value FROM keys WHERE value IS NOT NULL')
        return [{'name': row[0], 'value': row[1]} for row in rows]
    
    def delete_key(self, name):
        '''Deletes an API key. Alias for remove_key.'''
        return self.remove_key(name)

    def _do_keys_add(self, params):
        '''Adds/Updates a third party resource credential'''
        key, value = self._parse_params(params)
        if not (key and value):
            self._help_keys_add()
            return
        self.add_key(key, value)
        self.output(f"Key '{key}' added.")

    def _do_keys_remove(self, params):
        '''Removes a third party resource credential'''
        key, value = self._parse_params(params)
        if not key:
            self._help_keys_remove()
            return
        if self.get_key(key):
            self.delete_key(key)
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
            return getattr(self, '_do_modules_'+arg)(params)
        else:
            self.help_modules()

    def _do_modules_search(self, params):
        '''Searches installed modules'''
        modules = list(self._loaded_modules.keys())
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
        # This is overridden by subclasses (TestRecon)
        raise NotImplementedError

    def do_show(self, params):
        '''Shows various framework items'''
        if not params:
            self.help_show()
            return
        arg, params = self._parse_params(params)
        show_names = self._get_show_names()
        tables = self.get_tables()
        if arg in show_names:
            getattr(self, 'show_' + arg)()
        elif arg in tables:
            self.do_db(f"query SELECT ROWID, * FROM `{arg}`")
        else:
            self.help_show()

    def _get_show_names(self):
        prefix = 'show_'
        return [x[len(prefix):] for x in self.get_names() if x.startswith(prefix)]

    def do_db(self, params):
        '''Interfaces with the workspace's database'''
        if not params:
            self.help_db()
            return
        arg, params = self._parse_params(params)
        if arg in self._parse_subcommands('db'):
            return getattr(self, '_do_db_'+arg)(params)
        else:
            self.help_db()

    def _do_db_notes(self, params):
        '''Adds notes to rows in the database'''
        table, params = self._parse_params(params)
        if not table:
            self._help_db_notes()
            return
        tables = self.get_tables()
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
            # Update notes
            affected = 0
            for rowid in rowids:
                affected += self.query(f"UPDATE `{table}` SET notes = ? WHERE ROWID = ?", (note, rowid))
            self.output(f"{affected} rows affected.")
        else:
            self.output('Invalid table name.')

    def _do_db_insert(self, params):
        '''Inserts a row into the database'''
        table, params = self._parse_params(params)
        if not table:
            self._help_db_insert()
            return
        tables = self.get_tables()
        if table in tables:
            # Get columns
            columns = [(c[0], c[1]) for c in self.get_columns(table) if c[0] != 'module']
            if not columns:
                self.error('Cannot add records to this table.')
                return
            
            if params:
                values = params.split('~')
                if len(columns) == len(values):
                    col_names = [c[0] for c in columns]
                    placeholders = ','.join(['?' for _ in columns])
                    query = f"INSERT INTO `{table}` ({','.join(col_names)}) VALUES ({placeholders})"
                    affected = self.query(query, tuple(values))
                    self.output(f"{affected} rows affected.")
                else:
                    self.error('Columns and values length mismatch.')
            else:
                values = []
                for column in columns:
                    try:
                        value = input(f"{column[0]} ({column[1]}): ")
                        values.append(value)
                    except KeyboardInterrupt:
                        print('')
                        return
                col_names = [c[0] for c in columns]
                placeholders = ','.join(['?' for _ in columns])
                query = f"INSERT INTO `{table}` ({','.join(col_names)}) VALUES ({placeholders})"
                affected = self.query(query, tuple(values))
                self.output(f"{affected} rows affected.")
        else:
            self.output('Invalid table name.')

    def _do_db_delete(self, params):
        '''Deletes a row from the database'''
        table, params = self._parse_params(params)
        if not table:
            self._help_db_delete()
            return
        tables = self.get_tables()
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
            # Delete rows
            affected = 0
            for rowid in rowids:
                affected += self.query(f"DELETE FROM `{table}` WHERE ROWID = ?", (rowid,))
            self.output(f"{affected} rows affected.")
        else:
            self.output('Invalid table name.')

    def _do_db_query(self, params):
        '''Queries the database with custom SQL'''
        if not params:
            self._help_db_query()
            return
        try:
            results = self.query(params, include_header=True)
            if isinstance(results, list):
                if len(results) <= 1:  # Only header or empty
                    self.output('No data returned.')
                else:
                    header = list(results[0])
                    rows = results[1:]
                    self.table(rows, header=header)
                    self.output(f"{len(rows)} rows returned")
            else:
                self.output(f"{results} rows affected.")
        except Exception as e:
            self.error(f"Invalid query. {e}")

    def _do_db_schema(self, params):
        '''Displays the database schema'''
        tables = self.get_tables()
        for table in tables:
            columns = self.get_columns(table)
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
        if not Framework._record:
            filename, params = self._parse_params(params)
            if not filename:
                self._help_script_record()
                return
            if not self._is_writeable(filename):
                self.output(f"Cannot record commands to '{filename}'.")
            else:
                Framework._record = filename
                self.output(f"Recording commands to '{Framework._record}'.")
        else:
            self.output('Recording is already started.')

    def _do_script_stop(self, params):
        '''Stops command recording'''
        if Framework._record:
            self.output(f"Recording stopped. Commands saved to '{Framework._record}'.")
            Framework._record = None
        else:
            self.output('Recording is already stopped.')

    def _do_script_status(self, params):
        '''Provides the status of command recording'''
        status = 'started' if Framework._record else 'stopped'
        self.output(f"Command recording is {status}.")

    def _do_script_execute(self, params):
        '''Executes commands from a script file'''
        if not params:
            self._help_script_execute()
            return
        if os.path.exists(params):
            sys.stdin = open(params)
            Framework._script = 1
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
        if not Framework._spool:
            filename, params = self._parse_params(params)
            if not filename:
                self._help_spool_start()
                return
            if not self._is_writeable(filename):
                self.output(f"Cannot spool output to '{filename}'.")
            else:
                Framework._spool = codecs.open(filename, 'ab', encoding='utf-8')
                self.output(f"Spooling output to '{Framework._spool.name}'.")
        else:
            self.output('Spooling is already started.')

    def _do_spool_stop(self, params):
        '''Stops output spooling'''
        if Framework._spool:
            self.output(f"Spooling stopped. Output saved to '{Framework._spool.name}'.")
            Framework._spool = None
        else:
            self.output('Spooling is already stopped.')

    def _do_spool_status(self, params):
        '''Provides the status of output spooling'''
        status = 'started' if Framework._spool else 'stopped'
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

    def do_dashboard(self, params):
        '''Displays a summary of activity'''
        # Get activity from dashboard table
        try:
            activity = self.query('SELECT module, runs FROM dashboard ORDER BY runs DESC')
            if activity:
                self.table(activity, header=['Module', 'Runs'], title='Activity Summary')
                # Get summary counts for each table
                summary = []
                for table in self.get_tables():
                    count = self.query(f'SELECT COUNT(*) FROM `{table}`')[0][0]
                    if count > 0:
                        summary.append((table.title(), count))
                if summary:
                    self.table(summary, header=['Category', 'Quantity'], title='Results Summary')
            else:
                self.output('This workspace has no record of activity.')
        except Exception:
            self.output('This workspace has no record of activity.')

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

    def help_show(self):
        tables = self.get_tables()
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
        return [x for x in self._loaded_modules if x.startswith(text)]

    def complete_show(self, text, line, *ignored):
        tables = self.get_tables()
        options = sorted(self._get_show_names() + tables)
        return [x for x in options if x.startswith(text)]

    def complete_db(self, text, line, *ignored):
        arg, params = self._parse_params(line.split(' ', 1)[1])
        subs = self._parse_subcommands('db')
        if arg in subs:
            return getattr(self, '_complete_db_'+arg)(text, params)
        return [sub for sub in subs if sub.startswith(text)]

    def _complete_db_insert(self, text, *ignored):
        return [x for x in sorted(self.get_tables()) if x.startswith(text)]
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


class TestModuleMixin:
    """
    Mixin that provides module CLI methods for testing.
    
    This mixin should be inherited by mock modules to provide
    the do_*, help_*, and complete_* methods for module-level commands.
    
    Example usage:
        class MockModule(TestModuleMixin, BaseModule):
            meta = {...}
    """
    
    # Module-specific flags
    _reload = 0
    
    # Output settings
    ruler = '-'
    spacer = '  '
    
    #==================================================
    # OUTPUT METHODS (for testing)
    #==================================================
    
    def error(self, line):
        '''Formats and presents errors.'''
        import re
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
    
    def print_exception(self, line=''):
        import traceback
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
    
    def _print_summary(self):
        '''Prints the summary of results.'''
        if not hasattr(self, '_summary_counts') or not self._summary_counts:
            return
        print('')
        print('-------')
        print('SUMMARY')
        print('-------')
        for table, counts in sorted(self._summary_counts.items()):
            new = counts.get('new', 0)
            cnt = counts.get('count', 0)
            print(f"{table}: {cnt} total ({new} new)")
        print('')
    
    #==================================================
    # COMMAND METHODS
    #==================================================
    
    def do_info(self, params):
        '''Shows details about the loaded module'''
        import textwrap
        spacer = '  '
        
        print('')
        
        # Meta info
        for item in ['name', 'author', 'version']:
            value = self.meta.get(item, '')
            print(f"{item.title().rjust(10)}: {value}")
        
        # Required keys
        if self.meta.get('required_keys'):
            keys_str = ', '.join(self.meta.get('required_keys', []))
            print(f"{'keys'.title().rjust(10)}: {keys_str}")
        
        print('')
        
        # Description
        print('Description:')
        description = self.meta.get('description', '')
        print(f"{spacer}{textwrap.fill(description, 100, subsequent_indent=spacer)}")
        print('')
        
        # Options
        print('Options:', end='')
        self._list_options()
        
        # Sources
        if self.meta.get('query'):
            print('Source Options:')
            print(f"{spacer}{'default'.ljust(15)}{self.meta.get('query')}")
            print(f"{spacer}{'<string>'.ljust(15)}string representing a single input")
            print(f"{spacer}{'<path>'.ljust(15)}path to a file containing a list of inputs")
            print(f"{spacer}{'query <sql>'.ljust(15)}database query returning one column of inputs")
            print('')
        
        # Comments
        if self.meta.get('comments'):
            print('Comments:')
            for comment in self.meta.get('comments', []):
                prefix = '* '
                if comment.startswith('\t'):
                    prefix = spacer + '- '
                    comment = comment[1:]
                print(f"{spacer}{textwrap.fill(prefix + comment, 100, subsequent_indent=spacer)}")
            print('')
    
    def do_input(self, params):
        '''Shows inputs based on the source option'''
        if not self.meta.get('query'):
            self.output('Source option not available for this module.')
            return
        
        try:
            source = self.options.get('SOURCE', 'default')
            query = self.meta.get('query')
            inputs = self._get_source(source, query)
            if inputs:
                rows = [[x] if not isinstance(x, (list, tuple)) else list(x) for x in inputs]
                self.table(rows, header=['Module Inputs'])
            else:
                self.output('Source contains no input.')
        except Exception as e:
            self.error(str(e))
    
    def do_run(self, params):
        '''Runs the loaded module'''
        try:
            self.run()
        except KeyboardInterrupt:
            print('')
            self.output('Module execution interrupted.')
        except Exception as e:
            self.print_exception()
        finally:
            # Print summary
            if hasattr(self, '_summary_counts') and self._summary_counts:
                self._print_summary()
    
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
        '''Loads a different module'''
        if not params:
            self._help_modules_load()
            return
        
        # Match modules
        modules = [x for x in self._loaded_modules if params in x]
        
        if not modules:
            self.error('Invalid module path.')
            return None
        elif len(modules) > 1:
            self.output(f"Multiple modules matched. Please be more specific.")
            for module in sorted(modules):
                print(f"  {module}")
            return None
        else:
            # Single match - return True to indicate transition
            return True
    
    def _parse_params(self, params):
        params = params.split()
        arg = ''
        if params:
            arg = params.pop(0)
        params = ' '.join(params)
        return arg, params
    
    def _parse_subcommands(self, command):
        subcommands = []
        for method in dir(self):
            if f"_do_{command}_" in method:
                subcommands.append(method.split('_')[-1])
        return subcommands
    
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
    
    def _help_modules_load(self):
        print("Loads a module")
        print(f"{os.linesep}Usage: modules load <path>{os.linesep}")
    
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


class TestReconMixin:
    """
    Mixin that provides Recon-level CLI methods for testing.
    
    This mixin should be inherited by test Recon instances to provide
    the do_*, help_*, and complete_* methods for Recon-level commands
    (workspaces, snapshots, marketplace, modules load/reload, index).
    
    Example usage:
        class TestRecon(TestReconMixin, Recon):
            pass
    """
    
    # Caches for completion
    _workspaces_cache = []
    _snapshots_cache = []
    _marketplace = True
    
    # Client-level attributes
    _prompt_template = '{}[{}] > '
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._base_prompt = self._prompt_template.format('', self._name)
    
    #==================================================
    # BANNER AND MENU METHODS (client-level)
    #==================================================
    
    def _print_banner(self):
        """Print the startup banner."""
        import random
        banner_lines = [
            "    _/_/_/    _/_/_/_/    _/_/_/    _/_/_/    _/      _/            _/      _/    _/_/_/",
            "   _/    _/  _/        _/        _/    _/  _/_/    _/  _/_/_/_/_/  _/_/    _/  _/       ",
            "  _/_/_/    _/_/_/    _/        _/    _/  _/  _/  _/            _/  _/  _/  _/  _/_/_/  ",
            " _/    _/  _/        _/        _/    _/  _/    _/_/            _/    _/_/  _/      _/   ",
            "_/    _/  _/_/_/_/    _/_/_/    _/_/_/  _/      _/            _/      _/    _/_/_/      ",
        ]
        for line in banner_lines:
            print(line)
        print('')
        
        # Print module counts by category
        counts = [(len(self._loaded_category.get(x, [])), x) for x in getattr(self, '_loaded_category', {})]
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
        import random
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
    
    #==================================================
    # OUTPUT METHODS
    #==================================================
    
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
    
    def error(self, line):
        '''Formats and presents errors.'''
        line = str(line)
        if not re.search('[.,;!?]$', line):
            line += '.'
        line = line[:1].upper() + line[1:]
        print(f"{Colors.R}[!] {line}{Colors.N}")
    
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
        spacer = '  '
        for i in range(0, cols):
            lens.append(len(max([str(x[i]) if x[i] != None else '' for x in tdata], key=len)))
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
            separator_str = f"{spacer}+-{'%s---'*(cols-1)}%s-+"
            separator_sub = tuple(['-'*int(x) for x in lens])
            separator = separator_str % separator_sub
            data_str = f"{spacer}| {'%s | '*(cols-1)}%s |"
            print('')
            print(separator)
            if title:
                print(f"{spacer}| {title.center(tdata_len)} |")
                print(separator)
            if header:
                rdata = tdata.pop(0)
                data_sub = tuple([rdata[i].center(int(lens[i])) for i in range(0, cols)])
                print(data_str % data_sub)
                print(separator)
            for rdata in tdata:
                data_sub = tuple([str(rdata[i]).ljust(int(lens[i])) if rdata[i] != None else ''.ljust(int(lens[i])) for i in range(0, cols)])
                print(data_str % data_sub)
            print(separator)
            print('')

    def _list_modules(self, modules):
        '''Lists modules in a formatted way'''
        spacer = '  '
        if modules:
            key_len = len(max(modules, key=len)) + len(spacer)
            last_category = ''
            for module in sorted(modules):
                category = module.split('/')[0]
                if category != last_category:
                    last_category = category
                    print('')
                    print(f"{spacer}{category.upper()}")
                    print(f"{spacer}{'-'*len(category)}")
                print(f"{spacer*2}{module}")
        else:
            print('')
            print(f"{Colors.G}[*]{Colors.N} No modules enabled/installed.")
        print('')
    
    #==================================================
    # SUPPORT METHODS
    #==================================================
    
    def _parse_params(self, params):
        params = params.split()
        arg = ''
        if params:
            arg = params.pop(0)
        params = ' '.join(params)
        return arg, params

    def _parse_subcommands(self, command):
        subcommands = []
        for method in dir(self):
            if f"_do_{command}_" in method:
                subcommands.append(method.split('_')[-1])
        return subcommands

    #==================================================
    # WORKSPACES COMMAND METHODS
    #==================================================
    
    def do_workspaces(self, params):
        '''Manages workspaces'''
        if not params:
            self.help_workspaces()
            return
        arg, params = self._parse_params(params)
        if arg in self._parse_subcommands('workspaces'):
            return getattr(self, '_do_workspaces_'+arg)(params)
        else:
            self.help_workspaces()
    
    def _do_workspaces_list(self, params):
        '''Lists existing workspaces'''
        workspaces = self._get_workspaces()
        if workspaces:
            rows = [(ws, 'N/A') for ws in sorted(workspaces)]
            self.table(rows, header=['Workspaces', 'Modified'])
        else:
            self.output('No workspaces found.')
    
    def _do_workspaces_create(self, params):
        '''Creates a new workspace'''
        if not params:
            self._help_workspaces_create()
            return
        try:
            self._create_workspace(params)
            self.output(f"Workspace '{params}' created.")
        except Exception as e:
            self.output(f"Unable to create '{params}' workspace.")
    
    def _do_workspaces_load(self, params):
        '''Loads an existing workspace'''
        if not params:
            self._help_workspaces_load()
            return
        workspaces = self._get_workspaces()
        if params in workspaces:
            if not self._init_workspace(params):
                self.output(f"Unable to initialize '{params}' workspace.")
        else:
            self.output('Invalid workspace name.')
    
    def _do_workspaces_remove(self, params):
        '''Removes an existing workspace'''
        if not params:
            self._help_workspaces_remove()
            return
        try:
            self._delete_workspace(params)
            self.output(f"Workspace '{params}' removed.")
        except Exception as e:
            self.output(f"Unable to remove '{params}' workspace.")
    
    #==================================================
    # SNAPSHOTS COMMAND METHODS
    #==================================================
    
    def do_snapshots(self, params):
        '''Manages workspace snapshots'''
        if not params:
            self.help_snapshots()
            return
        arg, params = self._parse_params(params)
        if arg in self._parse_subcommands('snapshots'):
            return getattr(self, '_do_snapshots_'+arg)(params)
        else:
            self.help_snapshots()
    
    def _do_snapshots_list(self, params):
        '''Lists existing database snapshots'''
        snapshots = self._get_snapshots()
        if snapshots:
            self.table([[x] for x in snapshots], header=['Snapshots'])
        else:
            self.output('This workspace has no snapshots.')
    
    def _do_snapshots_take(self, params):
        '''Takes a snapshot of the current database'''
        from datetime import datetime
        import shutil
        try:
            timestamp = datetime.strftime(datetime.now(), '%Y%m%d%H%M%S')
            src = os.path.join(self.workspace, 'data.db')
            dst = os.path.join(self.workspace, f'snapshot_{timestamp}.db')
            shutil.copy2(src, dst)
            snapshot = f'snapshot_{timestamp}.db'
            self.output(f"Snapshot created: {snapshot}")
        except Exception as e:
            self.error(str(e))
    
    def _load_snapshot(self, name):
        """Load a snapshot, replacing the current database."""
        import shutil
        src = os.path.join(self.workspace, name)
        dst = os.path.join(self.workspace, 'data.db')
        shutil.copy2(src, dst)
    
    def _delete_snapshot(self, name):
        """Delete a snapshot file."""
        path = os.path.join(self.workspace, name)
        if os.path.exists(path):
            os.remove(path)
    
    def _do_snapshots_load(self, params):
        '''Loads an existing database snapshot'''
        if not params:
            self._help_snapshots_load()
            return
        snapshots = self._get_snapshots()
        if params in snapshots:
            self._load_snapshot(params)
            self.output(f"Snapshot loaded: {params}")
        else:
            self.error(f"No snapshot named '{params}'.")
    
    def _do_snapshots_remove(self, params):
        '''Removes an existing snapshot'''
        if not params:
            self._help_snapshots_remove()
            return
        snapshots = self._get_snapshots()
        if params in snapshots:
            self._delete_snapshot(params)
            self.output(f"Snapshot removed: {params}")
        else:
            self.error(f"No snapshot named '{params}'.")
    
    #==================================================
    # MARKETPLACE COMMAND METHODS
    #==================================================
    
    def do_marketplace(self, params):
        '''Interfaces with the module marketplace'''
        if not self._marketplace:
            self.alert('Marketplace disabled.')
            return
        if not params:
            self.help_marketplace()
            return
        arg, params = self._parse_params(params)
        if arg in self._parse_subcommands('marketplace'):
            return getattr(self, '_do_marketplace_'+arg)(params)
        else:
            self.help_marketplace()
    
    def _do_marketplace_refresh(self, params):
        '''Refreshes the marketplace index'''
        self._fetch_module_index()
        self._update_module_index()
        self.output('Marketplace index refreshed.')
    
    def _do_marketplace_search(self, params):
        '''Searches marketplace modules'''
        # Use core's _search_module_index which searches path, name, description, status
        modules = self._search_module_index(params) if params else self._module_index
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
        else:
            self.error('No modules found.')
            self._help_marketplace_search()
    
    def _do_marketplace_info(self, params):
        '''Shows detailed information about available modules'''
        if not params:
            self._help_marketplace_info()
            return
        modules = [m for m in self._module_index if params in m.get('path', '')]
        if modules:
            for module in modules:
                rows = []
                for key in ('path', 'name', 'author', 'version', 'last_updated', 'description', 'required_keys', 'dependencies', 'files', 'status'):
                    row = (key, module.get(key, ''))
                    rows.append(row)
                self.table(rows)
        else:
            self.error('Invalid module path.')
    
    def _do_marketplace_install(self, params):
        '''Installs modules from the marketplace'''
        if not params:
            self._help_marketplace_install()
            return
        # Find matching modules
        modules = [m for m in self._module_index if params in m.get('path', '')]
        if modules:
            for module in modules:
                self._install_module(module.get('path', ''))
            self._do_modules_reload('')
        else:
            self.error('Invalid module path.')
    
    def _do_marketplace_remove(self, params):
        '''Removes marketplace modules from the framework'''
        if not params:
            self._help_marketplace_remove()
            return
        # Find matching modules (including disabled status)
        modules = [m for m in self._module_index if params in m.get('path', '') and m.get('status') in ('installed', 'disabled')]
        if modules:
            for module in modules:
                self._remove_module(module.get('path', ''))
            self._do_modules_reload('')
        else:
            self.error('Invalid module path.')
    
    #==================================================
    # MODULES COMMAND METHODS
    #==================================================
    
    def _match_modules(self, term):
        """Find modules matching the term."""
        return [x for x in self._loaded_modules if term in x]
    
    def _do_modules_load(self, params):
        '''Loads a module'''
        if not params:
            self._help_modules_load()
            return
        
        # Match modules
        modules = self._match_modules(params)
        
        if not modules:
            self.error('Invalid module name.')
            return None
        elif len(modules) > 1:
            self.output(f"Multiple modules match '{params}'.")
            self._list_modules(modules)
            return None
        else:
            # Single match - return the module path
            return modules[0]
    
    def _do_modules_reload(self, params):
        '''Reloads all modules'''
        self.output('Reloading modules...')
        self._load_modules()
    
    #==================================================
    # INDEX COMMAND METHODS
    #==================================================
    
    def do_index(self, params):
        '''Builds module index for the framework'''
        if not params:
            self.help_index()
            return
        
        # Parse params - might be "all" or "module_filter" with optional filename
        parts = params.split()
        module_filter = parts[0] if parts else 'all'
        filename = parts[1] if len(parts) > 1 else None
        
        # Find matching modules
        if module_filter == 'all':
            modules = list(self._loaded_modules.keys())
        else:
            modules = [x for x in self._loaded_modules if module_filter in x]
        
        if not modules:
            self.output('No modules found.')
            return
        
        self.output('Building index markup...')
        
        # Build YAML for each module
        import yaml
        index_data = []
        for mod_path in sorted(modules):
            module = self._loaded_modules.get(mod_path)
            if module and hasattr(module, 'meta'):
                meta = module.meta
                entry = {
                    'path': mod_path,
                    'name': meta.get('name', ''),
                    'author': meta.get('author', ''),
                    'version': meta.get('version', ''),
                    'description': meta.get('description', ''),
                    'dependencies': meta.get('dependencies', []),
                    'files': meta.get('files', []),
                    'required_keys': meta.get('required_keys', []),
                }
                index_data.append(entry)
                # Print YAML for this module
                print(yaml.dump([entry], default_flow_style=False))
        
        # Write to file if filename provided
        if filename:
            try:
                with open(filename, 'w') as f:
                    yaml.dump(index_data, f, default_flow_style=False)
                self.output('Module index created.')
            except Exception as e:
                self.error(f"Failed to write index: {e}")
    
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
        print(f"{os.linesep}Usage: workspaces create <name>{os.linesep}")
    
    def _help_workspaces_load(self):
        print("Loads an existing workspace")
        print(f"{os.linesep}Usage: workspaces load <name>{os.linesep}")
    
    def _help_workspaces_remove(self):
        print("Removes an existing workspace")
        print(f"{os.linesep}Usage: workspaces remove <name>{os.linesep}")
    
    def help_snapshots(self):
        print(getattr(self, 'do_snapshots').__doc__)
        print(f"{os.linesep}Usage: snapshots <{'|'.join(self._parse_subcommands('snapshots'))}> [...]{os.linesep}")
    
    def _help_snapshots_load(self):
        print("Loads an existing database snapshot")
        print(f"{os.linesep}Usage: snapshots load <name>{os.linesep}")
    
    def _help_snapshots_remove(self):
        print("Removes an existing snapshot")
        print(f"{os.linesep}Usage: snapshots remove <name>{os.linesep}")
    
    def _help_modules_load(self):
        print("Loads a module")
        print(f"{os.linesep}Usage: modules load <path>{os.linesep}")
    
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
        return [x for x in self._get_workspaces() if x.startswith(text)]
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
        return [x for x in self._get_snapshots() if x.startswith(text)]
    _complete_snapshots_remove = _complete_snapshots_load
    
    def _complete_modules_reload(self, text, *ignored):
        return []
