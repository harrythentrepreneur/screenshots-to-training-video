from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import shutil
from pathlib import Path
import asyncio
import logging
import json

from src.main import ScriptGenerationProcessor, VideoGuideProcessor
from src.models.base import GuideType
from src.processors.heygen_processor import HeyGenProcessor
from src.processors.video_processor import VideoProcessor
from src.processors.speech_processor import SpeechProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="StudioX Trainer API",
    description="API for generating training videos from screenshots and context",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Add your Next.js frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create necessary directories
for dir_path in ["data/input/screenshots", "data/middleware", "data/output"]:
    os.makedirs(dir_path, exist_ok=True)

class VideoGenerationRequest(BaseModel):
    title: str
    goal: str
    detailed_context: str
    guide_type: str = "TUTORIAL"  # Default to TUTORIAL

@app.post("/api/generate-video")
async def generate_video(
    context: VideoGenerationRequest,
    screenshots: List[UploadFile] = File(...)
):
    """
    Generate a training video from screenshots and context.
    
    Args:
        context: Video generation context (title, goal, detailed context)
        screenshots: List of screenshot files (PNG)
    
    Returns:
        Path to the generated video
    """
    try:
        # Save context
        context_path = "data/input/context.txt"
        with open(context_path, "w") as f:
            f.write(f"{context.title}\n{context.goal}\n{context.detailed_context}")

        # Save screenshots
        screenshots_dir = "data/input/screenshots"
        for screenshot in screenshots:
            if not screenshot.filename.endswith('.png'):
                raise HTTPException(status_code=400, detail="Only PNG files are allowed")
            
            # Save with original filename to preserve order
            file_path = os.path.join(screenshots_dir, screenshot.filename)
            with open(file_path, "wb") as f:
                shutil.copyfileobj(screenshot.file, f)

        # Initialize processors
        guide_type = GuideType[context.guide_type]
        script_processor = ScriptGenerationProcessor(guide_type)
        heygen_processor = HeyGenProcessor()
        video_processor = VideoProcessor()
        speech_processor = SpeechProcessor()

        # 1. Rename screenshots by timestamp
        script_processor._rename_screenshots_by_timestamp(screenshots_dir)

        # 2. Generate script
        logger.info("Loading context and screenshots...")
        context_obj = script_processor._load_context(context_path)
        screenshots = await script_processor._analyze_screenshots(screenshots_dir, context_obj)

        logger.info("Processing screenshots...")
        processed_content = await script_processor.content_processor.process_screenshots(screenshots)
        flow_analysis = script_processor.content_processor.analyze_flow(processed_content)

        logger.info("Generating script...")
        script = await script_processor.script_generator.generate_script(
            processed_content=processed_content,
            flow_analysis=flow_analysis,
            guide_context=context_obj
        )

        # Save outputs
        output_txt_path = "data/middleware/output.txt"
        output_json_path = "data/middleware/output.json"
        timing_txt_path = "data/middleware/TIMING.txt"

        # Save script text
        with open(output_txt_path, "w") as f:
            text = script_processor.remove_show_markers(script.introduction.text) + "\n\n"
            for step in script.steps:
                text += script_processor.remove_show_markers(step.text) + "\n\n"
            text += script_processor.remove_show_markers(script.conclusion.text)
            f.write(text)

        # Save script JSON
        with open(output_json_path, "w") as f:
            json.dump(script.to_dict(), f, indent=2)

        # Generate and save TIMING.txt
        with open(timing_txt_path, "w") as f:
            f.write(f"[SHOW: {script.introduction.screenshot_id}] {script_processor.remove_show_markers(script.introduction.text)}\n")
            for step in script.steps:
                f.write(f"[SHOW: {step.screenshot_id}] {script_processor.remove_show_markers(step.text)}\n")
            f.write(f"[SHOW: {script.conclusion.screenshot_id}] {script_processor.remove_show_markers(script.conclusion.text)}\n")

        # 3. Generate video using HeyGen
        logger.info("Generating video using HeyGen...")
        video_path = await heygen_processor.generate_video(output_txt_path)

        # 4. Process video with screenshot overlays and timing
        logger.info("Transcribing video and extracting timing...")
        transcription = speech_processor._transcribe_video(video_path)
        timing = speech_processor.extract_timing_from_timing_txt(transcription['segments'], timing_txt_path)
        
        logger.info("Processing video with overlays...")
        final_video_path = video_processor.process_video(
            video_path=video_path,
            output_json=output_json_path,
            timing_txt_path=timing_txt_path,
            screenshots_dir=screenshots_dir,
            mask_path="data/middleware/circle_mask.png"
        )

        # Return the video file
        return FileResponse(
            final_video_path,
            media_type="video/mp4",
            filename="training_video.mp4"
        )

    except Exception as e:
        logger.error(f"Error generating video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"} 