"""Render service: the only place where media work happens. n8n calls it over HTTP.

Binds 127.0.0.1 only. Steps: voice (Kokoro, local), storyboard, look frames and animation
(Blender, local), master and Shorts (Pillow + ffmpeg), package. Every call is written to the
production ledger (out/<project>/ledger.jsonl) with the planned role and the real actor.
"""
import json
import os
import sys
import threading
import time
import traceback
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(__file__))
import steps  # noqa: E402

ROLES = {
    "script": "Producer",
    "voice": "Voice-over (local model)",
    "storyboard": "Storyboard & Camera Director",
    "look": "AI Image Artist",
    "animate": "AI Video Animator",
    "master": "AI Video Animator",
    "shorts": "Storyboard & Camera Director",
    "package": "Producer",
}
LOCK = threading.Lock()
DECISIONS = ("approved", "rejected", "changes")


def post_json(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status


def run_step(name, p):
    run = steps.Run(p["project"])
    q = p.get("quality", "final")
    t = time.time()
    with LOCK:
        if name == "voice":
            res = steps.step_voice(run, steps.ROOT / p["script"])
        elif name == "storyboard":
            res = steps.step_storyboard(run, steps.ROOT / p["storyboard"])
        elif name == "look":
            res = steps.step_look(run)
        elif name == "animate":
            res = steps.step_animate(run, q)
        elif name == "master":
            res = steps.step_master(run, q)
        elif name == "shorts":
            fixes_path = run.dir / "shorts_fixes.json"
            fixes = json.loads(fixes_path.read_text()) if fixes_path.exists() else {}
            only = p.get("only")
            if p.get("rework"):
                led = run.ledger()
                review = [e for e in led if e.get("gate") == "shorts" and e["event"] == "changes"
                          and e.get("execution") == p.get("execution")]
                if not review:
                    raise ValueError("no refused Short in this execution: refuse with ./flow.py review-shorts")
                only = []
                for idx, verdict in (review[-1].get("shorts") or {}).items():
                    if isinstance(verdict, dict):
                        only.append(int(idx))
                        fixes.setdefault(idx, {}).update(verdict.get("fix") or {})
                fixes_path.write_text(json.dumps(fixes, indent=2))
            res = steps.step_shorts(run, only, fixes, q)
        elif name == "package":
            # this execution only, refusals included
            approvals = [e for e in run.ledger() if e.get("event") in DECISIONS and e.get("execution") == p.get("execution")]
            res = steps.step_package(run, approvals)
        else:
            raise ValueError(f"unknown step {name}")
    res["seconds"] = round(time.time() - t, 1)
    run.log({"event": "delivered", "stage": name, "role_planned": ROLES[name], "actor": "render service",
             "files": res.get("files", []), "detail": {k: v for k, v in res.items() if k != "files"},
             "execution": p.get("execution")})
    return res


class H(BaseHTTPRequestHandler):
    def _send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/health":
            return self._send(200, {"ok": True})
        if u.path == "/ledger":
            project = parse_qs(u.query).get("project", ["DEMO-001"])[0]
            run = steps.Run(project)
            return self._send(200, {"ledger": run.ledger(), "assets": run.state["assets"]})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        p = json.loads(self.rfile.read(n) or b"{}")
        try:
            if u.path == "/run/start":
                run = steps.Run(p["project"])
                sc = steps.parse_script(steps.ROOT / p["script"])
                ev = run.log({"event": "approved", "stage": "script", "gate": "script", "role_planned": ROLES["script"],
                              "actor": p.get("approved_by", "builder (for this demo)"),
                              "files": [p["script"]], "detail": {"script_sha1": sc["sha1"], "lines": len(sc["lines"])},
                              "execution": p.get("execution")})
                return self._send(200, ev)
            if u.path.startswith("/step/"):
                name = u.path.split("/")[2]
                if p.get("callback"):
                    def bg():
                        try:
                            res = run_step(name, p)
                        except Exception as e:  # report the failure to the waiting workflow
                            res = {"error": str(e), "trace": traceback.format_exc()[-2000:]}
                        # n8n may not have reached its Wait node yet when a cached step returns at once
                        for _ in range(300):
                            try:
                                post_json(p["callback"], res)
                                break
                            except Exception:
                                time.sleep(2)
                    threading.Thread(target=bg, daemon=True).start()
                    return self._send(202, {"accepted": name})
                return self._send(200, run_step(name, p))
            if u.path == "/handoff":
                run = steps.Run(p["project"])
                ev = run.log({"event": "awaiting", "gate": p["gate"], "stage": p["gate"],
                              "role_planned": ROLES.get(p["gate"], p["gate"]), "files": p.get("files", []),
                              "resume_url": p["resume_url"], "execution": p.get("execution")})
                return self._send(200, ev)
            if u.path == "/decide":
                run = steps.Run(p["project"])
                led = run.ledger()
                # ledger order, not timestamps: two events can share the same second
                waiting = [i for i, e in enumerate(led) if e["event"] == "awaiting" and e["gate"] == p["gate"]]
                if not waiting:
                    return self._send(409, {"error": f"nothing is waiting at gate {p['gate']}"})
                i_last = waiting[-1]
                last = led[i_last]
                done = [e for e in led[i_last + 1:] if e["event"] in DECISIONS and e.get("gate") == p["gate"]]
                if done:
                    return self._send(409, {"error": f"gate {p['gate']} was already decided at {done[-1]['ts']}"})
                if p["gate"] == "shorts" and p["decision"] == "rejected":
                    return self._send(400, {"error": "refuse Shorts one by one, each with its fix: "
                                                     "./flow.py review-shorts --reject 2 --note ... --fix caption_pos=lower"})
                if p["gate"] == "shorts" and p["decision"] == "changes":
                    fixes_path = run.dir / "shorts_fixes.json"
                    known = json.loads(fixes_path.read_text()) if fixes_path.exists() else {}
                    refused = {k: v for k, v in (p.get("shorts") or {}).items() if isinstance(v, dict)}
                    if not refused:
                        return self._send(400, {"error": "a refusal names at least one Short"})
                    for k, v in refused.items():
                        fix = v.get("fix") or {}
                        if not fix or all(known.get(k, {}).get(a) == b for a, b in fix.items()):
                            return self._send(400, {"error": f"Short {k}: the refusal needs a fix that changes the cut "
                                                             "(for example --fix caption_pos=lower); without one the same file would come back"})
                ev = run.log({"event": p["decision"], "gate": p["gate"], "stage": p["gate"],
                              "role_planned": last["role_planned"], "actor": p.get("by", "builder (for this demo)"),
                              "note": p.get("note"), "shorts": p.get("shorts"), "files": last["files"],
                              "execution": last.get("execution")})
                post_json(last["resume_url"], {"decision": p["decision"], "by": ev["actor"], "note": p.get("note"),
                                               "shorts": p.get("shorts"), "ts": ev["ts"]})
                return self._send(200, ev)
            self._send(404, {"error": "not found"})
        except ValueError as e:
            self._send(400, {"error": str(e)})
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"error": str(e)})


if __name__ == "__main__":
    port = int(os.environ.get("RENDER_PORT", "8790"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"render service on 127.0.0.1:{port}", flush=True)
    srv.serve_forever()
