"""Stage: assembly (FFmpeg, deterministic, no models).

    python -m pipeline.assemble radio   # narration + score on black, for user test 1
    python -m pipeline.assemble film    # the film, 16:9 and 9:16

Mix: narration normalised to -16 LUFS, score to music_lufs, score ducked under the
voice with sidechaincompress, then a two-pass loudnorm to -14 LUFS / -1 dBTP.
Video: square shot masters concatenated, end card appended, centre-cropped to each
aspect ratio, English subtitles burned in, H.264 + AAC at a constant 24 fps."""
from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .common import OUT, ensure_dirs, ffmpeg, load_storyboard
from . import timeline

SIZE, FPS = 1080, 24
WORK = OUT / "assembly"
FINAL = OUT / "final"
ASPECTS = {
    # name: (crop of the square master, output size, subtitle wrap, libass style)
    "16x9": ("1080:608", "1280:720", 42, "FontSize=17,MarginV=18,Outline=1.2,Shadow=0"),
    "9x16": ("608:1080", "720:1280", 26, "FontSize=11,MarginV=70,Outline=1,Shadow=0"),
}


# ---------- audio ----------

def mix_audio(sb: dict, rows: list[dict], length: float) -> Path:
    narr = [r for r in rows if r["wav"]]
    args, chains = [], []
    for i, r in enumerate(narr):
        args += ["-i", str(r["wav"])]
        ms = int(r["voice_start"] * 1000)
        chains.append(f"[{i}]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[n{i}]")
    m = len(narr)
    args += ["-i", str(OUT / "music" / "score.wav")]
    music_lufs = sb["music"].get("music_lufs", -26)
    fade_out = max(length - 4, 0)
    graph = ";".join(chains + [
        "".join(f"[n{i}]" for i in range(m)) + f"amix=inputs={m}:normalize=0,apad,atrim=0:{length:.3f},"
        "loudnorm=I=-16:TP=-2,aresample=48000,asplit=2[voice][key]",
        f"[{m}]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{length:.3f},"
        f"loudnorm=I={music_lufs}:TP=-3,aresample=48000,"
        f"afade=t=in:d=2,afade=t=out:st={fade_out:.3f}:d=4[bed]",
        "[bed][key]sidechaincompress=threshold=0.02:ratio=6:attack=300:release=1500[ducked]",
        "[voice][ducked]amix=inputs=2:normalize=0:duration=first[mix]",
    ])
    raw = WORK / "mix_raw.wav"
    ffmpeg(*args, "-filter_complex", graph, "-map", "[mix]", str(raw))
    return loudnorm_two_pass(raw, WORK / "mix.wav")


def loudnorm_two_pass(src: Path, out: Path, I=-14.0, TP=-1.0, LRA=11.0) -> Path:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src), "-af",
                        f"loudnorm=I={I}:TP={TP}:LRA={LRA}:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    stats = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
    af = (f"loudnorm=I={I}:TP={TP}:LRA={LRA}:measured_I={stats['input_i']}:measured_TP={stats['input_tp']}:"
          f"measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}:"
          f"offset={stats['target_offset']}:linear=true,aresample=48000")
    ffmpeg("-i", str(src), "-af", af, str(out))
    (WORK / "loudness.json").write_text(json.dumps(stats, indent=2))
    return out


# ---------- subtitles ----------

def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def write_srt(rows: list[dict], path: Path, width: int) -> None:
    """At most two lines per cue; long lines split into several cues timed by length."""
    cues = []
    for r in rows:
        text = r["subtitle"].strip()
        if not text or not r["voice_len"]:
            continue
        lines = textwrap.wrap(text, width)
        groups = [lines[i:i + 2] for i in range(0, len(lines), 2)]
        total_chars = sum(len(" ".join(g)) for g in groups)
        t = r["voice_start"]
        for g in groups:
            span = r["voice_len"] * len(" ".join(g)) / total_chars
            cues.append((t, t + span + 0.2, "\n".join(g)))
            t += span
    path.write_text("".join(f"{i}\n{_ts(a)} --> {_ts(b)}\n{txt}\n\n" for i, (a, b, txt) in enumerate(cues, 1)),
                    encoding="utf-8")


# ---------- picture ----------

def _font(size: int):
    for name in ("DejaVuSans.ttf", "Arial.ttf", "arial.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def end_card(sb: dict) -> Path:
    """Text kept inside the centre 560 px so it survives both crops."""
    img = Image.new("RGB", (SIZE, SIZE), "black")
    d = ImageDraw.Draw(img)
    lines = sb["end_card"]["lines"]
    fonts = [_font(40)] + [_font(26)] * (len(lines) - 1)
    heights = [d.textbbox((0, 0), l, font=f)[3] + 18 for l, f in zip(lines, fonts)]
    y = (SIZE - sum(heights)) / 2
    for l, f, h in zip(lines, fonts, heights):
        w = d.textlength(l, font=f)
        d.text(((SIZE - w) / 2, y), l, font=f, fill="white")
        y += h
    png, mp4 = WORK / "end_card.png", WORK / "end_card.mp4"
    img.save(png)
    ffmpeg("-loop", "1", "-i", str(png), "-t", str(sb["end_card"]["seconds"]), "-r", str(FPS),
           "-vf", "format=yuv420p,fade=t=in:d=0.5", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(mp4))
    return mp4


def picture(sb: dict, rows: list[dict], mode: str) -> Path:
    body = WORK / "body.mp4"
    if mode == "radio":
        ffmpeg("-f", "lavfi", "-i", f"color=black:s={SIZE}x{SIZE}:r={FPS}", "-t", f"{timeline.total(rows):.3f}",
               "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(body))
    else:
        missing = [r["id"] for r in rows if not (OUT / "shots" / f"{r['id']}.mp4").exists()]
        if missing:
            raise SystemExit(f"Missing shot clips {missing}; run the shots stage first.")
        lst = WORK / "shots.txt"
        lst.write_text("".join(f"file '{(OUT / 'shots' / (r['id'] + '.mp4')).as_posix()}'\n" for r in rows))
        ffmpeg("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(body))
    lst = WORK / "all.txt"
    lst.write_text(f"file '{body.as_posix()}'\nfile '{end_card(sb).as_posix()}'\n")
    full = WORK / "picture.mp4"
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(full))
    return full


# ---------- export ----------

def run(mode: str = "film") -> list[Path]:
    sb = load_storyboard()
    ensure_dirs(WORK, FINAL)
    rows = timeline.build(sb)
    if not any(r["wav"] for r in rows):
        raise SystemExit("No narration audio found; run the narration stage first.")
    length = timeline.total(rows) + sb["end_card"]["seconds"]
    audio = mix_audio(sb, rows, length)
    pic = picture(sb, rows, mode)
    (WORK / "timeline.json").write_text(json.dumps(
        [{k: v for k, v in r.items() if k != "wav"} for r in rows], indent=2, ensure_ascii=False))

    outs = []
    aspects = {"16x9": ASPECTS["16x9"]} if mode == "radio" else ASPECTS
    for name, (crop, scale, wrap, style) in aspects.items():
        srt = f"subs_{name}.srt"
        write_srt(rows, WORK / srt, wrap)
        out = FINAL / (f"radio_cut.mp4" if mode == "radio" else f"film_{name}.mp4")
        vf = f"crop={crop},scale={scale}:flags=lanczos,subtitles={srt}:force_style='{style}',fps={FPS},format=yuv420p"
        # run from WORK so the subtitles path has no drive letter or colon (Windows-safe)
        ffmpeg("-i", str(pic), "-i", str(audio), "-map", "0:v", "-map", "1:a", "-vf", vf,
               "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-r", str(FPS),
               "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(out.resolve()),
               cwd=WORK)
        outs.append(out)
        print(f"  assembled {out.relative_to(OUT.parent)} ({length:.1f}s)")
    return outs


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else "film")
