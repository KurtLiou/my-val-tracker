"""本機資料儲存：設定、個人檔案、對局快取、lineup 收藏。全部放在 %USERPROFILE%\\.valtracker"""
import json
import os
import threading

ROOT = os.path.join(os.path.expanduser("~"), ".valtracker")
MATCH_DIR = os.path.join(ROOT, "matches_v2")
RAW_DIR = os.path.join(ROOT, "raw")
_lock = threading.Lock()

for d in (ROOT, MATCH_DIR, RAW_DIR):
    os.makedirs(d, exist_ok=True)


def _read(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _write(path, data):
    tmp = path + ".tmp"
    with _lock:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)


# ---------- 設定 ----------
SETTINGS_PATH = os.path.join(ROOT, "settings.json")
DEFAULT_SETTINGS = {"henrik_key": "", "riot_id": "", "youtube_key": "", "sync_count": 40,
                    "update_repo": "", "auto_sync": True, "show_enemies": True,
                    "buddy_enabled": True, "buddy_provider": "none", "buddy_key": "", "buddy_model": "",
                    "buddy_interval": 20, "buddy_clickthrough": True,
                    "buddy_skin": "jiujiu", "buddy_size": "m", "buddy_x": None, "buddy_y": None,
                    "voice_enabled": True, "voice_engine": "edge", "voice_name": "zh-TW-HsiaoYuNeural",
                    "voice_rate": 5, "voice_pitch": 10, "voice_volume": 70}


def settings():
    return {**DEFAULT_SETTINGS, **_read(SETTINGS_PATH, {})}


def save_settings(new):
    cur = settings()
    for k in DEFAULT_SETTINGS:
        if k in new and (new[k] is not None or k in ("buddy_x", "buddy_y")):
            cur[k] = new[k]
    cur["sync_count"] = max(5, min(150, int(cur.get("sync_count") or 40)))
    cur["update_repo"] = str(cur.get("update_repo") or "").strip().strip("/")
    cur["auto_sync"] = bool(cur.get("auto_sync"))
    cur["show_enemies"] = bool(cur.get("show_enemies"))
    cur["buddy_enabled"] = bool(cur.get("buddy_enabled"))
    cur["buddy_clickthrough"] = bool(cur.get("buddy_clickthrough"))
    cur["buddy_interval"] = max(10, min(120, int(cur.get("buddy_interval") or 20)))
    if cur.get("buddy_skin") not in ("jiujiu", "hoshina", "rinne", "wakaba", "custom"):
        cur["buddy_skin"] = "jiujiu"
    if cur.get("buddy_size") not in ("s", "m", "l"):
        cur["buddy_size"] = "m"
    for k in ("buddy_x", "buddy_y"):
        cur[k] = int(cur[k]) if isinstance(cur.get(k), (int, float)) else None
    cur["voice_enabled"] = bool(cur.get("voice_enabled"))
    if cur.get("voice_engine") not in ("edge", "windows"):
        cur["voice_engine"] = "edge"
    for k, lo, hi in (("voice_rate", -30, 50), ("voice_pitch", -20, 40), ("voice_volume", 0, 100)):
        try:
            cur[k] = max(lo, min(hi, int(cur.get(k) or 0)))
        except (TypeError, ValueError):
            cur[k] = DEFAULT_SETTINGS[k]
    if cur.get("buddy_provider") not in ("none", "gemini", "claude"):
        cur["buddy_provider"] = "none"
    _write(SETTINGS_PATH, cur)
    return cur


# ---------- 個人檔案（牌位、RR 歷史、PUUID） ----------
PROFILE_PATH = os.path.join(ROOT, "profile.json")


def profile():
    return _read(PROFILE_PATH, {})


def save_profile(**kw):
    p = profile()
    p.update({k: v for k, v in kw.items() if v is not None})
    _write(PROFILE_PATH, p)
    return p


def merge_rr_history(entries):
    """依 match_id 合併 RR 紀錄，保留最新 300 筆。"""
    p = profile()
    by_id = {e["match_id"]: e for e in p.get("rr_history", []) if e.get("match_id")}
    for e in entries:
        if e.get("match_id"):
            by_id[e["match_id"]] = e
    hist = sorted(by_id.values(), key=lambda e: e.get("date") or 0)[-300:]
    save_profile(rr_history=hist)
    return hist


# ---------- 對局快取（統一格式） ----------
def has_match(mid, min_version=2):
    """已經存過、而且是新版格式（有位置資料）才算有。舊格式會被重新下載。"""
    m = load_match(mid)
    return bool(m) and (m.get("v") or 1) >= min_version


def save_match(m):
    _write(os.path.join(MATCH_DIR, f'{m["id"]}.json'), m)


def load_match(mid):
    return _read(os.path.join(MATCH_DIR, f"{mid}.json"), None)


def all_matches(puuid=None):
    out = []
    for fn in os.listdir(MATCH_DIR):
        if not fn.endswith(".json"):
            continue
        m = _read(os.path.join(MATCH_DIR, fn), None)
        if not m:
            continue
        if puuid and not any(p["id"] == puuid for p in m.get("players", [])):
            continue
        out.append(m)
    out.sort(key=lambda m: m.get("start") or 0, reverse=True)
    return out


def clear_matches():
    for fn in os.listdir(MATCH_DIR):
        if fn.endswith(".json"):
            os.remove(os.path.join(MATCH_DIR, fn))


# ---------- Lineup 收藏 ----------
FAV_PATH = os.path.join(ROOT, "lineup_favorites.json")


def favorites():
    return _read(FAV_PATH, [])


def add_favorite(item):
    favs = favorites()
    favs.append(item)
    _write(FAV_PATH, favs)
    return favs


def remove_favorite(fid):
    favs = [f for f in favorites() if f.get("id") != fid]
    _write(FAV_PATH, favs)
    return favs


# ---------- 玩家名稱（好友、組隊過的人） ----------
def known_names():
    return profile().get("known_names", {})


def add_names(mapping):
    if not mapping:
        return
    names = known_names()
    names.update({k: v for k, v in mapping.items() if k and v and "#" in v})
    save_profile(known_names=names)


# ---------- 自訂特務圖片（放在 %USERPROFILE%\.valtracker\agents） ----------
AGENT_IMG_DIR = os.path.join(ROOT, "agents")
os.makedirs(AGENT_IMG_DIR, exist_ok=True)


def custom_agent_images():
    return sorted(f for f in os.listdir(AGENT_IMG_DIR)
                  if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")))


# ---------- 對戰陪伴的自訂圖片（放在 %USERPROFILE%\.valtracker\buddy） ----------
BUDDY_IMG_DIR = os.path.join(ROOT, "buddy")
os.makedirs(BUDDY_IMG_DIR, exist_ok=True)


def buddy_images():
    return sorted(f for f in os.listdir(BUDDY_IMG_DIR)
                  if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")))


def buddy_outfits():
    """自訂造型包：buddy 資料夾裡的子資料夾，每個資料夾是一套造型（裡面放 happy.png 等）。
    資料夾名稱用「Lv10」這種格式 → 等級 10 解鎖；「ACE」→ 打出 ACE 解鎖；其他名稱直接可用。"""
    out = []
    for name in sorted(os.listdir(BUDDY_IMG_DIR)):
        full = os.path.join(BUDDY_IMG_DIR, name)
        if os.path.isdir(full):
            files = sorted(f for f in os.listdir(full) if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")))
            if files:
                out.append({"name": name, "files": files})
    return out
