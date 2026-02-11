"""
Interceptors for builtin functions during module execution.
These allow us to capture input(), print(), and file operations.
"""
import builtins
import os
import tempfile
import codecs
import logging
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional, TextIO, TYPE_CHECKING
from threading import local

if TYPE_CHECKING:
    from recon.server.context import ExecutionContext

logger = logging.getLogger(__name__)

# Thread-local storage for execution context
_context_local = local()


def get_current_context() -> Optional['ExecutionContext']:
    """Get the current execution context for this thread"""
    return getattr(_context_local, 'context', None)


def set_current_context(ctx: Optional['ExecutionContext']):
    """Set the current execution context for this thread"""
    _context_local.context = ctx


# Store original builtins
_original_print = builtins.print
_original_input = builtins.input
_original_open = builtins.open


def intercepted_print(*args, **kwargs):
    """
    Intercepted print function that routes output through events.
    Falls back to original print if no context is active.
    """
    ctx = get_current_context()
    if ctx is not None:
        # Convert args to string message
        message = ' '.join(str(arg) for arg in args)
        end = kwargs.get('end', '\n')
        if end and end != '\n':
            message += end.rstrip('\n')
        # Route through events
        ctx.events.output(message)
    else:
        # No context, use original print
        _original_print(*args, **kwargs)


def intercepted_input(prompt: str = '') -> str:
    """
    Intercepted input function that requests input via RPC events.
    Falls back to original input if no context is active.
    """
    ctx = get_current_context()
    if ctx is not None:
        return ctx.request_input(prompt)
    else:
        return _original_input(prompt)


class InterceptedFile:
    """
    A file-like object that captures writes for sending to client.
    Used for intercepting file output from reporting modules.
    """
    
    def __init__(self, filepath: str, mode: str, ctx: 'ExecutionContext', 
                 encoding: str = 'utf-8', **kwargs):
        self.filepath = filepath
        self.mode = mode
        self.ctx = ctx
        self.encoding = encoding
        self._content = []
        self._binary = 'b' in mode
        self._closed = False
        
        # For read operations, we need the actual file
        if 'r' in mode:
            self._real_file = _original_open(filepath, mode, encoding=encoding if not self._binary else None, **kwargs)
        else:
            self._real_file = None
    
    def write(self, data):
        if self._real_file:
            return self._real_file.write(data)
        self._content.append(data)
        return len(data)
    
    def writelines(self, lines):
        for line in lines:
            self.write(line)
    
    def read(self, size=-1):
        if self._real_file:
            return self._real_file.read(size)
        raise IOError("File not opened for reading")
    
    def readline(self, size=-1):
        if self._real_file:
            return self._real_file.readline(size)
        raise IOError("File not opened for reading")
    
    def readlines(self, hint=-1):
        if self._real_file:
            return self._real_file.readlines(hint)
        raise IOError("File not opened for reading")
    
    def close(self):
        if self._closed:
            return
        self._closed = True
        
        if self._real_file:
            self._real_file.close()
        elif self._content and self.ctx:
            # Send content to client
            if self._binary:
                import base64
                content = base64.b64encode(b''.join(self._content)).decode('ascii')
                self.ctx.events.file_output(
                    filename=os.path.basename(self.filepath),
                    content=content,
                    encoding='base64',
                    binary=True
                )
            else:
                content = ''.join(self._content)
                self.ctx.events.file_output(
                    filename=os.path.basename(self.filepath),
                    content=content,
                    encoding=self.encoding,
                    binary=False
                )
    
    def flush(self):
        if self._real_file:
            self._real_file.flush()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
    
    # Properties expected by some code
    @property
    def name(self):
        return self.filepath
    
    @property
    def closed(self):
        return self._closed


def intercepted_open(filepath, mode='r', *args, **kwargs):
    """
    Intercepted open function that captures file writes.
    For reads, it checks if we have injected content.
    For writes, it captures output to send to client.
    """
    ctx = get_current_context()
    
    if ctx is None:
        # No context, use original open
        return _original_open(filepath, mode, *args, **kwargs)
    
    # Check if this is reading from injected content
    if 'r' in mode and isinstance(filepath, str) and filepath.startswith('__content__:'):
        content_id = filepath.split(':', 1)[1]
        content = ctx.get_content(content_id)
        if content is not None:
            import io
            if 'b' in mode:
                return io.BytesIO(content.encode('utf-8'))
            else:
                return io.StringIO(content)
    
    # For write operations to workspace paths, intercept
    if ('w' in mode or 'a' in mode) and isinstance(filepath, str):
        # Intercept writes that look like output files
        # (in workspace directory or explicitly marked)
        return InterceptedFile(filepath, mode, ctx, **kwargs)
    
    # For read operations, check if file exists on server first
    if 'r' in mode and isinstance(filepath, str):
        if not os.path.exists(filepath):
            # File doesn't exist on server - request from client
            logger.debug(f"File not found on server, requesting from client: {filepath}")
            content = ctx.request_file(filepath)
            if content is not None:
                import io
                logger.debug(f"Got file content from client: {len(content)} chars")
                if 'b' in mode:
                    return io.BytesIO(content.encode('utf-8'))
                return io.StringIO(content)
            # Client couldn't provide file either - raise original error
            raise FileNotFoundError(f"[Errno 2] No such file or directory: '{filepath}'")
    
    # Default: use original open
    return _original_open(filepath, mode, *args, **kwargs)


def intercepted_codecs_open(filepath, mode='r', encoding='utf-8', *args, **kwargs):
    """Intercepted codecs.open for encoding-aware file operations"""
    ctx = get_current_context()
    
    if ctx is None:
        return codecs.open(filepath, mode, encoding, *args, **kwargs)
    
    if ('w' in mode or 'a' in mode) and isinstance(filepath, str):
        return InterceptedFile(filepath, mode, ctx, encoding=encoding)
    
    return codecs.open(filepath, mode, encoding, *args, **kwargs)


@contextmanager
def install_interceptors():
    """
    Context manager to install interceptors for the duration of execution.
    """
    # Save originals (in case of nested contexts)
    saved_print = builtins.print
    saved_input = builtins.input
    saved_open = builtins.open
    saved_codecs_open = codecs.open
    
    try:
        # Install interceptors
        builtins.print = intercepted_print
        builtins.input = intercepted_input
        builtins.open = intercepted_open
        codecs.open = intercepted_codecs_open
        yield
    finally:
        # Restore originals
        builtins.print = saved_print
        builtins.input = saved_input
        builtins.open = saved_open
        codecs.open = saved_codecs_open


@contextmanager
def execution_context(ctx: 'ExecutionContext'):
    """
    Context manager to set up execution context for a thread.
    Installs interceptors and sets thread-local context.
    """
    old_context = get_current_context()
    set_current_context(ctx)
    try:
        with install_interceptors():
            yield ctx
    finally:
        set_current_context(old_context)
