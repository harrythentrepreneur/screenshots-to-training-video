from enum import Enum
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

class GuideType(Enum):
    PRODUCT_DEMO = "product_demo"
    SOP = "sop"
    TUTORIAL = "tutorial"

@dataclass
class ScreenshotInfo:
    id: str
    description: str
    context: str
    timestamp: Optional[float] = None
    file_path: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'ScreenshotInfo':
        return cls(**data)

    def __lt__(self, other: 'ScreenshotInfo') -> bool:
        """Enable sorting by timestamp if available, otherwise by ID."""
        if self.timestamp is not None and other.timestamp is not None:
            return self.timestamp < other.timestamp
        elif self.timestamp is not None:
            return True  # Timestamped items come before non-timestamped
        elif other.timestamp is not None:
            return False  # Non-timestamped items come after timestamped
        else:
            return int(self.id) < int(other.id)  # Fall back to ID-based sorting

@dataclass
class GuideContext:
    title: str
    goal: str
    detailed_context: str
    target_audience: str
    duration: Optional[int] = None
    created_at: datetime = datetime.now()

    def to_dict(self) -> Dict:
        data = asdict(self)
        data['created_at'] = data['created_at'].isoformat()
        return data

@dataclass
class GuideInput:
    screenshots: List[ScreenshotInfo]
    context: GuideContext
    guide_type: GuideType

    def to_dict(self) -> Dict:
        return {
            'screenshots': [s.to_dict() for s in self.screenshots],
            'context': self.context.to_dict(),
            'guide_type': self.guide_type.value
        }

@dataclass
class ScriptSection:
    text: str
    screenshot_id: Optional[str]
    duration: float
    transition: Optional[Dict] = None

    def to_dict(self) -> Dict:
        data = asdict(self)
        # Add screenshot cue if there's a screenshot ID
        if self.screenshot_id and f"[SHOW: {self.screenshot_id}]" not in self.text:
            # Find a good place to insert the cue (after the first sentence)
            sentences = self.text.split('.')
            if len(sentences) > 1:
                sentences[0] = sentences[0] + f" [SHOW: {self.screenshot_id}]"
                data['text'] = '.'.join(sentences)
            else:
                data['text'] = f"{self.text} [SHOW: {self.screenshot_id}]"
        return data

@dataclass
class Script:
    introduction: ScriptSection
    steps: List[ScriptSection]
    conclusion: ScriptSection
    metadata: Dict

    def to_dict(self) -> Dict:
        return {
            'introduction': self.introduction.to_dict(),
            'steps': [step.to_dict() for step in self.steps],
            'conclusion': self.conclusion.to_dict(),
            'metadata': self.metadata
        }

@dataclass
class ScriptOutput:
    script: Script
    screenshot_mapping: Dict[str, List[str]]
    timing: Dict[str, float]
    metadata: Dict

    def to_dict(self) -> Dict:
        return {
            'script': self.script.to_dict(),
            'screenshot_mapping': self.screenshot_mapping,
            'timing': self.timing,
            'metadata': self.metadata
        } 