# -*- coding: utf-8 -*-
"""같은 설정을 여러 번 돌려 **차이가 편차보다 큰지** 먼저 본다.

이 파일이 있는 이유:
2026-09-18, 탐색 예산을 올렸더니 점수가 3.67 → 3.47 로 내려갔다. "많이 담으면
나빠진다"고 결론 낼 뻔했는데, 같은 설정을 3회 다시 돌려 보니 편차 자체가 0.20 이었다.
두 설정의 실제 차이는 0.04 — 구분되지 않는 값이었다.

한 번 재고 방향을 말하지 않는다. 그게 여기 있는 전부다.
"""
import statistics as st
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class Measurement:
    label: str
    runs: List[float]   # 회차별 평균
    failures: int = 0   # 심판 실패 총 건수
    items: Dict[str, List[float]] = field(default_factory=dict)  # 항목별 회차 결과

    @property
    def mean(self):
        return st.mean(self.runs)

    @property
    def spread(self):
        return max(self.runs) - min(self.runs) if len(self.runs) > 1 else float("nan")

    def __str__(self):
        if len(self.runs) == 1:
            return (f"{self.label}: {self.mean:.2f} "
                    f"(1회 — 편차를 모르므로 이 값으로 비교하지 말 것)")
        return (f"{self.label}: {self.mean:.2f} "
                f"(폭 {self.spread:.2f} · {len(self.runs)}회: "
                + ", ".join(f"{r:.2f}" for r in self.runs) + ")"
                + (f" · 심판 실패 {self.failures}" if self.failures else ""))


    # ── 항목별 흔들림 ────────────────────────────────────────────────
    # 소울매트 CS 에이전트에서 먼저 만든 것을 올려 왔다. 전체 평균만 보면
    # "39건 중 36건 통과"가 매번 같은 36건인지, 회차마다 다른 36건인지 알 수 없다.
    # 둘은 완전히 다른 상황이다.

    @property
    def flaky(self) -> List[Tuple[str, float]]:
        """회차마다 결과가 달라진 항목. **이 건들은 비교 근거로 쓸 수 없다.**"""
        out = [(k, sum(v) / len(v)) for k, v in self.items.items()
               if len(set(v)) > 1]
        return sorted(out, key=lambda x: x[1])

    @property
    def always_fail(self) -> List[str]:
        """매번 최저점인 항목. **진짜 고칠 곳은 여기다.**"""
        return sorted(k for k, v in self.items.items() if set(v) == {0} or set(v) == {0.0})

    def print_items(self, reps_label="회"):
        if not self.items:
            return
        if self.flaky:
            # 0/1 통과 여부일 때와 점수(예: 1~5)일 때 표시가 달라야 한다.
            # 예전 판은 무조건 'N회 중 M회 통과' 로 찍어서, 1~5점 척도에서
            # '3회 중 11회 통과' 같은 말이 안 되는 줄이 나왔다.
            binary = all(set(v) <= {0.0, 1.0} for v in self.items.values())
            print(f"  [회차마다 결과가 달라진 항목 {len(self.flaky)}개]"
                  " — 비교 근거로 쓸 수 없다")
            for k, _ in self.flaky:
                vals = self.items[k]
                if binary:
                    print(f"    {k}  {len(vals)}{reps_label} 중 "
                          f"{int(sum(vals))}회 통과")
                else:
                    print(f"    {k}  {', '.join(f'{v:g}' for v in vals)}"
                          f"  (평균 {sum(vals)/len(vals):.2f})")
        if self.always_fail:
            print(f"  [매번 실패 {len(self.always_fail)}개] — 진짜 고칠 곳은 여기다")
            print("    " + ", ".join(self.always_fail))


def _to_items(result):
    """run_once 의 반환을 {항목: 점수} 로 맞춘다. ScoreSet 도 dict 도 받는다."""
    if hasattr(result, "as_items"):
        return result.as_items(), result.mean, len(result.failures)
    if isinstance(result, dict):
        vals = list(result.values())
        return result, (sum(vals) / len(vals) if vals else float("nan")), 0
    return {}, float(result), 0


def measure(label, run_once, reps=3):
    """run_once() 를 reps 번 돌려 Measurement 로 만든다.

    run_once 는 ScoreSet, {항목: 점수} dict, 또는 그냥 숫자를 돌려주면 된다.
    앞의 둘이면 항목별 흔들림(`flaky`, `always_fail`)까지 같이 잡힌다."""
    runs, fails, items = [], 0, {}
    for _ in range(reps):
        got, mean, nf = _to_items(run_once())
        runs.append(mean)
        fails += nf
        for k, v in got.items():
            items.setdefault(k, []).append(float(v))
    return Measurement(label, runs, fails, items)


def distinguishable(a: Measurement, b: Measurement):
    """두 측정의 차이를 '있다'고 말해도 되는가.

    기준은 **차이 > 두 측정 중 큰 폭**이다. 통계적으로 엄밀한 검정은 아니고,
    3~5회 반복으로 방향을 말해도 되는지 거르는 최소 관문이다.
    엄밀함이 필요하면 회차를 늘리고 t 검정을 쓸 것."""
    if len(a.runs) < 2 or len(b.runs) < 2:
        return False
    return abs(a.mean - b.mean) > max(a.spread, b.spread)


def compare(arms, reps=3, note=""):
    """설정 여러 개를 나란히 재고, **구분되는 것만** 구분된다고 말한다.

    arms: {이름: run_once} — run_once 는 ScoreSet 를 돌려주는 함수.

    ⚠️ A/B 를 짤 때 가장 흔한 실수: 기능을 '껐다'면서 그 기능이 흘리는 정보는
    그대로 두는 것. 2026-09-18 에 연도 필터를 끄면서 후보 목록의 연도 '표기'는
    남겨 둬, 사실은 같은 조건 둘을 비교하고 차이가 없다고 결론 낼 뻔했다.
    끄는 쪽은 그 기능이 근거에 남기는 것까지 전부 꺼야 한다."""
    ms = [measure(name, fn, reps) for name, fn in arms.items()]
    print(f"── {reps}회씩 측정 ──" + (f"  ({note})" if note else ""))
    for m in ms:
        print("  " + str(m))
        m.print_items()
    best = max(ms, key=lambda m: m.mean)
    ties = [m for m in ms if m is not best and not distinguishable(best, m)]
    print()
    if ties:
        print(f"  '{best.label}' 가 가장 높지만 "
              + ", ".join(f"'{m.label}'" for m in ties)
              + " 와는 구분되지 않는다 (차이가 편차 안).")
        print("  → 구분되지 않으면 점수로 고르지 말고 비용·단순함으로 고를 것.")
    else:
        print(f"  '{best.label}' 가 나머지 전부와 구분된다.")
    return ms
