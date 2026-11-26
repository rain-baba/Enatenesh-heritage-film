"""Stage: moving shots. Produces one square master clip per shot at
outputs/shots/<shot>.mp4, timed to the narration.

- render = "wan": uses the Wan 2.2 clip made on Kaggle (outputs/shots/wan/<shot>.mp4,
  see kaggle/wan_i2v.py). If that clip is missing or stale, falls back to Ken Burns.
- render = "kenburns": slow pan and zoom over the keyframe, made locally with FFmpeg.

Square masters let assembly crop both 16:9 and 9:16 from the same material.
"""
from __future__ import annotations

from .common import (OUT, duration_of, ensure_dirs, ffmpeg, file_sha, input_hash, is_fresh,
                     load_storyboard, mark_fresh)
from . import timeline

SIZE = 1080
FPS = 24
DIR = OUT / "shots"
WAN = DIR / "wan"


def wan_hash(sb: dict, shot: dict) -> str:
    """Hash of everything that determines a Wan clip. Shared with kaggle/wan_i2v.py."""
    key = OUT / "keyframes" / f"{shot['id']}.png"
    return input_hash(file_sha(key), shot["motion_prompt"], shot["seed"], sb["models"]["video"])


def kenburns(src, out, dur: float, zoom: str = "in", pan: str = "none") -> None:
    n = max(int(round(dur * FPS)), 2)
    a = 0.15
    p = f"(on/{n - 1})"
    z = f"1+{a}*{p}" if zoom == "in" else f"{1 + a}-{a}*{p}"
    cx, cy = "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"
    x = {"left": f"(iw-iw/zoom)*(1-{p})", "right": f"(iw-iw/zoom)*{p}"}.get(pan, cx)
    y = {"up": f"(ih-ih/zoom)*(1-{p})", "down": f"(ih-ih/zoom)*{p}"}.get(pan, cy)
    vf = (f"scale={SIZE * 2}:{SIZE * 2}:force_original_aspect_ratio=increase,crop={SIZE * 2}:{SIZE * 2},"
          f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={SIZE}x{SIZE}:fps={FPS},format=yuv420p")
    ffmpeg("-loop", "1", "-i", str(src), "-vf", vf, "-frames:v", str(n),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-r", str(FPS), str(out))


def fit_clip(src, out, dur: float) -> None:
    """Scale a generated clip to the square master and fit it to the shot length:
    trim the weak first 0.25 s if there is room, stretch up to 1.3x, then hold the last frame."""
    clip = duration_of(src)
    skip = 0.25 if clip - 0.25 >= dur / 1.3 else 0.0
    usable = clip - skip
    stretch = min(max(dur / usable, 1.0), 1.3)
    hold = max(dur - usable * stretch, 0)
    vf = (f"trim=start={skip},setpts=(PTS-STARTPTS)*{stretch:.4f},"
          f"scale={SIZE}:{SIZE}:force_original_aspect_ratio=increase,crop={SIZE}:{SIZE},fps={FPS},"
          f"tpad=stop_mode=clone:stop_duration={hold:.3f},format=yuv420p")
    ffmpeg("-i", str(src), "-vf", vf, "-t", f"{dur:.3f}", "-an",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-r", str(FPS), str(out))


def run(only: set[str] | None = None) -> None:
    sb = load_storyboard()
    ensure_dirs(DIR, WAN)
    times = {r["id"]: r for r in timeline.build(sb)}
    for shot in sb["shots"]:
        sid = shot["id"]
        if only and sid not in only:
            continue
        key = OUT / "keyframes" / f"{sid}.png"
        if not key.exists():
            raise SystemExit(f"Missing keyframe for {sid}; run the keyframes stage first.")
        dur = times[sid]["duration"]
        out = DIR / f"{sid}.mp4"
        kb = shot.get("kenburns", {})

        source, mode = key, "kenburns"
        if shot["render"] == "wan":
            wan = WAN / f"{sid}.mp4"
            if is_fresh(wan, wan_hash(sb, shot)):
                source, mode = wan, "wan"
            else:
                print(f"  shot {sid}: no current Wan clip, using Ken Burns fallback")

        h = input_hash(mode, file_sha(source), dur, kb, SIZE, FPS)
        if is_fresh(out, h):
            print(f"  shot {sid}: cached ({mode})")
            continue
        if mode == "wan":
            fit_clip(source, out, dur)
        else:
            kenburns(source, out, dur, kb.get("zoom", "in"), kb.get("pan", "none"))
        mark_fresh(out, h)
        print(f"  shot {sid}: {mode}, {dur:.1f}s")


if __name__ == "__main__":
    import sys
    run(set(sys.argv[1:]) or None)
