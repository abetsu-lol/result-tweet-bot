"""X API v2 with OAuth 1.0a user context: image upload and (reply) posts.

Costs money per request (pay-per-use credits), so nothing here retries a post, and the
token's access level is checked on the free media upload before anything is posted.
"""
from requests_oauthlib import OAuth1

from .http import new_session, request

API = "https://api.x.com"


class XPermissionError(Exception):
    """The access token cannot post (app permission was not "Read and write" when it was issued)."""


class XClient:
    def __init__(self, app_credentials, account, session=None):
        self._session = session or new_session()
        self._session.auth = OAuth1(app_credentials["consumer_key"], app_credentials["consumer_secret"],
                                    account.access_token, account.access_token_secret)

    def _post(self, path, **kwargs):
        return request(self._session, "POST", f"{API}{path}", retries=0, **kwargs)

    def upload_png(self, data):
        """Uploads one image (chunked upload in a single segment) and returns its media id."""
        init = self._post("/2/media/upload/initialize",
                          json={"media_type": "image/png", "total_bytes": len(data), "media_category": "tweet_image"})
        level = init.headers.get("x-access-level", "")
        if level and "write" not in level:
            raise XPermissionError(f"access token is {level}; reissue it after setting Read and write")
        media_id = init.json()["data"]["id"]
        self._post(f"/2/media/upload/{media_id}/append",
                   files={"media": ("image.png", data, "image/png")}, data={"segment_index": "0"})
        self._post(f"/2/media/upload/{media_id}/finalize")
        return media_id

    def post(self, text, *, reply_to, media_ids=()):
        """Creates a reply to reply_to and returns the new post's id."""
        body = {"text": text, "reply": {"in_reply_to_tweet_id": reply_to}}
        if media_ids:
            body["media"] = {"media_ids": list(media_ids)}
        return self._post("/2/tweets", json=body).json()["data"]["id"]
