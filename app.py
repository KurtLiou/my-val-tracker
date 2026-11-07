"""
VAL 小戰績 — 特戰英豪個人戰績工具（桌面 App）

執行：python app.py            開 App 視窗（需要 pywebview；沒裝會改用瀏覽器）
展示：python app.py --demo     假資料，看所有頁面
瀏覽器：python app.py --browser 改用瀏覽器開
監看：python app.py --watch    背景監看，開特戰英豪時自動打開 App
"""
import base64
import json
import os
import sys
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DEMO = "--demo" in sys.argv
if DEMO:
    os.environ["VALTRACKER_DEMO"] = "1"  # 展示模式的養成存檔分開放
BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(BASE, "static")
PORT = 8787  # 實際用的 port 在 main() 決定（被佔用就換一個）
ORIGIN = f"http://127.0.0.1:{PORT}"

import autostart  # noqa: E402
import buddy  # noqa: E402
import persona  # noqa: E402
import progress  # noqa: E402
import voice  # noqa: E402
import store  # noqa: E402
import stats  # noqa: E402
import updater  # noqa: E402

if DEMO:
    import demo
else:
    import service
    from henrik import HenrikError
    from riot import RiotError

TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".json": "application/json",
         ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
         ".gif": "image/gif", ".ico": "image/x-icon"}
PICTURES = os.path.join(os.path.expanduser("~"), "Pictures", "VAL小戰績")
_demo_matches = None


def _matches_and_me():
    global _demo_matches
    if DEMO:
        if _demo_matches is None:
            _demo_matches = demo.matches()
        return _demo_matches, demo.ME, demo.profile()
    p = store.profile()
    me = p.get("puuid")
    return (store.all_matches(me) if me else []), me, p


def _file(handler, root, name):
    full = os.path.normpath(os.path.join(root, name))
    if not full.startswith(os.path.normpath(root)) or not os.path.isfile(full):
        return handler._send(404, b"not found", "text/plain")
    with open(full, "rb") as f:
        return handler._send(200, f.read(), TYPES.get(os.path.splitext(full)[1].lower(), "application/octet-stream"))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _safe(self, fn):
        try:
            fn()
        except Exception as e:  # 錯誤顯示在畫面上
            msg = str(e) if type(e).__name__ in ("RiotError", "HenrikError", "SyncError", "HTTPStatusError",
                                                 "UpdateError", "RuntimeError") \
                else f"{type(e).__name__}: {e}"
            self._json({"error": msg})

    # ---------- GET ----------
    def do_GET(self):
        self._safe(self._get)

    def _get(self):
        url = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        path = url.path

        if path == "/" or path.startswith("/static/"):
            return _file(self, STATIC, "index.html" if path == "/" else path[len("/static/"):])

        if path.startswith("/custom/"):  # 你自己放的特務圖片
            from urllib.parse import unquote
            return _file(self, store.AGENT_IMG_DIR, unquote(path[len("/custom/"):]))

        if path == "/api/ping":
            return self._json({"ok": True})

        if path == "/api/custom-agents":
            return self._json({"files": store.custom_agent_images(), "folder": store.AGENT_IMG_DIR})

        if path == "/api/events":
            since = int(q.get("since", 0) or 0)
            return self._json([] if DEMO else service.events_since(since))

        if path == "/api/autostart":
            return self._json(autostart.diagnose())

        if path == "/api/buddy/skin":
            cfg = store.settings()
            f = progress.full()
            cid = store.current_char()
            return self._json({"skin": cfg["buddy_skin"], "char": cid, "size": cfg["buddy_size"],
                               "files": store.char_files(cid) if cid else [],
                               "moods": [{"id": m, "name": n, "need": k} for m, n, k in store.BUDDY_MOODS],
                               "bond": f["current_bond"]["index"],
                               "custom_name": persona.load(cid).get("name") if cid else "",
                               "characters": store.list_characters(),
                               "equipped": f["equipped"], "adjust": f["adjust"].get(cfg["buddy_skin"], {}),
                               "frame": f["frame"], "level": f["level"],
                               "outfits": store.char_outfits(cid) if cid else [], "outfit": f.get("outfit")})

        if path == "/api/voices":
            return self._json({"voices": voice.list_voices(), "sovits": voice.sovits_status(), "trained": voice.trained_models(),
                               "edge": [{"id": v, "name": n} for v, n in voice.VOICES]})

        if path == "/api/persona":
            cid = q.get("char") or store.current_char()
            if not cid:
                return self._json({"error": "目前不是自訂角色"})
            return self._json({"char": cid, "persona": persona.load(cid), "has_template": persona.has_template(cid)})

        if path == "/api/progress":
            if not DEMO:
                p = store.profile()
            else:
                p = demo.profile()
            return self._json(progress.full(p.get("name") or ""))

        if path.startswith("/custom-buddy/"):  # /custom-buddy/<角色ID>/<檔名>
            from urllib.parse import unquote
            return _file(self, store.CHAR_DIR, unquote(path[len("/custom-buddy/"):]))

        if path == "/api/buddy/state":
            return self._json(buddy.state())

        if path == "/api/version":
            return self._json({"version": updater.local_version()})

        if path == "/api/heat":
            ms, me, _ = _matches_and_me()
            return self._json(stats.map_heat(ms, me, q.get("map")) if me else {})

        if path == "/api/status":
            if DEMO:
                p = demo.profile()
                return self._json({"demo": True, "game_open": True, "henrik_ready": False,
                                   "profile": p, "match_count": 40,
                                   "settings": {**store.settings(), "henrik_key": None, "buddy_key": None,
                                                "henrik_key_set": False,
                                                "buddy_key_set": bool(store.settings()["buddy_key"]),
                                                "buddy_pos_set": store.settings()["buddy_x"] is not None}})
            return self._json(service.status())

        if path == "/api/stats":
            ms, me, p = _matches_and_me()
            if not me:
                return self._json({"empty": True})
            if DEMO:
                progress.credit(ms, me)
            return self._json(stats.aggregate(ms, me, p, q.get("queue", "all"), store.known_names()))

        if path.startswith("/api/match/"):
            mid = path.rsplit("/", 1)[-1]
            ms, me, _ = _matches_and_me()
            m = next((x for x in ms if x["id"] == mid), None)
            return self._json(stats.match_detail(m, me, store.known_names()) if m else {"error": "找不到這場對局"})

        if path == "/api/live":
            return self._json(demo.live() if DEMO else service.live())

        if path == "/api/favorites":
            return self._json(store.favorites())

        self._send(404, b"not found", "text/plain")

    # ---------- POST ----------
    def do_POST(self):
        # 只接受自己頁面送來的請求，避免其他網站偷改設定
        origin = self.headers.get("Origin")
        if origin and origin not in (ORIGIN, f"http://localhost:{PORT}"):
            return self._json({"error": "forbidden"}, 403)
        self._safe(self._post)

    def _post(self):
        path = urlparse(self.path).path
        body = self._body()

        if path == "/api/sync":
            if DEMO:
                time.sleep(0.8)
                return self._json({"source": "demo", "new": 0})
            return self._json(service.locked_sync(body.get("count")))

        if path == "/api/settings":
            store.save_settings(body)
            return self._json({"ok": True})

        if path == "/api/autostart":
            if body.get("enabled"):
                autostart.enable()
            else:
                autostart.disable()
            return self._json({"enabled": autostart.enabled()})

        if path == "/api/buddy/preview":
            buddy.preview(PORT)
            return self._json({"ok": True})

        if path == "/api/characters/create":
            cid = store.create_character(body.get("name"))
            store.save_settings({"buddy_skin": "custom:" + cid})
            return self._json({"id": cid})

        if path == "/api/characters/delete":
            cid = body.get("id")
            if store.current_char() == cid:
                store.save_settings({"buddy_skin": "jiujiu"})
            store.delete_character(cid)
            return self._json({"ok": True})

        if path == "/api/persona":
            cid = body.get("char") or store.current_char()
            return self._json({"persona": persona.save(cid, body.get("persona") or {})})

        if path == "/api/persona/reset":
            return self._json({"persona": persona.reset(body.get("char") or store.current_char())})

        if path == "/api/progress/equip":
            return self._json({"equipped": progress.equip(body.get("skin") or store.settings()["buddy_skin"],
                                                          body.get("item"), bool(body.get("on")))})

        if path == "/api/progress/frame":
            progress.set_frame(body.get("frame") or "default")
            return self._json({"ok": True})

        if path == "/api/progress/adjust":
            progress.adjust(body.get("skin") or "custom", body.get("item"), body.get("x", 0), body.get("y", 0), body.get("s", 1))
            return self._json({"ok": True})

        if path == "/api/progress/nickname":
            progress.set_nickname(body.get("nickname"))
            return self._json({"ok": True})

        if path == "/api/progress/outfit":
            progress.set_outfit(body.get("outfit") or "")
            return self._json({"ok": True})

        if path == "/api/names":  # 前端傳來的中文名稱（給 AI 講回憶用）
            progress.NAMES["maps"].update(body.get("maps") or {})
            progress.NAMES["agents"].update(body.get("agents") or {})
            return self._json({"ok": True})

        if path == "/api/voice/test":
            text = str(body.get("text") or "嗨～我是你的陪伴角色！今天也一起加油吧！")
            ov = body.get("voice")
            import re as _re0
            if voice.speak_lang(ov) == "ja" or _re0.search(r"[\u3040-\u30ff]", text):  # 日文模式，或打的是日文：翻成日文念（沒設定 AI 就念固定的日文測試句）
                import buddy
                import re as _re
                if _re.search(r"[\u3040-\u30ff]", text):  # 打的本來就是日文（有假名）就直接念
                    ja, text = text, ""
                else:
                    ja = buddy.to_japanese(text) or voice.JA_TEST
                r = voice.speak(ja, wait=True, override=ov, lang="ja", alt_text=text or None)
                r["spoken"] = ja
                return self._json(r)
            return self._json(voice.speak(text, wait=True, override=ov))

        if path == "/api/voices/add":  # 上傳你自己的錄音（聲音複製用）
            data = str(body.get("data") or "")
            if "," not in data or not data.startswith("data:"):
                return self._json({"error": "錄音格式不對"})
            raw = base64.b64decode(data.split(",", 1)[1])
            if len(raw) > 20 * 1024 * 1024:
                return self._json({"error": "錄音太大（上限 20MB，5～10 秒就夠了）"})
            if not str(body.get("text") or "").strip():
                return self._json({"error": "請打上錄音裡講的每一個字（逐字稿）"})
            ext = os.path.splitext(str(body.get("filename") or ""))[1] or ".wav"
            return self._json({"voice": voice.add_voice(body.get("name"), body.get("text"), body.get("lang") or "zh", raw, ext)})

        if path == "/api/voices/model":  # 接上 / 拿掉微調訓練好的模型
            try:
                return self._json({"meta": voice.set_voice_model(body.get("id"), body.get("gpt"), body.get("sovits"))})
            except ValueError as e:
                return self._json({"error": str(e)})

        if path == "/api/voices/delete":
            voice.delete_voice(body.get("id"))
            if store.settings().get("voice_clone") == body.get("id"):
                store.save_settings({"voice_clone": "", "voice_engine": "edge"})
            return self._json({"ok": True})

        if path == "/api/sovits/start":
            threading.Thread(target=voice.start_sovits, kwargs={"wait": True}, daemon=True).start()
            return self._json(voice.sovits_status())

        if path == "/api/sovits/stop":
            voice.stop_sovits()
            return self._json({"ok": True})

        if path == "/api/buddy/upload":  # 在角色房間上傳表情圖
            data = str(body.get("data") or "")
            if not data.startswith("data:image/") or "," not in data:
                return self._json({"error": "圖片格式不對"})
            raw = base64.b64decode(data.split(",", 1)[1])
            if len(raw) > 15 * 1024 * 1024:
                return self._json({"error": "圖片太大（上限 15MB）"})
            ext = os.path.splitext(str(body.get("name") or ""))[1] or "." + data[11:data.index(";")]
            cid = body.get("char") or store.current_char()
            return self._json({"file": store.save_char_image(cid, body.get("mood"), raw, ext)})

        if path == "/api/buddy/remove":
            store.remove_char_image(body.get("char") or store.current_char(), str(body.get("mood") or ""))
            return self._json({"ok": True})

        if path == "/api/buddy/setup":  # 調整位置模式
            if body.get("reset"):
                store.save_settings({"buddy_x": None, "buddy_y": None})
                return self._json({"ok": True})
            buddy.open_setup(PORT)
            return self._json({"ok": True})

        if path == "/api/buddy/test":
            return self._json(buddy.one_cycle())

        if path == "/api/desktop-shortcut":
            return self._json({"path": autostart.desktop_shortcut()})

        if path == "/api/update/check":
            repo = store.settings()["update_repo"]
            if not repo:
                return self._json({"error": "還沒設定更新來源（設定頁填 GitHub 的「帳號/repo」）。"})
            return self._json(updater.check(repo))

        if path == "/api/update/apply":
            return self._json(updater.apply(store.settings()["update_repo"]))

        if path == "/api/save-image":  # 回顧卡存成圖片，放到「圖片\VAL小戰績」
            data = str(body.get("data") or "")
            if not data.startswith("data:image/png;base64,"):
                return self._json({"error": "圖片格式不對"})
            os.makedirs(PICTURES, exist_ok=True)
            out = os.path.join(PICTURES, time.strftime("回顧_%Y%m%d_%H%M%S.png"))
            with open(out, "wb") as f:
                f.write(base64.b64decode(data.split(",", 1)[1]))
            if os.name == "nt":
                os.startfile(PICTURES)
            return self._json({"path": out})

        if path == "/api/open-folder":
            cid = store.current_char()
            folder = {"agents": store.AGENT_IMG_DIR,
                      "buddy": store.char_dir(cid) if cid else store.CHAR_DIR}.get(body.get("which"), PICTURES)
            os.makedirs(folder, exist_ok=True)
            if os.name == "nt":
                os.startfile(folder)
            return self._json({"path": folder})

        if path == "/api/clear-cache":
            store.clear_matches()
            return self._json({"ok": True})

        if path == "/api/favorites":
            url = str(body.get("url") or "").strip()
            if not url.startswith(("https://", "http://")):
                return self._json({"error": "請貼上影片網址"})
            item = {"id": uuid.uuid4().hex[:10], "url": url, "title": str(body.get("title") or "")[:80],
                    "agent": body.get("agent"), "map": body.get("map"), "added": int(time.time() * 1000)}
            return self._json(store.add_favorite(item))

        if path == "/api/favorites/delete":
            return self._json(store.remove_favorite(body.get("id")))

        self._send(404, b"not found", "text/plain")


def _make_server():
    """先用 8787；被佔用（例如已經開了一個）就讓系統挑一個空的 port。"""
    global PORT, ORIGIN
    try:
        server = ThreadingHTTPServer(("127.0.0.1", 8787), Handler)
    except OSError:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    PORT = server.server_address[1]
    ORIGIN = f"http://127.0.0.1:{PORT}"
    return server


def _run_browser(server, url):
    print(f"VAL 小戰績已啟動：{url}" + ("（展示模式）" if DEMO else ""))
    print("關閉這個視窗即可結束。")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def _run_window(server, url):
    import webview  # pywebview：用 Windows 內建的 Edge WebView2 開一個原生視窗

    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True  # YouTube 等外部連結用瀏覽器開
    except Exception:
        pass
    webview.create_window(
        "VAL 小戰績" + ("（展示模式）" if DEMO else ""), url,
        width=1360, height=880, min_size=(960, 640), background_color="#0e1220",
    )
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
    except Exception:
        pass
    webview.start()
    if not DEMO:
        autostart.mark_app_closed()
    server.shutdown()


def main():
    if "--watch" in sys.argv:
        return autostart.watch()
    if "--buddy" in sys.argv:
        return buddy.window_main()
    server = _make_server()
    url = ORIGIN + "/"
    if not DEMO:
        autostart.mark_app_running(PORT)
        # 舊版單一自訂角色 → 搬到 characters/；Claude 放進 buddy_import 的角色 → 匯入
        store.migrate_legacy_custom()
        got = store.import_character_seeds(os.path.join(os.path.dirname(os.path.abspath(__file__)), "buddy_import"))
        if got and store.settings()["buddy_skin"] == "jiujiu":
            store.save_settings({"buddy_skin": "custom:" + got[0]})
        service.start_monitor()
    if "--browser" in sys.argv or "--no-browser" in sys.argv:
        return _run_browser(server, url)
    try:
        _run_window(server, url)
    except ImportError:
        print("還沒安裝 pywebview，先用瀏覽器開。想要 App 視窗請執行：python -m pip install pywebview")
        _run_browser(server, url)
    except Exception:  # 視窗開不起來（例如缺 WebView2）→ 記錄錯誤，改用瀏覽器
        import traceback
        with open(os.path.join(store.ROOT, "error.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S\n") + traceback.format_exc() + "\n")
        _run_browser(server, url)


if __name__ == "__main__":
    main()
