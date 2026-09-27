# -*- coding: utf-8 -*-
"""evalkit — LLM 시스템을 잴 때 매번 다시 짜게 되는 것들.

    from evalkit import score_all, measure, compare, distinguishable

자세한 사용법과 '왜 이렇게 되어 있는지'는 README.md 를 읽을 것.
"""
from .judging import ScoreSet, Verdict, judge, parse_reason, parse_score, score_all
from .repeats import Measurement, compare, distinguishable, measure

__all__ = ["Verdict", "ScoreSet", "judge", "score_all", "parse_score", "parse_reason",
           "Measurement", "measure", "distinguishable", "compare"]
