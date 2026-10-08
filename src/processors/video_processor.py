import logging
import subprocess
from pathlib import Path
from typing import Dict, List
import json
import shlex

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self):
        """Initialize the video processor."""
        self.resolution = (1920, 1080)
        self.screenshot_scale = 0.9  # 90% of width
        self.person_size = (320, 320)  # Size for the circular person overlay
        self.person_margin = 40  # Margin from bottom-right corner

    def _get_video_duration(self, video_path: str) -> float:
        """Get the duration of a video file in seconds."""
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get video duration: {e}")
            raise

    async def process_video(self,
                          input_video: str,
                          output_json: dict,
                          timestamps: Dict[str, float],
                          screenshots_dir: str) -> str:
        """
        Process video with screenshots and timing.
        
        Args:
            input_video: Path to input video
            output_json: Script and timing data
            timestamps: Screenshot timestamps from speech processing
            screenshots_dir: Directory containing screenshots
            
        Returns:
            Path to processed video
        """
        logger.info("Starting video processing...")
        
        # Create screenshot mapping from script data
        screenshot_mapping = {}
        # Add introduction screenshot
        if 'introduction' in output_json and 'screenshot_id' in output_json['introduction']:
            screenshot_mapping[output_json['introduction']['screenshot_id']] = [output_json['introduction']['screenshot_id']]
        
        # Add step screenshots
        if 'steps' in output_json:
            for step in output_json['steps']:
                if 'screenshot_id' in step:
                    screenshot_mapping[step['screenshot_id']] = [step['screenshot_id']]
        
        # Add conclusion screenshot
        if 'conclusion' in output_json and 'screenshot_id' in output_json['conclusion']:
            screenshot_mapping[output_json['conclusion']['screenshot_id']] = [output_json['conclusion']['screenshot_id']]
        
        # 1. Prepare screenshots
        screenshot_paths = self._prepare_screenshots(
            screenshots_dir,
            screenshot_mapping
        )
        
        # 2. Generate FFmpeg command
        ffmpeg_cmd = self._generate_ffmpeg_command(
            input_video,
            screenshot_paths,
            timestamps
        )
        
        # 3. Execute FFmpeg
        output_path = self._execute_ffmpeg(ffmpeg_cmd, input_video)
        
        logger.info("Video processing complete")
        return output_path

    def _prepare_screenshots(self,
                           screenshots_dir: str,
                           screenshot_mapping: Dict[str, List[str]]) -> Dict[str, str]:
        """Prepare screenshot paths for FFmpeg."""
        screenshot_paths = {}
        for screenshot_id in screenshot_mapping.keys():
            # Look for screenshot in directory
            screenshot_path = Path(screenshots_dir) / f"{screenshot_id}.png"
            if screenshot_path.exists():
                screenshot_paths[screenshot_id] = str(screenshot_path)
            else:
                logger.warning(f"Screenshot not found: {screenshot_path}")
        
        return screenshot_paths

    def _generate_ffmpeg_command(self,
                               input_video: str,
                               screenshot_paths: Dict[str, str],
                               timestamps: Dict[str, float]) -> List[str]:
        """Generate FFmpeg command for video processing."""
        # Get input video duration
        video_duration = self._get_video_duration(input_video)
        logger.info(f"Input video duration: {video_duration} seconds")
        
        # Base command
        cmd = [
            'ffmpeg',
            '-i', input_video,  # Main video
            '-i', 'data/middleware/circle_mask.png',  # Mask for circular crop
        ]
        
        # Add screenshot inputs (start from index 2)
        for path in screenshot_paths.values():
            cmd.extend(['-i', path])
        
        # Build filter complex
        filters = []
        
        # Create white background with duration
        filters.append(f'color=c=white:s={self.resolution[0]}x{self.resolution[1]}:d={video_duration}[bg]')
        
        # Increase avatar overlay size by 40%
        new_size = int(self.person_size[0] * 1.4)
        # Crop and scale avatar, then apply mask
        filters.extend([
            f"[0:v]scale='if(gt(iw,ih),-1,{new_size})':'if(gt(iw,ih),{new_size},-1)':force_original_aspect_ratio=increase,crop={new_size}:{new_size},format=rgba[avatar_sq]",
            f"[avatar_sq][1:v]alphamerge[person_circle]"
        ])
        
        # Process screenshots
        sorted_screenshots = sorted(
            [(id, path, timestamps.get(id, 0)) for id, path in screenshot_paths.items()],
            key=lambda x: x[2]
        )
        
        # Scale all screenshots first
        for i, (screenshot_id, _, _) in enumerate(sorted_screenshots, start=2):
            filters.append(f'[{i}:v]scale=\'min({self.resolution[0]},iw*0.85)\':\'min({self.resolution[1]},ih*0.85)\':force_original_aspect_ratio=decrease[scaled_{i}]')
        
        # Start with white background
        filters.append('[bg]copy[base]')
        
        # Add each screenshot with enable/disable logic
        for i, (screenshot_id, _, timestamp) in enumerate(sorted_screenshots):
            input_idx = i + 2  # Account for video and mask inputs
            next_timestamp = timestamps.get(sorted_screenshots[i+1][0], video_duration) if i < len(sorted_screenshots)-1 else video_duration
            
            # Add screenshot with enable/disable based on timestamp
            filters.append(
                f'[base][scaled_{input_idx}]overlay=(W-w)/2:(H-h)/2:enable=\'gte(t,{timestamp})*lt(t,{next_timestamp})\'[base]'
            )
        
        # Add person overlay last
        filters.append(
            f'[base][person_circle]overlay=W-w-{self.person_margin}:H-h-{self.person_margin}[out]'
        )
        
        # Join filters with semicolons and escape properly
        filter_complex = ';'.join(filters)
        logger.info(f"Filter complex: {filter_complex}")
        
        # Add map for output
        cmd.extend(['-filter_complex', filter_complex])
        # Log the filter_complex string for debugging
        logger.info(f"FFmpeg filter_complex: {filter_complex}")
        cmd.extend(['-map', '[out]'])
        cmd.extend(['-map', '0:a'])  # Keep original audio
        
        # Set output duration to match input video
        cmd.extend(['-t', str(video_duration)])
        
        # Output path
        output_path = str(Path('data/output/processed_video.mp4'))
        cmd.extend(['-y', output_path])
        
        return cmd

    def _execute_ffmpeg(self, cmd: List[str], input_video: str) -> str:
        """Execute FFmpeg command."""
        logger.info("Executing FFmpeg command...")
        try:
            # Execute command without shell=True to avoid escaping issues
            subprocess.run(cmd, check=True)
            output_path = str(Path('data/output/processed_video.mp4'))
            logger.info(f"FFmpeg command executed successfully. Output: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg command failed: {e}")
            raise 