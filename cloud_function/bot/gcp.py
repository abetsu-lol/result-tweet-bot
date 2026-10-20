"""Secret Manager and Cloud Storage over their REST APIs.

google-auth picks up the runtime service account on Cloud Functions and gcloud's
application default credentials locally, so the same code runs in both places.
"""
import base64
import gzip
import json
from urllib.parse import quote

import google.auth
from google.auth.transport.requests import AuthorizedSession

from .http import USER_AGENT, HttpError, request

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def authorized_session():
    credentials, _ = google.auth.default(scopes=SCOPES)
    session = AuthorizedSession(credentials)
    session.headers["User-Agent"] = USER_AGENT
    return session


class SecretStore:
    def __init__(self, session):
        self._session = session

    def latest(self, secret_name):
        """Value of the latest enabled version of projects/<p>/secrets/<id>."""
        url = f"https://secretmanager.googleapis.com/v1/{secret_name}/versions/latest:access"
        data = request(self._session, "GET", url).json()["payload"]["data"]
        return base64.b64decode(data).decode("utf-8")


class Bucket:
    """Objects of one bucket. Paths are built by the caller so no listing is ever needed."""

    def __init__(self, session, name):
        self._session = session
        self.name = name

    def _get(self, path):
        """The object's content as text, or None when it does not exist."""
        url = f"https://storage.googleapis.com/storage/v1/b/{self.name}/o/{quote(path, safe='')}"
        response = self._session.get(url, params={"alt": "media"}, timeout=30)
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise HttpError(response.status_code, f"gs://{self.name}/{path}", response.text)
        return response.text

    def _upload(self, path, data, content_type, *, only_if_absent=False):
        params = {"uploadType": "media", "name": path}
        if only_if_absent:
            params["ifGenerationMatch"] = "0"
        response = self._session.post(
            f"https://storage.googleapis.com/upload/storage/v1/b/{self.name}/o",
            params=params, data=data, headers={"Content-Type": content_type}, timeout=60)
        if only_if_absent and response.status_code == 412:
            return False  # already stored
        if response.status_code >= 400:
            raise HttpError(response.status_code, f"gs://{self.name}/{path}", response.text)
        return True

    def read_json(self, path):
        """Parsed JSON, or None when the object does not exist."""
        text = self._get(path)
        return None if text is None else json.loads(text)

    def read_ndjson(self, path):
        """Records of a newline-delimited JSON object, or [] when it does not exist."""
        text = self._get(path)
        return [] if text is None else [json.loads(line) for line in text.splitlines() if line.strip()]

    def write_json(self, path, obj):
        self._upload(path, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json")

    def write_ndjson(self, path, records):
        body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
        self._upload(path, body.encode("utf-8"), "application/x-ndjson")

    def write_gzip_json_once(self, path, obj):
        """Stores gzipped JSON unless the object already exists. Returns True if written."""
        raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return self._upload(path, gzip.compress(raw, mtime=0), "application/gzip", only_if_absent=True)
