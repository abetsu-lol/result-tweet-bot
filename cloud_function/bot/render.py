"""PNG tables of games (per_game layout) or champions (summary layout)."""
import io
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .text import kda, percent, signed

ROWS_PER_IMAGE = 8  # preferred rows; more per image only when needed to stay within one post
ASSETS = Path(__file__).parent / "assets"

WIDTH = 1200
PADDING = 32
TITLE_HEIGHT = 84
HEADER_HEIGHT = 44
ROW_HEIGHT = 64
ICON = 44

BACKGROUND = (250, 250, 252)
TEXT = (28, 30, 36)
MUTED = (110, 116, 128)
RULE = (226, 228, 234)
WIN = (37, 99, 235)
LOSS = (220, 38, 38)


@lru_cache(maxsize=None)
def _font(size, bold=False):
    weight = "Bold" if bold else "Regular"
    return ImageFont.truetype(str(ASSETS / f"NotoSansJP-{weight}-subset.otf"), size)


def _diff_color(value):
    if value is None or value == 0:
        return TEXT
    return WIN if value > 0 else LOSS


class _Canvas:
    def __init__(self, title, rows):
        height = TITLE_HEIGHT + HEADER_HEIGHT + ROW_HEIGHT * rows + PADDING
        self.image = Image.new("RGB", (WIDTH, height), BACKGROUND)
        self.draw = ImageDraw.Draw(self.image)
        self.draw.text((PADDING, 26), title, font=_font(34, bold=True), fill=TEXT)

    def header(self, columns):
        y = TITLE_HEIGHT + HEADER_HEIGHT // 2
        for x, label in columns:
            self.draw.text((x, y), label, font=_font(20), fill=MUTED, anchor="lm")
        self.draw.line((PADDING, TITLE_HEIGHT + HEADER_HEIGHT, WIDTH - PADDING, TITLE_HEIGHT + HEADER_HEIGHT),
                       fill=RULE, width=2)

    def row_y(self, index):
        return TITLE_HEIGHT + HEADER_HEIGHT + ROW_HEIGHT * index + ROW_HEIGHT // 2

    def text(self, x, y, value, *, size=24, bold=False, fill=TEXT):
        self.draw.text((x, y), value, font=_font(size, bold), fill=fill, anchor="lm")

    def champion(self, x, y, champions, name, max_width):
        """Icon plus Japanese name, shrinking the name to fit max_width."""
        icon = champions.icon(name)
        if icon:
            tile = Image.open(io.BytesIO(icon)).convert("RGB").resize((ICON, ICON))
            self.image.paste(tile, (x, y - ICON // 2))
        label, size = champions.name(name), 24
        while size > 14 and self.draw.textlength(label, font=_font(size)) > max_width:
            size -= 2
        self.text(x + ICON + 10, y, label, size=size)

    def rule(self, index):
        y = TITLE_HEIGHT + HEADER_HEIGHT + ROW_HEIGHT * (index + 1)
        self.draw.line((PADDING, y, WIDTH - PADDING, y), fill=RULE, width=1)

    def png(self):
        out = io.BytesIO()
        self.image.save(out, format="PNG", optimize=True)
        return out.getvalue()


def games_image(title, records, champions):
    canvas = _Canvas(title, len(records))
    canvas.header([(PADDING, "結果"), (110, "チャンピオン"), (430, "対面"), (720, "KDA@15"),
                   (850, "GD@15"), (970, "CSD@15"), (1090, "KP")])
    for i, record in enumerate(records):
        m, y = record["metrics"], canvas.row_y(i)
        canvas.text(PADDING, y, "勝" if m["win"] else "負", size=28, bold=True, fill=WIN if m["win"] else LOSS)
        canvas.champion(110, y, champions, m["champion"], 250)
        canvas.champion(430, y, champions, m["opponent_champion"], 230)
        canvas.text(720, y, kda(m["kda_15"]))
        canvas.text(850, y, signed(m["gold_diff_15"]), fill=_diff_color(m["gold_diff_15"]))
        canvas.text(970, y, signed(m["cs_diff_15"]), fill=_diff_color(m["cs_diff_15"]))
        canvas.text(1090, y, percent(m["kill_participation"]))
        canvas.rule(i)
    return canvas.png()


def champions_image(title, rows, champions):
    canvas = _Canvas(title, len(rows))
    canvas.header([(PADDING, "チャンピオン"), (420, "試合"), (520, "勝敗"), (660, "勝率"),
                   (780, "平均GD@15"), (930, "平均CSD@15"), (1090, "平均KP")])
    for i, row in enumerate(rows):
        y = canvas.row_y(i)
        gold = None if row["gold_diff_15"] is None else round(row["gold_diff_15"])
        cs = None if row["cs_diff_15"] is None else round(row["cs_diff_15"])
        canvas.champion(PADDING, y, champions, row["champion"], 300)
        canvas.text(420, y, str(row["games"]))
        canvas.text(520, y, f"{row['wins']}-{row['losses']}")
        canvas.text(660, y, percent(row["wins"] / row["games"]))
        canvas.text(780, y, signed(gold), fill=_diff_color(gold))
        canvas.text(930, y, signed(cs), fill=_diff_color(cs))
        canvas.text(1090, y, percent(row["kill_participation"]))
        canvas.rule(i)
    return canvas.png()
