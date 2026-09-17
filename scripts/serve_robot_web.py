#!/usr/bin/env python3
"""Serve the iPhone robot's static web UI.

For local desktop smoke tests HTTP is enough. iPhone Safari requires HTTPS
before it will grant microphone access; use a trusted reverse proxy such as
Caddy in front of this server for exhibition use.
"""
from __future__ import annotations

import argparse
import http.server
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1] / "web"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    handler = lambda *handler_args: http.server.SimpleHTTPRequestHandler(
        *handler_args, directory=str(ROOT)
    )
    server = http.server.ThreadingHTTPServer((args.host, args.port), handler)
    print(f"robot web: http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
