"""
與 Riot Client / VALORANT 伺服器溝通的部分。

資料來源：
- 本機 Riot Client（lockfile）：拿 token、自己的 PUUID、目前狀態（大廳/選角/對戰中）
- pd.{shard}.a.pvp.net：戰績、單場資料、牌位、玩家名稱
- glz-{region}-1.{shard}.a.pvp.net：選角中 / 對戰中的對局資料

這些都是非官方端點，Riot 隨時可能更改。
"""
import base64
import json
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.request

PLATFORM = base64.b64encode(json.dumps({
    "platformType": "PC",
    "platformOS": "Windows",
    "platformOSVersion": "10.0.19042.1.256.64bit",
    "platformChipset": "Unknown",
}).encode()).decode()

# 本機 Riot Client 用的是自簽憑證，只有連 127.0.0.1 時才略過驗證
_LOCAL_SSL = ssl.create_default_context()
_LOCAL_SSL.check_hostname = False
_LOCAL_SSL.verify_mode = ssl.CERT_NONE



class RiotError(Exception):
    pass


class HTTPStatusError(RiotError):
    def __init__(self, code, url):
        super().__init__(f"HTTP {code}: {url}")
        self.code = code


def _request(url, method="GET", headers=None, body=None, local=False, timeout=10):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=dict(headers or {}))
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_LOCAL_SSL if local else None) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise HTTPStatusError(e.code, url) from None
    except urllib.error.URLError as e:
        raise RiotError(f"連線失敗：{e.reason}") from None


class RiotClient:
    TOKEN_TTL = 20 * 60  # token 約 1 小時過期，保守一點每 20 分鐘重拿

    def __init__(self):
        self._lock = threading.Lock()
        self.port = self.password = None
        self.access_token = self.entitlement = self.puuid = None
        self.region = self.shard = self.version = None
        self._token_time = 0
        self._season = None
        self._season_time = 0
        self._ttl_cache = {}  # key -> (expire, value)

    # ---------- 連線 ----------
    @staticmethod
    def _localappdata():
        return os.environ.get("LOCALAPPDATA", "")

    def _read_lockfile(self):
        path = os.path.join(self._localappdata(), "Riot Games", "Riot Client", "Config", "lockfile")
        if not os.path.exists(path):
            raise RiotError("找不到 Riot Client，請先開啟特戰英豪並登入。")
        with open(path, encoding="utf-8") as f:
            parts = f.read().strip().split(":")
        if len(parts) < 5:
            raise RiotError("lockfile 格式不正確，請重開 Riot Client。")
        self.port, self.password = parts[2], parts[3]

    def _local_headers(self):
        auth = base64.b64encode(f"riot:{self.password}".encode()).decode()
        return {"Authorization": f"Basic {auth}"}

    def local(self, path, method="GET"):
        return _request(f"https://127.0.0.1:{self.port}{path}", method,
                        headers=self._local_headers(), local=True, timeout=5)

    def _detect_region_and_version(self):
        log = os.path.join(self._localappdata(), "VALORANT", "Saved", "Logs", "ShooterGame.log")
        text = ""
        if os.path.exists(log):
            with open(log, encoding="utf-8", errors="ignore") as f:
                text = f.read()

        m = re.search(r"https://glz-(.+?)-1\.(.+?)\.a\.pvp\.net", text)
        if m:
            self.region, self.shard = m.group(1), m.group(2)
        else:
            try:
                region = (self.local("/riotclient/region-locale") or {}).get("region", "").lower()
            except RiotError:
                region = ""
            if not region:
                raise RiotError("無法判斷伺服器區域，請先進入一次遊戲大廳。")
            self.region = region
            self.shard = "na" if region in ("na", "latam", "br") else region

        try:
            self.version = _request("https://valorant-api.com/v1/version")["data"]["riotClientVersion"]
        except Exception:
            m = re.search(r"CI server version: (\S+)", text)
            if not m:
                raise RiotError("無法取得遊戲版本號。")
            self.version = m.group(1)

    def connect(self):
        self._read_lockfile()
        try:
            tok = self.local("/entitlements/v1/token")
        except RiotError as e:
            raise RiotError(f"無法連上 Riot Client（{e}）。請確認已登入。") from None
        self.access_token = tok["accessToken"]
        self.entitlement = tok["token"]
        self.puuid = tok["subject"]
        self._detect_region_and_version()
        self._token_time = time.time()

    def ensure(self):
        with self._lock:
            if not self.access_token or time.time() - self._token_time > self.TOKEN_TTL:
                self.connect()

    # ---------- 遠端 API ----------
    def _remote_headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "X-Riot-Entitlements-JWT": self.entitlement,
            "X-Riot-ClientPlatform": PLATFORM,
            "X-Riot-ClientVersion": self.version,
            "User-Agent": "ShooterGame/13 Windows/10.0.19043.1.256.64bit",
        }

    def _remote(self, url, method="GET", body=None):
        self.ensure()
        try:
            return _request(url, method, self._remote_headers(), body)
        except HTTPStatusError as e:
            if e.code in (400, 401, 403):  # token 過期 → 重新連線再試一次
                with self._lock:
                    self.connect()
                return _request(url, method, self._remote_headers(), body)
            raise

    def pd(self, path, method="GET", body=None):
        return self._remote(f"https://pd.{self.shard}.a.pvp.net{path}", method, body)

    def glz(self, path):
        return self._remote(f"https://glz-{self.region}-1.{self.shard}.a.pvp.net{path}")

    def shared(self, path):
        return self._remote(f"https://shared.{self.shard}.a.pvp.net{path}")

    def _cached(self, key, ttl, fn):
        hit = self._ttl_cache.get(key)
        if hit and hit[0] > time.time():
            return hit[1]
        val = fn()
        self._ttl_cache[key] = (time.time() + ttl, val)
        return val

    # ---------- 玩家資料 ----------
    def self_name(self):
        """自己的 Riot ID：直接問本機 Riot Client，不用打遠端。"""
        for path, gn, tl in (("/chat/v1/session", "game_name", "game_tag"),
                             ("/player-account/aliases/v1/active", "game_name", "tag_line")):
            try:
                d = self.local(path) or {}
                if d.get(gn):
                    return f"{d[gn]}#{d.get(tl, '')}"
            except RiotError:
                pass
        return ""

    def friend_names(self):
        """好友列表（本機 Riot Client）：{puuid: 名字#TAG}。一起組隊的人通常都在裡面。"""
        out = {}
        for path in ("/chat/v4/friends", "/chat/v4/presences"):
            try:
                d = self.local(path) or {}
            except RiotError:
                continue
            for f in d.get("friends") or d.get("presences") or []:
                if f.get("puuid") and f.get("game_name"):
                    out[f["puuid"]] = f'{f["game_name"]}#{f.get("game_tag", "")}'
        return out

    def names(self, puuids):
        """查玩家名稱。遠端被擋（403 等）時回傳空的，不讓整個流程失敗。"""
        puuids = [p for p in dict.fromkeys(puuids) if p]
        if not puuids:
            return {}
        out = {}
        if self.puuid in puuids:
            me = self.self_name()
            if me:
                out[self.puuid] = me
        rest = [p for p in puuids if p not in out]
        if rest:
            try:
                res = self.pd("/name-service/v2/players", "PUT", rest) or []
                for r in res:
                    if r.get("GameName"):
                        out[r["Subject"]] = f'{r["GameName"]}#{r.get("TagLine", "")}'
            except RiotError:
                pass
        return out

    def current_season(self):
        if self._season and time.time() - self._season_time < 3600:
            return self._season
        try:
            content = self.shared("/content-service/v3/content") or {}
            for s in content.get("Seasons") or []:
                if s.get("IsActive") and s.get("Type") == "act":
                    self._season, self._season_time = s["ID"], time.time()
                    break
        except RiotError:
            pass
        return self._season

    def rank(self, puuid):
        def fetch():
            data = self.pd(f"/mmr/v1/players/{puuid}") or {}
            comp = (data.get("QueueSkills") or {}).get("competitive") or {}
            seasons = comp.get("SeasonalInfoBySeasonID") or {}
            sid = self.current_season() or (data.get("LatestCompetitiveUpdate") or {}).get("SeasonID")
            cur = seasons.get(sid) or {}
            peak = 0
            for s in seasons.values():
                for tier in (s.get("WinsByTier") or {}):
                    peak = max(peak, int(tier))
            games = cur.get("NumberOfGames", 0) or 0
            wins = cur.get("NumberOfWinsWithPlacements", cur.get("NumberOfWins", 0)) or 0
            return {
                "tier": cur.get("CompetitiveTier", 0) or 0,
                "rr": cur.get("RankedRating", 0) or 0,
                "wins": wins,
                "games": games,
                "peak": peak,
            }
        return self._cached(("rank", puuid), 300, fetch)

    # ---------- 原始資料（給 sync 用） ----------
    def history_ids(self, count=40):
        """分頁抓自己的對局 ID（每頁 20 場）。"""
        self.ensure()
        ids, start = [], 0
        while start < count:
            end = min(start + 20, count)
            res = self.pd(f"/match-history/v1/history/{self.puuid}?startIndex={start}&endIndex={end}") or {}
            batch = [h["MatchID"] for h in res.get("History") or []]
            ids += batch
            if len(batch) < end - start:
                break
            start = end
        return ids

    def match_raw(self, match_id):
        return self.pd(f"/match-details/v1/matches/{match_id}")

    def mmr_raw(self, puuid=None):
        return self.pd(f"/mmr/v1/players/{puuid or self.puuid}")

    def competitive_updates(self, count=40):
        out, start = [], 0
        while start < count:
            end = min(start + 20, count)
            res = self.pd(f"/mmr/v1/players/{self.puuid}/competitiveupdates"
                          f"?startIndex={start}&endIndex={end}&queue=competitive") or {}
            batch = res.get("Matches") or []
            out += batch
            if len(batch) < end - start:
                break
            start = end
        return out

    def is_available(self):
        lock = os.path.join(self._localappdata(), "Riot Games", "Riot Client", "Config", "lockfile")
        if not os.path.exists(lock):
            self.access_token = None
            return False
        try:
            self.ensure()
            return True
        except RiotError:
            return False

    # ---------- 對戰中隊友 ----------
    def session_state(self):
        """回傳 MENUS / PREGAME / INGAME，取不到時回傳 None（只問本機，不打遠端）。"""
        try:
            pres = self.local("/chat/v4/presences") or {}
        except RiotError:
            return None
        for p in pres.get("presences") or []:
            if p.get("puuid") != self.puuid or p.get("product") != "valorant":
                continue
            try:
                priv = json.loads(base64.b64decode(p.get("private") or ""))
            except Exception:
                return None
            return priv.get("sessionLoopState") or (priv.get("matchPresenceData") or {}).get("sessionLoopState")
        return None

    def _match_id(self, kind):
        try:
            return (self.glz(f"/{kind}/v1/players/{self.puuid}") or {}).get("MatchID")
        except HTTPStatusError as e:
            if e.code == 404:
                return None
            raise

    def live(self, include_enemies=True, rank_fallback=None):
        """選角中只有隊友（Riot 選角時本來就不給敵方資料）；對戰中可以加上敵方。
        開了「隱藏名稱」的人：不論隊友或敵方，都不查名字、牌位、等級。"""
        self.ensure()
        state = self.session_state()
        players, phase, map_id, queue = [], None, None, None

        if state in ("PREGAME", None):
            mid = self._match_id("pregame")
            if mid:
                m = self.glz(f"/pregame/v1/matches/{mid}") or {}
                phase, map_id, queue = "pregame", m.get("MapID"), m.get("QueueID")
                for p in (m.get("AllyTeam") or {}).get("Players") or []:
                    players.append({
                        "puuid": p.get("Subject"), "side": "ally",
                        "agent": (p.get("CharacterID") or "").lower(),
                        "locked": p.get("CharacterSelectionState") == "locked",
                        "identity": p.get("PlayerIdentity") or {},
                    })

        if not phase and state in ("INGAME", None):
            mid = self._match_id("core-game")
            if mid:
                m = self.glz(f"/core-game/v1/matches/{mid}") or {}
                phase, map_id = "ingame", m.get("MapID")
                queue = (m.get("MatchmakingData") or {}).get("QueueID") or ""
                all_players = m.get("Players") or []
                my_team = next((p.get("TeamID") for p in all_players if p.get("Subject") == self.puuid), None)
                for p in all_players:
                    side = "ally" if p.get("TeamID") == my_team else "enemy"
                    if side == "enemy" and not include_enemies:
                        continue
                    players.append({
                        "puuid": p.get("Subject"), "side": side,
                        "agent": (p.get("CharacterID") or "").lower(),
                        "locked": True,
                        "identity": p.get("PlayerIdentity") or {},
                    })

        if not phase:
            return {"phase": "menus", "state": state}

        # 尊重「隱藏名稱」：開了的人不查名字、不查牌位（自己除外）
        visible = [p["puuid"] for p in players
                   if p["puuid"] == self.puuid or not p["identity"].get("Incognito")]
        names = self._cached(("names", tuple(sorted(visible))), 600, lambda: self.names(visible))

        out = []
        for p in players:
            ident = p["identity"]
            is_me = p["puuid"] == self.puuid
            hidden = ident.get("Incognito") and not is_me
            row = {
                "me": is_me, "side": p["side"],
                "hidden": bool(hidden),
                "agent": p["agent"],
                "locked": p["locked"],
                "level": None if (hidden or ident.get("HideAccountLevel")) else ident.get("AccountLevel"),
                "name": None if hidden else names.get(p["puuid"]),
                "rank": None,
            }
            if not hidden:
                try:
                    row["rank"] = self.rank(p["puuid"])
                except RiotError:
                    if rank_fallback:
                        row["rank"] = rank_fallback(p["puuid"])
            out.append(row)
        out.sort(key=lambda r: (r["side"] != "ally", not r["me"]))
        return {"phase": phase, "map": map_id, "queue": queue, "players": out}
