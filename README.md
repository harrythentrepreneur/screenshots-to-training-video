<div align="center">

# Screenshots → Training Video

### Turn a folder of screenshots into a narrated how-to video

Drop in screenshots and a short brief. AI vision reads each screen, an LLM writes the narration, and an AI presenter delivers it, with your screenshots cut in at the right moment.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776ab) ![FastAPI](https://img.shields.io/badge/api-FastAPI-009688) ![License MIT](https://img.shields.io/badge/license-MIT-black) ![Status](https://img.shields.io/badge/status-early%20prototype-orange)

</div>

---

## Why

Making a training video for a piece of software usually means you record the screen, write a script, record a voiceover, then edit the three together. Most teams already have the screenshots. This project tests how much of the rest an AI pipeline can do for you: SOPs, product demos and onboarding tutorials.

## How it works

```
data/input/
  context.txt          title · goal · details
  screenshots/1.png …  in order
        │
        ▼
1. Vision analysis      GPT-4o describes every screenshot
2. Script writing       Gemini 2.5 Pro writes intro → steps → outro,
                        tagging lines with [SHOW: n]
        │  data/middleware/output.txt · output.json · TIMING.txt
        ▼
3. Presenter video      HeyGen renders an avatar reading the script (optional)
4. Timing               Whisper transcribes the video and finds each [SHOW: n] cue
5. Compositing          FFmpeg overlays each screenshot on cue
        │
        ▼
data/output/processed_video.mp4
```

Three guide styles are built in: `TUTORIAL`, `SOP` and `PRODUCT_DEMO`.

## Quick start

```bash
git clone https://github.com/harrythentrepreneur/screenshots-to-training-video.git
cd screenshots-to-training-video
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your keys
```

Put your brief in `data/input/context.txt`. Line 1 is the title, line 2 is the goal, and the remaining lines are the details. Put screenshots in `data/input/screenshots/` as `1.png`, `2.png`, and so on.

Run it as an API:

```bash
uvicorn src.api.main:app --reload
# POST /api/generate-video   (title, goal, detailed_context, guide_type + screenshot files)
# GET  /api/health
```

Or run the steps one at a time from Python. `src/main.py` holds the orchestrator classes.

## Configuration

| Variable | Used for |
| --- | --- |
| `OPENAI_API_KEY` | Screenshot analysis (GPT-4o vision) |
| `GOOGLE_API_KEY` | Script writing (Gemini) |
| `HEYGEN_API_KEY` | Avatar presenter video (optional) |
| `HEYGEN_AVATAR_ID`, `HEYGEN_VOICE_ID` | Which HeyGen avatar and voice to use |

FFmpeg must be on your `PATH`, and Whisper downloads its model on first use.

## Status and limits

This is an **early prototype**, shared as a working reference rather than a finished tool.

- Script generation is the most complete stage.
- Video compositing expects a circular-crop mask at `data/middleware/circle_mask.png`. Supply any white-circle-on-black PNG.
- Model names are pinned to the versions used during development. Update them in `src/generators/script_generator.py` and `src/processors/image_analyzer.py`.

Next ideas: a web UI, voice-only mode (no avatar), and more output formats.

## Layout

```
src/api/main.py                 FastAPI app
src/main.py                     Orchestrators (script phase, video phase)
src/processors/image_analyzer   Vision analysis
src/generators/script_generator Gemini script writer
src/processors/heygen_processor Avatar video
src/processors/speech_processor Whisper timing
src/processors/video_processor  FFmpeg compositing
```

## License

[MIT](LICENSE) · Built by [Harry Edwards](https://github.com/harrythentrepreneur)
