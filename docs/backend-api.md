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
| `POST` | `/auth/password-reset/send-code` | 불필요 | 가입 이메일에 비밀번호 재설정 코드를 요청합니다. |
| `POST` | `/auth/password-reset/verify` | 불필요 | 이메일 코드 확인 후 재설정 토큰을 받습니다. |
| `POST` | `/auth/password-reset/complete` | 불필요 | 토큰과 새 비밀번호·확인값으로 비밀번호를 변경합니다. |
| `GET` | `/users/me` | 필요 | 현재 로그인한 사용자 정보를 조회합니다. |
| `PATCH` | `/users/me` | 필요 | 닉네임을 수정합니다. 정규화 후 중복 닉네임은 `409`로 거부합니다. |
| `POST` | `/users/me/password` | 필요 | 현재 비밀번호 확인 후 비밀번호를 변경합니다. 로그인 세션은 유지합니다. |
| `GET` | `/users/me/posts` | 필요 | 내가 작성한 글을 조회합니다. `post_type=LOST|FOUND` 및 `limit`, `offset`을 지원하며 완료된 글도 포함합니다. |
| `GET` | `/users/me/favorites` | 필요 | 관심 등록한 글을 최신 등록순으로 조회합니다. `limit`, `offset`을 지원합니다. |
| `GET` | `/users/me/favorites/{post_id}` | 필요 | 현재 계정의 관심 등록 여부(`saved`)를 조회합니다. |
| `POST` | `/users/me/favorites/{post_id}` | 필요 | 관심 등록합니다. 반복 요청은 중복 저장하지 않으며 본인 글은 `422`로 거부합니다. |
| `DELETE` | `/users/me/favorites/{post_id}` | 필요 | 관심 등록을 해제합니다. 이미 해제된 상태에서도 성공합니다. |
| `POST` | `/users/me/withdrawal/password` | 필요 | 현재 비밀번호를 확인하고 10분 동안 유효한 탈퇴 인증 토큰을 발급합니다. |
| `POST` | `/users/me/withdrawal/send-code` | 필요 | 비밀번호 확인 토큰으로 가입 이메일에 탈퇴 인증 코드를 전송합니다. |
| `POST` | `/users/me/withdrawal/verify-email` | 필요 | 탈퇴 인증 토큰과 이메일 코드를 확인합니다. |
| `DELETE` | `/users/me` | 필요 | 이메일 인증된 토큰으로 즉시 회원탈퇴를 처리합니다. |

### 주요 요청 값

- 이메일 인증 요청: `email`
- 이메일 인증 확인: `email`, 6자리 `code`
- 회원가입: `email`, `nickname`, `password`
- 로그인: `email`, `password`
- 토큰 갱신·로그아웃: `refresh_token`
- 프로필 수정: `nickname`만 허용합니다. 닉네임은 NFKC 정규화 및 앞뒤 공백 제거 후 2~30자로 검증하며, 대소문자는 구분합니다. 회원가입에도 동일한 규칙과 중복 검사를 적용합니다.
- 비밀번호 변경: `current_password`, `password`, `password_confirmation`. 새 비밀번호는 8~128자이며 확인 입력이 일치해야 합니다. 이메일 재인증이나 재로그인을 요구하지 않습니다.
- 비밀번호 재설정: `email`로 코드를 요청하고 `email`, 6자리 `code`로 인증한 뒤, 발급받은 `reset_token`과 `password`, `password_confirmation`을 제출합니다. 회원가입 화면과 동일하게 영문·숫자를 포함한 8~20자로 검증하며, 완료 시 기존 refresh 세션을 폐기합니다. 별도의 `0012_password_reset` migration이 인증 정보를 저장합니다.

내 정보와 관심 글 기능에는 `0010_account_profile_favorites` migration이 필요합니다. 기존 사용자 행을 수정하거나 테이블·컬럼을 삭제하지 않고 `users.nickname`의 UNIQUE 제약과 `favorite_posts` 테이블만 추가합니다. 기존 닉네임이 중복된 환경에서는 자동 변경하지 않고 migration을 중단합니다. downgrade는 관심 글 데이터 손실을 막기 위해 명시적으로 차단합니다.

삭제된 게시글은 작성 글·관심 글 목록에서 제외하며, 작성 글은 현재 사용자 소유만 조회합니다. 기존 `/posts/mine`은 후보 추천용 열린 글 조회 규칙을 유지합니다. 키워드 알림 설정은 준비 중 버튼만 유지합니다.

### 회원탈퇴

`비밀번호 확인 → 이메일 코드 발송 → 코드 인증 → 탈퇴` 순서입니다. 비밀번호 확인 요청은 `current_password`, 이후 요청은 `withdrawal_token`을 사용하며 코드 인증에는 6자리 `code`, 최종 탈퇴에는 `confirmed: true`가 추가로 필요합니다. 이메일 주소는 요청으로 받지 않고 로그인한 계정의 주소로만 전송합니다. 토큰은 서버에서 해시로 보관하고 계정과 비밀번호 상태에 묶습니다. 새 비밀번호 확인은 이전 토큰을 폐기하며, 비밀번호 변경 후에는 이전 탈퇴 인증을 사용할 수 없습니다. 클라이언트는 토큰을 URL이나 영구 저장소에 넣지 않습니다.

코드 유효 시간은 기본 5분이며 비밀번호 확인의 10분 유효 시간을 넘지 않습니다. 재전송은 기본 60초 간격이고, 코드 확인은 최대 5회 시도할 수 있습니다. 재전송하면 이전 코드·이메일 인증 결과를 무효화합니다. 인증 만료 또는 미완료 시 서버와 화면 모두 최종 탈퇴를 막습니다.

탈퇴에는 `0011_account_withdrawal` migration이 필요합니다. 이 revision은 기존 테이블·컬럼을 삭제하지 않고 채팅의 사용자·게시글 참조를 nullable/`SET NULL`로 바꾸며, 활성 채팅에는 참조가 필수인 제약을 추가합니다. 탈퇴 인증 테이블도 추가합니다. migration 자체는 기존 계정·게시글·채팅 데이터를 지우지 않습니다.

탈퇴가 실행되면 계정 행, 로그인 세션, 이메일/탈퇴 인증, 관심 목록, 모든 작성 글(완료·기존 삭제 표시 글 포함), 게시글 사진 행과 실제 파일을 삭제합니다. 다른 사용자가 관심 등록한 해당 글과 삭제된 글을 참조하는 추천 실행 기록·임베딩도 정리합니다. 닉네임·이메일은 재사용할 수 있고, 재가입은 새로운 UUID이므로 이전 글·채팅에 접근할 수 없습니다.

참여 중인 활성 채팅은 `CLOSED/GENERAL`로 바꾸고 기존 종료 사유·시각은 보존합니다. 탈퇴자의 멤버십과 사용자 ID 연결은 제거합니다. 상대방에게는 `탈퇴한 사용자`로 표시하며, 삭제된 글의 카드는 링크·메타데이터 없이 `삭제된 게시물입니다.`만 표시합니다. 상대방의 이전 대화와 채팅 사진은 계속 열람 가능하며 숨김/복원과 읽음 처리도 유지됩니다. 탈퇴자가 요청자였던 경우 상대방 소유의 게시글은 삭제하지 않습니다. 마지막 참여자까지 탈퇴하여 열람자가 없는 채팅은 메시지·사진과 함께 정리합니다.

게시글 사진은 DB commit 전 임시 디스크 백업 후 삭제합니다. 저장소 또는 DB commit 오류가 나면 계정/게시글 삭제를 rollback하고 이미 삭제한 파일을 복원합니다. 파일시스템과 DB가 하나의 트랜잭션은 아니므로 프로세스 강제 종료 같은 장애까지 원자성을 보장하지는 않습니다.

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
  "algorithm_version": "hybrid-v3",
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

`score`는 확률이 아닌 정렬 점수입니다. `hybrid-v3`의 규칙 점수는 문자열 15% + 카테고리 25% + 발생 시간 30% + 좌표 거리 30%이며, 최종 점수는 규칙 50% + 임베딩 50%입니다. 같은 물건·케이스·스티커에 서로 다른 명시적 색상이 적혀 있으면 최종 점수에서 0.25를 감점하고 0 아래로 내려가지 않게 합니다. 색상이 없거나 서로 다른 부분을 묘사하면 감점하지 않습니다. 현재 장소 문구만으로는 거리 점수를 계산하지 않습니다. 임베딩이 없는 쌍은 `semantic_score: null`이며 규칙 점수에서 색상 감점을 적용합니다. 근거 코드는 각각 거리 0.5 km 이내, 발생 시간 구간 겹침, 동일 카테고리, 임베딩 유사도 0.75 이상일 때만 부여합니다. 이 기준과 가중치는 평가 전의 임시 값입니다. 응답에 근거가 없는 후보도 포함될 수 있습니다. `run_id`는 같은 입력 상태의 반복 조회에서 동일하며, 점수 계산 자체는 매번 수행합니다. 현재 **캐시는 없습니다**.

인증 누락은 `401`, 남의 기준 글은 `403`, 없는·삭제된 기준 글은 `404`, 완료된 기준 글·빈 검색어는 `422`입니다. 검색·필터에 맞는 후보가 없으면 `200`과 빈 `items`, `total: 0`을 반환합니다. 최신순에는 기존 `GET /posts`를 사용합니다. 새 글·수정·완료·삭제로 조회 대상이 바뀌면 후보순 첫 페이지부터 다시 요청해야 합니다.

백엔드 배포 시 `0009_record_color_conflict`까지 Alembic 마이그레이션을 적용해야 새 API가 실행 기록을 저장할 수 있습니다. DB의 `recommendation_items.color_conflict`는 색상 충돌 감점 여부를 기록합니다. v2 기록은 그대로 보존되고 새 조회는 v3 실행으로 저장됩니다. 이 브랜치의 프론트 홈 화면은 후보순 API에 연결되어 있습니다. 배포 후에는 `/docs`에서 로그인 토큰으로 두 API를 호출하거나, 같은 API 주소를 바라보는 Expo 앱에서 확인할 수 있습니다.

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
