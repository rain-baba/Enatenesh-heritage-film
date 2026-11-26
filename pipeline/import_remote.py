"""Import outputs made on Kaggle or Colab.

The notebooks write a zip whose paths mirror this repo (outputs/shots/wan/...,
outputs/music/candidates/...) plus remote_runs.jsonl with one line per model call.
This unpacks the media and appends the call log to runs.jsonl, skipping ids
already present so importing twice is harmless."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from .common import ROOT, RUNS


def run(zip_path: str) -> None:
    seen = set()
    if RUNS.exists():
        seen = {json.loads(l)["id"] for l in RUNS.read_text(encoding="utf-8").splitlines() if l.strip()}
    added = files = 0
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if name.endswith("remote_runs.jsonl"):
                with open(RUNS, "a", encoding="utf-8") as out:
                    for line in z.read(name).decode("utf-8").splitlines():
                        if line.strip() and json.loads(line)["id"] not in seen:
                            out.write(line.rstrip() + "\n")
                            added += 1
            elif name.startswith("outputs/") and not name.endswith("/"):
                dest = ROOT / name
                if ROOT.resolve() not in dest.resolve().parents:
                    raise SystemExit(f"refusing to write outside the repo: {name}")
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(name))
                files += 1
    print(f"  imported {files} file(s) and {added} log line(s) from {Path(zip_path).name}")
