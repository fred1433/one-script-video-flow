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

ledger = [json.loads(l) for l in (RUN / "ledger.jsonl").read_text().splitlines()]
# one run = from a script approval to its package; show the first complete run unless told otherwise
starts = [i for i, e in enumerate(ledger) if e["event"] == "approved" and e.get("stage") == "script"]
runs = []
for i, s0 in enumerate(starts):
    seg = ledger[s0:(starts[i + 1] if i + 1 < len(starts) else len(ledger))]
    if any(e["event"] == "delivered" and e.get("stage") == "package" for e in seg):
        runs.append(seg)
run_events = runs[int(sys.argv[2]) if len(sys.argv) > 2 else 0]
delivered = lambda st: [e for e in run_events if e["event"] == "delivered" and e.get("stage") == st]
sb = json.loads((RUN / delivered("storyboard")[0]["files"][0]).read_text())
master_file = delivered("master")[0]["files"][0]
# line texts as they were in this run: read back from the master's own caption file
srt_rows = [b.split("\n", 2)[2].strip() for b in (RUN / master_file.replace(".mp4", ".srt")).read_text().strip().split("\n\n")]
line_text = dict(zip(sb["lines"].keys(), srt_rows))
pkg_event = delivered("package")[0]


def london(ts):
    d = datetime.fromisoformat(ts).astimezone(LON)
    return {"iso": d.isoformat(), "hm": d.strftime("%H:%M"), "day": d.strftime("%-d %b %Y")}


def copy(name):
    shutil.copy(RUN / name, MEDIA / name)
    return f"media/{name}"


def poster(video, t, out):
    subprocess.run(["taskpolicy", "-b", "ffmpeg", "-threads", "2", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(RUN / video), "-frames:v", "1",
                    "-q:v", "3", str(MEDIA / out)], check=True)
    return f"media/{out}"


def look_poster():
    """The look frame signed off in this run, without overlays, as the film's poster."""
    from PIL import Image
    look = next(e for e in run_events if e["event"] == "delivered" and e.get("stage") == "look")["files"][0]
    Image.open(RUN / look).convert("RGB").crop((0, 0, 1920, 1080)).save(MEDIA / "poster_master.jpg", quality=88)
    return "media/poster_master.jpg"


def probe(name):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height", "-of", "json",
                        str(RUN / name)], capture_output=True, text=True, check=True)
    j = json.loads(r.stdout)
    v = next(s for s in j["streams"] if "width" in s)
    return {"duration": round(float(j["format"]["duration"]), 1), "w": v["width"], "h": v["height"],
            "mb": round((RUN / name).stat().st_size / 1e6, 1)}


master = master_file
data = {
    "project": "DEMO-001",
    "status": pkg_event["detail"]["status"],
    "master": {"src": copy(master), "file": master, "poster": look_poster(), **probe(master)},
    "scenes": [{"id": s["id"], "title": s["title"], "start": s["start"], "end": s["start"] + s["duration"] + s["hold"],
                "short": s["short"]} for s in sb["scenes"]],
    "lines": [{"id": k, "text": line_text[k], "start": v["start"], "end": v["end"], "scene": v["scene"]}
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
    names = [f for e in delivered("shorts") for f in e["files"] if asset in f]
    versions = []
    for name in names:
        v = int(name.split("_v")[-1].split(".")[0])
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
data["thumbnail"] = copy(pkg_event["files"][1])
(SITE / "data.js").write_text("window.RUN = " + json.dumps(data, indent=1) + ";\n")
print("site/data.js written;", len(data["events"]), "events;", sum(len(s["versions"]) for s in data["shorts"]) + 1, "videos")
