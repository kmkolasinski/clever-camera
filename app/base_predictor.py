from abc import abstractmethod, ABC
from pathlib import Path
from typing import Any

from PIL.Image import Image


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
    def predict(self, image: Image) -> Any:
        pass
