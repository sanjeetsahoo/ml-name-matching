"""HTTP API for partial-accept triage."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .engine import DecisionEngine
from .models import PartialAcceptCase


class _BaseJsonHandler(BaseHTTPRequestHandler):
    decision_engine: DecisionEngine

    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Any:
        content_length = self.headers.get("Content-Length")
        if content_length is None:
            raise ValueError("missing Content-Length header")

        try:
            size = int(content_length)
        except ValueError as exc:
            raise ValueError("invalid Content-Length header") from exc

        if size <= 0:
            raise ValueError("request body is empty")

        raw = self.rfile.read(size)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("request body must be valid JSON") from exc


def build_handler(decision_engine: DecisionEngine) -> type[_BaseJsonHandler]:
    """Build a request handler bound to one engine instance."""

    class PartialAcceptHandler(_BaseJsonHandler):
        decision_engine = decision_engine

        def do_GET(self) -> None:  # noqa: N802 (http method naming)
            path = urlparse(self.path).path
            if path == "/health":
                self._send_json(HTTPStatus.OK, {"status": "ok"})
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "route not found"})

        def do_POST(self) -> None:  # noqa: N802 (http method naming)
            path = urlparse(self.path).path
            try:
                payload = self._read_json_body()
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return

            if path == "/triage":
                self._handle_single(payload)
                return

            if path == "/triage/batch":
                self._handle_batch(payload)
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"error": "route not found"})

        def _handle_single(self, payload: Any) -> None:
            try:
                case = PartialAcceptCase.from_payload(payload)
            except ValueError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return

            result = self.decision_engine.triage_case(case)
            self._send_json(HTTPStatus.OK, result.to_dict())

        def _handle_batch(self, payload: Any) -> None:
            items: list[Any]
            if isinstance(payload, list):
                items = payload
            elif isinstance(payload, dict) and isinstance(payload.get("cases"), list):
                items = payload["cases"]
            else:
                self._send_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "batch payload must be a list or {'cases': [...]}"},
                )
                return

            cases: list[PartialAcceptCase] = []
            for index, item in enumerate(items):
                try:
                    cases.append(PartialAcceptCase.from_payload(item))
                except ValueError as exc:
                    self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        {"error": f"invalid case at index {index}: {exc}"},
                    )
                    return

            results = self.decision_engine.triage_batch(cases)
            decision_counts = {
                "AUTO_ACCEPT": 0,
                "AUTO_REJECT": 0,
                "SEND_TO_OPS": 0,
            }
            for result in results:
                decision_counts[result.decision.value] += 1

            self._send_json(
                HTTPStatus.OK,
                {
                    "total_cases": len(results),
                    "decision_counts": decision_counts,
                    "results": [result.to_dict() for result in results],
                },
            )

    return PartialAcceptHandler


def create_server(host: str, port: int, decision_engine: DecisionEngine | None = None) -> ThreadingHTTPServer:
    """Create an HTTP server instance."""
    engine = decision_engine or DecisionEngine()
    handler_cls = build_handler(engine)
    return ThreadingHTTPServer((host, port), handler_cls)
