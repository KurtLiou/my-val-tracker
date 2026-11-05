"""
開特戰英豪時自動打開 VAL 小戰績。

原理：一個很輕的背景小程式（開機時自動執行），每 5 秒看一次工作管理員裡有沒有
VALORANT 的程式。有的話就打開 App。它只看「程式名稱清單」，不碰遊戲本身。
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

import store

GAME_EXES = ("VALORANT-Win64-Shipping.exe", "VALORANT.exe")
WATCH_LOG = os.path.join(store.ROOT, "watch.log")
STARTUP_DIR = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
SHORTCUT = os.path.join(STARTUP_DIR, "VAL小戰績-自動啟動.lnk")
APP_INFO = os.path.join(store.ROOT, "app_running.json")
WATCH_LOCK_PORT = 8786
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW：跑指令時不跳黑色視窗


def log(msg):
    """監看程式的紀錄（設定頁的「自動啟動診斷」會顯示最後幾行）。"""
    try:
        if os.path.exists(WATCH_LOG) and os.path.getsize(WATCH_LOG) > 200_000:
            os.replace(WATCH_LOG, WATCH_LOG + ".old")
        with open(WATCH_LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def log_tail(n=12):
    try:
        with open(WATCH_LOG, encoding="utf-8", errors="ignore") as f:
            return f.read().splitlines()[-n:]
    except OSError:
        return []


# ---------- 怎麼啟動自己 ----------
def _launch_cmd(*args):
    if getattr(sys, "frozen", False):  # 打包成 exe
        return [sys.executable, *args]
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        cand = exe[:-10] + "pythonw.exe"
        if os.path.exists(cand):
            exe = cand
    return [exe, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py"), *args]


# ---------- 開機自動執行（啟動資料夾的捷徑） ----------
def enabled():
    return os.path.exists(SHORTCUT)


def _ps_quote(s):
    return "'" + str(s).replace("'", "''") + "'"


def enable():
    if os.name != "nt":
        raise RuntimeError("自動啟動只支援 Windows。")
    cmd = _launch_cmd("--watch")
    target, arguments = cmd[0], " ".join(f'"{a}"' for a in cmd[1:])
    workdir = os.path.dirname(os.path.abspath(cmd[1] if len(cmd) > 1 else cmd[0]))
    icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    script = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(" + _ps_quote(SHORTCUT) + ");"
        "$s.TargetPath=" + _ps_quote(target) + ";"
        "$s.Arguments=" + _ps_quote(arguments) + ";"
        "$s.WorkingDirectory=" + _ps_quote(workdir) + ";"
        + ("$s.IconLocation=" + _ps_quote(icon) + ";" if os.path.exists(icon) else "")
        + "$s.Save()"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                       capture_output=True, text=True, creationflags=NO_WINDOW, timeout=20)
    if not os.path.exists(SHORTCUT):
        raise RuntimeError("建立開機捷徑失敗：" + (r.stderr.strip()[:200] or "不明原因"))
    log(f"已建立開機捷徑：{target} {arguments}")
    # 馬上開始監看，不用等下次開機
    if not watcher_running():
        subprocess.Popen(cmd, creationflags=NO_WINDOW, close_fds=True)
        time.sleep(1.5)
    if not watcher_running():
        raise RuntimeError("捷徑建好了，但監看程式沒有啟動。請看設定頁的診斷紀錄。")


def _make_shortcut(path_expr, cmd, name):
    """用 PowerShell 建立 .lnk 捷徑。path_expr 是 PowerShell 運算式（資料夾）。"""
    target, arguments = cmd[0], " ".join(f'"{a}"' for a in cmd[1:])
    here = os.path.dirname(os.path.abspath(__file__))
    icon = os.path.join(here, "icon.ico")
    script = (
        "$d=" + path_expr + ";"
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d " + _ps_quote(name) + "));"
        "$s.TargetPath=" + _ps_quote(target) + ";"
        "$s.Arguments=" + _ps_quote(arguments) + ";"
        "$s.WorkingDirectory=" + _ps_quote(here) + ";"
        + ("$s.IconLocation=" + _ps_quote(icon) + ";" if os.path.exists(icon) else "")
        + "$s.Save(); Write-Output (Join-Path $d " + _ps_quote(name) + ")"
    )
    out = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                         check=True, capture_output=True, text=True, creationflags=NO_WINDOW, timeout=20)
    return out.stdout.strip()


def desktop_shortcut():
    """在桌面建立「VAL 小戰績」捷徑（桌面在 OneDrive 裡也找得到）。"""
    if os.name != "nt":
        raise RuntimeError("只支援 Windows。")
    return _make_shortcut("[Environment]::GetFolderPath('Desktop')", _launch_cmd(), "VAL 小戰績.lnk")


def disable():
    if os.path.exists(SHORTCUT):
        os.remove(SHORTCUT)


# ---------- App 是否已經開著 ----------
def mark_app_running(port):
    try:
        with open(APP_INFO, "w", encoding="utf-8") as f:
            json.dump({"port": port, "pid": os.getpid(), "t": time.time()}, f)
    except OSError:
        pass


def mark_app_closed():
    try:
        os.remove(APP_INFO)
    except OSError:
        pass


def app_running():
    try:
        with open(APP_INFO, encoding="utf-8") as f:
            port = json.load(f)["port"]
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=2)
        return True
    except Exception:
        return False


# ---------- 監看遊戲 ----------
def game_running():
    try:
        out = subprocess.run(["tasklist", "/NH", "/FO", "CSV"], capture_output=True, text=True,
                             errors="ignore", creationflags=NO_WINDOW, timeout=15).stdout.lower()
        return any(f'"{exe.lower()}"' in out for exe in GAME_EXES)
    except Exception as e:
        log(f"讀取工作清單失敗：{e}")
        return False


def watcher_running():
    """監看程式有在跑嗎？（它會佔用 8786 port 當作鎖）"""
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", WATCH_LOCK_PORT))
        return False
    except OSError:
        return True
    finally:
        s.close()


def diagnose():
    return {"windows": os.name == "nt", "enabled": enabled(), "shortcut": SHORTCUT,
            "watcher_running": watcher_running() if os.name == "nt" else False,
            "game_running": game_running() if os.name == "nt" else False,
            "launch_cmd": " ".join(_launch_cmd()), "log": log_tail()}


def watch():
    # 用一個本機 port 當鎖，避免同時跑兩個監看程式
    lock = socket.socket()
    try:
        lock.bind(("127.0.0.1", WATCH_LOCK_PORT))
    except OSError:
        log("監看程式已經在跑了，這個就不重複啟動")
        return
    log(f"監看程式啟動（{sys.executable}）")
    was_running = False
    while True:
        try:
            running = game_running()
            if running and not was_running:
                log("偵測到特戰英豪啟動")
                if app_running():
                    log("App 已經開著，不用再開")
                else:
                    cmd = _launch_cmd()
                    subprocess.Popen(cmd, creationflags=NO_WINDOW, close_fds=True,
                                     cwd=os.path.dirname(os.path.abspath(__file__)))
                    log("已打開 App：" + " ".join(cmd))
            elif was_running and not running:
                log("特戰英豪已關閉")
            was_running = running
        except Exception as e:
            log(f"錯誤：{e}")
        time.sleep(5)
