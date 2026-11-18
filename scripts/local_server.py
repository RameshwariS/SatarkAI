"""Run the whole app on your laptop: serves frontend/ and routes /api/* to the
Lambda handler.

  MOCK_AWS=1 python scripts/local_server.py      # no AWS needed (rules only)
  python scripts/local_server.py                 # uses your AWS credentials
Open http://localhost:8000
"""
import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend", "src"))
import app  # noqa: E402


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=os.path.join(ROOT, "frontend"), **kw)

    def _api(self, method):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode() if length else ""
        res = app.handler({"requestContext": {"http": {"method": method}}, "rawPath": self.path.split("?")[0], "body": body})
        data = res["body"].encode()
        self.send_response(res["statusCode"])
        for k, v in res["headers"].items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self._api("GET")
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            return self._api("POST")
        self.send_error(404)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Nivesh Kavach running at http://localhost:{port}  (mock AWS: {os.environ.get('MOCK_AWS') == '1'})")
    ThreadingHTTPServer(("", port), Handler).serve_forever()
