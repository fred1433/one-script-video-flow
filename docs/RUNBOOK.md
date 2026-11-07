# Runbook: one approved script to a master and three Shorts

This is the operating sheet for the team. One row per role: what lands with you, what you hand back and under which name, who signs it off, and how the job restarts after a refusal.

The workflow lives in n8n (`n8n/workflow.json`). Every hand-off is a real waiting point in n8n: nothing moves to the next role until someone answers the gate. Every answer is written to the production ledger (`out/DEMO-001/ledger.jsonl`) with the time, the planned role and the person who actually answered.

In this demo every gate was answered by the builder's rehearsal command (`./flow.py run`), seconds after each hand-off, and the refusal of Short 2 was staged: its caption was planned at the centre of the frame on purpose, to show a refusal going round. The films were watched frame by frame afterwards. In a studio each gate waits for a person.

## File names

One rule, set in the kit (`kit/kit_v01.json`, key `naming`):

```
{project}_{asset}_v{version:02d}.{ext}
DEMO-001_master_v01.mp4
DEMO-001_S02_vertical_v02.mp4
DEMO-001_vo_L07_v01.wav
```

A file keeps its version while its inputs are unchanged. Change one input (a script line, a framing, a caption position) and only the files that depend on it get the next version. Nobody renames anything by hand.

## Roles

| Role (planned) | Receives | Hands back | Signs off | After a refusal |
|---|---|---|---|---|
| Producer | The client brief | The approved script, `script/DEMO-001_script.md` (one line per sentence, `L01`...) | Producer: approving the script is what starts the workflow | Edit the line and start again. Only the changed line is voiced again; every scene render is reused. |
| Voice-over (a local model in this demo; a voice artist or ElevenLabs in production) | The approved script | One file per line, `DEMO-001_vo_L03_v01.wav`, plus word timings for captions | No gate of its own: the lines are heard against the shots at the storyboard gate | Change the line in the script and approve the script again (Producer). Only that line is voiced again, same name, next version. |
| Storyboard & Camera Director | Script and voice timings | `DEMO-001_storyboard_v01.json` (the shot plan: 16:9 and 9:16 camera for every scene, line timings) and a contact sheet `DEMO-001_storyboard_v01.png` | Gate "storyboard" | Edit `script/storyboard_DEMO-001.json` and start again. The render cache is keyed on the whole shot plan, so a plan change renders the scenes again (about three hours on an M1 Max: 10,894 s in the recorded run). |
| AI Image Artist | Approved storyboard and the kit | `DEMO-001_lookframes_v01.png`: two finished frames that fix the look (materials, light, palette) before anything is animated | Gate "look" | Change the kit and raise its version. Every scene renders again, because the look changed. |
| AI Video Animator | Approved look | Scene renders, then `DEMO-001_master_v01.mp4` and `DEMO-001_master_v01.srt` | Gate "master" | Fix the storyboard or the kit and start again; both send the scenes back to Blender. A change that only touches voice, captions or labels renders nothing again. |
| Storyboard & Camera Director (vertical review) | Approved master | `DEMO-001_S01_vertical_v01.mp4`, `S02`, `S03`, composed natively at 1080x1920 from the vertical camera planned in the storyboard | Gate "shorts", one decision per Short | Refuse one Short with a reason and a fix (`--fix caption_pos=lower`). The package stays on hold, only that Short is cut again as `v02`, and it comes back to the same gate. The fix is kept for later runs. |
| Producer | Everything approved | `DEMO-001_package.json` (title, chapters, files and their checksums, every approval), thumbnail, SRT files. Status: Ready to upload | | |

## Commands

```
./flow.py up                 # render service on 127.0.0.1:8790, n8n on 127.0.0.1:5678
./flow.py start              # the approved script enters the workflow
./flow.py status             # the ledger, one line per event
./flow.py approve storyboard # answer a gate
./flow.py reject look --note "the stop reads orange, not amber"   # any gate but the Shorts gate
./flow.py review-shorts --approve 1,3 --reject 2 --note "The caption covers the lug" --fix caption_pos=lower
./flow.py down
```

`./flow.py run` starts the script and answers every gate in order, for an unattended rehearsal.

## Where a paid tool would plug in

No paid connector ships switched off in this workflow: an integration that never ran is not something to hand over. Each media step is one function in `render/steps.py` with a fixed input and output, and that is where a paid tool would go:

- Voice: `_tts(text, voice)` returns audio and word timings. A voice API would replace it line for line, and the word timings would come from its timestamps.
- Look frames: `step_look` renders two frames from the kit. An image model would take the storyboard frame as its reference here.
- Animation: `step_animate` renders each scene in Blender. An image-to-video model would take a scene's look frame and its shot plan, and return a clip of the same length.

## What this demo used

- n8n 2.46.6, self-hosted with docker compose. n8n sits on an internal network with no route out, and a two-port relay is its only door. No Execute Command node.
- Render service: Python, on the host, called by n8n over HTTP.
- Voice: Kokoro-82M, voice `bf_emma`, run locally (Apache 2.0 model); the audition of four British voices is in `docs/voice_audition.md`.
- 3D: Blender 5.2 (EEVEE), one model built from code, clay material, two cameras.
- Captions, callouts, titles: Pillow, using Manrope (SIL Open Font License).
- Sound: the click and the section sweep are synthesised in code. No music.
- Edit, encode, loudness: ffmpeg.
- Model API spend for the run: 0 dollars.
