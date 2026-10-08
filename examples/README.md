# Examples

## acme-dashboard

A made-up app called Acme Dashboard, used to show the video compositing stage without any API keys. No real product, person or account appears here.

| File | What it is | Normally made by |
| --- | --- | --- |
| `context.txt` | The brief: title, goal, details | You |
| `screenshots/1.png` … `4.png` | Four app screens, 1600 × 1000 | You |
| `output.json` | Script with `[SHOW: n]` tags | Gemini (stage 2), hand-written here |
| `TIMING.txt` | One line per screenshot cue | Gemini (stage 2), hand-written here |
| `presenter.mp4` | 14 s silent placeholder presenter, 1280 × 720 | HeyGen (stage 3) |
| `timestamps.json` | Second at which each cue starts | Whisper (stage 4), hand-written here |
| `circle_mask.png` | White circle on black, 448 × 448 | You |
| `source/acme.html` | HTML used to draw the four screens (`?screen=1..4`) | |
| `source/presenter.html` | SVG presenter, one frame per `?t=0..1` | |

Run the real compositing stage from the repo root (needs `ffmpeg` on your `PATH`):

```bash
python examples/run_compositing.py
# -> data/output/processed_video.mp4  (1920 x 1080, 14 s)
```

The script calls `VideoProcessor.process_video()` from `src/processors/video_processor.py` unchanged. `assets/demo.gif` in this repo is a straight GIF conversion of that output:

```bash
ffmpeg -i data/output/processed_video.mp4 \
  -vf "fps=10,scale=1000:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=256[p];[b][p]paletteuse=dither=none" \
  assets/demo.gif
```
