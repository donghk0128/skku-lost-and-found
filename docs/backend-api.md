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
| `PATCH` | `/posts/{post_id}` | 필요 | 작성자만 게시글 정보를 수정할 수 있습니다. |
| `PATCH` | `/posts/{post_id}/status` | 필요 | 작성자만 게시글을 완료 표시할 수 있습니다. |
| `DELETE` | `/posts/{post_id}` | 필요 | 작성자만 게시글을 삭제 표시할 수 있습니다. |

- 게시글 생성에는 `post_type`(`LOST` 또는 `FOUND`), `title`, `description`이 필요합니다.
- 선택 값: `item_name`, `category_id`, `location_text`, 좌표, 발생 시각 범위
- 목록 조회: `post_type`, `category_id`, `status`, `q`, `limit`(기본 20), `offset`(기본 0)을 사용할 수 있습니다. `q`는 제목·설명·물건명에서 공백 차이를 무시하고 검색합니다.
- 완료 표시 요청 본문은 `{"status": "COMPLETED"}`입니다. 완료된 글은 조회할 수 있지만 `OPEN`으로 되돌릴 수는 없습니다.
- 수정·완료 표시·삭제는 본인이 작성한 게시글만 가능합니다.
- 추천은 요청할 때마다 계산하며 기본 상위 5개를 반환합니다(`limit`: 1~20). 점수는 순위를 위한 임시 값이고 동일 물건일 확률이 아닙니다. 완료·삭제된 글은 후보에서 제외합니다.

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
