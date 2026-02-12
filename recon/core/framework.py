"""
Recon-ng Framework Core

This module provides the core business logic for recon-ng, including:
- Database operations (query, insert, etc.)
- API key management
- HTTP request handling
- Module support utilities

This module does NOT contain any CLI-specific code. CLI functionality
is implemented in recon/client/.
"""
from contextlib import closing
import codecs
import inspect
import json
import os
import random
import re
import requests
import sqlite3
import string

#=================================================
# SUPPORT CLASSES
#=================================================

class FrameworkException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)

class Colors(object):
    """
    ANSI color codes for terminal output.
    
    For use in prompts with readline, use the RL_* variants which wrap
    escape sequences in \\001 and \\002 markers so readline can correctly
    calculate prompt width.
    """
    N = '\033[m' # native/reset
    R = '\033[31m' # red
    G = '\033[32m' # green
    O = '\033[33m' # orange
    B = '\033[34m' # blue
    P = '\033[35m' # purple/magenta
    
    # Readline-safe versions (for use in prompts)
    RL_N = '\001\033[m\002'
    RL_R = '\001\033[31m\002'
    RL_G = '\001\033[32m\002'
    RL_O = '\001\033[33m\002'
    RL_B = '\001\033[34m\002'
    RL_P = '\001\033[35m\002'

class Options(dict):

    def __init__(self, *args, **kwargs):
        self.required = {}
        self.description = {}
        super(Options, self).__init__(*args, **kwargs)

    def __getitem__(self, name):
        name = self.__keytransform__(name)
        return super(Options, self).__getitem__(name)

    def __setitem__(self, name, value):
        name = self.__keytransform__(name)
        value = self._autoconvert(value)
        super(Options, self).__setitem__(name, value)

    def __delitem__(self, name):
        name = self.__keytransform__(name)
        super(Options, self).__delitem__(name)
        if name in self.required:
            del self.required[name]
        if name in self.description:
            del self.description[name]

    def __keytransform__(self, key):
        return key.upper()

    def _boolify(self, value):
        # designed to throw an exception if value is not a string representation of a boolean
        return {'true':True, 'false':False}[value.lower()]

    def _autoconvert(self, value):
        if value in (None, True, False):
            return value
        elif (isinstance(value, str)) and value.lower() in ('none', "''", '""'):
            return None
        orig = value
        for fn in (self._boolify, int, float):
            try:
                value = fn(value)
                break
            except ValueError: pass
            except KeyError: pass
            except AttributeError: pass
        if type(value) is int and '.' in str(orig):
            return float(orig)
        return value

    def init_option(self, name, value=None, required=False, description=''):
        name = self.__keytransform__(name)
        self[name] = value
        self.required[name] = required
        self.description[name] = description

    def serialize(self):
        options = []
        for key in self:
            option = {}
            option['name'] = key
            option['value'] = self[key]
            option['required'] = self.required[key]
            option['description'] = self.description[key]
            options.append(option)
        return options

#=================================================
# FRAMEWORK CLASS
#=================================================

class Framework:
    """
    Core framework class providing business logic for recon-ng.
    
    This class is used by the server's Engine class. It does not inherit
    from cmd.Cmd and contains no CLI-specific code.
    """
    # mode flags
    _script = 0
    _load = 0
    _mode = 0
    # framework variables
    _global_options = Options()
    _loaded_modules = {}
    app_path = ''
    data_path = ''
    core_path = ''
    home_path = ''
    mod_path = ''
    spaces_path = ''
    workspace = ''
    _record = None
    _spool = None
    _summary_counts = {}

    def __init__(self, params):
        self._modulename = params
        self.ruler = '-'
        self.spacer = '  '
        self.time_format = '%Y-%m-%d %H:%M:%S'
        self._exit = 0

    #==================================================
    # SUPPORT METHODS
    #==================================================

    def to_unicode_str(self, obj, encoding='utf-8'):
        # converts non-stringish types to unicode
        if type(obj) not in (str, bytes):
            obj = str(obj)
        obj = self.to_unicode(obj, encoding)
        return obj

    def to_unicode(self, obj, encoding='utf-8'):
        # converts bytes to unicode
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

    #==================================================
    # OUTPUT METHODS
    # These methods check for a server execution context and route
    # output through RPC events if available. Otherwise, they print
    # directly (for CLI use or testing).
    #==================================================

    def _get_event_publisher(self):
        """Get the event publisher from execution context if available."""
        try:
            from recon.server.interceptors import get_current_context
            ctx = get_current_context()
            if ctx is not None:
                return ctx.events
        except ImportError:
            pass
        return None

    def verbose(self, line):
        '''Formats and presents output if in verbose mode.'''
        if self._global_options.get('VERBOSITY', 1) >= 1:
            events = self._get_event_publisher()
            if events:
                events.verbose(str(line))
            else:
                self.output(line)

    def debug(self, line):
        '''Formats and presents output if in debug mode (very verbose).'''
        if self._global_options.get('VERBOSITY', 1) >= 2:
            events = self._get_event_publisher()
            if events:
                events.debug(str(line))
            else:
                self.output(line)

    def alert(self, line):
        '''Formats and presents important output.'''
        events = self._get_event_publisher()
        if events:
            events.alert(str(line))
        else:
            print(f"{Colors.G}[*]{Colors.N} {line}")

    def error(self, line):
        '''Formats and presents errors.'''
        line = str(line)
        if not re.search('[.,;!?]$', line):
            line += '.'
        line = line[:1].upper() + line[1:]
        events = self._get_event_publisher()
        if events:
            events.error(line)
        else:
            print(f"{Colors.R}[!] {line}{Colors.N}")

    def output(self, line):
        '''Formats and presents normal output.'''
        events = self._get_event_publisher()
        if events:
            events.output(str(line))
        else:
            print(f"{Colors.B}[*]{Colors.N} {line}")

    def heading(self, line, level=1):
        '''Formats and presents styled header text.'''
        events = self._get_event_publisher()
        if events:
            events.heading(str(line), level)
        else:
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
        events = self._get_event_publisher()
        if events:
            # Send structured data through events
            events.table(list(data), header, title)
        else:
            # Local table formatting
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

    #==================================================
    # DATABASE METHODS
    #==================================================

    def query(self, *args, **kwargs):
        path = os.path.join(self.workspace, 'data.db')
        return self._query(path, *args, **kwargs)

    def _query(self, path, query, values=(), include_header=False):
        '''Queries the database and returns the results as a list.'''
        self.debug(f"DATABASE => {path}")
        self.debug(f"QUERY => {query}")
        with sqlite3.connect(path) as conn:
            with closing(conn.cursor()) as cur:
                if values:
                    self.debug(f"VALUES => {repr(values)}")
                    cur.execute(query, values)
                else:
                    cur.execute(query)
                # a rowcount of -1 typically refers to a select statement
                if cur.rowcount == -1:
                    rows = []
                    if include_header:
                        rows.append(tuple([x[0] for x in cur.description]))
                    rows.extend(cur.fetchall())
                    results = rows
                # a rowcount of 1 == success and 0 == failure
                else:
                    conn.commit()
                    results = cur.rowcount
                return results

    def get_columns(self, table):
        return [(x[1], x[2]) for x in self.query(f"PRAGMA table_info('{table}')")]

    def get_tables(self):
        return [x[0] for x in self.query('SELECT name FROM sqlite_master WHERE type=\'table\'') if x[0] not in ['dashboard']]

    #==================================================
    # INSERT METHODS
    #==================================================

    def _display(self, data, rowcount):
        '''Displays insert results. Uses alert for new records, verbose for duplicates.'''
        display = self.alert if rowcount else self.verbose
        for key in sorted(data.keys()):
            display(f"{key.title()}: {data[key]}")
        display(self.ruler*50)

    def insert_domains(self, domain=None, notes=None, mute=False):
        '''Adds a domain to the database and returns the affected row count.'''
        data = dict(
            domain = domain,
            notes = notes
        )
        rowcount = self.insert('domains', data.copy(), data.keys())
        if not mute: self._display(data, rowcount)
        return rowcount

    def insert_tenants(self, brand=None, name=None, id=None, region=None, subregion=None, domain=None, desktopSSOEnabled=None, CBAEnabled=None, usesCloudSync=None, mute=False):
        '''Adds a tenant to the database and returns the affected row count.'''
        data = dict(
            brand=brand,
            name=name,
            id=id,
            region=region,
            subregion=subregion,
            domain=domain,
            desktopSSOEnabled=desktopSSOEnabled,
            CBAEnabled=CBAEnabled,
            usesCloudSync=usesCloudSync
        )
        rowcount = self.insert('tenants', data.copy(), data.keys())
        if not mute: self._display(data, rowcount)
        return rowcount

    def insert_companies(self, company=None, description=None, notes=None, mute=False):
        '''Adds a company to the database and returns the affected row count.'''
        data = dict(
            company = company,
            description = description,
            notes = notes
        )
        rowcount = self.insert('companies', data.copy(), ('company',))
        if not mute: self._display(data, rowcount)
        return rowcount

    def insert_netblocks(self, netblock=None, notes=None, mute=False):
        '''Adds a netblock to the database and returns the affected row count.'''
        data = dict(
            netblock = netblock,
            notes = notes
        )
        rowcount = self.insert('netblocks', data.copy(), data.keys())
        if not mute: self._display(data, rowcount)
        return rowcount

    def insert_locations(self, latitude=None, longitude=None, street_address=None, notes=None, mute=False):
        '''Adds a location to the database and returns the affected row count.'''
        data = dict(
            latitude = latitude,
            longitude = longitude,
            street_address = street_address,
            notes = notes
        )
        rowcount = self.insert('locations', data.copy(), data.keys())
        if not mute: self._display(data, rowcount)
        return rowcount

    def insert_vulnerabilities(self, host=None, reference=None, example=None, publish_date=None, category=None, status=None, notes=None, mute=False):
        '''Adds a vulnerability to the database and returns the affected row count.'''
        data = dict(
            host = host,
            reference = reference,
            example = example,
            publish_date = publish_date.strftime(self.time_format) if publish_date else None,
            category = category,
            status = status,
            notes = notes
        )
        rowcount = self.insert('vulnerabilities', data.copy(), data.keys())
        if not mute: self._display(data, rowcount)
        return rowcount

    def insert_ports(self, ip_address=None, host=None, port=None, protocol=None, banner=None, notes=None, mute=False):
        '''Adds a port to the database and returns the affected row count.'''
        data = dict(
            ip_address = ip_address,
            port = port,
            host = host,
            protocol = protocol,
            banner = banner,
            notes = notes
        )
        rowcount = self.insert('ports', data.copy(), ('ip_address', 'port', 'host'))
        if not mute: self._display(data, rowcount)
        return rowcount

    def insert_hosts(self, host=None, cname=None, ip_address=None, region=None, country=None, latitude=None, longitude=None, notes=None, mute=False):
        '''Adds a host to the database and returns the affected row count.'''
        data = dict(
            host = host,
            cname = cname,
            ip_address = ip_address,
            region = region,
            country = country,
            latitude = latitude,
            longitude = longitude,
            notes = notes
        )
        rowcount = self.insert('hosts', data.copy(), ('host', 'ip_address'))
        if not mute: self._display(data, rowcount)
        return rowcount

    def insert_contacts(self, first_name=None, middle_name=None, last_name=None, email=None, title=None, region=None, country=None, phone=None, notes=None, mute=False):
        '''Adds a contact to the database and returns the affected row count.'''
        data = dict(
            first_name = first_name,
            middle_name = middle_name,
            last_name = last_name,
            title = title,
            email = email,
            region = region,
            country = country,
            phone = phone,
            notes = notes
        )
        rowcount = self.insert('contacts', data.copy(), ('first_name', 'middle_name', 'last_name', 'title', 'email', 'phone'))
        if not mute: self._display(data, rowcount)
        return rowcount

    def insert_credentials(self, username=None, password=None, _hash=None, _type=None, leak=None, notes=None, mute=False):
        '''Adds a credential to the database and returns the affected row count.'''

        # account for hashes provided in the password field
        if password and not _hash:
            _type = self.is_hash(password)
            if _type:
                _hash = password
                password = None
        # handle hashes provided without a type
        if _hash and not _type:
            _type = self.is_hash(_hash)
        # add email usernames to contacts
        if username is not None and '@' in username:
            self.insert_contacts(first_name=None, last_name=None, title=None, email=username)

        data = dict (
            username = username,
            password = password,
            hash = _hash,
            type = _type,
            leak = leak,
            notes = notes
        )
        rowcount = self.insert('credentials', data.copy(), data.keys())
        if not mute: self._display(data, rowcount)
        return rowcount

    def insert_leaks(self, leak_id=None, description=None, source_refs=None, leak_type=None, title=None, import_date=None, leak_date=None, attackers=None, num_entries=None, score=None, num_domains_affected=None, attack_method=None, target_industries=None, password_hash=None, password_type=None, targets=None, media_refs=None, notes=None, mute=False):
        '''Adds a leak to the database and returns the affected row count.'''
        data = dict(
            leak_id = leak_id,
            description = description,
            source_refs = source_refs,
            leak_type = leak_type,
            title = title,
            import_date = import_date,
            leak_date = leak_date,
            attackers = attackers,
            num_entries = num_entries,
            score = score,
            num_domains_affected = num_domains_affected,
            attack_method = attack_method,
            target_industries = target_industries,
            password_hash = password_hash,
            password_type = password_type,
            targets = targets,
            media_refs = media_refs,
            notes = notes
        )
        rowcount = self.insert('leaks', data.copy(), data.keys())
        if not mute: self._display(data, rowcount)
        return rowcount

    def insert_pushpins(self, source=None, screen_name=None, profile_name=None, profile_url=None, media_url=None, thumb_url=None, message=None, latitude=None, longitude=None, time=None, notes=None, mute=False):
        '''Adds a pushpin to the database and returns the affected row count.'''
        data = dict(
            source = source,
            screen_name = screen_name,
            profile_name = profile_name,
            profile_url = profile_url,
            media_url = media_url,
            thumb_url = thumb_url,
            message = message,
            latitude = latitude,
            longitude = longitude,
            time = time.strftime(self.time_format),
            notes = notes
        )
        rowcount = self.insert('pushpins', data.copy(), data.keys())
        if not mute: self._display(data, rowcount)
        return rowcount

    def insert_profiles(self, username=None, resource=None, url=None, category=None, contact_id=None, notes=None, mute=False):
        '''Adds a profile to the database and returns the affected row count.'''
        data = dict(
            username = username,
            resource = resource,
            url = url,
            category = category,
            contact_id = contact_id,
            notes = notes
        )
        rowcount = self.insert('profiles', data.copy(), ('username', 'url'))
        if not mute: self._display(data, rowcount)
        return rowcount

    def insert_repositories(self, name=None, owner=None, description=None, resource=None, category=None, url=None, notes=None, mute=False):
        '''Adds a repository to the database and returns the affected row count.'''
        data = dict(
            name = name,
            owner = owner,
            description = description,
            resource = resource,
            category = category,
            url = url,
            notes = notes
        )
        rowcount = self.insert('repositories', data.copy(), data.keys())
        if not mute: self._display(data, rowcount)
        return rowcount

    def insert(self, table, data, unique_columns=[]):
        '''Inserts items into database and returns the affected row count.
        table - the table to insert the data into
        data - the information to insert into the database table in the form of a dictionary
               where the keys are the column names and the values are the column values
        unique_columns - a list of column names that should be used to determine if the
                         information being inserted is unique'''
        # set module to the calling module unless the do_add command was used
        data['module'] = 'user_defined' if '_do_db_insert' in [x[3] for x in inspect.stack()] else self._modulename.split('/')[-1]
        # sanitize the inputs to remove NoneTypes, blank strings, and zeros
        columns = [x for x in data.keys() if data[x]]
        # make sure that module is not seen as a unique column
        unique_columns = [x for x in unique_columns if x in columns and x != 'module']
        # exit if there is nothing left to insert
        if not columns:
            return 0
        # convert any type to unicode (str) for external processing
        for column in columns:
            data[column] = self.to_unicode_str(data[column])

        # build the insert query
        columns_str = '`, `'.join(columns)
        placeholder_str = ', '.join('?'*len(columns))
        unique_columns_str = ' and '.join([f"`{column}`=?" for column in unique_columns])
        if not unique_columns:
            query = f"INSERT INTO `{table}` (`{columns_str}`) VALUES ({placeholder_str})"
        else:
            query = f"INSERT INTO `{table}` (`{columns_str}`) SELECT {placeholder_str} WHERE NOT EXISTS(SELECT * FROM `{table}` WHERE {unique_columns_str})"
        values = tuple([data[column] for column in columns] + [data[column] for column in unique_columns])

        # query the database
        rowcount = self.query(query, values)

        # increment summary tracker
        if table not in self._summary_counts:
            self._summary_counts[table] = {'count': 0, 'new': 0}
        self._summary_counts[table]['new'] += rowcount
        self._summary_counts[table]['count'] += 1

        return rowcount

    #==================================================
    # OPTIONS METHODS
    #==================================================

    def register_option(self, name, value, required, description):
        self.options.init_option(name=name, value=value, required=required, description=description)
        # needs to be optimized rather than ran on every register
        self._load_config()

    def _validate_options(self):
        for option in self.options:
            # if value type is bool or int, then we know the options is set
            if not type(self.options[option]) in [bool, int]:
                if self.options.required[option] is True and not self.options[option]:
                    raise FrameworkException(f"Value required for the '{option}' option.")
        return

    def _load_config(self):
        config_path = os.path.join(self.workspace, 'config.dat')
        # don't bother loading if a config file doesn't exist
        if os.path.exists(config_path):
            # retrieve saved config data
            with open(config_path) as config_file:
                try:
                    config_data = json.loads(config_file.read())
                except ValueError:
                    # file is corrupt, nothing to load, exit gracefully
                    pass
                else:
                    # set option values
                    for key in self.options:
                        try:
                            self.options[key] = config_data[self._modulename][key]
                        except KeyError:
                            # invalid key, contnue to load valid keys
                            continue

    def _save_config(self, name, module=None, options=None):
        config_path = os.path.join(self.workspace, 'config.dat')
        # create a config file if one doesn't exist
        open(config_path, 'a').close()
        # retrieve saved config data
        with open(config_path) as config_file:
            try:
                config_data = json.loads(config_file.read())
            except ValueError:
                # file is empty or corrupt, nothing to load
                config_data = {}
        # override implicit defaults if specified
        module = module or self._modulename
        options = options or self.options
        # create a container for the current module
        if module not in config_data:
            config_data[module] = {}
        # set the new option value in the config
        config_data[module][name] = options[name]
        # remove the option if it has been unset
        if config_data[module][name] is None:
            del config_data[module][name]
        # remove the module container if it is empty
        if not config_data[module]:
            del config_data[module]
        # write the new config data to the config file
        with open(config_path, 'w') as config_file:
            json.dump(config_data, config_file, indent=4)

    #==================================================
    # API KEY METHODS
    #==================================================

    def get_key(self, name):
        rows = self._query_keys('SELECT value FROM keys WHERE name=? AND value NOT NULL', (name,))
        if not rows:
            return None
        return rows[0][0]

    def add_key(self, name, value):
        result = self._query_keys('UPDATE keys SET value=? WHERE name=?', (value, name))
        if not result:
            return self._query_keys('INSERT INTO keys VALUES (?, ?)', (name, value))
        return result

    def remove_key(self, name):
        #return self._query_keys('UPDATE keys SET value=NULL WHERE name=?', (name,))
        return self._query_keys('DELETE FROM keys WHERE name=?', (name,))

    def _query_keys(self, query, values=()):
        path = os.path.join(self.home_path, 'keys.db')
        result = self._query(path, query, values)
        # filter out tokens when not called from the get_key method
        if type(result) is list and 'get_key' not in [x[3] for x in inspect.stack()]:
            result = [x for x in result if not x[0].endswith('_token')]
        return result

    def _get_key_names(self):
        return [x[0] for x in self._query_keys('SELECT name FROM keys')]

    #==================================================
    # REQUEST METHODS
    #==================================================

    def request(self, method, url, **kwargs):
        # process socket timeout
        kwargs['timeout'] = kwargs.get('timeout') or self._global_options['timeout']
        # process headers
        headers = kwargs.get('headers') or {}
        # set the User-Agent header
        if 'user-agent' not in [h.lower() for h in headers]:
            headers['user-agent'] = self._global_options['user-agent']
        # normalize capitalization of the User-Agent header
        headers = {k.title(): v for k, v in headers.items()}
        kwargs['headers'] = headers
        # process proxy
        proxy = self._global_options['proxy']
        if proxy:
            proxies = {
                'http': f"http://{proxy}",
                'https': f"http://{proxy}",
            }
            kwargs['proxies'] = proxies
        # disable TLS validation and warning
        kwargs['verify'] = False
        requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
        # send the request
        resp = getattr(requests, method.lower())(url, **kwargs)
        return resp

    #==================================================
    # MODULES METHODS
    #==================================================

    def _match_modules(self, params):
        # return an exact match
        if params in Framework._loaded_modules:
            return [params]
        # use the provided name as a keyword search and return the results
        return [x for x in Framework._loaded_modules if params in x]
