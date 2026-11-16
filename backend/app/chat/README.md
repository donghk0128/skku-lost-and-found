# 게시물 연결 1:1 채팅

인증된 게시물 작성자와 요청자만 대화·사진·기록에 접근한다. API prefix는 `/api/v1/chat/rooms`다.

## 정책

- `(post_id, requester_id)`당 방 하나. 중복 시작은 기존 방을 반환한다.
- 본인 게시물, 완료·삭제된 게시물에는 신규 방을 만들 수 없다.
- `GENERAL`: 해당 방만 종료, 게시물은 유지.
- `RETURNED`: 게시물을 `COMPLETED`로 변경하고 나머지 활성 방을 `POST_COMPLETED`로 종료.
- 기존 게시물 완료 API도 모든 활성 방을 종료한다. 활성 방이 있으면 게시물 삭제는 409.
- 양쪽 참여자가 종료할 수 있다. 종료 후 재개·새 방 생성은 불가하며 기록만 열람한다.
- 숨김은 종료한 방에서만 가능하며 본인 목록에만 적용된다. `include_hidden=true`로 복구 가능.
- 게시물이 soft delete되어도 참여자의 채팅 기록과 사진은 유지된다.

## HTTP 계약

모든 요청은 access token을 `Authorization: Bearer ...`로 전달한다. 비참여자는 방·메시지·사진 모두 404다.

| Method | Path | 요청 / 역할 |
|---|---|---|
| POST | `/` | `{ "post_id": "UUID" }` 생성 또는 기존 방 반환 (200) |
| GET | `/` | `limit=20&offset=0&include_hidden=false` 목록, 총 개수 |
| GET | `/{room_id}` | 상대 닉네임, 게시물 제목, 상태, 마지막 메시지, 안 읽은 수 |
| POST | `/{room_id}/messages` | `{ "content": "1~2000자", "client_message_id": "전송 식별자" }` 텍스트 전송 (201) |
| POST | `/{room_id}/images` | multipart `files` 여러 장 + 선택 `content`, `client_message_id`. 장당 5MiB, 합계 50MiB (201) |
| GET | `/{room_id}/messages` | `after=0&limit=50` sequence 오름차순, `next_after`, `has_more` |
| GET | `/{room_id}/messages/{message_id}/image` | 참여자만 사진 다운로드, private/no-store |
| GET | `/{room_id}/messages/{message_id}/images/{image_id}` | 묶음의 특정 사진 다운로드, 참여자만 허용 |
| PATCH | `/{room_id}/read` | `{ "sequence": 5 }` 존재하는 메시지까지만, 이전 읽음 위치로 후퇴 불가 |
| PATCH | `/{room_id}/visibility` | `{ "is_hidden": true }` 본인 목록에서 숨김 |
| POST | `/{room_id}/close` | `{ "reason": "RETURNED" 또는 "GENERAL" }` |

사진은 기존 영속 이미지 볼륨 아래 `chat/` 디렉터리에 저장한다. DB에는 경로만 저장하고 응답에는 인증이 필요한 URL을 제공한다. 업로드 후 DB 커밋 실패 시 파일을 정리한다. 파일 크기·MIME·시그니처 검증은 기존 게시물 이미지 정책과 같다.

사진 여러 장과 설명은 하나의 `IMAGE` 메시지이며 응답의 `images` 배열에 사진 ID·형식·순서·인증 URL을 담는다. 묶음 하나가 sequence와 안 읽은 수 1개에 해당한다. 예전 클라이언트의 단일 `file` 요청과 첫 사진용 `image_url`·`/image` 경로도 호환한다.

모든 파일을 검증한 후 저장하고, 업로드나 DB 커밋 실패 시 이미 쓴 파일을 정리한다. 클라이언트는 동일 묶음 재시도에 같은 `client_message_id`를 사용한다. 서버는 방·발신자·전송 식별자가 같으면 기존 메시지를 반환하고, 내용이 달라지면 409로 거부한다. 종료된 방에서도 이미 성공한 요청의 재확인은 가능하다.

## WebSocket

`/api/v1/chat/rooms/{room_id}/ws?after=0`

1. 연결 후 10초 안에 첫 JSON 프레임 `{ "token": "access JWT" }`를 전송한다. 토큰을 URL에 넣지 않는다.
2. 서버는 `after` 이후 저장된 메시지를 `{"type":"message","message":{...}}`로 전달한다.
3. 클라이언트는 `{"content":"메시지","client_message_id":"전송 식별자"}`로 텍스트를 보낼 수 있다. 사진·읽음·종료는 HTTP API를 사용한다.
4. 종료 시 `{"type":"room_closed","reason":"GENERAL"}` 등을 보낸 뒤 정상 종료한다.
5. 4401은 인증 만료/실패, 4404는 방 접근 불가, 4409는 종료된 방 등 충돌이다. 재접속 시 마지막 수신 sequence를 `after`로 전달한다.

서버는 0.5초마다 짧은 DB 세션으로 상태와 메시지를 확인한다. idle socket이 DB 연결을 점유하지 않고 여러 worker에서도 전달되지만, 접속 수가 늘면 Redis/pub-sub 등으로 교체해야 한다. 프론트는 HTTP로 전송하고 WebSocket으로 수신하며 중복 메시지를 ID로 제거하고 누락 없는 sequence부터 재접속한다.

텍스트와 사진 모두 같은 전송을 재시도할 때 식별자를 유지한다. 텍스트를 HTTP와 WebSocket 양쪽으로 재시도해도 같은 방·발신자·식별자이면 메시지 하나만 저장한다. 구 클라이언트 호환을 위해 식별자는 선택 필드이며 생략하면 중복 방지를 보장하지 않는다.

대화 화면은 하단 근처에 있을 때만 새 메시지를 따라간다. 위로 스크롤해 과거 대화를 읽으면 위치를 유지하고 최신 메시지 이동 버튼을 제공한다. 과거 기록을 읽는 중 도착한 새 메시지는 하단으로 돌아오면 읽음 처리한다.

## DB 및 검증

`0006_create_chat_tables`가 `chat_rooms`, `chat_room_members`, `chat_messages`를 생성한다. 쓰기는 게시물 → 채팅방 → 멤버 순으로 잠가 생성/완료/삭제/전송의 경합을 직렬화한다. 읽음은 시각과 sequence를 함께 보관한다.

`0007_create_chat_message_images`는 `chat_message_images` 테이블을 만들고 기존 사진 경로를 `position=0`인 사진 행으로 이전한다. 실제 파일은 옮기지 않는다. `chat_messages`의 사진 경로·형식 컬럼을 제거하고 재시도 식별자와 요청 fingerprint를 추가한다. 여러 사진 또는 설명이 있는 사진 메시지는 구 스키마에 담을 수 없으므로 downgrade를 차단해 데이터 손실을 막는다.

```powershell
docker compose exec -T backend alembic upgrade head
docker compose exec -T backend python -m pytest -q
```

PostgreSQL 동시성 테스트는 **마이그레이션이 적용된 폐기 가능한 `*_test` DB**에 `TEST_CHAT_DATABASE_URL`을 지정해 실행한다. `tests/test_chat_postgres.py`는 동시 생성·전송·종료·게시물 상태 변경과 DB 제약을 검증하고 자신이 만든 행을 정리한다. 마이그레이션 downgrade는 대상 테이블 데이터를 삭제하므로 테스트 DB에서만 검증한다.

FCM, 푸시 알림, Supabase/EC2 반영은 이 구현 범위에 포함하지 않는다.
