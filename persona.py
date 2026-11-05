"""
自訂角色的「角色設定」：個性、四個階段的語氣、稱呼、口頭禪、各情境的離線台詞。
有範本的角色（static/personas/<角色ID>.json：alya、mikasa、eris）會預設帶入，可以在角色房間自己改。

俄文處理：AI 會寫「Молодец！（做得好）」這種格式。
- 對話框只顯示中文翻譯：「做得好！」
- 語音用俄文聲音念俄文、中文聲音念其他部分（翻譯不念）
"""
import json
import os
import random
import re

import store

BASE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(BASE, "static", "personas")
BLANK = {"enabled": False, "name": "", "prompt": "", "tones": ["", "", "", ""], "address": ["{n}", "{n}", "{n}", "{n}"],
         "catchphrases": [], "lines": {}, "lines_min_stage": {}}
W = r"[А-Яа-яЁё]+"
PUNCT = r"!！?？.。…,，"
# 一段俄文：俄文單字（中間可以有空白或標點）＋結尾標點，後面可能接（翻譯）
RU_SEG = re.compile(rf"({W}(?:[\s{PUNCT}—\-]*{W})*)([{PUNCT}]*)\s*(?:[（(]([^）)]*)[）)])?")


def has_template(cid):
    return os.path.exists(os.path.join(TEMPLATES, f"{cid}.json"))


def template(cid):
    try:
        with open(os.path.join(TEMPLATES, f"{cid}.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return dict(BLANK)


def _path(cid):
    return os.path.join(store.char_dir(cid), "persona.json")


def load(cid):
    try:
        with open(_path(cid), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    base = template(cid) if (not d.get("prompt") and has_template(cid)) else {}
    out = {**BLANK, **base, **{k: v for k, v in d.items() if v not in (None, "")}}
    if not d.get("prompt") and has_template(cid):  # 還沒自己改過就用範本（保留自己取的名字）
        out = {**BLANK, **template(cid), **({"name": d["name"]} if d.get("name") else {})}
    return out


def save(cid, d):
    cur = load(cid)
    for k in ("enabled", "name", "prompt", "tones", "address", "catchphrases", "lines"):
        if k in d:
            cur[k] = d[k]
    cur["tones"] = (list(cur["tones"]) + [""] * 4)[:4]
    cur["address"] = (list(cur["address"]) + ["{n}"] * 4)[:4]
    with open(_path(cid), "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=1)
    return cur


def reset(cid):
    t = template(cid)
    with open(_path(cid), "w", encoding="utf-8") as f:
        json.dump(t if has_template(cid) else {**BLANK, "name": load(cid).get("name", "")}, f, ensure_ascii=False, indent=1)
    return load(cid)


def active():
    """目前是自訂角色、而且有開啟角色設定時才用。"""
    cid = store.current_char()
    if not cid:
        return None
    p = load(cid)
    return p if p.get("enabled") and p.get("prompt") else None


# ---------- 俄文：顯示與語音 ----------
def display(line):
    """對話框用：俄文換成中文翻譯（沒附翻譯的俄文就保留）。"""
    def rep(m):
        ru, end, tr = m.group(1), m.group(2), m.group(3)
        if not tr:
            return ru + end
        tr = tr.strip()
        return tr + (end if end and tr[-1:] not in PUNCT else "")
    out = RU_SEG.sub(rep, line or "")
    return re.sub(r"\s{2,}", " ", out).strip()


def speech(line):
    """語音用：[(語言, 文字)]。俄文用俄文聲音念，翻譯不念。"""
    segs, pos = [], 0
    for m in RU_SEG.finditer(line or ""):
        before = line[pos:m.start()].strip()
        if before:
            segs.append(("zh", before))
        segs.append(("ru", (m.group(1) + m.group(2)).strip()))
        pos = m.end()
    rest = (line or "")[pos:].strip()
    if rest:
        segs.append(("zh", rest))
    # 把只剩標點的中文段落拿掉
    return [(lang, t) for lang, t in segs if re.search(r"[\w一-鿿]", t)]


# ---------- 給 AI ----------
def system_prompt(p, stage, nickname):
    call = (p["address"][stage] if stage < len(p["address"]) else "{n}").format(n=nickname or "你")
    tone = p["tones"][stage] if stage < len(p["tones"]) else ""
    cps = "、".join(f"「{c}」" for c in p.get("catchphrases") or [])
    return f"""{p['prompt']}

現在你們的關係階段：{tone}
你要這樣稱呼玩家：{call}
口頭禪（偶爾自然地用，不要每句都用）：{cps}

你會看到玩家此刻的遊戲畫面截圖，只用來感受氣氛：剛擊殺或贏回合就稱讚、剛陣亡或落後就安慰打氣、看不出發生什麼就閒聊。
嚴格規則：只說一句繁體中文（俄文另計），中文 15 個字以內，最多 1 個 emoji；絕對不要給戰術建議、不要提到任何敵方資訊；不要重複最近說過的話。
只回傳 JSON：{{"line": "你要說的話", "mood": "從可用表情裡選一個"}}"""


# ---------- 離線台詞 ----------
def line_for(p, mood, stage, nickname, avoid=()):
    lines = (p.get("lines") or {}).get(mood) or (p.get("lines") or {}).get("happy") or []
    min_stage = p.get("lines_min_stage") or {}
    pool = [x for x in lines if stage >= min_stage.get(x, 0) and x not in avoid] or lines
    if not pool:
        return None
    call = (p["address"][stage] if stage < len(p["address"]) else "{n}").format(n=nickname or "你")
    return random.choice(pool).replace("{n}", call)
