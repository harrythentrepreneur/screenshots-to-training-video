import whisper
import logging
from typing import Dict, List
import json
from pathlib import Path
import string
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SpeechProcessor:
    def __init__(self):
        """Initialize the speech processor with Whisper model."""
        logger.info("Loading Whisper model...")
        self.whisper_model = whisper.load_model("base")
        logger.info("Whisper model loaded successfully")

    async def process_video(self, video_path: str, output_json: dict) -> Dict[str, float]:
        """
        Process video and return timestamp mapping for [SHOW: X] markers
        
        Args:
            video_path: Path to the MP4 video
            output_json: The output.json containing script and timing information
            
        Returns:
            Dict mapping screenshot IDs to timestamps
        """
        logger.info(f"Processing video: {video_path}")
        
        # 1. Get transcription with word-level timestamps
        transcription = self._transcribe_video(video_path)
        
        # 2. Get our original script from output.json
        original_script = self._extract_script_text(output_json)
        
        # 3. Create mapping of screenshot IDs to their positions in script
        screenshot_positions = self._map_screenshots_to_script(output_json)
        
        # 4. Align transcribed text with original script
        timestamps = self._align_with_timestamps(
            transcription['segments'],
            original_script,
            screenshot_positions
        )
        
        logger.info(f"Found timestamps for {len(timestamps)} screenshots")
        return timestamps

    def _transcribe_video(self, video_path: str) -> Dict:
        """Transcribe video using Whisper API with word timestamps."""
        logger.info("Starting video transcription...")
        result = self.whisper_model.transcribe(
            video_path,
            word_timestamps=True,
            language="en"
        )
        logger.info("Transcription completed")
        return result

    def _extract_script_text(self, output_json: dict) -> str:
        """Extract the full script text from output.json."""
        script_parts = []
        
        # Add introduction
        if output_json['script']['introduction']:
            script_parts.append(output_json['script']['introduction']['text'])
        
        # Add steps
        for step in output_json['script']['steps']:
            script_parts.append(step['text'])
        
        # Add conclusion
        if output_json['script']['conclusion']:
            script_parts.append(output_json['script']['conclusion']['text'])
        
        return ' '.join(script_parts)

    def _map_screenshots_to_script(self, output_json: dict) -> Dict[str, int]:
        """Map each screenshot ID to its position in the script."""
        positions = {}
        current_pos = 0
        
        # Process introduction
        if output_json['script']['introduction']:
            text = output_json['script']['introduction']['text']
            if '[SHOW:' in text:
                screenshot_id = self._extract_screenshot_id(text)
                positions[screenshot_id] = current_pos
            current_pos += len(text.split())
        
        # Process steps
        for step in output_json['script']['steps']:
            text = step['text']
            if '[SHOW:' in text:
                screenshot_id = self._extract_screenshot_id(text)
                positions[screenshot_id] = current_pos
            current_pos += len(text.split())
        
        return positions

    def _extract_screenshot_id(self, text: str) -> str:
        """Extract screenshot ID from [SHOW: X] marker."""
        match = re.search(r'\[SHOW: (.*?)\]', text)
        return match.group(1) if match else None

    def _align_with_timestamps(self, 
                             segments: List[Dict],
                             original_script: str,
                             screenshot_positions: Dict[str, int]) -> Dict[str, float]:
        """Align transcribed text with original script to find timestamps."""
        timestamps = {}
        
        # Convert segments to word-level timestamps
        words_with_timestamps = []
        for segment in segments:
            for word in segment['words']:
                words_with_timestamps.append({
                    'word': word['word'],
                    'start': word['start'],
                    'end': word['end']
                })
        
        # Find timestamps for each screenshot
        for screenshot_id, position in screenshot_positions.items():
            # Find the corresponding word in transcribed text
            if position < len(words_with_timestamps):
                word = words_with_timestamps[position]
                timestamps[screenshot_id] = word['start']
        
        return timestamps

    def extract_timing_from_timing_txt(self, segments: List[Dict], timing_txt_path: str) -> Dict[str, float]:
        """
        Extract timestamps for each screenshot from the timing file and transcript.
        
        Args:
            segments: List of transcript segments with word timestamps
            timing_txt_path: Path to TIMING.txt file
            
        Returns:
            Dict mapping screenshot IDs to their timestamps
        """
        logger.info("Extracting timestamps from timing file and transcript...")
        
        # Read timing file
        with open(timing_txt_path, 'r') as f:
            timing_lines = f.readlines()
        
        # Extract all words with timestamps from transcript
        words_with_timestamps = []
        for segment in segments:
            for word in segment['words']:
                words_with_timestamps.append({
                    'word': word['word'].strip().lower(),
                    'start': word['start'],
                    'end': word['end']
                })
        
        # Process each timing line
        timestamps = {}
        for line in timing_lines:
            if '[SHOW:' not in line:
                continue
                
            # Extract screenshot ID and text
            match = re.search(r'\[SHOW: (\d+)\](.*)', line)
            if not match:
                continue
                
            screenshot_id = match.group(1)
            text = match.group(2).strip()
            
            # Get first few words after [SHOW: X] for matching
            words_to_match = text.split()[:5]  # Use first 5 words for matching
            logger.info(f"\nProcessing screenshot {screenshot_id}")
            logger.info(f"Text to match: {' '.join(words_to_match)}")
            
            # Find the best matching position in transcript
            best_match = None
            best_score = 0
            
            for i in range(len(words_with_timestamps) - len(words_to_match)):
                window = words_with_timestamps[i:i + len(words_to_match)]
                window_text = ' '.join(w['word'] for w in window)
                
                # Calculate match score (number of matching words)
                score = sum(1 for a, b in zip(words_to_match, window) if a.lower() == b['word'].lower())
                
                if score > best_score:
                    best_score = score
                    best_match = window[0]['start']  # Use start time of first matching word
            
            if best_match is not None:
                timestamps[screenshot_id] = best_match
                logger.info(f"Found timestamp for screenshot {screenshot_id}: {best_match:.2f}s (match score: {best_score}/{len(words_to_match)})")
            else:
                logger.warning(f"Could not find timestamp for screenshot {screenshot_id}")
                # Use the last known timestamp or 0 if none exists
                last_timestamp = max(timestamps.values()) if timestamps else 0
                timestamps[screenshot_id] = last_timestamp + 1.0  # Add 1 second buffer
        
        # Sort timestamps by screenshot ID to ensure correct order
        sorted_timestamps = dict(sorted(timestamps.items(), key=lambda x: int(x[0])))
        
        # Log final timing sequence
        logger.info("\nFinal timing sequence:")
        for screenshot_id, timestamp in sorted_timestamps.items():
            logger.info(f"Screenshot {screenshot_id}: {timestamp:.2f}s")
        
        return sorted_timestamps 