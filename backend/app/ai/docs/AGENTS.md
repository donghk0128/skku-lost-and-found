# AI Engineer 작업 범위 분리 계획

## 요약

`backend/app/ai` 내부 구현, 장소 데이터, 프롬프트, provider, 내부 workflow와 단위 테스트는 먼저 진행한다. 공용 API 계약, 게시글 DB/API, 프런트 화면은 담당자 승인 전까지 변경하지 않는다.

따라서 이번 작업은 AI 기능을 독립적으로 완성하고 검증한 뒤 연결에 필요한 계약서를 전달하는 단계까지 진행한다. 승인 전에는 기존 API 응답과 게시글 동작을 깨지 않는다.

## 지금 가능한 AI 작업

### 1. 사진 분석 코어 완성

- 기존 `vision_schemas`, `vision_prompt`, `vision_providers`를 AI 내부 기능으로 완성한다.
- 물품명, 카테고리, 색상, 재질, 브랜드, 형태, 보이는 문자, 키워드, 신뢰도와 경고를 구조화한다.
- 여러 사진의 분석 결과를 하나의 물품 특징으로 병합하는 내부 서비스를 추가한다.
- 최대 5장, JPEG/PNG/WebP, 장당 5MiB라는 연결 예정 정책을 내부 검증 상수와 테스트에 반영한다.
- 상충하는 브랜드·색상·물품 종류는 임의로 확정하지 않고 경고에 남긴다.
- 사진 속 문자는 데이터로만 취급하고 prompt injection 명령으로 처리하지 않는다.
- 사진 원본을 저장하지 않는 순수 in-memory 분석 인터페이스로 만든다.

### 2. AI 내부 통합 모델 준비

공용 API를 바꾸지 않고 다음 내부 결과 모델을 준비한다.

```json
{
  "post": {
    "post_type": "LOST",
    "title": "...",
    "description": "...",
    "item_name": "...",
    "category_id": 1,
    "location_text": null,
    "latitude": null,
    "longitude": null,
    "event_start_at": null,
    "event_end_at": null
  },
  "metadata": {
    "missing_fields": [],
    "location_candidates": [],
    "selected_location_ids": [],
    "image_attributes": [],
    "keywords": [],
    "warnings": [],
    "time_precision": null,
    "collected_fields": {}
  }
}
```

- `post`는 직접 작성 게시글과 같은 필드명과 타입을 사용한다.
- AI 진행 상태, 장소 후보, 사진 특징과 경고는 `metadata`로 분리한다.
- 기존 `/ai/post-drafts`, `/ai/post-draft-chat` 응답은 승인 전까지 변경하지 않는다.
- 필요한 경우에만 내부 결과를 기존 `AIDraftResponse`로 변환하는 호환 어댑터만 준비한다.

### 4. AI 검증과 문서화

- provider를 호출하지 않는 fake provider 기반 단위 테스트를 우선 작성한다.
- OpenAI/Ollama가 동일한 내부 schema를 만족하는지 contract test를 추가한다.
- 장소 단일·복수 검출, 이미지 병합, 한·영 출력, 텍스트와 이미지의 상충 정보를 검증한다.
- `backend/app/ai/README.md`에는 현재 구현 상태와 API 미연결 상태를 명확히 구분한다.
- 백엔드·프런트 담당자에게 전달할 요청/응답 예시와 오류 코드를 별도 연동 명세로 작성한다.

## 승인 후 진행할 백엔드 연동 작업

다음 작업은 백엔드 담당자 승인 또는 공동 작업이 필요하다.

- AI 이미지 분석 엔드포인트 또는 multipart AI chat 엔드포인트 추가
- `AIChatRequest/Response`를 `post + metadata` 구조로 변경
- `confirmed_locations[]`와 대표 장소를 받을 공용 API 계약 추가
- 인증, 요청 크기 제한, MIME 및 파일 시그니처 검증 연결
- 이미지 분석 provider dependency injection과 오류 매핑
- AI 대화 중 누적된 `image_attributes`를 다음 요청에서 안전하게 전달하는 방식 확정
- API 변경에 따른 OpenAPI 문서와 통합 테스트 수정

승인 전에는 새 API를 라우터에 등록하거나 기존 응답 필드를 변경하지 않는다.

## 별도 담당자에게 미룰 작업

### 게시글 백엔드

실제 복수 장소 저장은 AI 모듈만으로 해결할 수 없다. 백엔드 담당자에게 다음 작업을 요청한다.

- `post_locations` 관계 테이블 도입
- 생성·수정·조회 API에 `locations[]` 추가
- 대표 장소 표시 방식 결정
- 기존 단일 장소 데이터를 대표 장소 한 건으로 마이그레이션
- 장소별 게시글 검색과 임베딩 반영
- 기존 `location_text/latitude/longitude` 호환 기간 결정

이 작업 전에는 AI가 복수 장소 후보를 만들 수만 있고, 게시글에는 대표 장소 하나만 저장할 수 있다.

### 프런트엔드

프런트 담당자에게 다음 작업을 요청한다.

- 장소 후보 복수 선택 버튼과 대표 장소 선택 UI
- 대화 어느 시점에서든 사진을 전송하는 UI
- 최대 5장 선택·삭제·재분석 상태 관리
- `post`와 `metadata` 분리 응답 적용
- 분석 중, 실패, 재시도와 AI 경고 표시
- 사진 원본을 게시 완료까지 보관하고 기존 게시글 이미지 API로 업로드
- AI가 초안을 갱신했을 때 이전 사용자 입력으로 되돌리는 기능
- 한·영 번역 키 추가

## 권장 작업 순서

1. 단일 사진 vision provider와 schema를 검증한다.
2. 여러 사진 결과 병합 로직을 구현한다.
3. 텍스트·사진 통합 내부 workflow를 구현한다.
4. 내부 `post + metadata` 모델과 기존 응답 호환 어댑터를 만든다.
5. AI 전용 테스트와 README를 갱신한다.
6. 백엔드 담당자에게 API 및 다중 장소 저장 변경안을 전달한다.
7. 승인을 받은 뒤 AI API 연결을 공동 구현한다.
8. API가 확정되면 프런트 담당자가 다중 선택과 사진 전송 UI를 연결한다.
9. 세 영역을 합친 영·한 E2E 테스트를 수행한다.

## 완료 기준

- 공식 장소 사전이 양 캠퍼스와 한·영 명칭을 포함한다.
- 하나의 문장에서 여러 장소를 안정적으로 검출한다.
- 최대 5장의 사진에서 특징을 추출하고 병합한다.
- AI 내부 결과가 `post + metadata`로 분리된다.
- 기존 공개 API와 게시글 동작은 승인 전까지 유지된다.

## 가정

- `backend/app/ai` 내부 작업은 AI engineer의 작업 범위다.
- 게시글 DB, 게시글 API, 프런트 소스와 기존 공개 API 계약은 다른 담당자의 승인 대상이다.
- 승인 전에는 장소와 사진 기능을 내부적으로 완성하되 실제 사용자 화면에는 노출하지 않는다.
