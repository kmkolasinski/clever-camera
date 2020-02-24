from core.base_predictor import ClassifierPredictor
from core.tflite_classifier_predictor import TFClassifierPredictor
import os

dir_path = os.path.dirname(os.path.realpath(__file__))


def get() -> ClassifierPredictor:
    model = TFClassifierPredictor.load(dir_path)
    return model
