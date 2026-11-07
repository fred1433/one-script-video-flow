"""Check (c): one changed line re-voices that line and re-cuts what contains it, nothing else."""
import json, sys
from pathlib import Path
d, lid = Path(sys.argv[1]), sys.argv[2]
led = [json.loads(l) for l in (d / "ledger.jsonl").read_text().splitlines()]
starts = [i for i, e in enumerate(led) if e["event"] == "approved" and e["stage"] == "script"]
last = led[starts[-1]:]
step = {e["stage"]: e for e in last if e["event"] == "delivered"}
print("voice changed lines:", step["voice"]["detail"]["changed_lines"])
print("scenes rendered again:", step["animate"]["detail"]["rendered"], "reused:", len(step["animate"]["detail"]["reused"]))
print("master:", step["master"]["files"], "shorts:", [(s["file"], s["rebuilt"]) for s in step["shorts"]["detail"]["shorts"]])
assert step["voice"]["detail"]["changed_lines"] == [lid], "another line was voiced again"
assert step["animate"]["detail"]["rendered"] == []
srt = (d / step["master"]["files"][0].replace(".mp4", ".srt")).read_text()
hit = [l for l in srt.splitlines() if "locks with a single" in l]
assert hit, "the new line is not in the master captions"
unchanged = [s["file"] for s in step["shorts"]["detail"]["shorts"] if not s["rebuilt"]]
print("(c) new line in the master captions:", hit, "| Shorts reused as they were:", unchanged)
