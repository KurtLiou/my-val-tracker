"""把資料來源（遊戲開著 → Riot；沒開 → HenrikDev）和本機快取串在一起。"""
import threading
import time

import buddy
import normalize
import store
from henrik import HenrikClient, HenrikError
from riot import RiotClient, RiotError

riot = RiotClient()


class SyncError(Exception):
    pass


def status():
    s = store.settings()
    p = store.profile()
    game = riot.is_available()
    return {
        "game_open": game,
        "henrik_ready": bool(s["henrik_key"] and (p.get("puuid") or s["riot_id"])),
        "profile": {k: p.get(k) for k in ("name", "puuid", "region", "rank", "last_sync", "last_source")},
        "match_count": len(store.all_matches(p.get("puuid"))) if p.get("puuid") else 0,
        "settings": {
            "riot_id": s["riot_id"], "sync_count": s["sync_count"],
            "henrik_key_set": bool(s["henrik_key"]), "youtube_key": s["youtube_key"],
            "update_repo": s["update_repo"], "auto_sync": s["auto_sync"], "show_enemies": s["show_enemies"],
            "buddy_enabled": s["buddy_enabled"], "buddy_provider": s["buddy_provider"],
            "buddy_key_set": bool(s["buddy_key"]), "buddy_model": s["buddy_model"],
            "buddy_interval": s["buddy_interval"], "buddy_clickthrough": s["buddy_clickthrough"],
            "buddy_skin": s["buddy_skin"], "buddy_size": s["buddy_size"], "buddy_pos_set": s["buddy_x"] is not None,
            **{k: s[k] for k in ("voice_enabled", "voice_engine", "voice_name", "voice_rate", "voice_pitch", "voice_volume")},
        },
    }


def _step(label, fn):
    try:
        return fn()
    except RiotError as e:
        raise RiotError(f"{label}失敗（{e}）") from None


def _sync_riot(count):
    riot.ensure()
    me = riot.puuid
    name = riot.self_name() or riot.names([me]).get(me, "")
    ids = _step("讀取對局列表", lambda: riot.history_ids(count))
    new, failed = 0, 0
    for mid in ids:
        if store.has_match(mid):
            continue
        try:
            raw = riot.match_raw(mid)
        except RiotError:
            failed += 1
            if failed >= 3 and new == 0:
                raise RiotError("讀取單場資料一直失敗，Riot 可能擋了這個請求。") from None
            continue
        if not raw or not (raw.get("matchInfo") or {}).get("isCompleted", True):
            continue
        nm = normalize.from_riot(raw)
        if not name:
            p = next((x for x in nm["players"] if x["id"] == me and x["name"]), None)
            name = f'{p["name"]}#{p["tag"]}' if p else ""
        store.save_match(nm)
        new += 1
    try:
        rank = riot.rank(me)
    except RiotError:
        rank = None
    try:
        store.merge_rr_history(normalize.rr_from_riot(riot.competitive_updates(min(count, 60))))
    except RiotError:
        pass
    store.save_profile(puuid=me, name=name or None, region=riot.region, shard=riot.shard,
                       rank=_fill_rank(rank, me), last_sync=int(time.time() * 1000), last_source="riot")
    try:
        store.add_names(riot.friend_names())
    except RiotError:
        pass
    _resolve_partner_names(me)
    return new


def _fill_rank(rank, me):
    """牌位查不到（被擋或還沒打定位）時，用 RR 紀錄或最近一場競技的牌位補上。"""
    if rank and rank.get("tier"):
        return rank
    rank = dict(rank or {"tier": 0, "rr": 0, "wins": 0, "games": 0, "peak": 0})
    hist = store.profile().get("rr_history") or []
    if hist:
        rank["tier"], rank["rr"] = hist[-1].get("tier") or 0, hist[-1].get("rr") or 0
    if not rank.get("tier"):
        for m in store.all_matches(me):
            if m.get("queue") == "competitive":
                p = next((x for x in m["players"] if x["id"] == me), None)
                if p and p.get("tier"):
                    rank["tier"] = p["tier"]
                    break
    peak = 0
    for m in store.all_matches(me):
        p = next((x for x in m["players"] if x["id"] == me), None)
        if p and m.get("queue") == "competitive":
            peak = max(peak, p.get("tier") or 0)
    rank["peak"] = max(rank.get("peak") or 0, peak, rank.get("tier") or 0)
    rank["estimated"] = True
    return rank


def _resolve_partner_names(me, limit=12):
    """把「一起組隊的人」的名字補齊：先看好友列表，再用 HenrikDev（有設定 key 才會）。"""
    known = store.known_names()
    missing = []
    for m in store.all_matches(me):
        my = next((p for p in m["players"] if p["id"] == me), None)
        if not my or not my.get("party"):
            continue
        for p in m["players"]:
            if p["id"] != me and p.get("party") == my["party"]:
                if p.get("name"):
                    known.setdefault(p["id"], f'{p["name"]}#{p["tag"]}')
                elif p["id"] not in known and p["id"] not in missing:
                    missing.append(p["id"])
    store.add_names(known)
    if missing:
        found = riot.names(missing) if riot.access_token else {}
        store.add_names(found)
        missing = [x for x in missing if x not in found]
    key = store.settings()["henrik_key"]
    if missing and key:
        h = HenrikClient(key)
        got = {}
        for pid in missing[:limit]:
            try:
                acc = h.account_by_puuid(pid) or {}
                if acc.get("name"):
                    got[pid] = f'{acc["name"]}#{acc.get("tag", "")}'
            except HenrikError:
                break
        store.add_names(got)


def _sync_henrik(count):
    s = store.settings()
    p = store.profile()
    h = HenrikClient(s["henrik_key"])
    puuid, region, name = p.get("puuid"), p.get("region"), p.get("name")
    if s["riot_id"] and (not puuid or (name and s["riot_id"].lower() != name.lower())):
        acc = h.account(s["riot_id"]) or {}
        puuid, region = acc.get("puuid"), (acc.get("region") or "ap").lower()
        name = f'{acc.get("name", "")}#{acc.get("tag", "")}'
    if not puuid:
        raise SyncError("離線同步需要 Riot ID（設定頁填「名字#TAG」），或先開一次遊戲讓 App 記住你。")
    region = region or "ap"
    new = 0
    for m in h.matches(region, puuid, count):
        nm = normalize.from_henrik(m)
        if nm["id"] and not store.has_match(nm["id"]):
            store.save_match(nm)
            new += 1
    rank = None
    try:
        rank = normalize.rank_from_henrik(h.mmr(region, puuid))
        store.merge_rr_history(normalize.rr_from_henrik(h.mmr_history(region, puuid)))
    except HenrikError:
        pass
    store.save_profile(puuid=puuid, name=name, region=region, rank=_fill_rank(rank, puuid),
                       last_sync=int(time.time() * 1000), last_source="henrik")
    _resolve_partner_names(puuid)
    return new


def credit_progress():
    """把新對局算進養成，有升級／解鎖就發通知、讓陪伴角色說話。"""
    import progress
    p = store.profile()
    me = p.get("puuid")
    if not me:
        return []
    evs = progress.credit(store.all_matches(me), me)
    names = {i[0]: i[1] for i in progress.ITEMS}
    for ev in evs:
        push_event("progress", sub=ev["kind"], **{k: v for k, v in ev.items() if k != "kind"})
        if ev["kind"] == "level_up":
            buddy.say(f"升到 Lv.{ev['level']} 了！好厲害 🎉", "wow")
        elif ev["kind"] == "unlock":
            got = [names.get(i, "新對話框") for i in ev["items"]]
            buddy.say(f"解鎖了{'、'.join(got[:2])}！快來換上 ✨", "wow")
        elif ev["kind"] == "bond_up":
            buddy.say(f"我們變成「{ev['stage']}」了耶 💕", "wow")
    return evs


def sync(count=None):
    count = count or store.settings()["sync_count"]
    errors = []
    if riot.is_available():
        try:
            return {"source": "riot", "new": _sync_riot(count)}
        except RiotError as e:
            errors.append(f"遊戲：{e}")
    try:
        return {"source": "henrik", "new": _sync_henrik(count)}
    except (HenrikError, SyncError) as e:
        errors.append(str(e))
    raise SyncError("；".join(errors) or "沒有可用的資料來源。")


_rank_cache = {}


def _henrik_rank(puuid):
    """Riot 牌位查詢被擋時，改用 HenrikDev（有設定 key 才會）。結果快取 10 分鐘。"""
    hit = _rank_cache.get(puuid)
    if hit and hit[0] > time.time():
        return hit[1]
    key = store.settings()["henrik_key"]
    if not key:
        return None
    try:
        r = normalize.rank_from_henrik(HenrikClient(key).mmr(store.profile().get("region") or "ap", puuid))
    except HenrikError:
        r = None
    _rank_cache[puuid] = (time.time() + 600, r)
    return r


def live():
    if not riot.is_available():
        return {"phase": "offline"}
    return riot.live(include_enemies=store.settings()["show_enemies"], rank_fallback=_henrik_rank)


# ---------------- 打完自動同步 + 通知 ----------------
_events = []
_events_lock = threading.Lock()
_sync_lock = threading.Lock()


def push_event(kind, **data):
    with _events_lock:
        eid = (_events[-1]["id"] + 1) if _events else 1
        _events.append({"id": eid, "kind": kind, "t": int(time.time() * 1000), **data})
        del _events[:-30]


def events_since(eid):
    with _events_lock:
        return [e for e in _events if e["id"] > eid]


def locked_sync(count=None):
    with _sync_lock:
        r = sync(count)
    try:
        r["progress"] = credit_progress()
    except Exception:
        pass
    return r


def _last_match_event():
    import stats
    p = store.profile()
    me = p.get("puuid")
    ms = store.all_matches(me) if me else []
    if not ms:
        return
    s = stats.match_summary(ms[0], me)
    if not s:
        return
    rr = next((h for h in reversed(p.get("rr_history") or []) if h.get("match_id") == s["id"]), None)
    push_event("match_end", won=s["won"], k=s["k"], d=s["d"], a=s["a"], acs=s["acs"],
               map=s["map"], agent=s["agent"], rr=rr.get("change") if rr else None, id=s["id"])


def _monitor():
    prev, was_open = None, False
    while True:
        try:
            open_now = riot.is_available()
            if open_now and not was_open:
                push_event("game_open")
            was_open = open_now
            state = riot.session_state() if open_now else None
            if state == "INGAME" and prev != "INGAME":
                try:
                    buddy.start_match()
                except Exception:
                    pass
            if prev == "INGAME" and state != "INGAME":
                buddy.end_match()
            if prev == "INGAME" and state in ("MENUS", None) and open_now and store.settings()["auto_sync"]:
                time.sleep(20)  # 等伺服器把戰績寫好
                for _ in range(3):
                    try:
                        r = locked_sync(10)
                        if r.get("new"):
                            _last_match_event()
                            break
                    except Exception:
                        pass
                    time.sleep(30)
            if state:
                prev = state
        except Exception:
            pass
        time.sleep(10)


def start_monitor():
    threading.Thread(target=_monitor, daemon=True).start()
    threading.Thread(target=lambda: _quiet(credit_progress), daemon=True).start()  # 開 App 時補算舊對局


def _quiet(fn):
    try:
        fn()
    except Exception:
        pass
