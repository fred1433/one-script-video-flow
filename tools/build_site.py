"""Copies a finished run into site/: the four final MP4s, the refused Short, posters, and data.js.

    python tools/build_site.py out/DEMO-001
Every time, name, role and version shown on the page comes from the run's ledger and state.
"""
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
RUN = Path(sys.argv[1]).resolve()
SITE = ROOT / "site"
MEDIA = SITE / "media"
MEDIA.mkdir(parents=True, exist_ok=True)
LON = ZoneInfo("Europe/London")

state = json.loads((RUN / "state.json").read_text())["assets"]
ledger = [json.loads(l) for l in (RUN / "ledger.jsonl").read_text().splitlines()]
sb = json.loads((RUN / state["storyboard"]["file"]).read_text())
vo = json.loads((RUN / "DEMO-001_vo-lines_v01.json").read_text())
pkg = json.loads((RUN / "DEMO-001_package.json").read_text())


def london(ts):
    d = datetime.fromisoformat(ts).astimezone(LON)
    return {"iso": d.isoformat(), "hm": d.strftime("%H:%M"), "day": d.strftime("%-d %b %Y")}


def copy(name):
    shutil.copy(RUN / name, MEDIA / name)
    return f"media/{name}"


def poster(video, t, out):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(RUN / video), "-frames:v", "1",
                    "-q:v", "3", str(MEDIA / out)], check=True)
    return f"media/{out}"


def probe(name):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height", "-of", "json",
                        str(RUN / name)], capture_output=True, text=True, check=True)
    j = json.loads(r.stdout)
    v = next(s for s in j["streams"] if "width" in s)
    return {"duration": round(float(j["format"]["duration"]), 1), "w": v["width"], "h": v["height"],
            "mb": round((RUN / name).stat().st_size / 1e6, 1)}


# only the last full run is shown (the one that produced the package now in out/)
last_start = max(i for i, e in enumerate(ledger) if e["event"] == "approved" and e.get("stage") == "script"
                 and any(x["event"] == "delivered" and x.get("stage") == "package" for x in ledger[i:]))
first_pkg = next(i for i in range(last_start, len(ledger)) if ledger[i]["event"] == "delivered" and ledger[i]["stage"] == "package")
run_events = ledger[last_start:first_pkg + 1]

master = state["master"]["file"]
data = {
    "project": "DEMO-001",
    "status": pkg["status"],
    "master": {"src": copy(master), "file": master, "poster": poster(master, 39.5, "poster_master.jpg"), **probe(master)},
    "scenes": [{"id": s["id"], "title": s["title"], "start": s["start"], "end": s["start"] + s["duration"] + s["hold"],
                "short": s["short"]} for s in sb["scenes"]],
    "lines": [{"id": k, "text": vo["lines"][k]["text"], "start": v["start"], "end": v["end"], "scene": v["scene"]}
              for k, v in sb["lines"].items()],
    "shorts": [],
    "events": [],
}
plan = {s["id"]: s for s in sb["plan"]["scenes"]}
for s in sb["scenes"]:
    if not s["short"]:
        continue
    idx = s["short"]
    asset = f"S{idx:02d}_vertical"
    a = state[asset]
    versions = []
    for v in range(1, a["version"] + 1):
        name = f"DEMO-001_{asset}_v{v:02d}.mp4"
        if (RUN / name).exists():
            versions.append({"v": v, "file": name, "src": copy(name),
                             "poster": poster(name, 6.0 if idx != 2 else 9.4, f"poster_S{idx:02d}_v{v:02d}.jpg"), **probe(name)})
    data["shorts"].append({"index": idx, "scene": s["id"], "hook": " ".join(plan[s["id"]]["hook"]),
                           "start": s["start"], "versions": versions})

STAGE = {"script": "Script approved", "voice": "Voice-over", "storyboard": "Storyboard", "look": "Look frames",
         "animate": "Scenes rendered", "master": "Master edit", "shorts": "Shorts", "package": "Ready to upload"}
for e in run_events:
    data["events"].append({"event": e["event"], "stage": e.get("stage"), "label": STAGE.get(e.get("stage"), e.get("stage")),
                           "role": e.get("role_planned"), "actor": e.get("actor"), "files": e.get("files", []),
                           "note": e.get("note"), "shorts": e.get("shorts"), "detail": e.get("detail"),
                           "time": london(e["ts"])})
data["thumbnail"] = copy(pkg["thumbnail"])
(SITE / "data.js").write_text("window.RUN = " + json.dumps(data, indent=1) + ";\n")
print("site/data.js written;", len(data["events"]), "events;", sum(len(s["versions"]) for s in data["shorts"]) + 1, "videos")
