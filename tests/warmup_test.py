"""Verifies OllamaClient.warm_up() -- the fix for enemy AI appearing "stuck"
at "(waiting for first token...)" in debug mode. Root cause: large models
(e.g. gemma3:27b) can take a long time to load into memory, and none of
that load time produces any streamed output, so if it lands on an in-battle
turn it can outlast that turn's timeout. warm_up() force-loads the model
once at startup (see main.py) with its own generous timeout, so in-battle
calls only ever hit the fast already-warm path.

Checks:
  - warm_up() POSTs to /api/generate (not /api/chat) with no "prompt" field
    (that's what makes it just a load, not a generation) and the configured
    model/keep_alive, and returns how long the load took.
  - A connection error during warm-up raises OllamaError like every other
    client call does, rather than a raw requests exception.

Run directly: python3 tests/warmup_test.py
"""
import http.server
import json
import os
import socketserver
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.ollama_client import OllamaClient, OllamaError


class _WarmupFakeOllama(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *_args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(length))
        assert self.path == "/api/generate", f"warm_up must hit /api/generate, got {self.path}"
        assert "prompt" not in req, "warm-up request must not include a prompt (that would generate tokens)"
        assert req["model"] == "fake-model", req
        assert req["keep_alive"] == "30m", req
        time.sleep(0.05)  # simulate nonzero load time
        body = json.dumps({"model": req["model"], "done": True, "response": ""}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_warm_up_loads_without_generating():
    server = socketserver.TCPServer(("127.0.0.1", 0), _WarmupFakeOllama)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = OllamaClient(host=f"http://127.0.0.1:{port}", model="fake-model", timeout=5, keep_alive="30m")
        elapsed = client.warm_up()
        assert elapsed >= 0.05, f"expected warm_up to take at least the simulated load time, got {elapsed}"
        print(f"test_warm_up_loads_without_generating: PASS (elapsed={elapsed:.3f}s)")
    finally:
        server.shutdown()


def test_warm_up_raises_ollama_error_on_connection_failure():
    client = OllamaClient(host="http://localhost:1", model="fake-model", timeout=0.5)
    try:
        client.warm_up()
        raise AssertionError("expected OllamaError")
    except OllamaError as exc:
        assert "Could not reach Ollama" in str(exc), exc
        print(f"test_warm_up_raises_ollama_error_on_connection_failure: PASS ({exc})")


def main():
    test_warm_up_loads_without_generating()
    test_warm_up_raises_ollama_error_on_connection_failure()
    print("\nALL WARM-UP TESTS PASSED")


if __name__ == "__main__":
    main()
