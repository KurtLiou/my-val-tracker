"""
HenrikDev 非官方 API：沒開遊戲時用來抓自己的戰績。
需要到 https://api.henrikdev.xyz/dashboard/ 申請免費 API key，貼到 App 的「設定」頁。
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.henrikdev.xyz"


class HenrikError(Exception):
    pass


class HenrikClient:
    def __init__(self, key):
        if not key:
            raise HenrikError("還沒設定 HenrikDev API key（設定頁可以填）。")
        self.key = key

    def _get(self, path, params=None, retry=True):
        url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
        req = urllib.request.Request(url, headers={"Authorization": self.key, "User-Agent": "valtracker-personal"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read()).get("data")
        except urllib.error.HTTPError as e:
            if e.code == 429 and retry:  # 被限速，等一下再試一次
                time.sleep(8)
                return self._get(path, params, retry=False)
            try:
                msg = json.loads(e.read()).get("errors", [{}])[0].get("message", "")
            except Exception:
                msg = ""
            if e.code in (401, 403):
                raise HenrikError("HenrikDev API key 無效或權限不足。") from None
            if e.code == 404:
                raise HenrikError("HenrikDev 找不到這個帳號，請確認 Riot ID。") from None
            raise HenrikError(f"HenrikDev 錯誤 {e.code} {msg}".strip()) from None
        except urllib.error.URLError as e:
            raise HenrikError(f"連不上 HenrikDev：{e.reason}") from None

    def account(self, riot_id):
        if "#" not in riot_id:
            raise HenrikError("Riot ID 格式要像「名字#TAG」。")
        name, tag = riot_id.rsplit("#", 1)
        q = lambda s: urllib.parse.quote(s.strip(), safe="")
        return self._get(f"/valorant/v1/account/{q(name)}/{q(tag)}")

    def account_by_puuid(self, puuid):
        return self._get(f"/valorant/v2/by-puuid/account/{puuid}")

    def matches(self, region, puuid, count=40):
        out, start = [], 0
        while start < count:
            size = min(10, count - start)
            batch = self._get(f"/valorant/v4/by-puuid/matches/{region}/pc/{puuid}",
                              {"size": size, "start": start}) or []
            out += batch
            if len(batch) < size:
                break
            start += size
        return out

    def mmr(self, region, puuid):
        return self._get(f"/valorant/v3/by-puuid/mmr/{region}/pc/{puuid}")

    def mmr_history(self, region, puuid):
        return self._get(f"/valorant/v2/by-puuid/mmr-history/{region}/pc/{puuid}")
