from __future__ import annotations

import os

import uvicorn

from control.transports.tasks_grpc import serve as serve_grpc
from shared.config.environment import integer_parser, resolve_environment


def main() -> None:
    grpc_server = serve_grpc()
    try:
        host = os.getenv("CONTROL_HOST") or resolve_environment(
            "OMERTA_CONTROL_HTTP_HOST",
            aliases=("AION_CONTROL_HTTP_HOST",),
            # Container peers require the HTTP service on every container interface.
            default="0.0.0.0",  # nosec B104
        )
        port = resolve_environment(
            "OMERTA_CONTROL_HTTP_PORT",
            aliases=("AION_CONTROL_HTTP_PORT",),
            default="8000",
            parser=integer_parser(minimum=1, maximum=65535),
        )
        assert isinstance(host, str)
        assert isinstance(port, int)
        uvicorn.run(
            "control.app.main:app",
            host=host,
            port=port,
        )
    finally:
        grpc_server.stop(grace=5)


if __name__ == "__main__":
    main()
