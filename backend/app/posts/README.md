# Posts

분실물(`LOST`)과 습득물(`FOUND`) 게시글을 관리하는 백엔드 모듈입니다. 현재 구현 범위는 **로그인 사용자의 게시글 등록**과 **게시글 단건 조회**입니다.

## API

| 방식 | 경로 | 인증 | 동작 |
|---|---|---|---|
| `POST` | `/api/v1/posts` | Bearer access token 필요 | 게시글 생성, 성공 시 `201` |
| `GET` | `/api/v1/posts/{post_id}` | 불필요 | 게시글 단건 조회, 성공 시 `200` |

### 게시글 생성

`POST /api/v1/posts`의 JSON 요청 본문:

```json
{
  "post_type": "LOST",
  "title": "학생회관에서 에어팟 분실",
  "description": "검은색 케이스입니다."
}
```

- `post_type`: `LOST` 또는 `FOUND`
- `title`: 공백을 제외하고 1~100자
- `description`: 공백을 제외하고 1자 이상
- 정의되지 않은 요청 필드는 허용하지 않습니다. `author_id`는 요청에서 받지 않고 인증된 사용자 ID로 설정합니다.
- 새 글의 `status`는 `OPEN`, `creation_method`는 `MANUAL`입니다.
- 성공 응답에는 `id`, `author_id`, `post_type`, `title`, `description`, `status`, `creation_method`, `created_at`, `updated_at`이 포함됩니다.

인증 실패 시 `401`, 요청 형식 오류 시 `422`를 반환합니다.

### 게시글 조회

`GET /api/v1/posts/{post_id}`는 UUID로 게시글을 조회합니다. `deleted_at`이 설정된 글은 조회 대상에서 제외합니다. 게시글이 없거나 삭제 표시가 되어 있으면 `404`를 반환합니다. 잘못된 UUID 형식은 `422`입니다.

## 코드와 DB

| 파일 | 역할 |
|---|---|
| `model.py` | `Category`, `Post` SQLAlchemy 모델과 DB 제약 |
| `schemas.py` | 생성 요청 및 응답 형식 |
| `repository.py` | 게시글 추가와 삭제되지 않은 글 조회 |
| `service.py` | 작성자 지정, 저장 트랜잭션, 조회 실패 처리 |
| `router.py` | HTTP 경로, 인증 및 DB 세션 연결 |

마이그레이션은 `backend/alembic/versions/0002_create_post_tables.py`에 있으며, `0001_create_auth_tables` 다음에 `categories`와 `posts` 테이블을 생성합니다. 모델은 `backend/alembic/env.py`에 등록되어 있습니다. 로컬 실행과 마이그레이션 적용 방법은 저장소 최상위 `README.md`를 참고하세요.

테스트는 `backend/tests/test_posts_service.py`에 있습니다. 별도 SQLite DB에서 인증된 작성자 지정, 기본값, 생성·조회, 삭제 표시된 글 제외, 요청 검증을 확인합니다.

## 아직 구현되지 않은 범위

목록·페이지네이션, 수정, 삭제 API, 카테고리 선택, 위치·발생 시각 입력, 이미지·태그, 검색·필터, 상태 변경은 후속 작업입니다. DB 모델에 있는 선택 열이 현재 생성 API에 모두 노출되는 것은 아닙니다.
