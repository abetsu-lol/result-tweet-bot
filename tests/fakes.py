"""In-memory stand-ins for the Riot client and the data bucket."""
import copy


class FakeRiot:
    def __init__(self, matches=None, timelines=None, puuid="puuid-me"):
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

    def write_gzip_json_once(self, path, obj):
        if path in self.objects:
            return False
        self.writes.append(path)
        self.objects[path] = copy.deepcopy(obj)
        return True
