import os
import json
import asyncio
import aiohttp
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv
from PIL import Image
import openai
from src.models.base import GuideContext, ScreenshotInfo

# Load environment variables
load_dotenv()

# Suppress gRPC warnings
os.environ['GRPC_ENABLE_FORK_SUPPORT'] = '0'

class GuideContext:
    def __init__(self, title: str, goal: str, target_audience: str, detailed_context: str, total_steps: Optional[int] = None):
        self.title = title
        self.goal = goal
        self.target_audience = target_audience
        self.detailed_context = detailed_context
        self.total_steps = total_steps

    def validate(self) -> bool:
        return bool(self.title and self.goal and self.target_audience and self.detailed_context)

class ImageProcessor:
    def __init__(self, input_dir: str):
        self.input_dir = Path(input_dir)
        self.supported_formats = {'.png', '.jpg', '.jpeg', '.tif', '.tiff'}

    def get_image_files(self) -> List[Path]:
        """Get all supported image files from the input directory."""
        return [
            f for f in self.input_dir.glob('*')
            if f.suffix.lower() in self.supported_formats
        ]

    def extract_step_number(self, filename: str) -> str:
        """Extract step number from filename."""
        base_name = Path(filename).stem
        import re
        match = re.search(r'\d+', base_name)
        return match.group(0) if match else ""

    def prepare_image(self, image_path: Path) -> str:
        """Convert image to base64 string."""
        with Image.open(image_path) as img:
            import base64
            from io import BytesIO
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode()

class OpenAIAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = openai.OpenAI(api_key=api_key)

    async def analyze_image(self, session: aiohttp.ClientSession, image_path: Path, context: GuideContext, processor: ImageProcessor) -> Dict[str, str]:
        """Analyze image using OpenAI's Vision API."""
        try:
            img_str = processor.prepare_image(image_path)
            step_number = processor.extract_step_number(image_path.name)
            
            if not step_number:
                print(f"Warning: Could not extract step number from {image_path.name}")
                return None

            print(f"Processing image {image_path.name}...")
            
            response = await session.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {
                            "role": "system",
                            "content": f"You are analyzing a screenshot from a StudioX Trainer guide. Guide Title: {context.title}, Goal: {context.goal}, Context: {context.detailed_context}"
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Please describe what is shown in this screenshot in relation to the StudioX Trainer context. Focus on describing the current state, visible elements, and what this step represents in the overall process. Keep the description clear and concise."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{img_str}"
                                    }
                                }
                            ]
                        }
                    ],
                    "max_tokens": 500
                }
            )
            
            result = await response.json()
            description = result['choices'][0]['message']['content']
            print(f"Completed step {step_number}")
            
            return {
                "screenshot_id": step_number,
                "description": description
            }
        except Exception as e:
            print(f"Error analyzing image {image_path}: {str(e)}")
            return None

class OutputGenerator:
    def __init__(self, output_file: str):
        self.output_file = output_file
        # Create text output file path by replacing .json with .txt
        self.text_output_file = output_file.replace('.json', '.txt')

    def generate_json(self, steps: List[Dict[str, str]]) -> None:
        """Generate JSON output file."""
        with open(self.output_file, 'w') as f:
            json.dump(steps, f, indent=2)
            
    def generate_text(self, steps: List[Dict[str, str]]) -> None:
        """Generate text-only output file with just the script text."""
        with open(self.text_output_file, 'w') as f:
            for step in steps:
                # Write just the description with the show cue
                f.write(f"{step['description']} [SHOW: {step['screenshot_id']}]\n\n")

async def process_images(analyzer: OpenAIAnalyzer, processor: ImageProcessor, context: GuideContext) -> List[ScreenshotInfo]:
    """Process all images concurrently."""
    async with aiohttp.ClientSession() as session:
        tasks = []
        for image_path in processor.get_image_files():
            task = analyzer.analyze_image(session, image_path, context, processor)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # Convert results to ScreenshotInfo objects
        screenshots = []
        for result in results:
            if result is not None:
                screenshots.append(ScreenshotInfo(
                    id=result['screenshot_id'],
                    description=result['description'],
                    context=result['description'],  # Using description as context for now
                    file_path=str(processor.input_dir / f"{result['screenshot_id']}.png")
                ))
        
        return screenshots

async def main():
    # Initialize components with static values
    context = GuideContext(
        title="StudioX Trainer Guide",
        goal="Create AI-powered video training guides",
        target_audience="Software trainers and content creators",
        detailed_context="""
        StudioX Trainer is a powerful tool that automates the creation of video training guides.
        It uses AI to analyze screenshots and generate engaging video content.
        The process involves uploading screenshots, adding descriptions, and letting the AI create the video.
        """,
        total_steps=None
    )

    if not context.validate():
        print("Error: Invalid guide context")
        return

    processor = ImageProcessor(os.getenv('INPUT_DIRECTORY'))
    analyzer = OpenAIAnalyzer(os.getenv('OPENAI_API_KEY'))
    output_gen = OutputGenerator(os.getenv('OUTPUT_FILE'))

    # Process all images concurrently
    screenshots = await process_images(analyzer, processor, context)

    # Sort screenshots by number
    screenshots.sort(key=lambda x: int(x.id))
    
    # Convert to dictionary format for output
    steps = [{
        "screenshot_id": s.id,
        "description": s.description,
        "context": s.context
    } for s in screenshots]
    
    # Generate both JSON and text outputs
    output_gen.generate_json(steps)
    output_gen.generate_text(steps)
    print(f"Analysis complete. Output saved to {os.getenv('OUTPUT_FILE')} and {output_gen.text_output_file}")

if __name__ == "__main__":
    asyncio.run(main()) 