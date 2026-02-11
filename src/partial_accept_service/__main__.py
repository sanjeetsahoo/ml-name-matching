"""Entrypoint to run the partial accept triage API service."""

from __future__ import annotations

import os

from .api import create_server
from .config import TriageConfig
from .engine import DecisionEngine


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def main() -> None:
    host = os.getenv("SERVICE_HOST", "0.0.0.0")
    port = _int_env("SERVICE_PORT", 8080)

    config = TriageConfig.from_env()
    engine = DecisionEngine(config=config)
    server = create_server(host=host, port=port, decision_engine=engine)
    print(
        "Starting partial-accept triage service",
        f"on http://{host}:{port}",
        f"(accept>={config.auto_accept_threshold}, reject<={config.auto_reject_threshold})",
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
