# AI 게시글 작성 모듈

분실·습득 설명을 검토 가능한 게시글 초안으로 변환하는 백엔드 모듈입니다. 인증된 사용자의 자연어 입력에서 물품, 카테고리, 장소와 발생 시간을 구조화하고, 정보가 부족하면 LangGraph 워크플로가 후속 질문을 반환합니다. 모델 출력은 게시글로 바로 확정하지 않으며 사용자가 확인하고 수정할 수 있는 초안으로 제공합니다.

## 구현 현황

| 영역 | 상태 | 내용 |
|---|---|---|
| 자연어 초안 생성 | 구현 | 제목, 설명, 물품명, 카테고리, 장소, 시간, 키워드와 누락 필드 추출 |
| 대화형 정보 수집 | 구현 | 필수 정보가 부족하면 `item_name`, `location`, `event_time` 순서로 질문 |
| 다국어 응답 | 구현 | 요청의 `locale`에 따라 한국어와 영어 질문 및 초안 생성 |
| 장소 정규화 | 구현 | locale별 정식 명칭과 별칭 검색, 층 정보 보존, 복수 후보 확인 |
| AI provider | 구현 | 서버 설정으로 OpenAI 또는 Ollama 선택 |
| LangSmith 추적 | 선택 | 환경 변수로 LangGraph 실행 추적 활성화 |
| 이미지 속성 추출 | 내부 코드만 존재 | Vision schema와 provider는 있으나 FastAPI 엔드포인트에는 연결되지 않음 |
| Human in the Loop 재개 | 계획 | checkpointer, `thread_id`, `interrupt()`는 아직 사용하지 않음 |

## 처리 흐름

```text
인증된 요청
  → LangGraph 장소 검색
  → AI provider 초안 생성 및 Pydantic 검증
  → 카테고리 DB 조회와 장소·시간 정규화
  → 누락 정보가 있으면 NEEDS_INPUT
  → 필수 정보가 모이면 READY 초안 반환
```

대화 상태는 서버 DB에 저장하지 않습니다. 클라이언트가 이전 초안, 대기 중인 필드와 수집된 값을 다음 요청에 다시 보내는 stateless 구조입니다. 각 요청은 그래프의 `START`에서 시작하지만 조건부 edge에 따라 필요한 노드만 실행합니다.

## API

모든 엔드포인트는 `/api/v1` 아래에 등록되며 Bearer access token이 필요합니다.

### `POST /api/v1/ai/post-drafts`

한 번의 자연어 입력으로 초안을 생성합니다.

주요 요청 필드:

- `post_type`: `LOST` 또는 `FOUND`
- `locale`: `ko` 또는 `en`, 기본값 `ko`
- `natural_language`: 사용자의 분실·습득 설명
- `confirmed_location`: 사용자가 확정한 장소와 좌표
- `confirmed_event_start_at`, `confirmed_event_end_at`: 사용자가 확정한 timezone 포함 시각

확정된 장소와 시간은 모델 추론보다 우선합니다. 두 확정 시각은 함께 전달해야 하며 시작 시각이 종료 시각보다 늦을 수 없습니다.

### `POST /api/v1/ai/post-draft-chat`

필수 정보를 여러 차례에 걸쳐 수집합니다.

주요 요청 필드:

- `post_type`, `locale`
- `messages`: 최대 12개의 사용자 메시지
- `draft`: 직전 응답의 미완성 초안
- `pending_field`: 현재 답변을 기다리는 필드
- `collected_fields`: 이전 단계에서 수집한 필드별 답변

응답의 `status`는 다음 중 하나입니다.

- `NEEDS_INPUT`: `pending_field`와 `assistant_message`를 사용해 추가 정보를 요청합니다.
- `READY`: 필수 정보가 모였으며 반환된 `draft`를 사용자에게 검토시킬 수 있습니다.

현재 워크플로는 충돌한 자연어 답변을 구조화된 확정값으로 해결하지 않습니다. 전체 대화를 다시 추출한 결과가 모호하면 같은 필드를 다시 질문할 수 있습니다.

## 장소 사전

장소 사전은 [`knowledge/campus_locations.json`](./knowledge/campus_locations.json)에 있습니다.

```json
{
  "id": "samsung_library",
  "names": {
    "ko": "삼성학술정보관",
    "en": "Samsung Library"
  },
  "aliases": {
    "ko": ["디도"],
    "en": ["Samsung Library"]
  }
}
```

- `id`: 언어와 무관한 내부 식별자
- `names`: locale별 표시 명칭
- `aliases`: 사용자 입력에서 검색할 locale별 별칭

검색은 요청 locale의 표현을 우선하지만 다른 언어의 별칭도 허용합니다. 출력은 요청 locale의 정식 명칭을 사용하고 해당 명칭이 없으면 한국어로 fallback합니다. 학교 공식 건물 번호를 연동할 때는 현재 `id`를 대체하기보다 별도 코드 필드로 추가하는 것이 안전합니다.

## 디렉터리 구조

```text
backend/app/ai/
├── router.py                 # 인증된 FastAPI 엔드포인트
├── schemas.py                # API 요청·응답 schema
├── service.py                # provider, DB와 정규화 연결
├── workflow.py               # LangGraph 대화 흐름
├── core/
│   ├── prompt.py             # 텍스트 초안 system prompt
│   ├── providers.py          # OpenAI·Ollama provider
│   ├── schemas.py            # provider 독립 draft schema
│   ├── service.py            # 독립 provider 생성 helper
│   ├── vision_prompt.py
│   ├── vision_providers.py
│   └── vision_schemas.py
├── knowledge/
│   ├── campus_locations.json
│   └── location_retriever.py
└── docs/                     # Git·PR·README 작성 규칙
```

## 설정

백엔드 설정은 [`backend/.env.example`](../../.env.example)을 기준으로 저장소의 `backend/.env`에 작성합니다. 실제 API key가 포함된 `.env`는 커밋하지 않습니다.

| Name | Required | Description | Safe example |
|---|---|---|---|
| `AI_PROVIDER` | No | `openai` 또는 `ollama`; 코드 기본값은 `ollama` | `ollama` |
| `AI_MODEL` | No | 서버가 사용할 모델명; 코드 기본값은 `llama3.2:3b` | `llama3.2:3b` |
| `AI_TIMEOUT_SECONDS` | No | provider 요청 제한 시간(초) | `120` |
| `AI_REASONING_EFFORT` | No | OpenAI reasoning effort | `none` |
| `OLLAMA_BASE_URL` | Ollama 사용 시 | Ollama API 주소 | `http://127.0.0.1:11434` |
| `OPENAI_API_KEY` | OpenAI 사용 시 | OpenAI API 인증 key | placeholder 사용 |
| `OPENAI_BASE_URL` | No | OpenAI 호환 API 기본 주소 | `https://api.openai.com/v1` |
| `LANGSMITH_TRACING` | No | LangGraph 추적 활성화 | `false` |
| `LANGSMITH_API_KEY` | 추적 사용 시 | LangSmith 인증 key | placeholder 사용 |
| `LANGSMITH_PROJECT` | No | LangSmith 프로젝트명 | `skku-lost-and-found-local` |
| `LANGSMITH_ENDPOINT` | No | LangSmith API 주소 | `https://api.smith.langchain.com` |

`backend/.env.example`은 `AI_PROVIDER=openai` 예시를 제공하지만 코드 기본값은 `ollama`입니다. `.env`를 사용하지 않을 때는 코드 기본값이 적용됩니다.

## 실행

저장소 루트에서 실행합니다.

```powershell
docker compose up --build -d db backend
```

상태와 API 문서를 확인합니다.

```text
http://127.0.0.1:8000/api/v1/health
http://127.0.0.1:8000/docs
```

로그는 표준 출력에서 확인합니다.

```powershell
docker compose logs -f backend
```

환경 변수를 변경했다면 컨테이너를 다시 생성합니다.

```powershell
docker compose up -d --force-recreate backend
```

## 검증

AI 전용 자동화 테스트는 현재 작업 범위에서 제거되었습니다. 인증, 게시글, 매칭과 이메일을 포함한 나머지 백엔드 테스트는 저장소 루트에서 다음 명령으로 실행할 수 있습니다.

```powershell
docker compose run --rm backend python -m pytest -q
```

AI 전용 자동화 테스트, 평가 데이터와 Streamlit 도구는 현재 저장소에서 제거한 상태입니다.

서버 실행 후 최소 상태 확인은 다음 URL로 수행할 수 있습니다.

```text
GET http://127.0.0.1:8000/api/v1/health
```

## 주의 사항

- 모델 출력은 Pydantic으로 검증하지만 사실이 확정된 결과는 아닙니다.
- 장소 사전에 없는 모델 생성 위치는 자동 확정하지 않습니다.
- 모델이 반환한 카테고리가 DB에 없으면 `503 ai_category_unavailable`을 반환합니다.
- provider rate limit은 `429`, 그 외 provider 오류는 `503`으로 변환합니다.
- LangSmith 추적을 활성화하면 대화 입력과 결과가 외부 서비스에 전송될 수 있으므로 개인정보를 입력하지 않습니다.
- `OPENAI_API_KEY`는 클라이언트에 전달하지 않고 서버에서만 사용합니다.

## 관련 문서

- [Git 커밋 규칙](./docs/GIT_COMMIT.md)
- [PR 작성 가이드](./docs/PR_GENERATION_GUIDE.md)
- [README 작성 규칙](./docs/README_RULES.md)
