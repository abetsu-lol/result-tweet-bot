"""Data Dragon: Riot's static CDN for champion names and icons (no API key, not rate limited)."""
from .http import new_session, request

BASE = "https://ddragon.leagueoflegends.com"
LOCALE = "ja_JP"


class DataDragon:
    def __init__(self, session=None):
        self._session = session or new_session()
        self._champions = None  # lowercased champion id -> champion entry
        self._icons = {}
        self.version = None

    def _load(self):
        if self._champions is None:
            self.version = request(self._session, "GET", f"{BASE}/api/versions.json").json()[0]
            data = request(self._session, "GET", f"{BASE}/cdn/{self.version}/data/{LOCALE}/champion.json").json()
            # match-v5 championName equals the Data Dragon id except for casing (e.g. FiddleSticks)
            self._champions = {c["id"].lower(): c for c in data["data"].values()}
        return self._champions

    def _champion(self, name):
        return self._load().get(name.lower()) if name else None

    def name(self, champion_name):
        """Japanese display name; falls back to the given name for unknown champions."""
        champion = self._champion(champion_name)
        return champion["name"] if champion else (champion_name or "-")

    def icon(self, champion_name):
        """Square PNG icon as bytes, or None for unknown champions."""
        champion = self._champion(champion_name)
        if not champion:
            return None
        file = champion["image"]["full"]
        if file not in self._icons:
            url = f"{BASE}/cdn/{self.version}/img/champion/{file}"
            self._icons[file] = request(self._session, "GET", url).content
        return self._icons[file]
