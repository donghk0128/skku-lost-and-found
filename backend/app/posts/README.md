# Posts

분실물(`LOST`)과 습득물(`FOUND`) 게시글을 관리하는 백엔드 모듈입니다. 게시글 등록·조회·수정·삭제와 사진 업로드·조회 API를 제공합니다.

## API

| 방식 | 경로 | 인증 | 동작 |
|---|---|---|---|
| `POST` | `/api/v1/posts` | Bearer access token 필요 | 게시글 생성, 성공 시 `201` |
| `GET` | `/api/v1/posts` | 불필요 | 게시글 목록 조회, 성공 시 `200` |
| `GET` | `/api/v1/categories` | 불필요 | 카테고리 목록 조회, 성공 시 `200` |
| `GET` | `/api/v1/posts/{post_id}` | 불필요 | 게시글 단건 조회, 성공 시 `200` |
| `PATCH` | `/api/v1/posts/{post_id}` | Bearer access token 필요 | 작성자만 게시글 정보 수정, 성공 시 `200` |
| `PATCH` | `/api/v1/posts/{post_id}/status` | Bearer access token 필요 | 작성자만 완료 표시, 성공 시 `200` |
| `DELETE` | `/api/v1/posts/{post_id}` | Bearer access token 필요 | 작성자만 삭제 표시, 성공 시 `204` |
| `POST` | `/api/v1/posts/{post_id}/images` | Bearer access token 필요 | 작성자가 사진 한 장 업로드, 성공 시 `201` |
| `GET` | `/api/v1/posts/{post_id}/images` | 불필요 | 게시글의 사진 목록 조회 |
| `GET` | `/api/v1/posts/{post_id}/images/{image_id}/content` | 불필요 | 사진 파일 읽기 |

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
- 선택 사항인 `item_name`(물건 이름)과 `location_text`(장소 설명)은 각각 최대 100자, 255자입니다.
- `category_id`는 `GET /api/v1/categories`로 조회한 카테고리의 ID입니다. 존재하지 않는 ID는 `422`입니다.
- 지도 좌표 `latitude`(`-90`~`90`)와 `longitude`(`-180`~`180`)는 함께 입력합니다. 소수점 아래 최대 6자리입니다.
- `event_start_at`, `event_end_at`은 발생 시각 범위입니다. 두 값을 함께 입력하고, 시간대가 포함된 ISO 8601 형식(예: `2026-10-15T09:00:00+09:00`)을 사용합니다. 시작 시각은 끝 시각보다 늦을 수 없습니다.
- 정의되지 않은 요청 필드는 허용하지 않습니다. `author_id`는 요청에서 받지 않고 인증된 사용자 ID로 설정합니다.
- 새 글의 `status`는 `OPEN`, `creation_method`는 `MANUAL`입니다.
- 성공 응답에는 `id`, `author_id`, 입력한 게시글 정보, `status`, `creation_method`, `created_at`, `updated_at`이 포함됩니다. 좌표는 JSON 숫자로 반환합니다.

인증 실패 시 `401`, 요청 형식 오류 시 `422`를 반환합니다.

### 게시글 목록

`GET /api/v1/posts`는 삭제 표시된 글을 제외하고 최신순으로 반환합니다. 같은 시각에 작성된 글은 ID 역순으로 정렬합니다.

- `post_type`: 선택 사항. `LOST` 또는 `FOUND`로 목록을 좁힙니다.
- `category_id`: 선택 사항. 해당 카테고리의 게시글만 조회합니다.
- `status`: 선택 사항. `OPEN` 또는 `COMPLETED`로 목록을 좁힙니다. 생략하면 두 상태 모두 조회합니다.
- `q`: 선택 사항. 제목·설명·물건 이름에서 검색합니다. 공백으로 나눈 검색어는 모두 포함되어야 하며, 각 검색어는 글 안의 공백 차이를 무시합니다. 예를 들어 `무선이어폰`은 `무선 이어폰`도 찾습니다. 영문 대소문자는 구분하지 않습니다. 최대 100자이며 공백만 입력하면 `422`입니다.
- `limit`: 한 번에 받을 글 수. 기본값 20, 범위 1~100.
- `offset`: 앞에서 건너뛸 글 수. 기본값 0.
- 응답의 `items`는 현재 페이지의 글, `total`은 필터에 맞는 전체 글 수입니다. `limit`과 `offset`도 응답에 포함됩니다.
- 잘못된 쿼리 값은 `422`입니다.

### 게시글 단건 조회

`GET /api/v1/posts/{post_id}`는 UUID로 게시글을 조회합니다. `deleted_at`이 설정된 글은 조회 대상에서 제외합니다. 게시글이 없거나 삭제 표시가 되어 있으면 `404`를 반환합니다. 잘못된 UUID 형식은 `422`입니다.

### 게시글 수정·삭제

`PATCH /api/v1/posts/{post_id}`는 제목·설명·물건 이름·카테고리·장소·좌표·발생 시각 중 하나 이상을 받습니다. 입력하지 않은 필드는 유지합니다. 제목·설명에는 `null`을 쓸 수 없고, 선택 필드에는 `null`을 보내 값을 비울 수 있습니다. 좌표와 발생 시각은 각각 쌍으로 수정하거나 비워야 합니다. 빈 본문, 공백뿐인 문자열, 잘못된 범위·시각, 정의되지 않은 필드와 존재하지 않는 카테고리는 `422`입니다. `post_type`과 작성자 ID는 수정할 수 없습니다.

`DELETE /api/v1/posts/{post_id}`는 DB 행을 지우지 않고 `deleted_at`을 기록합니다. 이후 목록과 단건 조회에서는 보이지 않습니다. 두 요청 모두 로그인이 필요하며, 다른 사람의 글은 `403`, 없거나 이미 삭제된 글은 `404`입니다.

`PATCH /api/v1/posts/{post_id}/status`의 요청 본문은 `{"status": "COMPLETED"}`입니다. 작성자만 열린 글을 완료 표시할 수 있고, 같은 요청을 다시 보내도 `200`과 현재 글을 반환합니다. 현재는 `OPEN`으로 되돌리는 요청을 지원하지 않습니다. `COMPLETED`는 작성자가 분실물을 찾았거나 습득물을 돌려주는 등 이 글의 문제가 해결됐다고 표시한 상태입니다. 완료된 글은 목록·단건 조회에서 계속 보이며, `status` 필터로 구분할 수 있습니다. 인증이 없으면 `401`, 다른 작성자의 글이면 `403`, 삭제된 글이면 `404`, 잘못된 요청 본문은 `422`입니다.

## 코드와 DB

| 파일 | 역할 |
|---|---|
| `model.py` | `Category`, `Post`, `PostImage` SQLAlchemy 모델과 DB 제약 |
| `storage.py` | 사진 파일을 로컬 Docker 볼륨에 저장·조회 |
| `schemas.py` | 생성·수정 요청 및 단건·목록 응답 형식 |
| `repository.py` | 게시글 추가·수정·삭제 표시와 조회에 필요한 DB 작업 |
| `service.py` | 작성자 확인, 저장 트랜잭션, 조회 실패 처리 |
| `router.py` | HTTP 경로, 인증 및 DB 세션 연결 |

`backend/alembic/versions/0002_create_post_tables.py`가 `categories`와 `posts` 테이블을 만들고, `0003_seed_post_categories.py`가 임시 카테고리 항목을 넣습니다. `0004_create_post_images.py`는 사진 메타데이터 테이블을 만듭니다. 모델은 `backend/alembic/env.py`에 등록되어 있습니다. 로컬 실행과 마이그레이션 적용 방법은 저장소 최상위 `README.md`를 참고하세요.

게시글 API 테스트는 `backend/tests/test_posts_service.py`와 `backend/tests/test_posts_api.py`에 있습니다. 별도 SQLite DB와 가짜 저장소에서 작성자 지정, 생성·조회, 목록 필터·페이지네이션, 작성자만 수정·삭제·사진 업로드, 선택 필드 검증, 삭제된 글 제외, HTTP 응답 코드를 확인합니다. `backend/tests/test_post_image_storage.py`는 로컬 파일 저장·조회와 잘못된 경로 차단을 확인합니다.

## 카테고리와 후속 작업

카테고리 테이블은 `0002_create_post_tables.py`에서 생성되고, `0003_seed_post_categories.py`가 임시 항목을 넣습니다. `code`는 식별자이고 `name`은 화면 표시 이름입니다. 카테고리는 생성·수정 요청에서 선택하거나 `null`로 비울 수 있습니다.

사진은 `multipart/form-data`의 `file` 필드로 한 장씩 업로드하며, 게시글당 최대 5장입니다. JPEG·PNG·WebP 형식, 파일당 최대 5MiB입니다. `post_images` 테이블에는 게시글 ID, 저장 경로, 파일 형식과 순서를 저장합니다. 사진 파일 자체는 Compose의 `post_images_data` 볼륨에 있습니다. 사진 목록 응답의 `content_url`을 요청하면 백엔드가 파일을 읽어 반환합니다. 삭제 표시된 게시글의 사진은 API에서 보이지 않습니다.

태그와 사진 교체·삭제는 후속 작업입니다. 카테고리 항목은 팀 결정에 맞춰 변경할 수 있습니다.
