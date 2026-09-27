# -*- coding: utf-8 -*-
"""혼자 하는 오케스트레이터 — 대조군.

공정하게 맞춘다. **같은 코퍼스 · 같은 모델 · 같은 도구(read_one·후보목록) ·
같은 읽기 예산**(절수 × 절예산 = 12건). 다른 것은 하나뿐이다 — 나누지 않는다.
하나가 순서대로 고르고, 읽고, 혼자 다 쓴다.

대조군을 약하게 만들지 않기 위해 둘을 지켰다.

  ① 예산을 끝까지 쓴다. 모델이 후보에 없는 제목을 답해도 루프를 끊지 않고
     가장 가까운 것(없으면 맨 앞)을 읽는다. 팀 쪽 조사관과 **똑같은 규칙**이다.
     중간에 멈추면 이긴 것이 아니라 상대를 묶어 둔 것이다.
  ② 읽기 한도도 같다. 팀 조사관이 6,000자씩 보면 혼자 하는 쪽도 6,000자씩 본다.

실제로 예산을 다 썼는지는 결과의 '읽은건수'로 확인한다. 12가 아니면 실험이 깨진 것이다.
"""
import difflib
import json
import time

import metrics
from common import ask, config, corpus
from graph import DOCS, LINKS, TITLES, read_one

고르기 = """너는 리서치 보고서를 혼자 쓰는 조사관이다.

질문: {q}
이미 읽은 것: {읽음}
남은 예산: {남음}건

아래 후보 중 이 보고서를 쓰는 데 가장 필요한 자료 **하나**의 제목만 그대로 출력하라.
다른 말은 쓰지 마라.

{후보}"""

쓰기 = """너는 리서치 보고서를 혼자 쓰는 조사관이다.

질문: {q}

아래는 네가 읽은 자료 전부다. **여기 있는 것만 근거로 쓴다.**

{자료}

네가 읽은 자료의 제목은 정확히 이것뿐이다: {제목들}

규칙:
- 한국어로 2,400~3,600자의 보고서를 쓴다. 자료는 영어지만 답은 한국어로 쓴다.
- 내용 단위로 절을 나누고 각 절에 `## 제목` 을 붙인다.
- **사실을 말하는 문장은 하나도 빠짐없이** 마침표 앞에 «자료 제목» 을 붙인다.
  예) 하타 요가는 몸을 통해 에너지를 다룬다 «Hatha yoga».
- 제목은 위에 적힌 영어 표기를 **글자 그대로** 옮긴다.
- 위 목록에 없는 자료는 절대 인용하지 마라. «» 안에는 위 목록의 제목만 넣는다.
- 머리말 한 문단으로 시작하고 맺음말 한 문단으로 끝낸다."""


def run(question, cfg=None):
    cfg = cfg or config()
    예산 = cfg["절수"] * cfg["절예산"]
    읽음, 본문, 글자, 호출 = [], [], 0, 0
    t0 = time.time()

    for i in range(예산):
        cand = [t for t in TITLES if t not in 읽음]
        for t in 읽음:                       # 팀 쪽과 같은 링크 타기
            cand = [l for l in LINKS.get(t, []) if l not in 읽음] + \
                   [c for c in cand if c not in LINKS.get(t, [])]
        보여줄 = cand[:40]
        pick, used = ask(고르기.format(q=question, 읽음=", ".join(읽음) or "없음",
                                       남음=예산 - i,
                                       후보="\n".join(f"- {t}" for t in 보여줄)))
        글자 += used
        호출 += 1
        pick = pick.strip().strip("-•\"'«» ")
        if pick not in 보여줄:
            near = difflib.get_close_matches(pick, 보여줄, n=1, cutoff=0.6)
            pick = near[0] if near else 보여줄[0]
        읽음.append(pick)
        본문.append(f"### {pick}\n{read_one(pick, cfg['읽기한도'])}")

    report, used = ask(쓰기.format(q=question, 자료="\n\n".join(본문),
                                   제목들=" · ".join(f"«{t}»" for t in 읽음)))
    글자 += used
    호출 += 1

    m = metrics.score(report, 읽음)
    m.update({"격리율": 1.0, "코디네이터가본글자": 글자, "조사관이본글자": 0,
              "LLM호출": 호출, "절수": report.count("\n## "), "재위임절": 0,
              "배정고침": 0})
    return {"report": report, "metrics": m, "secs": round(time.time() - t0, 1),
            "설정": {"구조": "혼자"}, "읽은자료": 읽음,
            "절상세": [{"idx": 0, "제목": "(나누지 않음)", "역할": None,
                        "읽은자료": 읽음, "부족": False, "round": 0,
                        "인용": metrics.cites(report), "원고": report}]}


if __name__ == "__main__":
    import sys
    from common import questions
    qs = {q["id"]: q for q in questions()}
    qid = sys.argv[1] if len(sys.argv) > 1 else "Q8"
    q = qs[qid]
    cfg = config()
    print(f"[{qid}·{q['유형']}] {q['q']}\n")
    out = run(q["q"])
    m = out["metrics"]
    예산 = cfg["절수"] * cfg["절예산"]
    print(metrics.line("혼자", m))
    print(f"  예산 {예산}건 중 {m['읽은건수']}건 읽음 — "
          + ("다 썼다. 공정하다." if m["읽은건수"] == 예산
             else "★ 다 안 썼다. 이 비교는 무효다."))
    print(f"  호출 {m['LLM호출']} · {out['secs']}초")
    print("\n" + "─" * 70 + "\n" + out["report"][:1200] + "\n…")
