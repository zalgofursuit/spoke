"""Local GUI server. Binds to 127.0.0.1 only, so it's just for you."""
import json, mimetypes, threading, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from . import __version__, core

HERE = Path(__file__).parent
MIME = {".js": "application/javascript", ".css": "text/css"}  # Windows registries sometimes get these wrong


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, data, ctype="application/json"):
        if not isinstance(data, bytes):
            data = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _file(self, base, rel):
        base = base.resolve()
        p = (base / rel).resolve()
        if p != base and base not in p.parents:
            return self._send(403, b"Forbidden", "text/plain")
        if p.is_dir():
            p = p / "index.html"
        if not p.is_file():
            return self._send(404, b"Not found", "text/plain")
        ct = MIME.get(p.suffix.lower()) or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        if ct.startswith("text/") or ct.endswith(("javascript", "xml")):
            ct += "; charset=utf-8"
        self._send(200, p.read_bytes(), ct)

    def _body(self):
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def do_GET(self):
        path = unquote(self.path.split("?")[0])
        if path == "/":
            return self._file(HERE, "admin.html")
        if path in ("/admin.css", "/admin.js"):
            return self._file(HERE, path[1:])
        if path == "/api/posts":
            q = parse_qs(urlsplit(self.path).query)
            num = lambda k, d: int(q[k][0]) if k in q and q[k][0].isdigit() else d
            return self._send(200, core.page_posts(num("page", 1), min(num("per", 15), 100) or 15))
        if path == "/api/config":
            return self._send(200, {"config": core.load_config(), "themes": core.list_themes(), "version": __version__})
        if path.startswith("/media/"):
            return self._file(core.MEDIA, path[7:])
        if path.startswith("/thumbs/"):
            return self._file(core.THUMBS, path[8:])
        if path.startswith("/site/"):
            return self._file(core.SITE, path[6:])
        self._send(404, b"Not found", "text/plain")

    def _write(self, method):
        path = unquote(self.path.split("?")[0])
        try:
            if path == "/api/upload" and method == "POST":
                name = core.save_upload(unquote(self.headers.get("X-Filename", "image.jpg")), self._body())
                return self._send(200, {"file": name})
            if path == "/api/build" and method == "POST":
                return self._send(200, {"posts": core.build()})
            if path == "/api/config" and method == "PUT":
                core.save_config(json.loads(self._body()))
                core.build()
                return self._send(200, {"ok": True})
            if path == "/api/posts" and method == "POST":
                post = core.save_post(json.loads(self._body()))
            elif path.startswith("/api/posts/") and method == "PUT":
                post = core.save_post(json.loads(self._body()), path.split("/")[-1])
            elif path.startswith("/api/posts/") and method == "DELETE":
                core.delete_post(path.split("/")[-1])
                post = {"deleted": True}
            else:
                return self._send(404, b"Not found", "text/plain")
            core.build()
            self._send(200, post)
        except Exception as e:  # report problems to the GUI instead of crashing
            self._send(400, str(e).encode(), "text/plain")

    do_POST = lambda self: self._write("POST")
    do_PUT = lambda self: self._write("PUT")
    do_DELETE = lambda self: self._write("DELETE")


def main(port=4747):
    core.ensure()
    if not core.load_posts():
        core.save_post({"type": "text", "title": "Hello, world",
                        "body": "Your **Spoke** blog is up and running. Edit or delete this post, then ride on.",
                        "tags": ["welcome"]})
    core.build()
    while True:
        try:
            srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            port += 1
    url = f"http://127.0.0.1:{port}/"
    print(f"Spoke is running at {url}\nPress Ctrl+C to stop.")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nParked the bike. Bye!")
