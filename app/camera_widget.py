import threading
import time
from pathlib import Path
from time import sleep
from typing import Optional, Dict, Any, Tuple, List

import numpy as np
import remi.gui as gui
from PIL import ImageDraw

from camera_client import CameraClient
from gui import CustomFormWidget, CustomButton, HorizontalLine, PILImage
from gui import PILImageViewerWidget
from history_widget import append_snapshots_history
from tflite_classifier_predictor import TFClassifierPredictor


class CameraKeys:
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


class CameraWidget(gui.Widget):
    def __init__(self, *args):
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
        self.append(HorizontalLine())
        hbox = gui.HBox()

        hbox.append(self.testCameraButton)
        hbox.append(self.testPredictorButton)
        hbox.append(self.runMonitoringButton)
        hbox.append(self.stopMonitoringButton)
        hbox.set_style({"display": "flow-root"})

        self.append(hbox)
        self.settings = CustomFormWidget()
        self.settings.add_text(CameraKeys.NAME, "Custom name of the camera", "Home")
        self.settings.add_text(
            CameraKeys.MODEL_NAME, "Model Name", "mobilenet_v1_1.0_224_quant"
        )
        self.settings.add_text(CameraKeys.JPEG_URL, "Camera JPEG URL endpoint")
        self.settings.add_text(CameraKeys.USER, "Camera User name")
        self.settings.add_text(CameraKeys.PASSWORD, "Camera Password")
        self.settings.add_text(
            CameraKeys.CLASS_FILTER, "Class filter (comma separated))", "*"
        )
        self.settings.add_numeric(
            CameraKeys.CHECK_PERIOD, "Check period [seconds]", default_value=5
        )
        self.settings.add_numeric(CameraKeys.ROI_X_MIN, "ROI X minimum [%]")
        self.settings.add_numeric(CameraKeys.ROI_Y_MIN, "ROI Y minimum [%]")
        self.settings.add_numeric(
            CameraKeys.ROI_X_MAX, "ROI X maximum [%]", default_value=100
        )
        self.settings.add_numeric(
            CameraKeys.ROI_Y_MAX, "ROI Y maximum [%]", default_value=100
        )
        self.settings.style["width"] = "80%"

        self.imageWidget = PILImageViewerWidget("./resources/sample_snapshot.jpg")
        self.imageWidget.load("./resources/sample_snapshot.jpg")
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

        self.settings.inputs[CameraKeys.ROI_X_MIN].onchange.do(
            self.camera_settings_changed
        )
        self.settings.inputs[CameraKeys.ROI_Y_MIN].onchange.do(
            self.camera_settings_changed
        )
        self.settings.inputs[CameraKeys.ROI_X_MAX].onchange.do(
            self.camera_settings_changed
        )
        self.settings.inputs[CameraKeys.ROI_Y_MAX].onchange.do(
            self.camera_settings_changed
        )

    def _monitoring_process(self):
        sleepTime = float(self.settings.get_value(CameraKeys.CHECK_PERIOD))
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
                img_diff = (
                    np.abs(np.array(cim).mean(-1) - np.array(pim).mean(-1)) / 255.0
                )
                total_change = (img_diff > threshold).mean()
                print(f"Detected change: {total_change}")
                if total_change < 0.01:
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

            self.check_predictions(
                image=currentImage, predictions=predictions, image_change=total_change
            )
            currentImage = currentImage.copy()
            currentImage.thumbnail((1024, 1024))
            roi = self.get_camera_roi(currentImage)
            self.draw_camera_roi(roi, currentImage)
            self.imageWidget.set_image(currentImage)
            sleep(delta)

    def check_predictions(
        self, image: PILImage, predictions: List[Tuple[float, str]], image_change: float
    ):
        if len(predictions) == 0:
            return False
        classFilter = self.settings.get_value(CameraKeys.CLASS_FILTER)
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
            camera_name=self.settings.get_value(CameraKeys.NAME),
            image_change=image_change,
        )

    def start_monitoring(self, emitter=None):
        if self.isRunning:
            self.infoLabel.set_text("")
            return
        self.isRunning = True
        cameraThread = threading.Thread(target=self._monitoring_process)
        cameraThread.start()

    def stop_monitoring(self, emitter=None):
        print("Info: Monitoring finished ... ")
        self.isRunning = False

    def set_camera_client(self):
        self.cameraClient = CameraClient(
            user=self.settings.get_value(CameraKeys.USER),
            password=self.settings.get_value(CameraKeys.PASSWORD),
            jpeg_url=self.settings.get_value(CameraKeys.JPEG_URL),
        )

    def get_camera_roi(self, image: PILImage) -> Tuple[int, int, int, int]:
        x_min = int(self.settings.get_value(CameraKeys.ROI_X_MIN))
        y_min = int(self.settings.get_value(CameraKeys.ROI_Y_MIN))
        x_max = int(self.settings.get_value(CameraKeys.ROI_X_MAX))
        y_max = int(self.settings.get_value(CameraKeys.ROI_Y_MAX))
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
        draw.rectangle((roi[:2], roi[2:]), fill=None, outline="red", width=2)

    def test_camera(self, emitter=None):
        if self.cameraClient is None or not self.cameraClient.is_valid():
            self.set_camera_client()

        image, msg = self.cameraClient.get_snapshot()
        self.camera_settings_changed(emitter=None)
        self.infoLabel.set_text(msg)

    def test_predictor(self, emitter=None):
        image = self.cameraClient.get_latest_snapshot()
        if image is not None:
            roi = self.get_camera_roi(image)
            image = image.crop(box=roi)
            predictions = self.predictor.predict(image=image)
            self.infoLabel.set_text(f"Info: Classifier OK! Predicted: {predictions}")

    def camera_settings_changed(self, emitter=None, *args):
        if self.cameraClient is None:
            return False
        image = self.cameraClient.get_latest_snapshot()
        if image is not None:
            image.thumbnail((1024, 1024))
            roi = self.get_camera_roi(image)
            self.draw_camera_roi(roi, image)
        self.imageWidget.set_image(image)

    def get_settings(self) -> Dict[str, Any]:
        config = {
            k: self.settings.get_value(k) for k, _ in self.settings.inputs.items()
        }
        return config

    def set_settings(self, settings: Dict[str, Any]) -> None:
        for key, value in settings.items():
            if self.settings.has_field(key):
                self.settings.set_value(key, value)

        model_path = self.settings.get_value(CameraKeys.MODEL_NAME)
        model_path = Path("models") / model_path
        if model_path.exists():
            self.predictor = TFClassifierPredictor.load(model_path)
        else:
            self.predictor = None
            self.infoLabel.set_text(f"Error: Cannot find model at path: {model_path}")

        self.set_camera_client()
