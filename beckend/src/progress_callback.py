"""Progress callback interface for tracking job progress"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional


class Stage(Enum):
    """Discovery pipeline stages with their percentage weights"""
    LOADING = ("loading", 10)
    PROFILING = ("profiling", 25)
    DETECTING = ("detecting", 30)
    LLM_VALIDATION = ("llm_validation", 20)
    BUSINESS_VALIDATION = ("business_validation", 10)
    REPORTING = ("reporting", 5)

    def __init__(self, stage_name: str, weight: int):
        self._stage_name = stage_name
        self._weight = weight

    @property
    def stage_name(self) -> str:
        return self._stage_name

    @property
    def weight(self) -> int:
        return self._weight


class ProgressCallback(ABC):
    """Abstract base class for progress reporting callbacks"""

    @abstractmethod
    def set_stage(self, stage: Stage, total_items: int) -> None:
        """
        Set the current processing stage

        Args:
            stage: The current pipeline stage
            total_items: Total number of items to process in this stage
        """
        pass

    @abstractmethod
    def increment(self, message: str = "") -> None:
        """
        Increment progress within the current stage

        Args:
            message: Optional progress message
        """
        pass

    @abstractmethod
    def update(self, stage: Stage, percent: int, message: str = "") -> None:
        """
        Direct progress update

        Args:
            stage: Current stage
            percent: Overall progress percentage (0-100)
            message: Progress message
        """
        pass


class NoOpProgressCallback(ProgressCallback):
    """No-operation progress callback for backward compatibility"""

    def set_stage(self, stage: Stage, total_items: int) -> None:
        pass

    def increment(self, message: str = "") -> None:
        pass

    def update(self, stage: Stage, percent: int, message: str = "") -> None:
        pass


class ConsoleProgressCallback(ProgressCallback):
    """Console-based progress callback for CLI usage"""

    def __init__(self):
        self.current_stage: Optional[Stage] = None
        self.total_items: int = 0
        self.current_items: int = 0

    def set_stage(self, stage: Stage, total_items: int) -> None:
        self.current_stage = stage
        self.total_items = total_items
        self.current_items = 0
        print(f"\n[{stage.stage_name.upper()}] Starting...")

    def increment(self, message: str = "") -> None:
        self.current_items += 1
        if message:
            if self.total_items > 0:
                print(f"  [{self.current_items}/{self.total_items}] {message}")
            else:
                print(f"  {message}")

    def update(self, stage: Stage, percent: int, message: str = "") -> None:
        if message:
            print(f"[{stage.stage_name.upper()} - {percent}%] {message}")
