"""In-memory stand-ins for the Riot client and the data bucket."""
import copy


class FakeRiot:
    def __init__(self, matches=None, timelines=None, puuid="puuid-me", key_id="key-1"):
        self.key_id = key_id
        self.matches = matches or {}       # match id -> match payload
        self.timelines = timelines or {}   # match id -> timeline payload
        self._puuid = puuid
        self.calls = []

    def puuid(self, account):
        self.calls.append(("puuid", account.game_name))
        return self._puuid

    def match_ids(self, region, puuid, *, start_time, end_time):
        self.calls.append(("match_ids", start_time, end_time))
        ids = [mid for mid, m in self.matches.items()
               if start_time <= m["info"]["gameStartTimestamp"] // 1000 <= end_time]
        return sorted(ids, reverse=True)

    def match(self, region, match_id):
        self.calls.append(("match", match_id))
        return copy.deepcopy(self.matches[match_id])

    def timeline(self, region, match_id):
        self.calls.append(("timeline", match_id))
        return copy.deepcopy(self.timelines[match_id])


class FakeBucket:
    def __init__(self):
        self.objects = {}
        self.writes = []

    def read_json(self, path):
        return copy.deepcopy(self.objects.get(path))

    def read_ndjson(self, path):
        return copy.deepcopy(self.objects.get(path, []))

    def write_json(self, path, obj):
        self.writes.append(path)
        self.objects[path] = copy.deepcopy(obj)

    def write_ndjson(self, path, records):
        self.writes.append(path)
        self.objects[path] = copy.deepcopy(records)

    def write_bytes(self, path, data, content_type):
        self.writes.append(path)
        self.objects[path] = data

    def write_gzip_json_once(self, path, obj):
        if path in self.objects:
            return False
        self.writes.append(path)
        self.objects[path] = copy.deepcopy(obj)
        return True


class FakeChampions:
    """Data Dragon stand-in: Japanese names from a small table, a tiny icon for known ones."""
    NAMES = {"Ahri": "アーリ", "Zed": "ゼド", "Garen": "ガレン"}

    def __init__(self):
        from io import BytesIO
        from PIL import Image
        out = BytesIO()
        Image.new("RGB", (8, 8), (200, 100, 50)).save(out, format="PNG")
        self.icon_png = out.getvalue()

    def name(self, champion):
        return self.NAMES.get(champion, champion or "-")

    def icon(self, champion):
        return self.icon_png if champion in self.NAMES else None


class FakeX:
    """Records uploads and posts; post ids are sequential strings."""

    def __init__(self, fail_on_post=None):
        self.uploads, self.posts = [], []
        self.fail_on_post = fail_on_post

    def upload_png(self, data):
        self.uploads.append(data)
        return f"media-{len(self.uploads)}"

    def post(self, text, *, reply_to, media_ids=()):
        if self.fail_on_post is not None and len(self.posts) == self.fail_on_post:
            raise RuntimeError("X failed")
        self.posts.append({"text": text, "reply_to": reply_to, "media_ids": list(media_ids)})
        return f"post-{len(self.posts)}"
