"""
StudioX Trainer - Main Orchestrator
===================================

This module serves as the main orchestrator for the StudioX Trainer application.
It coordinates the script generation and video processing phases, managing the
flow between different components of the system.

Components:
- ScriptGenerationProcessor: Handles script generation from screenshots and context
- VideoGuideProcessor: Manages video processing with screenshots and voiceover
"""

import asyncio
import json
import os
from pathlib import Path
import logging
from typing import Dict, List, Tuple
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

# ============================================================================
# Imports
# ============================================================================
from src.processors.speech_processor import SpeechProcessor
from src.processors.video_processor import VideoProcessor
from src.processors.content_processor import ContentProcessor
from src.processors.heygen_processor import HeyGenProcessor
from src.generators.script_generator import ScriptGenerator
from src.models.base import ScriptOutput, GuideType, GuideContext, ScreenshotInfo
from src.processors.image_analyzer import ImageProcessor, OpenAIAnalyzer, process_images

# ============================================================================
# Logging Configuration
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Script Generation Phase
# ============================================================================
class ScriptGenerationProcessor:
    """
    Handles the script generation phase of the StudioX Trainer.
    
    This class manages:
    1. Input validation (screenshots and context)
    2. Screenshot analysis using AI vision
    3. Script generation with contextual content
    4. Output generation in both text and JSON formats
    """
    
    def __init__(self, guide_type: GuideType):
        """Initialize the script generation processor."""
        self.script_generator = ScriptGenerator(guide_type=guide_type)
        self.content_processor = ContentProcessor()
        self.guide_type = guide_type
        self.image_processor = None
        self.image_analyzer = None

    def _rename_screenshots_by_timestamp(self, screenshots_dir: str) -> None:
        """
        Rename screenshots based on their timestamps.
        Files are sorted by timestamp (earliest first) and renamed to N.png, (N-1).png, etc.
        where N is the total number of screenshots.
        
        Args:
            screenshots_dir: Directory containing the screenshots
        """
        logger.info("Renaming screenshots based on timestamps...")
        
        # Get all PNG files and their timestamps
        screenshot_files = []
        for filename in os.listdir(screenshots_dir):
            if filename.endswith('.png'):
                file_path = os.path.join(screenshots_dir, filename)
                # Get file creation time
                timestamp = os.path.getctime(file_path)
                screenshot_files.append((file_path, timestamp))
        
        # Sort by timestamp (earliest first)
        screenshot_files.sort(key=lambda x: x[1])
        
        # Create a temporary directory for renaming
        temp_dir = os.path.join(screenshots_dir, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # First move all files to temp directory with new names
        # Assign highest number to earliest timestamp
        total_files = len(screenshot_files)
        for i, (file_path, timestamp) in enumerate(screenshot_files):
            new_name = f"{total_files - i}.png"  # Reverse the numbering
            temp_path = os.path.join(temp_dir, new_name)
            os.rename(file_path, temp_path)
            logger.info(f"Renamed {os.path.basename(file_path)} (timestamp: {timestamp}) to {new_name}")
        
        # Then move them back to original directory
        for filename in os.listdir(temp_dir):
            src = os.path.join(temp_dir, filename)
            dst = os.path.join(screenshots_dir, filename)
            os.rename(src, dst)
        
        # Remove temp directory
        os.rmdir(temp_dir)
        logger.info("Screenshot renaming complete")

    async def validate_inputs(self, context_path: str, screenshots_dir: str) -> bool:
        """
        Validate all required inputs exist and are in correct format.
        
        Args:
            context_path: Path to context.txt
            screenshots_dir: Directory containing screenshots
            
        Returns:
            bool: True if all inputs are valid
        """
        logger.info("Validating inputs...")
        
        # Check context file exists
        if not os.path.exists(context_path):
            logger.error(f"Context file not found: {context_path}")
            return False
            
        # Check screenshots directory exists
        if not os.path.exists(screenshots_dir):
            logger.error(f"Screenshots directory not found: {screenshots_dir}")
            return False
            
        # Check screenshots exist and are in correct format
        screenshots = [f for f in os.listdir(screenshots_dir) if f.endswith('.png')]
        if not screenshots:
            logger.error(f"No PNG screenshots found in {screenshots_dir}")
            return False
            
        logger.info("Input validation successful")
        return True

    def _load_context(self, context_path: str) -> GuideContext:
        """
        Load and parse context from file.
        
        Context file format:
        - First line: Title
        - Second line: Goal
        - Remaining lines: Detailed context
        """
        with open(context_path, 'r') as f:
            content = f.read()
            
        # Parse the content into sections
        lines = content.strip().split('\n')
        title = lines[0]
        goal = lines[1]
        detailed_context = '\n'.join(lines[2:])
        
        return GuideContext(
            title=title,
            goal=goal,
            detailed_context=detailed_context,
            target_audience="General audience",  # Default value
            duration=None  # Optional
        )

    async def _analyze_screenshots(self, screenshots_dir: str, guide_context: GuideContext) -> List[ScreenshotInfo]:
        """
        Analyze screenshots using the image analyzer.
        
        This method:
        1. Initializes the image processor and analyzer
        2. Processes all images using AI vision
        3. Returns analyzed screenshots with detailed descriptions
        """
        logger.info("Analyzing screenshots...")
        
        # Initialize image processor and analyzer
        self.image_processor = ImageProcessor(screenshots_dir)
        self.image_analyzer = OpenAIAnalyzer(os.getenv('OPENAI_API_KEY'))
        
        # Process all images
        screenshots = await process_images(
            analyzer=self.image_analyzer,
            processor=self.image_processor,
            context=guide_context
        )
        
        # Sort screenshots by number
        screenshots.sort(key=lambda x: int(x.id))
        logger.info(f"Successfully analyzed {len(screenshots)} screenshots")
        
        return screenshots

    def remove_show_markers(self, text):
        # Removes [SHOW: ...] (case-insensitive, allows spaces)
        return re.sub(r'\[SHOW:.*?\]', '', text, flags=re.IGNORECASE).strip()

    async def generate_script(self, context_path: str, screenshots_dir: str) -> Tuple[str, str]:
        """
        Generate script and output files.
        
        Process flow:
        1. Load context from file
        2. Analyze screenshots using AI vision
        3. Process screenshots and analyze flow
        4. Generate script with contextual content
        5. Save outputs in both text and JSON formats
        
        Args:
            context_path: Path to context.txt
            screenshots_dir: Directory containing screenshots
            
        Returns:
            Tuple[str, str]: Paths to output.txt and output.json
        """
        logger.info("Starting script generation...")

        # Delete old outputs to prevent mismatches
        for fname in ["output.txt", "output.json"]:
            if os.path.exists(fname):
                os.remove(fname)
                logger.info(f"Deleted old {fname}")
        
        # Load context
        guide_context = self._load_context(context_path)
        
        # Analyze screenshots
        screenshots = await self._analyze_screenshots(screenshots_dir, guide_context)
        
        # Process screenshots
        processed_screenshots = await self.content_processor.process_screenshots(screenshots)
        flow_analysis = self.content_processor.analyze_flow(processed_screenshots)
        
        # Generate script
        script = await self.script_generator.generate_script(
            processed_content=processed_screenshots,
            flow_analysis=flow_analysis,
            guide_context=guide_context
        )
        
        # Create script output
        script_output = ScriptOutput(
            script=script,
            screenshot_mapping={s.id: [s.id] for s in screenshots},
            timing={s.id: 10.0 for s in screenshots},  # Default timing
            metadata=script.metadata
        )
        
        # Save output.txt
        output_txt_path = "data/middleware/output.txt"
        with open(output_txt_path, 'w') as f:
            # Convert script to text format
            text = self.remove_show_markers(script.introduction.text) + "\n\n"
            for step in script.steps:
                text += self.remove_show_markers(step.text) + "\n\n"
            text += self.remove_show_markers(script.conclusion.text)
            f.write(text)
        logger.info(f"Script text saved to {output_txt_path}")
        
        # Save output.json
        output_json_path = "data/middleware/output.json"
        with open(output_json_path, 'w') as f:
            json.dump(script_output.to_dict(), f, indent=2)
        logger.info(f"Script data saved to {output_json_path}")
        
        # Save TIMING.txt
        timing_txt_path = "data/middleware/TIMING.txt"
        with open(timing_txt_path, 'w') as f:
            f.write(f"[SHOW: {script.introduction.screenshot_id}] {self.remove_show_markers(script.introduction.text)}\n")
            for step in script.steps:
                f.write(f"[SHOW: {step.screenshot_id}] {self.remove_show_markers(step.text)}\n")
            f.write(f"[SHOW: {script.conclusion.screenshot_id}] {self.remove_show_markers(script.conclusion.text)}\n")
        logger.info(f"Timing script saved to {timing_txt_path}")
        
        return output_txt_path, output_json_path

# ============================================================================
# Video Processing Phase
# ============================================================================
class VideoGuideProcessor:
    """
    Handles the video processing phase of the StudioX Trainer.
    
    This class manages:
    1. Loading script data
    2. Processing speech to get timestamps
    3. Processing video with screenshots
    4. Generating final video output
    """
    
    def __init__(self):
        """Initialize the video guide processor."""
        self.speech_processor = SpeechProcessor()
        self.video_processor = VideoProcessor()

    async def process_video_guide(self, video_path: str, script_path: str, screenshots_dir: str) -> str:
        """
        Process a video guide with screenshots.
        
        Process flow:
        1. Load script data
        2. Process speech to get timestamps
        3. Process video with screenshots
        4. Generate final video
        
        Args:
            video_path: Path to input video
            script_path: Path to script JSON
            screenshots_dir: Directory containing screenshots
            
        Returns:
            str: Path to the processed video
        """
        # Load script data
        with open(script_path, 'r') as f:
            script_data = json.load(f)
            
        # Process speech to get timestamps
        timestamps = await self.speech_processor.process_speech(video_path)
        
        # Process video with screenshots
        output_path = await self.video_processor.process_video(
            video_path=video_path,
            screenshots_dir=screenshots_dir,
            script_data=script_data,
            timestamps=timestamps
        )
        
        return output_path

# ============================================================================
# Main Execution
# ============================================================================
async def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("main")

    # Initialize processors
    video_processor = VideoProcessor()
    speech_processor = SpeechProcessor()

    # Use existing files
    video_path = "data/output/generated_video.mp4"
    screenshots_dir = "data/input/screenshots"
    timing_txt_path = "data/middleware/TIMING.txt"

    # Process video with screenshot overlays and timing
    logger.info("Transcribing video and extracting timing...")
    transcription = speech_processor._transcribe_video(video_path)
    timing = speech_processor.extract_timing_from_timing_txt(transcription['segments'], timing_txt_path)
    logger.info("Processing video with overlays...")
    final_video_path = await video_processor.process_video(
        input_video=video_path,
        output_json=json.load(open("data/middleware/output.json")),
        timestamps=timing,
        screenshots_dir=screenshots_dir
    )
    logger.info(f"Final processed video saved at {final_video_path}")

if __name__ == "__main__":
    asyncio.run(main()) 