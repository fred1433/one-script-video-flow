#!/usr/bin/env python3
"""One command line for the whole flow.

  ./flow.py up [--offline]          start the render service (host) and n8n (docker)
  ./flow.py start                   send the approved script into the workflow
  ./flow.py status                  print the production ledger
  ./flow.py approve <gate> [--note] approve the file waiting at a gate (the Shorts gate needs review-shorts)
  ./flow.py reject <gate> --note    send it back
  ./flow.py review-shorts --approve 1,3 --reject 2 --note "..." --fix caption_pos=lower
  ./flow.py run [--reject-short 2 --note ... --fix ...]   start, then answer every gate in order
  ./flow.py down
"""
import argparse
import json
import re
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RENDER = "http://127.0.0.1:8790"
N8N = "http://127.0.0.1:5678"
PROJECT = "DEMO-001"
GATES = ["storyboard", "look", "master", "shorts"]


def compose_cmd():
    ok = subprocess.run(["docker", "compose", "version"], capture_output=True).returncode == 0
    return ["docker", "compose"] if ok else ["docker-compose"]


def call(method, url, body=None, timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"{url}: {e.code} {e.read().decode()[:300]}")


def wait_for(url, seconds=180):
    for _ in range(seconds):
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(1)
    sys.exit(f"{url} did not answer within {seconds}s")


def up(offline):
    out = Path(os.environ.get("FLOW_OUT", ROOT / "out"))
    out.mkdir(parents=True, exist_ok=True)
    log = open(out / "render_service.log", "a")
    py = str(ROOT / ".venv/bin/python")
    cmd = [py, str(ROOT / "render/service.py")]
    env = dict(os.environ, HF_HUB_OFFLINE="1" if offline else os.environ.get("HF_HUB_OFFLINE", "0"))
    if offline:
        # macOS sandbox: the render service may talk to loopback only
        cmd = ["sandbox-exec", "-f", str(ROOT / "tests/no-network.sb")] + cmd
    if os.environ.get("FLOW_GENTLE") == "1":
        cmd = ["taskpolicy", "-b"] + cmd  # shared machine: background priority
    p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, cwd=ROOT, start_new_session=True)
    (out / "render_service.pid").write_text(str(p.pid))
    wait_for(RENDER + "/health", 60)
    subprocess.run(compose_cmd() + ["up", "-d"], cwd=ROOT, check=True)
    wait_for(N8N + "/healthz", 240)
    print("render service and n8n are up")


def down():
    out = Path(os.environ.get("FLOW_OUT", ROOT / "out"))
    pid = out / "render_service.pid"
    if pid.exists():
        try:
            os.killpg(int(pid.read_text()), 15)
        except ProcessLookupError:
            pass
        pid.unlink()
    subprocess.run(compose_cmd() + ["down"], cwd=ROOT)


def ledger():
    return call("GET", f"{RENDER}/ledger?project={PROJECT}")["ledger"]


def status():
    for e in ledger():
        files = ", ".join(e.get("files", [])[:4]) + (" ..." if len(e.get("files", [])) > 4 else "")
        print(f"{e['ts']}  {e['event']:<9} {e.get('stage', ''):<11} {e.get('role_planned', ''):<30} "
              f"{e.get('actor', '')[:28]:<28} {files}")


def pending():
    """The gate waiting now, by ledger order (two events can share the same second)."""
    led = ledger()
    for i in range(len(led) - 1, -1, -1):
        e = led[i]
        if e["event"] == "awaiting":
            decided = any(d.get("gate") == e["gate"] and d["event"] in ("approved", "rejected", "changes")
                          for d in led[i + 1:])
            return None if decided else e["gate"]
        if e["event"] == "delivered" and e.get("stage") == "package":
            return "done"
    return None


def shorts_waiting():
    """Indices of the Short versions waiting at the review gate, read from the last hand-off."""
    last = [e for e in ledger() if e["event"] == "awaiting" and e.get("gate") == "shorts"][-1]
    return sorted({int(m.group(1)) for f in last["files"] for m in [re.search(r"_S(\d+)_vertical", f)] if m})


def decide(gate, decision, note=None, shorts=None):
    return call("POST", f"{RENDER}/decide", {"project": PROJECT, "gate": gate, "decision": decision, "note": note,
                                              "shorts": shorts, "by": "builder (for this demo)"})


def start(script, quality):
    body = {"project": PROJECT, "script": script, "storyboard": "script/storyboard_DEMO-001.json",
            "quality": quality, "approved_by": "builder (for this demo)"}
    for _ in range(90):  # n8n registers published webhooks a few seconds after it reports healthy
        req = urllib.request.Request(f"{N8N}/webhook/one-script-flow", data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            n0 = len(ledger())
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
            for _ in range(30):  # the run counts as started once the script approval is in the ledger
                if any(e["event"] == "approved" and e.get("stage") == "script" for e in ledger()[n0:]):
                    return json.loads(raw) if raw.strip().startswith(b"{") else {"started": True}
                time.sleep(2)
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            time.sleep(2)
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(3)
    sys.exit("the workflow webhook never registered")


def parse_fix(items):
    return dict(i.split("=", 1) for i in items or [])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("gate", nargs="?")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--note")
    ap.add_argument("--approve", default="")
    ap.add_argument("--reject", default="")
    ap.add_argument("--fix", action="append")
    ap.add_argument("--reject-short", type=int)
    ap.add_argument("--script", default="script/DEMO-001_script.md")
    ap.add_argument("--quality", default="final")
    ap.add_argument("--timeout", type=int, default=4 * 3600)
    a = ap.parse_args()
    if a.cmd == "up":
        up(a.offline)
    elif a.cmd == "down":
        down()
    elif a.cmd == "status":
        status()
    elif a.cmd == "start":
        print(start(a.script, a.quality))
    elif a.cmd == "approve":
        print(decide(a.gate, "approved", a.note))
    elif a.cmd == "reject":
        print(decide(a.gate, "rejected", a.note))
    elif a.cmd == "review-shorts":
        shorts = {i: "approved" for i in a.approve.split(",") if i}
        for i in [x for x in a.reject.split(",") if x]:
            shorts[i] = {"rejected": a.note, "fix": parse_fix(a.fix)}
        print(decide("shorts", "changes" if a.reject else "approved", a.note, shorts))
    elif a.cmd == "run":
        n0 = len(ledger())
        print(start(a.script, a.quality))
        rejected_once = False
        t_end = time.time() + a.timeout
        while time.time() < t_end:
            try:
                led = ledger()[n0:]
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                time.sleep(3)  # the service is busy cutting; ask again
                continue
            if any(e["event"] == "delivered" and e.get("stage") == "package" for e in led):
                print("package ready")
                status()
                return
            g = pending() if led else None
            if g in GATES:
                if g == "shorts" and a.reject_short and not rejected_once:
                    shorts = {str(i): "approved" for i in shorts_waiting() if i != a.reject_short}
                    shorts[str(a.reject_short)] = {"rejected": a.note, "fix": parse_fix(a.fix)}
                    print(f"review shorts: S{a.reject_short:02d} sent back ({a.note})")
                    decide("shorts", "changes", a.note, shorts)
                    rejected_once = True
                elif g == "shorts":
                    idx = shorts_waiting()
                    print("approve shorts " + ",".join(f"S{i:02d}" for i in idx))
                    decide("shorts", "approved", "looks right", {str(i): "approved" for i in idx})
                else:
                    print(f"approve {g}")
                    decide(g, "approved", "looks right")
            time.sleep(3)
        sys.exit("timed out")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
