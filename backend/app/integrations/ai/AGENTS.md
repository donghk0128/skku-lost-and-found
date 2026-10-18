# AI Integration Instructions

이 파일은 `backend/app/integrations/ai`와 그 하위 파일을 작업하는 코딩 에이전트용 지침입니다.

## 적용 범위

- 기본 수정 범위는 `backend/app/integrations/ai/**`입니다.
- AI 기능의 테스트는 `backend/tests/`에 추가할 수 있습니다.
- 공용 API, 게시글 모델, migration 또는 설정 변경이 필요하면 먼저 기존 구현을 조사하고 사용자에게 영향 범위를 알립니다.
- `auth`, `users`, `posts`, `frontend` 등 다른 담당 영역은 명시적 요청 없이 수정하지 않습니다.
- 사용자의 현재 요청과 더 가까운 하위 `AGENTS.md`가 이 문서보다 우선합니다.

## 프로젝트 목표

AI 모듈은 사용자의 자연어 분실·습득 설명을 게시글 초안으로 구조화하고, 관련 가능성이 높은 반대 유형 게시물을 추천하는 기능을 담당합니다.

목표 흐름:

1. 자연어에서 물품 종류, 시간, 위치와 특징을 추출합니다.
2. 부족하거나 불확실한 정보는 추측으로 확정하지 않고 사용자 확인 대상으로 표시합니다.
3. 사용자가 검토하고 수정할 수 있는 게시글 초안을 반환합니다.
4. 구조화 정보와 설명의 의미 유사도를 결합해 후보 게시물을 순위화합니다.
5. 매칭 결과는 동일 물품의 확정 판정이 아닌 추천 후보로 제공합니다.

이미지 AI 분석, 외부 게시판 수집, 자동 반환 판정은 현재 범위에 포함하지 않습니다.

## 구현 원칙

- AI provider, prompt, 출력 schema와 application logic을 분리합니다.
- provider에 종속된 응답을 서비스 계층 밖으로 직접 노출하지 않습니다.
- 가능한 경우 Pydantic 모델로 입력과 출력을 검증합니다.
- 모델이 반환한 JSON은 신뢰하지 말고 누락 필드, 잘못된 타입과 허용되지 않은 값을 검사합니다.
- 날짜와 시간은 timezone을 포함한 값으로 처리하고, 상대 표현의 기준 시각을 명시적으로 전달합니다.
- GPS는 현재 위치일 뿐 실제 사건 위치로 단정하지 않습니다.
- 재시도는 횟수와 대상 오류를 제한하고 영구 오류를 숨기지 않습니다.
- 결정적인 전처리와 점수 계산은 모델 호출과 분리하여 단위 테스트가 가능하게 만듭니다.
- 모델명, timeout과 threshold는 한곳에서 설정하고 코드 여러 곳에 하드코딩하지 않습니다.

## 보안과 개인정보

- API key, access token, 인증 정보와 실제 `.env` 값을 코드·테스트·문서에 넣지 않습니다.
- 사용자 자연어, 위치, 이메일과 모델 원문 응답을 기본 로그에 남기지 않습니다.
- 외부 모델에는 기능 수행에 필요한 최소 데이터만 전달합니다.
- prompt injection으로 시스템 지침, 비밀값 또는 다른 사용자의 데이터를 노출하지 않도록 입력과 도구 권한을 구분합니다.
- AI 실패 시 사용자가 수동으로 게시글을 작성할 수 있는 흐름을 유지합니다.

## Python 스타일

- 기존 FastAPI, SQLAlchemy와 Pydantic 패턴을 따릅니다.
- 공개 함수와 복잡한 로직에는 Google 스타일 docstring을 사용합니다.
- 타입 힌트를 작성하고 `Any` 사용을 최소화합니다.
- 단순한 코드를 반복 설명하는 주석이나 docstring은 추가하지 않습니다.

```python
def build_draft(description: str) -> PostDraft:
    """자연어 설명에서 검토 가능한 게시글 초안을 생성합니다.

    Args:
        description: 사용자가 입력한 분실·습득 설명입니다.

    Returns:
        검증된 게시글 초안입니다.
    """
```

## 테스트

AI 테스트는 실제 외부 API에 의존하지 않도록 provider를 fake 또는 mock으로 교체합니다.

필수 검증 대상:

- 정상적인 구조화 응답
- 필수 필드 누락과 잘못된 JSON
- provider timeout, rate limit과 일시적 오류
- 모호한 시간·위치 표현
- 악의적 입력과 prompt injection 문자열
- 매칭 점수의 경계값과 안정적인 정렬
- 사용자 데이터가 로그나 오류 응답에 포함되지 않는지 여부

백엔드 전체 테스트:

```sh
docker compose run --rm backend python -m pytest -q
```

AI 테스트 파일이 추가된 뒤 특정 범위만 실행할 때:

```sh
docker compose run --rm backend python -m pytest -q tests/test_ai_*.py
```

존재하지 않는 테스트 파일이나 실행하지 않은 검증을 성공했다고 기록하지 않습니다.

## 문서와 Git 작업

- AI 모듈의 현재 상태, 입출력 계약과 실행 방법은 `README.md`에 기록합니다.
- 현재 구현과 향후 계획을 명확히 구분합니다.
- 커밋은 사용자가 요청했을 때만 수행합니다.
- PR 작성 또는 README 수정 시 다음 문서를 먼저 읽습니다.

  - 커밋 규칙: [docs/GIT_COMMIT.md](./docs/GIT_COMMIT.md)
  - PR 작성: [docs/PR_GENERATION_GUIDE.md](./docs/PR_GENERATION_GUIDE.md)
  - README 작성: [docs/README_RULES.md](./docs/README_RULES.md)

## 완료 조건

- 변경이 AI 담당 범위 안에 있거나 범위 확장 이유가 명확합니다.
- 입력과 모델 출력을 검증합니다.
- 실패 경로와 개인정보 노출 위험을 점검합니다.
- 관련 테스트를 실행하고 실제 결과를 보고합니다.
- 문서와 코드가 현재 구현 상태와 일치합니다.
