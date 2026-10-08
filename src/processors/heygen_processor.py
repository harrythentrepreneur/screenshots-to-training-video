"""
HeyGen Video Generation Processor
================================

This module handles the generation of initial videos using HeyGen's API.
It takes the script from output.txt and creates a video with an AI presenter.
"""

import os
import json
import logging
import aiohttp
import asyncio
from typing import Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class HeyGenProcessor:
    """
    Handles video generation using HeyGen's API.
    
    This class manages:
    1. Authentication with HeyGen API
    2. Video generation from script
    3. Video status checking and downloading
    """
    
    def __init__(self):
        """Initialize the HeyGen processor with API credentials."""
        self.api_key = os.getenv('HEYGEN_API_KEY')
        if not self.api_key:
            raise ValueError("HEYGEN_API_KEY environment variable is not set")
            
        self.base_url = "https://api.heygen.com/v2"  # Updated to v2
        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }
        logger.info("HeyGen processor initialized with API key")
        
    async def generate_video(self, script_path: str) -> str:
        """
        Generate a video using HeyGen's API.
        
        Process flow:
        1. Read script from output.txt
        2. Create video generation request
        3. Monitor video generation status
        4. Download completed video
        
        Args:
            script_path: Path to the script file (output.txt)
            
        Returns:
            str: Path to the generated video file
        """
        logger.info("Starting HeyGen video generation...")
        
        # Read script
        try:
            with open(script_path, 'r') as f:
                script_text = f.read()
            logger.info(f"Successfully read script from {script_path}")
        except Exception as e:
            logger.error(f"Failed to read script file: {str(e)}")
            raise
            
        # Create video generation request
        video_id = await self._create_video(script_text)
        if not video_id:
            raise Exception("Failed to create video")
            
        # Monitor video generation
        video_url = await self._monitor_video_status(video_id)
        if not video_url:
            raise Exception("Video generation failed")
            
        # Download video
        output_path = "data/output/generated_video.mp4"
        await self._download_video(video_url, output_path)
        
        logger.info(f"Video generation complete: {output_path}")
        return output_path
        
    async def _create_video(self, script: str) -> Optional[str]:
        """Create a video generation request using the latest API version."""
        async with aiohttp.ClientSession() as session:
            try:
                # Split script into chunks of 1500 characters
                script_chunks = [script[i:i+1500] for i in range(0, len(script), 1500)]
                logger.info(f"Split script into {len(script_chunks)} chunks")
                
                # Create video inputs for each chunk
                video_inputs = []
                for i, chunk in enumerate(script_chunks):
                    video_inputs.append({
                        "character": {
                            "type": "avatar",
                            "avatar_id": os.getenv("HEYGEN_AVATAR_ID", ""),
                            "avatar_style": "normal"
                        },
                        "voice": {
                            "type": "text",
                            "input_text": chunk,
                            "voice_id": os.getenv("HEYGEN_VOICE_ID", "")
                        },
                        "background": {
                            "type": "color",
                            "value": "#000000"  # Black background
                        }
                    })
                    logger.debug(f"Created video input for chunk {i+1}")
                
                payload = {
                    "video_inputs": video_inputs,
                    "dimension": {
                        "width": 1280,
                        "height": 720
                    }
                }
                
                logger.info(f"Sending video generation request to {self.base_url}/video/generate")
                logger.debug(f"Request payload: {json.dumps(payload, indent=2)}")
                
                response = await session.post(
                    f"{self.base_url}/video/generate",
                    headers=self.headers,
                    json=payload
                )
                
                response_text = await response.text()
                logger.debug(f"API Response: {response_text}")
                
                if response.status == 200:
                    response_json = json.loads(response_text)
                    video_id = None
                    if "data" in response_json and "video_id" in response_json["data"]:
                        video_id = response_json["data"]["video_id"]
                    if video_id:
                        logger.info(f"Successfully created video with ID: {video_id}")
                        return video_id
                    else:
                        logger.error("No video_id in successful response")
                        logger.error(f"Full response: {response_text}")
                        return None
                else:
                    logger.error(f"Failed to create video. Status: {response.status}")
                    logger.error(f"Response: {response_text}")
                    return None
            except Exception as e:
                logger.error(f"Error creating video: {str(e)}", exc_info=True)
                return None
                
    async def _monitor_video_status(self, video_id: str) -> Optional[str]:
        """Monitor video generation status and return URL when complete."""
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    logger.info(f"Checking status for video {video_id}")
                    response = await session.get(
                        f"https://api.heygen.com/v1/video_status.get",
                        headers=self.headers,
                        params={"video_id": video_id}
                    )
                    
                    response_text = await response.text()
                    logger.debug(f"Status response: {response_text}")
                    
                    if response.status == 200:
                        response_json = json.loads(response_text)
                        data = response_json.get("data", {})
                        status = data.get("status")
                        error = data.get("error")
                        video_url = data.get("video_url")
                        
                        logger.info(f"Video status: {status}")
                        if error:
                            logger.error(f"HeyGen API error: {error}")
                        
                        if status == 'completed':
                            if video_url:
                                logger.info("Video generation completed successfully. Video URL: %s", video_url)
                                return video_url
                            else:
                                logger.error("No video URL in completed response")
                                return None
                        elif status == 'failed':
                            logger.error(f"Video generation failed: {error}")
                            return None
                        else:
                            logger.info(f"Video is still processing (status: {status}). Will check again in 5 seconds...")
                            await asyncio.sleep(5)
                    else:
                        logger.error(f"Failed to check video status. Status: {response.status}")
                        logger.error(f"Response: {response_text}")
                        return None
                except Exception as e:
                    logger.error(f"Error checking video status: {str(e)}", exc_info=True)
                    return None
                    
    async def _download_video(self, video_url: str, output_path: str) -> bool:
        """Download the generated video."""
        async with aiohttp.ClientSession() as session:
            try:
                logger.info(f"Downloading video from {video_url}")
                async with session.get(video_url) as response:
                    if response.status == 200:
                        with open(output_path, 'wb') as f:
                            while True:
                                chunk = await response.content.read(8192)
                                if not chunk:
                                    break
                                f.write(chunk)
                        logger.info(f"Video downloaded successfully to {output_path}")
                        return True
                    else:
                        logger.error(f"Failed to download video. Status: {response.status}")
                        logger.error(f"Response: {await response.text()}")
                        return False
                        
            except Exception as e:
                logger.error(f"Error downloading video: {str(e)}", exc_info=True)
                return False 