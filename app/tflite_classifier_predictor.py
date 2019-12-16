from pathlib import Path
from typing import List, Tuple, Union

import numpy as np
import tflite_runtime.interpreter as tflite
from PIL.Image import Image
from dataclasses import dataclass

from base_predictor import AbstractPredictor


def load_labels(filename: str):
    with open(filename, "r") as f:
        return [line.strip() for line in f.readlines()]


@dataclass(frozen=True)
class TFClassifierPredictor(AbstractPredictor):
    interpreter: tflite.Interpreter
    labels: List[str]
    input_mean: float = 127.5
    input_std: float = 127.5
    k_top: int = 5
    score_threshold: float = 0.1

    @classmethod
    def load(cls, path: Union[Path, str]) -> "TFClassifierPredictor":
        model_path = Path(path) / "model.tflite"
        label_file = Path(path) / "labels.txt"
        interpreter = tflite.Interpreter(model_path=str(model_path))
        interpreter.allocate_tensors()
        labels = load_labels(label_file)
        return TFClassifierPredictor(interpreter=interpreter, labels=labels)

    def predict(self, image: Image) -> List[Tuple[float, str]]:
        input_details = self.interpreter.get_input_details()
        output_details = self.interpreter.get_output_details()

        height = input_details[0]["shape"][1]
        width = input_details[0]["shape"][2]
        img = image.resize((width, height))

        # check the type of the input tensor
        floating_model = input_details[0]["dtype"] == np.float32
        # add N dim
        input_data = np.expand_dims(img, axis=0)

        if floating_model:
            input_data = (np.float32(input_data) - self.input_mean) / self.input_std

        self.interpreter.set_tensor(input_details[0]["index"], input_data)
        self.interpreter.invoke()
        output_data = self.interpreter.get_tensor(output_details[0]["index"])
        results = np.squeeze(output_data)

        top_k = results.argsort()[-self.k_top :][::-1]
        predictions = []
        for i in top_k:
            if floating_model:
                score = float(results[i])
            else:
                score = float(results[i]) / 255.0
            if score > self.score_threshold:
                predictions.append((float(f"{score:.3f}"), self.labels[i]))
        return predictions
