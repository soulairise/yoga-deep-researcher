# 요가·명상 딥리서처

코디네이터 하나가 보고서 목차를 짜고, 조사관(서브에이전트) 넷을 **동시에** 내보내
각자 한 절씩 쓰게 한 뒤 이어 붙여 장문 보고서를 만든다.
정답표 없이 재고, 장치를 하나씩 꺼서 무엇이 실제로 값을 했는지 가른다.

모두의연구소 「에이전트 팀 꾸리기」 딥리서처 실습 프로젝트 (2026-09-27).
설계 판단과 측정 결과는 **[REPORT.md](REPORT.md)** 에 있다.

## 왜 나누는가 — 숫자부터

| | |
|---|---|
| 코퍼스 | 영어 위키백과 요가·명상·호흡 **59건** |
| 총 글자 | **1,421,393자** (추정 355,348토큰) |
| 모델 창 | gpt-4o-mini · 128,000토큰 |
| 비율 | **2.8배 — 한 창에 안 들어간다** |
| 내부 링크 | 1,065개 |

들어갔으면 그냥 다 넣으면 됐다. 안 들어가서 나눈다.

## 돌리는 법

파이썬 3.10 이상.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

키는 환경변수 `OPENAI_API_KEY` 또는 macOS 키체인에서 읽는다(`common.api_key()`).
**저장소에 키를 넣지 않는다.** 키체인에 두면 셸 히스토리에도 안 남는다.

```bash
security add-generic-password -a "$USER" -s soulmat-openai -w
```

순서대로.

```bash
.venv/bin/python fetch_corpus.py          # 코퍼스 수집 (키 불필요 · 약 2분)
.venv/bin/python metrics.py               # 지표 자체 검증 (키 불필요)
.venv/bin/python graph.py Q8              # 팀으로 한 질문 (약 15초)
.venv/bin/python baseline.py Q8           # 혼자 하는 대조군
.venv/bin/python ablation.py              # 절제 실험 6설정 × 4질문 × 2회 (약 15분)
.venv/bin/streamlit run app.py            # 데모
```

`data/corpus.json` 은 저장소에 들어 있으므로 `fetch_corpus.py` 없이도 나머지가 다 돈다.
(사람이 읽기 좋은 `data/docs/*.md` 는 corpus.json 과 내용이 같은 사본이라 넣지 않았다.
`fetch_corpus.py` 를 돌리면 생긴다.)

## 파일

| 파일 | 하는 일 |
|---|---|
| `fetch_corpus.py` | 위키백과에서 본문과 **코퍼스 안쪽 링크**를 모은다. 총 글자가 창을 넘는지 판정한다 |
| `data/corpus.json` | 문서 59건 + 링크 |
| `data/questions.json` | 질문 10건. 정답표 없이 **"왜 나눌 만한가"** 한 줄씩 |
| `config.json` | 절수·절예산·바퀴상한·역할 명단·**스위치 셋** |
| `graph.py` | 기획 → 배치 → 조사관(팬아웃) → 점검 → 종합 → 평가 |
| `metrics.py` | 지표. **정답표도 판정 모델도 쓰지 않는다** |
| `baseline.py` | 혼자 하는 오케스트레이터. 예산·모델·도구를 맞춘다 |
| `ablation.py` | 스위치를 하나씩 끄고 같은 잣대로 잰다 |
| `app.py` | 데모. 절마다 누가 무엇을 읽고 무엇을 썼는지 펼친다 |
| `evalkit/` | 공통 평가 도구 복사본. 차이가 편차보다 큰지 판정한다 |
| `output/` | `runs.jsonl` · `ablation.json` · `reports/` |

## 자료 출처

영어 위키백과 (CC BY-SA 4.0). 문서 제목과 링크 구조는 `data/corpus.json` 에 그대로 있다.
