# -*- coding: utf-8 -*-
"""딥리서처 — 코디네이터 하나가 목차를 짜고 조사관 넷을 동시에 내보낸다.

  기획 → 배치 → (조사관 × N 동시) → 점검 → [재위임] → 종합 → 평가

이 파일에서 지키는 것 둘.

  **컨텍스트 격리** — 원문은 read_one() 안에서만 펼쳐지고 조사관의 창에만 들어간다.
  위로 올라가는 것은 원고와 '무엇을 읽었는지' 목록뿐이다. 코디네이터는 원문을 못 본다.
  주장으로 끝내지 않으려고 누가 몇 글자를 봤는지 세서 격리율로 보인다.

  **스위치는 한군데** — 배정·역할·재위임을 config.json 의 값 하나씩으로 끈다.
  로그만 찍고 코드 경로는 그대로인 가짜 스위치를 만들지 않으려고, 끄면 실제로
  다른 후보 목록·다른 지시문·다른 엣지를 타게 짰다.
"""
import difflib
import json
import operator
import re
import time
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

import metrics
from common import WINDOW, ask, config, corpus

CORPUS = corpus()
DOCS, LINKS = CORPUS["docs"], CORPUS["links"]
TITLES = sorted(DOCS)

범용지시 = "너는 조사관이다. 맡은 절에 필요한 내용을 자료에서 찾아 쓴다."


# ── 도구 ──────────────────────────────────────────────────────────────
def read_one(title, limit):
    """자료 한 건을 편다. **이 함수가 원문이 나가는 유일한 문이다.**"""
    d = DOCS.get(title)
    return "" if d is None else d["text"][:limit]


def cards(n):
    """제목 + 앞 n자. 코디네이터가 보는 것은 이것뿐이다 — 전문의 1.9% 남짓."""
    return "\n".join(f"- {t} :: {DOCS[t]['text'][:n].strip()}" for t in TITLES)


def 후보(읽음, 배정, 남의구역, 배정켬):
    """다음에 읽을 만한 것. 배정을 켜면 '내 시작자료 + 읽은 것의 링크 − 남의 구역',
    끄면 코퍼스 전체다. 이 한 함수가 배정·구역 스위치의 실제 경로다."""
    if not 배정켬:
        return [t for t in TITLES if t not in 읽음]
    c = [t for t in 배정 if t not in 읽음]
    for t in 읽음:
        c += [l for l in LINKS.get(t, []) if l not in 읽음 and l not in c]
    c = [t for t in c if t not in 남의구역]
    return c or [t for t in TITLES if t not in 읽음 and t not in 남의구역]


# ── 상태 ──────────────────────────────────────────────────────────────
class S(TypedDict, total=False):
    question: str
    cfg: dict
    outline: list
    zones: dict
    sections: Annotated[list, operator.add]
    rounds: int
    gaps: list
    report: str
    metrics: dict
    coord_chars: Annotated[int, operator.add]
    agent_chars: Annotated[int, operator.add]
    calls: Annotated[int, operator.add]
    plan_fix: int
    # 아래 다섯은 Send 가 조사관 한 명에게만 들려 보내는 짐이다.
    # 조사관은 이 값들을 돌려주지 않으므로 리듀서가 필요 없다.
    #
    # 2026-09-28 정정 — 처음엔 "스키마에 없으면 LangGraph 가 조용히 버린다"고 적었는데
    # **틀렸다.** langgraph 1.2.11 은 스키마에 없어도 Send 페이로드를 그대로 전달한다
    # (이 다섯 줄을 지우고 돌려도 파이프라인은 멀쩡히 돈다). 그때 KeyError 를 낸 것은
    # 아래 `다시()` 가 Send 가 아니라 노드 이름을 돌려준 쪽 하나뿐이었다.
    # 이 줄들은 이제 "무엇이 실려 오는가"를 적어 두는 문서 역할만 한다.
    idx: int
    절: dict
    남의구역: list
    round: int
    이미읽음: list


# ── ① 기획 ────────────────────────────────────────────────────────────
기획프롬프트 = """아래는 요가·명상 자료 {n}건의 제목과 첫머리다.

{cards}

질문: {q}

이 질문에 답하는 보고서의 목차를 {k}개 절로 짜라.

절을 **내용 단위**로 갈라라. '개요·역사·분석' 같은 형식 단위로 나누면 네 명이
같은 자료를 읽게 된다. 서로 다른 자료를 읽게 되는 축으로 갈라야 한다.

절마다 역할을 아래에서 하나 고르고, 그 절을 시작할 자료를 **위 목록에 실제로 있는
제목 그대로** 2건 지정하라. 절끼리 시작자료가 겹치지 않게 하라.

역할: {roles}

JSON 배열만 출력하라. 다른 말은 쓰지 마라.
[{{"제목": "...", "역할": "...", "시작자료": ["...", "..."], "왜": "한 줄"}}]"""


def _json(s):
    m = re.search(r"\[.*\]", s, re.S)
    return json.loads(m.group(0)) if m else []


def n_기획(s):
    cfg = s["cfg"]
    k, roles = cfg["절수"], [r["이름"] for r in cfg["역할명단"]]
    p = 기획프롬프트.format(n=len(TITLES), cards=cards(cfg["카드길이"]),
                            q=s["question"], k=k, roles=" · ".join(roles))
    out, used = ask(p)
    try:
        plan = _json(out)[:k]
    except Exception:
        plan = []

    # ── 코드가 검사한다. 모델은 그럴듯한 제목을 지어낸다. ──
    # 실제로 「Krishnamacharya's Yoga Makaranda」처럼 있을 법한데 없는 제목이 나온다.
    # 가장 가까운 실제 제목으로 바꾸고, 몇 건을 고쳤는지 센다. 조용히 넘기면
    # '배정했다'와 '배정이 닿았다'를 구별할 수 없다.
    고침, 쓴자료 = 0, set()
    for sec in plan:
        real = []
        for t in (sec.get("시작자료") or [])[:2]:
            if t in DOCS:
                real.append(t)
            else:
                near = difflib.get_close_matches(str(t), TITLES, n=1, cutoff=0.5)
                고침 += 1
                if near:
                    real.append(near[0])
        sec["시작자료"] = [t for t in real if t not in 쓴자료] or real
        쓴자료 |= set(sec["시작자료"])
        if sec.get("역할") not in roles:
            sec["역할"] = roles[len(쓴자료) % len(roles)]

    while len(plan) < k:                      # 모델이 적게 내놓으면 채운다
        i = len(plan)
        plan.append({"제목": f"보충 {i+1}", "역할": roles[i % len(roles)],
                     "시작자료": [TITLES[i]], "왜": "기획이 모자라 자동으로 채운 절"})

    zones = {str(i): sorted({t for j, o in enumerate(plan) if j != i
                             for t in o["시작자료"]})
             for i in range(len(plan))}
    return {"outline": plan, "zones": zones, "plan_fix": 고침,
            "coord_chars": used, "calls": 1, "rounds": 0}


# ── ② 배치 ────────────────────────────────────────────────────────────
def n_배치(s):
    """구역표를 확정하는 자리. 배정을 끄면 여기서 시작자료와 구역이 통째로 비워진다."""
    if s["cfg"]["스위치"]["배정"]:
        return {"zones": s["zones"]}
    return {"zones": {k: [] for k in s["zones"]},
            "outline": [{**o, "시작자료": []} for o in s["outline"]]}


def 파견(s):
    """팬아웃. 조사관마다 자기 절·역할·시작자료·남의 구역·예산만 들고 간다."""
    cfg = s["cfg"]
    todo = s.get("gaps") if s.get("rounds", 0) > 0 else list(range(len(s["outline"])))
    return [Send("조사관", {"question": s["question"], "cfg": cfg, "idx": i,
                            "절": s["outline"][i], "남의구역": s["zones"][str(i)],
                            "round": s.get("rounds", 0),
                            "이미읽음": [t for sec in s.get("sections", [])
                                        if sec["idx"] == i for t in sec["읽은자료"]]})
            for i in todo]


# ── ③ 조사관 ──────────────────────────────────────────────────────────
고르기 = """{지시}

보고서 절: 「{제목}」
질문: {q}
이미 읽은 것: {읽음}

아래 후보 중 이 절을 쓰는 데 가장 필요한 자료 **하나**의 제목만 그대로 출력하라.
다른 말은 쓰지 마라.

{후보}"""

쓰기 = """{지시}

너는 보고서의 한 절만 쓴다. 전체 보고서를 쓰지 마라.

보고서가 답해야 할 질문: {q}
네가 맡은 절: 「{제목}」

아래는 네가 읽은 자료다. **여기 있는 것만 근거로 쓴다.**

{자료}

네가 읽은 자료의 제목은 정확히 이것뿐이다: {제목들}

규칙:
- 한국어로 600~900자. 자료는 영어지만 답은 한국어로 쓴다.
- **사실을 말하는 문장은 하나도 빠짐없이** 마침표 앞에 «자료 제목» 을 붙인다.
  예) 하타 요가는 몸을 통해 에너지를 다룬다 «Hatha yoga».
- 제목은 위에 적힌 영어 표기를 **글자 그대로** 옮긴다. 줄이거나 번역하지 마라.
- 인용이 붙지 않은 문장은 앞뒤를 잇는 문장 하나 정도여야 한다.
- 위 목록에 없는 자료는 절대 인용하지 마라. «» 안에는 위 목록의 제목만 넣는다.
  본문에 나오는 책 이름·사람 이름·다른 문헌 이름을 «» 로 감싸면 안 된다.
- 절 제목은 쓰지 말고 본문만 쓴다.

본문을 쓴 뒤 마지막 줄에 한 줄만 덧붙여라:
부족: 예 또는 아니오 / 이유 한 마디
판단 기준 — 읽은 자료로 이 절의 **핵심을 쓸 수 없었으면** '예'.
자료가 더 있으면 좋겠다는 정도면 '아니오'."""


def n_조사관(s):
    cfg, 절 = s["cfg"], s["절"]
    지시 = (next((r["지시"] for r in cfg["역할명단"] if r["이름"] == 절.get("역할")),
                범용지시) if cfg["스위치"]["역할"] else 범용지시)
    배정켬 = cfg["스위치"]["배정"]
    읽음 = list(s.get("이미읽음") or [])
    # 재위임 바퀴에서 **이미 읽은 것도 다시 펴 놓는다.** 새로 읽은 것만 보고 쓰게
    # 두었더니 두 번째 원고가 첫 원고의 내용을 통째로 잃었다. read_one 은 캐시에서
    # 꺼내는 것이라 다시 읽는 데 호출도 돈도 들지 않는다.
    본문 = [f"### {t}\n{read_one(t, cfg['읽기한도'])}" for t in 읽음]
    쓴글자, 호출 = 0, 0

    for _ in range(cfg["절예산"]):
        cand = 후보(읽음, 절.get("시작자료") or [], s["남의구역"], 배정켬)
        if not cand:
            break
        보여줄 = cand[:40]
        pick, used = ask(고르기.format(지시=지시, 제목=절["제목"], q=s["question"],
                                       읽음=", ".join(읽음) or "없음",
                                       후보="\n".join(f"- {t}" for t in 보여줄)))
        쓴글자 += used
        호출 += 1
        pick = pick.strip().strip("-•\"'«» ")
        # 후보에 없는 제목을 답하면 **멈추지 않고** 맨 앞 후보를 읽는다.
        # 여기서 루프를 끊으면 예산을 다 못 쓰고, 대조군에서 같은 실수를 하면
        # 상대 손발을 묶어 놓고 이기는 실험이 된다.
        if pick not in 보여줄:
            pick = difflib.get_close_matches(pick, 보여줄, n=1, cutoff=0.6)
            pick = pick[0] if pick else 보여줄[0]
        읽음.append(pick)
        본문.append(f"### {pick}\n{read_one(pick, cfg['읽기한도'])}")

    원고, used = ask(쓰기.format(지시=지시, q=s["question"], 제목=절["제목"],
                                 제목들=" · ".join(f"«{t}»" for t in 읽음) or "(없음)",
                                 자료="\n\n".join(본문) or "(없음)"))
    쓴글자 += used
    호출 += 1

    부족 = bool(re.search(r"부족\s*[:：]\s*예", 원고))
    원고 = re.sub(r"\n?부족\s*[:：].*$", "", 원고, flags=re.S).strip()
    return {"sections": [{"idx": s["idx"], "제목": 절["제목"], "역할": 절.get("역할"),
                          "원고": 원고, "읽은자료": 읽음, "부족": 부족,
                          "round": s["round"],
                          "인용": metrics.cites(원고)}],
            "agent_chars": 쓴글자, "calls": 호출}


# ── ④ 점검 ────────────────────────────────────────────────────────────
def 밀도(sec):
    """1,000자당 인용 수. 두 원고 중 무엇을 남길지 이것으로 가른다."""
    return len(sec["인용"]) / max(len(sec["원고"]), 1) * 1000


def 채택(sections, 규칙):
    """절마다 원고 하나씩 고른다. 재위임이 돌면 한 절에 원고가 둘이 된다."""
    best = {}
    for sec in sections:
        cur = best.get(sec["idx"])
        if cur is None:
            best[sec["idx"]] = sec
        elif 규칙 == "덮어쓰기":
            best[sec["idx"]] = sec if sec["round"] >= cur["round"] else cur
        else:                                  # 인용밀도
            best[sec["idx"]] = sec if 밀도(sec) > 밀도(cur) else cur
    return [best[i] for i in sorted(best)]


def n_점검(s):
    cfg = s["cfg"]
    골라둔 = 채택(s["sections"], cfg["두번째원고"])
    gaps = [sec["idx"] for sec in 골라둔 if sec["부족"]] if cfg["스위치"]["재위임"] else []
    if s.get("rounds", 0) + 1 >= cfg["바퀴상한"]:
        gaps = []
    return {"gaps": gaps, "rounds": s.get("rounds", 0) + 1}


def 다시(s):
    """재위임도 **팬아웃으로** 돌아가야 한다. 노드 이름만 돌려주면 조사관이
    전체 상태를 받게 되고, 자기 절이 무엇인지 모른 채 깨진다 (여기서 한 번 깨졌다)."""
    return 파견(s) if s.get("gaps") else "종합"


# ── ⑤ 종합 ────────────────────────────────────────────────────────────
머리맺음 = """아래는 보고서 각 절의 제목과 첫머리다.

질문: {q}

{윤곽}

이 보고서의 머리말 한 문단(3~4문장)과 맺음말 한 문단(3~4문장)을 한국어로 써라.
절의 내용을 다시 쓰지 마라. 새로운 사실을 지어내지 마라. 인용 표기는 쓰지 마라.

형식:
머리말:
(한 문단)
맺음말:
(한 문단)"""


def n_종합(s):
    """**절 본문에 손대지 않는다.** 다시 쓰면 문체는 매끄러워지지만 원문을 본 적
    없는 모델이 «제목» 을 근거가 아니라 장식으로 옮긴다. 거기서 허위 인용이 난다.
    그래서 편집자는 머리말·맺음말만 쓰고, 절은 쓴 사람의 것 그대로 둔다.
    대가는 문체가 들쭉날쭉하다는 것이고, 그건 감수하기로 했다."""
    cfg = s["cfg"]
    secs = 채택(s["sections"], cfg["두번째원고"])
    윤곽 = "\n".join(f"{i+1}. {x['제목']} — {x['원고'][:120]}…"
                     for i, x in enumerate(secs))
    out, used = ask(머리맺음.format(q=s["question"], 윤곽=윤곽))
    머리 = re.split(r"맺음말\s*[:：]", out)[0].replace("머리말:", "").strip()
    맺음 = (re.split(r"맺음말\s*[:：]", out) + [""])[1].strip()

    본문 = "\n\n".join(f"## {i+1}. {x['제목']}\n\n{x['원고']}"
                       for i, x in enumerate(secs))
    report = f"# {s['question']}\n\n{머리}\n\n{본문}\n\n## 맺음말\n\n{맺음}"
    return {"report": report, "sections": [], "coord_chars": used, "calls": 1}


# ── ⑥ 평가 ────────────────────────────────────────────────────────────
def n_평가(s):
    secs = 채택(s["sections"], s["cfg"]["두번째원고"])
    읽음 = [t for sec in secs for t in sec["읽은자료"]]
    m = metrics.score(s["report"], 읽음)
    tot = s.get("coord_chars", 0) + s.get("agent_chars", 0)
    m["격리율"] = round(s.get("coord_chars", 0) / tot, 3) if tot else 0.0
    m["코디네이터가본글자"] = s.get("coord_chars", 0)
    m["조사관이본글자"] = s.get("agent_chars", 0)
    m["LLM호출"] = s.get("calls", 0)
    m["절수"] = len(secs)
    m["재위임절"] = sum(1 for x in secs if x["round"] > 0)
    m["배정고침"] = s.get("plan_fix", 0)
    return {"metrics": m}


# ── 조립 ──────────────────────────────────────────────────────────────
def build():
    g = StateGraph(S)
    for name, fn in [("기획", n_기획), ("배치", n_배치), ("조사관", n_조사관),
                     ("점검", n_점검), ("종합", n_종합), ("평가", n_평가)]:
        g.add_node(name, fn)
    g.add_edge(START, "기획")
    g.add_edge("기획", "배치")
    g.add_conditional_edges("배치", 파견, ["조사관"])
    g.add_edge("조사관", "점검")
    g.add_conditional_edges("점검", 다시, ["조사관", "종합"])
    g.add_edge("종합", "평가")
    g.add_edge("평가", END)
    return g.compile()


TEAM = build()


def run(question, cfg=None, 스위치=None):
    cfg = json.loads(json.dumps(cfg or config()))
    if 스위치:
        cfg["스위치"].update(스위치)
    t0 = time.time()
    out = TEAM.invoke({"question": question, "cfg": cfg},
                      {"recursion_limit": 60})
    out["secs"] = round(time.time() - t0, 1)
    out["설정"] = {"스위치": cfg["스위치"], "절수": cfg["절수"],
                   "절예산": cfg["절예산"], "두번째원고": cfg["두번째원고"]}
    out["절상세"] = [{k: v for k, v in x.items() if k != "원고"} | {"원고": x["원고"]}
                     for x in 채택(out.get("sections", []), cfg["두번째원고"])]
    return out


if __name__ == "__main__":
    import sys
    from common import questions
    qs = {q["id"]: q for q in questions()}
    qid = sys.argv[1] if len(sys.argv) > 1 else "Q8"
    q = qs[qid]
    print(f"코퍼스 {len(TITLES)}건 · {CORPUS['total_chars']:,}자 "
          f"(추정 {CORPUS['total_chars']//4:,}토큰 / 창 {WINDOW:,} = "
          f"{CORPUS['total_chars']/4/WINDOW:.1f}배)\n")
    print(f"[{qid}·{q['유형']}] {q['q']}\n")
    out = run(q["q"])
    for x in out["절상세"]:
        print(f"  {x['idx']+1}. 「{x['제목']}」 ({x['역할']}) "
              f"읽음 {', '.join(x['읽은자료'])}")
    print()
    print(metrics.line("기본", out["metrics"]))
    m = out["metrics"]
    print(f"  격리율 {m['격리율']:.1%} (코디 {m['코디네이터가본글자']:,}자 / "
          f"조사관 {m['조사관이본글자']:,}자) · 호출 {m['LLM호출']} · {out['secs']}초 "
          f"· 배정 고침 {m['배정고침']}건")
    print("\n" + "─" * 70 + "\n")
    print(out["report"])
