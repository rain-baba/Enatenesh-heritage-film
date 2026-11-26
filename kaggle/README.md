# GPU stages on Kaggle

Wan 2.2 and ACE-Step need a GPU, so they run in a Kaggle notebook. Settings:
**Accelerator: GPU T4 x2**, **Internet: on** (needs a phone-verified account).
The notebook clones this public repo, so commit and push the keyframes first.

Each script writes a zip. Download it from the notebook's Output panel, then on
your machine run `python -m pipeline.run import <zip>`. That unpacks the media and
appends the GPU calls to `runs.jsonl`.

## Notebook 1: Wan 2.2 moving shots

```python
# cell 1
!git clone -q https://github.com/<you>/<repo> /kaggle/working/repo
!pip install -q -U git+https://github.com/huggingface/diffusers transformers accelerate ftfy imageio imageio-ffmpeg
!nvidia-smi --query-gpu=name,memory.total --format=csv
```

```python
# cell 2: one shot first, to measure time and memory before batching
!cd /kaggle/working/repo && python kaggle/wan_i2v.py s04
```

```python
# cell 3: the rest of the shots marked render="wan"
!cd /kaggle/working/repo && python kaggle/wan_i2v.py
```

Download `/kaggle/working/wan_out.zip`.

If a shot fails or takes too long, set its `render` to `kenburns` in
`storyboard.json`. The local pipeline then uses a pan and zoom over the keyframe.

## Notebook 2: ACE-Step 1.5 score candidates

```python
# cell 1
!git clone -q https://github.com/<you>/<repo> /kaggle/working/repo
!git clone -q https://github.com/ace-step/ACE-Step-1.5 /kaggle/working/ACE-Step-1.5
!pip install -q uv && cd /kaggle/working/ACE-Step-1.5 && uv sync
```

```python
# cell 2: three candidates, one per seed in storyboard.music.candidate_seeds
!cd /kaggle/working/ACE-Step-1.5 && uv run python /kaggle/working/repo/kaggle/ace_step.py --acestep /kaggle/working/ACE-Step-1.5
```

Download `/kaggle/working/music_out.zip`. Listen to each candidate under the
narration, then set `music.chosen` and `music.chosen_reason` in the storyboard.
