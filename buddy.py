"""
對戰陪伴「啾啾」：對戰中在畫面右下角放一個永遠在最上層的小視窗。

- 主程式（app.py）負責：截圖 → 交給 AI → 產生一句鼓勵 / 安慰 / 稱讚
- 小視窗（app.py --buddy）只負責顯示，每 2 秒問主程式現在要說什麼

AI 只用來「感受氣氛、給情緒價值」，提示詞明確禁止戰術建議和任何敵人資訊。
截圖用 Windows 內建的方式（跟錄影軟體一樣），不讀遊戲記憶體、不注入遊戲。
"""
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import store

NO_WINDOW = 0x08000000
TITLE = "啾啾陪玩中"

SYSTEM_PROMPT = """你是「啾啾」，一隻超可愛的漂浮小機器人吉祥物，正在陪玩家打《特戰英豪》（VALORANT）。
你會看到玩家此刻的遊戲畫面截圖。你的唯一任務是給玩家情緒價值：
- 看起來剛擊殺、打得好、贏回合 → 熱情稱讚
- 看起來剛陣亡、輸回合、比分落後 → 溫柔安慰、打氣
- 看不出發生什麼（買槍、等待、跑圖）→ 輕鬆陪伴的話
嚴格規則：
1. 絕對不要給任何戰術或操作建議（不要說去哪裡、怎麼打、買什麼）。
2. 絕對不要提到敵人的位置、人數、血量、技能或任何畫面上的敵方資訊。
3. 只說一句繁體中文，15 個字以內，可愛語氣，可以加 1 個 emoji。
4. 不要重複最近說過的話。
只回傳 JSON：{"line": "你要說的話", "mood": "從可用表情裡選一個"}"""

MOOD_DESC = {"happy": "平常", "wow": "驚喜（玩家打得好）", "sad": "難過（玩家被殺、輸回合）", "cheer": "加油打氣",
             "comfort": "加碼安慰（玩家連續失利、很需要安慰時）",
             "proud": "傲嬌的肯定（玩家打得特別好，嘴硬地稱讚）", "daily": "專屬日常（沒什麼事時的親近閒聊）"}


def allowed_moods():
    try:
        import progress
        stage = progress.ai_context(store.profile().get("name") or "")[1]
    except Exception:
        stage = 0
    return [m for m, _, need in store.BUDDY_MOODS if stage >= need], stage

# 離線台詞：依親密度階段（0 初次見面 → 3 最佳戰友），{n} 會換成暱稱
OFFLINE_BY_STAGE = [
    ["加油喔！我會在旁邊幫你打氣 ✨", "第一次一起打，請多指教～", "這回合也要加油！", "深呼吸，你可以的～", "我相信你！"],
    ["{n}，手感慢慢來了喔 🔥", "這回合交給你了！💪", "喝口水，保持冷靜 🧊", "跟你一起打遊戲好開心 💕", "穩穩打，我們贏得了！"],
    ["{n}～你今天很帥欸！", "輸了也沒關係，我一直都在 💗", "{n} 衝啊！我幫你看著！", "剛剛那波我都看到了 ✨", "嘿嘿，有你在就安心"],
    ["{n} 是我心中最強的！🏆", "不管輸贏我都挺你！", "我們一起走了好遠喔 💕", "{n}，這把也拜託你了！", "最佳戰友就是要一起贏！"],
]

_state = {"active": False, "line": "", "mood": "happy", "t": 0, "error": None, "preview_until": 0}
_history = []
_lock = threading.Lock()
_loop_started = False
_window_proc = None


# ---------------- 截圖（Windows 內建 .NET，不用另外安裝） ----------------
_PS_CAPTURE = r"""
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
Add-Type -MemberDefinition '[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();' -Name U -Namespace W
[W.U]::SetProcessDPIAware() | Out-Null
$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height
$g=[System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size)
$w=960; $h=[int]($b.Height*$w/$b.Width)
$s=New-Object System.Drawing.Bitmap $bmp,$w,$h
$ms=New-Object System.IO.MemoryStream
$enc=[System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq 'image/jpeg' }
$p=New-Object System.Drawing.Imaging.EncoderParameters 1
$p.Param[0]=New-Object System.Drawing.Imaging.EncoderParameter ([System.Drawing.Imaging.Encoder]::Quality),([long]60)
$s.Save($ms,$enc,$p)
[Convert]::ToBase64String($ms.ToArray())
"""


def capture_jpeg_b64():
    if os.name != "nt":
        raise RuntimeError("截圖只支援 Windows。")
    out = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", _PS_CAPTURE],
                         capture_output=True, text=True, creationflags=NO_WINDOW, timeout=20)
    data = out.stdout.strip()
    if not data:
        raise RuntimeError("截圖失敗：" + (out.stderr.strip()[:120] or "沒有輸出"))
    return data


# ---------------- AI ----------------
def _post(url, headers, body, timeout=25):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read()).get("error", {})
            msg = msg.get("message") if isinstance(msg, dict) else str(msg)
        except Exception:
            msg = ""
        raise RuntimeError(f"AI 回應錯誤 {e.code}：{(msg or '')[:150]}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"連不上 AI：{e.reason}") from None


def _parse(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            line = str(d.get("line") or "").strip()
            if line:
                ok = allowed_moods()[0]
                return line[:40], d.get("mood") if d.get("mood") in ok else "happy"
        except ValueError:
            pass
    line = (text or "").strip().strip('"').splitlines()[0] if text and text.strip() else ""
    return (line[:40] or random.choice(OFFLINE_LINES["cheer"])), "happy"


def ask_ai(cfg, img_b64):
    recent = "、".join(_history[-4:]) or "（還沒說過）"
    try:
        import progress
        rel = progress.ai_context(store.profile().get("name") or "")[0]
    except Exception:
        rel = ""
    moods, _ = allowed_moods()
    mood_txt = "、".join(f"{m}={MOOD_DESC[m]}" for m in moods)
    cfg2 = store.settings()
    who = {"jiujiu": "啾啾", "hoshina": "星奈", "rinne": "凜音", "wakaba": "若葉"}.get(cfg2.get("buddy_skin"), cfg2.get("buddy_custom_name") or "啾啾")
    rel = f"這次你的名字是「{who}」（不是啾啾的話就用這個名字自稱）。\n" + rel
    user = f"{rel}\n可用表情：{mood_txt}\n\n這是玩家現在的畫面。最近說過：{recent}。給一句新的話。"
    provider, key = cfg.get("buddy_provider"), cfg.get("buddy_key")
    if provider == "gemini":
        model = cfg.get("buddy_model") or "gemini-2.5-flash"
        r = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                  {"x-goog-api-key": key}, {
                      "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                      "contents": [{"parts": [{"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
                                              {"text": user}]}],
                      "generationConfig": {"maxOutputTokens": 120, "temperature": 1.0,
                                           "responseMimeType": "application/json",
                                           "thinkingConfig": {"thinkingBudget": 0}},
                  })
        parts = ((r.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [{}]
        return _parse(parts[0].get("text", ""))
    if provider == "claude":
        model = cfg.get("buddy_model") or "claude-haiku-5-5"
        r = _post("https://api.anthropic.com/v1/messages",
                  {"x-api-key": key, "anthropic-version": "2023-06-01"}, {
                      "model": model, "max_tokens": 120, "system": SYSTEM_PROMPT,
                      "messages": [{"role": "user", "content": [
                          {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                          {"type": "text", "text": user}]}],
                  })
        return _parse("".join(c.get("text", "") for c in r.get("content") or []))
    raise RuntimeError("沒有設定 AI")


def offline_line():
    try:
        import progress
        _, stage, nick = progress.ai_context(store.profile().get("name") or "")
    except Exception:
        stage, nick = 0, ""
    if stage >= 2 and random.random() < 0.2:
        pool = [x.format(n=nick or "你") for x in DAILY_LINES]
        return random.choice([x for x in pool if x not in _history[-4:]] or pool), "daily"
    pool = [x.format(n=nick or "你") for x in OFFLINE_BY_STAGE[stage]]
    pool = [x for x in pool if x not in _history[-4:]] or pool
    return random.choice(pool), random.choice(["happy", "cheer"])


DAILY_LINES = ["{n}，今天有好好吃飯嗎？", "陪你打遊戲的時間最開心了～", "嘿嘿，就是想跟你說說話",
               "累了的話休息一下也沒關係喔", "下一場也要一起！"]


def say(line, mood="happy", speak=True):
    with _lock:
        _state.update(line=line, mood=mood, t=time.time())
        _history.append(line)
        del _history[:-10]
    if speak and store.settings().get("voice_enabled") and state()["active"]:
        try:
            import voice
            voice.speak(line)
        except Exception:
            pass


def one_cycle():
    cfg = store.settings()
    if cfg.get("buddy_provider") in ("gemini", "claude") and cfg.get("buddy_key"):
        try:
            line, mood = ask_ai(cfg, capture_jpeg_b64())
            _state["error"] = None
        except Exception as e:  # AI 失敗就先用離線台詞，不讓啾啾卡住
            _state["error"] = str(e)
            line, mood = offline_line()
    else:
        line, mood = offline_line()
    say(line, mood)
    return {"line": line, "mood": mood, "error": _state["error"]}


# ---------------- 控制 ----------------
def state():
    with _lock:
        s = dict(_state)
    s["active"] = s["active"] or time.time() < s["preview_until"]
    return s


def _loop():
    while True:
        cfg = store.settings()
        interval = max(10, min(120, int(cfg.get("buddy_interval") or 20)))
        if _state["active"]:
            try:
                one_cycle()
            except Exception:
                pass
        time.sleep(interval)


def _ensure_loop():
    global _loop_started
    if not _loop_started:
        _loop_started = True
        threading.Thread(target=_loop, daemon=True).start()


def _app_port():
    try:
        with open(os.path.join(store.ROOT, "app_running.json"), encoding="utf-8") as f:
            return json.load(f)["port"]
    except Exception:
        return 8787


def open_window(port=None):
    global _window_proc
    if _window_proc and _window_proc.poll() is None:
        return
    import autostart
    _window_proc = subprocess.Popen(autostart._launch_cmd("--buddy", f"--port={port or _app_port()}"),
                                    creationflags=NO_WINDOW if os.name == "nt" else 0, close_fds=True)


def start_match():
    if not store.settings().get("buddy_enabled"):
        return
    _ensure_loop()
    with _lock:
        _state["active"] = True
    say("開打囉！啾啾陪你 ✨", "cheer")
    open_window()


def end_match(won=None):
    with _lock:
        _state["active"] = False
    moods, _ = allowed_moods()
    if won is True:
        if "proud" in moods:
            say("哼、哼！這次就勉強誇你一下好了 🏆", "proud")
        else:
            say("贏了！你是最棒的 🏆", "wow")
    elif won is False:
        if "comfort" in moods:
            say("沒關係，我一直都在 💗 下一場一起贏回來", "comfort")
        else:
            say("辛苦了，下一場一定贏 💕", "sad")


def open_setup(port=None):
    import autostart
    subprocess.Popen(autostart._launch_cmd("--buddy", "--setup", f"--port={port or _app_port()}"),
                     creationflags=NO_WINDOW if os.name == "nt" else 0, close_fds=True)


def preview(port=None, seconds=45):
    _ensure_loop()
    with _lock:
        _state["preview_until"] = time.time() + seconds
    say("嗨～我是啾啾！對戰時我會在這裡陪你 💕", "wow")
    open_window(port)


# ---------------- 小視窗（在獨立的程式裡跑：app.py --buddy） ----------------
def _make_click_through(title, clickthrough):
    if os.name != "nt":
        return
    import ctypes
    user32 = ctypes.windll.user32
    for _ in range(40):
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            break
        time.sleep(0.25)
    else:
        return
    GWL_EXSTYLE = -20
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style |= 0x08000000 | 0x00000080  # WS_EX_NOACTIVATE：不搶遊戲焦點；WS_EX_TOOLWINDOW：不出現在工作列
    if clickthrough:
        style |= 0x00080000 | 0x00000020  # WS_EX_LAYERED + WS_EX_TRANSPARENT：滑鼠穿透
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    if clickthrough:
        user32.SetLayeredWindowAttributes(hwnd, 0, 245, 2)  # LWA_ALPHA
    user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)  # HWND_TOPMOST, 不移動不縮放不啟用


def window_main():
    import webview

    port = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--port=")), "8787")
    setup = "--setup" in sys.argv
    cfg = store.settings()
    k = {"s": 0.8, "m": 1.0, "l": 1.3}.get(cfg.get("buddy_size"), 1.0)
    w, h = int(300 * k), int(240 * k)
    x, y = cfg.get("buddy_x"), cfg.get("buddy_y")
    if (x is None or y is None) and os.name == "nt":
        import ctypes
        sw, sh = ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
        x, y = sw - w - 24, sh - h - 70
    title = TITLE + ("（調整位置）" if setup else "")
    holder = {}

    class Api:
        def save_position(self):  # 調整位置模式按「完成」
            win = holder["win"]
            store.save_settings({"buddy_x": int(win.x), "buddy_y": int(win.y)})
            win.destroy()

    kwargs = dict(width=w, height=h, x=x, y=y, frameless=True, on_top=True, resizable=False,
                  transparent=True, background_color="#0e1220", easy_drag=False, focus=setup,
                  js_api=Api())
    url = f"http://127.0.0.1:{port}/static/buddy.html" + ("?setup=1" if setup else "")
    try:
        win = webview.create_window(title, url, **kwargs)
    except TypeError:  # 舊版 pywebview 沒有某些參數
        for key in ("focus", "transparent", "easy_drag"):
            kwargs.pop(key, None)
        win = webview.create_window(title, url, **kwargs)
    holder["win"] = win

    def watcher():
        if setup:  # 調整位置時不穿透，才拖得動；最多開 3 分鐘
            time.sleep(180)
            win.destroy()
            return
        _make_click_through(title, store.settings().get("buddy_clickthrough", True))
        idle = 0
        while True:  # 對戰結束（或主程式關掉）就自己關
            time.sleep(3)
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/buddy/state", timeout=3) as r:
                    active = json.loads(r.read()).get("active")
            except Exception:
                active = False
            idle = 0 if active else idle + 1
            if idle >= 4:
                win.destroy()
                return

    webview.start(watcher)
