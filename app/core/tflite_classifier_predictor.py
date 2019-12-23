from pathlib import Path
from typing import List, Union, Tuple

import numpy as np
import tflite_runtime.interpreter as tflite
from PIL.Image import Image
from cached_property import cached_property
from dataclasses import dataclass

from core.base_predictor import ClassifierPredictor, ClassificationOutput


def load_labels(filename: str) -> List[str]:
    with open(filename, "r") as f:
        return [line.strip() for line in f.readlines()]


@dataclass(frozen=True)
class TFClassifierPredictor(ClassifierPredictor):
    interpreter: tflite.Interpreter
    labels: List[str]
    input_mean: float = 127.5
    input_std: float = 127.5
    k_top: int = 5
    score_threshold: float = 0.2

    @classmethod
    def load(cls, path: Union[Path, str]) -> "TFClassifierPredictor":
        model_path = Path(path) / "model.tflite"
        label_file = Path(path) / "labels.txt"
        interpreter = tflite.Interpreter(model_path=str(model_path))
        interpreter.allocate_tensors()
        labels = load_labels(label_file)
        return TFClassifierPredictor(interpreter=interpreter, labels=labels)

    @cached_property
    def input_details(self):
        return self.interpreter.get_input_details()

    @cached_property
    def output_details(self):
        return self.interpreter.get_output_details()

    @cached_property
    def floating_model(self) -> bool:
        return self.input_details[0]["dtype"] == np.float32

    @cached_property
    def input_shape(self) -> Tuple[int, int, int, int]:
        return self.input_details[0]["shape"]

    @cached_property
    def output_shape(self) -> Tuple[int, int]:
        return self.output_details[0]["shape"]

    @cached_property
    def batch_size(self) -> int:
        return self.input_shape[0]

    def prepare_image(self, image: Image) -> np.ndarray:
        height, width = self.input_shape[1:3]
        img = image.resize((width, height))
        # add N dim
        input_data = np.expand_dims(img, axis=0)
        if self.floating_model:
            input_data = (np.float32(input_data) - self.input_mean) / self.input_std
        return input_data

    def prepare_images(self, images: List[Image]) -> np.ndarray:
        return np.concatenate([self.prepare_image(img) for img in images], axis=0)

    def postprocess_predictions(self, predictions: np.ndarray) -> ClassificationOutput:
        top_k = predictions.argsort()[-self.k_top :][::-1]
        scores = []
        labels = []
        for i in top_k:
            if self.floating_model:
                score = float(predictions[i])
            else:
                score = float(predictions[i]) / 255.0
            if score > self.score_threshold:
                scores.append(float(f"{score:.3f}"))
                labels.append(self.labels[i])

        return ClassificationOutput(labels=labels, scores=scores)

    def predict(self, images: List[Image]) -> List[ClassificationOutput]:

        images = self.prepare_images(images)
        output_data = []
        for image in images:
            image = np.expand_dims(image, 0)  # (1, height, width, 3)
            # Run prediction for single image
            # I couldn't make mobile net to work with batch_size > 1
            self.interpreter.set_tensor(self.input_details[0]["index"], image)
            self.interpreter.invoke()
            output = self.interpreter.get_tensor(self.output_details[0]["index"])
            output_data.append(np.squeeze(output))
        return [
            self.postprocess_predictions(image_predictions)
            for image_predictions in output_data
        ]
