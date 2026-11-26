PY ?= python

.PHONY: setup smoke validate radio film narration keyframes shots music clean-film

setup:      ## install Python dependencies (FFmpeg must be on PATH)
	$(PY) -m pip install -r requirements.txt

smoke:      ## call each hosted provider once, log latency
	$(PY) -m pipeline.smoke_test

validate:
	$(PY) -m pipeline.run validate

radio:      ## narration over placeholder score on black (user test 1)
	$(PY) -m pipeline.run radio

film:       ## the whole pipeline: narration, keyframes, shots, music, both exports
	$(PY) -m pipeline.run film

narration keyframes shots music:
	$(PY) -m pipeline.run $@

clean-film: ## remove generated media to force a full regeneration
	rm -rf outputs/narration outputs/refs outputs/keyframes outputs/shots/*.mp4* outputs/music/score.wav* outputs/final outputs/assembly
