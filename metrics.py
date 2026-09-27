# -*- coding: utf-8 -*-
"""지표 — **정답표도 판정 모델도 쓰지 않는다.**

만들어진 글과 실제로 읽은 자료, 둘만 본다. 그래서 설정을 어떻게 바꿔도,
질문을 갈아 끼워도, 코퍼스를 통째로 바꿔도 잣대가 그대로다. 절제 실험이
성립하는 조건이 그거다.

지표마다 **어느 장치를 보는 신호인지**를 붙여 두었다. 종합 점수 하나로는
'나빠졌다'까지만 말할 수 있고 범인은 못 잡는다.

  근거율        ← 깊이 · 재위임
  최다문서편중   ← 배정 · 구역
  중복률        ← 배정 · 구역
  읽고안쓴문서   ← 배정 품질
  격리율        ← 컨텍스트 격리
  허위인용      ← 경보. 신호가 아니다. 0이 아니면 그 보고서는 볼 것도 없다.

설명이 한 줄로 안 되는 지표는 넣지 않았다.
"""
import re
import unicodedata

# 문장 분리 규칙은 **여기 한 곳에만** 있고 바꾸지 않는다.
# 지표가 좋아진 줄 알았는데 분리 규칙이 바뀐 것이었다 — 흔한 사고라 못을 박는다.
# 아래 self_test() 가 매번 이 규칙이 그대로인지 확인한다.
# 마침표 앞이 **홑 대문자면 쪼개지 않는다.** 「B. K. S. Iyengar」·「S. N. Goenka」가
# 세 문장으로 갈려 근거율이 실제의 1/3로 찍혔다. 지표가 나빠 보이는데 원인이
# 시스템이 아니라 분리 규칙인 경우다 — 교안이 경고한 바로 그 사고.
_SENT = re.compile(r"(?<=[.!?。])(?<![A-Z]\.)\s+|(?<=다)\s*\n+|\n{2,}")
_CITE = re.compile(r"«([^»]{1,120})»")


def sentences(text):
    """제목 줄(#, ##…)과 목록 기호는 문장으로 세지 않는다."""
    body = [l for l in text.splitlines() if not l.lstrip().startswith("#")]
    out = []
    for chunk in _SENT.split("\n".join(body)):
        s = (chunk or "").strip().lstrip("-*•0123456789. ").strip()
        if len(s) >= 10:
            out.append(s)
    return out


def cites(text):
    return _CITE.findall(text)


def fold(t):
    """표기 변형을 접는다. 「Bhagavad Gītā」와 코퍼스의 「Bhagavad Gita」는 같은 문서다.
    마크론 때문에 허위 인용 경보가 울리면 **경보를 못 믿게 된다** — 경보는 0이어야
    뜻이 있으므로, 같은 것을 같다고 보는 일이 느슨해지는 것보다 중요하다.
    (산스크리트 전사 표기를 접는 방법은 앞 프로젝트에서 쓰던 것과 같다.)"""
    d = unicodedata.normalize("NFKD", t)
    return "".join(c for c in d if not unicodedata.combining(c)).lower().strip()


def score(report, read_titles, corpus_titles=None):
    """report: 최종 보고서 문자열 · read_titles: 실제로 read_one() 한 문서 제목들
    (중복 포함 — 중복률을 재려면 몇 번 읽었는지가 필요하다)"""
    sents = sentences(report)
    cs = cites(report)
    read_uniq = set(read_titles)

    with_cite = sum(1 for s in sents if _CITE.search(s))
    근거율 = with_cite / len(sents) if sents else 0.0

    가장많이 = {}
    for c in cs:
        가장많이[c] = 가장많이.get(c, 0) + 1
    편중 = (max(가장많이.values()) / len(cs)) if cs else 0.0

    # 같은 문서를 여러 절이 겹쳐 읽은 비율. 구역이 일하면 0 에 가깝다.
    중복률 = (len(read_titles) - len(read_uniq)) / len(read_titles) if read_titles else 0.0

    읽음f = {fold(t): t for t in read_uniq}
    인용f = {fold(c) for c in cs}
    안쓴 = sorted(v for k, v in 읽음f.items() if k not in 인용f)
    허위 = sorted({c for c in set(cs) if fold(c) not in 읽음f})

    return {
        "근거율": round(근거율, 3),
        "최다문서편중": round(편중, 3),
        "중복률": round(중복률, 3),
        "읽고안쓴문서": len(안쓴),
        "허위인용": len(허위),
        "_읽고안쓴목록": 안쓴,
        "_허위인용목록": 허위,
        "문장수": len(sents),
        "인용수": len(cs),
        "읽은건수": len(read_titles),
        "고유문서수": len(read_uniq),
        "보고서길이": len(report),
    }


HEADER = ["근거율", "최다문서편중", "중복률", "읽고안쓴문서", "허위인용",
          "인용수", "읽은건수", "보고서길이"]


def line(label, m, extra=None):
    s = (f"{label:<16} 근거율 {m['근거율']:>5.1%} · 편중 {m['최다문서편중']:>5.1%} · "
         f"중복 {m['중복률']:>5.1%} · 안쓴 {m['읽고안쓴문서']:>2}건 · "
         f"허위 {m['허위인용']:>2}건 · 인용 {m['인용수']:>3} · "
         f"읽음 {m['읽은건수']:>2} · {m['보고서길이']:>5,}자")
    return s + (f" · {extra}" if extra else "")


def self_test():
    """분리 규칙이 그대로인지 매번 확인한다. 여기서 틀리면 모든 숫자를 믿으면 안 된다."""
    t = ("# 제목\n\n"
         "요가의 호흡법은 «Pranayama» 에 정리되어 있다.\n"
         "우짜이는 목을 좁혀 소리를 낸다 «Ujjayi».\n"
         "- 반다는 몸을 잠근다\n")
    s, c = sentences(t), cites(t)
    assert len(s) == 3, f"문장 분리가 바뀌었다: {len(s)}개 — {s}"
    # 이니셜이 든 문장은 한 문장이어야 한다. 여기서 깨지면 근거율이 통째로 틀린다.
    ini = sentences("B. K. S. Iyengar는 정렬을 강조했다 «B. K. S. Iyengar». "
                    "K. Pattabhi Jois는 흐름을 강조했다 «K. Pattabhi Jois».")
    assert len(ini) == 2, f"이니셜에서 쪼개진다: {len(ini)}개 — {ini}"
    assert c == ["Pranayama", "Ujjayi"], f"인용 추출이 바뀌었다: {c}"
    m = score(t, ["Pranayama", "Ujjayi", "Pranayama", "Asana"])
    assert m["인용수"] == 2 and m["읽은건수"] == 4 and m["고유문서수"] == 3
    assert m["중복률"] == 0.25 and m["읽고안쓴문서"] == 1 and m["허위인용"] == 0
    assert m["근거율"] == 0.667          # 세 문장 중 둘에 인용이 붙었다
    # 표기 변형은 같은 문서로 접힌다. 접히지 않으면 경보가 오작동한다.
    assert score("바가바드 기타를 인용한다 «Bhagavad Gītā».",
                 ["Bhagavad Gita"])["허위인용"] == 0
    # 접는다고 아무거나 같아지면 안 된다. 「Sutta」가 붙으면 다른 문서다.
    assert score("경을 인용한다 «Ānāpānasati Sutta».",
                 ["Anapanasati"])["허위인용"] == 1
    return True


if __name__ == "__main__":
    print("자체 검증:", "통과" if self_test() else "실패")
    print("  문장 분리·인용 추출·다섯 지표가 모두 못 박은 대로 돈다.")
