# 사진 분석 코어 구현 계획

## 1. 목표

사용자가 게시글 작성 UI의 어느 단계에서든 사진을 첨부하면 사진을 분석해 다음 게시글 필드를 생성하거나 보완한다.

- `title`
- `description`
- `item_name`
- `category_id`

색상, 재질, 브랜드, 형태, 보이는 문자와 같은 물품 특징은 `description`에 포함한다. 사진으로 확인되지 않은 필수 정보는 기존 텍스트 전용 흐름과 같은 질문을 통해 수집한다.

이 문서의 우선 구현 범위는 `backend/app/ai` 내부의 schema, prompt, provider, 병합 서비스, workflow와 단위 테스트다. 공개 API와 프런트엔드 변경은 담당자 승인 후 별도 연동 단계에서 진행한다.

## 2. 현재 상태

| 영역 | 상태 | 내용 |
|---|---|---|
| 단일 사진 schema | 일부 구현 | `ImageAttributes`가 물품명, 카테고리 코드, 색상, 재질, 브랜드, 형태, 문자 등을 표현한다. |
| Vision provider | 일부 구현 | OpenAI와 Ollama가 단일 JPEG, PNG, WebP 이미지를 분석한다. |
| 이미지 검증 | 일부 구현 | MIME 형식만 검사하며 크기, 파일 시그니처와 최대 장수 검증은 없다. |
| 다중 사진 병합 | 미구현 | 여러 사진의 분석 결과를 하나의 물품 특징으로 합치는 로직이 없다. |
| 게시글 필드 생성 | 미구현 | Vision 결과에서 `title`, `description`, `item_name`, `category_id`를 만드는 계층이 없다. |
| 대화 workflow 연결 | 미구현 | 현재 LangGraph workflow는 텍스트만 처리한다. |
| AI 전용 테스트 | 미구현 | Vision provider, 병합 및 사진 포함 workflow 테스트가 없다. |

관련 파일은 다음과 같다.

- `core/vision_schemas.py`: 단일 사진 분석 schema
- `core/vision_prompt.py`: Vision 공통 prompt
- `core/vision_providers.py`: OpenAI·Ollama Vision adapter
- `core/schemas.py`: 텍스트 기반 게시글 초안 schema
- `service.py`: 게시글 초안 생성과 카테고리 DB 조회
- `workflow.py`: 부족한 필드를 수집하는 텍스트 기반 LangGraph workflow
- `schemas.py`: 현재 공개 AI 요청·응답 schema
- `../posts/schemas.py`: 최종 게시글 필드 계약

## 3. 목표 처리 흐름

```text
START
  → analyze_images
      → 업로드 이미지 검증
      → 각 사진 독립 분석
      → 여러 사진의 관찰값 병합
      → 안전한 image_context 생성
  → retrieve
  → route_start
      ├─ 새 사진 있음 → extract
      ├─ 이전 필드 있음 → collect
      └─ 최초 텍스트 요청 → extract
  → request 또는 draft
  → END
```

사진이 대화 중 언제 추가되더라도 현재 `pending_field`와 관계없이 `analyze_images`를 먼저 실행한다. 사진에서 얻은 구조화 속성은 안전한 `image_context`로 변환하고 기존 텍스트 provider가 `title`, `description`, `item_name`, `category_code`를 생성하거나 보완한다. Application service는 기존 경로를 사용해 `category_code`를 `category_id`로 변환한다.

기존 `retrieve`, `extract`, `collect`, `request`, `draft` node는 재사용한다. 새 사진이 들어온 요청을 기존 `collect`로 보내면 `"사진을 첨부했어요"` 같은 메시지를 현재 질문의 답으로 잘못 처리할 수 있으므로 `route_start`만 새 사진을 우선 `extract`로 보내도록 보완한다.

## 4. 필드 생성 및 병합 정책

### 4.1 `item_name`

- 사진에서 충분히 식별되면 기존 AI 추출값을 갱신한다.
- 여러 사진의 물품 종류가 충돌하면 임의로 확정하지 않고 경고를 남긴다.
- 사진으로 식별하지 못하면 기존 텍스트 값 또는 사용자 답변을 사용한다.

### 4.2 `category_id`

- Vision provider는 DB ID 대신 안정적인 `category_code`를 반환한다.
- Application service가 기존 `PostRepository.get_category_by_code()`를 이용해 `category_id`로 변환한다.
- 사진 간 카테고리가 충돌하면 기존 값을 유지하거나 `OTHER`로 처리하고 경고를 남긴다.
- DB에 해당 코드가 없으면 기존 `ai_category_unavailable` 오류를 사용한다.

### 4.3 `description`

- 물품명, 색상, 브랜드, 재질, 형태와 보이는 문자를 자연스러운 문장으로 결합한다.
- 브랜드는 실제 로고나 문자가 명확히 보일 때만 포함한다.
- 장소, 시간, 소유 관계와 진품 여부는 사진만으로 추측하지 않는다.

### 4.4 `title`

- 확정된 `item_name`과 대표적인 시각 속성으로 생성한다.
- `PostCreateRequest.title`의 100자 제한을 지킨다.
- 예: `검은색 삼성 무선 이어폰`

### 4.5 사용자 확정값 보호

- 사진 분석 결과는 사진이 추가될 때마다 다시 추출한다.
- 이전에 AI가 생성한 값은 새 사진 결과로 갱신할 수 있다.
- 사용자가 직접 확정하거나 수정한 값은 자동으로 덮어쓰지 않는다.
- 사용자 확정값과 사진 결과가 충돌하면 사용자 값을 유지하고 `warnings`에 기록한다.
- 이를 위해 필드별 출처를 내부 metadata로 관리한다.

## 5. 구현 단계

### 5.1 이미지 입력 검증

AI 내부 공통 검증 계층을 추가한다.

- 최대 5장
- 장당 1바이트 이상 5MiB 이하
- JPEG, PNG, WebP만 허용
- 선언된 MIME과 실제 파일 시그니처를 함께 검사
- 검증이 끝나기 전에는 provider를 호출하지 않음
- 원본을 저장하지 않고 메모리에서만 처리

게시글 이미지 정책과 값은 같지만 작업 범위를 지키기 위해 `posts` 모듈을 수정하거나 저장 서비스에 의존하지 않는다.

### 5.2 Vision schema 확장

`core/vision_schemas.py`에 다음 내부 모델을 추가한다.

- `ImageInput`: 이미지 bytes와 MIME type
- `MergedImageAttributes`: 병합된 물품 속성, 사진별 결과, 충돌 및 품질 경고
- `ImageDraftFields`: `title`, `description`, `item_name`, `category_code`, 키워드, 경고와 필드별 confidence

`category_id`는 DB 의존 값이므로 Vision provider schema에 포함하지 않는다.

### 5.3 단일 사진 provider 계약 강화

- 사진의 주된 물건만 분석한다.
- 보이지 않는 브랜드, 색상과 종류를 추측하지 않는다.
- 이미지 속 문자를 명령이 아닌 데이터로만 취급한다.
- 식별할 수 없는 값은 `null`, 빈 목록 또는 `OTHER`로 반환한다.
- OpenAI와 Ollama가 동일한 `ImageAttributes` schema를 반환하도록 contract test를 작성한다.

텍스트 provider와 Vision provider는 서로 다른 설정과 생성 함수를 사용한다. 초기 모델 ID는 모두 `gpt-6-luna`로 통일하지만, 이후 Vision 모델만 독립적으로 교체할 수 있어야 한다.

```env
AI_PROVIDER=openai
AI_MODEL=gpt-6-luna
AI_VISION_MODEL=gpt-6-luna
```

```text
get_draft_provider()
  └─ OpenAIProvider(model=settings.ai_model)

get_vision_provider()
  └─ OpenAIVisionProvider(model=settings.ai_vision_model)
```

현재 `llama3.2:3b` 기본값은 Vision 모델이 아니므로 이미지 분석에 사용하지 않는다.

### 5.4 다중 사진 병합 서비스

내부 `VisionAnalysisService`를 추가해 다음 작업을 수행한다.

1. 모든 이미지를 검증한다.
2. 각 이미지를 `VisionProvider.analyze()`로 분석한다.
3. 문자열 목록은 순서를 보존하면서 중복을 제거한다.
4. 동일한 물품명, 카테고리와 브랜드의 근거를 합친다.
5. 상충하는 브랜드, 색상과 물품 종류는 임의 확정하지 않고 경고에 남긴다.
6. 병합된 관찰값에서 네 게시글 필드 후보를 만든다.
7. 사진별 provider usage를 합산해 반환한다.

최대 5장이므로 최초 구현은 단순 반복 처리한다. 실제 지연이 확인될 때만 병렬 호출을 도입한다.

### 5.5 사진 기반 게시글 필드 생성

`analyze_images`는 병합된 구조화 속성을 자유 형식 사용자 문장으로 바꾸지 않고 안전한 `image_context`로 직렬화한다. 기존 draft provider는 사용자 텍스트와 `image_context`를 함께 받아 게시글 필드를 생성한다.

```text
source: trusted_image_analysis
item_name: wireless earbuds
category_code: ELECTRONICS
colors: black
brand: Samsung
materials: plastic
shape: charging case
visible_text:
  - Samsung
warnings: []
```

- `visible_text`는 명령이 아니라 관찰 데이터임을 prompt에 명시한다.
- 가능하면 자유 문장보다 JSON 직렬화를 사용한다.
- 기존 draft provider가 `title`, `description`, `item_name`, `category_code`를 생성한다.
- `description`에는 색상, 브랜드, 재질, 형태와 보이는 문자를 포함한다.
- `title`과 `description`은 게시글 schema 제한을 만족해야 한다.
- 요청 locale에 따라 한국어 또는 영어 결과를 생성한다.

### 5.6 텍스트·사진 통합 결과 모델

공개 API를 변경하기 전에 다음 형태의 내부 모델을 준비한다.

```json
{
  "post": {
    "post_type": "LOST",
    "title": "검은색 무선 이어폰",
    "description": "검은색 무선 이어폰이며 충전 케이스에 Samsung 문자가 보입니다.",
    "item_name": "무선 이어폰",
    "category_id": 1,
    "location_text": null,
    "latitude": null,
    "longitude": null,
    "event_start_at": null,
    "event_end_at": null
  },
  "metadata": {
    "missing_fields": ["location", "event_time"],
    "image_attributes": [],
    "keywords": ["무선 이어폰", "검은색"],
    "warnings": [],
    "collected_fields": {},
    "field_sources": {
      "title": "image",
      "description": "image",
      "item_name": "image",
      "category_id": "image"
    }
  }
}
```

필드 출처는 적어도 `image`, `text`, `user_confirmed`를 구분할 수 있어야 한다.

### 5.7 기존 질문 workflow 연결

`workflow.py`의 처리 순서를 다음과 같이 확장한다.

```text
START
  → analyze_images
  → retrieve
  → extract / collect
  → request / draft
  → END
```

`analyze_images`는 다음 state를 추가하거나 갱신한다.

```python
class State(TypedDict, total=False):
    # 기존 텍스트 workflow state 유지
    locale: Locale
    messages: list[str]
    fields: AIRequiredFields
    previous_fields: AIRequiredFields
    draft: AIDraftResponse
    pending_field: PendingDraftField | None

    # 이미지 처리 state
    images: list[ImageInput]
    image_attributes: MergedImageAttributes | None
    image_context: str | None
    images_analyzed: bool
```

기존 node의 재사용 범위는 다음과 같다.

| 기존 요소 | 재사용 | 필요한 변경 |
|---|---:|---|
| `retrieve` | 예 | 위치 검색에는 사용자 메시지만 사용한다. |
| `extract` | 예 | provider 입력을 사용자 텍스트와 `image_context`로 조립한다. |
| `collect` | 예 | 새 사진 요청은 라우팅 단계에서 `collect`를 건너뛴다. |
| `request` | 예 | 기존 질문과 순서를 그대로 사용한다. |
| `draft` | 예 | provider 입력을 사용자 텍스트와 `image_context`로 조립한다. |
| `_pending` | 예 | `item_name`, `location`, `event_time` 순서를 유지한다. |
| `route_start` | 일부 | 새 사진이 있으면 `extract`를 우선 선택한다. |

권장 라우팅은 다음과 같다.

```python
def route_start(state: State) -> Literal["collect", "extract", "draft"]:
    if state.get("images_analyzed"):
        return "extract"

    previous = state.get("previous_fields")
    if previous and _pending(previous) is None:
        return "draft"

    return "collect" if previous else "extract"
```

이미지 관찰 정보는 사용자 메시지 배열에 직접 삽입하지 않는다. Provider 호출 직전에 별도 context로 결합한다.

```python
def _conversation(state: State) -> str:
    user_text = _text(state["messages"])
    image_context = state.get("image_context")
    if not image_context:
        return user_text
    return f"{user_text}\n\n[IMAGE_OBSERVATIONS]\n{image_context}"
```

동작 기준은 다음과 같다.

- 첫 요청에 사진만 첨부해도 분석을 시작한다.
- `item_name` 질문 중 사진을 첨부하면 사진에서 값을 채우고 다음 부족한 필드로 이동한다.
- 장소나 시간 질문 중 사진을 첨부해도 네 게시글 필드는 다시 분석한다.
- 사진에서 장소와 시간을 추측하지 않는다.
- 사진으로 `item_name`을 얻지 못하면 기존 질문을 그대로 사용한다.
- 사진이 없는 요청은 현재 텍스트 전용 흐름과 동일하게 동작한다.
- 사진 분석이 실패해도 기존 텍스트 대화 상태를 잃지 않고 경고와 재시도 가능 상태를 반환한다.
- `retrieve`에는 `image_context`를 전달하지 않아 사진 배경을 분실 장소로 오인하지 않게 한다.
- 사용자가 첨부한 사진은 게시글 작성 시에도 첨부되도록 연동한다.

### 5.8 모델 설정 및 선택

텍스트 초안 모델과 Vision 모델은 설정을 분리하되 최초 구현에서는 둘 다 `gpt-6-luna`를 사용한다.

| 용도 | 설정 | 초기값 |
|---|---|---|
| 텍스트 필드 추출 및 draft 생성 | `AI_MODEL` | `gpt-6-luna` |
| 이미지 속성 추출 | `AI_VISION_MODEL` | `gpt-6-luna` |

`gpt-6-luna`는 이미지 입력과 Structured Outputs를 지원하므로 현재 `ImageAttributes` JSON schema에 사용할 수 있다. 두 설정을 지금부터 분리해 두면 실제 평가 후 Vision만 다른 모델로 교체해도 텍스트 workflow와 provider 설정을 변경할 필요가 없다.

모델 평가는 동일한 gold dataset으로 다음 지표를 측정한다.

- `item_name` 정확도
- `category_code` 정확도
- 색상, 재질과 브랜드 precision
- 한글·영문 OCR 정확도
- 존재하지 않는 브랜드를 생성하는 비율
- JSON schema 준수율
- 사진당 응답 시간과 비용
- 상충하는 다중 사진의 병합 정확도

최소 50개 물품과 물품당 1~3장의 사진으로 평가하고, 전체 설명의 자연스러움보다 `item_name`, `category_code` 정확도와 브랜드 hallucination 비율에 높은 가중치를 둔다.

## 6. 테스트 계획

Provider를 실제 호출하지 않는 fake provider 기반 단위 테스트를 우선 작성한다.

### 6.1 입력 검증

- 정상 JPEG, PNG, WebP 허용
- MIME 위장 및 잘못된 파일 시그니처 거부
- 빈 파일 거부
- 장당 5MiB 초과 거부
- 6장 이상 거부
- 원본 이미지가 저장되지 않는지 확인

### 6.2 분석 및 병합

- 단일 사진에서 네 게시글 필드 생성
- 여러 사진의 속성 중복 제거 및 병합
- 상충하는 브랜드, 색상, 카테고리와 물품 종류 경고
- 이미지 속 prompt injection 문장을 데이터로만 처리
- locale별 title과 description 생성

### 6.3 Workflow

- 새 사진이 기존 AI 추출 필드를 재계산함
- 사용자 확정 필드는 유지하고 충돌 경고를 생성함
- 사진에서 누락된 `item_name`을 기존 질문으로 보완함
- 장소와 시간은 기존 질문 순서를 유지함
- 대화 어느 단계에서 사진을 첨부해도 같은 분석 경로가 실행됨
- 사진 없는 요청의 기존 동작 회귀 테스트
- 사진 분석 실패 후에도 텍스트 대화 상태가 유지됨
- 새 사진이 있는 요청은 기존 `collect`가 아니라 `extract`로 이동함
- 사진이 없는 요청은 기존 `route_start` 동작을 유지함
- 위치 검색에는 `image_context`가 포함되지 않음

### 6.4 Provider contract

- OpenAI와 Ollama가 같은 `ImageAttributes` schema를 만족함
- refusal, timeout, rate limit, 잘못된 응답을 기존 `ProviderError`로 변환함

## 7. API 및 프런트엔드 연동 단계

다음 작업은 AI 코어 구현과 분리하며 담당자 승인 후 진행한다.

- multipart AI chat endpoint 추가 또는 기존 endpoint 확장
- 이미지 파일과 stateless 대화 상태 전달 방식 확정
- 공개 응답을 `post + metadata` 구조로 전환
- 인증, 전체 요청 크기 제한과 오류 매핑
- 프런트에서 어느 단계에서든 사진 추가, 삭제와 재분석
- 게시 완료 후 기존 게시글 이미지 API로 원본 업로드

권장 요청 형태는 기존 chat payload와 새 이미지를 한 요청에서 받는 multipart 방식이다.

```text
payload: 기존 AIChatRequest JSON
images: 새로 추가된 이미지, 최대 5장
```

현재 대화는 stateless 구조이므로 다음 요청에서도 이미지 분석 상태가 필요하다. AI 서버에 원본을 저장하지 않기 위해 프런트가 현재 첨부 사진을 필요할 때 다시 전송하거나, 서버가 반환한 검증된 `image_attributes`를 다음 요청에 전달해야 한다. 새 사진이 들어오면 이전 이미지 기반 AI 필드는 새 분석 결과로 다시 계산한다.

## 8. 권장 작업 순서

1. `AI_MODEL`과 `AI_VISION_MODEL` 설정을 분리하고 둘 다 `gpt-6-luna`로 설정한다.
2. 이미지 검증과 Vision schema를 보완한다.
3. 단일 provider contract test를 작성한다.
4. 다중 사진 병합 서비스와 안전한 `image_context` 생성을 구현한다.
5. `analyze_images` node를 `START` 직후에 추가한다.
6. 새 사진 요청이 `extract`로 이동하도록 `route_start`를 보완한다.
7. 기존 `extract`와 `draft`가 사용자 텍스트와 `image_context`를 함께 사용하게 한다.
8. 기존 경로로 `category_code`를 `category_id`로 변환한다.
9. 텍스트·사진 병합과 필드 출처 관리를 구현한다.
10. fake provider 기반 단위 및 회귀 테스트를 수행한다.
11. README에 구현 상태를 반영하고 백엔드 연동 계약서를 작성한다.
12. API 변경 승인 후 router와 프런트엔드를 연결한다.

## 9. 완료 기준

- 최대 5장의 유효한 JPEG, PNG, WebP 사진을 메모리에서 분석한다.
- 여러 사진의 속성을 하나의 물품 정보로 병합한다.
- 사진으로 `title`, `description`, `item_name`, `category_id`를 생성하거나 보완한다.
- 새 사진이 추가되면 기존 AI 추출 필드도 다시 분석한다.
- 사용자 확정값은 보존하고 사진과의 충돌을 경고한다.
- 사진으로 얻지 못한 필수 필드는 기존 텍스트 질문 흐름으로 수집한다.
- 사진 없는 기존 흐름이 동일하게 동작한다.
- 사진 원본을 AI 모듈에 저장하지 않는다.
- OpenAI와 Ollama가 같은 내부 schema를 만족한다.
- 텍스트 모델과 Vision 모델 설정이 분리되고 초기값은 모두 `gpt-6-luna`다.
- `analyze_images`를 제외한 기존 텍스트 workflow node를 재사용한다.
- 공개 API는 승인 전까지 변경하지 않는다.

## 10. 구현 원칙

- 기존 Pydantic schema, provider, LangGraph와 카테고리 조회 경로를 재사용한다.
- 새 framework, 저장소 또는 speculative abstraction을 추가하지 않는다.
- 이미지 검증, 사용자 확정값 보호와 오류 처리는 단순화를 이유로 생략하지 않는다.
- 실제 성능 문제가 확인되기 전에는 이미지 병렬 처리와 별도 cache를 도입하지 않는다.
