# -*- coding: utf-8 -*-
"""코퍼스 — 영어 위키백과 '요가·명상·호흡' 클러스터.  `python fetch_corpus.py`

한국어 위키는 이 주제가 얇다. 「Tirumalai Krishnamacharya」·「Anapanasati」처럼
계보를 잇는 문서가 한두 문단뿐이라 절을 나눌 거리가 안 나온다. 그래서 영어로 모으고
**보고서는 한국어로 쓴다.** 조사관이 읽는 것과 쓰는 것의 언어가 다른 셈인데,
이 프로젝트에서는 그게 오히려 인용을 보기 쉽게 만든다 — 한국어 문장에 «English Title»
이 붙으니 어느 문장이 어느 자료에서 왔는지 눈으로도 구분된다.

본문만 받지 않고 **코퍼스 안으로 들어오는 링크만 추려** 같이 남긴다.
링크가 0인 문서는 탐색만으로는 영원히 못 닿는다. 그 자리에는 배정이 유일한 경로다.
"""
import json
import os
import re
from collections import Counter

from wiki import page, resolve

BASE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(BASE, "data", "docs")
CORPUS = os.path.join(BASE, "data", "corpus.json")

# 네 덩어리로 골랐다. 한 덩어리 안에서는 서로를 가리키고, 덩어리끼리도 이어진다.
SEEDS = [
    # ① 고전 요가 — 경전과 철학
    "Yoga", "Yoga Sutras of Patanjali", "Patanjali", "Raja yoga",
    "Ashtanga (eight limbs of yoga)", "Yamas", "Niyama", "Dharana", "Pratyahara",
    "Samadhi", "Dhyana in Hinduism", "Bhagavad Gita",
    # ② 하타요가 — 몸과 호흡의 기술
    "Hatha yoga", "Hatha Yoga Pradipika", "Pranayama", "Asana", "Bandha (yoga)",
    "Mudra", "Nadi (yoga)", "Prana", "Chakra", "Kundalini", "Kundalini yoga",
    "Nath", "Gorakhnath", "Shatkarma",
    # ③ 불교 명상 — 호흡을 보는 또 하나의 계보
    "Buddhist meditation", "Anapanasati", "Samatha", "Vipassanā",
    "Satipatthana", "Dhyāna in Buddhism", "Mindfulness", "Sati (Buddhism)",
    "Zen", "Zazen", "Vipassana movement", "S. N. Goenka", "Theravada",
    # ④ 근현대 — 전통이 오늘의 수업이 되기까지
    "Modern yoga", "Yoga as exercise", "Tirumalai Krishnamacharya",
    "B. K. S. Iyengar", "K. Pattabhi Jois", "Ashtanga vinyasa yoga", "Iyengar Yoga",
    "Sivananda Saraswati", "Swami Vivekananda", "Paramahansa Yogananda",
    "Kriya Yoga school of Lahiri Mahasaya", "Lahiri Mahasaya",
    "Transcendental Meditation", "Maharishi Mahesh Yogi",
    "Jon Kabat-Zinn", "Mindfulness-based stress reduction", "Surya Namaskar",
    "Indra Devi",
    # ⑤ 호흡 그 자체 — 대표님 도메인의 한가운데
    "Holotropic Breathwork", "Diaphragmatic breathing", "Ujjayi breath",
    "Kapalabhati", "Nadi shodhana", "Buteyko method",
]


def save(title, text):
    os.makedirs(DOCS, exist_ok=True)
    name = re.sub(r'[/\\:*?"<>|]', "_", title).replace(" ", "_")
    open(os.path.join(DOCS, f"{name}.md"), "w", encoding="utf-8").write(
        f"# {title}\n\n{text.strip()}\n")
    return name


def main():
    print("── 문서 확인 ──")
    titles, seen = [], set()
    for s in SEEDS:
        t, how = resolve(s)
        if t is None:
            print(f"  X {s}: {how}")
        elif t in seen:
            print(f"  · {s} → {t} (중복)")
        else:
            seen.add(t)
            titles.append(t)
    print(f"  문서 {len(titles)}건\n")

    print("── 본문 받기 ──")
    docs = {}
    for i, t in enumerate(titles, 1):
        d = page(t)
        if d is None or len(d["text"]) < 1500:
            print(f"  X {t} (본문 {len(d['text']) if d else 0}자 — 너무 짧아 뺀다)")
            continue
        docs[t] = d
        print(f"  {i:2d}. {t} ({len(d['text']):,}자)")

    inside = set(docs)
    out_docs, links, total_links = {}, {}, 0
    for t, d in docs.items():
        out = sorted((set(d["links"]) & inside) - {t})
        total_links += len(out)
        links[t] = out
        out_docs[t] = {"title": t, "file": save(t, d["text"]),
                       "chars": len(d["text"]), "text": d["text"].strip()}

    incoming = Counter()
    for t, ls in links.items():
        for l in ls:
            incoming[l] += 1
    unreachable = [t for t in out_docs if incoming[t] == 0]
    isolated = [t for t in out_docs if incoming[t] == 0 and not links[t]]

    total_chars = sum(d["chars"] for d in out_docs.values())
    json.dump({"docs": out_docs, "links": links,
               "total_chars": total_chars, "internal_links": total_links},
              open(CORPUS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 이 구조를 쓸 이유가 있는지 여기서 판정한다. 창에 들어가면 그냥 다 넣으면 된다.
    tokens = total_chars / 4          # 영어는 대략 4자 = 1토큰
    window = 128_000                  # gpt-4o-mini
    print("\n── 결과 ──")
    print(f"  문서 {len(out_docs)}건 · {total_chars:,}자 · 내부 링크 {total_links}개")
    print(f"  추정 토큰 {tokens:,.0f} / 모델 창 {window:,}  →  "
          f"{tokens / window:.1f}배 " + ("(넘는다. 나눌 이유가 있다)" if tokens > window
                                        else "(안 넘는다. 주제를 다시 잡아야 한다)"))
    print(f"  링크로 닿을 수 없는 문서(들어오는 링크 0): {unreachable or '없음'}")
    print(f"  완전히 떨어진 문서(양쪽 다 0): {isolated or '없음'}")
    print(f"  저장: {CORPUS}")


if __name__ == "__main__":
    main()
