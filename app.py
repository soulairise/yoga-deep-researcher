# -*- coding: utf-8 -*-
"""데모 — 직접 물어보고, **누가 무엇을 읽고 무엇을 썼는지** 본다.

  streamlit run app.py

숫자만 보여 주는 화면은 이 프로젝트의 요점을 놓친다. 이 구조의 값어치는
'답이 맞았나'가 아니라 '어떻게 나눠서 그 답에 닿았나'에 있으므로,
기획이 짠 목차와 배정 · 조사관이 실제로 읽은 자료 · 절 원고를 모두 펼쳐 둔다.
스위치도 화면에서 끌 수 있게 해서, 절제 실험을 눈으로 한 번 더 하게 했다.
"""
import time

import streamlit as st

import baseline
import graph
import metrics
from common import api_key, config, corpus, questions

st.set_page_config(page_title="요가·명상 딥리서처", page_icon="🪷", layout="wide")
C = corpus()
CFG = config()

st.title("🪷 요가·명상 딥리서처")
st.caption(
    f"코디네이터 하나가 목차를 짜고 조사관 넷을 동시에 내보낸다 · "
    f"코퍼스 {len(C['docs'])}건 · {C['total_chars']:,}자 "
    f"(추정 {C['total_chars']//4:,}토큰 = 모델 창의 {C['total_chars']/4/128000:.1f}배) · "
    f"내부 링크 {C['internal_links']}개"
)

# ── 설정 ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("설정")
    절수 = st.slider("절 수 (조사관 수)", 1, 6, CFG["절수"])
    절예산 = st.slider("절마다 읽을 자료", 1, 6, CFG["절예산"])
    st.caption(f"총 읽기 예산 **{절수 * 절예산}건**. 폭과 깊이는 손잡이가 하나다.")
    st.divider()
    st.subheader("스위치 (절제 실험)")
    배정 = st.toggle("배정·구역", True, help="코디네이터가 시작 자료를 나눠 주고 남의 구역을 알려 준다")
    역할 = st.toggle("역할", True, help="조사관마다 다른 지시문을 붙인다")
    재위임 = st.toggle("재위임", True, help="부족하다고 신고한 절만 다시 내보낸다")
    두번째 = st.radio("두 번째 원고", ["인용밀도", "덮어쓰기"], horizontal=True,
                       help="재위임으로 원고가 둘이 됐을 때 무엇을 남길까")
    st.divider()
    대조 = st.toggle("혼자 하는 대조군도 같이 돌리기", False,
                     help="같은 자료·모델·도구·예산. 나누지 않는 것만 다르다")

if not api_key():
    st.error("OPENAI_API_KEY 를 찾지 못했습니다. 환경변수에 넣거나 macOS 키체인에 "
             "`soulmat-openai` 로 저장하세요.")
    st.stop()

# ── 질문 ──────────────────────────────────────────────────────────────
QS = questions()
라벨 = {f"[{q['유형']}] {q['q']}": q for q in QS}
# ?q=Q8 로 열면 그 질문을 바로 돌린다. 화면 캡처를 자동으로 찍기 위한 문이고,
# 링크로 특정 질문을 바로 보여 줄 때도 쓴다.
미리 = st.query_params.get("q")
기본선택 = next((k for k, v in 라벨.items() if v["id"] == 미리), "(직접 입력)")
고른 = st.selectbox("준비된 질문", ["(직접 입력)"] + list(라벨),
                     index=(["(직접 입력)"] + list(라벨)).index(기본선택))
if 고른 == "(직접 입력)":
    q = st.text_input("질문", "요가 전통에서 호흡을 다루는 기법에는 어떤 것들이 있는가?")
    왜 = None
else:
    q = 라벨[고른]["q"]
    왜 = 라벨[고른]["왜 나눌 만한가"]
    st.info(f"**왜 나눌 만한가** — {왜}")

눌림 = st.button("조사 시작", type="primary")
if not (눌림 or (미리 and 기본선택 != "(직접 입력)")):
    st.stop()

cfg = config()
cfg.update({"절수": 절수, "절예산": 절예산, "두번째원고": 두번째})
cfg["스위치"] = {"배정": 배정, "역할": 역할, "재위임": 재위임}

with st.spinner(f"조사관 {절수}명이 각자 {절예산}건씩 읽는 중…"):
    t0 = time.time()
    out = graph.run(q, cfg)
    solo = baseline.run(q, cfg) if 대조 else None

m = out["metrics"]

# ── 계기판 ────────────────────────────────────────────────────────────
st.subheader("계기판")
st.caption("정답표도 판정 모델도 쓰지 않는다. 만들어진 글과 실제로 읽은 자료만 본다.")
c = st.columns(6)
c[0].metric("근거율 ↑", f"{m['근거율']:.0%}", help="문장 중 «자료»가 붙은 비율 — 깊이·재위임의 계기")
c[1].metric("최다문서편중 ↓", f"{m['최다문서편중']:.0%}", help="인용이 한 문서에 몰렸나 — 배정·구역의 계기")
c[2].metric("중복률 ↓", f"{m['중복률']:.0%}", help="같은 문서를 여러 절이 겹쳐 읽었나 — 배정·구역의 계기")
c[3].metric("읽고 안 쓴 문서 ↓", f"{m['읽고안쓴문서']}건", help="예산을 쓰고 버렸다 — 배정 품질의 계기")
c[4].metric("허위 인용", f"{m['허위인용']}건",
            delta="경보" if m["허위인용"] else "정상",
            delta_color="inverse" if m["허위인용"] else "normal",
            help="읽지 않은 자료를 인용했나 — 신호가 아니라 경보다. 0이어야 한다")
c[5].metric("격리율 ↓", f"{m['격리율']:.0%}", help="코디네이터가 본 글자 ÷ 팀 전체가 본 글자")

if m["허위인용"]:
    st.error(f"**허위 인용 {m['허위인용']}건** — {', '.join(m['_허위인용목록'])}. "
             "이건 높낮이를 견주는 값이 아니라 경보입니다. 이 보고서는 탈락입니다.")

st.caption(
    f"코디네이터가 본 글자 {m['코디네이터가본글자']:,} · 조사관이 본 글자 "
    f"{m['조사관이본글자']:,} · LLM 호출 {m['LLM호출']}회 · {out['secs']}초 · "
    f"재위임된 절 {m['재위임절']}개 · 배정이 없는 제목을 가리켜 고친 건수 {m['배정고침']}"
)

# ── 분업이 어떻게 갈렸나 ──────────────────────────────────────────────
st.subheader("① 기획 — 코디네이터가 짠 목차와 배정")
st.caption("코디네이터가 본 것은 자료 전문이 아니라 **제목 + 앞 250자 카드**뿐이다.")
st.dataframe(
    [{"절": i + 1, "제목": o["제목"], "역할": o.get("역할"),
      "시작 자료(배정)": ", ".join(o.get("시작자료") or []) or "— (배정 끔)",
      "왜": o.get("왜", "")} for i, o in enumerate(out["outline"])],
    hide_index=True, use_container_width=True)

st.subheader("②③ 조사관 — 누가 무엇을 읽고 무엇을 썼나")
탭 = st.tabs([f"{i+1}. {x['제목'][:18]}" for i, x in enumerate(out["절상세"])])
for t, x in zip(탭, out["절상세"]):
    with t:
        a, b = st.columns([1, 2])
        with a:
            st.markdown(f"**역할** {x['역할'] or '(역할 끔)'}")
            st.markdown("**읽은 자료**")
            for r in x["읽은자료"]:
                쓴 = "✅" if r in x["인용"] else "⬜"
                st.markdown(f"{쓴} {r}")
            st.caption("✅ 인용까지 된 자료 · ⬜ 읽었지만 보고서에 안 쓴 자료")
            st.markdown(f"**자기신고** {'부족하다고 신고함' if x['부족'] else '충분'} · "
                        f"바퀴 {x['round']+1}")
            st.markdown(f"**인용 {len(x['인용'])}개** / {len(x['원고'])}자")
        with b:
            st.markdown(x["원고"])

# ── 보고서 ────────────────────────────────────────────────────────────
st.subheader("⑤ 종합 — 최종 보고서")
st.caption("편집자는 절 본문에 손대지 않는다. 머리말과 맺음말만 새로 쓴다 — "
           "다시 쓰면 원문을 본 적 없는 모델이 인용을 흘린다.")
if solo:
    left, right = st.columns(2)
    with left:
        st.markdown(f"#### 팀 ({절수}명)")
        st.caption(metrics.line("", m).strip())
        st.markdown(out["report"])
    with right:
        sm = solo["metrics"]
        st.markdown("#### 혼자 (대조군)")
        st.caption(metrics.line("", sm).strip())
        예산 = 절수 * 절예산
        if sm["읽은건수"] == 예산:
            st.caption(f"예산 {예산}건을 다 썼다. 공정한 비교다.")
        else:
            st.warning(f"대조군이 예산 {예산}건 중 {sm['읽은건수']}건만 읽었다. "
                       "이 비교는 무효다.")
        st.markdown(solo["report"])
else:
    st.markdown(out["report"])

with st.expander("원문과 대조해 보기 — 인용이 제자리에 붙었나"):
    st.caption("읽지 않은 자료를 인용한 것은 코드가 잡는다. 읽은 자료를 엉뚱한 문장에 "
               "갖다 붙인 것은 **사람만** 잡는다. 아래에서 직접 대조하세요.")
    쓴자료 = sorted({r for x in out["절상세"] for r in x["읽은자료"]})
    골라 = st.selectbox("자료", 쓴자료)
    st.text(C["docs"][골라]["text"][:3000])
