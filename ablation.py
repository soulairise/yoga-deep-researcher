# -*- coding: utf-8 -*-
"""절제 실험 — 스위치를 하나씩 끄고 같은 잣대로 잰다.  `python ablation.py`

규칙 셋을 지킨다.

  **한 번에 하나만 끈다.** 둘을 같이 끄면 어느 쪽 효과인지 알 수 없다.
  **잣대는 안 바뀐다.** metrics.py 는 정답표를 안 보므로 설정을 어떻게 바꿔도 그대로다.
  **한 번 재고 방향을 말하지 않는다.** 질문 넷 × 2회를 돌리고, 차이가 회차 편차보다
  클 때만 '구분된다'고 쓴다. 판정은 공통 도구 evalkit 의 distinguishable() 이 한다.

스위치를 껐다고 로그만 찍고 코드 경로는 그대로인 가짜 절제를 막으려고,
끈 결과가 실제로 달라졌는지도 같이 센다(배정을 끄면 시작자료가 0건이어야 한다).
"""
import json
import os
import sys
import time

import baseline
import graph
import metrics
from common import OUT, REPORTS, config, questions
from evalkit.repeats import Measurement, distinguishable

ARMS = {
    "기본":        {},
    "배정 끔":     {"스위치": {"배정": False}},
    "역할 끔":     {"스위치": {"역할": False}},
    "재위임 끔":   {"스위치": {"재위임": False}},
    "덮어쓰기":    {"두번째원고": "덮어쓰기"},
    "혼자":        {"구조": "혼자"},
}
QS = ["Q1", "Q4", "Q8", "Q10"]      # 단일 · 분산 · 추적 · 추적(배정만이 경로)
REPS = 2
지표 = ["근거율", "최다문서편중", "중복률", "읽고안쓴문서", "허위인용",
        "인용수", "읽은건수", "보고서길이", "LLM호출", "격리율"]
# 방향: 높을수록 좋은 것 / 낮을수록 좋은 것. 계기는 방향이 정해져야 계기다.
좋음 = {"근거율": "↑", "최다문서편중": "↓", "중복률": "↓", "읽고안쓴문서": "↓",
        "허위인용": "0", "인용수": "↑", "읽은건수": "·", "보고서길이": "·",
        "LLM호출": "↓", "격리율": "↓"}


def one(arm, q):
    cfg = config()
    spec = ARMS[arm]
    if spec.get("구조") == "혼자":
        return baseline.run(q["q"], cfg)
    for k, v in spec.items():
        if k == "스위치":
            cfg["스위치"].update(v)
        else:
            cfg[k] = v
    return graph.run(q["q"], cfg)


def main():
    qs = {x["id"]: x for x in questions()}
    log = open(os.path.join(OUT, "runs.jsonl"), "a", encoding="utf-8")
    표 = {}          # arm -> 지표 -> [회차별 평균]
    per_q = {}       # (arm, qid) -> 지표 dict
    t0 = time.time()

    for arm in ARMS:
        표[arm] = {k: [] for k in 지표}
        for rep in range(REPS):
            회차 = {k: [] for k in 지표}
            for qid in QS:
                q = qs[qid]
                out = one(arm, q)
                m = out["metrics"]
                for k in 지표:
                    회차[k].append(float(m.get(k, 0)))
                per_q.setdefault((arm, qid), []).append(m)
                name = f"{arm.replace(' ', '')}_{qid}_r{rep+1}.md"
                open(os.path.join(REPORTS, name), "w", encoding="utf-8").write(
                    out["report"])
                log.write(json.dumps({"arm": arm, "qid": qid, "rep": rep + 1,
                                      "유형": q["유형"], "질문": q["q"],
                                      "설정": out["설정"], "metrics": m,
                                      "secs": out["secs"], "보고서파일": name,
                                      "절상세": [{kk: vv for kk, vv in x.items()
                                                  if kk != "원고"}
                                                 for x in out["절상세"]]},
                                     ensure_ascii=False) + "\n")
                log.flush()
                print(f"  {arm:<8} {qid:<4} r{rep+1}  "
                      f"근거 {m['근거율']:.0%} 편중 {m['최다문서편중']:.0%} "
                      f"중복 {m['중복률']:.0%} 허위 {m['허위인용']} "
                      f"({out['secs']}초)", flush=True)
            for k in 지표:
                표[arm][k].append(sum(회차[k]) / len(회차[k]))
    log.close()

    # ── 표 ──
    print(f"\n\n══ 질문 {len(QS)}개 × {REPS}회 평균 "
          f"({(time.time()-t0)/60:.1f}분) ══\n")
    head = ["설정"] + [f"{k}{좋음[k]}" for k in 지표]
    print("| " + " | ".join(head) + " |")
    print("|" + "|".join(["---"] * len(head)) + "|")
    for arm in ARMS:
        row = [arm]
        for k in 지표:
            v = sum(표[arm][k]) / len(표[arm][k])
            row.append(f"{v:.1%}" if k in ("근거율", "최다문서편중", "중복률",
                                           "격리율") else f"{v:.1f}")
        print("| " + " | ".join(row) + " |")

    # ── 구분되는가 ──
    print("\n── 기본과 구분되는가 (차이 > 회차 편차) ──")
    base = {k: Measurement(f"기본·{k}", 표["기본"][k]) for k in 지표}
    for arm in ARMS:
        if arm == "기본":
            continue
        말 = []
        for k in 지표:
            a = Measurement(f"{arm}·{k}", 표[arm][k])
            if distinguishable(base[k], a):
                d = a.mean - base[k].mean
                말.append(f"{k} {'+' if d > 0 else ''}"
                          + (f"{d:.1%}p" if k in ("근거율", "최다문서편중",
                                                  "중복률", "격리율")
                             else f"{d:.1f}"))
        print(f"  {arm:<8} " + (" · ".join(말) if 말
                                else "구분되는 지표 없음 "
                                     "(이 표본으로는 효과를 보지 못했다)"))

    # ── 질문 유형별 (기본) ──
    print("\n── 기본 설정, 질문 유형별 ──")
    for qid in QS:
        ms = per_q[("기본", qid)]
        avg = {k: sum(m[k] for m in ms) / len(ms) for k in 지표}
        print(f"  {qid} {qs[qid]['유형']:<3} " + metrics.line("", avg).strip())

    json.dump({"arms": 표, "questions": QS, "reps": REPS,
               "per_question": {f"{a}|{q}": v for (a, q), v in per_q.items()}},
              open(os.path.join(OUT, "ablation.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n저장: {OUT}/ablation.json · runs.jsonl · reports/")


if __name__ == "__main__":
    main()
