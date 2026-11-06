"""
陪伴角色的語音。

引擎：
1. 我的聲音（聲音複製）：用你自己錄的聲音，透過電腦上的 GPT-SoVITS 即時合成。
   只能用你本人、或明確同意你使用的人的聲音。
2. Microsoft Edge 線上神經語音（自然、有台灣女聲）：第一次用會自動安裝 edge-tts 套件。
   這不是官方開放的介面，哪天失效就自動改用 3。
3. Windows 內建語音（System.Speech）：一定能用，但聲音比較機器。

每個角色可以有自己的聲音（存在角色設定的 voice 欄位）；沒設定就用全域語音設定。
俄文段落一律用俄文神經語音念，翻譯不念。
播放用 Windows 內建的播放器（PowerShell 背景執行），不會跳出視窗。
"""
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import store

NO_WINDOW = 0x08000000
TTS_DIR = os.path.join(store.ROOT, "tts")
VOICE_DIR = os.path.join(store.ROOT, "voices")
for _d in (TTS_DIR, VOICE_DIR):
    os.makedirs(_d, exist_ok=True)

VOICES = [
    ("zh-TW-HsiaoYuNeural", "曉雨（台灣・活潑）"),
    ("zh-TW-HsiaoChenNeural", "曉臻（台灣・溫柔）"),
    ("zh-CN-XiaoyiNeural", "曉伊（可愛）"),
    ("zh-CN-XiaoxiaoNeural", "曉曉（自然）"),
    ("zh-TW-YunJheNeural", "雲哲（台灣・男聲）"),
]
RU_VOICE = "ru-RU-SvetlanaNeural"
AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".flac", ".ogg")

_speaking = threading.Lock()
_install_state = {"tried": False, "ok": None, "error": None}
_sovits = {"proc": None, "error": None, "starting": False}

# 依序播放多個檔案（俄文段、中文段）
_PS_PLAY = r"""
Add-Type -AssemblyName PresentationCore
foreach ($f in ($env:VT_FILES -split '\|')) {
  $p = New-Object System.Windows.Media.MediaPlayer
  $p.Volume = [double]$env:VT_VOL
  $p.Open([uri]$f)
  $i = 0; while (-not $p.NaturalDuration.HasTimeSpan -and $i -lt 60) { Start-Sleep -Milliseconds 100; $i++ }
  $p.Play()
  $d = 3000; if ($p.NaturalDuration.HasTimeSpan) { $d = $p.NaturalDuration.TimeSpan.TotalMilliseconds }
  Start-Sleep -Milliseconds ([int]$d + 120)
  $p.Close()
}
"""

# Windows 內建語音：每段用對應語言的聲音；電腦沒有俄文語音的話就念中文翻譯
_PS_SAPI = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = [int]$env:VT_RATE
$s.Volume = [int]$env:VT_VOL
$all = $s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo }
$zh = $all | Where-Object { $_.Culture.Name -like 'zh*' } | Select-Object -First 1
$ru = $all | Where-Object { $_.Culture.Name -like 'ru*' } | Select-Object -First 1
foreach ($seg in ($env:VT_SEGS | ConvertFrom-Json)) {
  if ($seg.lang -eq 'ru') {
    if ($ru) { $s.SelectVoice($ru.Name); $s.Speak($seg.text) }
    elseif ($seg.alt) { if ($zh) { $s.SelectVoice($zh.Name) }; $s.Speak($seg.alt) }
  } else { if ($zh) { $s.SelectVoice($zh.Name) }; $s.Speak($seg.text) }
}
"""


def _ps(script, env, wait):
    full_env = {**os.environ, **env}
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]
    if wait:
        r = subprocess.run(cmd, env=full_env, capture_output=True, text=True, creationflags=NO_WINDOW, timeout=60)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or "").strip()[:200] or "播放失敗")
    else:
        subprocess.Popen(cmd, env=full_env, creationflags=NO_WINDOW, close_fds=True)


def _python_exe():
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        cand = exe[:-11] + "python.exe"
        if os.path.exists(cand):
            return cand
    return exe


# ================= 聲音庫（你錄的聲音） =================
_VID = re.compile(r"^[a-z0-9_-]{1,32}$")


def _vdir(vid):
    if not _VID.match(str(vid or "")):
        raise ValueError("聲音 ID 不正確")
    return os.path.join(VOICE_DIR, vid)


def list_voices():
    out = []
    for vid in sorted(os.listdir(VOICE_DIR)):
        d = os.path.join(VOICE_DIR, vid)
        if not _VID.match(vid) or not os.path.isdir(d):
            continue
        meta = store._read(os.path.join(d, "meta.json"), {})
        ref = next((f for f in os.listdir(d) if f.startswith("ref") and f.lower().endswith(AUDIO_EXTS)), None)
        out.append({"id": vid, "name": meta.get("name") or vid, "text": meta.get("text", ""),
                    "lang": meta.get("lang", "zh"), "ref": ref, "seconds": meta.get("seconds")})
    return out


def _wav_seconds(path):
    try:
        import wave
        with wave.open(path) as w:
            return round(w.getnframes() / float(w.getframerate()), 1)
    except Exception:
        return None


def add_voice(name, text, lang, data, ext):
    ext = ext.lower() if ext.lower() in AUDIO_EXTS else ".wav"
    vid = "v" + format(int(time.time() * 1000) % 0xFFFFFFFF, "x")
    d = _vdir(vid)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "ref" + ext)
    with open(path, "wb") as f:
        f.write(data)
    secs = _wav_seconds(path) if ext == ".wav" else None
    meta = {"name": str(name or "我的聲音")[:16], "text": str(text or "").strip()[:200],
            "lang": lang if lang in ("zh", "en", "ja", "ko", "yue") else "zh", "seconds": secs}
    store._write(os.path.join(d, "meta.json"), meta)
    return {"id": vid, **meta}


def delete_voice(vid):
    shutil.rmtree(_vdir(vid), ignore_errors=True)


def voice_ref(vid):
    v = next((x for x in list_voices() if x["id"] == vid), None)
    if not v or not v["ref"]:
        raise RuntimeError("找不到這個聲音的錄音")
    return os.path.join(_vdir(vid), v["ref"]), v


# ================= GPT-SoVITS 本機服務 =================
def sovits_port():
    return int(store.settings().get("sovits_port") or 9880)


def find_sovits():
    """沒設定資料夾時，到 C:\\、D:\\、E:\\ 根目錄找 GPT-SoVITS 開頭的資料夾。"""
    for drive in ("D:\\", "C:\\", "E:\\"):
        try:
            names = sorted(os.listdir(drive), reverse=True)
        except OSError:
            continue
        for n in names:
            d = os.path.join(drive, n)
            if n.lower().startswith("gpt-sovits") and os.path.exists(os.path.join(d, "api_v2.py")):
                return d
    return ""


def sovits_dir():
    d = store.settings().get("sovits_dir") or ""
    if not d and os.name == "nt":
        d = find_sovits()
        if d:
            store.save_settings({"sovits_dir": d})
    return d


def sovits_dir_ok(d=None):
    d = d or sovits_dir()
    return bool(d) and os.path.exists(os.path.join(d, "api_v2.py"))


def _sovits_python(d):
    for cand in (os.path.join(d, "runtime", "python.exe"), os.path.join(d, "runtime", "python")):
        if os.path.exists(cand):
            return cand
    return None


def sovits_running():
    s = socket.socket()
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", sovits_port()))
        return True
    except OSError:
        return False
    finally:
        s.close()


def sovits_status():
    d = sovits_dir()
    return {"dir": d, "dir_ok": sovits_dir_ok(d), "python_ok": bool(d and _sovits_python(d)),
            "running": sovits_running(), "starting": _sovits["starting"], "error": _sovits["error"],
            "port": sovits_port()}


def start_sovits(wait=False):
    """在背景啟動 GPT-SoVITS 的 API（api_v2.py）。已經在跑就不重複啟動。"""
    if sovits_running():
        return True
    d = sovits_dir()
    if not sovits_dir_ok(d):
        _sovits["error"] = "還沒設定 GPT-SoVITS 資料夾，或資料夾裡找不到 api_v2.py"
        return False
    py = _sovits_python(d)
    if not py:
        _sovits["error"] = "GPT-SoVITS 資料夾裡找不到 runtime\\python.exe，請用官方的 Windows 整合包"
        return False
    if not (_sovits["proc"] and _sovits["proc"].poll() is None):
        log = open(os.path.join(store.ROOT, "sovits.log"), "ab")
        _sovits["proc"] = subprocess.Popen(
            [py, "api_v2.py", "-a", "127.0.0.1", "-p", str(sovits_port())], cwd=d, stdout=log, stderr=log,
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},  # 繁中 Windows 預設 cp950，印日文字會當掉
            creationflags=NO_WINDOW if os.name == "nt" else 0)
        _sovits["error"] = None
    if not wait:
        return True
    _sovits["starting"] = True
    try:
        for _ in range(120):  # 第一次載入模型可能要一兩分鐘
            if sovits_running():
                return True
            if _sovits["proc"].poll() is not None:
                _sovits["error"] = "GPT-SoVITS 啟動失敗，請看 %USERPROFILE%\\.valtracker\\sovits.log"
                return False
            time.sleep(1)
        _sovits["error"] = "GPT-SoVITS 啟動太久（超過 2 分鐘）"
        return False
    finally:
        _sovits["starting"] = False


def restart_sovits():
    stop_sovits()
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{sovits_port()}/control?command=exit", timeout=5)
    except Exception:
        pass
    for _ in range(20):
        if not sovits_running():
            break
        time.sleep(0.5)
    return start_sovits(wait=True)


def stop_sovits():
    p = _sovits.get("proc")
    if p and p.poll() is None:
        p.terminate()


def _sovits_file(text, vid, speed=1.0):
    ref, v = voice_ref(vid)
    key = hashlib.md5(f"sovits|{vid}|{speed}|{text}".encode()).hexdigest()
    path = os.path.join(TTS_DIR, key + ".wav")
    if os.path.exists(path):
        return path
    if not sovits_running() and not start_sovits(wait=True):
        raise RuntimeError(_sovits["error"] or "GPT-SoVITS 沒有在跑")
    q = {"text": text, "text_lang": "zh", "ref_audio_path": ref, "prompt_text": v["text"],
         "prompt_lang": v["lang"], "media_type": "wav", "streaming_mode": "false",
         "speed_factor": str(speed), "text_split_method": "cut5"}
    url = f"http://127.0.0.1:{sovits_port()}/tts?" + urllib.parse.urlencode(q)
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "ignore")
        if "codec" in msg and not _sovits.get("utf8_retry"):
            _sovits["utf8_retry"] = True  # 舊的 GPT-SoVITS 不是用 UTF-8 開的：關掉重開一次
            restart_sovits()
            return _sovits_file(text, vid, speed)
        raise RuntimeError("GPT-SoVITS 合成失敗：" + msg[:150]) from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"連不上 GPT-SoVITS：{e.reason}") from None
    with open(path + ".part", "wb") as f:
        f.write(data)
    os.replace(path + ".part", path)
    return path


# ================= Edge 神經語音 =================
def ensure_edge_tts():
    """沒有 edge-tts 就自動安裝一次（在背景）。"""
    try:
        import edge_tts  # noqa: F401
        _install_state["ok"] = True
        return True
    except ImportError:
        pass
    if getattr(sys, "frozen", False):
        _install_state.update(ok=False, error="exe 版沒有內建 edge-tts，請用 2_start.bat 開的版本")
        return False
    if not _install_state["tried"]:
        _install_state["tried"] = True
        try:
            r = subprocess.run([_python_exe(), "-m", "pip", "install", "--quiet", "edge-tts"],
                               capture_output=True, text=True, creationflags=NO_WINDOW if os.name == "nt" else 0, timeout=180)
            if r.returncode != 0:
                raise RuntimeError(r.stderr.strip()[-200:])
            import importlib
            importlib.invalidate_caches()
            import edge_tts  # noqa: F401
            _install_state["ok"] = True
            return True
        except Exception as e:
            _install_state.update(ok=False, error=f"自動安裝 edge-tts 失敗：{e}")
    return False


def _edge_file(text, vc, voice=None):
    import asyncio
    import edge_tts
    voice = voice or vc.get("name") or VOICES[0][0]
    rate = f'{int(vc.get("rate") or 0):+d}%'
    pitch = f'{int(vc.get("pitch") or 0):+d}Hz'
    key = hashlib.md5(f"{voice}|{rate}|{pitch}|{text}".encode()).hexdigest()
    path = os.path.join(TTS_DIR, key + ".mp3")
    if not os.path.exists(path):
        async def run():
            await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(path + ".part")
        asyncio.run(run())
        os.replace(path + ".part", path)
    return path


def _trim_cache(keep=400):
    try:
        files = sorted((os.path.join(TTS_DIR, f) for f in os.listdir(TTS_DIR) if f.endswith((".mp3", ".wav"))),
                       key=os.path.getmtime)
        for f in files[:-keep]:
            os.remove(f)
    except OSError:
        pass


# ================= 要用哪個聲音 =================
def resolve_voice(override=None):
    """回傳 {"engine": "clone"|"edge"|"windows", ...}。角色有自己的聲音就用角色的。"""
    cfg = store.settings()
    base = {"engine": cfg.get("voice_engine", "edge"), "name": cfg.get("voice_name"),
            "rate": cfg.get("voice_rate", 0), "pitch": cfg.get("voice_pitch", 0), "clone": cfg.get("voice_clone")}
    vc = override
    if vc is None:
        cid = store.current_char()
        if cid:
            import persona
            vc = (persona.load(cid).get("voice") or {})
    if vc and vc.get("engine") and vc.get("engine") != "default":
        return {**base, **{k: v for k, v in vc.items() if v not in (None, "")}}
    return base


def speak(text, wait=False, override=None):
    """念出一句話。回傳用了哪個引擎；wait=True 時會等念完（測試按鈕用）。"""
    cfg = store.settings()
    if os.name != "nt":
        return {"engine": None, "error": "語音只支援 Windows"}
    if not text:
        return {"engine": None}
    if not _speaking.acquire(blocking=wait):
        return {"engine": None, "skipped": True}  # 上一句還在念，就跳過，不要疊在一起

    import persona
    segs = persona.speech(text) or [("zh", text)]
    alts = [m.group(3) or "" for m in persona.RU_SEG.finditer(text)]  # 沒有俄文聲音時改念翻譯
    vc = resolve_voice(override)

    def job():
        try:
            vol = max(0, min(100, int(cfg.get("voice_volume") or 70)))
            err = None
            edge_ok = None
            if vc["engine"] in ("clone", "edge"):
                try:
                    files = []
                    for lang, t in segs:
                        if lang == "ru":  # 俄文一律用俄文神經語音
                            if edge_ok is None:
                                edge_ok = ensure_edge_tts()
                            if edge_ok:
                                files.append(_edge_file(t, vc, RU_VOICE))
                        elif vc["engine"] == "clone" and vc.get("clone"):
                            speed = max(0.6, min(1.6, 1 + int(vc.get("rate") or 0) / 100))
                            files.append(_sovits_file(t, vc["clone"], speed))
                        else:
                            if edge_ok is None:
                                edge_ok = ensure_edge_tts()
                            if not edge_ok:
                                raise RuntimeError(_install_state.get("error") or "Edge 語音無法使用")
                            files.append(_edge_file(t, vc))
                    _trim_cache()
                    if files:
                        _ps(_PS_PLAY, {"VT_FILES": "|".join(files), "VT_VOL": str(vol / 100)}, wait=True)
                    return {"engine": vc["engine"]}
                except Exception as e:
                    err = f"{'我的聲音' if vc['engine'] == 'clone' else 'Edge 語音'}失敗，改用 Windows 內建語音（{e}）"
            rate = max(-10, min(10, round(int(vc.get("rate") or 0) / 10)))
            ru_i = iter(alts)
            payload = [{"lang": lang, "text": t, "alt": next(ru_i, "") if lang == "ru" else ""} for lang, t in segs]
            _ps(_PS_SAPI, {"VT_SEGS": json.dumps(payload, ensure_ascii=False), "VT_RATE": str(rate), "VT_VOL": str(vol)}, wait=True)
            return {"engine": "windows", "error": err}
        finally:
            _speaking.release()

    if wait:
        try:
            return job()
        except Exception as e:
            return {"engine": None, "error": str(e)}
    threading.Thread(target=lambda: _safe(job), daemon=True).start()
    return {"engine": "queued"}


def _safe(fn):
    try:
        fn()
    except Exception:
        pass
