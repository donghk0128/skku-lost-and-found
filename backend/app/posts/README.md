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

### 복수 장소 (migration `0013_post_locations`, `0014_post_location_limit_policy`)

일반 작성과 `POST /api/v1/posts/ai-assisted` 모두 `locations` 배열을 받습니다. 게시글당
0~20개이며, 배열 순서를 그대로 저장합니다. 각 항목에는 `location_text`(1~255자),
`latitude`, `longitude`를 사용합니다. 장소 설명 또는 좌표 한 쌍이 필요하며, 설명만
또는 좌표만 입력할 수도 있습니다. 빈 항목은 허용하지 않습니다. 좌표의 범위와 정밀도는
기존 단일 좌표와 동일합니다.

```json
{
  "post_type": "LOST",
  "title": "에어팟 분실",
  "description": "검은색 케이스입니다.",
  "locations": [
    {"location_text": "학생회관", "latitude": 37.588, "longitude": 126.993},
    {"location_text": "도서관", "latitude": 37.589, "longitude": 126.994}
  ]
}
```

- 생성·상세·목록 응답의 `locations`에는 저장된 전체 목록이 순서대로 포함됩니다.
  응답의 `position`은 0부터 시작하는 순서이며, 요청에서는 보내지 않습니다.
- `PATCH /posts/{post_id}`에 `locations`를 보내면 전체 목록을 교체합니다.
  `[]`는 모든 위치 삭제, 생략은 유지입니다. `null`은 허용하지 않습니다.
- `locations`와 최상위 `location_text`/`latitude`/`longitude`를 한 요청에 함께 보내면
  `422`입니다. 클라이언트는 두 형식 중 하나를 선택해야 합니다.
- 기존 단일 위치 요청도 받으며, 새 관계 테이블에 한 건으로 저장합니다. 기존 클라이언트가
  단일 위치를 수정하면 첫 번째 위치만 바꾸고 나머지는 보존합니다. 첫 번째의 텍스트와
  좌표를 모두 비우면 해당 항목을 제거하고 다음 위치를 대표 위치로 올립니다.
- 첫 번째 위치는 호환용 최상위 `location_text`/`latitude`/`longitude`에도 반영합니다.
  첫 번째에 좌표가 없으면 뒤 항목에 핀이 있어도 최상위 좌표는 `null`입니다.
- DB의 `post_locations`는 `(post_id, position)` 복합 기본 키, 위치 내용과 좌표 쌍·범위
  제약을 사용합니다. `position`은 0 이상이며, 최대 개수는 API에서 검사합니다.
  게시글 실제 삭제 시 위치도 FK `ON DELETE CASCADE`로 삭제됩니다.
- migration은 완료·삭제 표시된 글까지 기존 단일 위치를 순서 0으로 복사합니다.
  위치가 없는 글은 행을 만들지 않습니다. 기존 단일 위치 컬럼은 유지합니다.
  복수 위치가 남아 있으면 데이터 손실을 막기 위해 downgrade를 거부합니다.

배포 전 저장소 루트에서 `docker compose run --rm backend alembic upgrade head`를 실행해야 합니다.
직접 작성 화면은 전체 배열을 전송하고 수정 시 `locations` 전체를 복원합니다. 빈 입력 행은
제외하며 같은 이름이나 좌표가 반복되어도 합치지 않습니다. 상세 지도는 기존처럼 첫 번째
위치만 표시합니다. 지도 컴포넌트와 핀 선택 UI는 변경하지 않습니다. AI 초안·대화의 기존
`confirmed_location` 계약도 유지하며, AI가 복수 확정 위치를 전달하는 작업은 별도입니다.

최대 개수 정책은 `app/posts/constants.py`의 `MAX_POST_LOCATIONS = 20` 한 곳에서 관리합니다.
`GET /api/v1/posts/limits`는 인증 없이 `{"max_locations": 20}`을 반환하며, 직접 작성
화면은 이 값을 조회해 전송 전에 검사합니다. 조회 실패 시에도 서버가 개수 제한을 검증합니다.
제한 변경은 상수 수정 후 백엔드를 재시작하면 적용됩니다. DB에는 상한을 고정하지 않았으므로
이를 위해 추가 migration을 만들 필요가 없습니다. 기존에 저장된 목록은 잘라내지 않습니다.
이미 적용된 `0013`의 기존 상한은 `0014_post_location_limit_policy`에서 제거합니다.

#### 복수 장소 매칭

매칭 v5는 양쪽 게시글의 좌표가 있는 위치들 사이에서 가장 가까운 거리를 사용합니다.
좌표가 없는 항목은 거리 계산에서 제외합니다. 어느 한쪽에도 유효한 좌표가 없으면
기존 v4의 거리 정보 없음 처리를 유지합니다. 이 거리를 위치 점수, `NEARBY_LOCATION`
근거, 실행 기록에 공통으로 사용합니다. 좌표를 많이 등록할수록 가까운 조합이 나올
가능성이 커지는 효과는 별도 평가가 필요합니다. 임베딩 입력은 물건명·제목·설명으로
유지하며, `location_text` 비교 규칙은 추가하지 않았습니다.

### 게시글 목록

`GET /api/v1/posts`는 삭제 표시된 글을 제외하고 최신순으로 반환합니다. 같은 시각에 작성된 글은 ID 역순으로 정렬합니다.

- `post_type`: 선택 사항. `LOST` 또는 `FOUND`로 목록을 좁힙니다.
- `category_id`: 선택 사항. 해당 카테고리의 게시글만 조회합니다.
- `status`: 선택 사항. `OPEN` 또는 `COMPLETED`로 목록을 좁힙니다. 생략하면 두 상태 모두 조회합니다.
- `q`: 선택 사항. 제목·설명·물건 이름 중 한 필드에 입력 문구가 포함되는지 검색합니다. 내부 공백과 단어 순서를 유지한 하나의 문구이며, 영문 대소문자는 구분하지 않습니다. 최대 100자이며 공백만 입력하면 `422`입니다.
- `title_terms`, `content_terms`, `location_terms`: 각 쿼리 키를 반복해 문구를 최대 20개 전달합니다. 같은 종류 안에서는 OR, 종류 간에는 AND입니다. 장소는 대표 위치뿐 아니라 `post_locations` 전체의 원문 텍스트를 검사하며, 별칭 정규화는 하지 않습니다. `%`, `_`도 일반 문자로 검색합니다.
- `event_at`: 시간대를 포함한 날짜·시각 하나입니다. 게시물의 발생 시작·종료 사이에 포함되는지 경계를 포함해 검사하며, 발생 시각이 없는 글은 제외합니다. 생략한 조건은 제한하지 않습니다.
- 후보순 API도 같은 필터를 점수 계산과 페이지네이션 전에 적용합니다. 점수 계산 방식은 유지합니다.
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
| `model.py` | `Category`, `Post`, `PostLocation`, `PostImage` SQLAlchemy 모델과 DB 제약 |
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
