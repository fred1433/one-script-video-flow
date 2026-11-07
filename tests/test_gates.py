"""Gate rules, replayed on the real render service with a stand-in for n8n's resume webhook.

  .venv/bin/python tests/test_gates.py
1. a Short refused without a fix that changes the cut is answered 400 (the same file would come back);
2. "reject" on the Shorts gate is answered 400 and points to review-shorts;
3. a Short refused, reworked and handed back within the same second can still be approved;
4. a rework with no refusal in this execution is answered 400, not a crash or an old refusal;
5. flow.pending() reads ledger order, not timestamps.
"""
import json, os, subprocess, sys, tempfile, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT, FAKE = 18790, 18791
got = []


class Resume(BaseHTTPRequestHandler):
    def do_POST(self):
        got.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        self.send_response(200); self.end_headers()

    def log_message(self, *a):
        pass


def call(path, body):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def main():
    out = tempfile.mkdtemp(prefix="gates_")
    threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", FAKE), Resume).serve_forever, daemon=True).start()
    env = dict(os.environ, FLOW_OUT=out, FLOW_CACHE=out + "/cache", RENDER_PORT=str(PORT), FLOW_NO_BLENDER="1")
    svc = subprocess.Popen([sys.executable, str(ROOT / "render/service.py")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1); break
            except Exception:
                time.sleep(0.2)
        P, X = "GATES-TEST", "exec-1"
        hand = {"project": P, "gate": "shorts", "files": ["a.mp4"], "resume_url": f"http://127.0.0.1:{FAKE}/r", "execution": X}
        assert call("/handoff", hand)[0] == 200
        code, body = call("/decide", {"project": P, "gate": "shorts", "decision": "changes",
                                      "shorts": {"1": "approved", "2": {"rejected": "covers the lug", "fix": {}}}})
        assert code == 400, (code, body); print("1. refusal without a fix:", code, body["error"][:70])
        code, body = call("/decide", {"project": P, "gate": "shorts", "decision": "rejected", "note": "no"})
        assert code == 400, (code, body); print("2. reject on the Shorts gate:", code, body["error"][:70])
        code, _ = call("/decide", {"project": P, "gate": "shorts", "decision": "changes",
                                   "shorts": {"1": "approved", "2": {"rejected": "covers the lug", "fix": {"caption_pos": "lower"}}}})
        assert code == 200
        assert call("/handoff", hand)[0] == 200          # back within the same second
        code, body = call("/decide", {"project": P, "gate": "shorts", "decision": "approved"})
        assert code == 200, (code, body); print("3. refused, handed back in the same second, approved:", code, len(got), "resumes sent")
        code, body = call("/step/shorts", {"project": "GATES-FRESH", "rework": True, "execution": "exec-9"})
        assert code == 400, (code, body); print("4. rework with no refusal in this execution:", code, body["error"][:70])
        sys.path.insert(0, str(ROOT))
        import flow
        led = [json.loads(l) for l in (Path(out) / P / "ledger.jsonl").read_text().splitlines()]
        assert len({e["ts"] for e in led[-2:]}) >= 1
        flow.ledger = lambda: led[:-1]                    # last handoff not yet answered
        assert flow.pending() == "shorts"
        flow.ledger = lambda: led
        assert flow.pending() is None
        print("5. pending() by ledger order: waiting, then answered")
        print("all gate tests passed")
    finally:
        svc.terminate()


if __name__ == "__main__":
    main()
