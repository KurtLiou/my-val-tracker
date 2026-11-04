"""展示模式用的假資料（統一格式），讓你不用開遊戲也能看所有頁面。"""
import random
import time

ME = "demo-me"
AGENTS = ["add6443a-41bd-e414-f6ad-e58d267f4e95", "320b2a48-4d9b-a075-30f1-1f93a9b638fa",
          "a3bfb853-43b2-7238-a4f1-ad90e9e46bcc", "1e58de9c-4950-5125-93e9-a0aee9f98746",
          "569fdd95-4d10-43ab-ca70-79becc718b46", "f94c3b30-42be-e959-889c-5aa313dba261",
          "8e253930-4c05-31dd-1b6c-968525494517", "707eab51-4836-f488-046a-cda6bf494859",
          "9f0d8ba9-4140-b941-57d3-a7ad57c6b417", "dade69b4-4f5a-8528-247b-219e5a1facd6",
          "e370fa57-4757-3604-3648-499e1f642d3f", "601dbbe7-43ce-be57-2a40-4abd24953621"]
MY_AGENTS = AGENTS[:4] + [AGENTS[9]]
MAPS = ["/Game/Maps/Ascent/Ascent", "/Game/Maps/Bonsai/Bonsai", "/Game/Maps/Triad/Triad",
        "/Game/Maps/Port/Port", "/Game/Maps/Duality/Duality", "/Game/Maps/Jam/Jam", "/Game/Maps/Juliett/Juliett"]
WEAPONS = ["9c82e19d-4575-0200-1a81-3eacf00cf872"] * 5 + ["ee8e8d15-496b-07ac-e5f6-8fae5d4c7b1a"] * 3 + \
          ["a03b24d3-4319-996d-0f8c-94bbfba1dfc7", "e336c6b8-418d-9340-d77f-7a9e4cfe0702",
           "462080d1-4035-2937-7c09-27aa2a5c27a7", "1baa85b4-4c70-1284-64bb-6481dfc3bb4e",
           "29a0cfab-485b-f5d5-779a-b59f85e204a8"]
QUEUES = ["competitive"] * 6 + ["unrated", "unrated", "swiftplay", "deathmatch"]


def _game_xy(nx, ny):
    """把 0~1 的小地圖座標轉回遊戲座標（用義境空島的換算參數，展示用）。"""
    return (ny - 0.573242) / -7e-05, (nx - 0.813895) / 7e-05


def _match(i, rng, now):
    queue = rng.choice(QUEUES)
    mid = f"demo-{i:03d}"
    start = now - i * rng.randint(2, 7) * 3_600_000 - rng.randint(0, 3_000_000)
    duo = rng.random() < 0.35
    players = []
    for n in range(10):
        pid = ME if n == 0 else ("demo-duo" if n == 1 and duo else f"p{i}-{n}")
        team = "Blue" if n < 5 else "Red"
        players.append({"id": pid, "name": "Demo玩家" if pid == ME else ("好麻吉" if pid == "demo-duo" else f"玩家{n}"),
                        "tag": "TW1" if pid == ME else "0000", "team": team,
                        "party": "party-me" if pid in (ME, "demo-duo") else f"pt{i}{n}",
                        "agent": rng.choice(MY_AGENTS) if pid == ME else rng.choice(AGENTS),
                        "tier": rng.randint(12, 17), "level": rng.randint(30, 300),
                        "score": 0, "k": 0, "d": 0, "a": 0, "hs": 0, "bs": 0, "ls": 0,
                        "casts": [0, 0, 0, 0]})
    skill = {p["id"]: (1.35 if p["id"] == ME else rng.uniform(0.7, 1.3)) for p in players}
    if queue == "deathmatch":
        for p in players:
            p["team"] = p["id"]
            p["k"] = int(rng.gauss(18, 5) * skill[p["id"]])
            p["d"] = rng.randint(12, 26)
            p["score"] = p["k"] * 100
        return {"v": 1, "id": mid, "src": "demo", "start": start, "len": 540000, "queue": queue,
                "map": rng.choice(MAPS), "season": None, "completed": True,
                "teams": {p["id"]: {"won": False, "rw": 0} for p in players},
                "players": players, "rounds": [], "kills": []}

    target = 4 if queue == "swiftplay" else 13
    by_id = {p["id"]: p for p in players}
    rounds, kills = [], []
    wins = {"Blue": 0, "Red": 0}
    r = 0
    bias = rng.uniform(-0.15, 0.15)
    while max(wins.values()) < target or (target == 13 and abs(wins["Blue"] - wins["Red"]) < 2 and r < 30):
        if target == 4 and max(wins.values()) >= 4:
            break
        alive = {"Blue": [p["id"] for p in players[:5]], "Red": [p["id"] for p in players[5:]]}
        t, dmg, econ = rng.randint(5000, 20000), [], {}
        site = rng.choice([(0.3, 0.3), (0.65, 0.35), (0.5, 0.7)])
        spot = {p["id"]: [min(.95, max(.05, rng.gauss(site[0], .13))), min(.95, max(.05, rng.gauss(site[1], .13)))]
                for p in players}
        for p in players:
            econ[p["id"]] = [rng.choice([800, 2400, 3900, 4700, 5300]), rng.randint(400, 4500)]
        while alive["Blue"] and alive["Red"]:
            pb = 0.5 + bias + 0.03 * (len(alive["Blue"]) - len(alive["Red"]))
            win_team = "Blue" if rng.random() < pb else "Red"
            lose_team = "Red" if win_team == "Blue" else "Blue"
            killer = max(alive[win_team], key=lambda x: rng.random() * skill[x])
            victim = rng.choice(alive[lose_team])
            alive[lose_team].remove(victim)
            hs = rng.random() < (0.28 if killer == ME else 0.2)
            dmg.append([killer, victim, 150, 2 if hs else 0, 1 if hs else 2, 0 if rng.random() < 0.8 else 1])
            assists = [a for a in alive[win_team] if a != killer and rng.random() < 0.25][:2]
            for a in assists:
                dmg.append([a, victim, 40, 1 if rng.random() < 0.3 else 0, 1, 0])
                by_id[a]["a"] += 1
            for pid in alive["Blue"] + alive["Red"] + [victim]:
                spot[pid][0] = min(.95, max(.05, spot[pid][0] + rng.gauss(0, .03)))
                spot[pid][1] = min(.95, max(.05, spot[pid][1] + rng.gauss(0, .03)))
            pos = [[pid, *_game_xy(*spot[pid])] for pid in alive["Blue"] + alive["Red"]]
            vx, vy = _game_xy(*spot[victim])
            kills.append({"r": r, "t": t, "k": killer, "v": victim, "a": assists, "vx": vx, "vy": vy, "pos": pos,
                          "w": rng.choice(WEAPONS), "wt": "weapon"})
            by_id[killer]["k"] += 1
            by_id[killer]["score"] += 200 + rng.randint(0, 60)
            by_id[victim]["d"] += 1
            for x in (killer, victim):
                pass
            t += rng.randint(1500, 9000)
        winner = "Blue" if alive["Blue"] else "Red"
        wins[winner] += 1
        planter = rng.choice(players[:5] if (r < 12) == False else players[5:])["id"] if rng.random() < 0.5 else None
        for p in players:
            p["hs"] += sum(d[3] for d in dmg if d[0] == p["id"])
            p["bs"] += sum(d[4] for d in dmg if d[0] == p["id"])
            p["ls"] += sum(d[5] for d in dmg if d[0] == p["id"])
            p["score"] += rng.randint(20, 60)
            p["casts"] = [c + rng.randint(0, 2) for c in p["casts"]]
        plant_xy = list(_game_xy(*site)) if planter else None
        rounds.append({"plant_xy": plant_xy, "win": winner, "result": rng.choice(["elim", "elim", "elim", "detonate", "defuse"]),
                       "planter": planter, "defuser": None, "site": rng.choice("AB") if planter else None,
                       "dmg": dmg, "econ": econ})
        r += 1
    won_team = "Blue" if wins["Blue"] > wins["Red"] else "Red"
    return {"v": 2, "id": mid, "src": "demo", "start": start, "len": r * 100000, "queue": queue,
            "map": rng.choice(MAPS), "season": None, "completed": True,
            "teams": {"Blue": {"won": won_team == "Blue", "rw": wins["Blue"]},
                      "Red": {"won": won_team == "Red", "rw": wins["Red"]}},
            "players": players, "rounds": rounds, "kills": kills}


def matches():
    rng = random.Random(7)
    now = int(time.time() * 1000)
    return [_match(i, rng, now) for i in range(40)]


def profile():
    now = int(time.time() * 1000)
    rng = random.Random(3)
    hist, tier, rr = [], 14, 40
    for i in range(30):
        change = rng.choice([-18, -15, -12, 17, 19, 21, 24, 8])
        rr += change
        if rr >= 100:
            tier, rr = tier + 1, rr - 100
        elif rr < 0:
            tier, rr = tier - 1, rr + 100
        hist.append({"match_id": f"rr{i}", "date": now - (30 - i) * 8 * 3_600_000,
                     "tier": tier, "rr": rr, "change": change, "map": rng.choice(MAPS)})
    return {"name": "Demo玩家#TW1", "puuid": ME, "region": "ap",
            "rank": {"tier": tier, "rr": rr, "wins": 22, "games": 41, "peak": 18},
            "rr_history": hist, "last_sync": now, "last_source": "demo"}


def live():
    return {"phase": "ingame", "map": "/Game/Maps/Ascent/Ascent", "queue": "competitive",
            "players": [
                {"me": True, "side": "ally", "hidden": False, "agent": "320b2a48-4d9b-a075-30f1-1f93a9b638fa", "locked": True,
                 "level": 213, "name": "Demo玩家#TW1", "rank": {"tier": 15, "rr": 47, "wins": 22, "games": 41, "peak": 18}},
                {"me": False, "side": "ally", "hidden": False, "agent": "add6443a-41bd-e414-f6ad-e58d267f4e95", "locked": True,
                 "level": 88, "name": "隊友A#1234", "rank": {"tier": 14, "rr": 81, "wins": 30, "games": 55, "peak": 16}},
                {"me": False, "side": "ally", "hidden": True, "agent": "569fdd95-4d10-43ab-ca70-79becc718b46", "locked": True,
                 "level": None, "name": None, "rank": None},
                {"me": False, "side": "ally", "hidden": False, "agent": "8e253930-4c05-31dd-1b6c-968525494517", "locked": True,
                 "level": None, "name": "隊友B#TW", "rank": {"tier": 16, "rr": 12, "wins": 12, "games": 20, "peak": 16}},
                {"me": False, "side": "ally", "hidden": False, "agent": "1e58de9c-4950-5125-93e9-a0aee9f98746", "locked": True,
                 "level": 402, "name": "隊友C#0001", "rank": {"tier": 13, "rr": 55, "wins": 0, "games": 0, "peak": 18}},
                {"me": False, "side": "enemy", "hidden": False, "agent": "a3bfb853-43b2-7238-a4f1-ad90e9e46bcc", "locked": True,
                 "level": 156, "name": "敵人A#KR1", "rank": {"tier": 16, "rr": 60, "wins": 25, "games": 40, "peak": 19}},
                {"me": False, "side": "enemy", "hidden": True, "agent": "707eab51-4836-f488-046a-cda6bf494859", "locked": True,
                 "level": None, "name": None, "rank": None},
                {"me": False, "side": "enemy", "hidden": False, "agent": "f94c3b30-42be-e959-889c-5aa313dba261", "locked": True,
                 "level": 90, "name": None, "rank": {"tier": 14, "rr": 5, "wins": 8, "games": 19, "peak": 15}},
                {"me": False, "side": "enemy", "hidden": False, "agent": "9f0d8ba9-4140-b941-57d3-a7ad57c6b417", "locked": True,
                 "level": 301, "name": "敵人C#0420", "rank": {"tier": 15, "rr": 77, "wins": 31, "games": 52, "peak": 17}},
                {"me": False, "side": "enemy", "hidden": False, "agent": "dade69b4-4f5a-8528-247b-219e5a1facd6", "locked": True,
                 "level": 44, "name": "敵人D#TW", "rank": {"tier": 0, "rr": 0, "wins": 0, "games": 0, "peak": 0}},
            ]}
