"""
檢查更新：從 GitHub repo 下載新版檔案。

repo 根目錄要有 version.json：
  {"version": "2.1.0", "notes": "這版改了什麼", "files": ["app.py", "static/app.js", ...]}
App 會比對版本號，有新版就把 files 列出的檔案一個個下載下來覆蓋。
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
LOCAL_VERSION = os.path.join(BASE, "version.json")
SAFE = re.compile(r"^[A-Za-z0-9_\-./]+$")


class UpdateError(Exception):
    pass


def local_version():
    try:
        with open(LOCAL_VERSION, encoding="utf-8") as f:
            return json.load(f).get("version", "0")
    except (OSError, ValueError):
        return "0"


def _vtuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:4]) or (0,)


def _raw(repo, path):
    if not re.match(r"^[\w.-]+/[\w.-]+$", repo or ""):
        raise UpdateError("更新來源格式要像「帳號/repo名稱」。")
    url = f"https://raw.githubusercontent.com/{repo}/main/{path}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Cache-Control": "no-cache"}),
                                    timeout=20) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise UpdateError(f"下載 {path} 失敗（HTTP {e.code}）。repo 要是公開的，分支叫 main。") from None
    except urllib.error.URLError as e:
        raise UpdateError(f"連不上 GitHub：{e.reason}") from None


def check(repo):
    remote = json.loads(_raw(repo, "version.json"))
    cur = local_version()
    return {"current": cur, "latest": remote.get("version"), "notes": remote.get("notes", ""),
            "available": _vtuple(remote.get("version")) > _vtuple(cur),
            "frozen": bool(getattr(sys, "frozen", False))}


def apply(repo):
    if getattr(sys, "frozen", False):
        raise UpdateError("exe 版不能自己換檔案。請用「2_start.bat」開的版本更新，再重新執行「4_build_exe.bat」。")
    remote = json.loads(_raw(repo, "version.json"))
    files = remote.get("files") or []
    downloaded = {}
    for rel in files:  # 先全部下載成功才覆蓋，避免更新到一半壞掉
        if not SAFE.match(rel) or ".." in rel or rel.startswith("/"):
            raise UpdateError(f"不安全的檔名：{rel}")
        downloaded[rel] = _raw(repo, rel)
    downloaded["version.json"] = json.dumps(remote, ensure_ascii=False, indent=2).encode()
    for rel, data in downloaded.items():
        full = os.path.join(BASE, *rel.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        tmp = full + ".new"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, full)
    return {"updated": len(downloaded), "version": remote.get("version")}
