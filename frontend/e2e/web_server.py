"""Serve the static Next.js export with extensionless route support."""

from __future__ import annotations

import argparse
from functools import partial
from http.client import HTTPConnection
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


class ExportHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, api_url: str, **kwargs) -> None:
        self.api = urlsplit(api_url)
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args: object) -> None:
        return

    def copyfile(self, source, outputfile) -> None:
        try:
            super().copyfile(source, outputfile)
        except BrokenPipeError:
            pass

    def proxy_api(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else None
        headers = {
            name: value
            for name, value in self.headers.items()
            if name.lower() not in {"connection", "content-length", "host"}
        }
        connection = HTTPConnection(self.api.hostname, self.api.port, timeout=60)
        try:
            connection.request(self.command, self.path, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read()
            self.send_response(response.status)
            for name, value in response.getheaders():
                if name.lower() not in {"connection", "content-length", "transfer-encoding"}:
                    self.send_header(name, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            try:
                self.wfile.write(payload)
            except BrokenPipeError:
                pass
        finally:
            connection.close()

    def do_GET(self) -> None:
        if urlsplit(self.path).path.startswith("/api/"):
            self.proxy_api()
            return
        parsed = urlsplit(self.path)
        route = unquote(parsed.path)
        if route != "/" and not Path(route).suffix:
            candidate = Path(self.directory, f"{route.lstrip('/')}.html")
            if candidate.is_file():
                self.path = f"{route}.html" + (f"?{parsed.query}" if parsed.query else "")
        super().do_GET()

    def do_POST(self) -> None:
        if urlsplit(self.path).path.startswith("/api/"):
            self.proxy_api()
            return
        self.send_error(404)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default=".next-e2e")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3100)
    parser.add_argument("--api-url", default="http://127.0.0.1:8010")
    args = parser.parse_args()
    handler = partial(ExportHandler, directory=args.directory, api_url=args.api_url)
    ThreadingHTTPServer((args.host, args.port), handler).serve_forever()


if __name__ == "__main__":
    main()
