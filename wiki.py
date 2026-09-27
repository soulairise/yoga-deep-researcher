# -*- coding: utf-8 -*-
"""위키백과 API 얇은 래퍼. 429 를 만나면 기다렸다 다시 친다."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

LANG = "en"          # set_lang() 으로 바꾼다


def api():
    return f"https://{LANG}.wikipedia.org/w/api.php"


def set_lang(code):
    """한국어 위키가 얇은 주제가 있다. 그때 영어로 갈아탄다."""
    global LANG
    LANG = code
UA = "soulmat-deepresearch-study/1.0 (https://github.com/soulairise; mykim97@gmail.com)"
PAUSE = 1.1          # 연달아 때리면 429 가 온다. 급하게 굴 이유가 없다.
_last = [0.0]


def call(**p):
    p.update(format="json", formatversion="2")
    url = api() + "?" + urllib.parse.urlencode(p)
    for attempt in range(6):
        wait = PAUSE - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return json.load(urllib.request.urlopen(req, timeout=30))
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError(f"위키 호출이 계속 막힙니다: {p.get('titles') or p.get('srsearch')}")


def resolve(title):
    """제목이 실제로 있는지 확인한다. 넘겨주기는 최종 제목으로 바꾼다
    — 안 그러면 같은 문서를 두 번 담는다.

    **없으면 None 이다. 검색 결과로 대신 채우지 않는다.**
    처음엔 검색으로 가장 비슷한 걸 넣게 짰는데, '크리슈나마차리아'가 '바마나'로,
    '하타요가 프라디피카'가 '달인좌'로 들어왔다. 코퍼스에 무관한 문서를 섞는 것은
    없는 문서를 빼는 것보다 나쁘다. 비슷한 후보는 참고로만 돌려준다."""
    d = call(action="query", titles=title, redirects=1, prop="info")
    pg = d["query"]["pages"][0]
    if "missing" not in pg:
        return pg["title"], ("그대로" if pg["title"] == title else f"넘겨주기←{title}")
    hits = call(action="query", list="search", srsearch=title,
                srlimit=3)["query"]["search"]
    near = ", ".join(h["title"] for h in hits) or "-"
    return None, f"없음 (비슷한 것: {near})"


def page(title):
    """본문(플레인) · 분류 · 링크를 한 번에 가져온다."""
    d = call(action="query", titles=title, redirects=1,
             prop="extracts|categories|links", explaintext=1, exsectionformat="plain",
             cllimit=200, pllimit=500, plnamespace=0, clshow="!hidden")
    pg = d["query"]["pages"][0]
    if "missing" in pg:
        return None
    return {"title": pg["title"], "text": pg.get("extract", ""),
            "cats": [c["title"].replace("Category:", "") for c in pg.get("categories", [])],
            "links": [l["title"] for l in pg.get("links", [])]}
