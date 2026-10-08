"""Run the real FFmpeg compositing stage on the Acme Dashboard example.

This needs no API keys. It skips the stages that call paid APIs
(vision analysis, script writing, HeyGen, Whisper timing) and feeds
VideoProcessor the files those stages would normally produce:

  screenshots/1-4.png   invented app screenshots
  output.json           the script JSON (hand-written)
  timestamps.json       when each [SHOW: n] cue starts (hand-written,
                        normally found by Whisper)
  presenter.mp4         a silent placeholder presenter clip
                        (normally the HeyGen avatar video)
  circle_mask.png       white circle on black, 448 x 448

Run from the repo root:

    python examples/run_compositing.py

Output: data/output/processed_video.mp4
"""
import asyncio
import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples" / "acme-dashboard"

# Load video_processor.py directly so the package __init__ (which pulls in
# the OpenAI client) is not imported. This stage only needs ffmpeg.
spec = importlib.util.spec_from_file_location(
    "video_processor", ROOT / "src" / "processors" / "video_processor.py")
assert spec and spec.loader
vp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vp)


async def main():
    import os
    os.chdir(ROOT)  # VideoProcessor uses paths relative to the repo root
    (ROOT / "data" / "middleware").mkdir(parents=True, exist_ok=True)
    (ROOT / "data" / "output").mkdir(parents=True, exist_ok=True)
    shutil.copy(EX / "circle_mask.png", ROOT / "data" / "middleware" / "circle_mask.png")

    out = await vp.VideoProcessor().process_video(
        input_video=str(EX / "presenter.mp4"),
        output_json=json.loads((EX / "output.json").read_text()),
        timestamps=json.loads((EX / "timestamps.json").read_text()),
        screenshots_dir=str(EX / "screenshots"),
    )
    print("wrote", out)


if __name__ == "__main__":
    asyncio.run(main())
