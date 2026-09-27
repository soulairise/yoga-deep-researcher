# -*- coding: utf-8 -*-
"""공통 — 코퍼스·설정·모델·키. 그리고 **본 글자 수를 세는 계량기**."""
import json
import os
import subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "output")
REPORTS = os.path.join(OUT, "reports")
os.makedirs(REPORTS, exist_ok=True)

MODEL = "gpt-4o-mini"      # 창 128k. 코퍼스(추정 35만 토큰)가 2.8배로 안 들어간다.
WINDOW = 128_000


def api_key():
    """환경변수 → macOS 키체인. 키를 파일이나 셸 히스토리에 남기지 않는다."""
    if os.getenv("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    try:
        k = subprocess.run(["security", "find-generic-password", "-a", os.environ["USER"],
                            "-s", "soulmat-openai", "-w"],
                           capture_output=True, text=True, check=True).stdout.strip()
        os.environ["OPENAI_API_KEY"] = k
        return k
    except Exception:
        return ""


def corpus():
    return json.load(open(os.path.join(DATA, "corpus.json"), encoding="utf-8"))


def questions():
    return json.load(open(os.path.join(DATA, "questions.json"),
                          encoding="utf-8"))["questions"]


def config():
    return json.load(open(os.path.join(BASE, "config.json"), encoding="utf-8"))


# ── 계량기 ────────────────────────────────────────────────────────────
# 격리를 말로 주장하지 않고 **숫자로** 보이기 위한 장치다. 모델에 넣기 직전에
# 글자를 세고, 그 수를 호출한 쪽이 상태로 돌려보낸다. 팬아웃이 스레드로 도는데
# 공유 카운터를 += 하면 경합이 생기므로, 세는 것은 각자 하고 합치는 것은
# LangGraph 의 리듀서에 맡긴다.
def ask(prompt, model=None, temperature=0.0):
    """LLM 한 번. **(답, 넣은 글자 수)** 를 돌려준다. 글자 수를 안 돌려주는
    호출 경로를 만들지 않는 것이 이 프로젝트의 규칙이다 — 격리율이 곧 증거라서."""
    from langchain_openai import ChatOpenAI
    api_key()
    m = ChatOpenAI(model=model or MODEL, temperature=temperature,
                   timeout=180, max_retries=3)
    return m.invoke(prompt).content.strip(), len(prompt)
