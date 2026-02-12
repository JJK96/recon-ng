"""
Recon-ng Base Module

This module provides the Recon class which manages:
- Workspace initialization and management
- Module loading and categorization
- Marketplace operations (install, remove, search)
- Global options and configuration

This module does NOT contain any CLI-specific code. CLI functionality
is implemented in recon/client/.
"""

__author__    = 'Tim Tomes (@lanmaster53)'

from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
import errno
import importlib.util
import importlib.machinery
from importlib.machinery import SourceFileLoader
import json
import os
import random
import re
import shutil
import sys
import traceback
import yaml

# import framework libs
from recon.core import framework

# set the __version__ variable based on the VERSION file
exec(open(os.path.join(Path(os.path.abspath(__file__)).parents[2], 'VERSION')).read())

#=================================================
# BASE CLASS
#=================================================

class Recon(framework.Framework):
    """
    Core Recon class providing business logic for workspace and module management.
    
    This class is used by the server's Engine class. It does not inherit
    from cmd.Cmd and contains no CLI-specific code.
    """

    repo_url = 'https://raw.githubusercontent.com/lanmaster53/recon-ng-modules/master/'

    def __init__(self, check=True, analytics=True, marketplace=True, accessible=False):
        framework.Framework.__init__(self, 'base')
        self._name = 'recon-ng'
        # set toggle flags
        self._check = check
        self._analytics = analytics
        self._marketplace = marketplace
        self._accessible = accessible
        # set path variables
        self.app_path = framework.Framework.app_path = sys.path[0]
        self.core_path = framework.Framework.core_path = os.path.join(self.app_path, 'core')
        self.home_path = framework.Framework.home_path = os.path.join(os.path.expanduser('~'), '.recon-ng')
        self.mod_path = framework.Framework.mod_path = os.path.join(self.home_path, 'modules')
        self.data_path = framework.Framework.data_path = os.path.join(self.home_path, 'data')
        self.spaces_path = framework.Framework.spaces_path = os.path.join(self.home_path, 'workspaces')
        # Initialize module tracking
        self._loaded_category = {}
        self._loaded_modules = framework.Framework._loaded_modules = {}
        # Module index for marketplace
        self._module_index = []

    def start(self, mode, workspace='default'):
        """
        Initialize framework components and workspace.
        
        Args:
            mode: Operation mode (Mode.JOB for server, Mode.CONSOLE for CLI)
            workspace: Name of workspace to load
        """
        self._mode = framework.Framework._mode = mode
        self._init_global_options()
        self._init_home()
        self._init_workspace(workspace)
        self._check_version()

    #==================================================
    # OUTPUT METHODS (stubs for modules)
    #==================================================

    def print_exception(self):
        """Print exception traceback (for module error handling)."""
        # In server mode, we log to stderr; client has its own handling
        import traceback
        traceback.print_exc()

    #==================================================
    # SUPPORT METHODS
    #==================================================

    def _init_global_options(self):
        self.options = self._global_options
        self.register_option('nameserver', '8.8.8.8', True, 'default nameserver for the resolver mixin')
        self.register_option('proxy', None, False, 'proxy server (address:port)')
        self.register_option('threads', 10, True, 'number of threads (where applicable)')
        self.register_option('timeout', 10, True, 'socket timeout (seconds)')
        self.register_option('user-agent', f"Recon-ng/v{__version__.split('.')[0]}", True, 'user-agent string')
        self.register_option('verbosity', 1, True, 'verbosity level (0 = minimal, 1 = verbose, 2 = debug)')

    def _init_home(self):
        # initialize home folder
        if not os.path.exists(self.home_path):
            os.makedirs(self.home_path)
        # initialize keys database
        self._query_keys('CREATE TABLE IF NOT EXISTS keys (name TEXT PRIMARY KEY, value TEXT)')
        # initialize module index
        self._fetch_module_index()

    def _check_version(self):
        if self._check:
            pattern = r"'(\d+\.\d+\.\d+[^']*)'"
            remote = 0
            try:
                remote = re.search(pattern, self.request('GET', 'https://raw.githubusercontent.com/lanmaster53/recon-ng/master/VERSION').text).group(1)
            except Exception as e:
                self.error(f"Version check failed ({type(e).__name__}).")
            if remote != __version__:
                self.alert('Your version of Recon-ng does not match the latest release.')
                self.alert('Please consider updating before further use.')
                self.output(f"Remote version:  {remote}")
                self.output(f"Local version:   {__version__}")
        else:
            self.alert('Version check disabled.')

    def _send_analytics(self, cd):
        """Send analytics data (for module usage tracking)."""
        if self._analytics:
            try:
                cid_path = os.path.join(self.home_path, '.cid')
                if not os.path.exists(cid_path):
                    # create the cid and file
                    import uuid
                    with open(cid_path, 'w') as fp:
                        fp.write(self.to_unicode_str(uuid.uuid4()))
                with open(cid_path) as fp:
                    cid = fp.read().strip()
                params = {
                        'v': 1,
                        'tid': 'UA-52269615-2',
                        'cid': cid,
                        't': 'screenview',
                        'an': 'Recon-ng',
                        'av': __version__,
                        'cd': cd
                        }
                self.request('GET', 'https://www.google-analytics.com/collect', params=params)
            except Exception as e:
                self.debug(f"Analytics failed ({type(e).__name__}).")
                return
        else:
            self.debug('Analytics disabled.')

    def _load_source(self, modname, filename):
        loader = importlib.machinery.SourceFileLoader(modname, filename)
        spec = importlib.util.spec_from_file_location(modname, filename, loader=loader)
        module = importlib.util.module_from_spec(spec)
        # cache the module in sys.modules
        sys.modules[module.__name__] = module
        loader.exec_module(module)
        return module

    #==================================================
    # WORKSPACE METHODS
    #==================================================

    def _init_workspace(self, workspace):
        if not workspace:
            return
        path = os.path.join(self.spaces_path, workspace)
        self.workspace = framework.Framework.workspace = path
        if not os.path.exists(path):
            os.makedirs(path)
            self._create_db()
        else:
            self._migrate_db()
        # load workspace configuration
        self._load_config()
        # reload modules after config to populate options
        self._load_modules()
        return True

    def remove_workspace(self, workspace):
        path = os.path.join(self.spaces_path, workspace)
        try:
            shutil.rmtree(path)
        except OSError:
            return False
        if workspace == self.workspace.split('/')[-1]:
            self._init_workspace('default')
        return True

    def _get_workspaces(self):
        workspaces = []
        path = self.spaces_path
        if os.path.exists(path):
            for name in os.listdir(path):
                if os.path.isdir(os.path.join(path, name)):
                    workspaces.append(name)
        return workspaces

    def _get_snapshots(self):
        snapshots = []
        if os.path.exists(self.workspace):
            for f in os.listdir(self.workspace):
                if re.search(r'^snapshot_\d{14}.db$', f):
                    snapshots.append(f)
        return snapshots

    def _create_db(self):
        self.query('CREATE TABLE IF NOT EXISTS domains (domain TEXT, notes TEXT, module TEXT)')
        self.query('CREATE TABLE IF NOT EXISTS companies (company TEXT, description TEXT, notes TEXT, module TEXT)')
        self.query('CREATE TABLE IF NOT EXISTS tenants (brand TEXT, name TEXT, id TEXT, region TEXT, subregion TEXT, domain TEXT, desktopSSOEnabled BOOLEAN, CBAEnabled BOOLEAN, usesCloudSync BOOLEAN, module TEXT)')
        self.query('CREATE TABLE IF NOT EXISTS netblocks (netblock TEXT, notes TEXT, module TEXT)')
        self.query('CREATE TABLE IF NOT EXISTS locations (latitude TEXT, longitude TEXT, street_address TEXT, notes TEXT, module TEXT)')
        self.query('CREATE TABLE IF NOT EXISTS vulnerabilities (host TEXT, reference TEXT, example TEXT, publish_date TEXT, category TEXT, status TEXT, notes TEXT, module TEXT)')
        self.query('CREATE TABLE IF NOT EXISTS ports (ip_address TEXT, host TEXT, port TEXT, protocol TEXT, banner TEXT, notes TEXT, module TEXT)')
        self.query('CREATE TABLE IF NOT EXISTS hosts (host TEXT, cname TEXT, ip_address TEXT, region TEXT, country TEXT, latitude TEXT, longitude TEXT, organization TEXT, notes TEXT, module TEXT)')
        self.query('CREATE TABLE IF NOT EXISTS contacts (first_name TEXT, middle_name TEXT, last_name TEXT, email TEXT, title TEXT, region TEXT, country TEXT, phone TEXT, notes TEXT, module TEXT)')
        self.query('CREATE TABLE IF NOT EXISTS credentials (username TEXT, password TEXT, hash TEXT, type TEXT, leak TEXT, notes TEXT, module TEXT)')
        self.query('CREATE TABLE IF NOT EXISTS leaks (leak_id TEXT, description TEXT, source_refs TEXT, leak_type TEXT, title TEXT, import_date TEXT, leak_date TEXT, attackers TEXT, num_entries TEXT, score TEXT, num_domains_affected TEXT, attack_method TEXT, target_industries TEXT, password_hash TEXT, password_type TEXT, targets TEXT, media_refs TEXT, notes TEXT, module TEXT)')
        self.query('CREATE TABLE IF NOT EXISTS pushpins (source TEXT, screen_name TEXT, profile_name TEXT, profile_url TEXT, media_url TEXT, thumb_url TEXT, message TEXT, latitude TEXT, longitude TEXT, time TEXT, notes TEXT, module TEXT)')
        self.query('CREATE TABLE IF NOT EXISTS profiles (username TEXT, resource TEXT, url TEXT, category TEXT, contact_id INTEGER, notes TEXT, module TEXT)')
        self.query('CREATE TABLE IF NOT EXISTS repositories (name TEXT, owner TEXT, description TEXT, resource TEXT, category TEXT, url TEXT, notes TEXT, module TEXT)')
        self.query('CREATE TABLE IF NOT EXISTS dashboard (module TEXT PRIMARY KEY, runs INT)')
        self.query('PRAGMA user_version = 13')

    def _migrate_db(self):
        db_version = lambda self: self.query('PRAGMA user_version')[0][0]
        db_orig = db_version(self)
        if db_version(self) == 0:
            # add mname column to contacts table
            tmp = self.get_random_str(20)
            self.query(f"ALTER TABLE contacts RENAME TO {tmp}")
            self.query('CREATE TABLE contacts (fname TEXT, mname TEXT, lname TEXT, email TEXT, title TEXT, region TEXT, country TEXT)')
            self.query(f"INSERT INTO contacts (fname, lname, email, title, region, country) SELECT fname, lname, email, title, region, country FROM {tmp}")
            self.query(f"DROP TABLE {tmp}")
            self.query('PRAGMA user_version = 1')
        if db_version(self) == 1:
            # rename name columns
            tmp = self.get_random_str(20)
            self.query(f"ALTER TABLE contacts RENAME TO {tmp}")
            self.query('CREATE TABLE contacts (first_name TEXT, middle_name TEXT, last_name TEXT, email TEXT, title TEXT, region TEXT, country TEXT)')
            self.query(f"INSERT INTO contacts (first_name, middle_name, last_name, email, title, region, country) SELECT fname, mname, lname, email, title, region, country FROM {tmp}")
            self.query(f"DROP TABLE {tmp}")
            # rename pushpin table
            self.query('ALTER TABLE pushpin RENAME TO pushpins')
            # add new tables
            self.query('CREATE TABLE IF NOT EXISTS domains (domain TEXT)')
            self.query('CREATE TABLE IF NOT EXISTS companies (company TEXT, description TEXT)')
            self.query('CREATE TABLE IF NOT EXISTS netblocks (netblock TEXT)')
            self.query('CREATE TABLE IF NOT EXISTS locations (latitude TEXT, longitude TEXT)')
            self.query('CREATE TABLE IF NOT EXISTS vulnerabilities (host TEXT, reference TEXT, example TEXT, publish_date TEXT, category TEXT)')
            self.query('CREATE TABLE IF NOT EXISTS ports (ip_address TEXT, host TEXT, port TEXT, protocol TEXT)')
            self.query('CREATE TABLE IF NOT EXISTS leaks (leak_id TEXT, description TEXT, source_refs TEXT, leak_type TEXT, title TEXT, import_date TEXT, leak_date TEXT, attackers TEXT, num_entries TEXT, score TEXT, num_domains_affected TEXT, attack_method TEXT, target_industries TEXT, password_hash TEXT, targets TEXT, media_refs TEXT)')
            self.query('PRAGMA user_version = 2')
        if db_version(self) == 2:
            # add street_address column to locations table
            self.query('ALTER TABLE locations ADD COLUMN street_address TEXT')
            self.query('PRAGMA user_version = 3')
        if db_version(self) == 3:
            # account for db_version bug
            if 'creds' in self.get_tables():
                # rename creds table
                self.query('ALTER TABLE creds RENAME TO credentials')
            self.query('PRAGMA user_version = 4')
        if db_version(self) == 4:
            # add status column to vulnerabilities table
            if 'status' not in [x[0] for x in self.get_columns('vulnerabilities')]:
                self.query('ALTER TABLE vulnerabilities ADD COLUMN status TEXT')
            # add module column to all tables
            for table in ['domains', 'companies', 'netblocks', 'locations', 'vulnerabilities', 'ports', 'hosts', 'contacts', 'credentials', 'leaks', 'pushpins']:
                if 'module' not in [x[0] for x in self.get_columns(table)]:
                    self.query(f"ALTER TABLE {table} ADD COLUMN module TEXT")
            self.query('PRAGMA user_version = 5')
        if db_version(self) == 5:
            # add profile table
            self.query('CREATE TABLE IF NOT EXISTS profiles (username TEXT, resource TEXT, url TEXT, category TEXT, notes TEXT, module TEXT)')
            self.query('PRAGMA user_version = 6')
        if db_version(self) == 6:
            # add repositories table
            self.query('CREATE TABLE IF NOT EXISTS repositories (name TEXT, owner TEXT, description TEXT, resource TEXT, category TEXT, url TEXT, module TEXT)')
            self.query('PRAGMA user_version = 7')
        if db_version(self) == 7:
            # add password_type column to leaks table
            self.query('ALTER TABLE leaks ADD COLUMN password_type TEXT')
            self.query('UPDATE leaks SET password_type=\'unknown\'')
            self.query('PRAGMA user_version = 8')
        if db_version(self) == 8:
            # add banner column to ports table
            self.query('ALTER TABLE ports ADD COLUMN banner TEXT')
            # add notes column to all tables
            for table in ['domains', 'companies', 'netblocks', 'locations', 'vulnerabilities', 'ports', 'hosts', 'contacts', 'credentials', 'leaks', 'pushpins', 'profiles', 'repositories']:
                if 'notes' not in [x[0] for x in self.get_columns(table)]:
                    self.query(f"ALTER TABLE {table} ADD COLUMN notes TEXT")
            self.query('PRAGMA user_version = 9')
        if db_version(self) == 9:
            # add phone column to contacts table
            self.query('ALTER TABLE contacts ADD COLUMN phone TEXT')
            self.query('PRAGMA user_version = 10')
        if db_version(self) == 10:
            self.query('ALTER TABLE profiles ADD COLUMN contact_id INTEGER')
            self.query('ALTER TABLE hosts ADD COLUMN organization TEXT')
            self.query('PRAGMA user_version = 11')
        if db_version(self) == 11:
            self.query('CREATE TABLE IF NOT EXISTS tenants (brand TEXT, name TEXT, id TEXT, region TEXT, subregion TEXT, domain TEXT, desktopSSOEnabled BOOLEAN, CBAEnabled BOOLEAN, usesCloudSync BOOLEAN, module TEXT)')
            self.query('PRAGMA user_version = 12')
        if db_version(self) == 12:
            self.query('ALTER TABLE hosts ADD COLUMN cname TEXT')
            self.query('PRAGMA user_version = 13')
        if db_orig != db_version(self):
            self.alert(f"Database upgraded to version {db_version(self)}.")

    #==================================================
    # MODULE METHODS
    #==================================================

    def _request_file_from_repo(self, path):
        resp = self.request('GET', urljoin(self.repo_url, path))
        if resp.status_code != 200:
            raise framework.FrameworkException(f"Invalid response from module repository ({resp.status_code}).")
        return resp

    def _write_local_file(self, path, content):
        dirpath = os.path.sep.join(path.split(os.path.sep)[:-1])
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)
        with open(path, 'w') as outfile:
            outfile.write(content)

    def _remove_empty_dirs(self, base_path):
        for root, dirs, files in os.walk(base_path, topdown=False):
            for rel_path in dirs:
                abs_path = os.path.join(root, rel_path)
                if os.path.exists(abs_path):
                    if not os.listdir(abs_path):
                        os.removedirs(abs_path)

    def _fetch_module_index(self):
        if self._marketplace:
            path = os.path.join(self.home_path, 'modules.yml')
            # Skip fetching if file already exists
            if os.path.exists(path):
                self.debug('Module index file already exists, skipping fetch.')
                return
            content = '[]'
            self.debug('Fetching index file...')
            try:
                resp = self._request_file_from_repo('modules.yml')
            except Exception as e:
                self.error(f"Unable to synchronize module index. ({type(e).__name__})")
                return
            content = resp.text
            self._write_local_file(path, content)
        else:
            self.alert('Marketplace disabled.')

    def _update_module_index(self):
        self.debug('Updating index file...')
        # initialize module index
        self._module_index = []
        # load module index from local copy
        path = os.path.join(self.home_path, 'modules.yml')
        if os.path.exists(path):
            with open(path, 'r') as infile:
                self._module_index = yaml.safe_load(infile) or []
            # add status to index for each module
            for module in self._module_index:
                status = 'not installed'
                if module['path'] in self._loaded_category.get('disabled', []):
                    status = 'disabled'
                elif module['path'] in self._loaded_modules.keys():
                    status = 'installed'
                    loaded = self._loaded_modules[module['path']]
                    # Handle modules that may be missing version in index
                    module_version = module.get('version')
                    loaded_version = loaded.meta.get('version')
                    if module_version and loaded_version and loaded_version != module_version:
                        status = 'outdated'
                module['status'] = status

    def _search_module_index(self, s):
        keys = ('path', 'name', 'description', 'status')
        modules = []
        for module in self._module_index:
            for key in keys:
                if re.search(s, module.get(key, '')):
                    modules.append(module)
                    break
        return modules

    def _get_module_from_index(self, path):
        for module in self._module_index:
            if module['path'] == path:
                return module
        return None

    def _install_module(self, path):
        # download supporting data files
        downloads = {}
        module_info = self._get_module_from_index(path)
        if not module_info:
            raise framework.FrameworkException(f"Module '{path}' not found in index.")
        files = module_info.get('files', [])
        for filename in files:
            try:
                resp = self._request_file_from_repo('/'.join(['data', filename]))
            except:
                self.error(f"Supporting file download for {path} failed: ({filename})")
                self.error('Module installation aborted.')
                raise
            abs_path = os.path.join(self.data_path, filename)
            downloads[abs_path] = resp.text
        # download the module
        rel_path = '.'.join([path, 'py'])
        try:
            resp = self._request_file_from_repo('/'.join(['modules', rel_path]))
        except:
            self.error(f"Module installation failed: {path}")
            raise
        abs_path = os.path.join(self.mod_path, rel_path)
        downloads[abs_path] = resp.text
        # install the module
        for abs_path, content in downloads.items():
            self._write_local_file(abs_path, content)
        self.output(f"Module installed: {path}")

    def _remove_module(self, path):
        # remove the module
        rel_path = '.'.join([path, 'py'])
        abs_path = os.path.join(self.mod_path, rel_path)
        os.remove(abs_path)
        # remove supporting data files
        module_info = self._get_module_from_index(path)
        if module_info:
            files = module_info.get('files', [])
            for filename in files:
                abs_path = os.path.join(self.data_path, filename)
                if os.path.exists(abs_path):
                    os.remove(abs_path)
        self.output(f"Module removed: {path}")

    def _load_modules(self):
        self._loaded_category = {}
        self._loaded_modules = framework.Framework._loaded_modules = {}
        # crawl the module directory and build the module tree
        if not os.path.exists(self.mod_path):
            return
        for dirpath, dirnames, filenames in os.walk(self.mod_path, followlinks=True):
            # remove hidden files and directories
            filenames = [f for f in filenames if not f[0] == '.']
            dirnames[:] = [d for d in dirnames if not d[0] == '.']
            if len(filenames) > 0:
                for filename in [f for f in filenames if f.endswith('.py')]:
                    self._load_module(dirpath, filename)
        # cleanup module directory
        self._remove_empty_dirs(self.mod_path)
        # update module index
        self._update_module_index()

    def _load_module(self, dirpath, filename):
        mod_name = filename.split('.')[0]
        mod_category = re.search('/modules/([^/]*)', dirpath).group(1)
        mod_dispname = '/'.join(re.split('/modules/', dirpath)[-1].split('/') + [mod_name])
        mod_loadname = mod_dispname.replace('/', '_')
        mod_loadpath = os.path.join(dirpath, filename)
        try:
            # import the module into memory
            mod = SourceFileLoader(mod_loadname, mod_loadpath).load_module()
            __import__(mod_loadname)
            # add the module to the framework's loaded modules
            self._loaded_modules[mod_dispname] = sys.modules[mod_loadname].Module(mod_dispname)
            self._categorize_module(mod_category, mod_dispname)
            # return indication of success to support module reload
            return True
        except ImportError as e:
            # notify the user of missing dependencies
            self.error(f"Module '{mod_dispname}' disabled. Dependency required: '{self.to_unicode_str(e)[16:]}'")
        except:
            # notify the user of errors
            self.print_exception()
            self.error(f"Module '{mod_dispname}' disabled.")
        # remove the module from the framework's loaded modules
        self._loaded_modules.pop(mod_dispname, None)
        self._categorize_module('disabled', mod_dispname)

    def _categorize_module(self, category, module):
        if not category in self._loaded_category:
            self._loaded_category[category] = []
        self._loaded_category[category].append(module)

    def get_loaded_module(self, path):
        """Get a loaded module by path."""
        return self._loaded_modules.get(path)


#=================================================
# SUPPORT CLASSES
#=================================================

class Mode(object):
   '''Contains constants that represent the state of the interpreter.'''
   CONSOLE = 0
   CLI     = 1
   WEB     = 2
   JOB     = 3
   
   def __init__(self):
       raise NotImplementedError('This class should never be instantiated.')
