from typing import List, Dict
from src.models.base import ScreenshotInfo, GuideContext, GuideType, GuideInput
import asyncio
from dataclasses import dataclass

@dataclass
class ProcessedScreenshot:
    id: str
    description: str
    context: str
    key_points: List[str]
    suggested_duration: float
    timestamp: float = None

@dataclass
class FlowAnalysis:
    logical_groups: List[List[ProcessedScreenshot]]
    key_points: List[str]
    suggested_transitions: List[Dict]

class ContentProcessor:
    def __init__(self):
        self.processed_screenshots: List[ProcessedScreenshot] = []

    async def process_screenshots(self, screenshots: List[ScreenshotInfo]) -> List[ProcessedScreenshot]:
        """Process screenshots in parallel to extract key information."""
        tasks = []
        for screenshot in screenshots:
            task = self._process_single_screenshot(screenshot)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        self.processed_screenshots = results

        # Sort screenshots based on timestamps if available, otherwise by ID
        if any(s.timestamp is not None for s in screenshots):
            # Sort by timestamp, with None values at the end
            self.processed_screenshots.sort(key=lambda x: (x.timestamp if x.timestamp is not None else float('inf')))
        else:
            # Sort by ID if no timestamps are available
            self.processed_screenshots.sort(key=lambda x: int(x.id))

        return self.processed_screenshots

    async def _process_single_screenshot(self, screenshot: ScreenshotInfo) -> ProcessedScreenshot:
        """Process a single screenshot to extract key information."""
        # Here we would typically use NLP or other processing
        # For now, we'll create a simple processed version
        return ProcessedScreenshot(
            id=screenshot.id,
            description=screenshot.description,
            context=screenshot.context,
            key_points=[screenshot.description],  # Simplified for now
            suggested_duration=10.0,  # Default duration
            timestamp=screenshot.timestamp  # Include timestamp in processed screenshot
        )

    def analyze_flow(self, screenshots: List[ProcessedScreenshot]) -> FlowAnalysis:
        """Analyze the flow of screenshots to identify logical groups and transitions."""
        # Group screenshots into logical sections
        logical_groups = self._group_screenshots(screenshots)
        
        # Extract key points
        key_points = self._extract_key_points(screenshots)
        
        # Generate suggested transitions
        transitions = self._generate_transitions(logical_groups)
        
        return FlowAnalysis(
            logical_groups=logical_groups,
            key_points=key_points,
            suggested_transitions=transitions
        )

    def _group_screenshots(self, screenshots: List[ProcessedScreenshot]) -> List[List[ProcessedScreenshot]]:
        """Group screenshots into logical sections based on content."""
        # For now, we'll use a simple grouping strategy
        # In a real implementation, this would use more sophisticated analysis
        return [screenshots[i:i+3] for i in range(0, len(screenshots), 3)]

    def _extract_key_points(self, screenshots: List[ProcessedScreenshot]) -> List[str]:
        """Extract key points from the screenshots."""
        return [point for screenshot in screenshots for point in screenshot.key_points]

    def _generate_transitions(self, groups: List[List[ProcessedScreenshot]]) -> List[Dict]:
        """Generate suggested transitions between groups."""
        transitions = []
        for i in range(len(groups) - 1):
            transitions.append({
                "type": "fade",
                "duration": 1.0,
                "from_group": i,
                "to_group": i + 1
            })
        return transitions 