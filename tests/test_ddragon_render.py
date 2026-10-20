import io

from PIL import Image

from bot import aggregate, render
from bot.ddragon import DataDragon
from fakes import FakeChampions


class Response:
    status_code, headers, text = 200, {}, ""

    def __init__(self, payload=None, content=b""):
        self._payload, self.content = payload, content

    def json(self):
        return self._payload


class Session:
    def __init__(self, routes):
        self.routes, self.calls, self.headers = routes, [], {}

    def request(self, method, url, **kwargs):
        self.calls.append(url)
        return self.routes[url]


BASE = "https://ddragon.leagueoflegends.com"
ROUTES = {
    f"{BASE}/api/versions.json": Response(["16.20.1", "16.19.1"]),
    f"{BASE}/cdn/16.20.1/data/ja_JP/champion.json": Response({"data": {
        "Fiddlesticks": {"id": "Fiddlesticks", "name": "フィドルスティックス", "image": {"full": "Fiddlesticks.png"}},
        "Ahri": {"id": "Ahri", "name": "アーリ", "image": {"full": "Ahri.png"}},
    }}),
    f"{BASE}/cdn/16.20.1/img/champion/Ahri.png": Response(content=b"icon"),
}


def test_names_are_japanese_and_match_case_insensitively():
    dd = DataDragon(Session(ROUTES))
    assert dd.name("Ahri") == "アーリ"
    assert dd.name("FiddleSticks") == "フィドルスティックス"  # match-v5 casing differs from Data Dragon
    assert dd.name("NewChamp") == "NewChamp" and dd.name(None) == "-"


def test_icons_are_fetched_once_and_unknown_ones_are_none():
    session = Session(ROUTES)
    dd = DataDragon(session)
    assert dd.icon("Ahri") == b"icon" and dd.icon("Ahri") == b"icon"
    assert dd.icon("NewChamp") is None
    assert session.calls.count(f"{BASE}/cdn/16.20.1/img/champion/Ahri.png") == 1


def metrics(champion, win, gold=100):
    return {"metrics": {"win": win, "champion": champion, "opponent_champion": "Zed", "gold_diff_15": gold,
                        "cs_diff_15": None, "kill_participation": 0.5, "kda_15": {"kills": 1, "deaths": 2, "assists": 3}}}


def test_by_champion_sorts_by_games_and_averages():
    rows = aggregate.by_champion([metrics("Ahri", True, 100), metrics("Garen", False), metrics("Ahri", False, 300)])
    assert [(r["champion"], r["games"], r["wins"], r["losses"]) for r in rows] == [("Ahri", 2, 1, 1), ("Garen", 1, 0, 1)]
    assert rows[0]["gold_diff_15"] == 200 and rows[0]["cs_diff_15"] is None


def test_images_have_one_row_per_item():
    games = [metrics("Ahri", i % 2 == 0, gold=None if i == 3 else 100 * i) for i in range(render.ROWS_PER_IMAGE)]
    image = Image.open(io.BytesIO(render.games_image("10/19 ソロランク", games, FakeChampions())))
    expected = render.TITLE_HEIGHT + render.HEADER_HEIGHT + render.ROW_HEIGHT * len(games) + render.PADDING
    assert image.size == (render.WIDTH, expected)

    rows = aggregate.by_champion(games + [metrics("UnknownChamp", True)])
    image = Image.open(io.BytesIO(render.champions_image("10/13〜10/19", rows, FakeChampions())))
    assert image.size[1] == render.TITLE_HEIGHT + render.HEADER_HEIGHT + render.ROW_HEIGHT * 2 + render.PADDING


def test_long_champion_names_are_shrunk_to_fit():
    class LongNames(FakeChampions):
        def name(self, champion):
            return "とてもながいチャンピオンのなまえ" * 2
    png = render.games_image("10/19", [metrics("Ahri", True)], LongNames())
    assert Image.open(io.BytesIO(png)).size[0] == render.WIDTH
