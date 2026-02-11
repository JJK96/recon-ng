# =============================================================================
# Base stage - common dependencies and build tools
# =============================================================================
FROM python:3.11-alpine AS base

RUN apk add --no-cache --virtual .build-deps \
        gcc \
        libc-dev \
        libxslt-dev \
        libffi-dev && \
    apk add --no-cache libxslt

WORKDIR /recon-ng

# Copy package configuration
COPY pyproject.toml README.md ./
COPY recon/ ./recon/

# Set Python path
ENV PYTHONPATH=/recon-ng


# =============================================================================
# RPC Server image
# =============================================================================
FROM base AS server

# Install with server dependencies
RUN pip install --no-cache-dir ".[server]" && \
    apk del .build-deps

CMD ["python3", "-m", "recon.server.main"]


# =============================================================================
# Web Server image
# =============================================================================
FROM base AS web

# Install with web dependencies
RUN pip install --no-cache-dir ".[web]" && \
    apk del .build-deps

EXPOSE 5000

CMD ["uvicorn", "recon.core.web:asgi_app", "--host", "0.0.0.0", "--port", "5000"]
