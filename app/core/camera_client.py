import threading
import time
from abc import abstractmethod, ABC
from io import BytesIO
from time import sleep
from typing import Optional, Tuple
import requests
from PIL import Image
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
from core.widgets import PILImage


class BaseCameraClient(ABC):
    def __init__(self, user: str, password: str, url: str):
        self.user = user
        self.password = password
        self.url = url
        self.image: Optional[PILImage] = None

    @abstractmethod
    def is_valid(self) -> bool:
        pass

    @abstractmethod
    def get_snapshot(self) -> Tuple[Optional[Image.Image], str]:
        pass

    def check_connection(self) -> Tuple[bool, str]:
        if not self.is_valid():
            return (
                False,
                "Invalid session, bad camera "
                "configuration. Check login, password and url.",
            )

        return True, ""

    def get_latest_snapshot(self) -> Optional[PILImage]:
        """
        Returns: latest camera frame
        """
        if self.image is not None:
            return self.image.copy()
        return None


class JPEGCameraClient(BaseCameraClient):
    def __init__(self, user: str, password: str, url: str, timeout: int):
        super().__init__(user, password, url)
        self.timeout = timeout
        self.session = None
        self.msg: Optional[str] = None
        self.is_ok: bool = False
        self.during_requesting_image: bool = False
        self._init_session()

    def is_valid(self) -> bool:
        return self.session is not None

    def _init_session(self):
        self.session = requests.session()
        self.session.auth = HTTPDigestAuth(self.user, self.password)

        if self.get_snapshot()[0] is None:
            self.session.auth = HTTPBasicAuth(self.user, self.password)
            if self.get_snapshot()[0] is None:
                self.session = None

    def get_snapshot(self) -> Tuple[Optional[Image.Image], str]:
        """
        Returns: current image camera frame
        """
        start = time.time()
        self.during_requesting_image = True
        is_ok, msg = self.check_connection()
        if not is_ok:
            self.is_ok = False
            self.msg = msg
            self.during_requesting_image = False
            return None, msg

        try:
            response = self.session.get(self.url, timeout=self.timeout)
            if not response.ok:
                msg = f"Bad response: {response}. Check url."
                self.is_ok = False
                self.msg = msg
                self.during_requesting_image = False
                return None, msg
            image_bytes = BytesIO()
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    image_bytes.write(chunk)
            image = Image.open(image_bytes)
        except Exception as error:
            msg = f"Cannot get image bytes: {error}"

            self.is_ok = False
            self.msg = msg
            self.during_requesting_image = False
            return None, msg

        dt = time.time() - start
        msg = f"Camera is OK! Captured image of size {image.size} in {dt:.2} seconds."
        self.is_ok = True
        self.msg = msg
        self.during_requesting_image = False
        self.image = image.copy()
        return image, msg

    def get_async_snapshot(self) -> Tuple[Optional[Image.Image], str]:
        """
        Returns: current image camera frame and run background thread
            to download new one
        """
        while self.during_requesting_image:
            # wait for the last request to finish, simple single
            # element queue implementation
            sleep(0.01)
        cameraThread = threading.Thread(target=self.get_snapshot)
        cameraThread.start()
        if self.is_ok:
            return self.image, self.msg
        return None, self.msg


def get_camera_client(
    user: str, password: str, url: str, timeout: int
) -> JPEGCameraClient:
    return JPEGCameraClient(user=user, password=password, url=url, timeout=timeout)
