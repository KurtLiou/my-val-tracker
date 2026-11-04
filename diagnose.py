"""連線診斷：逐一測試會用到的 Riot 端點，只印出結果代碼，不會印出 token 或密碼。"""
import sys

from riot import HTTPStatusError, RiotClient, RiotError


def main():
    c = RiotClient()
    print("=== VAL 小戰績 連線診斷 ===\n")
    try:
        c.connect()
    except RiotError as e:
        print("連不上 Riot Client：", e)
        return
    print(f"區域 region={c.region}  shard={c.shard}  版本={c.version}")
    print(f"自己的名稱（本機）：{'有' if c.self_name() else '沒有'}\n")

    me = c.puuid
    tests = [
        ("對局列表", lambda: c.pd(f"/match-history/v1/history/{me}?startIndex=0&endIndex=1")),
        ("牌位 MMR", lambda: c.pd(f"/mmr/v1/players/{me}")),
        ("RR 紀錄", lambda: c.pd(f"/mmr/v1/players/{me}/competitiveupdates?startIndex=0&endIndex=1&queue=competitive")),
        ("名稱查詢", lambda: c.pd("/name-service/v2/players", "PUT", [me])),
        ("賽季資料", lambda: c.shared("/content-service/v3/content")),
        ("選角狀態", lambda: c.glz(f"/pregame/v1/players/{me}")),
        ("對戰狀態", lambda: c.glz(f"/core-game/v1/players/{me}")),
    ]
    first_match = None
    for label, fn in tests:
        try:
            r = fn()
            print(f"  OK    {label}")
            if label == "對局列表":
                h = (r or {}).get("History") or []
                first_match = h[0]["MatchID"] if h else None
        except HTTPStatusError as e:
            note = "（不在選角/對戰中，正常）" if e.code == 404 and label in ("選角狀態", "對戰狀態") else ""
            print(f"  {e.code}   {label}{note}")
        except RiotError as e:
            print(f"  錯誤  {label}：{e}")
    if first_match:
        try:
            c.pd(f"/match-details/v1/matches/{first_match}")
            print("  OK    單場資料")
        except HTTPStatusError as e:
            print(f"  {e.code}   單場資料")
    print("\n把這個畫面截圖給 Claude 就可以了。")


if __name__ == "__main__":
    main()
    if "--no-pause" not in sys.argv:
        input("\n按 Enter 關閉…")
