import asyncio
import os
import json
from pathlib import Path
from src.processors.speech_processor import SpeechProcessor

async def test_speech_processing():
    # Initialize processor
    processor = SpeechProcessor()
    
    # Load output.json
    output_path = Path("output.json")
    with open(output_path) as f:
        output_json = json.load(f)
    
    # Process video
    video_path = os.environ.get("EXAMPLE_VIDEO", "example.mp4")
    print(f"\nProcessing video: {video_path}")
    timestamps = await processor.process_video(video_path, output_json)
    
    # Print results
    print("\nScreenshot Timestamps:")
    for screenshot_id, timestamp in timestamps.items():
        print(f"{screenshot_id}: {timestamp:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(test_speech_processing()) 