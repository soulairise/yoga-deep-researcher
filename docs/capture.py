# -*- coding: utf-8 -*-
"""데모 화면을 파일로 찍는다.  `python docs/capture.py`

헤드리스 크롬의 `--screenshot` 은 이 앱에 쓸 수 없다. Streamlit 은 WebSocket 으로
화면을 그리는데 `--virtual-time-budget` 은 가상 시간만 돌릴 뿐 실제 응답을 기다리지
않는다. 실제로 로딩 뼈대만 찍혔다. DOM 을 떠서 따로 렌더해 봤지만 Streamlit 이
스타일을 JS 로 주입해서 스타일 없는 화면이 나왔다.

그래서 크롬을 디버깅 포트로 띄우고 CDP 로 **답변 글자가 나타난 것을 확인한 뒤** 찍는다.
"""
import json
import os
import subprocess
import time
import urllib.parse
import urllib.request

import websocket

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9222
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo.png")
Q = "Q8"
URL = f"http://localhost:8501/?q={Q}"
WAIT_FOR = "최종 보고서"        # 이 글자가 보이면 보고서까지 그려진 것이다


def cdp(ws, mid, method, **params):
    ws.send(json.dumps({"id": mid, "method": method, "params": params}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == mid:
            return msg.get("result", {})


def main():
    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
         "--window-size=1680,2560",
         "--force-device-scale-factor=2", "--user-data-dir=/tmp/chrome-shot", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(40):                       # 디버깅 포트가 열릴 때까지
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise SystemExit("크롬 디버깅 포트가 열리지 않았습니다")

        page = next(t for t in tabs if t["type"] == "page")
        ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=90)
        i = 0
        i += 1; cdp(ws, i, "Page.enable")
        i += 1; cdp(ws, i, "Page.navigate", url=URL)

        for sec in range(90):                     # 답변이 그려질 때까지 실제로 기다린다
            time.sleep(1)
            i += 1
            r = cdp(ws, i, "Runtime.evaluate",
                    expression="document.body.innerText", returnByValue=True)
            if WAIT_FOR in (r.get("result", {}).get("value") or ""):
                print(f"답변 확인 ({sec + 1}초)")
                break
        else:
            raise SystemExit(f"{WAIT_FOR!r} 이 나타나지 않았습니다. 앱과 API 키를 확인하세요.")

        time.sleep(1.5)                           # 애니메이션이 끝나도록
        i += 1
        h = cdp(ws, i, "Runtime.evaluate",
                expression="document.body.scrollHeight", returnByValue=True
                )["result"]["value"]
        # captureBeyondViewport 로 찍었더니 **고정 위치인 사이드바가 왼쪽으로
        # 밀려 잘렸다.** 스크롤 밖까지 찍는 대신 창 자체를 높게 띄우고
        # 뷰포트 그대로 찍는다. (scrollHeight 는 그래도 찍어 둔다 — 잘린 분량을 알려고)
        i += 1
        shot = cdp(ws, i, "Page.captureScreenshot", format="png")
        if "data" not in shot:
            raise SystemExit(f"캡처가 비었습니다: {shot}")
        import base64
        open(OUT, "wb").write(base64.b64decode(shot["data"]))
        print(f"저장: {OUT} ({os.path.getsize(OUT) // 1024} KB) · 페이지 전체 높이 {h}px 중 2,560px 를 찍었다")
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
