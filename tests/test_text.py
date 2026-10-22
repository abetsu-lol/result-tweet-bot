from bot import text
from fakes import FakeChampions


def record(win=True, gold=100, cs=5, kp=0.5, champion="Ahri", opponent="Zed", kda=(1, 0, 2)):
    return {"metrics": {"win": win, "champion": champion, "opponent_champion": opponent, "gold_diff_15": gold,
                        "cs_diff_15": cs, "kill_participation": kp,
                        "kda_15": {"kills": kda[0], "deaths": kda[1], "assists": kda[2]}}}


def test_weighted_length_counts_cjk_as_two():
    assert text.weighted_length("abc 123") == 7
    assert text.weighted_length("ソロランク") == 10
    assert text.weighted_length("GD@15 +3") == 8


def test_period_label():
    assert text.period_label("2026-10-19", "2026-10-19") == "10/19"
    assert text.period_label("2026-10-13", "2026-10-19") == "10/13〜10/19"


def test_summary_counts_and_averages_ignoring_missing_values():
    records = [record(win=True, gold=300, kp=0.4), record(win=False, gold=None, kp=0.6), record(win=False, gold=-100)]
    assert text.summary("10/19", records) == "10/19 ソロランク 1勝2敗\n平均 GD@15 +100 / KP 50%"


def test_summary_without_any_gold_value():
    assert text.summary("10/19", [record(gold=None)]).endswith("GD@15 - / KP 50%")


def test_game_line_uses_japanese_names_and_signs():
    line = text.game_line(record(win=False, gold=-184, cs=15, kp=0.59, opponent=None), FakeChampions())
    assert line == "負 アーリ vs - 1/0/2 GD-184 CS+15 KP59%"


def test_split_into_posts_respects_the_weighted_limit():
    header = "10/13〜10/19 ソロランク 6勝6敗"
    lines = [f"勝 アンベッサ vs エイトロックス 3/1/2 GD+{i:04d} CS+40 KP31%" for i in range(12)]
    posts = text.split_into_posts(header, lines)
    assert len(posts) > 1
    assert all(text.weighted_length(p) <= text.MAX_WEIGHTED_LENGTH for p in posts)
    assert posts[0].startswith(header)
    assert "\n".join(posts).split("\n")[1:] == lines  # every line once, in order


def test_rank_line():
    gold = {"tier": "GOLD", "rank": "II", "league_points": 45, "wins": 1, "losses": 1}
    assert text.rank_line({"solo_duo": gold}) == "ランク: ゴールド II 45LP"
    assert text.rank_line({"solo_duo": {**gold, "tier": "GRANDMASTER", "rank": "I", "league_points": 512}}) == \
        "ランク: グランドマスター 512LP"
    assert text.rank_line({"solo_duo": None}) == "ランク: なし"
    assert text.rank_line(None) is None


def test_summary_ends_with_the_rank_when_known():
    snapshot = {"solo_duo": {"tier": "DIAMOND", "rank": "IV", "league_points": 0, "wins": 1, "losses": 1}}
    assert text.summary("10/19", [record()], snapshot).splitlines()[-1] == "ランク: ダイヤモンド IV 0LP"
    assert len(text.summary("10/19", [record()]).splitlines()) == 2
