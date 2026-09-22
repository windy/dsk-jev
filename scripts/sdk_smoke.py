"""Run after go build -o bin/dsk-jev ./cmd/server; pip install typesafe-sdk==0.7.1.
Uses a local fake upstream, never a real API key or paid request.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typesafe_sdk import TypeSafeClient

ROOT = Path(__file__).resolve().parents[1]

class Upstream(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert body["thinking"] == {"type": "disabled"}
        questions = body["tools"][0]["function"]["parameters"]["properties"]["answers"]["properties"]
        answers = {}
        for key, q in questions.items():
            answers[key] = 0.25 if q["type"] == "number" else {k: (1.0 if i == 0 else 0.0) for i, k in enumerate(q["properties"])}
        payload = json.dumps({"choices": [{"finish_reason": "tool_calls", "message": {"tool_calls": [{"type":"function", "function":{"name":"submit_decisions", "arguments":json.dumps({"answers": answers})}}]}}], "usage": {"prompt_tokens": 100, "completion_tokens": 20}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)
    def log_message(self, *args):
        pass

upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
threading.Thread(target=upstream.serve_forever, daemon=True).start()
with socket.socket() as reservation:
    reservation.bind(("127.0.0.1", 0))
    port = reservation.getsockname()[1]
env = dict(os.environ, PROXY_API_KEY="smoke-local", DEEPSEEK_API_KEY="smoke-upstream", DEEPSEEK_BASE_URL=f"http://127.0.0.1:{upstream.server_port}", LISTEN_ADDR=f"127.0.0.1:{port}", DEEPSEEK_MODEL="deepseek-flash")
process = subprocess.Popen([os.environ.get('DSK_JEV_BINARY', str(ROOT / 'bin/dsk-jev'))], env=env)
try:
    for _ in range(100):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    else:
        raise RuntimeError("proxy failed to start")
    with TypeSafeClient(api_key="smoke-local", base_url=f"http://127.0.0.1:{port}", model="jev-latest") as client:
        request = json.loads((ROOT / "examples/ticket.json").read_text())
        result = client.system_one(state=request["state"], questions=request["questions"])
        assert result.choices["department"].choice == "billing"
        assert result.nouls["explicit_refund"].noul == 0.25
        assert result.scores["urgency"].score == 0.0
        assert result.usage.input_tokens == 100
        models = client.models.list()
        assert any(m.name == "jev-latest" for m in models.models)
        print("Official TypeSafe SDK: Choice, Score, Noul, usage and models OK")
finally:
    process.terminate()
    process.wait(timeout=10)
    upstream.shutdown()
    upstream.server_close()
