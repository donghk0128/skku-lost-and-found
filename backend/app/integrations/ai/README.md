# AI 게시글 작성

## 구현 현황

| 영역 | 상태 | 내용 |
|---|---|---|
| 자연어 게시글 초안 | 구현 | 분실·습득 설명에서 제목, 물품명, 카테고리, 장소, 시간, 키워드 및 누락 정보 추출 |
| Text provider | 구현 | Ollama와 OpenAI Responses API 지원 |
| 사진 업로드 | 구현 | JPEG·PNG·WebP, 최대 5장, 장당 5MiB 미리보기 |
| 사진 속성 추출 | 구현 | 선택한 사진 한 장에서 물품명, 카테고리, 색상, 재질, 브랜드, 형태, 보이는 글자 및 키워드 추출 |
| Vision provider | 구현 | Ollama `moondream`과 OpenAI 이미지 입력 지원 |
| Text 평가 harness | 구현 | 한국어 seed 데이터 100건, 자동 지표, JSON·CSV 결과 및 사람 평가표 생성 |
| Vision 정량 평가 | 계획 | 라벨링 이미지셋, 해상도별 품질·token·비용 및 환각률 비교 필요 |
| 서비스 통합 | 텍스트 구현 | 인증된 다회차 채팅, 초안 미리보기, AI-assisted 게시 및 기존 작성 화면 수정 흐름 연결 |
| 앱 사진 분석 | 후순위 | 프론트 사진 첨부 흐름 구현 후 vision provider와 연결 예정 |
| LangGraph workflow | 구현 | 텍스트 초안 추출, 누락 정보 질문 및 검토 준비 상태를 조건부 edge로 관리 |

## 주요 기능

### 자연어 게시글 초안

분실자 또는 습득자의 한국어 설명을 다음 필드로 구조화합니다.

- `title`, `description`, `item_name`
- `category_code`, `location_text`
- `event_start_at`, `event_end_at`
- `keywords`, `missing_fields`, `warnings`

모든 provider는 같은 Pydantic schema를 사용합니다. 모호한 시간과 장소는 임의로 확정하지 않고 누락 필드 또는 경고로 반환하도록 prompt를 구성했습니다. 생성된 모든 필드는 Streamlit에서 수정할 수 있습니다.

### FastAPI 초안 API

백엔드는 인증된 사용자에게 `POST /api/v1/ai/post-drafts`를 제공합니다. `post_type`과 자연어 설명을 받아 모델의 초안을 검증하고, 모델의 `category_code`를 DB의 `category_id`로 변환해 반환합니다. 이 요청은 게시글이나 대화 내용을 저장하지 않습니다.

지도에서 사용자가 확정한 장소·위경도와 발생 시각을 함께 보내면 해당 값이 모델의 추론값보다 우선합니다. 최종 확인된 글은 `POST /api/v1/posts/ai-assisted`로 저장할 수 있고, 이 경로는 게시글의 `creation_method`를 `AI_ASSISTED`로 기록합니다.

텍스트 채팅 화면은 `POST /api/v1/ai/post-draft-chat`에 현재까지의 사용자 입력만 전송합니다. 서버는 전체 입력을 다시 구조화한 뒤 `NEEDS_INPUT`이면 물품·장소·시간 중 한 가지를 추가 질문하고, `READY`이면 미리보기 가능한 초안을 반환합니다. 대화와 미완성 초안은 DB에 저장하지 않으며 클라이언트 메모리에서만 유지합니다. 준비된 초안은 바로 게시하거나 기존 작성 화면에 채워 사용자가 수정할 수 있습니다.

이 분기는 `app/ai/workflow.py`의 LangGraph `StateGraph`가 수행합니다. 현재 버전은 기존 API와 개인정보 보존 정책을 유지하기 위해 매 요청마다 클라이언트의 전체 사용자 입력으로 그래프를 실행하는 stateless 구조입니다. checkpointer, `thread_id` 및 `interrupt()` 기반 대화 재개는 아직 사용하지 않습니다. 이후 학교 장소 RAG와 구조화된 버튼 응답을 별도 노드로 추가한 다음, 앱 종료 후 대화 복구가 필요할 때 Human in the Loop와 checkpointer를 도입합니다.

서비스 API의 provider와 model은 클라이언트가 선택하지 않습니다. `backend/.env`의 `AI_PROVIDER`, `AI_MODEL`, `AI_TIMEOUT_SECONDS`, `OLLAMA_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL` 설정으로 서버에서 선택합니다.

### 사진 속성 추출 (아직 구현하지 않았음)

첨부한 사진 중 한 장을 선택하여 다음 정보를 구조화합니다.

- `item_name`, `category_code`
- `colors`, `materials`, `brand`, `shape`
- `keywords`, `visible_text`
- `confidence`, `warnings`

사진 속 문장은 지시가 아닌 데이터로 취급합니다. 사진으로 확인할 수 없는 소유자, 장소, 시간, 브랜드와 진품 여부는 추론하지 않도록 제한합니다.

### 측정 정보

한 건을 생성하거나 분석할 때 다음 정보를 화면과 다운로드 JSON에 포함합니다.

- provider와 model
- 전체 응답 시간
- 입력·출력 token 수
- 가격 snapshot에 등록된 OpenAI 모델의 예상 비용

## 구조

```text
ai/
├── core/
│   ├── prompt.py              # 게시글 초안 prompt
│   ├── providers.py           # Ollama/OpenAI text provider
│   ├── schemas.py             # 게시글 요청·응답 schema
│   ├── service.py             # 환경 변수 기반 provider 생성
│   ├── vision_prompt.py       # 사진 분석 prompt
│   ├── vision_providers.py    # Ollama/OpenAI vision provider
│   └── vision_schemas.py      # 사진 속성 schema
├── evals/
│   ├── build_dataset.py       # 100건 seed 데이터 생성
│   ├── build_human_review.py  # 20건 사람 평가 CSV 생성
│   ├── dataset.jsonl          # LOST 50건, FOUND 50건 정답셋
│   ├── metrics.py             # 자동 평가 지표
│   ├── pricing.json           # 날짜가 기록된 가격 snapshot
│   └── run_text_eval.py       # 모델별 text 평가 실행기
├── tests/                     # 외부 API를 호출하지 않는 단위 테스트
├── .env.example
├── requirements.txt
└── streamlit_app.py
```

## 설정

`.env.example`을 복사하여 이 디렉터리에 `.env`를 만듭니다. 실제 API key가 포함된 `.env`는 Git에서 제외됩니다.

| Name | Required | Description | Safe example |
|---|---|---|---|
| `OPENAI_API_KEY` | OpenAI 사용 시 | OpenAI API 인증 key | 빈 값 |
| `OPENAI_BASE_URL` | 아니요 | OpenAI API 기본 주소 | `https://api.openai.com/v1` |
| `OLLAMA_BASE_URL` | 아니요 | 로컬 Ollama API 주소 | `http://127.0.0.1:11434` |
| `AI_TIMEOUT_SECONDS` | 아니요 | provider 호출 제한 시간 | `120` |
| `LANGSMITH_TRACING` | 아니요 | LangGraph 실행 추적 활성화 | `false` |
| `LANGSMITH_API_KEY` | 추적 사용 시 | LangSmith API 인증 key | 빈 값 |
| `LANGSMITH_PROJECT` | 아니요 | 트레이스를 모을 LangSmith 프로젝트 | `skku-lost-and-found-local` |
| `LANGSMITH_ENDPOINT` | 아니요 | LangSmith API 주소 | `https://api.smith.langchain.com` |

모델과 provider는 Streamlit 또는 평가 명령의 인자로 선택합니다. 가격 계산은 [`evals/pricing.json`](./evals/pricing.json)에 등록된 모델만 지원하며, 평가 전에 공식 가격과 확인 날짜를 갱신해야 합니다.

## 빠른 시작

아래 명령은 이 `ai` 디렉터리를 현재 위치로 가정합니다.

### 1. Python 환경 구성

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. 환경 변수 구성

```powershell
Copy-Item .env.example .env
```

OpenAI를 사용할 경우 `.env`의 `OPENAI_API_KEY`에 개인 key를 직접 설정합니다. key를 코드, README, 테스트 또는 오류 출력에 넣지 않습니다.

### LangSmith 추적

백엔드의 LangGraph 실행은 `skku-post-draft-chat` 그래프로 표시되며 각 요청은 `post-draft-chat-turn` 실행으로 기록됩니다. 시험 환경에서 트레이스를 확인하려면 `backend/.env`에 다음 값을 설정합니다.

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=본인의_LangSmith_API_key
LANGSMITH_PROJECT=skku-lost-and-found-local
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

저장소 루트에서 백엔드 컨테이너를 다시 생성하면 변경된 환경 변수가 적용됩니다.

```powershell
docker compose up -d --force-recreate backend
docker compose logs -f backend
```

그 후 AI 채팅 요청을 한 번 보내고 LangSmith의 `skku-lost-and-found-local` 프로젝트에서 그래프 노드, 입력, 출력과 실행 시간을 확인합니다. 현재 시험 설정은 대화 원문과 모델 결과를 LangSmith로 전송하므로 실제 개인정보나 민감한 분실물 정보에는 사용하지 않습니다. 추적을 끄려면 `LANGSMITH_TRACING=false`로 변경한 뒤 백엔드 컨테이너를 다시 생성합니다.

### 3. Ollama 모델 준비

Ollama 설치 후 text 및 vision 모델을 내려받습니다.

```powershell
ollama pull llama3.2:3b
ollama pull moondream
```

Ollama가 백그라운드에서 실행되지 않는 환경에서는 다음 명령으로 서버를 시작합니다.

```powershell
ollama serve
```

### 4. Streamlit 실행

```powershell
python -m streamlit run streamlit_app.py
```

브라우저에서 provider, text model과 vision model을 선택합니다. OpenAI와 Ollama 모델명이 목록에 없다면 입력란에 직접 모델명을 지정할 수 있습니다.

## Text baseline 평가

### 데이터셋

[`evals/dataset.jsonl`](./evals/dataset.jsonl)은 템플릿으로 생성한 한국어 seed 데이터 100건입니다.

- `LOST` 50건, `FOUND` 50건
- 8개 카테고리
- 명시적·누락·모호한 시간과 장소 표현
- 각 요청에 대응하는 구조화된 정답

데이터셋을 다시 생성하려면 다음 명령을 사용합니다.

```powershell
python evals/build_dataset.py
```

이 데이터는 평가 harness 검증용 seed입니다. 공식 품질 평가 전 사람이 문장과 정답을 검수하고 실제 사용자 표현을 보강해야 합니다.

### 실행

모든 모델은 같은 dataset, prompt, schema와 temperature 0 조건을 사용합니다.

```powershell
python evals/run_text_eval.py --provider ollama --model llama3.2:3b
python evals/run_text_eval.py --provider openai --model gpt-4o
```

평가기는 warm-up 한 건을 측정에서 제외한 뒤 100건을 순차 실행합니다. 현재 중간 진행률과 checkpoint를 저장하지 않으며, 완료 후에만 `evals/results/`에 JSON과 CSV를 생성합니다. 로컬 모델은 장비에 따라 오래 걸릴 수 있습니다.

결과 디렉터리는 Git에서 제외됩니다.

### 자동 지표

- schema 유효 응답률과 오류율
- category 정확도
- item name과 location token F1
- 정답 대비 ±15분 이내의 시간 추출 정확도
- `missing_fields` F1
- p50·p95 응답 시간
- 입력·출력 token 및 측정 비용
- 성공 응답 기준 1,000건 예상 비용

### GPT-4o 실행 결과

2026-10-18에 동일한 100건으로 실행한 로컬 결과입니다.

| Metric | Result |
|---|---:|
| 성공 응답 | 79 / 100 |
| Schema 유효율 | 79% |
| Category 정확도 | 100% |
| 시간 추출 정확도 | 94.94% |
| `missing_fields` F1 | 98.31% |
| 응답 시간 p50 / p95 | 1.76초 / 2.54초 |
| 입력 / 출력 token | 44,868 / 10,085 |
| 측정 비용 | $0.21302 |
| 1,000건 예상 비용 | $2.69646 |

`item_name_f1`은 0%, `location_f1`은 11.39%로 측정됐습니다. 모델이 한국어 정답을 영어로 반환한 사례가 많아 현재 공백 기반 token F1이 의미적 동등성을 반영하지 못합니다. 이 두 수치는 모델 품질 결론에 직접 사용하지 말고 한국어·영어 정규화 또는 의미 기반 평가를 추가한 뒤 다시 해석해야 합니다. 또한 21건은 모델 출력이 Pydantic 의미 검증을 통과하지 못한 `invalid_response`입니다.

### 사람 평가표 생성

성공 결과 중 20건을 추출해 정보 충실도, 비환각성 및 수정 준비도를 1~5점으로 평가합니다.

```powershell
python evals/build_human_review.py evals/results/openai-gpt-4o.json
```

## 테스트

```powershell
python -m pytest -q
```

2026-10-18 기준 결과는 `13 passed`입니다. 테스트는 실제 Ollama 또는 OpenAI API를 호출하지 않으며 schema 검증, provider payload, 오류 처리와 평가 지표를 확인합니다.

## 개인정보와 보안

- `.env`, API key와 인증 정보는 Git에 포함하지 않습니다.
- 사용자 자연어, 위치, 이미지와 모델 원문 응답을 애플리케이션 로그에 기록하지 않습니다. 단, `LANGSMITH_TRACING=true`인 시험 환경에서는 LangGraph 입력과 출력이 LangSmith 트레이스로 전송됩니다.
- Streamlit에서 선택한 사진은 메모리에서 provider로 전송하며 파일 또는 DB에 저장하지 않습니다.
- OpenAI vision 요청에는 `store: false`를 지정합니다.
- prompt injection 문장은 시스템 지시가 아닌 사용자 데이터로 취급합니다.
- AI 출력은 확정 정보가 아니라 사용자가 검토하고 수정하는 초안입니다.

OpenAI를 선택하면 입력과 선택한 이미지가 외부 OpenAI API로 전송됩니다. Ollama를 선택하면 설정된 `OLLAMA_BASE_URL`로 전송됩니다.


## 다음 단계

1. 대표적인 open-source 및 commercial text·vision 모델을 동일 조건으로 비교합니다.
2. 이미지 해상도와 전송 detail을 변경하여 품질, latency, token과 비용의 균형점을 찾습니다.
3. 팀 회의를 통해 필수 추출 필드와 키워드를 확정하고 schema와 prompt를 조정합니다.
4. 라벨링된 이미지 데이터셋과 vision 평가 harness를 구축합니다.

## 관련 문서

- [AI 작업 지침](./AGENTS.md)
- [커밋 메시지 규칙](./docs/GIT_COMMIT.md)
- [PR 작성 지침](./docs/PR_GENERATION_GUIDE.md)
- [README 작성 규칙](./docs/README_RULES.md)
