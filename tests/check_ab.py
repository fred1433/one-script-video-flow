"""Checks (a) and (b) on the ledger and the files of one run."""
import json, sys
from pathlib import Path
d = Path(sys.argv[1])
led = [json.loads(l) for l in (d / "ledger.jsonl").read_text().splitlines()]
mp4 = sorted(p.name for p in d.glob("*.mp4"))
print("mp4 files:", mp4)
need = ["DEMO-001_master_v01.mp4", "DEMO-001_S01_vertical_v01.mp4", "DEMO-001_S02_vertical_v02.mp4", "DEMO-001_S03_vertical_v01.mp4"]
assert all(n in mp4 for n in need), "a final MP4 is missing"
print("(a) four final MP4s present")
i_ref = next(i for i, e in enumerate(led) if e["event"] == "changes" and e["gate"] == "shorts")
i_pkg = next(i for i, e in enumerate(led) if e["event"] == "delivered" and e["stage"] == "package")
rework = next(e for e in led[i_ref:] if e["event"] == "delivered" and e["stage"] == "shorts")
re_ok = next(e for e in led[i_ref:] if e["event"] == "approved" and e["gate"] == "shorts")
assert i_ref < i_pkg and led.index(re_ok) < i_pkg, "package written before the refused Short was approved again"
assert rework["files"] == ["DEMO-001_S02_vertical_v02.mp4"], rework["files"]
st = json.loads((d / "state.json").read_text())["assets"]
print(f"(b) refused at {led[i_ref]['ts']}, reworked file {rework['files']}, approved again at {re_ok['ts']}, package at {led[i_pkg]['ts']}")
print("    S01 and S03 untouched:", st["S01_vertical"]["version"], st["S03_vertical"]["version"])
