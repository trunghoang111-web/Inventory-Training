"""HTTP Server serving Static Frontend Assets and REST API."""
import os
import json
import mimetypes
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from backend.config import BASE_DIR, ASSETS_DIR, SLIDES_DIR, SERVER_HOST, SERVER_PORT
from backend.api import handle_api_request
from backend.simple_api import handle_simple_api_request

FRONTEND_DIR = BASE_DIR / "frontend"

class ASVHttpHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Concise logging
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        self._route_request("GET")

    def do_POST(self):
        self._route_request("POST")

    def do_PUT(self):
        self._route_request("PUT")

    def do_DELETE(self):
        self._route_request("DELETE")

    def _route_request(self, method: str):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = dict(urllib.parse.parse_qsl(parsed_url.query))

        # 1. API Route
        if path.startswith("/api/simple/"):
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body_bytes = self.rfile.read(content_length) if content_length > 0 else b""
                headers_dict = {k: v for k, v in self.headers.items()}
                status_code, resp_headers, resp_bytes = handle_simple_api_request(
                    method, path, headers_dict, body_bytes, query_params
                )
                self.send_response(status_code)
                self.send_header("Access-Control-Allow-Origin", "*")
                for hk, hv in resp_headers.items():
                    self.send_header(hk, hv)
                self.send_header("Content-Length", str(len(resp_bytes)))
                self.end_headers()
                self.wfile.write(resp_bytes)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                err_body = json.dumps({"error": f"Lỗi máy chủ: {str(exc)}"}, ensure_ascii=False).encode("utf-8")
                self.send_response(500)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(err_body)))
                self.end_headers()
                self.wfile.write(err_body)
            return

        if path.startswith("/api/"):
            try:
                content_length = int(self.headers.get("Content-Length", 0))
                body_bytes = self.rfile.read(content_length) if content_length > 0 else b""
                
                headers_dict = {k: v for k, v in self.headers.items()}
                status_code, resp_headers, resp_bytes = handle_api_request(
                    method, path, headers_dict, body_bytes, query_params
                )

                self.send_response(status_code)
                self.send_header("Access-Control-Allow-Origin", "*")
                for hk, hv in resp_headers.items():
                    self.send_header(hk, hv)
                self.send_header("Content-Length", str(len(resp_bytes)))
                self.end_headers()
                self.wfile.write(resp_bytes)
            except Exception as exc:
                import traceback
                traceback.print_exc()
                err_body = json.dumps({"error": f"Lỗi máy chủ: {str(exc)}"}, ensure_ascii=False).encode("utf-8")
                self.send_response(500)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(err_body)))
                self.end_headers()
                self.wfile.write(err_body)
            return

        # 2. Slides Route (/slides/...)
        if path.startswith("/slides/"):
            relative_path = path[len("/slides/"):]
            file_path = (SLIDES_DIR / relative_path).resolve()
            if not str(file_path).startswith(str(SLIDES_DIR.resolve())) or not file_path.is_file():
                self.send_error(404, "Slide Image Not Found")
                return
            self._serve_file(file_path)
            return

        # 3. Assets Route (/assets/...)
        if path.startswith("/assets/"):
            relative_path = path[len("/assets/"):]
            file_path = (ASSETS_DIR / relative_path).resolve()
            if not str(file_path).startswith(str(ASSETS_DIR.resolve())) or not file_path.is_file():
                self.send_error(404, "Asset Not Found")
                return
            self._serve_file(file_path)
            return

        # 3. Frontend Static Files Route
        clean_path = path.lstrip("/")
        if clean_path.startswith("frontend/"):
            clean_path = clean_path[len("frontend/"):]
        if not clean_path:
            clean_path = "index.html"
        file_path = (FRONTEND_DIR / clean_path).resolve()

        if not str(file_path).startswith(str(FRONTEND_DIR.resolve())) or not file_path.is_file():
            # SPA Fallback to index.html
            file_path = FRONTEND_DIR / "index.html"

        if file_path.is_file():
            self._serve_file(file_path)
        else:
            self.send_error(404, "Not Found")

    def _serve_file(self, file_path: Path):
        content_type, _ = mimetypes.guess_type(str(file_path))
        if not content_type:
            if file_path.suffix == ".js":
                content_type = "application/javascript"
            elif file_path.suffix == ".css":
                content_type = "text/css"
            elif file_path.suffix == ".html":
                content_type = "text/html"
            else:
                content_type = "application/octet-stream"

        try:
            content_bytes = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8" if "text" in content_type or "javascript" in content_type else content_type)
            self.send_header("Content-Length", str(len(content_bytes)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content_bytes)
        except Exception as e:
            self.send_error(500, f"Internal Error: {str(e)}")

def run_server(host=SERVER_HOST, port=SERVER_PORT):
    server_address = (host, port)
    httpd = HTTPServer(server_address, ASVHttpHandler)
    print(f"ASV Inventory Training Server running at http://{host}:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
