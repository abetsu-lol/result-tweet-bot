"""Post text: labels, number formatting and X's weighted length (twitter-text v3)."""
from datetime import date

MAX_WEIGHTED_LENGTH = 280

# twitter-text v3: code points in these ranges weigh 1, everything else (CJK, emoji, ...) weighs 2
_LIGHT_RANGES = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))


def weighted_length(text):
    return sum(1 if any(lo <= ord(ch) <= hi for lo, hi in _LIGHT_RANGES) else 2 for ch in text)


def signed(value):
    return "-" if value is None else f"{value:+d}"


def percent(ratio):
    return "-" if ratio is None else f"{round(ratio * 100)}%"


def kda(value):
    return "-" if not value else f"{value['kills']}/{value['deaths']}/{value['assists']}"


def short_date(day):
    d = date.fromisoformat(day)
    return f"{d.month}/{d.day}"


def period_label(first_day, last_day):
    """"10/19" for one day, "10/13〜10/19" for a range (days are 12:00-12:00 JST)."""
    first, last = short_date(first_day), short_date(last_day)
    return first if first == last else f"{first}〜{last}"


def average(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


TIERS_JA = {
    "IRON": "アイアン", "BRONZE": "ブロンズ", "SILVER": "シルバー", "GOLD": "ゴールド", "PLATINUM": "プラチナ",
    "EMERALD": "エメラルド", "DIAMOND": "ダイヤモンド", "MASTER": "マスター", "GRANDMASTER": "グランドマスター",
    "CHALLENGER": "チャレンジャー",
}
APEX_TIERS = ("MASTER", "GRANDMASTER", "CHALLENGER")  # no divisions; LP keeps counting from Master 0
LADDER_TIERS = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND"]  # 4 divisions each
DIVISIONS = ["IV", "III", "II", "I"]


def ladder_points(rank):
    """LP counted from Iron IV 0LP (100 per division, 400 per tier), so ranks can be subtracted."""
    if rank["tier"] in APEX_TIERS:
        return len(LADDER_TIERS) * 400 + rank["league_points"]
    return LADDER_TIERS.index(rank["tier"]) * 400 + DIVISIONS.index(rank["rank"]) * 100 + rank["league_points"]


def rank_label(rank):
    """"ゴールド II 45LP", or "なし" when unranked."""
    if not rank:
        return "なし"
    tier = TIERS_JA.get(rank["tier"], rank["tier"])
    division = "" if rank["tier"] in APEX_TIERS else f" {rank['rank']}"
    return f"{tier}{division} {rank['league_points']}LP"


def rank_line(end_snapshot, start_snapshot=None):
    """Rank at the end of the period, with the start and the LP change when the start is known.

    "ランク: ゴールド II 45LP → ゴールド I 4LP（+59LP）"; just the end when no start snapshot was
    stored; None when there is no end snapshot either.
    """
    if end_snapshot is None:
        return None
    end = end_snapshot.get("solo_duo")
    if start_snapshot is None:
        return f"ランク: {rank_label(end)}"
    start = start_snapshot.get("solo_duo")
    line = f"ランク: {rank_label(start)} → {rank_label(end)}"
    if start and end:
        change = ladder_points(end) - ladder_points(start)
        line += f"（{'±0' if change == 0 else f'{change:+d}'}LP）"
    return line


def summary(label, records, rank_snapshot=None, start_rank_snapshot=None):
    """First post's text: the period, the win-loss record, averages and the rank change."""
    wins = sum(1 for r in records if r["metrics"]["win"])
    losses = len(records) - wins
    gold = average([r["metrics"]["gold_diff_15"] for r in records])
    kp = average([r["metrics"]["kill_participation"] for r in records])
    lines = [f"{label} ソロランク {wins}勝{losses}敗",
             f"平均 GD@15 {signed(None if gold is None else round(gold))} / KP {percent(kp)}"]
    rank = rank_line(rank_snapshot, start_rank_snapshot)
    return "\n".join(lines + ([rank] if rank else []))


def game_line(record, champions):
    m = record["metrics"]
    result = "勝" if m["win"] else "負"
    return (f"{result} {champions.name(m['champion'])} vs {champions.name(m['opponent_champion'])} "
            f"{kda(m['kda_15'])} GD{signed(m['gold_diff_15'])} CS{signed(m['cs_diff_15'])} "
            f"KP{percent(m['kill_participation'])}")


def split_into_posts(header, lines, limit=MAX_WEIGHTED_LENGTH):
    """Packs lines into as few posts as possible; the header goes on the first post."""
    posts, current = [], header
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if weighted_length(candidate) <= limit:
            current = candidate
        else:
            posts.append(current)
            current = line
    posts.append(current)
    return posts
