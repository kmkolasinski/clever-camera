from io import BytesIO
from typing import Optional, Tuple
import requests
from PIL import Image
from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from gui import PILImage


class CameraClient:
    def __init__(self, user: str, password: str, jpeg_url: str):
        self.user = user
        self.password = password
        self.jpeg_url = jpeg_url
        self.session = None
        self.image: Optional[PILImage] = None
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
        self.image = None
        if not self.is_valid():
            return (
                None,
                "Error: Invalid session, bad camera "
                "configuration. Check login, password and url.",
            )
        try:
            response = self.session.get(self.jpeg_url)
            if not response.ok:
                return None, f"Error: Bad response: {response}. Check jpeg_url."
            image_bytes = BytesIO()
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    image_bytes.write(chunk)
            image = Image.open(image_bytes)
        except Exception as error:
            return None, f"Error: Cannot get image bytes: {error}"

        self.image = image.copy()
        return image, "Info: Camera is OK!"

    def get_latest_snapshot(self) -> Optional[PILImage]:
        if self.image is not None:
            return self.image.copy()
        return None
