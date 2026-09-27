# -*- coding: utf-8 -*-
"""LLM 을 심판으로 쓸 때의 최소 규칙.

이 파일이 지키는 것은 하나다. **심판이 실패한 것과 시스템이 틀린 것은 다르다.**
실패를 0 점으로 처리하면 심판이 죽은 만큼 평균이 조용히 낮아지고, 그 사실이
어디에도 남지 않는다. 그래서 실패는 None 이고, 평균에서 빠지고, 몇 건인지 보고된다.
"""
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Verdict:
    # 파이썬 3.9 도 쓰는 프로젝트가 있어 `float | None` 대신 Optional 로 쓴다.
    score: Optional[float]       # 실패하면 None. 0 이 아니다.
    reason: str = ""
    error: str = ""              # 실패했을 때 무엇이 실패했는지

    @property
    def ok(self):
        return self.score is not None


def parse_score(text, low=1, high=5, key="점수"):
    """'점수: 4' 형태에서 숫자를 꺼낸다. 범위를 벗어나거나 없으면 None."""
    m = re.search(rf"{key}\s*[:：]\s*(-?\d+(?:\.\d+)?)", text)
    if not m:
        return None
    v = float(m.group(1))
    return v if low <= v <= high else None


def parse_reason(text, key="이유"):
    return next((l.split(":", 1)[1].strip() for l in text.splitlines()
                 if l.startswith(key)), "")


def judge(call, prompt, low=1, high=5):
    """`call(prompt) -> str` 를 받아 판정 하나를 만든다.

    call 은 여러분의 LLM 호출 함수다. 이 모듈은 특정 라이브러리에 묶이지 않는다.
    호출이 터지든 응답을 못 읽든, 그 사실이 Verdict.error 에 남고 score 는 None 이다.
    """
    try:
        out = call(prompt)
    except Exception as e:
        return Verdict(None, error=f"호출 실패: {type(e).__name__}: {e}")
    s = parse_score(out, low, high)
    if s is None:
        return Verdict(None, error=f"응답 해석 실패: {out[:80]!r}")
    return Verdict(s, parse_reason(out))


@dataclass
class ScoreSet:
    """한 번의 채점 결과 묶음."""
    verdicts: List[Verdict] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)

    @property
    def scores(self):
        return [v.score for v in self.verdicts if v.ok]

    @property
    def failures(self):
        return [(l, v.error) for l, v in zip(self.labels, self.verdicts) if not v.ok]

    @property
    def mean(self):
        s = self.scores
        return sum(s) / len(s) if s else float("nan")

    def as_items(self):
        """{항목 이름: 점수} — 반복 측정에서 항목별 흔들림을 보려면 이게 필요하다."""
        return {l: v.score for l, v in zip(self.labels, self.verdicts) if v.ok}

    def by(self, groups):
        """groups[i] 로 묶은 평균. 유형별 점수를 볼 때 쓴다."""
        out = {}
        for g, v in zip(groups, self.verdicts):
            if v.ok:
                out.setdefault(g, []).append(v.score)
        return {g: sum(x) / len(x) for g, x in sorted(out.items())}


def score_all(items, prompt_of, call, label_of=str, workers=8):
    """문항 목록을 한꺼번에 채점한다. 실패는 세어서 남긴다."""
    def one(it):
        return judge(call, prompt_of(it))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        vs = list(ex.map(one, items))
    return ScoreSet(vs, [label_of(i) for i in items])
