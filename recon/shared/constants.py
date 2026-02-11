"""
Constants shared between client and server
"""

# Event types (server -> client)
class EventType:
    OUTPUT = 'output'
    ALERT = 'alert'
    ERROR = 'error'
    VERBOSE = 'verbose'
    DEBUG = 'debug'
    TABLE = 'table'
    HEADING = 'heading'
    PROGRESS = 'progress'
    INPUT_REQUIRED = 'input_required'
    FILE_OUTPUT = 'file_output'
    EXCEPTION = 'exception'


# Output levels for output events
class OutputLevel:
    INFO = 'info'
    SUCCESS = 'success'
    WARNING = 'warning'
    ERROR = 'error'


# RabbitMQ queue names
class Queues:
    RPC_REQUESTS = 'rpc.requests'
    
    @staticmethod
    def responses(client_id: str) -> str:
        return f'rpc.responses.{client_id}'
    
    @staticmethod
    def events(client_id: str) -> str:
        return f'events.{client_id}'


# RPC Commands
class Commands:
    # Workspaces
    WORKSPACES_LIST = 'workspaces/list'
    WORKSPACES_CREATE = 'workspaces/create'
    WORKSPACES_DELETE = 'workspaces/delete'
    WORKSPACES_INFO = 'workspaces/info'
    
    # Modules
    MODULES_LIST = 'modules/list'
    MODULES_SEARCH = 'modules/search'
    MODULES_LOAD = 'modules/load'
    MODULES_INFO = 'modules/info'
    MODULES_RUN = 'modules/run'
    MODULES_RELOAD = 'modules/reload'
    MODULES_INPUT = 'modules/input'
    
    # Options (server-side defaults)
    OPTIONS_LIST = 'options/list'
    OPTIONS_DEFAULTS = 'options/defaults'
    
    # Global Options
    GOPTIONS_LIST = 'goptions/list'
    GOPTIONS_SET = 'goptions/set'
    GOPTIONS_UNSET = 'goptions/unset'
    
    # Database
    DB_TABLES = 'db/tables'
    DB_SCHEMA = 'db/schema'
    DB_QUERY = 'db/query'
    DB_INSERT = 'db/insert'
    DB_DELETE = 'db/delete'
    DB_NOTES = 'db/notes'
    DB_EXPORT = 'db/export'
    
    # Keys
    KEYS_LIST = 'keys/list'
    KEYS_GET = 'keys/get'
    KEYS_ADD = 'keys/add'
    KEYS_DELETE = 'keys/delete'
    
    # Marketplace
    MARKETPLACE_SEARCH = 'marketplace/search'
    MARKETPLACE_INFO = 'marketplace/info'
    MARKETPLACE_INSTALL = 'marketplace/install'
    MARKETPLACE_INSTALL_ALL = 'marketplace/install_all'
    MARKETPLACE_REMOVE = 'marketplace/remove'
    MARKETPLACE_REFRESH = 'marketplace/refresh'
    
    # Dashboard
    DASHBOARD_SHOW = 'dashboard/show'
    
    # Input response
    INPUT_RESPONSE = 'input/response'
    
    # Snapshots
    SNAPSHOTS_LIST = 'snapshots/list'
    SNAPSHOTS_TAKE = 'snapshots/take'
    SNAPSHOTS_LOAD = 'snapshots/load'
    SNAPSHOTS_DELETE = 'snapshots/delete'


# Export formats
class ExportFormat:
    LIST = 'list'
    CSV = 'csv'
    JSON = 'json'
    JSONL = 'jsonl'
    XML = 'xml'


# Default values
DEFAULT_WORKSPACE = 'default'
DEFAULT_SERVER_URL = 'amqp://recon:recon@localhost:5672/'
DEFAULT_RECONNECT_ATTEMPTS = 5
DEFAULT_RECONNECT_DELAY = 2  # seconds
DEFAULT_INPUT_TIMEOUT = 300  # seconds
