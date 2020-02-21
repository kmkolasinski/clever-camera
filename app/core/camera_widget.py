import threading
import time
from datetime import datetime
from time import sleep
from typing import Optional, Dict, Any, Tuple, List, Iterator

import remi.gui as gui
from PIL import Image

from config.config import Config
from core.base_predictor import ClassificationOutput
from core.camera_client import get_camera_client, BaseCameraClient
from core.widgets import (
    PILImage,
    PILImageWidget,
    LoggerWidget,
    SettingsWidget,
    ROIWidget,
    DroppableTabBox,
    StyledDropDownMenu,
    SButton,
    MonitoringScheduleWidget,
)
from core.history_widget import append_snapshots_history
from core.tflite_classifier_predictor import TFClassifierPredictor

NAME = "camera_name"
MODEL_NAME = "model_name"
URL = "url"
USER = "user"
PASSWORD = "password"
CHECK_PERIOD = "check_period"
CAMERA_TIMEOUT = "timeout"
AUTO_START = "auto_start"
MONITORING_RUN_ICON = "fa-play-circle"
MONITORING_RUNNING_ICON = "fa-play-circle fa-spin"
MONITORING_SLEEP_ICON = "fa-bed fa-spin"
MEAN_CHANGE_THRESHOLD = 0.01
# the number of seconds between to events to be
# considered as two different events
EVENTS_SEQUENCE_SEPARATION = 5


class CameraWidget(SettingsWidget):
    def __init__(self, *args, **kwargs):
        super(CameraWidget, self).__init__(*args, **kwargs)
        self.camera_client: Optional[BaseCameraClient] = None
        self.predictor: Optional[TFClassifierPredictor] = None
        self.placeholder_cam_image = Image.open(Config.CAMERA_DEFAULT_IMAGE)
        self.is_running = False
        self.reload_cam_btn = SButton("Refresh Camera", "fa-camera-retro")
        self.check_predictor_btn = SButton("Test Classifier", "fa-robot")
        self.run_monitoring_btn = SButton(
            "Run monitoring", MONITORING_RUN_ICON, "btn btn-success"
        )
        self.stop_monitoring_btn = SButton(
            "Stop monitoring", "fa-stop-circle", "btn btn-warning"
        )

        self.rois_tab_widget = DroppableTabBox()
        self.logger = LoggerWidget(history_size=Config.LOGGER_HISTORY_SIZE)
        self.append(self.logger)

        menu_button = SButton("ROIs", icon="fa-vector-square")
        self.rois_menu = StyledDropDownMenu(menu_button)
        self.add_roi_btn = SButton("Add new ROI", icon="fa-plus-square")
        self.delete_roi_btn = SButton("Remove selected ROI", icon="fa-trash-alt")
        self.rois_menu.add_item("add_roi_button", self.add_roi_btn)
        self.rois_menu.add_item("remove_roi_button", self.delete_roi_btn)

        hbox = gui.HBox()
        hbox.append(self.rois_menu)
        hbox.append(self.reload_cam_btn)
        hbox.append(self.check_predictor_btn)
        hbox.append(self.run_monitoring_btn)
        hbox.append(self.stop_monitoring_btn)
        hbox.css_display = "table"
        hbox.css_margin = "auto"

        self.scheduler_widget = MonitoringScheduleWidget()

        self.add_text_field(NAME, "Custom name of the camera", "Home")
        self.settings.add_field("schedule", "Schedule", self.scheduler_widget)
        self.add_choice_field(MODEL_NAME, "Model Name", Config.list_models())
        self.add_text_field(URL, "Camera JPEG URL endpoint")
        self.add_text_field(USER, "Camera User name")
        self.add_text_field(PASSWORD, "Camera password")
        self.add_int_field(CHECK_PERIOD, "Check period [seconds]", default_value=5)
        self.add_int_field(CAMERA_TIMEOUT, "Camera timeout [seconds]", default_value=5)
        self.add_checkbox_field(AUTO_START, "Auto start monitoring?")

        self.cam_preview_widget = PILImageWidget(Config.APP_INSTANCE)
        self.cam_preview_widget.load(Config.CAMERA_DEFAULT_IMAGE, use_js=False)
        self.cam_preview_widget.css_width = "60%"
        self.cam_preview_widget.css_display = "block"
        self.cam_preview_widget.style["padding"] = "5px 5px"
        self.cam_preview_widget.style["border-radius"] = "5px"

        hlayout = gui.HBox()
        hlayout.append(self.cam_preview_widget)
        hlayout.append(self.rois_tab_widget)

        self.append(hlayout)
        self.append(hbox)
        self.append(self.settings)

        # signals
        self.add_roi_btn.onclick.do(self.add_new_roi)
        self.delete_roi_btn.onclick.do(self.delete_selected_roi)
        self.reload_cam_btn.onclick.do(self.reload_camera_connection)
        self.check_predictor_btn.onclick.do(self.test_predictor)
        self.run_monitoring_btn.onclick.do(self.start_monitoring)
        self.stop_monitoring_btn.onclick.do(self.stop_monitoring)
    
    @property
    def latest_camera_snapshot(self) -> PILImage:
        snapshot = None
        if self.camera_client is not None:
            snapshot = self.camera_client.get_latest_snapshot()

        if snapshot is None:
            snapshot = self.placeholder_cam_image
        return snapshot
    
    @property
    def is_auto_start_enabled(self):
        return self[AUTO_START].get_value()

    @gui.decorate_set_on_listener("(self, emitter)")
    @gui.decorate_event
    def on_events_sequence_finished(self, *args):
        return ()

    def emit_events_sequence_finished(self):
        return self.on_events_sequence_finished()

    def add_new_roi(self, emitter=None, roi_widget: Optional[ROIWidget] = None):
        if roi_widget is None:
            tab_index = len(self.rois_tab_widget.tab_keys_ordered_list)
            if tab_index > 0:
                tab_index = self.rois_tab_widget.tab_keys_ordered_list[-1].split("#")[
                    -1
                ]

            tab_index = int(tab_index) + 1
            roi_widget = ROIWidget(f"ROI #{tab_index}")

        roi_widget.on_roi_changed.do(self.camera_settings_changed)
        self.rois_tab_widget.append(roi_widget, roi_widget.name)
        self.camera_settings_changed()

    def delete_selected_roi(self, emitter=None):
        selected_key = self.rois_tab_widget.selected_widget_key
        if selected_key is None:
            return False
        self.rois_tab_widget.drop_tab(selected_key)
        self.camera_settings_changed()

    def iter_rois_widgets(self, only_enabled: bool = False) -> Iterator[ROIWidget]:
        for key in self.rois_tab_widget.tab_keys_ordered_list:
            widget: ROIWidget = self.rois_tab_widget.get_child(key)
            if widget.is_enabled() or not only_enabled:
                yield widget

    def start_monitoring(self, emitter=None):
        if not self.can_run_predictions():
            return False

        if self.is_running:
            self.logger.warning("Already running!")
            return False

        self.is_running = True
        monitoring_thread = threading.Thread(target=self._monitoring_process_fn)
        monitoring_thread.start()

    def stop_monitoring(self, emitter=None):
        self.logger.info("Monitoring stopped!")
        self.is_running = False

    def reload_camera_client(self):
        self.camera_client = get_camera_client(
            user=self[USER].get_value(),
            password=self[PASSWORD].get_value(),
            url=self[URL].get_value(),
            timeout=int(self[CAMERA_TIMEOUT].get_value()),
        )

    def reload_camera_connection(self, emitter=None):
        """
        Tries to get camera image and reconnect with the client if necessary
        """
        self.reload_camera_client()
        image, msg = self.camera_client.get_snapshot()
        self.camera_settings_changed(emitter=None, image=image)
        if image is None:
            self.logger.error(msg)
        else:
            self.logger.info(msg)

    def can_run_predictions(self) -> bool:
        self.load_classifier()
        if self.predictor is None:
            return False

        if self.camera_client is None:
            self.logger.error("Camera client not loaded! Click 'Refresh Camera' button.")
            return False
        return True

    def predict(
        self, image: PILImage, rois: Optional[List[ROIWidget]] = None
    ) -> Tuple[List[ROIWidget], List[ClassificationOutput], float]:

        start = time.time()
        crops = []
        if rois is None:
            rois = list(self.iter_rois_widgets(only_enabled=True))

        for roi in rois:
            crops.append(roi.crop(image))

        if len(rois) == 0:
            return [], [], 0.0

        predictions = self.predictor.predict(images=crops)
        dt = time.time() - start
        return rois, predictions, dt

    def format_predictions(
        self,
        rois: List[ROIWidget],
        predictions: List[ClassificationOutput],
        timedelta: float,
    ):
        predictions = [f"{r.name}: [{p}]" for r, p in zip(rois, predictions)]
        return f"Predicted in {timedelta:.2f} seconds: {predictions}"

    def test_predictor(self, emitter=None):

        if not self.can_run_predictions():
            image = self.placeholder_cam_image.copy()
        else:
            image = self.camera_client.get_latest_snapshot()

        if image is not None:
            rois_widgets, predictions, delta = self.predict(image=image)
            self.logger.info(self.format_predictions(rois_widgets, predictions, delta))

    def camera_settings_changed(self, emitter=None, image=None, *args):

        if image is None:
            # try to get latest image from camera
            if self.camera_client is not None:
                image = self.camera_client.get_latest_snapshot()
            # if not possible use default placeholder for display
            if image is None:
                image = self.placeholder_cam_image.copy()

        # resize image to max of the preview size width
        image = image.copy()
        if image.size[0] < Config.CAMERA_SNAPSHOT_PREVIEW_SIZE[0]:
            sw, sh = image.size
            tw, th = Config.CAMERA_SNAPSHOT_PREVIEW_SIZE
            scale = tw / sw
            image = image.resize((tw, int(sh * scale)))

        # thumbnail doest only down sampling it will not increase image size
        image.thumbnail(Config.CAMERA_SNAPSHOT_PREVIEW_SIZE)
        for roi in self.iter_rois_widgets():
            roi.draw_roi_on_image(image)
        self.cam_preview_widget.set_pil_image(image)

    def load_classifier(self):
        model_path = Config.MODELS_DIR / self[MODEL_NAME].get_value()
        self.predictor = None
        if model_path.exists():
            try:
                self.predictor = TFClassifierPredictor.load(model_path)
            except Exception as e:
                self.logger.error(f"Cannot load classifier: {e}")
        else:
            self.logger.error(f"Cannot find model at path: {model_path}")

    def get_settings(self) -> Dict[str, Any]:
        general_settings = super().get_settings()
        rois_settings = [roi.get_settings() for roi in self.iter_rois_widgets()]
        return {"general": general_settings, "rois": rois_settings}

    def set_settings(self, config: Dict[str, Any]) -> None:
        for key, value in config["general"].items():
            if self.settings.has_field(key):
                self.settings.set_value(key, value)

        for roi_config in config["rois"]:
            roi = ROIWidget.from_settings(roi_config)
            self.add_new_roi(roi_widget=roi)
        self.load_classifier()

    def _monitoring_process_fn(self):
        sleep_time = float(self[CHECK_PERIOD].get_value())
        events_sequence = []
        prev_image: Optional[PILImage] = None
        while self.is_running:
            if len(events_sequence) > 0:
                dt = datetime.now() - events_sequence[-1]
                if dt.total_seconds() > EVENTS_SEQUENCE_SEPARATION:
                    self.logger.info(
                        f"Sequence of size {len(events_sequence)} finished"
                    )
                    self.emit_events_sequence_finished()
                    events_sequence = []

            if not self.scheduler_widget.is_date_in_schedule():
                self.run_monitoring_btn.set_icon(MONITORING_SLEEP_ICON)
                sleep(sleep_time)
                continue

            self.run_monitoring_btn.set_icon(MONITORING_RUNNING_ICON)
            start = time.time()
            current_image, msg = self.camera_client.get_async_snapshot()

            if current_image is None:
                self.logger.warning(
                    f"Image not found. Waiting for {sleep_time} seconds."
                )
                sleep(sleep_time)
                continue

            rois_to_check = []
            rois_change_value = []
            if prev_image is not None:
                for roi in self.iter_rois_widgets(only_enabled=True):
                    change = roi.compute_roi_image_change(prev_image, current_image)
                    if change > MEAN_CHANGE_THRESHOLD:
                        rois_to_check.append(roi)
                        rois_change_value.append(change)
            else:
                rois_to_check = list(self.iter_rois_widgets(only_enabled=True))
            prev_image = current_image.copy()
            stop = time.time()
            if len(rois_to_check) == 0:
                delta = max(sleep_time - float(stop - start), 0)
                self.logger.info(f"Image not changed. Waiting {delta:.2f} seconds.")
                self.camera_settings_changed()
                sleep(delta)
                continue

            info = [
                f"{r.name} Δ={int(100*v)}%"
                for r, v in zip(rois_to_check, rois_change_value)
            ]
            info = ", ".join(info)
            self.logger.info(f"Image changed in ROIs ({info}), doing predictions.")

            rois, predictions, delta = self.predict(
                image=current_image, rois=rois_to_check
            )

            self.logger.info(self.format_predictions(rois, predictions, delta))
            for roi, roi_pred, im_delta in zip(rois, predictions, rois_change_value):
                self.check_and_update_history(
                    image=current_image,
                    roi=roi,
                    predictions=roi_pred,
                    image_change=im_delta,
                )
            self.camera_settings_changed(image=current_image)
            if len(rois) > 0:
                events_sequence.append(datetime.now())

            delta = max(sleep_time - (time.time() - start), 0)
            sleep(delta)
        self.run_monitoring_btn.set_icon(MONITORING_RUN_ICON)

    def check_and_update_history(
        self,
        image: PILImage,
        roi: ROIWidget,
        predictions: ClassificationOutput,
        image_change: float,
    ) -> bool:

        if predictions.is_empty():
            return False

        labels = roi.filter_labels(predictions.labels)
        if len(labels) == 0:
            return False

        return append_snapshots_history(
            image=image,
            labels=labels,
            roi_name=roi.name,
            labels_filter=roi.labels_filter,
            camera_name=self[NAME].get_value(),
            image_change=image_change,
        )
