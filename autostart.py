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

GAME_EXE = "VALORANT-Win64-Shipping.exe"
STARTUP_DIR = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
SHORTCUT = os.path.join(STARTUP_DIR, "VAL小戰績-自動啟動.lnk")
APP_INFO = os.path.join(store.ROOT, "app_running.json")
WATCH_LOCK_PORT = 8786
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW：跑指令時不跳黑色視窗


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
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                   check=True, creationflags=NO_WINDOW, timeout=20)
    # 馬上開始監看，不用等下次開機
    subprocess.Popen(cmd, creationflags=NO_WINDOW, close_fds=True)


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
        out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {GAME_EXE}", "/NH"],
                             capture_output=True, text=True, creationflags=NO_WINDOW, timeout=10).stdout
        return GAME_EXE.lower() in out.lower()
    except Exception:
        return False


def watch():
    # 用一個本機 port 當鎖，避免同時跑兩個監看程式
    lock = socket.socket()
    try:
        lock.bind(("127.0.0.1", WATCH_LOCK_PORT))
    except OSError:
        return
    was_running = False
    while True:
        running = game_running()
        if running and not was_running and not app_running():
            subprocess.Popen(_launch_cmd(), creationflags=NO_WINDOW, close_fds=True)
        was_running = running
        time.sleep(5)
