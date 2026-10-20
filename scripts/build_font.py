"""Builds the subset Noto Sans JP fonts bundled with the function (cloud_function/bot/assets/).

Only the glyphs the images can need are kept, so the fonts stay small: printable ASCII,
Japanese punctuation, hiragana, katakana, every character of the current Japanese
champion names (Data Dragon) and every non-ASCII character used in cloud_function/bot.
Re-run after new champions are released:

  .venv/Scripts/python scripts/build_font.py      (needs fonttools, see requirements-dev.txt)

Noto Sans JP is licensed under the SIL Open Font License 1.1 (copied next to the fonts).
"""
import json
import pathlib
import tempfile
import urllib.request

from fontTools import subset

NOTO_TAG = "Sans2.004"
NOTO_REPO = f"https://github.com/notofonts/noto-cjk/raw/{NOTO_TAG}"
NOTO_BASE = f"{NOTO_REPO}/Sans"
WEIGHTS = ["Regular", "Bold"]
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "cloud_function" / "bot" / "assets"
UA = {"User-Agent": "result-tweet-bot font builder"}


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as response:
        return response.read()


def champion_names():
    version = json.loads(fetch("https://ddragon.leagueoflegends.com/api/versions.json"))[0]
    data = json.loads(fetch(f"https://ddragon.leagueoflegends.com/cdn/{version}/data/ja_JP/champion.json"))
    return version, [c["name"] for c in data["data"].values()]


def characters(names):
    chars = {chr(c) for c in range(0x20, 0x7F)}
    chars |= set("、。・ー〜「」『』（）！？％＋－／：　…―")
    chars |= {chr(c) for c in range(0x3041, 0x3097)}  # hiragana
    chars |= {chr(c) for c in range(0x30A1, 0x30FB)}  # katakana
    chars |= set("".join(names))
    for source in (ROOT / "cloud_function" / "bot").rglob("*.py"):
        chars |= {ch for ch in source.read_text(encoding="utf-8") if ord(ch) > 0x7F}
    return "".join(sorted(chars))


def main():
    version, names = champion_names()
    text = characters(names)
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for weight in WEIGHTS:
            source = pathlib.Path(tmp) / f"NotoSansJP-{weight}.otf"
            source.write_bytes(fetch(f"{NOTO_BASE}/SubsetOTF/JP/NotoSansJP-{weight}.otf"))
            target = OUT / f"NotoSansJP-{weight}-subset.otf"
            options = subset.Options()
            options.layout_features = ["*"]
            options.name_IDs = ["*"]
            font = subset.load_font(str(source), options)
            subsetter = subset.Subsetter(options)
            subsetter.populate(text=text)
            subsetter.subset(font)
            subset.save_font(font, str(target), options)
            font.close()  # release the source file so the temporary directory can be removed (Windows)
            print(f"{target.relative_to(ROOT)}: {target.stat().st_size // 1024} KB")
    (OUT / "OFL.txt").write_bytes(fetch(f"{NOTO_REPO}/LICENSE"))
    print(f"{len(text)} characters, {len(names)} champions (Data Dragon {version}), Noto {NOTO_TAG}")


if __name__ == "__main__":
    main()
