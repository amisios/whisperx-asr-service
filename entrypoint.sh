#!/bin/bash
set -e

VERSION=$(python3 -c "from app.version import __version__; print(__version__)")
echo "WhisperX ASR Service v${VERSION}"

if [ "$SERVE_MODE" = "ray" ]; then
    echo "Starting in Ray Serve mode..."

    # Use a tmpfs-backed directory for Ray session data so it doesn't
    # trigger "filesystem 95% full" warnings against the host disk.
    export RAY_TMPDIR="/dev/shm/ray"
    mkdir -p "$RAY_TMPDIR"

    # Cap Ray's object store so it fits within the container's /dev/shm.
    # Default 4 GB leaves headroom in the 8g shm.
    export RAY_OBJECT_STORE_MEMORY="${RAY_OBJECT_STORE_MEMORY:-4000000000}"

    # Silence the FutureWarning about accelerator env var override
    export RAY_ACCEL_ENV_VAR_OVERRIDE_ON_ZERO=0

    # The Serve HTTP address is passed to serve.start() before serve.run().
    # RAY_SERVE_DEFAULT_HTTP_PORT is ignored by current Ray releases (checked
    # on 2.59), and the port then falls back to 8000. The dashboard is bound
    # to all container interfaces so that the port published by Docker
    # Compose (127.0.0.1 only) can reach it. It is protected by Ray token
    # authentication, which is enabled by default for local clusters (see
    # README "Ray Dashboard Access").
    exec python3 -c "
import ray
from ray import serve

ray.init(dashboard_host='0.0.0.0')
serve.start(http_options={'host': '0.0.0.0', 'port': 9000})

from app.serve_app import app
serve.run(app, blocking=True)
"
else
    echo "Starting in simple mode (uvicorn)..."
    exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9000
fi
