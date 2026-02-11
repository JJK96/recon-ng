"""
Pydantic schemas for RPC messages
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
import uuid


def generate_uuid() -> str:
    return str(uuid.uuid4())


def generate_timestamp() -> str:
    return datetime.utcnow().isoformat() + 'Z'


# ============================================================
# Base Messages
# ============================================================

class RPCRequest(BaseModel):
    """Request from client to server"""
    id: str = Field(default_factory=generate_uuid)
    client_id: str
    command: str
    workspace: str
    params: Dict[str, Any] = Field(default_factory=dict)
    global_options: Dict[str, Any] = Field(default_factory=dict)  # Client-side overrides
    timestamp: str = Field(default_factory=generate_timestamp)


class RPCResponse(BaseModel):
    """Response from server to client"""
    id: str  # Matches request ID
    status: str  # 'success' or 'error'
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None  # {code, message}
    timestamp: str = Field(default_factory=generate_timestamp)
    
    @classmethod
    def make_success(cls, request_id: str, result: Dict[str, Any] = None) -> 'RPCResponse':
        return cls(id=request_id, status='success', result=result or {})
    
    @classmethod
    def make_error(cls, request_id: str, code: str, message: str) -> 'RPCResponse':
        return cls(id=request_id, status='error', error={'code': code, 'message': message})


class RPCEvent(BaseModel):
    """Event pushed from server to client during execution"""
    id: str  # Request ID being processed
    type: str  # Event type (see EventType)
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=generate_timestamp)


# ============================================================
# Command Parameter Schemas
# ============================================================

class WorkspaceCreateParams(BaseModel):
    name: str


class WorkspaceDeleteParams(BaseModel):
    name: str


class ModulesListParams(BaseModel):
    category: Optional[str] = None


class ModulesSearchParams(BaseModel):
    term: str


class ModulesLoadParams(BaseModel):
    path: str


class ModulesInfoParams(BaseModel):
    path: str


class ModulesRunParams(BaseModel):
    path: str
    options: Dict[str, Any] = Field(default_factory=dict)
    file_content: Optional[str] = None  # For import modules
    file_name: Optional[str] = None  # Original filename


class ModulesReloadParams(BaseModel):
    path: Optional[str] = None  # None = reload all


class DbSchemaParams(BaseModel):
    table: str


class DbQueryParams(BaseModel):
    sql: str


class DbInsertParams(BaseModel):
    table: str
    data: Dict[str, Any]


class DbDeleteParams(BaseModel):
    table: str
    rowids: List[int]


class DbExportParams(BaseModel):
    table: str
    format: str = 'list'
    column: Optional[str] = None  # For list format
    unique: bool = True
    include_nulls: bool = False


class KeysGetParams(BaseModel):
    name: str


class KeysAddParams(BaseModel):
    name: str
    value: str


class KeysDeleteParams(BaseModel):
    name: str


class MarketplaceSearchParams(BaseModel):
    term: str


class MarketplaceInfoParams(BaseModel):
    path: str


class MarketplaceInstallParams(BaseModel):
    path: str


class MarketplaceRemoveParams(BaseModel):
    path: str


class SnapshotsTakeParams(BaseModel):
    name: Optional[str] = None


class SnapshotsLoadParams(BaseModel):
    name: str


class SnapshotsDeleteParams(BaseModel):
    name: str


class InputResponseParams(BaseModel):
    input_id: str
    value: str


# ============================================================
# Response Result Schemas
# ============================================================

class WorkspaceInfo(BaseModel):
    name: str
    tables: List[str] = Field(default_factory=list)
    record_count: int = 0


class ModuleInfo(BaseModel):
    path: str
    name: str
    author: str
    version: str
    description: str
    options: List[Dict[str, Any]] = Field(default_factory=list)
    required_keys: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    files: List[str] = Field(default_factory=list)
    comments: List[str] = Field(default_factory=list)
    query: Optional[str] = None


class ModuleListItem(BaseModel):
    path: str
    name: str
    status: str = 'installed'  # installed, not installed, disabled, outdated


class MarketplaceModuleInfo(BaseModel):
    path: str
    name: str
    author: str
    version: str
    description: str
    status: str
    required_keys: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)


class TableColumn(BaseModel):
    name: str
    type: str


class DashboardActivity(BaseModel):
    module: str
    runs: int


class DashboardSummary(BaseModel):
    table: str
    count: int


class GlobalOptions(BaseModel):
    nameserver: str = '8.8.8.8'
    proxy: Optional[str] = None
    threads: int = 10
    timeout: int = 10
    user_agent: str = 'Recon-ng/v5'
    verbosity: int = 1


# ============================================================
# Event Data Schemas
# ============================================================

class OutputEventData(BaseModel):
    message: str
    level: str = 'info'


class TableEventData(BaseModel):
    rows: List[List[Any]]
    header: List[str] = Field(default_factory=list)
    title: Optional[str] = None


class HeadingEventData(BaseModel):
    text: str
    level: int = 0


class ProgressEventData(BaseModel):
    current: int
    total: int
    message: Optional[str] = None


class InputRequiredEventData(BaseModel):
    input_id: str
    prompt: str = ''


class FileOutputEventData(BaseModel):
    filename: str
    content: str
    encoding: str = 'utf-8'
    binary: bool = False


class ExceptionEventData(BaseModel):
    type: str
    message: str
    traceback: Optional[str] = None
