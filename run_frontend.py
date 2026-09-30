"""
Frontend Dev Server Runner.
Launches a lightweight local static web server serving the frontend directory on port 3000.
"""
import http.server
import socketserver
import os
import sys
import webbrowser
from pathlib import Path

PORT = 3000
FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def log_message(self, format, *args):
        # Clean console output
        sys.stderr.write(f"[Frontend Server] {self.address_string()} - {format % args}\n")


def run():
    print("=" * 60)
    print("AI Response Validation System — Frontend Server")
    print("=" * 60)
    print(f"Serving frontend from: {FRONTEND_DIR}")
    print(f"Local URL: http://127.0.0.1:{PORT}")
    print("Connecting to backend at: http://127.0.0.1:8000")
    print("=" * 60)

    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"Server started on http://127.0.0.1:{PORT} (Press Ctrl+C to stop)")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nShutting down frontend server.")
    except OSError as e:
        if "address already in use" in str(e).lower() or e.errno == 98 or e.errno == 10048:
            print(f"Port {PORT} is already in use. Try opening http://127.0.0.1:{PORT} in your browser.")
        else:
            raise e

if __name__ == "__main__":
    run()
