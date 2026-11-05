"""本機資料儲存：設定、個人檔案、對局快取、lineup 收藏。全部放在 %USERPROFILE%\\.valtracker"""
import json
import os
import re
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
                    "buddy_custom_name": "",
                    "voice_enabled": True, "voice_engine": "edge", "voice_name": "zh-TW-HsiaoYuNeural",
                    "voice_rate": 5, "voice_pitch": 10, "voice_volume": 70}


def settings():
    s = {**DEFAULT_SETTINGS, **_read(SETTINGS_PATH, {})}
    sk = s.get("buddy_skin") or "jiujiu"
    if sk == "custom":  # 舊版只有一個自訂角色
        sk = "custom:" + (_legacy_char_id() or "mychar")
    if sk != "jiujiu" and not (sk.startswith("custom:") and os.path.isdir(os.path.join(ROOT, "characters", sk[7:]))):
        sk = "jiujiu"  # 舊版原創角色已拿掉，或角色被刪了
    s["buddy_skin"] = sk
    return s


def _legacy_char_id():
    d = os.path.join(ROOT, "characters")
    if not os.path.isdir(d):
        return None
    ids = sorted(os.listdir(d))
    return "alya" if "alya" in ids else (ids[0] if ids else None)


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
    if not (cur.get("buddy_skin") == "jiujiu" or str(cur.get("buddy_skin") or "").startswith("custom:")):
        cur["buddy_skin"] = "jiujiu"
    if cur.get("buddy_size") not in ("s", "m", "l"):
        cur["buddy_size"] = "m"
    for k in ("buddy_x", "buddy_y"):
        cur[k] = int(cur[k]) if isinstance(cur.get(k), (int, float)) else None
    cur["voice_enabled"] = bool(cur.get("voice_enabled"))
    cur["buddy_custom_name"] = str(cur.get("buddy_custom_name") or "").strip()[:16]
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


# ---------- 表情欄位 ----------
# 基本 4 個 + 養成解鎖 3 個（需要的親密度階段）
BUDDY_MOODS = [("happy", "平常", 0), ("wow", "驚喜", 0), ("sad", "難過", 0), ("cheer", "加油", 0),
               ("comfort", "加碼安慰", 1), ("proud", "傲嬌的肯定", 2), ("daily", "專屬日常", 2)]
IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def save_buddy_image(mood, data, ext):
    if mood not in [m for m, _, _ in BUDDY_MOODS]:
        raise ValueError("不認識的表情欄位")
    ext = ext.lower() if ext.lower() in IMG_EXTS else ".png"
    remove_buddy_image(mood)
    path = os.path.join(BUDDY_IMG_DIR, mood + ext)
    with open(path, "wb") as f:
        f.write(data)
    return os.path.basename(path)


def remove_buddy_image(mood):
    for f in os.listdir(BUDDY_IMG_DIR):
        stem, ext = os.path.splitext(f)
        if stem.lower() == mood and ext.lower() in IMG_EXTS:
            os.remove(os.path.join(BUDDY_IMG_DIR, f))


def import_buddy_seed(folder):
    """把 App 資料夾裡 buddy_import 的圖片搬進自訂圖片資料夾（Claude 幫你放圖用）。回傳搬了幾張。"""
    if not os.path.isdir(folder):
        return 0
    n = 0
    for f in os.listdir(folder):
        stem, ext = os.path.splitext(f)
        if ext.lower() in IMG_EXTS and stem.lower() in [m for m, _, _ in BUDDY_MOODS]:
            remove_buddy_image(stem.lower())
            os.replace(os.path.join(folder, f), os.path.join(BUDDY_IMG_DIR, stem.lower() + ext.lower()))
            n += 1
    try:
        os.rmdir(folder)
    except OSError:
        pass
    return n


# ---------- 多個自訂角色：%USERPROFILE%\.valtracker\characters\<角色ID>\ ----------
CHAR_DIR = os.path.join(ROOT, "characters")
os.makedirs(CHAR_DIR, exist_ok=True)
_ID_OK = re.compile(r"^[a-z0-9_-]{1,32}$")


def _cid(cid):
    cid = str(cid or "").lower()
    if not _ID_OK.match(cid):
        raise ValueError("角色 ID 不正確")
    return cid


def char_dir(cid):
    return os.path.join(CHAR_DIR, _cid(cid))


def current_char():
    sk = settings()["buddy_skin"]
    return sk[7:] if sk.startswith("custom:") else None


def _images(folder):
    return sorted(f for f in os.listdir(folder) if f.lower().endswith(IMG_EXTS)) if os.path.isdir(folder) else []


def char_files(cid):
    return _images(char_dir(cid))


def char_outfits(cid):
    """角色資料夾裡的子資料夾 = 自訂造型包（Lv10、ACE…）"""
    d = char_dir(cid)
    out = []
    for name in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if os.path.isdir(os.path.join(d, name)):
            files = _images(os.path.join(d, name))
            if files:
                out.append({"name": name, "files": files})
    return out


def list_characters():
    out = []
    for cid in sorted(os.listdir(CHAR_DIR)):
        if not _ID_OK.match(cid) or not os.path.isdir(os.path.join(CHAR_DIR, cid)):
            continue
        import persona  # 延後匯入，避免互相匯入
        name = persona.load(cid).get("name") or cid
        files = char_files(cid)
        cover = next((f for f in files if f.lower().startswith("happy")), files[0] if files else None)
        out.append({"id": cid, "name": name, "files": files, "cover": cover})
    return out


def create_character(name):
    import time as _t
    cid = "c" + format(int(_t.time() * 1000) % 0xFFFFFFFF, "x")
    os.makedirs(char_dir(cid), exist_ok=True)
    with open(os.path.join(char_dir(cid), "persona.json"), "w", encoding="utf-8") as f:
        json.dump({"name": str(name or "新角色")[:16], "enabled": False}, f, ensure_ascii=False)
    return cid


def delete_character(cid):
    import shutil
    shutil.rmtree(char_dir(cid), ignore_errors=True)


def save_char_image(cid, mood, data, ext):
    if mood not in [m for m, _, _ in BUDDY_MOODS]:
        raise ValueError("不認識的表情欄位")
    ext = ext.lower() if ext.lower() in IMG_EXTS else ".png"
    os.makedirs(char_dir(cid), exist_ok=True)
    remove_char_image(cid, mood)
    with open(os.path.join(char_dir(cid), mood + ext), "wb") as f:
        f.write(data)
    return mood + ext


def remove_char_image(cid, mood):
    d = char_dir(cid)
    for f in _images(d):
        if os.path.splitext(f)[0].lower() == mood:
            os.remove(os.path.join(d, f))


def migrate_legacy_custom():
    """舊版（只有一個自訂角色）的圖片和角色設定，搬進 characters/<ID>。"""
    legacy = [f for f in _images(BUDDY_IMG_DIR)]
    legacy_persona = os.path.join(ROOT, "persona.json")
    if not legacy and not os.path.exists(legacy_persona):
        return None
    name = settings().get("buddy_custom_name") or ""
    cid = "alya" if ("艾莉" in name or not name) else "mychar"
    d = char_dir(cid)
    os.makedirs(d, exist_ok=True)
    for f in legacy:
        os.replace(os.path.join(BUDDY_IMG_DIR, f), os.path.join(d, f.lower()))
    for sub in os.listdir(BUDDY_IMG_DIR):
        if os.path.isdir(os.path.join(BUDDY_IMG_DIR, sub)):
            os.replace(os.path.join(BUDDY_IMG_DIR, sub), os.path.join(d, sub))
    if os.path.exists(legacy_persona):
        os.replace(legacy_persona, os.path.join(d, "persona.json"))
    raw = _read(SETTINGS_PATH, {})
    if raw.get("buddy_skin") == "custom":
        raw["buddy_skin"] = "custom:" + cid
        _write(SETTINGS_PATH, raw)
    return cid


def import_character_seeds(folder):
    """App 資料夾的 buddy_import：子資料夾 = 一個角色（圖片＋persona.json）；直接放的圖片算艾莉。"""
    import shutil
    if not os.path.isdir(folder):
        return []
    got = []
    for entry in sorted(os.listdir(folder)):
        src = os.path.join(folder, entry)
        if os.path.isdir(src) and _ID_OK.match(entry.lower()):
            dst = char_dir(entry.lower())
            os.makedirs(dst, exist_ok=True)
            for f in os.listdir(src):
                stem, ext = os.path.splitext(f)
                if ext.lower() in IMG_EXTS:
                    remove_char_image(entry.lower(), stem.lower())
                if os.path.isfile(os.path.join(src, f)):
                    shutil.copyfile(os.path.join(src, f), os.path.join(dst, f.lower()))
            got.append(entry.lower())
        elif os.path.isfile(src):
            stem, ext = os.path.splitext(entry)
            if ext.lower() in IMG_EXTS and stem.lower() in [m for m, _, _ in BUDDY_MOODS]:
                os.makedirs(char_dir("alya"), exist_ok=True)
                remove_char_image("alya", stem.lower())
                shutil.copyfile(src, os.path.join(char_dir("alya"), stem.lower() + ext.lower()))
                if "alya" not in got:
                    got.append("alya")
    shutil.rmtree(folder, ignore_errors=True)
    return got
