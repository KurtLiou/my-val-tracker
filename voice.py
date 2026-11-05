"""
陪伴角色的語音。

1. Microsoft Edge 線上神經語音（自然、有台灣女聲）：第一次用會自動安裝 edge-tts 套件。
   這不是官方開放的介面，哪天失效就自動改用 2。
2. Windows 內建語音（System.Speech）：一定能用，但聲音比較機器。

播放用 Windows 內建的播放器（PowerShell 背景執行），不會跳出視窗。
"""
import hashlib
import os
import subprocess
import sys
import threading

import store

NO_WINDOW = 0x08000000
TTS_DIR = os.path.join(store.ROOT, "tts")
os.makedirs(TTS_DIR, exist_ok=True)

VOICES = [
    ("zh-TW-HsiaoYuNeural", "曉雨（台灣・活潑）"),
    ("zh-TW-HsiaoChenNeural", "曉臻（台灣・溫柔）"),
    ("zh-CN-XiaoyiNeural", "曉伊（可愛）"),
    ("zh-CN-XiaoxiaoNeural", "曉曉（自然）"),
    ("zh-TW-YunJheNeural", "雲哲（台灣・男聲）"),
]

_speaking = threading.Lock()
_install_state = {"tried": False, "ok": None, "error": None}

_PS_PLAY = r"""
Add-Type -AssemblyName PresentationCore
$p = New-Object System.Windows.Media.MediaPlayer
$p.Volume = [double]$env:VT_VOL
$p.Open([uri]$env:VT_FILE)
$i = 0; while (-not $p.NaturalDuration.HasTimeSpan -and $i -lt 60) { Start-Sleep -Milliseconds 100; $i++ }
$p.Play()
$d = 4000; if ($p.NaturalDuration.HasTimeSpan) { $d = $p.NaturalDuration.TimeSpan.TotalMilliseconds }
Start-Sleep -Milliseconds ([int]$d + 300)
$p.Close()
"""

_PS_SAPI = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$v = $s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo } | Where-Object { $_.Culture.Name -like 'zh*' } | Select-Object -First 1
if ($v) { $s.SelectVoice($v.Name) }
$s.Rate = [int]$env:VT_RATE
$s.Volume = [int]$env:VT_VOL
$s.Speak($env:VT_TEXT)
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


def _edge_file(text, cfg):
    import asyncio
    import edge_tts
    voice = cfg.get("voice_name") or VOICES[0][0]
    rate = f'{int(cfg.get("voice_rate") or 0):+d}%'
    pitch = f'{int(cfg.get("voice_pitch") or 0):+d}Hz'
    key = hashlib.md5(f"{voice}|{rate}|{pitch}|{text}".encode()).hexdigest()
    path = os.path.join(TTS_DIR, key + ".mp3")
    if not os.path.exists(path):
        async def run():
            await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(path + ".part")
        asyncio.run(run())
        os.replace(path + ".part", path)
    _trim_cache()
    return path


def _trim_cache(keep=300):
    try:
        files = sorted((os.path.join(TTS_DIR, f) for f in os.listdir(TTS_DIR) if f.endswith(".mp3")), key=os.path.getmtime)
        for f in files[:-keep]:
            os.remove(f)
    except OSError:
        pass


def speak(text, wait=False):
    """念出一句話。回傳用了哪個引擎；wait=True 時會等念完（測試按鈕用）。"""
    cfg = store.settings()
    if os.name != "nt":
        return {"engine": None, "error": "語音只支援 Windows"}
    if not text:
        return {"engine": None}
    if not _speaking.acquire(blocking=wait):
        return {"engine": None, "skipped": True}  # 上一句還在念，就跳過，不要疊在一起

    def job():
        try:
            vol = max(0, min(100, int(cfg.get("voice_volume") or 70)))
            if cfg.get("voice_engine", "edge") == "edge" and ensure_edge_tts():
                try:
                    path = _edge_file(text, cfg)
                    _ps(_PS_PLAY, {"VT_FILE": path, "VT_VOL": str(vol / 100)}, wait=True)
                    return {"engine": "edge"}
                except Exception as e:
                    err = f"Edge 語音失敗，改用 Windows 內建語音（{e}）"
            else:
                err = _install_state.get("error") if cfg.get("voice_engine", "edge") == "edge" else None
            rate = max(-10, min(10, round(int(cfg.get("voice_rate") or 0) / 10)))
            _ps(_PS_SAPI, {"VT_TEXT": text, "VT_RATE": str(rate), "VT_VOL": str(vol)}, wait=True)
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
