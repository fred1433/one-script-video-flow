"""Production steps called by the render service (and therefore by n8n).

Every step reads the run state, writes named files into out/<project>/, and returns the
list of files it produced. Work is cached by input hash: a step whose inputs did not change
keeps its file and its version number; a step whose inputs changed writes the next version.
"""
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
KIT_PATH = ROOT / "kit" / "kit_v01.json"
OUT = Path(os.environ.get("FLOW_OUT", ROOT / "out"))
CACHE = Path(os.environ.get("FLOW_CACHE", ROOT / "cache"))
BLENDER = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
FFMPEG = os.environ.get("FFMPEG", shutil.which("ffmpeg") or "ffmpeg")
SR = 24000


def kit():
    return json.loads(KIT_PATH.read_text())


def now():
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def h(*parts):
    m = hashlib.sha1()
    for p in parts:
        m.update(json.dumps(p, sort_keys=True).encode() if not isinstance(p, bytes) else p)
    return m.hexdigest()[:12]


def file_hash(p):
    return hashlib.sha1(Path(p).read_bytes()).hexdigest()[:12]


# ------------------------------------------------------------------ run state, naming, ledger
class Run:
    def __init__(self, project):
        self.project = project
        self.dir = OUT / project
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / "state.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {"assets": {}}

    def save(self):
        self.state_path.write_text(json.dumps(self.state, indent=2))

    def name(self, asset, version, ext):
        n = kit()["naming"]
        return n["pattern"].format(project=self.project, asset=asset, version=version, ext=ext)

    def version_for(self, asset, input_hash):
        """Same inputs keep the same version; new inputs get the next version."""
        a = self.state["assets"].get(asset)
        if a and a["input"] == input_hash:
            return a["version"], False
        return (a["version"] + 1 if a else 1), True

    def record(self, asset, version, input_hash, path, **extra):
        self.state["assets"][asset] = {"version": version, "input": input_hash, "file": Path(path).name,
                                       "sha1": file_hash(path), "written": now(), **extra}
        self.save()

    def log(self, event):
        event = {"ts": now(), **event}
        with open(self.dir / "ledger.jsonl", "a") as f:
            f.write(json.dumps(event) + "\n")
        return event

    def ledger(self):
        p = self.dir / "ledger.jsonl"
        return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


# ------------------------------------------------------------------ script
def parse_script(path):
    text = Path(path).read_text()
    meta = dict(re.findall(r"^(\w+): (.+)$", text.split("---")[1], re.M)) if text.startswith("---") else {}
    scenes, lines, cur = [], {}, None
    for raw in text.splitlines():
        m = re.match(r"## (\w)\. ([^\[]+?)\s*(\[short: S(\d+) \"(.+)\"\])?$", raw.strip())
        if m:
            cur = {"id": m.group(1), "title": m.group(2), "short": int(m.group(4)) if m.group(4) else None,
                   "hook": m.group(5), "lines": []}
            scenes.append(cur)
            continue
        m = re.match(r"(L\d\d): (.+)$", raw.strip())
        if m and cur:
            lines[m.group(1)] = {"id": m.group(1), "text": m.group(2), "scene": cur["id"]}
            cur["lines"].append(m.group(1))
    return {"meta": meta, "scenes": scenes, "lines": lines, "sha1": hashlib.sha1(text.encode()).hexdigest()[:12]}


# ------------------------------------------------------------------ step 1: voice
_PIPE = None


def _tts(text, voice):
    global _PIPE
    if _PIPE is None:
        from kokoro import KPipeline
        _PIPE = KPipeline(lang_code=voice["lang"], repo_id=voice["model"])
    audio, words, offset = [], [], 0.0
    for r in _PIPE(text, voice=voice["voice"], speed=voice["speed"]):
        a = r.audio.numpy()
        for t in r.tokens or []:
            if t.start_ts is None or not re.search(r"\w", t.text):
                continue
            words.append({"w": t.text, "s": round(offset + t.start_ts, 3), "e": round(offset + t.end_ts, 3)})
        audio.append(a)
        offset += len(a) / SR
    return np.concatenate(audio), words


def write_wav(path, audio):
    a = np.clip(audio, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((a * 32767).astype("<i2").tobytes())


def read_wav(path):
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32767


def step_voice(run, script_path):
    sc = parse_script(script_path)
    voice = kit()["voice"]
    vdir = run.dir / "voice"
    vdir.mkdir(exist_ok=True)
    (CACHE / "voice").mkdir(parents=True, exist_ok=True)
    out, changed = {}, []
    for lid, line in sc["lines"].items():
        key = h(line["text"], voice)
        wav, meta = CACHE / "voice" / f"{key}.wav", CACHE / "voice" / f"{key}.json"
        if not wav.exists():
            audio, words = _tts(line["text"], voice)
            write_wav(wav, audio)
            meta.write_text(json.dumps({"text": line["text"], "words": words, "dur": round(len(audio) / SR, 3)}))
        m = json.loads(meta.read_text())
        ver, new = run.version_for(f"vo_{lid}", key)
        dst = vdir / run.name(f"vo_{lid}", ver, "wav")
        if new or not dst.exists():
            shutil.copy(wav, dst)
            run.record(f"vo_{lid}", ver, key, dst, text=line["text"])
            if ver > 1:
                changed.append(lid)
        out[lid] = {"file": f"voice/{dst.name}", "version": ver, "dur": m["dur"], "words": m["words"], "text": line["text"]}
    lines_json = run.dir / run.name("vo-lines", 1, "json")
    lines_json.write_text(json.dumps({"script_sha1": sc["sha1"], "voice": voice, "lines": out}, indent=2))
    return {"files": [f"voice/{v['file'].split('/')[-1]}" for v in out.values()], "changed_lines": changed,
            "script_sha1": sc["sha1"], "voice": f"{voice['engine']} {voice['voice']}"}


# ------------------------------------------------------------------ step 2: storyboard
def build_timeline(run, sb, vo):
    """Two clocks: animation time (Blender keys) and film time (animation plus any held frames)."""
    fps = sb["fps"]
    t_anim, t_film = 0.0, 0.0
    tl = {"fps": fps, "lug_z": [], "theta": [], "section": [], "cams": {"wide": [], "tall": []}}
    placed, warnings, scenes = {}, [], []
    for s in sb["scenes"]:
        hold, cursor = 0.0, 0.0
        for lid, at in s["lines"].items():
            start = max(at, cursor)
            if start > at + 0.01:
                warnings.append(f"{lid} starts {start - at:.2f}s late: the previous line runs long")
            end = start + vo["lines"][lid]["dur"]
            placed[lid] = {"scene": s["id"], "start": round(t_film + start, 3), "end": round(t_film + end, 3)}
            cursor = end + sb["line_gap"]
        over = cursor - sb["line_gap"] + 0.6 - s["duration"]
        if over > 0:
            hold = math.ceil(over * fps) / fps
            warnings.append(f"scene {s['id']} holds its last frame {hold:.2f}s: its lines run past the shot")
        for track, keys in s.get("motion", {}).items():
            tl[track] += [[round(t_anim + t, 3), v] for t, v in keys]
        for cam, keys in s["cams"].items():
            tl["cams"][cam] += [[round(t_anim + k[0], 3)] + k[1:] for k in keys]
        scenes.append({"id": s["id"], "title": s["title"], "start": round(t_film, 3), "anim_start": round(t_anim, 3),
                       "duration": s["duration"], "hold": hold, "short": s.get("short"),
                       "events": s.get("events", {}), "callouts": s.get("callouts", []),
                       "overlay": s.get("overlay"), "endcard": s.get("endcard")})
        t_anim += s["duration"]
        t_film += s["duration"] + hold
    tl["frames"] = int(round(t_anim * fps)) + 2
    return tl, scenes, placed, warnings


def blender_job(job, log_path):
    job_path = Path(log_path).with_suffix(".job.json")
    job_path.write_text(json.dumps(job))
    with open(log_path, "w") as lg:
        subprocess.run([BLENDER, "-b", "--factory-startup", "-P", str(ROOT / "render/blender/scene.py"), "--",
                        str(job_path)], stdout=lg, stderr=subprocess.STDOUT, check=True)


def still(timeline, cam, t, out_png, pct=50, samples=16):
    res = [1920, 1080] if cam == "wide" else [1080, 1920]
    fr = int(round(1 + t * timeline["fps"]))
    blender_job({"timeline": timeline, "camera": cam, "frame_start": fr, "frame_end": fr, "out": str(out_png),
                 "res": res, "res_pct": pct, "samples": samples, "kit": kit(), "still": True},
                str(out_png) + ".log")


def step_storyboard(run, storyboard_path):
    sb = json.loads(Path(storyboard_path).read_text())
    vo = json.loads((run.dir / run.name("vo-lines", 1, "json")).read_text())
    tl, scenes, placed, warnings = build_timeline(run, sb, vo)
    key = h(sb, {k: v["dur"] for k, v in vo["lines"].items()}, kit()["geometry"])
    ver, new = run.version_for("storyboard", key)
    jpath = run.dir / run.name("storyboard", ver, "json")
    sheet = run.dir / run.name("storyboard", ver, "png")
    doc = {"project": run.project, "version": ver, "fps": sb["fps"], "timeline": tl, "scenes": scenes,
           "lines": placed, "warnings": warnings, "plan": sb, "kit_version": kit()["version"]}
    if new or not jpath.exists():
        jpath.write_text(json.dumps(doc, indent=2))
        # contact sheet: one frame per scene from each planned camera, rendered from the shot plan
        tmp = CACHE / "stills" / key
        tmp.mkdir(parents=True, exist_ok=True)
        cells = []
        for s in scenes:
            mid = s["anim_start"] + s["duration"] * 0.62
            for cam in (["wide", "tall"] if s["short"] else ["wide"]):
                p = tmp / f"{s['id']}_{cam}.png"
                if not p.exists():
                    still(tl, cam, mid, p)
                cells.append((s, cam, p))
        contact_sheet(cells, placed, vo, sheet, run.project, ver)
        run.record("storyboard", ver, key, jpath, sheet=sheet.name)
    return {"files": [jpath.name, sheet.name], "version": ver, "warnings": warnings,
            "duration": round(sum(s["duration"] + s["hold"] for s in scenes), 2)}


def font(size, weight=600):
    f = ImageFont.truetype(str(ROOT / kit()["type"]["file"]), size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def hexc(hx, a=255):
    hx = hx.lstrip("#")
    return tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def contact_sheet(cells, placed, vo, out, project, ver):
    P = kit()["palette"]
    W = 2400
    rows = []
    for s, cam, p in cells:
        im = Image.open(p).convert("RGB")
        rows.append((s, cam, im))
    widths = {"wide": 760, "tall": 240}
    H = 120 + len({s["id"] for s, _, _ in rows}) * 470
    sheet = Image.new("RGB", (W, H), hexc(P["paper"])[:3])
    d = ImageDraw.Draw(sheet)
    d.text((60, 40), f"{project}  storyboard v{ver:02d}", font=font(40, 800), fill=hexc(P["ink"]))
    y = 120
    for sid in dict.fromkeys(s["id"] for s, _, _ in rows):
        group = [(s, c, im) for s, c, im in rows if s["id"] == sid]
        x = 60
        for s, cam, im in group:
            w = widths[cam]
            im = im.resize((w, int(im.height * w / im.width)))
            if cam == "tall":
                im = im.resize((240, 426))
            sheet.paste(im, (x, y))
            x += w + 24
        s = group[0][0]
        d.text((x + 20, y), f"{s['id']}  {s['title']}", font=font(34, 800), fill=hexc(P["ink"]))
        d.text((x + 20, y + 48), f"{s['start']:.1f}s to {s['start'] + s['duration']:.1f}s"
               + (f"   vertical short S{s['short']:02d}" if s["short"] else ""), font=font(24, 600), fill=hexc(P["blue"]))
        ty = y + 100
        for lid, pl in placed.items():
            if pl["scene"] != sid:
                continue
            txt = vo["lines"][lid]["text"]
            for row in wrap(txt, font(24, 500), W - x - 80):
                d.text((x + 20, ty), row, font=font(24, 500), fill=hexc(P["ink"]))
                ty += 32
            ty += 10
        y += 470
    sheet.save(out)


def wrap(text, f, width):
    words, rows, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.getlength(t) > width and cur:
            rows.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        rows.append(cur)
    return rows


# ------------------------------------------------------------------ step 3: look frames (AI Image Artist)
def step_look(run):
    sb = json.loads((run.dir / run.state["assets"]["storyboard"]["file"]).read_text())
    tl = sb["timeline"]
    key = h(kit()["materials"], kit()["render"], kit()["geometry"], file_hash(ROOT / "render/blender/scene.py"))
    ver, new = run.version_for("lookframes", key)
    out = run.dir / run.name("lookframes", ver, "png")
    if new or not out.exists():
        tmp = CACHE / "stills" / ("look_" + key)
        tmp.mkdir(parents=True, exist_ok=True)
        c = next(s for s in sb["scenes"] if s["id"] == "C")
        d = next(s for s in sb["scenes"] if s["id"] == "D")
        a, b = tmp / "wide.png", tmp / "tall.png"
        if not a.exists():
            still(tl, "wide", c["anim_start"] + 10.0, a, pct=100, samples=48)
        if not b.exists():
            still(tl, "tall", d["anim_start"] + 9.0, b, pct=100, samples=48)
        A, B = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
        B = B.resize((int(B.width * 1080 / B.height), 1080))
        sheet = Image.new("RGB", (A.width + B.width + 40, 1080), hexc(kit()["palette"]["paper"])[:3])
        sheet.paste(A, (0, 0))
        sheet.paste(B, (A.width + 40, 0))
        sheet.save(out)
        run.record("lookframes", ver, key, out)
    return {"files": [out.name], "version": ver}


# ------------------------------------------------------------------ step 4: animation (AI Video Animator)
def scene_jobs(sb):
    jobs = []
    tl = sb["timeline"]
    for s in sb["scenes"]:
        f0 = int(round(s["anim_start"] * sb["fps"])) + 1
        f1 = int(round((s["anim_start"] + s["duration"]) * sb["fps"]))
        cams = ["wide"] + (["tall"] if s["short"] else [])
        for cam in cams:
            key = h(tl, cam, f0, f1, kit()["materials"], kit()["render"], kit()["geometry"],
                    file_hash(ROOT / "render/blender/scene.py"))
            jobs.append({"scene": s["id"], "cam": cam, "f0": f0, "f1": f1, "key": key})
    return jobs


def step_animate(run, quality="final"):
    sb = json.loads((run.dir / run.state["assets"]["storyboard"]["file"]).read_text())
    rendered, reused = [], []
    pct = {"final": 100, "preview": 34, "draft": 20}[quality]
    samples = {"final": kit()["render"]["samples"], "preview": 8, "draft": 4}[quality]
    for j in scene_jobs(sb):
        d = CACHE / "frames" / f"{j['key']}_{quality}"
        n = j["f1"] - j["f0"] + 1
        if d.exists() and len(list(d.glob("f_*.jpg"))) == n and (d / "anchors.json").exists():
            reused.append(f"{j['scene']}-{j['cam']}")
            continue
        d.mkdir(parents=True, exist_ok=True)
        res = [1920, 1080] if j["cam"] == "wide" else [1080, 1920]
        blender_job({"timeline": sb["timeline"], "camera": j["cam"], "frame_start": j["f0"], "frame_end": j["f1"],
                     "out": str(d), "anchors_out": str(d / "anchors.json"), "res": res, "res_pct": pct,
                     "samples": samples, "kit": kit()}, str(d / "render.log"))
        rendered.append(f"{j['scene']}-{j['cam']}")
    return {"rendered": rendered, "reused": reused, "quality": quality}


# ------------------------------------------------------------------ compositor
class Overlay:
    """Draws captions, callouts, titles and the demo notice over rendered frames."""

    def __init__(self, sb, vo, fmt, opts):
        self.sb, self.vo, self.fmt, self.opts = sb, vo, fmt, opts
        self.K = kit()
        self.P = self.K["palette"]
        self.W, self.H = (1920, 1080) if fmt == "wide" else (1080, 1920)
        self.cache = {}

    def text_img(self, text, size, weight, color, key=None):
        k = (text, size, weight, color)
        if k not in self.cache:
            f = font(size, weight)
            l, t, r, b = f.getbbox(text)
            im = Image.new("RGBA", (r + 4, b + 6), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((2, 0), text, font=f, fill=hexc(color))
            self.cache[k] = im
        return self.cache[k]

    def paste(self, base, im, xy, alpha=1.0):
        if alpha <= 0:
            return
        if alpha < 1:
            im = im.copy()
            im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
        base.alpha_composite(im, (int(xy[0]), int(xy[1])))

    @staticmethod
    def ramp(t, t_in, t_out, fade=0.35):
        if t < t_in or t > t_out:
            return 0.0
        return max(0.0, min(1.0, (t - t_in) / fade, (t_out - t) / fade))

    # ---------------- captions
    def caption(self, base, t, pos):
        for lid, pl in self.sb["lines"].items():
            if pl["start"] - 0.05 <= t <= pl["end"] + 0.25:
                line = self.vo["lines"][lid]
                words = line["words"]
                lt = t - pl["start"]
                if self.fmt == "wide":
                    self.caption_wide(base, line["text"], words, lt, self.ramp(t, pl["start"] - 0.05, pl["end"] + 0.25, 0.15))
                else:
                    self.caption_tall(base, words, lt, pos)
                return lid
        return None

    def caption_wide(self, base, text, words, lt, alpha):
        f = font(40, 600)
        rows = wrap(text, f, 1240)
        active = max([i for i, w in enumerate(words) if w["s"] <= lt] or [0])
        y = self.H - 96 - 56 * len(rows)
        wmax = max(f.getlength(r) for r in rows)
        plate = Image.new("RGBA", base.size, (0, 0, 0, 0))
        ImageDraw.Draw(plate).rounded_rectangle([(self.W - wmax) / 2 - 26, y - 12, (self.W + wmax) / 2 + 26, y + 56 * len(rows) + 6],
                                                22, fill=(247, 248, 248, int(190 * alpha)))
        base.alpha_composite(plate)
        wi = 0
        for row in rows:
            tokens = row.split()
            widths = [f.getlength(tok + " ") for tok in tokens]
            x = (self.W - sum(widths) + f.getlength(" ")) / 2
            for tok, w in zip(tokens, widths):
                col = self.P["blue"] if wi == active and lt < words[-1]["e"] + 0.1 else self.P["ink"]
                self.paste(base, self.text_img(tok, 40, 600, col), (x, y), alpha)
                x += w
                wi += 1
            y += 56

    def caption_tall(self, base, words, lt, pos):
        groups, cur = [], []
        for w in words:
            cur.append(w)
            full = len(cur) == 3 or len(" ".join(x["w"] for x in cur)) > 16
            if re.search(r"[,.]$", w["w"]) or (full and w["w"].lower() not in ("the", "a", "an", "to", "of", "into", "and", "on", "in")):
                groups.append(cur)
                cur = []
        if cur:
            groups.append(cur)
        g = next((g for g in groups if g[0]["s"] - 0.05 <= lt <= g[-1]["e"] + 0.12), None)
        if g is None:
            g = next((g for g in reversed(groups) if g[0]["s"] <= lt), None)
            if g is None or lt > g[-1]["e"] + 0.4:
                return
        size, wt = 76, 800
        f = font(size, wt)
        toks = [w["w"].strip() for w in g]
        widths = [f.getlength(x + " ") for x in toks]
        total = sum(widths) - f.getlength(" ")
        x = (self.W - total) / 2
        y = {"center": self.H * 0.47, "lower": self.H * 0.735}[pos]
        plate = Image.new("RGBA", base.size, (0, 0, 0, 0))
        ImageDraw.Draw(plate).rounded_rectangle([x - 28, y - 14, x + total + 28, y + size + 34], 30, fill=(247, 248, 248, 190))
        base.alpha_composite(plate)
        for w, tok, wd in zip(g, toks, widths):
            on = w["s"] - 0.03 <= lt <= w["e"] + 0.05
            im = self.text_img(tok, size, wt, self.P["blue"] if on else self.P["ink"])
            if on:
                d = ImageDraw.Draw(base)
                d.rounded_rectangle([x - 2, y + size + 8, x + f.getlength(tok) + 2, y + size + 16], 4, fill=hexc(self.P["turquoise"]))
            self.paste(base, im, (x, y))
            x += wd

    # ---------------- callouts
    def callouts(self, base, scene, t, anchors_row):
        for c in scene.get("callouts", []):
            if self.fmt not in c:
                continue
            a = self.ramp(t - scene["start"], c["in"], c["out"], 0.3)
            if a <= 0 or anchors_row is None:
                continue
            ax, ay = anchors_row[c["anchor"]][0] * self.W, anchors_row[c["anchor"]][1] * self.H
            dx, dy = c[self.fmt]
            grow = min(1.0, (t - scene["start"] - c["in"]) / 0.45)
            ex, ey = ax + dx * grow, ay + dy * grow
            layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            ink = hexc(self.P["ink"], int(255 * a))
            d.line([(ax, ay), (ex, ey)], fill=ink, width=3)
            r = 11
            d.ellipse([ax - r, ay - r, ax + r, ay + r], outline=hexc(self.P["blue"], int(255 * a)), width=4,
                      fill=(255, 255, 255, int(235 * a)))
            if grow >= 1:
                f = font(32 if self.fmt == "wide" else 38, 700)
                tw = f.getlength(c["label"])
                pad = 16
                bx = ex - tw - 2 * pad if dx < 0 else ex
                by = ey - 26
                d.rounded_rectangle([bx, by, bx + tw + 2 * pad, by + 54], 27, fill=(255, 255, 255, int(245 * a)),
                                    outline=hexc(self.P["ink"], int(255 * a)), width=2)
                d.text((bx + pad, by + 7), c["label"], font=f, fill=ink)
            base.alpha_composite(layer)

    # ---------------- titles, chapter, notice, effects
    def notice(self, base):
        txt = self.K["disclaimer"]
        size = 24 if self.fmt == "wide" else 30
        im = self.text_img(txt, size, 600, self.P["ink"])
        if self.fmt == "wide":
            self.paste(base, im, (self.W - im.width - 56, self.H - im.height - 40), 0.78)
        else:
            self.paste(base, im, ((self.W - im.width) / 2, self.H - 170), 0.78)

    def chapter(self, base, scene, t):
        lt = t - scene["start"]
        a = self.ramp(lt, 0.2, 4.6, 0.4)
        if a <= 0 or scene["id"] in ("A", "E"):
            return
        d = ImageDraw.Draw(base)
        d.rectangle([96, 86, 96 + 48, 92], fill=hexc(self.P["turquoise"], int(255 * a)))
        self.paste(base, self.text_img(scene["title"], 34, 700, self.P["ink"]), (94, 104), a)

    def title(self, base, scene, t):
        ov = scene.get("overlay")
        if not ov:
            return
        lt = t - scene["start"]
        a = self.ramp(lt, ov["in"], ov["out"], 0.5)
        if a <= 0:
            return
        y = 330
        for row in ov["title"]:
            self.paste(base, self.text_img(row, 92, 800, self.P["ink"]), (120, y), a)
            y += 104
        self.paste(base, self.text_img(ov["sub"], 34, 500, self.P["blue"]), (124, y + 22), a)

    def hook(self, base, rows, alpha=1.0):
        y = 210
        for row in rows:
            im = self.text_img(row, 84, 800, self.P["ink"])
            self.paste(base, im, ((self.W - im.width) / 2, y), alpha)
            y += 98

    def pulse(self, base, scene, t, anchors_row):
        ev = scene.get("events", {})
        if "click" in ev and anchors_row:
            lt = t - scene["start"] - ev["click"]
            if 0 <= lt <= 0.7:
                ax, ay = anchors_row["lug"][0] * self.W, anchors_row["lug"][1] * self.H
                layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
                d = ImageDraw.Draw(layer)
                for k in (0, 0.18):
                    p = lt - k
                    if 0 <= p <= 0.5:
                        r = 14 + p * 150
                        d.ellipse([ax - r, ay - r, ax + r, ay + r], outline=hexc(self.P["turquoise"], int(255 * (1 - p / 0.5))), width=5)
                base.alpha_composite(layer)
        if "pull" in ev and anchors_row:
            lt = t - scene["start"] - ev["pull"]
            a = self.ramp(lt, 0, 1.3, 0.2)
            if a > 0:
                cx, cy = anchors_row["cap"][0] * self.W, anchors_row["cap"][1] * self.H - (70 if self.fmt == "wide" else 90)
                lift = min(1, lt / 0.25) * 18 - max(0, (lt - 0.35) / 0.3) * 18
                cy -= max(0, lift)
                d = ImageDraw.Draw(base)
                col = hexc(self.P["amber"], int(255 * a))
                d.line([(cx, cy + 40), (cx, cy - 30)], fill=col, width=8)
                d.polygon([(cx - 24, cy - 22), (cx + 24, cy - 22), (cx, cy - 56)], fill=col)
                d.line([(cx - 38, cy - 70), (cx + 38, cy - 70)], fill=hexc(self.P["ink"], int(255 * a)), width=8)

    def endcard(self, base, scene, t):
        ec = scene.get("endcard")
        if not ec:
            return
        lt = t - scene["start"]
        a = max(0.0, min(1.0, (lt - ec["in"]) / 0.8))
        if a <= 0:
            return
        veil = Image.new("RGBA", base.size, hexc(self.P["paper"], int(236 * a)))
        base.alpha_composite(veil)
        y = self.H / 2 - 110
        for row in ec["text"]:
            im = self.text_img(row, 76, 800, self.P["ink"])
            self.paste(base, im, ((self.W - im.width) / 2, y), a)
            y += 92
        im = self.text_img(self.K["disclaimer"], 30, 600, self.P["blue"])
        self.paste(base, im, ((self.W - im.width) / 2, y + 40), a)


def load_anchors(d):
    p = Path(d) / "anchors.json"
    return {int(k): v for k, v in json.loads(p.read_text()).items()} if p.exists() else {}


def encode(frames_iter, n, size, out_path, fps):
    p = subprocess.Popen([FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                          f"{size[0]}x{size[1]}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "slow",
                          "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)],
                         stdin=subprocess.PIPE)
    for im in frames_iter:
        p.stdin.write(im.convert("RGB").tobytes())
    p.stdin.close()
    if p.wait():
        raise RuntimeError("ffmpeg encode failed")


def frames_for(sb, quality, scene_ids, cam):
    jobs = {(j["scene"], j["cam"]): j for j in scene_jobs(sb)}
    seq = []
    for s in sb["scenes"]:
        if s["id"] not in scene_ids:
            continue
        j = jobs[(s["id"], cam)]
        d = CACHE / "frames" / f"{j['key']}_{quality}"
        anchors = load_anchors(d)
        n = j["f1"] - j["f0"] + 1
        hold = int(round(s["hold"] * sb["fps"]))
        for i in range(n + hold):
            fi = min(i, n - 1)
            seq.append((s, d / f"f_{j['f0'] + fi:04d}.jpg", anchors.get(j["f0"] + fi), s["start"] + i / sb["fps"], i >= n))
    return seq


def compose(sb, vo, seq, fmt, opts, out_path, tail=None):
    ov = Overlay(sb, vo, fmt, opts)
    size = (ov.W, ov.H)
    total = len(seq) + (tail["frames"] if tail else 0)

    def gen():
        last = None
        for s, fp, anc, t, held in seq:
            base = Image.open(fp).convert("RGBA")
            if base.size != size:
                base = base.resize(size, Image.LANCZOS)
            if fmt == "wide":
                ov.title(base, s, t)
                ov.chapter(base, s, t)
            ov.callouts(base, s, t, anc)
            ov.pulse(base, s, t, anc)
            if fmt == "tall":
                ov.hook(base, opts["hook"])
            ov.caption(base, t, opts.get("caption_pos", "lower"))
            ov.endcard(base, s, t)
            ov.notice(base)
            last = (fp, s, t)
            yield base
        if tail:
            fp, s, t = last
            src = Image.open(fp).convert("RGBA").resize(size)
            for i in range(tail["frames"]):
                a = min(1.0, i / 12)
                im = src.filter(ImageFilter.GaussianBlur(18 * a)) if i < 14 else blurred
                if i == 13:
                    blurred = im
                im = im.copy()
                im.alpha_composite(Image.new("RGBA", size, hexc(ov.P["paper"], int(225 * a))))
                y = 700
                for row in opts["hook"]:
                    ti = ov.text_img(row, 84, 800, ov.P["ink"])
                    ov.paste(im, ti, ((ov.W - ti.width) / 2, y), a)
                    y += 98
                ti = ov.text_img(opts["tail_line"], 36, 600, ov.P["blue"])
                ov.paste(im, ti, ((ov.W - ti.width) / 2, y + 40), a)
                ov.notice(im)
                yield im

    encode(gen(), total, size, out_path, sb["fps"])
    return total


# ------------------------------------------------------------------ audio
def synth_click(sr=SR):
    t = np.arange(int(0.12 * sr)) / sr
    rng = np.random.default_rng(7)
    snap = rng.standard_normal(len(t)) * np.exp(-t / 0.0025)
    ring = (np.sin(2 * np.pi * 2300 * t) * 0.6 + np.sin(2 * np.pi * 3700 * t) * 0.35) * np.exp(-t / 0.018)
    thump = np.sin(2 * np.pi * 140 * t) * np.exp(-t / 0.03) * 0.7
    x = snap * 0.5 + ring + thump
    return x / np.abs(x).max()


def synth_swish(dur=1.1, sr=SR):
    n = int(dur * sr)
    rng = np.random.default_rng(11)
    x = rng.standard_normal(n)
    # one-pole low-pass sweep
    y, a = np.zeros(n), 0.0
    for i in range(n):
        k = 0.02 + 0.25 * math.sin(math.pi * i / n)
        a += k * (x[i] - a)
        y[i] = a
    env = np.sin(np.pi * np.arange(n) / n) ** 2
    y = y * env
    return y / np.abs(y).max()


def mix_audio(run, sb, vo, t0, t1, out_wav, extra_tail=0.0):
    n = int((t1 - t0 + extra_tail) * SR) + SR // 10
    bus = np.zeros(n, np.float32)

    def place(sig, t, gain):
        i = int((t - t0) * SR)
        if i >= n or i + len(sig) <= 0:
            return
        s0 = max(0, -i)
        i = max(i, 0)
        seg = sig[s0:s0 + n - i]
        bus[i:i + len(seg)] += seg * gain

    for lid, pl in sb["lines"].items():
        if pl["end"] >= t0 and pl["start"] <= t1:
            vf = run.dir / vo["lines"][lid]["file"]
            place(read_wav(vf), pl["start"], 0.95)
    click, swish = synth_click(), synth_swish()
    for s in sb["scenes"]:
        for ev, t in s.get("events", {}).items():
            at = s["start"] + t
            if not (t0 <= at <= t1):
                continue
            if ev == "click":
                place(click, at, 0.32)
            if ev == "swish":
                place(swish, at, 0.10)
    fade = int(0.25 * SR)
    bus[-fade:] *= np.linspace(1, 0, fade)
    write_wav(out_wav, bus)


def mux(video, wav, out):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(video), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
                    "-shortest", "-movflags", "+faststart", str(out)], check=True)


def srt(sb, vo, t0, t1, out):
    rows, k = [], 1

    def ts(x):
        x = max(0, x)
        return f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{int(x % 60):02d},{int(round((x % 1) * 1000)):03d}"
    for lid, pl in sb["lines"].items():
        if pl["start"] >= t0 and pl["end"] <= t1 + 0.01:
            rows.append(f"{k}\n{ts(pl['start'] - t0)} --> {ts(pl['end'] - t0)}\n{vo['lines'][lid]['text']}\n")
            k += 1
    Path(out).write_text("\n".join(rows))


# ------------------------------------------------------------------ step 5: master
def _sb_vo(run):
    sb = json.loads((run.dir / run.state["assets"]["storyboard"]["file"]).read_text())
    vo = json.loads((run.dir / run.name("vo-lines", 1, "json")).read_text())
    return sb, vo


def step_master(run, quality="final"):
    sb, vo = _sb_vo(run)
    key = h(sb, {k: [v["version"], v["text"]] for k, v in vo["lines"].items()}, [j["key"] for j in scene_jobs(sb)],
            quality, file_hash(__file__))
    ver, new = run.version_for("master", key)
    out = run.dir / run.name("master", ver, "mp4")
    if new or not out.exists():
        tmpv, tmpa = run.dir / ".master_video.mp4", run.dir / ".master_audio.wav"
        seq = frames_for(sb, quality, [s["id"] for s in sb["scenes"]], "wide")
        compose(sb, vo, seq, "wide", {}, tmpv)
        total = len(seq) / sb["fps"]
        mix_audio(run, sb, vo, 0, total, tmpa)
        mux(tmpv, tmpa, out)
        srt(sb, vo, 0, total, run.dir / run.name("master", ver, "srt"))
        tmpv.unlink()
        tmpa.unlink()
        run.record("master", ver, key, out, duration=round(total, 2))
    return {"files": [out.name], "version": ver, "rebuilt": new}


# ------------------------------------------------------------------ step 6: shorts
def step_shorts(run, only=None, overrides=None, quality="final"):
    sb, vo = _sb_vo(run)
    overrides = overrides or {}
    produced = []
    for s in sb["scenes"]:
        if not s["short"] or (only and s["short"] not in only):
            continue
        plan = next(p for p in sb["plan"]["scenes"] if p["id"] == s["id"])
        idx = s["short"]
        opts = {"hook": plan["hook"], "caption_pos": plan.get("caption_pos", {}).get("tall", "lower"),
                "tail_line": "From the full explainer, DEMO-001"}
        opts.update(overrides.get(str(idx), {}))
        jkey = [j["key"] for j in scene_jobs(sb) if j["scene"] == s["id"] and j["cam"] == "tall"]
        lines = {k: [v["version"], v["text"]] for k, v in vo["lines"].items() if sb["lines"][k]["scene"] == s["id"]}
        key = h(opts, lines, jkey, quality, file_hash(__file__), s)
        asset = kit()["naming"]["short_asset"].format(index=idx)
        ver, new = run.version_for(asset, key)
        out = run.dir / run.name(asset, ver, "mp4")
        if new or not out.exists():
            tmpv, tmpa = run.dir / f".s{idx}_video.mp4", run.dir / f".s{idx}_audio.wav"
            seq = frames_for(sb, quality, [s["id"]], "tall")
            tail = {"frames": int(2.0 * sb["fps"])}
            compose(sb, vo, seq, "tall", opts, tmpv, tail=tail)
            dur = len(seq) / sb["fps"]
            mix_audio(run, sb, vo, s["start"], s["start"] + dur, tmpa, extra_tail=2.0)
            mux(tmpv, tmpa, out)
            srt(sb, vo, s["start"], s["start"] + dur, run.dir / run.name(asset, ver, "srt"))
            tmpv.unlink()
            tmpa.unlink()
            run.record(asset, ver, key, out, duration=round(dur + 2.0, 2), source_scene=s["id"],
                       source_start=s["start"], caption_pos=opts["caption_pos"])
        produced.append({"short": idx, "file": out.name, "version": ver, "rebuilt": new})
    return {"files": [p["file"] for p in produced], "shorts": produced}


# ------------------------------------------------------------------ step 7: package
def step_package(run, approvals):
    sb, vo = _sb_vo(run)
    A = run.state["assets"]
    shorts = sorted(k for k in A if re.match(r"S\d\d_vertical", k))
    chapters = [f"{int(s['start'] // 60)}:{int(s['start'] % 60):02d} {s['title']}" for s in sb["scenes"]]
    thumb = run.dir / run.name("thumbnail", A["master"]["version"], "jpg")
    look = Image.open(run.dir / A["lookframes"]["file"]).convert("RGB").crop((0, 0, 1920, 1080)).convert("RGBA")
    ov = Overlay(sb, vo, "wide", {})
    y = 340
    for row in ["How a cartridge", "lock holds"]:
        ov.paste(look, ov.text_img(row, 120, 800, ov.P["ink"]), (110, y))
        y += 132
    ov.notice(look)
    look.convert("RGB").save(thumb, quality=92)
    manifest = {
        "project": run.project, "status": "Ready to upload", "written": now(),
        "title": "How a cartridge lock holds (fictional device)",
        "description": "An independent demo explainer of a fictional cartridge lock. No real product is shown.",
        "chapters": chapters,
        "files": {k: {"file": v["file"], "version": v["version"], "sha1": v["sha1"]} for k, v in A.items()
                  if k in ["master", "lookframes", "storyboard"] + shorts},
        "thumbnail": thumb.name, "approvals": approvals,
        "kit": {"id": kit()["kit_id"], "version": kit()["version"]},
        "model_api_spend_usd": 0,
    }
    mp = run.dir / f"{run.project}_package.json"
    mp.write_text(json.dumps(manifest, indent=2))
    return {"files": [mp.name, thumb.name], "status": "Ready to upload"}
