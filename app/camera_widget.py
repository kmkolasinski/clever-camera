import threading
import time
from pathlib import Path
from time import sleep
from typing import Optional, Dict, Any, Tuple, List

import numpy as np
import remi.gui as gui
from PIL import ImageDraw, Image

from camera_client import CameraClient
from config import Config
from gui import CustomFormWidget, CustomButton, HorizontalLine, PILImage, PILImageWidget
from history_widget import append_snapshots_history
from tflite_classifier_predictor import TFClassifierPredictor


NAME = "camera_name"
MODEL_NAME = "model_name"
JPEG_URL = "jpeg_url"
USER = "user"
PASSWORD = "password"
ROI_X_MIN = "roi_x_min"
ROI_Y_MIN = "roi_y_min"
ROI_X_MAX = "roi_x_max"
ROI_Y_MAX = "roi_y_max"
CROP_SIZE = "crop_size"
CHECK_PERIOD = "check_period"
CLASS_FILTER = "class_filter"


class CameraWidget(gui.Container):
    def __init__(self, app_instance, *args):
        super(CameraWidget, self).__init__(*args)
        self.cameraClient: Optional[CameraClient] = None
        self.predictor: Optional[TFClassifierPredictor] = None
        self.isRunning = False
        self.testCameraButton = CustomButton("Test Camera")
        self.testCameraButton.set_size(200, 40)
        self.testPredictorButton = CustomButton("Test Classifier")
        self.testPredictorButton.set_size(200, 40)
        self.runMonitoringButton = CustomButton("Run monitoring")
        self.runMonitoringButton.set_size(200, 40)
        self.stopMonitoringButton = CustomButton("Stop monitoring")
        self.stopMonitoringButton.set_size(200, 40)

        hbox = gui.HBox()
        hbox.append(self.testCameraButton)
        hbox.append(self.testPredictorButton)
        hbox.append(self.runMonitoringButton)
        hbox.append(self.stopMonitoringButton)
        hbox.set_style({"display": "flow-root"})
        self.append(hbox)

        self.settings = CustomFormWidget()
        self.add_text_field(NAME, "Custom name of the camera", "Home")
        self.add_text_field(MODEL_NAME, "Model Name", "mobilenet_v1_1.0_224_quant")
        self.add_text_field(JPEG_URL, "Camera JPEG URL endpoint")
        self.add_text_field(USER, "Camera User name")
        self.add_text_field(PASSWORD, "Camera Password")
        self.add_text_field(CLASS_FILTER, "Class filter (comma separated))", "*")
        self.add_int_field(CHECK_PERIOD, "Check period [seconds]", default_value=5)
        self.add_int_field(ROI_X_MIN, "ROI X minimum [%]")
        self.add_int_field(ROI_Y_MIN, "ROI Y minimum [%]")
        self.add_int_field(ROI_X_MAX, "ROI X maximum [%]", default_value=100)
        self.add_int_field(ROI_Y_MAX, "ROI Y maximum [%]", default_value=100)
        self.settings.style["width"] = "80%"

        self.defaultCameraImage = Image.open(Config.CAMERA_DEFAULT_IMAGE)
        self.imageWidget = PILImageWidget(app_instance)
        self.imageWidget.load(Config.CAMERA_DEFAULT_IMAGE, use_js=False)
        self.imageWidget.style["width"] = "50%"
        self.infoLabel = gui.Label("Info: ...")

        self.append(self.infoLabel)
        self.append(HorizontalLine())

        hlayout = gui.HBox()
        hlayout.append(self.settings)
        hlayout.append(self.imageWidget)
        self.append(hlayout)

        # signals
        self.testCameraButton.onclick.do(self.test_camera)
        self.testPredictorButton.onclick.do(self.test_predictor)
        self.runMonitoringButton.onclick.do(self.start_monitoring)
        self.stopMonitoringButton.onclick.do(self.stop_monitoring)

        self.settings.inputs[ROI_X_MIN].onchange.do(self.camera_settings_changed)
        self.settings.inputs[ROI_Y_MIN].onchange.do(self.camera_settings_changed)
        self.settings.inputs[ROI_X_MAX].onchange.do(self.camera_settings_changed)
        self.settings.inputs[ROI_Y_MAX].onchange.do(self.camera_settings_changed)

    def add_text_field(self, *args, **kwargs):
        self.settings.add_text(*args, **kwargs)

    def add_int_field(self, *args, **kwargs):
        self.settings.add_numeric(*args, **kwargs)

    def _monitoring_process_fn(self):
        sleepTime = float(self.settings.get_value(CHECK_PERIOD))
        while self.isRunning:
            print("Checking image ...")
            start = time.time()
            prevImage = self.cameraClient.get_latest_snapshot()
            currentImage, msg = self.cameraClient.get_snapshot()
            if currentImage is None:
                print(f"Image not found. Sleeping for: {sleepTime}")
                sleep(sleepTime)
                continue

            imagePixelsChanged = True
            if prevImage is not None:
                threshold = 0.2
                roi = self.get_camera_roi(currentImage)
                cim = currentImage.crop(box=roi).resize((200, 200), resample=2)
                pim = prevImage.crop(box=roi).resize((200, 200), resample=2)
                imageDiff = (
                    np.abs(np.array(cim).mean(-1) - np.array(pim).mean(-1)) / 255.0
                )
                totalChange = (imageDiff > threshold).mean()
                print(f"Detected change: {totalChange}")
                if totalChange < 0.01:
                    imagePixelsChanged = False

            stop = time.time()
            if not imagePixelsChanged:
                print(f"Image not changed. Sleeping for: {sleepTime}")
                delta = max(sleepTime - float(stop - start), 0)
                sleep(delta)
                continue

            print("Doing predictions ..")
            roi = self.get_camera_roi(currentImage)
            crop = currentImage.crop(box=roi)
            predictions = self.predictor.predict(image=crop)
            print(f"Done: {predictions}")
            stop = time.time()
            delta = max(sleepTime - float(stop - start), 0)
            self.infoLabel.set_text(
                f"Monitor predictions in {float(stop - start):.3}[s]: {predictions}"
            )

            self.check_and_append_predictions(
                image=currentImage, predictions=predictions, image_change=totalChange
            )
            currentImage = currentImage.copy()
            currentImage.thumbnail((1024, 1024))
            roi = self.get_camera_roi(currentImage)
            self.draw_camera_roi(roi, currentImage)
            self.imageWidget.set_pil_image(currentImage)
            sleep(delta)

    def check_and_append_predictions(
        self, image: PILImage, predictions: List[Tuple[float, str]], image_change: float
    ):
        if len(predictions) == 0:
            return False
        classFilter = self.settings.get_value(CLASS_FILTER)
        if classFilter == "*":
            labels = [label for score, label in predictions]
        else:
            searchWords = classFilter.lower().strip().split(",")
            labels = []
            for score, label in predictions:
                if label.lower() in searchWords:
                    labels.append(label)

        if len(labels) == 0:
            return False

        append_snapshots_history(
            image=image,
            labels=labels,
            class_filter=classFilter,
            camera_name=self.settings.get_value(NAME),
            image_change=image_change,
        )

    def start_monitoring(self, emitter=None):
        if not self.can_run_predictions():
            return False

        if self.isRunning:
            self.infoLabel.set_text("Warning: Already running!")
            return False

        self.isRunning = True
        cameraThread = threading.Thread(target=self._monitoring_process_fn)
        cameraThread.start()

    def stop_monitoring(self, emitter=None):
        self.infoLabel.set_text("Info: Monitoring stopped!")
        self.isRunning = False

    def set_camera_client(self):
        self.cameraClient = CameraClient(
            user=self.settings.get_value(USER),
            password=self.settings.get_value(PASSWORD),
            jpeg_url=self.settings.get_value(JPEG_URL),
        )

    def get_camera_roi(self, image: PILImage) -> Tuple[int, int, int, int]:
        x_min = int(self.settings.get_value(ROI_X_MIN))
        y_min = int(self.settings.get_value(ROI_Y_MIN))
        x_max = int(self.settings.get_value(ROI_X_MAX))
        y_max = int(self.settings.get_value(ROI_Y_MAX))
        x_min, y_min = max(0, x_min) / 100.0, max(0, y_min) / 100.0
        x_max, y_max = min(100, x_max) / 100.0, min(100, y_max) / 100.0
        width, height = image.size
        box = (
            int(x_min * width),
            int(y_min * height),
            int(x_max * width),
            int(y_max * height),
        )
        return box

    def draw_camera_roi(self, roi: Tuple[int, int, int, int], image: PILImage):
        draw = ImageDraw.Draw(image)
        draw.rectangle((roi[:2], roi[2:]), fill=None, outline="red", width=5)

    def test_camera(self, emitter=None):
        if self.cameraClient is None or not self.cameraClient.is_valid():
            self.set_camera_client()

        image, msg = self.cameraClient.get_snapshot()
        self.camera_settings_changed(emitter=None)
        self.infoLabel.set_text(msg)

    def can_run_predictions(self) -> bool:
        self.load_classifier()
        if self.predictor is None:
            return False

        if self.cameraClient is None:
            self.infoLabel.set_text(
                "Error: Camera client not loaded! Click 'test camera'"
            )
            return False
        return True

    def test_predictor(self, emitter=None):

        if not self.can_run_predictions():
            image = self.defaultCameraImage.copy()
        else:
            image = self.cameraClient.get_latest_snapshot()

        if image is not None:
            roi = self.get_camera_roi(image)
            imageCrop = image.crop(box=roi)
            predictions = self.predictor.predict(image=imageCrop)
            self.infoLabel.set_text(f"Info: Classifier OK! Predicted: {predictions}")

    def camera_settings_changed(self, emitter=None, *args):
        image = None
        if self.cameraClient is not None:
            image = self.cameraClient.get_latest_snapshot()

        if image is None:
            image = self.defaultCameraImage.copy()

        image.thumbnail((1024, 1024))
        roi = self.get_camera_roi(image)
        self.draw_camera_roi(roi, image)
        self.imageWidget.set_pil_image(image)

    def load_classifier(self):
        model_path = self.settings.get_value(MODEL_NAME)
        model_path = Path("models") / model_path
        self.predictor = None
        if model_path.exists():
            try:
                self.predictor = TFClassifierPredictor.load(model_path)
                self.infoLabel.set_text("Info: Classifier loaded!")
            except Exception as e:
                self.infoLabel.set_text(f"Error: Cannot load classifier: {e}")
        else:
            self.infoLabel.set_text(f"Error: Cannot find model at path: {model_path}")

    def get_settings(self) -> Dict[str, Any]:
        config = {
            k: self.settings.get_value(k) for k, _ in self.settings.inputs.items()
        }
        return config

    def set_settings(self, settings: Dict[str, Any]) -> None:
        for key, value in settings.items():
            if self.settings.has_field(key):
                self.settings.set_value(key, value)

        self.load_classifier()
