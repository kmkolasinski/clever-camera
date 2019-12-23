from abc import abstractmethod, ABC
from pathlib import Path
from typing import Any, List

from PIL.Image import Image
from dataclasses import dataclass


class AbstractPredictor(ABC):
    @classmethod
    @abstractmethod
    def load(cls, path: Path) -> "AbstractPredictor":
        """Create predictor from path.

        Args:
            path: path to folder with predictor weights etc

        Returns:
            initialized predictor
        """
        pass

    @abstractmethod
    def predict(self, images: List[Image]) -> Any:
        pass


@dataclass(frozen=True)
class ClassificationOutput:
    labels: List[str]
    scores: List[float]

    def __str__(self):
        tuples = [f"({int(s*100)}% {l})" for l, s in zip(self.labels, self.scores)]
        return ", ".join(tuples)

    def is_empty(self) -> bool:
        return len(self.labels) == 0


@dataclass(frozen=True)
class ClassifierPredictor(AbstractPredictor, ABC):
    def predict(self, images: List[Image]) -> List[ClassificationOutput]:
        """
        For given list of images crops it returns corresponding
        PredictionData

        Args:
            images list of N PIL images to be feed into predictor

        Returns:
            predictions a list of N PredictionData which correspond to
                input images
        """
        pass
