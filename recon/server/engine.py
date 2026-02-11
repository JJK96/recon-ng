"""
Engine - Core execution engine that wraps the existing Framework.
This provides a clean interface for the RPC handlers while reusing
the existing recon-ng logic.
"""
import os
import sys
import logging
import traceback
from typing import Any, Dict, List, Optional

from recon.server.context import ExecutionContext, RequestContext
from recon.server.interceptors import execution_context
from recon.server.events import EventPublisher, NullEventPublisher

logger = logging.getLogger(__name__)


class EngineError(Exception):
    """Base exception for engine errors"""
    pass


class WorkspaceNotFoundError(EngineError):
    """Raised when a workspace doesn't exist"""
    pass


class ModuleNotFoundError(EngineError):
    """Raised when a module doesn't exist"""
    pass


class Engine:
    """
    Core recon-ng engine that wraps the existing Framework.
    
    This class manages:
    - Workspace initialization and validation
    - Module loading and execution
    - Database operations
    - API key management
    - Marketplace operations
    
    It delegates to the existing Framework/Recon classes but provides
    a cleaner interface for the RPC layer.
    """
    
    def __init__(self, home_path: str = None):
        """
        Initialize the engine.
        
        Args:
            home_path: Path to recon-ng home directory. Defaults to ~/.recon-ng
        """
        self.home_path = home_path or os.path.join(os.path.expanduser('~'), '.recon-ng')
        self.spaces_path = os.path.join(self.home_path, 'workspaces')
        self.mod_path = os.path.join(self.home_path, 'modules')
        self.data_path = os.path.join(self.home_path, 'data')
        
        # Ensure directories exist
        os.makedirs(self.spaces_path, exist_ok=True)
        os.makedirs(self.mod_path, exist_ok=True)
        os.makedirs(self.data_path, exist_ok=True)
        
        # Import here to avoid circular imports and to allow patching paths
        from recon.core import base, framework
        self._framework = framework  # Store reference for later use
        
        # Patch the framework paths before creating the Recon instance
        framework.Framework.app_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        framework.Framework.home_path = self.home_path
        framework.Framework.mod_path = self.mod_path
        framework.Framework.data_path = self.data_path
        framework.Framework.spaces_path = self.spaces_path
        
        # Create a Recon instance for module management
        # We use Mode.JOB to suppress interactive features
        self._recon = base.Recon(check=False, analytics=False, marketplace=True)
        self._Mode = base.Mode
        
        # Initialize mode and global options (required before any framework operations)
        self._recon._mode = framework.Framework._mode = base.Mode.JOB
        self._recon._init_global_options()
        self._recon._init_home()
        
        # Initialize module tracking (needed before marketplace operations)
        self._recon._loaded_category = {}
        self._recon._loaded_modules = framework.Framework._loaded_modules = {}
        
        # Load modules ONCE at startup - they are workspace-independent
        self._recon._load_modules()
        
        # Track loaded modules by workspace
        self._workspace_modules: Dict[str, Dict] = {}
    
    def _get_workspace_path(self, workspace: str) -> str:
        """Get the full path to a workspace"""
        return os.path.join(self.spaces_path, workspace)
    
    def _ensure_workspace_exists(self, workspace: str):
        """Ensure a workspace exists, raise error if not"""
        path = self._get_workspace_path(workspace)
        if not os.path.exists(path):
            raise WorkspaceNotFoundError(f"Workspace '{workspace}' does not exist")
    
    def _init_workspace(self, workspace: str):
        """
        Initialize the recon instance for a workspace (lightweight).
        
        This only sets the workspace path and ensures the DB exists.
        Modules are loaded once at server startup and shared across all workspaces.
        """
        path = os.path.join(self.spaces_path, workspace)
        self._recon.workspace = self._framework.Framework.workspace = path
        
        # Ensure workspace directory and database exist
        if not os.path.exists(path):
            os.makedirs(path)
            self._recon._create_db()
        else:
            self._recon._migrate_db()
    
    # =========================================================
    # Workspace Operations
    # =========================================================
    
    def list_workspaces(self) -> List[str]:
        """List all available workspaces"""
        workspaces = []
        if os.path.exists(self.spaces_path):
            for name in os.listdir(self.spaces_path):
                if os.path.isdir(os.path.join(self.spaces_path, name)):
                    workspaces.append(name)
        return sorted(workspaces)
    
    def workspace_exists(self, workspace: str) -> bool:
        """Check if a workspace exists"""
        return os.path.exists(self._get_workspace_path(workspace))
    
    def create_workspace(self, workspace: str) -> bool:
        """Create a new workspace"""
        if self.workspace_exists(workspace):
            return False
        
        # Initialize the workspace (this creates the directory and database)
        self._init_workspace(workspace)
        return True
    
    def delete_workspace(self, workspace: str) -> bool:
        """Delete a workspace"""
        if not self.workspace_exists(workspace):
            return False
        return self._recon.remove_workspace(workspace)
    
    def get_workspace_info(self, workspace: str) -> Dict[str, Any]:
        """Get information about a workspace"""
        self._ensure_workspace_exists(workspace)
        self._init_workspace(workspace)
        
        tables = self._recon.get_tables()
        total_records = 0
        table_counts = {}
        for table in tables:
            count = self._recon.query(f'SELECT COUNT(*) FROM "{table}"')[0][0]
            table_counts[table] = count
            total_records += count
        
        return {
            'name': workspace,
            'tables': tables,
            'table_counts': table_counts,
            'total_records': total_records
        }
    
    # =========================================================
    # Module Operations
    # =========================================================
    
    def list_modules(self, category: str = None) -> List[Dict[str, Any]]:
        """List available modules, optionally filtered by category"""
        # Make sure modules are loaded
        if not self._recon._loaded_modules:
            self._recon._load_modules()
        
        modules = []
        for path, module in self._recon._loaded_modules.items():
            if category and not path.startswith(category + '/'):
                continue
            modules.append({
                'path': path,
                'name': module.meta.get('name', ''),
                'description': module.meta.get('description', ''),
                'version': module.meta.get('version', '1.0'),
                'author': module.meta.get('author', ''),
            })
        
        return sorted(modules, key=lambda x: x['path'])
    
    def search_modules(self, term: str) -> List[Dict[str, Any]]:
        """Search modules by term (searches path, name, description)"""
        term = term.lower()
        results = []
        
        for module in self.list_modules():
            if (term in module['path'].lower() or 
                term in module['name'].lower() or 
                term in module['description'].lower()):
                results.append(module)
        
        return results
    
    def get_module_info(self, path: str) -> Dict[str, Any]:
        """Get detailed information about a module"""
        if not self._recon._loaded_modules:
            self._recon._load_modules()
        
        if path not in self._recon._loaded_modules:
            raise ModuleNotFoundError(f"Module '{path}' not found")
        
        module = self._recon._loaded_modules[path]
        meta = module.meta
        
        # Get options
        options = []
        for name, opt in module.options.items():
            options.append({
                'name': name,
                'value': opt,
                'required': module.options.required.get(name, False),
                'description': module.options.description.get(name, '')
            })
        
        return {
            'path': path,
            'name': meta.get('name', ''),
            'author': meta.get('author', ''),
            'version': meta.get('version', '1.0'),
            'description': meta.get('description', ''),
            'options': options,
            'required_keys': meta.get('required_keys', []),
            'dependencies': meta.get('dependencies', []),
            'files': meta.get('files', []),
            'comments': meta.get('comments', []),
            'query': meta.get('query')
        }
    
    def reload_modules(self, path: str = None) -> List[str]:
        """Reload modules, optionally just a specific one"""
        if path:
            # Reload specific module
            module = self._recon._loaded_modules.get(path)
            if module:
                import sys
                mod_loadpath = os.path.abspath(sys.modules[module.__module__].__file__)
                self._recon._load_module(os.path.dirname(mod_loadpath), os.path.basename(mod_loadpath))
        else:
            # Reload all
            self._recon._load_modules()
        
        return list(self._recon._loaded_modules.keys())
    
    def run_module(
        self,
        workspace: str,
        path: str,
        options: Dict[str, Any],
        global_options: Dict[str, Any],
        ctx: ExecutionContext,
        file_content: str = None,
        file_name: str = None
    ) -> Dict[str, Any]:
        """
        Run a module with the given options.
        
        Args:
            workspace: Workspace name
            path: Module path
            options: Module-specific options
            global_options: Global option overrides
            ctx: Execution context for events and input
            file_content: Optional file content for import modules
            file_name: Original filename for file_content
            
        Returns:
            Dictionary with execution summary
        """
        self._ensure_workspace_exists(workspace)
        self._init_workspace(workspace)
        
        if path not in self._recon._loaded_modules:
            raise ModuleNotFoundError(f"Module '{path}' not found")
        
        module = self._recon._loaded_modules[path]
        
        # Get declared dependencies for error messages
        declared_deps = module.meta.get('dependencies', [])
        
        # Apply global options
        for name, value in global_options.items():
            name_upper = name.upper()
            if name_upper in self._recon._global_options:
                self._recon._global_options[name_upper] = value
        
        # Handle file content injection for import modules
        content_id = None
        if file_content is not None:
            content_id = ctx.store_content(file_content)
            # Set the SOURCE or FILENAME option to use injected content
            if 'SOURCE' in options and options['SOURCE']:
                pass  # Keep user's source option
            elif 'FILENAME' in [o.upper() for o in module.options.keys()]:
                options['FILENAME'] = f'__content__:{content_id}'
            elif 'SOURCE' in [o.upper() for o in module.options.keys()]:
                options['SOURCE'] = f'__content__:{content_id}'
        
        # Apply module options
        for name, value in options.items():
            name_upper = name.upper()
            if name_upper in module.options:
                module.options[name_upper] = value
        
        # Run the module within execution context
        summary = {}
        try:
            with execution_context(ctx):
                module.run()
                summary = dict(module._summary_counts) if hasattr(module, '_summary_counts') else {}
        except ImportError as e:
            # Handle missing Python dependencies
            deps_hint = ""
            if declared_deps:
                deps_hint = f" Declared dependencies: {', '.join(declared_deps)}."
            error_msg = (
                f"Import error while running module '{path}': {e}.{deps_hint} "
                f"Please install missing packages in the Docker container "
                f"(e.g., 'docker exec -it recon-server pip install <package>')."
            )
            ctx.events.exception(
                exc_type='ImportError',
                message=error_msg,
                traceback=traceback.format_exc()
            )
            raise EngineError(error_msg) from e
        except FileNotFoundError as e:
            # Handle missing system commands/binaries
            deps_hint = ""
            if declared_deps:
                deps_hint = f" Declared dependencies: {', '.join(declared_deps)}."
            error_msg = (
                f"Command or file not found while running module '{path}': {e}.{deps_hint} "
                f"Please install missing system packages in the Docker container "
                f"(e.g., 'docker exec -it recon-server apt-get install <package>')."
            )
            ctx.events.exception(
                exc_type='FileNotFoundError',
                message=error_msg,
                traceback=traceback.format_exc()
            )
            raise EngineError(error_msg) from e
        except OSError as e:
            # Handle other OS errors that might indicate missing dependencies
            if e.errno == 2:  # ENOENT - No such file or directory
                deps_hint = ""
                if declared_deps:
                    deps_hint = f" Declared dependencies: {', '.join(declared_deps)}."
                error_msg = (
                    f"Command or file not found while running module '{path}': {e}.{deps_hint} "
                    f"Please install missing system packages in the Docker container "
                    f"(e.g., 'docker exec -it recon-server apt-get install <package>')."
                )
                ctx.events.exception(
                    exc_type='OSError',
                    message=error_msg,
                    traceback=traceback.format_exc()
                )
                raise EngineError(error_msg) from e
            else:
                ctx.events.exception(
                    exc_type=type(e).__name__,
                    message=str(e),
                    traceback=traceback.format_exc()
                )
                raise
        except Exception as e:
            ctx.events.exception(
                exc_type=type(e).__name__,
                message=str(e),
                traceback=traceback.format_exc()
            )
            raise
        finally:
            # Clean up injected content
            if content_id:
                ctx.clear_content(content_id)
        
        return {
            'success': True,
            'summary': summary
        }
    
    # =========================================================
    # Database Operations
    # =========================================================
    
    def get_tables(self, workspace: str) -> List[str]:
        """Get list of tables in workspace database"""
        self._ensure_workspace_exists(workspace)
        self._init_workspace(workspace)
        return self._recon.get_tables()
    
    def get_columns(self, workspace: str, table: str) -> List[Dict[str, str]]:
        """Get columns for a table"""
        self._ensure_workspace_exists(workspace)
        self._init_workspace(workspace)
        columns = self._recon.get_columns(table)
        return [{'name': c[0], 'type': c[1]} for c in columns]
    
    def query(self, workspace: str, sql: str) -> Dict[str, Any]:
        """Execute a SQL query"""
        self._ensure_workspace_exists(workspace)
        self._init_workspace(workspace)
        
        result = self._recon.query(sql, include_header=True)
        
        if isinstance(result, list) and len(result) > 0:
            header = result[0]
            rows = result[1:] if len(result) > 1 else []
            return {'header': list(header), 'rows': [list(r) for r in rows]}
        else:
            return {'affected': result if isinstance(result, int) else 0}
    
    def insert(self, workspace: str, table: str, data: Dict[str, Any]) -> int:
        """Insert a record into a table"""
        self._ensure_workspace_exists(workspace)
        self._init_workspace(workspace)
        
        # Use the appropriate insert method
        method_name = f'insert_{table}'
        if hasattr(self._recon, method_name):
            method = getattr(self._recon, method_name)
            return method(**data)
        else:
            # Generic insert
            return self._recon.insert(table, data)
    
    def delete(self, workspace: str, table: str, rowids: List[int]) -> int:
        """Delete records from a table"""
        self._ensure_workspace_exists(workspace)
        self._init_workspace(workspace)
        
        count = 0
        for rowid in rowids:
            count += self._recon.query(f'DELETE FROM "{table}" WHERE ROWID = ?', (rowid,))
        return count
    
    def update_notes(self, workspace: str, table: str, rowids: List[int], note: str) -> int:
        """Update notes for records in a table"""
        self._ensure_workspace_exists(workspace)
        self._init_workspace(workspace)
        
        count = 0
        for rowid in rowids:
            count += self._recon.query(f'UPDATE "{table}" SET notes = ? WHERE ROWID = ?', (note, rowid))
        return count
    
    def export_table(
        self,
        workspace: str,
        table: str,
        format: str = 'list',
        column: str = None,
        unique: bool = True,
        include_nulls: bool = False
    ) -> Dict[str, Any]:
        """Export table data in various formats"""
        self._ensure_workspace_exists(workspace)
        self._init_workspace(workspace)
        
        columns = [c['name'] for c in self.get_columns(workspace, table)]
        
        if format == 'list' and column:
            # Single column export
            null_clause = '' if include_nulls else f' WHERE "{column}" IS NOT NULL'
            unique_clause = 'DISTINCT ' if unique else ''
            sql = f'SELECT {unique_clause}"{column}" FROM "{table}"{null_clause} ORDER BY 1'
            rows = self._recon.query(sql)
            return {
                'format': 'list',
                'data': [row[0] for row in rows if row[0] is not None or include_nulls]
            }
        else:
            # Full table export
            rows = self._recon.query(f'SELECT * FROM "{table}"')
            
            if format == 'csv':
                import csv
                import io
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(columns)
                writer.writerows(rows)
                return {'format': 'csv', 'data': output.getvalue()}
            
            elif format == 'json':
                import json
                data = [dict(zip(columns, row)) for row in rows]
                return {'format': 'json', 'data': json.dumps(data, indent=2)}
            
            elif format == 'jsonl':
                import json
                lines = [json.dumps(dict(zip(columns, row))) for row in rows]
                return {'format': 'jsonl', 'data': '\n'.join(lines)}
            
            else:  # list format, all columns
                return {
                    'format': 'table',
                    'header': columns,
                    'rows': [list(row) for row in rows]
                }
    
    # =========================================================
    # API Key Operations
    # =========================================================
    
    def list_keys(self) -> List[Dict[str, Any]]:
        """List all API keys"""
        rows = self._recon._query_keys('SELECT name, value FROM keys')
        return [{'name': row[0], 'value': row[1]} for row in rows]
    
    def get_key(self, name: str) -> Optional[str]:
        """Get an API key value"""
        return self._recon.get_key(name)
    
    def add_key(self, name: str, value: str) -> bool:
        """Add or update an API key"""
        self._recon.add_key(name, value)
        return True
    
    def delete_key(self, name: str) -> bool:
        """Delete an API key"""
        self._recon._query_keys('DELETE FROM keys WHERE name=?', (name,))
        return True
    
    # =========================================================
    # Marketplace Operations
    # =========================================================
    
    def marketplace_refresh(self) -> bool:
        """Refresh the module index from repository"""
        self._recon._fetch_module_index()
        self._recon._update_module_index()
        return True
    
    def marketplace_search(self, term: str) -> List[Dict[str, Any]]:
        """Search the marketplace"""
        if not hasattr(self._recon, '_module_index') or not self._recon._module_index:
            self._recon._update_module_index()
        
        modules = self._recon._search_module_index(term)
        return [
            {
                'path': m['path'],
                'name': m['name'],
                'description': m['description'],
                'version': m['version'],
                'status': m.get('status', 'not installed'),
                'author': m.get('author', ''),
                'required_keys': m.get('required_keys', []),
                'dependencies': m.get('dependencies', [])
            }
            for m in modules
        ]
    
    def marketplace_info(self, path: str) -> Dict[str, Any]:
        """Get information about a marketplace module"""
        if not hasattr(self._recon, '_module_index') or not self._recon._module_index:
            self._recon._update_module_index()
        
        module = self._recon._get_module_from_index(path)
        if not module:
            raise ModuleNotFoundError(f"Module '{path}' not found in marketplace")
        
        return module
    
    def marketplace_install(self, path: str) -> bool:
        """Install a module from the marketplace"""
        # Ensure module index is loaded
        if not hasattr(self._recon, '_module_index') or not self._recon._module_index:
            self._recon._update_module_index()
        
        try:
            self._recon._install_module(path)
            self._recon._load_modules()
            return True
        except Exception as e:
            logger.error(f"Failed to install module {path}: {e}")
            raise
    
    def marketplace_install_all(self) -> Dict[str, Any]:
        """Install all modules from the marketplace"""
        if not hasattr(self._recon, '_module_index') or not self._recon._module_index:
            self._recon._update_module_index()
        
        # Get all modules that are not installed
        all_modules = self._recon._module_index
        installed = []
        failed = []
        skipped = []
        
        for module in all_modules:
            path = module['path']
            status = module.get('status', 'not installed')
            
            if status == 'installed':
                skipped.append(path)
                continue
            
            try:
                self._recon._install_module(path)
                installed.append(path)
            except Exception as e:
                logger.error(f"Failed to install module {path}: {e}")
                failed.append({'path': path, 'error': str(e)})
        
        # Reload all modules once at the end
        self._recon._load_modules()
        
        return {
            'installed': installed,
            'failed': failed,
            'skipped': skipped,
            'total': len(all_modules)
        }
    
    def marketplace_remove(self, path: str) -> bool:
        """Remove an installed module"""
        try:
            self._recon._remove_module(path)
            self._recon._load_modules()
            return True
        except Exception as e:
            logger.error(f"Failed to remove module {path}: {e}")
            raise
    
    # =========================================================
    # Dashboard Operations
    # =========================================================
    
    def get_dashboard(self, workspace: str) -> Dict[str, Any]:
        """Get dashboard data for a workspace"""
        self._ensure_workspace_exists(workspace)
        self._init_workspace(workspace)
        
        # Activity data
        activity = []
        rows = self._recon.query('SELECT * FROM dashboard ORDER BY 1')
        for row in rows:
            activity.append({'module': row[0], 'runs': row[1]})
        
        # Summary data
        summary = []
        for table in self._recon.get_tables():
            if table == 'dashboard':
                continue
            count = self._recon.query(f'SELECT COUNT(*) FROM "{table}"')[0][0]
            summary.append({'table': table, 'count': count})
        
        return {
            'activity': activity,
            'summary': summary
        }
    
    # =========================================================
    # Snapshot Operations
    # =========================================================
    
    def list_snapshots(self, workspace: str) -> List[str]:
        """List snapshots for a workspace"""
        self._ensure_workspace_exists(workspace)
        self._init_workspace(workspace)
        return self._recon._get_snapshots()
    
    def take_snapshot(self, workspace: str, name: str = None) -> str:
        """Take a snapshot of the workspace database"""
        import shutil
        from datetime import datetime
        
        self._ensure_workspace_exists(workspace)
        workspace_path = self._get_workspace_path(workspace)
        
        if name is None:
            name = f"snapshot_{datetime.strftime(datetime.now(), '%Y%m%d%H%M%S')}"
        
        src = os.path.join(workspace_path, 'data.db')
        dst = os.path.join(workspace_path, f'{name}.db')
        shutil.copy(src, dst)
        
        return name
    
    def load_snapshot(self, workspace: str, name: str) -> bool:
        """Load a snapshot into the workspace database"""
        import shutil
        
        self._ensure_workspace_exists(workspace)
        workspace_path = self._get_workspace_path(workspace)
        
        src = os.path.join(workspace_path, f'{name}.db' if not name.endswith('.db') else name)
        dst = os.path.join(workspace_path, 'data.db')
        
        if not os.path.exists(src):
            return False
        
        shutil.copy(src, dst)
        return True
    
    def delete_snapshot(self, workspace: str, name: str) -> bool:
        """Delete a snapshot"""
        self._ensure_workspace_exists(workspace)
        workspace_path = self._get_workspace_path(workspace)
        
        path = os.path.join(workspace_path, name if name.endswith('.db') else f'{name}.db')
        if os.path.exists(path):
            os.remove(path)
            return True
        return False
    
    # =========================================================
    # Global Options
    # =========================================================
    
    def get_global_options(self) -> Dict[str, Any]:
        """Get global options with their defaults"""
        options = {}
        for name in self._recon._global_options:
            options[name] = {
                'value': self._recon._global_options[name],
                'required': self._recon._global_options.required.get(name, False),
                'description': self._recon._global_options.description.get(name, '')
            }
        return options
    
    def set_global_option(self, name: str, value: Any) -> bool:
        """Set a global option value"""
        name_upper = name.upper()
        if name_upper in self._recon._global_options:
            self._recon._global_options[name_upper] = value
            return True
        return False
    
    def unset_global_option(self, name: str) -> bool:
        """Unset (reset to default) a global option"""
        name_upper = name.upper()
        if name_upper in self._recon._global_options:
            # Reset to None - the framework will use defaults
            self._recon._global_options[name_upper] = None
            return True
        return False
    
    def get_module_inputs(self, workspace: str, path: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get the input data for a module based on the SOURCE option.
        
        Args:
            workspace: Workspace name
            path: Module path
            options: Optional options overrides (including 'source')
            
        Returns:
            Dictionary with 'inputs' list or 'error' message
        """
        self._ensure_workspace_exists(workspace)
        self._init_workspace(workspace)
        
        if path not in self._recon._loaded_modules:
            raise ModuleNotFoundError(f"Module '{path}' not found")
        
        module = self._recon._loaded_modules[path]
        
        # Check if module has a default source (meaning it uses SOURCE option)
        if not hasattr(module, '_default_source'):
            return {'inputs': [], 'error': 'Source option not available for this module.'}
        
        # Apply any option overrides
        if options:
            for name, value in options.items():
                name_upper = name.upper()
                if name_upper in module.options:
                    module.options[name_upper] = value
        
        # Get the current SOURCE value
        source_value = module.options.get('SOURCE', 'default')
        default_query = module._default_source
        
        try:
            inputs = module._get_source(source_value, default_query)
            # Convert inputs to strings for serialization
            inputs_list = [str(x) if not isinstance(x, (list, tuple)) else list(x) for x in inputs]
            return {'inputs': inputs_list}
        except Exception as e:
            return {'inputs': [], 'error': str(e)}
