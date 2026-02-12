"""
Recon-ng Module Base Class

This module provides the BaseModule class which all recon-ng modules inherit from.
It provides:
- Module initialization and option registration
- Source data retrieval (_get_source)
- Input validation
- HTTP helper methods
- Module execution hooks (module_pre, module_run, module_post)

This module does NOT contain any CLI-specific code. CLI functionality
is implemented in recon/client/.
"""

from requests.exceptions import Timeout
import html
import http.cookiejar
import io
import json
import os
import re
import socket
import sqlite3
import sys
import textwrap
import yaml

# framework libs
from recon.core import framework
from recon.utils import validators

#=================================================
# MODULE CLASS
#=================================================

class BaseModule(framework.Framework):
    """
    Base class for all recon-ng modules.
    
    Modules inherit from this class and implement:
    - meta: Dictionary with module metadata (name, author, description, etc.)
    - module_run(): Core module logic
    - Optionally: module_pre(), module_post() for setup/teardown
    """

    def __init__(self, params):
        framework.Framework.__init__(self, params)
        self.options = framework.Options()
        # update the meta dictionary by merging the class variable with any frontmatter
        self.meta = self._merge_dicts(self.meta, self._parse_frontmatter())
        # register a data source option if a default query is specified in the module
        if self.meta.get('query'):
            self._default_source = self.meta.get('query')
            self.register_option('source', 'default', True, 'source of input (see \'info\' for details)')
        # register all other specified options
        if self.meta.get('options'):
            for option in self.meta.get('options'):
                self.register_option(*option)
        # register any required keys
        if self.meta.get('required_keys'):
            self.keys = {}
            for key in self.meta.get('required_keys'):
                # add key to the database
                self._query_keys('INSERT OR IGNORE INTO keys (name) VALUES (?)', (key,))
                # migrate the old key if needed
                self._migrate_key(key)
                # add key to local keys dictionary
                # could fail to load on exception here to prevent loading modules
                # without required keys, but would need to do it in a separate loop
                # so that all keys get added to the database first. for now, the
                # framework will warn users of the missing key, but allow the module
                # to load.
                self.keys[key] = self.get_key(key)
                if not self.keys.get(key):
                    self.error(f"'{key}' key not set. {self._modulename.split('/')[-1]} module will likely fail at runtime. See 'keys add'.")
        self._reload = 0

    #==================================================
    # SUPPORT METHODS
    #==================================================

    def _merge_dicts(self, x, y):
        # start with x's keys and values
        z = x.copy()
        # modify z with y's keys and values
        z.update(y)
        return z

    def _parse_frontmatter(self):
        rel_path = '.'.join([self._modulename, 'py'])
        abs_path = os.path.join(self.mod_path, rel_path)
        with open(abs_path) as fp:
            state = False
            yaml_src = ''
            for line in fp:
                 if line == '---\n':
                      state = not state
                      continue
                 if state:
                      yaml_src += line
        return yaml.safe_load(yaml_src) or {}

    def _migrate_key(self, key):
        '''migrate key from old .dat file'''
        key_path = os.path.join(self.home_path, 'keys.dat')
        if os.path.exists(key_path):
            try:
                key_data = json.loads(open(key_path, 'rb').read())
                if key_data.get(key):
                    self.add_key(key, key_data.get(key))
            except:
                self.error(f"Corrupt key file. Manual migration of '{key}' required.")

    def ascii_sanitize(self, s):
        return ''.join([char for char in s if ord(char) in [10, 13] + list(range(32, 126))])

    def html_unescape(self, s):
        '''Unescapes HTML markup and returns an unescaped string.'''
        return html.unescape(s)

    def html_escape(self, s):
        escapes = {
            '&': '&amp;',
            '"': '&quot;',
            "'": '&apos;',
            '>': '&gt;',
            '<': '&lt;',
            }
        return ''.join(escapes.get(c, c) for c in s)

    def cidr_to_list(self, string):
        import ipaddress
        return [str(ip) for ip in ipaddress.ip_network(string)]

    def hosts_to_domains(self, hosts, exclusions=[]):
        domains = []
        for host in hosts:
            elements = host.split('.')
            # recursively walk through the elements
            # extracting all possible (sub)domains
            while len(elements) >= 2:
                # account for domains stored as hosts
                if len(elements) == 2:
                    domain = '.'.join(elements)
                else:
                    # drop the host element
                    domain = '.'.join(elements[1:])
                if domain not in domains + exclusions:
                    domains.append(domain)
                del elements[0]
        return domains

    def _validate_input(self):
        validator_type = self.meta.get('validator')
        if not validator_type:
            # passthru, no validator required
            self.debug('No validator required.')
            return
        validator = None
        validator_name = validator_type.capitalize() + 'Validator'
        for obj in [self, validators]:
            if hasattr(obj, validator_name):
                validator = getattr(validators, validator_name)()
        if not validator:
            # passthru, no validator defined
            self.debug('No validator defined.')
            return
        inputs = self._get_source(self.options['source'], self._default_source)
        for _input in inputs:
            validator.validate(_input)
            self.debug('All inputs validated.')

    #==================================================
    # OPTIONS METHODS
    #==================================================

    def _get_source(self, params, query=None):
        """
        Get input data based on the SOURCE option.
        
        Args:
            params: Source parameter value (e.g., 'default', 'query SELECT...', filepath, or literal value)
            query: Default query to use when params is 'default'
            
        Returns:
            List of input values
        """
        prefix = params.split()[0].lower()
        if prefix in ['query', 'default']:
            query = ' '.join(params.split()[1:]) if prefix == 'query' else query
            try:
                results = self.query(query)
            except sqlite3.OperationalError as e:
                raise framework.FrameworkException(f"Invalid source query. {type(e).__name__} {e}")
            if not results:
                sources = []
            elif len(results[0]) > 1:
                sources = [x[:len(x)] for x in results]
            else:
                sources = [x[0] for x in results]
        elif os.path.exists(params):
            sources = open(params).read().split()
        else:
            sources = [params]
        if not sources:
            raise framework.FrameworkException('Source contains no input.')
        return sources

    #==================================================
    # REQUEST METHODS
    #==================================================

    def make_cookie(self, name, value, domain, path='/'):
        return http.cookiejar.Cookie(
            version=0, 
            name=name, 
            value=value,
            port=None, 
            port_specified=False,
            domain=domain, 
            domain_specified=True, 
            domain_initial_dot=False,
            path=path, 
            path_specified=True,
            secure=False,
            expires=None,
            discard=False,
            comment=None,
            comment_url=None,
            rest={}
        )

    #==================================================
    # MODULE EXECUTION
    #==================================================

    def run(self):
        """
        Execute the module.
        
        This method:
        1. Validates options
        2. Validates input
        3. Resets summary counts
        4. Calls module_pre() hook
        5. Calls module_run() with inputs
        6. Calls module_post() hook
        7. Updates the dashboard
        """
        self._validate_options()
        self._validate_input()
        self._summary_counts = {}
        pre = self.module_pre()
        params = [pre] if pre is not None else []
        # provide input if a default query is specified in the module
        if hasattr(self, '_default_source'):
            objs = self._get_source(self.options['source'], self._default_source)
            params.insert(0, objs)
        # update the dashboard before running the module
        # data is added at runtime, so even if an error occurs, any new items
        # must be accounted for by a module execution attempt
        self.query(f"INSERT OR REPLACE INTO dashboard (module, runs) VALUES ('{self._modulename}', COALESCE((SELECT runs FROM dashboard WHERE module='{self._modulename}')+1, 1))")
        self.module_run(*params)
        self.module_post()

    #==================================================
    # HOOK METHODS
    #==================================================

    def module_pre(self):
        """Hook called before module_run(). Return value is passed to module_run()."""
        pass

    def module_run(self):
        """Main module logic. Override this in your module."""
        pass

    def module_post(self):
        """Hook called after module_run(). Use for cleanup."""
        pass
