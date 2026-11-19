# Backend API 요약

## 기본 정보

- 기본 경로: `/api/v1`
- Swagger UI: `/docs`
- OpenAPI JSON: `/api/v1/openapi.json`
- 인증이 필요한 요청은 `Authorization: Bearer {access_token}` 헤더를 사용합니다.

## 공통 응답

- 검증 오류: `422`와 함께 `error.code`, `error.message`, `error.details`를 반환합니다.
- 서비스 오류: `{"error": {"code": "...", "message": "..."}}` 형식으로 반환합니다.

## 상태 확인

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| `GET` | `/health` | API 상태를 확인합니다. |

## 인증과 사용자

| 메서드 | 경로 | 인증 | 설명 |
| --- | --- | --- | --- |
| `POST` | `/auth/email/send-code` | 불필요 | 학교 이메일로 인증 코드를 요청합니다. |
| `POST` | `/auth/email/verify` | 불필요 | 이메일 인증 코드를 확인합니다. |
| `POST` | `/auth/signup` | 불필요 | 인증된 이메일로 회원가입합니다. |
| `POST` | `/auth/login` | 불필요 | 로그인 후 access/refresh token을 받습니다. |
| `POST` | `/auth/refresh` | 불필요 | refresh token으로 access token을 갱신합니다. |
| `POST` | `/auth/logout` | 불필요 | refresh token을 폐기합니다. |
| `GET` | `/users/me` | 필요 | 현재 로그인한 사용자 정보를 조회합니다. |

### 주요 요청 값

- 이메일 인증 요청: `email`
- 이메일 인증 확인: `email`, 6자리 `code`
- 회원가입: `email`, `nickname`, `password`
- 로그인: `email`, `password`
- 토큰 갱신·로그아웃: `refresh_token`

## 게시글과 카테고리

| 메서드 | 경로 | 인증 | 설명 |
| --- | --- | --- | --- |
| `GET` | `/categories` | 불필요 | 게시글 카테고리 목록을 조회합니다. |
| `POST` | `/posts` | 필요 | 분실물 또는 습득물 게시글을 작성합니다. |
| `GET` | `/posts` | 불필요 | 삭제되지 않은 게시글 목록을 조회합니다. |
| `GET` | `/posts/{post_id}` | 불필요 | 게시글 상세를 조회합니다. |
| `GET` | `/posts/{post_id}/recommendations` | 불필요 | 반대 유형의 열린 게시글 중 추천 후보를 조회합니다. |
| `GET` | `/posts/mine` | 필요 | 드롭다운에 넣을 본인의 진행 중 게시글을 조회합니다. |
| `GET` | `/posts/{post_id}/ranked-candidates` | 필요 | 선택한 본인 글을 기준으로 검색·필터 후 후보순 목록을 조회합니다. |
| `PATCH` | `/posts/{post_id}` | 필요 | 작성자만 게시글 정보를 수정할 수 있습니다. |
| `PATCH` | `/posts/{post_id}/status` | 필요 | 작성자만 게시글을 완료 표시할 수 있습니다. |
| `DELETE` | `/posts/{post_id}` | 필요 | 작성자만 게시글을 삭제 표시할 수 있습니다. |

- 게시글 생성에는 `post_type`(`LOST` 또는 `FOUND`), `title`, `description`이 필요합니다.
- 선택 값: `item_name`, `category_id`, `location_text`, 좌표, 발생 시각 범위
- 목록 조회: `post_type`, `category_id`, `status`, `q`, `limit`(기본 20), `offset`(기본 0)을 사용할 수 있습니다. `q`는 제목·설명·물건명에서 공백 차이를 무시하고 검색합니다.
- 완료 표시 요청 본문은 `{"status": "COMPLETED"}`입니다. 완료된 글은 조회할 수 있지만 `OPEN`으로 되돌릴 수는 없습니다.
- 수정·완료 표시·삭제는 본인이 작성한 게시글만 가능합니다.
- 추천은 요청할 때마다 계산하며 기본 상위 5개를 반환합니다(`limit`: 1~20). 점수는 순위를 위한 임시 값이고 동일 물건일 확률이 아닙니다. 완료·삭제된 글은 후보에서 제외합니다.

### 홈 화면 후보순 API

기존 `/posts/{post_id}/recommendations`는 게시글 상세의 상위 5개 추천용으로 유지합니다. 홈 후보순은 아래 API를 사용합니다. 두 API 모두 저장된 임베딩을 읽으며, 조회할 때 Gemini를 호출하지 않습니다.

1. `GET /posts/mine?post_type=FOUND&limit=20&offset=0`: **분실했어요** 탭에서 기준으로 고를 내 습득글을 반환합니다. **습득했어요** 탭은 `post_type=LOST`를 사용합니다. `OPEN`이고 삭제되지 않은 본인 글만 반환하며, 응답은 일반 `PostListResponse`와 같습니다. 인증 필수입니다.
2. `GET /posts/{source_post_id}/ranked-candidates?category_id=1&q=에어팟&limit=20&offset=0`: 기준 글의 반대 유형에 대해 `OPEN`·미삭제, 카테고리 및 검색어를 **먼저** 적용합니다. 조건에 맞는 글을 모두 혼합 점수로 정렬한 뒤 페이지를 반환합니다. 기준 글은 본인 소유의 `OPEN` 글이어야 합니다. 인증 필수입니다. `q`는 기존 목록 검색과 동일하게 제목·설명·물건명에 적용됩니다. `category_id`와 `q`는 생략할 수 있습니다.

후보순 응답 예시(값은 예시):

```json
{
  "source_post_id": "11111111-1111-1111-1111-111111111111",
  "run_id": "22222222-2222-2222-2222-222222222222",
  "algorithm_version": "hybrid-v2",
  "items": [
    {
      "post": {
        "id": "33333333-3333-3333-3333-333333333333",
        "author_id": "44444444-4444-4444-4444-444444444444",
        "post_type": "LOST",
        "title": "검은 에어팟을 잃어버렸습니다",
        "description": "삼성학술정보관 앞에서 분실했습니다",
        "item_name": "에어팟",
        "category_id": 1,
        "location_text": "삼성학술정보관 앞",
        "latitude": 37.588,
        "longitude": 126.993,
        "event_start_at": "2026-11-18T13:00:00+09:00",
        "event_end_at": "2026-11-18T15:00:00+09:00",
        "status": "OPEN",
        "creation_method": "MANUAL",
        "created_at": "2026-11-18T16:00:00+09:00",
        "updated_at": "2026-11-18T16:00:00+09:00"
      },
      "rank": 1,
      "score": 0.8123,
      "rule_score": 0.7850,
      "semantic_score": 0.8761,
      "reasons": ["NEARBY_LOCATION", "OVERLAPPING_TIME", "SAME_CATEGORY", "SIMILAR_MEANING"]
    }
  ],
  "total": 4,
  "limit": 20,
  "offset": 0
}
```

`score`는 확률이 아닌 정렬 점수입니다. 임베딩이 없는 쌍은 `semantic_score: null`이며 규칙 점수만 사용합니다. 근거 코드는 각각 거리 0.5 km 이내, 발생 시간 구간 겹침, 동일 카테고리, 임베딩 유사도 0.75 이상일 때만 부여합니다. 이 기준은 평가 후 조정할 수 있습니다. 응답에 근거가 없는 후보도 포함될 수 있습니다. `run_id`는 같은 입력 상태의 반복 조회에서 동일하며, 점수 계산 자체는 매번 수행합니다. 현재 **캐시는 없습니다**.

인증 누락은 `401`, 남의 기준 글은 `403`, 없는·삭제된 기준 글은 `404`, 완료된 기준 글·빈 검색어는 `422`입니다. 검색·필터에 맞는 후보가 없으면 `200`과 빈 `items`, `total: 0`을 반환합니다. 최신순에는 기존 `GET /posts`를 사용합니다. 새 글·수정·완료·삭제로 조회 대상이 바뀌면 후보순 첫 페이지부터 다시 요청해야 합니다.

백엔드 배포 시 `0008_create_recommendation_runs`까지 Alembic 마이그레이션을 적용해야 새 API가 실행 기록을 저장할 수 있습니다. 이 변경은 아직 프론트 홈 화면에 연결되지 않았습니다. 배포 후에는 `/docs`에서 로그인 토큰으로 두 API를 호출해 확인할 수 있습니다.

## 게시글 사진

| 메서드 | 경로 | 인증 | 설명 |
| --- | --- | --- | --- |
| `POST` | `/posts/{post_id}/images` | 필요 | 작성자만 사진 한 장을 업로드할 수 있습니다. |
| `GET` | `/posts/{post_id}/images` | 불필요 | 게시글 사진 목록을 조회합니다. |
| `GET` | `/posts/{post_id}/images/{image_id}/content` | 불필요 | 사진 파일 내용을 조회합니다. |

- 업로드 요청은 `multipart/form-data`의 `file` 필드를 사용합니다.
- JPEG, PNG, WebP만 지원하며 사진 한 장은 최대 5MiB입니다.
- 게시글당 사진은 최대 5장입니다.

## 참고

- 정확한 요청·응답 예시는 실행 중인 Swagger UI를 기준으로 확인합니다.
- 게시글 세부 규칙은 `backend/app/posts/README.md`를 참고합니다.
