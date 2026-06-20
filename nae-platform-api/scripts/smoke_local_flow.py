from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def _read_payload(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _request_json(method: str, url: str, token: str | None = None, payload: dict | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, headers=headers, method=method)

    with urlopen(request, timeout=30) as response:
        raw = response.read().decode("utf-8")
        content_type = response.headers.get("Content-Type", "")
        return response.status, content_type, raw


def _print_step(title: str, status: int, body: str) -> None:
    print(f"\n== {title} ==")
    print(f"HTTP {status}")
    print(body.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test local NAE API flow")
    parser.add_argument("--base-url", default=os.getenv("NAE_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--payload", default=str(ROOT / "scripts" / "sample_payload.json"))
    parser.add_argument("--run-pipelines", action="store_true", help="Run staging, operational and analytics after raw insert")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--keep-sample-id", action="store_true", help="Reuse id_respuesta_origen from the sample payload")
    args = parser.parse_args()

    token = os.getenv("API_TOKEN")
    if not token:
        print("Missing API_TOKEN in environment or .env", file=sys.stderr)
        return 2

    payload_file = Path(args.payload)
    payload = _read_payload(payload_file)

    if not args.keep_sample_id:
        payload["id_respuesta_origen"] = f"smoke-{uuid4()}"

    try:
        status, _, raw = _request_json(
            "POST",
            f"{args.base_url}/api/v1/respuestas",
            token=token,
            payload=payload,
        )
        _print_step("POST /api/v1/respuestas", status, raw)
        if status >= 300:
            return 1

        response_data = json.loads(raw)
        raw_id = response_data.get("raw_id")

        if args.run_pipelines:
            for endpoint in (
                "/api/v1/pipelines/staging/raw-to-staging",
                "/api/v1/pipelines/operational/staging-to-operational",
                "/api/v1/pipelines/analytics/operational-to-analytics",
            ):
                status, _, body = _request_json(
                    "POST",
                    f"{args.base_url}{endpoint}?limit={args.limit}",
                    token=token,
                )
                _print_step(f"POST {endpoint}", status, body)
                if status >= 300:
                    return 1

        status, _, raw = _request_json("GET", f"{args.base_url}/api/v1/resumen?limit=3")
        _print_step("GET /api/v1/resumen?limit=3", status, raw)
        if status >= 300:
            return 1

        if raw_id is not None:
            print(f"\nInserted raw_id: {raw_id}")
            print(f"Smoketest completed at {datetime.now().isoformat(timespec='seconds')}")
        return 0
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        _print_step("HTTP error", exc.code, body)
        return 1
    except URLError as exc:
        print(f"Connection error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
