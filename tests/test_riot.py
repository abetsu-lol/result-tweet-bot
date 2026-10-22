from bot.config import RiotAccount
from bot.riot import MATCH_IDS_PAGE, RiotClient


class Response:
    status_code = 200
    headers = {}
    text = ""

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class Session:
    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.calls = []
        self.headers = {}

    def request(self, method, url, **kwargs):
        self.calls.append((url, kwargs.get("params")))
        return Response(self.payloads.pop(0))


def test_api_key_is_sent_as_header():
    session = Session()
    RiotClient("RGAPI-key", session)
    assert session.headers["X-Riot-Token"] == "RGAPI-key"


def test_puuid_quotes_riot_id_and_uses_region_host():
    session = Session({"puuid": "p"})
    client = RiotClient("k", session)
    assert client.puuid(RiotAccount("名前 です", "JP1", "jp1", "asia")) == "p"
    assert session.calls[0][0] == ("https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
                                   "%E5%90%8D%E5%89%8D%20%E3%81%A7%E3%81%99/JP1")


def test_match_ids_pages_until_a_short_page():
    first = [f"JP1_{i}" for i in range(MATCH_IDS_PAGE)]
    session = Session(first, ["JP1_last"])
    ids = RiotClient("k", session).match_ids("asia", "puuid", start_time=10, end_time=20)
    assert ids == first + ["JP1_last"]
    assert [params["start"] for _, params in session.calls] == [0, MATCH_IDS_PAGE]
    assert session.calls[0][1] == {"queue": 420, "startTime": 10, "endTime": 20, "start": 0, "count": MATCH_IDS_PAGE}


def test_match_and_timeline_paths():
    session = Session({"m": 1}, {"t": 1})
    client = RiotClient("k", session)
    assert client.match("asia", "JP1_1") == {"m": 1}
    assert client.timeline("asia", "JP1_1") == {"t": 1}
    assert [url for url, _ in session.calls] == [
        "https://asia.api.riotgames.com/lol/match/v5/matches/JP1_1",
        "https://asia.api.riotgames.com/lol/match/v5/matches/JP1_1/timeline",
    ]


def test_solo_duo_rank_picks_the_solo_queue_from_the_platform_host():
    session = Session([{"queueType": "RANKED_FLEX_SR", "tier": "SILVER", "rank": "I", "leaguePoints": 1, "wins": 1, "losses": 1},
                       {"queueType": "RANKED_SOLO_5x5", "tier": "GOLD", "rank": "II", "leaguePoints": 45, "wins": 10,
                        "losses": 8, "hotStreak": False}],
                      [])
    client = RiotClient("k", session)
    assert client.solo_duo_rank("jp1", "p") == {"tier": "GOLD", "rank": "II", "league_points": 45, "wins": 10, "losses": 8}
    assert session.calls[0][0] == "https://jp1.api.riotgames.com/lol/league/v4/entries/by-puuid/p"
    assert client.solo_duo_rank("jp1", "p") is None  # unranked: no entries
