from typing import List, Dict
from src.models.base import Script, ScriptSection, GuideType, GuideContext
from src.processors.content_processor import ProcessedScreenshot, FlowAnalysis
import openai
import google.generativeai as genai
from dataclasses import dataclass
import os
import logging
import time
import json
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Suppress gRPC warnings
os.environ['GRPC_ENABLE_FORK_SUPPORT'] = '0'
logging.getLogger('absl').setLevel(logging.ERROR)

@dataclass
class TemplateConfig:
    introduction_template: str
    step_template: str
    transition_template: str
    conclusion_template: str

class ScriptGenerator:
    def __init__(self, guide_type: GuideType):
        """Initialize the script generator with the specified guide type."""
        self.guide_type = guide_type
        self.templates = self._load_templates()
        
        # Configure Gemini with API key
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")
            
        genai.configure(api_key=api_key)
        self.gemini_model = genai.GenerativeModel('gemini-2.5-pro-preview-03-25')
        
        # Configure logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _load_templates(self) -> TemplateConfig:
        """Load templates based on guide type."""
        logger.info(f"Loading templates for {self.guide_type.value}")
        if self.guide_type == GuideType.PRODUCT_DEMO:
            return TemplateConfig(
                introduction_template="Welcome to this demonstration of {title}. Today, we'll explore {goal}.",
                step_template="Let's look at {description}",
                transition_template="Moving on to the next step, {next_description}",
                conclusion_template="That concludes our demonstration of {title}. Thank you for watching!"
            )
        elif self.guide_type == GuideType.SOP:
            return TemplateConfig(
                introduction_template="This standard operating procedure will guide you through {goal}.",
                step_template="Step {step_number}: {description}",
                transition_template="After completing this step, proceed to {next_description}",
                conclusion_template="You have now completed all steps in this procedure."
            )
        else:  # TUTORIAL
            return TemplateConfig(
                introduction_template="In this tutorial, we'll learn how to {goal}.",
                step_template="Let's {description}",
                transition_template="Now that we've done that, let's {next_description}",
                conclusion_template="Congratulations! You've completed this tutorial on {title}."
            )

    async def generate_script(self, 
                            processed_content: List[ProcessedScreenshot],
                            flow_analysis: FlowAnalysis,
                            guide_context: GuideContext) -> Script:
        """Generate a complete script with timing and transitions."""
        start_time = time.time()
        logger.info("Starting script generation...")
        logger.info(f"Processing {len(processed_content)} screenshots")
        
        # Log the input processed_content
        logger.info("Input processed_content:")
        for screenshot in processed_content:
            logger.info(f"Screenshot {screenshot.id}:")
            logger.info(f"  Description: {screenshot.description}")
            logger.info(f"  Context: {screenshot.context}")
            logger.info(f"  Duration: {screenshot.suggested_duration}")

        # First, gather all screenshot information asynchronously
        logger.info("Gathering screenshot information...")
        screenshot_info = await self._gather_screenshot_info(processed_content)
        
        # Generate the complete script in one shot
        logger.info("Generating complete script...")
        script_sections = await self._generate_complete_script(screenshot_info, guide_context)
        
        # Split the generated script into sections
        introduction, steps, conclusion = self._split_script_into_sections(script_sections)
        
        # Calculate metadata
        logger.info("Calculating script metadata...")
        metadata = self._calculate_metadata(introduction, steps, conclusion)
        
        end_time = time.time()
        logger.info(f"Script generation completed in {end_time - start_time:.2f} seconds")
        logger.info(f"Total duration: {metadata['total_duration']:.2f} seconds")
        logger.info(f"Total steps: {metadata['step_count']}")
        
        return Script(
            introduction=introduction,
            steps=steps,
            conclusion=conclusion,
            metadata=metadata
        )

    async def _gather_screenshot_info(self, processed_content: List[ProcessedScreenshot]) -> List[Dict]:
        """Gather all screenshot information asynchronously."""
        logger.info("Starting to gather screenshot information...")
        logger.info(f"Number of screenshots to process: {len(processed_content)}")
        
        screenshot_info = []
        for screenshot in processed_content:
            logger.info(f"Processing screenshot: {screenshot.id}")
            logger.info(f"Description: {screenshot.description}")
            logger.info(f"Context: {screenshot.context}")
            
            info = {
                "id": screenshot.id,
                "description": screenshot.description,
                "context": screenshot.context,
                "suggested_duration": screenshot.suggested_duration
            }
            screenshot_info.append(info)
            
        logger.info("Screenshot information gathered:")
        logger.info(json.dumps(screenshot_info, indent=2))
        return screenshot_info

    async def _generate_complete_script(self, 
                                      screenshot_info: List[Dict],
                                      guide_context: GuideContext) -> List[Dict]:
        """Generate the complete script in one shot using a comprehensive prompt."""
        # Prepare the screenshot data in the required format
        screenshots_json = json.dumps(screenshot_info, indent=2)
        
        # Log the screenshot data
        logger.info("\n=== SCREENSHOT DATA BEING SENT ===")
        logger.info(f"Number of screenshots: {len(screenshot_info)}")
        for idx, screenshot in enumerate(screenshot_info, 1):
            logger.info(f"\nScreenshot {idx}:")
            logger.info(f"ID: {screenshot['id']}")
            logger.info(f"Description: {screenshot['description']}")
            logger.info(f"Context: {screenshot['context']}")
            logger.info(f"Duration: {screenshot['suggested_duration']}")
        
        prompt = f"""You are an AI assistant tasked with generating a segmented voiceover script for a training video, including cues for when to display corresponding screenshots. Your output must strictly follow the specified format.

Overall User Context:
Title: {guide_context.title}
Goal: {guide_context.goal}
Target Audience: {guide_context.target_audience}
Detailed Context: {guide_context.detailed_context}

Screenshot Analysis Data:
{screenshots_json}

Your Task:
Create a voiceover script, broken down segment by segment, corresponding to each provided screenshot.
First, determine a concise and relevant title or topic for the training based only on the Detailed Description/Context Dump.
Then, use the Overall User Context (including the inferred title/topic) to frame the narrative, provide purpose, use correct terminology, and create introductions/conclusions/transitions. Use the Action/Content Description for each screenshot to narrate the specific action occurring in that step.

Crucially: Embed Screenshot Display Cues. Within each voiceover text segment, you must insert a specific marker [SHOW: Screenshot_ID] (where Screenshot_ID is the ID associated with that segment) to indicate the precise moment the corresponding screenshot should ideally appear on screen. Place this marker strategically just before or as the main visual element or action described in the screenshot is mentioned in the narration. This provides the necessary timing information for video editing.

Mandatory Rules & Output Format:

1. Strict Segmentation: The voiceover must be broken down so that each numbered output item corresponds directly to one Screenshot ID.

2. Timing Cue Integration: Each voiceover text segment must include exactly one instance of the marker [SHOW: Screenshot_ID], placed strategically within the text to signal when that specific screenshot should be displayed. The Screenshot_ID in the marker must match the ID on the first line of that output item.

3. Context Integration: Weave the Overall User Context (including terminology and the inferred topic) into the narration for relevance and flow. Explain why a step is being done, using the user's terms.

4. Transitions: Include natural-sounding transitions. These should typically occur at the end of one voiceover segment to lead into the next, or at the beginning of a segment referring back briefly.

5. Introduction/Conclusion: The voiceover for the first Screenshot ID should include the introduction (using the inferred title/topic). The voiceover for the last Screenshot ID should include the conclusion (summarizing the achievement related to the inferred topic).

6. Accuracy: Ensure the voiceover accurately describes the action relevant to the corresponding screenshot, interpreted within the Overall User Context. The [SHOW: Screenshot_ID] cue should align logically with this description.

Output Format: You must output the result as a numbered list. Each item in the list must contain exactly two lines:

Line 1: The Screenshot ID in square brackets, e.g., [SS_001]
Line 2: The Voiceover text segment for that specific screenshot/step, including the embedded [SHOW: Screenshot_ID] cue.

Example format:
1. [SS_001]
Welcome to this tutorial on [topic]. [SHOW: SS_001] Let's begin by...

2. [SS_002]
Now that we've seen the overview, let's look at the first step. [SHOW: SS_002] Here we can see...

BEGIN SCRIPT GENERATION BASED ON THE INPUTS ABOVE."""

        # Log the full prompt
        logger.info("\n=== FULL PROMPT BEING SENT TO GEMINI ===")
        logger.info(prompt)

        logger.info("\nSending prompt to Gemini for script generation...")
        response = self.gemini_model.generate_content(prompt)
        logger.info("Script generated successfully")
        
        # Log the raw response for debugging
        logger.info("\n=== RAW RESPONSE FROM GEMINI ===")
        logger.info(response.text)

        # Parse the response into sections
        sections = self._parse_generated_script(response.text)
        logger.info(f"\nParsed {len(sections)} sections from response")
        
        # Log each parsed section
        logger.info("\n=== PARSED SECTIONS ===")
        for idx, section in enumerate(sections, 1):
            logger.info(f"\nSection {idx}:")
            logger.info(f"ID: {section['screenshot_id']}")
            logger.info(f"Text: {section['text']}")
            logger.info(f"Duration: {section['duration']}")
            
        return sections

    def _parse_generated_script(self, generated_text: str) -> List[Dict]:
        """Parse the generated script text into structured sections."""
        sections = []
        current_section = None
        current_number = None
        
        logger.info("Starting to parse generated script...")
        
        for line in generated_text.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            logger.debug(f"Processing line: {line}")
            
            # Check if this is a numbered line with screenshot ID
            if line[0].isdigit() and '.' in line:
                parts = line.split('.', 1)
                if len(parts) == 2:
                    current_number = parts[0].strip()
                    line = parts[1].strip()
            
            # Check if this is a screenshot ID line
            if line.startswith('[') and line.endswith(']'):
                if current_section:
                    logger.debug(f"Adding section: {current_section}")
                    sections.append(current_section)
                screenshot_id = line[1:-1]
                logger.debug(f"Found new section with ID: {screenshot_id}")
                current_section = {
                    'screenshot_id': screenshot_id,
                    'text': '',
                    'duration': 10.0  # Default duration
                }
            elif current_section:
                if current_section['text']:
                    current_section['text'] += ' ' + line
                else:
                    current_section['text'] = line
        
        if current_section:
            logger.debug(f"Adding final section: {current_section}")
            sections.append(current_section)
        
        logger.info(f"Finished parsing. Found {len(sections)} sections")
        if sections:
            logger.info("First section preview:")
            logger.info(f"ID: {sections[0]['screenshot_id']}")
            logger.info(f"Text: {sections[0]['text'][:100]}...")
        else:
            logger.warning("No sections were parsed from the response")
            
        return sections

    def _split_script_into_sections(self, script_sections: List[Dict]) -> tuple:
        """Split the generated script into introduction, steps, and conclusion."""
        if not script_sections:
            raise ValueError("No script sections generated")
            
        introduction = ScriptSection(
            text=script_sections[0]['text'],
            screenshot_id=script_sections[0]['screenshot_id'],
            duration=15.0
        )
        
        steps = []
        for section in script_sections[1:-1]:
            steps.append(ScriptSection(
                text=section['text'],
                screenshot_id=section['screenshot_id'],
                duration=section['duration']
            ))
            
        conclusion = ScriptSection(
            text=script_sections[-1]['text'],
            screenshot_id=script_sections[-1]['screenshot_id'],
            duration=10.0
        )
        
        return introduction, steps, conclusion

    def _calculate_metadata(self,
                          introduction: ScriptSection,
                          steps: List[ScriptSection],
                          conclusion: ScriptSection) -> Dict:
        """Calculate metadata for the script."""
        logger.info("Calculating script metadata")
        total_duration = (
            introduction.duration +
            sum(step.duration for step in steps) +
            conclusion.duration
        )
        
        metadata = {
            "total_duration": total_duration,
            "step_count": len(steps),
            "guide_type": self.guide_type.value
        }
        logger.info(f"Metadata calculated: {metadata}")
        return metadata

    async def test_prompt_construction(self, processed_content: List[ProcessedScreenshot], guide_context: GuideContext):
        """Test function to verify prompt construction with screenshot data."""
        logger.info("Testing prompt construction...")
        
        # Gather screenshot info
        screenshot_info = await self._gather_screenshot_info(processed_content)
        
        # Generate the prompt
        screenshots_json = json.dumps(screenshot_info, indent=2)
        
        # Log the screenshot data
        logger.info("\n=== SCREENSHOT DATA ===")
        logger.info(screenshots_json)
        
        # Construct and log the full prompt
        prompt = f"""You are an AI assistant tasked with generating a segmented voiceover script for a training video, including cues for when to display corresponding screenshots. Your output must strictly follow the specified format.

Overall User Context:
Title: {guide_context.title}
Goal: {guide_context.goal}
Target Audience: {guide_context.target_audience}
Detailed Context: {guide_context.detailed_context}

Screenshot Analysis Data:
{screenshots_json}

Your Task:
Create a voiceover script, broken down segment by segment, corresponding to each provided screenshot.
First, determine a concise and relevant title or topic for the training based only on the Detailed Description/Context Dump.
Then, use the Overall User Context (including the inferred title/topic) to frame the narrative, provide purpose, use correct terminology, and create introductions/conclusions/transitions. Use the Action/Content Description for each screenshot to narrate the specific action occurring in that step.

Crucially: Embed Screenshot Display Cues. Within each voiceover text segment, you must insert a specific marker [SHOW: Screenshot_ID] (where Screenshot_ID is the ID associated with that segment) to indicate the precise moment the corresponding screenshot should ideally appear on screen. Place this marker strategically just before or as the main visual element or action described in the screenshot is mentioned in the narration. This provides the necessary timing information for video editing.

Mandatory Rules & Output Format:

1. Strict Segmentation: The voiceover must be broken down so that each numbered output item corresponds directly to one Screenshot ID.

2. Timing Cue Integration: Each voiceover text segment must include exactly one instance of the marker [SHOW: Screenshot_ID], placed strategically within the text to signal when that specific screenshot should be displayed. The Screenshot_ID in the marker must match the ID on the first line of that output item.

3. Context Integration: Weave the Overall User Context (including terminology and the inferred topic) into the narration for relevance and flow. Explain why a step is being done, using the user's terms.

4. Transitions: Include natural-sounding transitions. These should typically occur at the end of one voiceover segment to lead into the next, or at the beginning of a segment referring back briefly.

5. Introduction/Conclusion: The voiceover for the first Screenshot ID should include the introduction (using the inferred title/topic). The voiceover for the last Screenshot ID should include the conclusion (summarizing the achievement related to the inferred topic).

6. Accuracy: Ensure the voiceover accurately describes the action relevant to the corresponding screenshot, interpreted within the Overall User Context. The [SHOW: Screenshot_ID] cue should align logically with this description.

Output Format: You must output the result as a numbered list. Each item in the list must contain exactly two lines:

Line 1: The Screenshot ID in square brackets, e.g., [SS_001]
Line 2: The Voiceover text segment for that specific screenshot/step, including the embedded [SHOW: Screenshot_ID] cue.

Example format:
1. [SS_001]
Welcome to this tutorial on [topic]. [SHOW: SS_001] Let's begin by...

2. [SS_002]
Now that we've seen the overview, let's look at the first step. [SHOW: SS_002] Here we can see...

BEGIN SCRIPT GENERATION BASED ON THE INPUTS ABOVE."""

        logger.info("\n=== FULL PROMPT ===")
        logger.info(prompt)
        
        return prompt 