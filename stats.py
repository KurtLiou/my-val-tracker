"""
戰績分析。輸入：統一格式的對局（見 normalize.py）。
除了 Tracker 的基本數據，還多算：KAST、首殺/首死、交易擊殺、殘局、多殺、攻守勝率、
經濟、技能使用、武器、拍檔、時段熱力圖、徽章、連勝連敗、狀態提醒、每張地圖推薦特務。
"""
from collections import defaultdict
from datetime import datetime

TRADE_WINDOW_MS = 5000
HALF_LENGTH = {"competitive": 12, "unrated": 12, "premier": 12, "newmap": 12,
               "swiftplay": 4, "spikerush": 3}


def _div(a, b, nd=2):
    return round(a / b, nd) if b else None


def _pct(a, b, nd=1):
    return round(a / b * 100, nd) if b else None


def attacking_team(queue, rnd):
    """回傳這回合進攻方（Red/Blue）。Red 上半場進攻。"""
    half = HALF_LENGTH.get(queue)
    if not half:
        return None
    if rnd < half:
        return "Red"
    if rnd < half * 2:
        return "Blue"
    return "Red" if (rnd - half * 2) % 2 == 0 else "Blue"  # 延長賽每回合換邊


# ---------------- 單場 ----------------
def match_summary(m, me):
    players = m.get("players") or []
    my = next((p for p in players if p["id"] == me), None)
    if not my:
        return None
    team = my["team"]
    rounds = m.get("rounds") or []
    R = len(rounds)
    roster = defaultdict(set)
    for p in players:
        roster[p["team"]].add(p["id"])
    team_of = {p["id"]: p["team"] for p in players}

    kills_by_round = defaultdict(list)
    for k in m.get("kills") or []:
        kills_by_round[k["r"]].append(k)

    dealt = recv = 0
    fk = fd = traded_deaths = trade_kills = kast_rounds = 0
    multi = defaultdict(int)
    clutch_att, clutch_won = defaultdict(int), defaultdict(int)
    atk_p = atk_w = def_p = def_w = 0
    loadouts, spends = [], []
    plants = defuses = 0
    round_log = []

    for i, r in enumerate(rounds):
        for f, t, dmg, *_ in r.get("dmg") or []:
            if f == me and team_of.get(t) != team:
                dealt += dmg
            if t == me and team_of.get(f) != team:
                recv += dmg
        e = (r.get("econ") or {}).get(me) or [None, None]
        if e[0] is not None:
            loadouts.append(e[0])
        if e[1] is not None:
            spends.append(e[1])
        if r.get("planter") == me:
            plants += 1
        if r.get("defuser") == me:
            defuses += 1

        ks = sorted(kills_by_round.get(i, []), key=lambda k: k["t"])
        my_kills = [k for k in ks if k["k"] == me and team_of.get(k["v"]) != team]
        my_death = next((k for k in ks if k["v"] == me), None)
        assisted = any(me in (k.get("a") or []) for k in ks)
        if ks:
            if ks[0]["k"] == me:
                fk += 1
            elif ks[0]["v"] == me:
                fd += 1

        traded = False
        if my_death:
            killer = my_death["k"]
            traded = any(k["v"] == killer and team_of.get(k["k"]) == team and k["k"] != me
                         and 0 <= k["t"] - my_death["t"] <= TRADE_WINDOW_MS for k in ks)
            traded_deaths += traded
        for k in my_kills:  # 我幫隊友報仇
            trade_kills += any(d["k"] == k["v"] and team_of.get(d["v"]) == team and d["v"] != me
                               and 0 <= k["t"] - d["t"] <= TRADE_WINDOW_MS for d in ks)
        if my_kills or assisted or not my_death or traded:
            kast_rounds += 1
        if len(my_kills) >= 2:
            multi[min(len(my_kills), 5)] += 1

        # 殘局：隊上只剩我一個人時，對面還有幾個
        alive = {t: set(ids) for t, ids in roster.items()}
        vs = None
        for k in ks:
            alive.get(team_of.get(k["v"]), set()).discard(k["v"])
            mine = alive.get(team, set())
            if vs is None and mine == {me}:
                vs = sum(len(ids) for t, ids in alive.items() if t != team)
        won = r.get("win") == team
        if vs:
            clutch_att[vs] += 1
            clutch_won[vs] += won

        side = None
        atk = attacking_team(m.get("queue"), i)
        if atk:
            side = "atk" if atk == team else "def"
            if side == "atk":
                atk_p += 1
                atk_w += won
            else:
                def_p += 1
                def_w += won
        round_log.append({"won": won, "result": r.get("result"), "k": len(my_kills),
                          "died": bool(my_death), "side": side, "clutch": vs if (vs and won) else None,
                          "fk": bool(ks and ks[0]["k"] == me), "plant": r.get("planter") == me,
                          "site": r.get("site")})

    # 武器
    weapons = defaultdict(int)
    for k in m.get("kills") or []:
        if k["k"] == me and team_of.get(k["v"]) != team:
            weapons[k.get("w") or k.get("wt") or "unknown"] += 1

    teams = m.get("teams") or {}
    my_t = teams.get(team) or {}
    others = [v for t, v in teams.items() if t != team]
    if len(teams) == 2:
        won = my_t.get("won")
        draw = not won and not others[0].get("won")
        score = f'{my_t.get("rw", 0)}:{others[0].get("rw", 0)}'
    else:  # 死鬥等個人模式：分數最高者勝
        top = max(players, key=lambda p: p["k"])
        won, draw, score = top["id"] == me, False, None
    if draw:
        won = None

    acs_all = {p["id"]: (p["score"] / R if R else 0) for p in players}
    rounds_played = R or 1
    shots = my["hs"] + my["bs"] + my["ls"]
    party_ids = [p["id"] for p in players if my.get("party") and p.get("party") == my["party"] and p["id"] != me]
    acs = round(my["score"] / R) if R else None
    is_mvp = R and acs_all[me] == max(acs_all.values())
    is_team_mvp = R and acs_all[me] == max(v for k, v in acs_all.items() if team_of.get(k) == team)

    return {
        "id": m["id"], "start": m.get("start"), "len": m.get("len"), "queue": m.get("queue"),
        "map": m.get("map"), "agent": my["agent"], "tier": my["tier"], "src": m.get("src"),
        "won": won, "draw": draw, "score": score,
        "k": my["k"], "d": my["d"], "a": my["a"], "rounds": R,
        "kd": _div(my["k"], my["d"]) if my["d"] else float(my["k"]),
        "hs": _pct(my["hs"], shots), "adr": round(dealt / R) if R and dealt else None,
        "acs": acs, "dd": round((dealt - recv) / R) if R else None,
        "kast": _pct(kast_rounds, R) if R else None,
        "fk": fk, "fd": fd, "trades": trade_kills, "traded": traded_deaths,
        "multi": {str(k): v for k, v in multi.items()},
        "clutch_att": {str(k): v for k, v in clutch_att.items()},
        "clutch_won": {str(k): v for k, v in clutch_won.items()},
        "atk": [atk_w, atk_p], "def": [def_w, def_p],
        "loadout": round(sum(loadouts) / len(loadouts)) if loadouts else None,
        "spent": round(sum(spends) / len(spends)) if spends else None,
        "plants": plants, "defuses": defuses,
        "casts": [round(c / rounds_played, 2) for c in my["casts"]] if R else None,
        "weapons": dict(weapons), "party": party_ids,
        "mvp": bool(is_mvp), "team_mvp": bool(is_team_mvp) and not is_mvp,
        "round_log": round_log,
        "_dealt": dealt, "_recv": recv, "_hs": my["hs"], "_shots": shots,
        "_kast": kast_rounds, "_score": my["score"],
    }


def _side(pid, me, my_team, team_of):
    if pid == me:
        return "me"
    return "ally" if team_of.get(pid) == my_team else "enemy"


def replay_data(m, me):
    """2D 回放用：每次擊殺當下，每個人的位置（遊戲座標）。只放特務，不放其他人的名字。"""
    my = next((p for p in m["players"] if p["id"] == me), None)
    if not my:
        return None
    team_of = {p["id"]: p["team"] for p in m["players"]}
    agent_of = {p["id"]: p["agent"] for p in m["players"]}
    idx = {p["id"]: i for i, p in enumerate(m["players"])}
    kills = []
    for k in sorted(m.get("kills") or [], key=lambda k: (k["r"], k["t"])):
        if k.get("vx") is None and not k.get("pos"):
            continue
        pos = {pid: (x, y) for pid, x, y in k.get("pos") or [] if x is not None}
        kills.append({
            "r": k["r"], "t": k["t"], "w": k.get("w"),
            "k": idx.get(k["k"]), "v": idx.get(k["v"]),
            "ks": _side(k["k"], me, my["team"], team_of), "vs": _side(k["v"], me, my["team"], team_of),
            "kxy": pos.get(k["k"]), "vxy": [k["vx"], k["vy"]] if k.get("vx") is not None else pos.get(k["v"]),
            "pos": [[idx.get(pid), x, y] for pid, (x, y) in pos.items() if pid in idx],
        })
    if not kills:
        return None
    return {
        "players": [{"agent": agent_of[p["id"]], "side": _side(p["id"], me, my["team"], team_of)}
                    for p in m["players"]],
        "kills": kills,
        "plants": [[i, r["plant_xy"][0], r["plant_xy"][1], r.get("site")]
                   for i, r in enumerate(m.get("rounds") or []) if r.get("plant_xy")],
        "rounds": [r.get("win") == my["team"] for r in m.get("rounds") or []],
    }


def map_heat(matches, me, map_id):
    """某張地圖上：你擊殺的位置、你陣亡的位置（攻 / 守分開）。"""
    out = {"kills": [], "deaths": [], "games": 0}
    for m in matches:
        if map_id and m.get("map") != map_id:
            continue
        my = next((p for p in m["players"] if p["id"] == me), None)
        if not my:
            continue
        out["games"] += 1
        for k in m.get("kills") or []:
            atk = attacking_team(m.get("queue"), k["r"])
            side = None if not atk else ("atk" if atk == my["team"] else "def")
            pos = {pid: (x, y) for pid, x, y in k.get("pos") or [] if x is not None}
            if k["k"] == me and k.get("vx") is not None:
                out["kills"].append([k["vx"], k["vy"], side])
            if k["v"] == me:
                xy = (k["vx"], k["vy"]) if k.get("vx") is not None else pos.get(me)
                if xy:
                    out["deaths"].append([xy[0], xy[1], side])
    return out


def match_detail(m, me, known=None):
    """單場詳細：計分板 + 回合時間軸。其他玩家只顯示特務，名稱只顯示和你同隊伍組隊的人。"""
    s = match_summary(m, me)
    if not s:
        return None
    known = known or {}
    my = next(p for p in m["players"] if p["id"] == me)
    R = len(m.get("rounds") or []) or None
    dealt = defaultdict(int)
    team_of = {p["id"]: p["team"] for p in m["players"]}
    for r in m.get("rounds") or []:
        for f, t, dmg, *_ in r.get("dmg") or []:
            if team_of.get(f) != team_of.get(t):
                dealt[f] += dmg
    board = []
    for p in m["players"]:
        is_me = p["id"] == me
        in_party = bool(my.get("party")) and p.get("party") == my["party"]
        shots = p["hs"] + p["bs"] + p["ls"]
        board.append({
            "me": is_me, "ally": p["team"] == my["team"], "party": in_party and not is_me,
            "name": (f'{p["name"]}#{p["tag"]}' if p["name"] else known.get(p["id"])) if (is_me or in_party) else None,
            "agent": p["agent"], "tier": p["tier"] if (is_me or in_party) else None,
            "k": p["k"], "d": p["d"], "a": p["a"],
            "acs": round(p["score"] / R) if R else None,
            "adr": round(dealt[p["id"]] / R) if R and dealt[p["id"]] else None,
            "hs": _pct(p["hs"], shots),
        })
    board.sort(key=lambda b: (not b["ally"], -(b["acs"] or b["k"])))
    s["board"] = board
    s["replay"] = replay_data(m, me)
    for key in [k for k in s if k.startswith("_")]:
        s.pop(key)
    return s


# ---------------- 多場彙總 ----------------
BADGES = [
    ("ace", "ACE 大師", "打出過 5 殺"),
    ("clutch", "殘局之王", "贏下 1v2 以上的殘局"),
    ("headhunter", "爆頭機器", "單場爆頭率 35% 以上"),
    ("mvp", "全場 MVP", "拿過全場最高 ACS"),
    ("entry", "開路先鋒", "單場 4 次以上首殺"),
    ("planter", "埋包專家", "單場埋包 4 次以上"),
    ("defuser", "拆彈小天使", "拆包成功過"),
    ("wall", "人肉盾牌", "單場 KAST 90% 以上"),
    ("streak", "連勝火車", "連贏 3 場以上"),
    ("grinder", "肝帝", "一天打 6 場以上"),
]


def rr_forecast(hist, rank):
    """照最近的 RR 變化，估計幾場後升 / 掉一階。"""
    recent = [h.get("change") or 0 for h in (hist or [])[-20:]]
    if len(recent) < 5 or not rank or not rank.get("tier"):
        return None
    avg = sum(recent) / len(recent)
    rr = rank.get("rr") or 0
    if avg > 0.5:
        return {"dir": "up", "avg": round(avg, 1), "games": int(max(1, -(-(100 - rr) // avg))), "next": rank["tier"] + 1}
    if avg < -0.5:
        return {"dir": "down", "avg": round(avg, 1), "games": int(max(1, -(-(rr + 1) // -avg))), "next": rank["tier"] - 1}
    return {"dir": "flat", "avg": round(avg, 1)}


def aggregate(matches, me, profile=None, queue="all", known=None):
    sums = []
    for m in matches:
        if queue != "all" and m.get("queue") != queue:
            continue
        s = match_summary(m, me)
        if s:
            sums.append(s)
    sums.sort(key=lambda s: s.get("start") or 0, reverse=True)

    def block(ss):
        k = sum(s["k"] for s in ss)
        d = sum(s["d"] for s in ss)
        a = sum(s["a"] for s in ss)
        rs = [s for s in ss if s["rounds"]]
        R = sum(s["rounds"] for s in rs)
        decided = [s for s in ss if s["won"] is not None]
        wins = sum(1 for s in decided if s["won"])
        return {
            "games": len(ss), "wins": wins, "losses": len(decided) - wins,
            "winrate": _pct(wins, len(decided), 0),
            "k": k, "d": d, "a": a,
            "kd": _div(k, d), "kda": _div(k + a, d),
            "hs": _pct(sum(s["_hs"] for s in ss), sum(s["_shots"] for s in ss)),
            "adr": round(sum(s["_dealt"] for s in rs) / R) if R else None,
            "acs": round(sum(s["_score"] for s in rs) / R) if R else None,
            "dd": round(sum(s["_dealt"] - s["_recv"] for s in rs) / R) if R else None,
            "kast": _pct(sum(s["_kast"] for s in rs), R),
            "kpr": _div(sum(s["k"] for s in rs), R),
            "rounds": R,
        }

    overall = block(sums)
    rs = [s for s in sums if s["rounds"]]
    R = overall["rounds"]
    fk, fd = sum(s["fk"] for s in rs), sum(s["fd"] for s in rs)
    multi = defaultdict(int)
    catt, cwon = defaultdict(int), defaultdict(int)
    for s in sums:
        for key, v in s["multi"].items():
            multi[key] += v
        for key, v in s["clutch_att"].items():
            catt[key] += v
        for key, v in s["clutch_won"].items():
            cwon[key] += v
    atk = [sum(s["atk"][0] for s in sums), sum(s["atk"][1] for s in sums)]
    dfn = [sum(s["def"][0] for s in sums), sum(s["def"][1] for s in sums)]
    loads = [s["loadout"] for s in sums if s["loadout"]]
    casts = [s["casts"] for s in sums if s["casts"]]

    extra = {
        "fk": fk, "fd": fd, "fk_per_round": _div(fk, R, 3), "fk_fd": _div(fk, fd),
        "trades": sum(s["trades"] for s in sums), "traded": sum(s["traded"] for s in sums),
        "multi": dict(multi),
        "clutch": {"att": dict(catt), "won": dict(cwon),
                   "total_att": sum(catt.values()), "total_won": sum(cwon.values()),
                   "rate": _pct(sum(cwon.values()), sum(catt.values()), 0)},
        "atk": {"won": atk[0], "played": atk[1], "rate": _pct(*atk, 0)},
        "def": {"won": dfn[0], "played": dfn[1], "rate": _pct(*dfn, 0)},
        "loadout": round(sum(loads) / len(loads)) if loads else None,
        "plants": sum(s["plants"] for s in sums), "defuses": sum(s["defuses"] for s in sums),
        "casts": [round(sum(c[i] for c in casts) / len(casts), 2) for i in range(4)] if casts else None,
        "mvps": sum(s["mvp"] for s in sums), "team_mvps": sum(s["team_mvp"] for s in sums),
        "playtime_h": round(sum((s["len"] or 0) for s in sums) / 3_600_000, 1),
    }

    # 特務 / 地圖 / 武器
    by_agent, by_map = defaultdict(list), defaultdict(list)
    weapons = defaultdict(int)
    for s in sums:
        by_agent[s["agent"]].append(s)
        by_map[s["map"]].append(s)
        for w, n in s["weapons"].items():
            weapons[w] += n
    agents = sorted(({"agent": a, **block(ss)} for a, ss in by_agent.items()), key=lambda x: -x["games"])
    maps = []
    for mp, ss in by_map.items():
        if not mp:
            continue
        b = block(ss)
        a_ = [sum(s["atk"][0] for s in ss), sum(s["atk"][1] for s in ss)]
        d_ = [sum(s["def"][0] for s in ss), sum(s["def"][1] for s in ss)]
        best = None
        per_agent = defaultdict(list)
        for s in ss:
            per_agent[s["agent"]].append(s)
        cands = [(a, block(x)) for a, x in per_agent.items() if len(x) >= 2]
        if cands:
            a, bb = max(cands, key=lambda c: ((c[1]["winrate"] or 0), c[1]["acs"] or 0))
            if (bb["winrate"] or 0) >= 50:
                best = {"agent": a, "games": bb["games"], "winrate": bb["winrate"], "acs": bb["acs"]}
        maps.append({"map": mp, **b, "atk": _pct(*a_, 0), "def": _pct(*d_, 0), "best_agent": best})
    maps.sort(key=lambda x: -x["games"])
    total_wk = sum(weapons.values())
    weapon_list = sorted(({"weapon": w, "kills": n, "share": _pct(n, total_wk, 0)}
                          for w, n in weapons.items()), key=lambda x: -x["kills"])

    # 拍檔
    partners = defaultdict(lambda: {"games": 0, "wins": 0, "name": ""})
    names = dict(known or {})
    for m in matches:
        for p in m.get("players") or []:
            if p.get("name"):
                names[p["id"]] = f'{p["name"]}#{p["tag"]}'
    for s in sums:
        for pid in s["party"]:
            partners[pid]["games"] += 1
            partners[pid]["wins"] += bool(s["won"])
    partner_list = sorted(({"name": names.get(pid, "隊友"), "games": v["games"], "wins": v["wins"],
                            "winrate": _pct(v["wins"], v["games"], 0)}
                           for pid, v in partners.items()), key=lambda x: -x["games"])[:8]
    solo = [s for s in sums if not s["party"]]
    duo = [s for s in sums if s["party"]]

    # 時段熱力圖（本機時間）：[星期][小時] = [場數, 勝場]
    heat = [[[0, 0] for _ in range(24)] for _ in range(7)]
    per_day = defaultdict(list)
    for s in sums:
        if not s["start"]:
            continue
        dt = datetime.fromtimestamp(s["start"] / 1000)
        heat[dt.weekday()][dt.hour][0] += 1
        heat[dt.weekday()][dt.hour][1] += bool(s["won"])
        per_day[dt.date().isoformat()].append(s)
    days = [{"date": d, "games": len(ss), "wins": sum(bool(s["won"]) for s in ss),
             "kd": block(ss)["kd"]} for d, ss in sorted(per_day.items())][-60:]

    # 連勝連敗
    form = [("W" if s["won"] else "D" if s["won"] is None else "L") for s in sums[:20]]
    cur_streak = 0
    if form:
        first = form[0]
        for f in form:
            if f != first:
                break
            cur_streak += 1
        cur_streak = cur_streak if first == "W" else -cur_streak if first == "L" else 0
    best_streak, run = 0, 0
    for s in reversed(sums):
        run = run + 1 if s["won"] else 0
        best_streak = max(best_streak, run)

    # 狀態提醒（連敗 + 最近表現明顯下滑）
    recent = block(sums[:5])
    tilt = None
    if cur_streak <= -3 and overall["kd"] and recent["kd"] is not None and recent["kd"] < overall["kd"] * 0.85:
        tilt = {"losses": -cur_streak, "recent_kd": recent["kd"], "avg_kd": overall["kd"]}

    # 徽章
    got = defaultdict(int)
    for s in sums:
        got["ace"] += s["multi"].get("5", 0)
        got["clutch"] += sum(v for k, v in s["clutch_won"].items() if int(k) >= 2)
        got["headhunter"] += bool(s["hs"] and s["hs"] >= 35 and s["rounds"] >= 10)
        got["mvp"] += s["mvp"]
        got["entry"] += s["fk"] >= 4
        got["planter"] += s["plants"] >= 4
        got["defuser"] += s["defuses"]
        got["wall"] += bool(s["kast"] and s["kast"] >= 90)
    got["streak"] = 1 if best_streak >= 3 else 0
    got["grinder"] = sum(1 for d in days if d["games"] >= 6)
    badges = [{"id": b, "name": n, "desc": d, "count": got[b]} for b, n, d in BADGES]

    best = max(rs, key=lambda s: s["acs"] or 0, default=None)
    match_list = []
    for s in sums:
        item = {k: v for k, v in s.items() if not k.startswith("_") and k not in ("round_log", "weapons")}
        tags = []
        if s["multi"].get("5"):
            tags.append("ACE")
        elif s["multi"].get("4"):
            tags.append("4K")
        if any(int(k) >= 2 for k in s["clutch_won"]):
            tags.append("殘局")
        if s["mvp"]:
            tags.append("MVP")
        elif s["team_mvp"]:
            tags.append("隊伍MVP")
        item["tags"] = tags
        match_list.append(item)

    p = profile or {}
    return {
        "me": {"name": p.get("name"), "rank": p.get("rank"), "puuid": me},
        "overall": overall, "recent": recent, "extra": extra,
        "agents": agents, "maps": maps, "weapons": weapon_list,
        "partners": partner_list, "solo": block(solo), "duo": block(duo),
        "heat": heat, "days": days,
        "form": form, "streak": cur_streak, "best_streak": best_streak,
        "tilt": tilt, "badges": badges,
        "best_match": {k: best[k] for k in ("id", "acs", "k", "d", "a", "agent", "map")} if best else None,
        "rr_history": p.get("rr_history", [])[-60:],
        "forecast": rr_forecast(p.get("rr_history"), p.get("rank")),
        "matches": match_list,
        "queues": sorted({m.get("queue") or "custom" for m in matches}),
    }
