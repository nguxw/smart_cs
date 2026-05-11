from __future__ import annotations

import argparse
import json
import sys
from urllib.error import URLError
from urllib.request import urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check SmartCS /health output.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/health")
    parser.add_argument(
        "--expect",
        action="append",
        default=[],
        help="Expected key=value pair. Can be repeated.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        with urlopen(args.url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        print(f"health check failed: {exc}", file=sys.stderr)
        return 1

    failures: list[str] = []
    for item in args.expect:
        if "=" not in item:
            failures.append(f"invalid expectation: {item}")
            continue
        key, expected = item.split("=", 1)
        actual = str(payload.get(key))
        if actual != expected:
            failures.append(f"{key}: expected {expected}, got {actual}")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if failures:
        print("health expectation failures:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
