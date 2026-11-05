"""
陪伴角色養成：經驗值、共用等級、每個角色的親密度、配件解鎖、回憶簿。

經驗值記在「帳本」裡（每場對局只算一次），所以清掉對局快取也不會掉等級。
以前同步過的對局，第一次開啟時會一次補算進來。
"""
import json
import os
import threading
import time

import stats
import store

MAX_LEVEL = 50
_lock = threading.Lock()

# ---------- 經驗值規則 ----------
XP_RULES = [
    ("base", "打完一場", 40),
    ("win", "贏了", 30),
    ("mvp", "全場 MVP", 40),
    ("team_mvp", "隊伍 MVP", 15),
    ("ace", "ACE", 80),
    ("k4", "4 殺", 30),
    ("clutch", "贏下 1v2 以上殘局（每次）", 25),
    ("party", "和朋友組隊", 10),
]
XP = {k: v for k, _, v in XP_RULES}

# ---------- 親密度 ----------
STAGES = [(0, "初次見面"), (120, "熟悉"), (360, "好朋友"), (800, "最佳戰友")]


def stage_of(points):
    idx = 0
    for i, (need, _) in enumerate(STAGES):
        if points >= need:
            idx = i
    nxt = STAGES[idx + 1][0] if idx + 1 < len(STAGES) else None
    return {"index": idx, "name": STAGES[idx][1], "points": points, "next": nxt,
            "base": STAGES[idx][0], "max": len(STAGES) - 1}


# ---------- 配件（美術在 static/skins.js） ----------
# cond: (種類, 數量)。種類：level 等級、ace ACE 次數、clutch 殘局勝利、streak 最長連勝、
#       games 總場數、mvp MVP 次數、bond 任一角色親密度階段
ITEMS = [
    ("headphones", "電競耳機", "head", ("level", 3)),
    ("heartclip", "愛心髮夾", "hair", ("bond", 1)),
    ("catears", "貓耳髮箍", "head", ("level", 6)),
    ("crown", "ACE 皇冠", "head", ("ace", 1)),
    ("headband", "戰術頭帶", "head", ("games", 50)),
    ("sunglasses", "酷酷墨鏡", "face", ("mvp", 5)),
    ("halo", "天使光環", "head", ("level", 10)),
    ("scarf", "冬季圍巾", "neck", ("level", 15)),
    ("cape", "殘局王披風", "back", ("clutch", 5)),
    ("fire", "連勝火焰", "aura", ("streak", 5)),
    ("wings", "星光翅膀", "back", ("level", 25)),
    ("goldaura", "傳說金光", "aura", ("level", 40)),
    ("bestie", "最佳戰友徽章", "neck", ("bond", 3)),
]
FRAMES = [
    ("default", "基本對話框", ("level", 1)),
    ("star", "星星對話框", ("level", 4)),
    ("heart", "愛心對話框", ("bond", 2)),
    ("neon", "霓虹對話框", ("level", 20)),
    ("gold", "黃金對話框", ("level", 30)),
]
COND_TEXT = {"level": "等級 {n}", "ace": "打出 {n} 次 ACE", "clutch": "贏 {n} 次殘局（1v2 以上）",
             "streak": "連勝 {n} 場", "games": "累積 {n} 場", "mvp": "拿 {n} 次全場 MVP",
             "bond": "任一角色親密度達到「{stage}」"}


def _xp_for_level(lv):
    return 100 + 20 * (lv - 1)


def level_from_xp(total):
    lv, rest = 1, total
    while lv < MAX_LEVEL and rest >= _xp_for_level(lv):
        rest -= _xp_for_level(lv)
        lv += 1
    return lv, rest, (_xp_for_level(lv) if lv < MAX_LEVEL else 0)


# ---------- 存檔 ----------
def _path():
    return os.path.join(store.ROOT, "progress_demo.json" if os.environ.get("VALTRACKER_DEMO") else "progress.json")


def load():
    try:
        with open(_path(), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    d.setdefault("ledger", {})
    d.setdefault("affection", {})
    d.setdefault("memories", [])
    d.setdefault("equipped", {})
    d.setdefault("adjust", {})
    d.setdefault("frame", "default")
    d.setdefault("nickname", "")
    d.setdefault("announced", [])
    d.setdefault("outfit", "")
    # 舊版的單一自訂角色存成 "custom"，搬到 "custom:<角色ID>"
    legacy = store._legacy_char_id()
    if legacy:
        for k in ("affection", "equipped", "adjust"):
            if "custom" in d[k]:
                d[k].setdefault("custom:" + legacy, d[k].pop("custom"))
    return d


def save(d):
    tmp = _path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, _path())


# ---------- 計分 ----------
def score_match(s):
    """s = stats.match_summary 的結果。回傳 (xp, 明細, 計數)"""
    parts = [("base", XP["base"])]
    if s["won"]:
        parts.append(("win", XP["win"]))
    if s.get("mvp"):
        parts.append(("mvp", XP["mvp"]))
    elif s.get("team_mvp"):
        parts.append(("team_mvp", XP["team_mvp"]))
    aces = int(s["multi"].get("5", 0))
    k4 = int(s["multi"].get("4", 0))
    clutch = sum(v for k, v in s["clutch_won"].items() if int(k) >= 2)
    if aces:
        parts.append(("ace", XP["ace"] * aces))
    if k4:
        parts.append(("k4", XP["k4"] * k4))
    if clutch:
        parts.append(("clutch", XP["clutch"] * clutch))
    if s.get("party"):
        parts.append(("party", XP["party"]))
    counts = {"ace": aces, "k4": k4, "clutch": clutch, "mvp": int(bool(s.get("mvp"))), "won": s["won"]}
    return sum(v for _, v in parts), parts, counts


def _memory_for(s, counts, skin):
    base = {"t": s.get("start") or int(time.time() * 1000), "map": s.get("map"), "agent": s.get("agent"),
            "match": s["id"], "skin": skin, "k": s["k"], "d": s["d"], "a": s["a"], "acs": s.get("acs")}
    if counts["ace"]:
        return {**base, "kind": "ace"}
    if counts["clutch"]:
        best = max(int(k) for k, v in s["clutch_won"].items() if v and int(k) >= 2)
        return {**base, "kind": "clutch", "vs": best}
    if counts["k4"]:
        return {**base, "kind": "k4"}
    if s.get("mvp") and s.get("acs") and s["acs"] >= 300:
        return {**base, "kind": "mvp"}
    return None


def credit(matches, me):
    """把還沒算過的對局記進帳本。回傳這次的新事件（升級、解鎖、親密度提升）。"""
    if not me:
        return []
    with _lock:
        d = load()
        before = summary(d)
        skin = store.settings().get("buddy_skin") or "jiujiu"
        new = []
        pending = sum(1 for m in matches if m.get("id") and m["id"] not in d["ledger"])
        backfill = pending > 8  # 以前的對局：經驗照算，但親密度只給一點（那時候角色還沒陪你）
        for m in sorted(matches, key=lambda x: x.get("start") or 0):
            if not m.get("id") or m["id"] in d["ledger"]:
                continue
            s = stats.match_summary(m, me)
            if not s:
                continue
            xp, parts, counts = score_match(s)
            d["ledger"][m["id"]] = {"t": s.get("start"), "xp": xp, "parts": parts, "skin": skin, **counts}
            gain = 2 if backfill else 10 + (5 if s["won"] else 0) + (5 if counts["ace"] else 0)
            d["affection"][skin] = d["affection"].get(skin, 0) + gain
            mem = _memory_for(s, counts, skin)
            if mem:
                d["memories"].append(mem)
            new.append(m["id"])
        d["memories"] = sorted(d["memories"], key=lambda x: x.get("t") or 0)[-120:]
        events = []
        if new:
            after = summary(d)
            if after["level"] > before["level"]:
                events.append({"kind": "level_up", "level": after["level"], "from": before["level"]})
            got = [i for i in after["unlocked_ids"] if i not in before["unlocked_ids"] and i not in d["announced"]]
            if got:
                events.append({"kind": "unlock", "items": got})
                d["announced"] += got
            sa, sb = after["bond"].get(skin, {}).get("index", 0), before["bond"].get(skin, {}).get("index", 0)
            if sa > sb:
                events.append({"kind": "bond_up", "skin": skin, "stage": STAGES[sa][1]})
            # 第一次補算舊對局時不要一次跳一堆通知
            if len(new) > 8:
                events = [{"kind": "backfill", "matches": len(new), "level": after["level"]}]
        save(d)
        return events


# ---------- 匯總 ----------
def _counters(d):
    led = sorted(d["ledger"].values(), key=lambda x: x.get("t") or 0)
    best = run = 0
    for e in led:
        run = run + 1 if e.get("won") else 0
        best = max(best, run)
    bonds = {k: stage_of(v) for k, v in d["affection"].items()}
    return {
        "games": len(led), "ace": sum(e.get("ace", 0) for e in led), "clutch": sum(e.get("clutch", 0) for e in led),
        "mvp": sum(e.get("mvp", 0) for e in led), "streak": best,
        "bond": max([b["index"] for b in bonds.values()] or [0]),
    }, bonds


def _cond(cond, level, c):
    kind, n = cond
    have = level if kind == "level" else c.get(kind, 0)
    text = COND_TEXT[kind].format(n=n, stage=STAGES[min(n, len(STAGES) - 1)][1])
    return have >= n, text, min(have, n), n


def summary(d=None):
    d = d or load()
    total = sum(e["xp"] for e in d["ledger"].values())
    level, into, need = level_from_xp(total)
    c, bonds = _counters(d)
    items, unlocked = [], []
    for iid, name, slot, cond in ITEMS:
        ok, text, have, n = _cond(cond, level, c)
        items.append({"id": iid, "name": name, "slot": slot, "unlocked": ok, "cond": text, "have": have, "need": n})
        if ok:
            unlocked.append(iid)
    frames = []
    for fid, name, cond in FRAMES:
        ok, text, have, n = _cond(cond, level, c)
        frames.append({"id": fid, "name": name, "unlocked": ok, "cond": text})
        if ok and fid != "default":
            unlocked.append("frame:" + fid)
    return {"level": level, "xp": into, "xp_next": need, "total_xp": total, "max_level": MAX_LEVEL,
            "counters": c, "bond": bonds, "items": items, "frames": frames, "unlocked_ids": unlocked}


def full(profile_name=""):
    d = load()
    s = summary(d)
    skin = store.settings().get("buddy_skin") or "jiujiu"
    unlocked = set(s["unlocked_ids"])
    equipped = [i for i in d["equipped"].get(skin, []) if i in unlocked]
    frame = d["frame"] if d["frame"] == "default" or ("frame:" + d["frame"]) in unlocked else "default"
    outfits = []
    cid = store.current_char()
    for o in (store.char_outfits(cid) if cid else []):
        ok, cond = outfit_unlocked(o["name"], s["level"], s["counters"])
        outfits.append({**o, "unlocked": ok, "cond": cond})
    outfit = d["outfit"] if any(o["name"] == d["outfit"] and o["unlocked"] for o in outfits) else ""
    return {**s, "skin": skin, "equipped": equipped, "outfits": outfits, "outfit": outfit, "equipped_all": d["equipped"], "adjust": d["adjust"],
            "frame": frame, "nickname": d["nickname"] or (profile_name or "").split("#")[0],
            "memories": list(reversed(d["memories"][-40:])), "rules": XP_RULES,
            "stages": [{"need": n, "name": t} for n, t in STAGES],
            "current_bond": s["bond"].get(skin) or stage_of(0)}


# ---------- 操作 ----------
def equip(skin, item, on):
    with _lock:
        d = load()
        unlocked = set(summary(d)["unlocked_ids"])
        if on and item not in unlocked:
            raise ValueError("這個配件還沒解鎖")
        slot = next((s for i, _, s, _ in ITEMS if i == item), None)
        cur = [i for i in d["equipped"].get(skin, []) if i != item]
        if on:
            # 同一個位置只能戴一個（例如頭上只能一頂）
            cur = [i for i in cur if next((s for j, _, s, _ in ITEMS if j == i), None) != slot] + [item]
        d["equipped"][skin] = cur
        save(d)
        return cur


def set_frame(fid):
    with _lock:
        d = load()
        if fid != "default" and "frame:" + fid not in summary(d)["unlocked_ids"]:
            raise ValueError("這個對話框還沒解鎖")
        d["frame"] = fid
        save(d)


def adjust(skin, item, x, y, scale):
    with _lock:
        d = load()
        d["adjust"].setdefault(skin, {})[item] = {"x": round(float(x), 1), "y": round(float(y), 1),
                                                  "s": max(0.3, min(3.0, round(float(scale), 2)))}
        save(d)


def outfit_unlocked(name, level, counters):
    import re
    m = re.match(r"(?i)^lv\.?\s*(\d+)", name or "")
    if m:
        return level >= int(m.group(1)), f"等級 {m.group(1)}"
    if (name or "").upper().startswith("ACE"):
        return counters.get("ace", 0) >= 1, "打出 1 次 ACE"
    return True, ""


def set_outfit(name):
    with _lock:
        d = load()
        if name:
            s = summary(d)
            ok, cond = outfit_unlocked(name, s["level"], s["counters"])
            if not ok:
                raise ValueError(f"這套造型要{cond}才能穿")
        d["outfit"] = name
        save(d)


def set_nickname(name):
    with _lock:
        d = load()
        d["nickname"] = str(name or "").strip()[:20]
        save(d)


# ---------- 給 AI 和離線台詞用的「關係」 ----------
NAMES = {"maps": {}, "agents": {}}  # 前端會把中文名稱傳過來


def ai_context(profile_name=""):
    f = full(profile_name)
    st = f["current_bond"]["index"]
    tone = ["禮貌、有點害羞，像剛認識的新隊友",
            "輕鬆友善，會開點小玩笑",
            "很熟的好朋友，會撒嬌、吐槽，偶爾提起一起打過的回憶",
            "最佳戰友，非常了解玩家、無條件挺他，常提起共同回憶"][st]
    mems = []
    for m in f["memories"][:3]:
        where = NAMES["maps"].get(m.get("map"), "")
        who = NAMES["agents"].get(m.get("agent"), "")
        what = {"ace": "打出 ACE", "clutch": f"贏下 1v{m.get('vs', 2)} 殘局", "k4": "打出 4 殺", "mvp": "拿下全場 MVP"}.get(m["kind"], "")
        mems.append((f"在{where}" if where else "") + (f"用{who}" if who else "") + what)
    lines = [f"玩家的暱稱：{f['nickname'] or '玩家'}（可以這樣叫他）",
             f"你們的關係：{f['current_bond']['name']}。說話語氣：{tone}",
             f"玩家等級：Lv.{f['level']}"]
    if mems and st >= 2:
        lines.append("你們的共同回憶（偶爾自然地提起，不要每次都講）：" + "；".join(mems))
    return "\n".join(lines), st, f["nickname"]
