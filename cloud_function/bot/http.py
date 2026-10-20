"""HTTP helpers shared by the API clients."""
import time

import requests

USER_AGENT = "result-tweet-bot/0.1 (+https://github.com/abetsu-lol/result-tweet-bot)"
TIMEOUT_SECONDS = 30


class HttpError(Exception):
    """A request failed. The message has the status and URL path but no credentials."""

    def __init__(self, status, url, body=""):
        self.status = status
        super().__init__(f"HTTP {status} for {url.split('?')[0]} {body[:200]}".rstrip())


def new_session():
    """A session with an explicit User-Agent.

    The Riot API sits behind Cloudflare, which rejects some default library User-Agents
    (error code 1010), so every client identifies itself.
    """
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return session


def request(session, method, url, *, retries=3, max_wait=60, sleep=time.sleep, **kwargs):
    """Sends a request, retrying on 429 (honouring Retry-After) and on 5xx."""
    kwargs.setdefault("timeout", TIMEOUT_SECONDS)
    for attempt in range(retries + 1):
        response = session.request(method, url, **kwargs)
        retryable = response.status_code == 429 or response.status_code >= 500
        if not retryable or attempt == retries:
            break
        wait = response.headers.get("Retry-After")
        sleep(min(float(wait) if wait and wait.isdigit() else 2 ** attempt, max_wait))
    if response.status_code >= 400:
        raise HttpError(response.status_code, url, response.text)
    return response
