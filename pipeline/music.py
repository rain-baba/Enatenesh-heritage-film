"""Stage: music. ACE-Step 1.5 runs on Kaggle (kaggle/ace_step.py) and writes
candidates to outputs/music/candidates/seed_<seed>.wav. This stage selects the
candidate named in storyboard.music.chosen and writes outputs/music/score.wav.

If no candidate is chosen yet, it writes a quiet synthetic placeholder pad
(no model involved), which is what the radio cut uses."""
from __future__ import annotations

import shutil

from .common import OUT, ensure_dirs, ffmpeg, file_sha, input_hash, is_fresh, load_storyboard, mark_fresh

DIR = OUT / "music"
CANDS = DIR / "candidates"


def placeholder(out, seconds: int = 150) -> None:
    """A minor pad: three sines with slow tremolo, low-passed. Clearly a placeholder."""
    tones = [220.0, 261.63, 329.63, 110.0]
    inputs = []
    for f in tones:
        inputs += ["-f", "lavfi", "-i", f"sine=frequency={f}:duration={seconds}"]
    mix = "".join(f"[{i}]" for i in range(len(tones)))
    af = (f"{mix}amix=inputs={len(tones)},tremolo=f=0.15:d=0.5,lowpass=f=900,"
          f"afade=t=in:d=3,volume=0.6,aformat=sample_rates=48000:channel_layouts=stereo")
    ffmpeg(*inputs, "-filter_complex", af, str(out))


def run() -> None:
    sb = load_storyboard()
    ensure_dirs(DIR, CANDS)
    m = sb["music"]
    out = DIR / "score.wav"
    if m["chosen"] is None:
        h = input_hash("placeholder")
        if not is_fresh(out, h):
            placeholder(out)
            mark_fresh(out, h)
        print("  music: placeholder pad (no candidate chosen yet)")
        return
    src = CANDS / f"seed_{m['chosen']}.wav"
    if not src.exists():
        raise SystemExit(f"Chosen candidate {src.name} not found. Import the Kaggle output first.")
    h = input_hash("chosen", file_sha(src))
    if not is_fresh(out, h):
        shutil.copyfile(src, out)
        mark_fresh(out, h)
    print(f"  music: using candidate seed {m['chosen']}")


if __name__ == "__main__":
    run()
