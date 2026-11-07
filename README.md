# One script, one film, three Shorts

An n8n workflow that takes one approved script and returns a finished explainer (16:9) and three vertical Shorts (9:16), with every hand-off between roles waiting for a real sign-off and written to a ledger.

The sample is a 72-second explainer of a fictional cartridge lock. The device was invented for this demo; it is not a real product and the film makes no clinical claim. Every export carries the line "Independent demo · fictional device".

Page with the film, the Shorts and the hand-offs: https://theaipipe.com/demos/one-script-video-flow/

## Run it

Needs: macOS or Linux, Python 3.12, Blender 5.2, ffmpeg, docker with compose.

```
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
./flow.py up        # render service on 127.0.0.1:8790, n8n on 127.0.0.1:5678
./flow.py run       # sends the approved script in and answers each gate in turn
```

`./flow.py run` is the unattended rehearsal. In production each gate is answered by the person who owns it: `./flow.py status` shows what is waiting, `./flow.py approve <gate>` or `./flow.py reject <gate> --note "..."` answers it. The Shorts gate takes one decision per Short:

```
./flow.py review-shorts --approve 1,3 --reject 2 --note "The caption covers the lug" --fix caption_pos=lower
```

The first run renders every scene in Blender (about an hour and a half on an M1 Max). After that a run only redoes what changed.

## What is where

| Path | What it is |
|---|---|
| `n8n/workflow.json` | The workflow: 24 nodes, four human waiting points, one machine wait for the render |
| `render/service.py` | The render service n8n calls over HTTP (bound to 127.0.0.1) |
| `render/steps.py` | The steps: voice, storyboard, look frames, animation, master, Shorts, package |
| `render/blender/scene.py` | The lock, its materials, lights and the two cameras, built from code |
| `kit/kit_v01.json` | The kit: palette, typeface, voice, materials, file-name rule. One file, versioned |
| `script/DEMO-001_script.md` | The approved script |
| `script/storyboard_DEMO-001.json` | The shot plan: timings, both cameras, labels, Short hooks |
| `docs/RUNBOOK.md` | One row per role: receives, hands back, signs off, after a refusal |
| `tests/recipe.sh` | The three checks: clean clone offline, a refused Short, a changed line |
| `out/DEMO-001/` | Created by a run: the files, `ledger.jsonl`, `state.json` |

## The three checks

`tests/recipe.sh <repo> <empty dir>` clones the repository, runs it with an empty output folder, no API key and the render service in a macOS sandbox that blocks outbound network (n8n already has no route out), then:

1. produces the four MP4s after the sign-offs;
2. refuses Short 2 and checks that the package waits and that only Short 2 is cut again;
3. changes one line of the script, approves it again, and checks that only that line is voiced again and no scene is rendered again.

## Licences

Code: MIT. Manrope: SIL Open Font License 1.1 (`kit/fonts/OFL.txt`). Kokoro-82M: Apache 2.0. The palette and typeface are inspired by a public website; this is not an approved brand kit.
