# Ethics: consent, licences, labelling

## Consent

The film depicts my late father (illustrated, not photoreal) and, as a child, me. No real
person's voice is used or cloned: the narration is a stock Gemini TTS voice.

| Person | Shown or voiced | Consent from | Form | Date | Scope |
|---|---|---|---|---|---|
| My father (deceased) | Shown, illustrated likeness | Helen and Hana, my sisters (his daughters) | Written message (kept privately) | 2026-11-26 | An AI-generated illustrated film of him, the narration script in `storyboard.json`, public posting with an AI label |
| Me (Tihitna), as a child | Shown, illustrated | Myself | n/a | 2026-11-26 | Same |
| Helen, Hana, Beza | Not shown; user-test feedback only | Each of them | Verbal / message | 2026-11-26 | Quoting their feedback in DESIGN.md by first name |

Consent was recorded before any image of him was generated. The words in the narration are my
own account; my sisters read the narration script before it was published.

## Private data

Free endpoints may use inputs for training. Prompts describe appearance and scenes only: no
surnames, places of residence, dates or other identifying family details are sent to any model.

## Licences

| Component | Licence / terms | Output use |
|---|---|---|
| FLUX.2 [klein] 4B (Cloudflare Workers AI) | Apache 2.0 weights; Cloudflare terms for the hosted API | Usable |
| Wan 2.2 TI2V-5B | Apache 2.0 | Usable |
| ACE-Step 1.5 | MIT (code); trained on licensed, royalty-free and synthetic data | Usable, including commercially |
| Gemini TTS / Gemini Flash (free tier) | Google Gemini API terms; free-tier inputs may be used to improve products | Usable |
| FFmpeg | LGPL/GPL tool; no claim on outputs | Usable |
| DejaVu Sans (end card) | Bitstream Vera / DejaVu licence | Usable |

## Labelling

- The film ends with an end card stating it was made with AI and naming every model used.
- The post is published with the platform's AI-content label switched on.
- No watermark or provenance metadata from any model output is stripped.
- Style is described in words (gouache, warm, grainy). No living artist is named in any prompt.
