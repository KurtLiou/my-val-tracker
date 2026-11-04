"""
把 Riot 原始對局資料和 HenrikDev v4 資料轉成同一種格式，後面的分析只認這一種。

統一格式：
match = {
  v, id, src, start(ms), len(ms), queue, map, season, completed,
  teams:   {teamId: {won, rw}},
  players: [{id, name, tag, team, party, agent, tier, level, score, k, d, a, hs, bs, ls, casts:[c,q,e,x]}],
  rounds:  [{win, result, planter, defuser, site, dmg:[[from,to,dmg,hs,bs,ls]], econ:{puuid:[loadout, spent]}}],
  kills:   [{r, t, k, v, a:[...], w, wt, vx, vy, pos:[[puuid, x, y], ...]}],   (位置是遊戲座標)
}
"""
from datetime import datetime

VERSION = 2  # v2：加入擊殺位置與玩家位置（2D 回放用）


def _result(s):
    s = (s or "").lower()
    for key, val in (("defus", "defuse"), ("deton", "detonate"), ("elimin", "elim"),
                     ("expire", "time"), ("time", "time"), ("surrend", "surrender")):
        if key in s:
            return val
    return s or "other"


def _iso_ms(s):
    try:
        return int(datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp() * 1000)
    except (ValueError, TypeError):
        return None


# ---------------- Riot 原始格式 ----------------
def from_riot(raw):
    info = raw.get("matchInfo") or {}
    players = []
    for p in raw.get("players") or []:
        st = p.get("stats") or {}
        ac = st.get("abilityCasts") or {}
        players.append({
            "id": p.get("subject"), "name": p.get("gameName") or "", "tag": p.get("tagLine") or "",
            "team": p.get("teamId"), "party": p.get("partyId"),
            "agent": (p.get("characterId") or "").lower(),
            "tier": p.get("competitiveTier") or 0, "level": p.get("accountLevel"),
            "score": st.get("score") or 0, "k": st.get("kills") or 0,
            "d": st.get("deaths") or 0, "a": st.get("assists") or 0,
            "hs": 0, "bs": 0, "ls": 0,
            "casts": [ac.get("grenadeCasts") or 0, ac.get("ability1Casts") or 0,
                      ac.get("ability2Casts") or 0, ac.get("ultimateCasts") or 0],
        })
    by_id = {p["id"]: p for p in players}

    rounds, kills = [], []
    for i, r in enumerate(raw.get("roundResults") or []):
        dmg, econ = [], {}
        for ps in r.get("playerStats") or []:
            sid = ps.get("subject")
            for d in ps.get("damage") or []:
                hs, bs, ls = d.get("headshots", 0), d.get("bodyshots", 0), d.get("legshots", 0)
                dmg.append([sid, d.get("receiver"), d.get("damage", 0), hs, bs, ls])
                if sid in by_id:
                    by_id[sid]["hs"] += hs
                    by_id[sid]["bs"] += bs
                    by_id[sid]["ls"] += ls
            e = ps.get("economy") or {}
            econ[sid] = [e.get("loadoutValue"), e.get("spent")]
            for k in ps.get("kills") or []:
                fd = k.get("finishingDamage") or {}
                vl = k.get("victimLocation") or {}
                kills.append({
                    "r": i, "t": k.get("roundTime") or 0,
                    "k": k.get("killer"), "v": k.get("victim"), "a": k.get("assistants") or [],
                    "w": (fd.get("damageItem") or "").lower(), "wt": (fd.get("damageType") or "").lower(),
                    "vx": vl.get("x"), "vy": vl.get("y"),
                    "pos": [[pl.get("subject"), (pl.get("location") or {}).get("x"), (pl.get("location") or {}).get("y")]
                            for pl in k.get("playerLocations") or [] if pl.get("location")],
                })
        pl = r.get("plantLocation") or {}
        rounds.append({
            "win": r.get("winningTeam"), "result": _result(r.get("roundResult")),
            "planter": r.get("bombPlanter"), "defuser": r.get("bombDefuser"),
            "site": r.get("plantSite") or None, "dmg": dmg, "econ": econ,
            "plant_xy": [pl.get("x"), pl.get("y")] if pl.get("x") or pl.get("y") else None,
        })

    teams = {t.get("teamId"): {"won": bool(t.get("won")), "rw": t.get("roundsWon") or 0}
             for t in raw.get("teams") or []}
    return {
        "v": VERSION, "id": info.get("matchId"), "src": "riot",
        "start": info.get("gameStartMillis"), "len": info.get("gameLengthMillis"),
        "queue": info.get("queueID") or info.get("queueId") or "",
        "map": info.get("mapId"), "season": info.get("seasonId"),
        "completed": info.get("isCompleted", True),
        "teams": teams, "players": players, "rounds": rounds, "kills": kills,
    }


# ---------------- HenrikDev v4 ----------------
def from_henrik(m):
    meta = m.get("metadata") or {}
    players = []
    for p in m.get("players") or []:
        st = p.get("stats") or {}
        ac = p.get("ability_casts") or {}
        players.append({
            "id": p.get("puuid"), "name": p.get("name") or "", "tag": p.get("tag") or "",
            "team": p.get("team_id"), "party": p.get("party_id"),
            "agent": ((p.get("agent") or {}).get("id") or "").lower(),
            "tier": (p.get("tier") or {}).get("id") or 0, "level": p.get("account_level"),
            "score": st.get("score") or 0, "k": st.get("kills") or 0,
            "d": st.get("deaths") or 0, "a": st.get("assists") or 0,
            "hs": st.get("headshots") or 0, "bs": st.get("bodyshots") or 0, "ls": st.get("legshots") or 0,
            "casts": [ac.get("grenade") or 0, ac.get("ability1") or 0,
                      ac.get("ability2") or 0, ac.get("ultimate") or 0],
        })

    rounds = []
    for r in m.get("rounds") or []:
        dmg, econ = [], {}
        for s in r.get("stats") or []:
            sid = (s.get("player") or {}).get("puuid")
            for d in s.get("damage_events") or []:
                to = (d.get("player") or {}).get("puuid") or d.get("receiver_puuid")
                dmg.append([sid, to, d.get("damage", 0), d.get("headshots", 0),
                            d.get("bodyshots", 0), d.get("legshots", 0)])
            e = s.get("economy") or {}
            econ[sid] = [e.get("loadout_value"), None]
        plant, defuse = r.get("plant") or {}, r.get("defuse") or {}
        ploc = plant.get("location") or {}
        rounds.append({
            "win": r.get("winning_team"), "result": _result(r.get("result")),
            "planter": (plant.get("player") or {}).get("puuid"),
            "defuser": (defuse.get("player") or {}).get("puuid"),
            "site": plant.get("site"), "dmg": dmg, "econ": econ,
            "plant_xy": [ploc.get("x"), ploc.get("y")] if ploc else None,
        })

    raw_kills = m.get("kills") or []
    # 有些版本 round 從 1 開始，從 0 開始才對得上 rounds 陣列
    offset = 1 if raw_kills and rounds and max(k.get("round", 0) for k in raw_kills) >= len(rounds) else 0
    kills = []
    for k in raw_kills:
        w = k.get("weapon") or {}
        kills.append({
            "r": max(0, (k.get("round") or 0) - offset), "t": k.get("time_in_round_in_ms") or 0,
            "k": (k.get("killer") or {}).get("puuid"), "v": (k.get("victim") or {}).get("puuid"),
            "a": [a.get("puuid") for a in k.get("assistants") or [] if a.get("puuid")],
            "w": (w.get("id") or "").lower(), "wt": (w.get("type") or "").lower(),
            "vx": (k.get("location") or {}).get("x"), "vy": (k.get("location") or {}).get("y"),
            "pos": [[(pl.get("player") or {}).get("puuid"), (pl.get("location") or {}).get("x"),
                     (pl.get("location") or {}).get("y")] for pl in k.get("player_locations") or []],
        })

    teams = {t.get("team_id"): {"won": bool(t.get("won")), "rw": (t.get("rounds") or {}).get("won") or 0}
             for t in m.get("teams") or []}
    return {
        "v": VERSION, "id": meta.get("match_id"), "src": "henrik",
        "start": _iso_ms(meta.get("started_at")), "len": meta.get("game_length_in_ms"),
        "queue": (meta.get("queue") or {}).get("id") or "",
        "map": (meta.get("map") or {}).get("id"), "season": (meta.get("season") or {}).get("id"),
        "completed": meta.get("is_completed", True),
        "teams": teams, "players": players, "rounds": rounds, "kills": kills,
    }


# ---------------- 牌位 / RR ----------------
def rank_from_henrik(d):
    d = d or {}
    cur = d.get("current") or {}
    peak = d.get("peak") or {}
    seasonal = d.get("seasonal") or []
    last = seasonal[-1] if seasonal else {}
    return {
        "tier": (cur.get("tier") or {}).get("id") or 0, "rr": cur.get("rr") or 0,
        "peak": (peak.get("tier") or {}).get("id") or 0,
        "wins": last.get("wins") or 0, "games": last.get("games") or 0,
    }


def rr_from_riot(updates):
    return [{
        "match_id": u.get("MatchID"), "date": u.get("MatchStartTime"),
        "tier": u.get("TierAfterUpdate") or 0, "rr": u.get("RankedRatingAfterUpdate") or 0,
        "change": u.get("RankedRatingEarned") or 0, "map": u.get("MapID"),
    } for u in updates or []]


def rr_from_henrik(data):
    return [{
        "match_id": h.get("match_id"), "date": _iso_ms(h.get("date")),
        "tier": (h.get("tier") or {}).get("id") or 0, "rr": h.get("rr") or 0,
        "change": h.get("last_change") or 0, "map": (h.get("map") or {}).get("id"),
    } for h in (data or {}).get("history") or []]
