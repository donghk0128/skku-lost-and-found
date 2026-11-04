# Docker에서 인증 이메일 발송하기

서비스는 이메일로 가입·로그인합니다. 인증 메일은 서버의 SMTP 계정에서 가입자의 `@skku.edu` 주소로 전송합니다. 발신 계정과 가입자 계정은 별개이므로 Gmail 발신 계정으로 학교 이메일에 보낼 수 있습니다.

## 1. Google 발신 계정 준비

1. 발송에 사용할 Gmail 계정에 로그인합니다.
2. [Google 계정 보안](https://myaccount.google.com/security)에서 2단계 인증을 활성화합니다.
3. [앱 비밀번호](https://myaccount.google.com/apppasswords)에서 `SKKU FINDER Docker` 같은 이름으로 앱 비밀번호를 만듭니다.
4. 발급받은 16자리 값을 `SMTP_PASSWORD`에 입력합니다. 표시용 공백은 제외합니다. 일반 Google 로그인 비밀번호는 사용하지 않습니다.

이 구현은 SMTP 사용자 이름과 앱 비밀번호로 인증합니다. Google Cloud 프로젝트 생성, Gmail API 활성화, OAuth 동의 화면 및 클라이언트 ID 설정은 필요하지 않습니다.

학교·조직 Google Workspace 계정은 정책에 따라 앱 비밀번호 메뉴가 없을 수 있습니다. 보안 키만 사용하는 2단계 인증이나 고급 보호 프로그램에서도 제한될 수 있습니다. 이 경우 발신용 개인 Gmail 계정을 사용하거나 조직 관리자에게 허용된 발송 방식을 확인합니다. 가입자가 사용하는 학교 계정에 앱 비밀번호를 만들 필요는 없습니다.

근거: [Google 앱 비밀번호 안내](https://support.google.com/accounts/answer/185833), [Gmail SMTP 서버 및 포트](https://developers.google.com/workspace/gmail/imap/imap-smtp).

## 2. backend/.env 설정

기존 `backend/.env`의 나머지 설정을 유지하면서 아래 항목을 확인합니다. 실제 이메일·앱 비밀번호는 로컬 파일에 직접 입력합니다. `.env`는 Git과 Docker 이미지 빌드에서 제외됩니다.

```dotenv
EMAIL_DELIVERY_MODE=smtp
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-sender@gmail.com
SMTP_PASSWORD=your-16-character-app-password
SMTP_FROM_EMAIL=your-sender@gmail.com
SMTP_FROM_NAME=SKKU FINDER
SMTP_USE_TLS=true

EMAIL_VERIFICATION_EXPIRE_MINUTES=5
EMAIL_VERIFICATION_RESEND_SECONDS=60
ALLOWED_EMAIL_DOMAIN=skku.edu
```

- `SMTP_USERNAME`: 발신 Gmail 계정의 전체 이메일 주소.
- `SMTP_PASSWORD`: 해당 발신 계정에서 발급한 앱 비밀번호.
- `SMTP_FROM_EMAIL`: 위 발신 Gmail 주소와 동일하게 설정.
- `SMTP_FROM_NAME`: 수신자에게 표시할 발신자 이름.
- `SMTP_USE_TLS=true`: 포트 587에서 STARTTLS로 연결. 이 구현은 포트 465의 implicit SSL 연결을 지원하지 않음.
- `ALLOWED_EMAIL_DOMAIN`: 가입자 수신 주소의 도메인 제한. 현재는 `skku.edu`만 허용하며 `g.skku.edu`는 허용하지 않음.
- 만료 5분과 재요청 간격 60초 유지. 현재 프런트엔드 인증 타이머는 5분 기준이므로 만료 시간을 바꿀 때는 화면도 함께 조정해야 함.

Compose는 이메일 관련 값을 `backend/.env`에서 읽습니다. 루트 `.env`나 셸의 `EMAIL_DELIVERY_MODE`로 자동 덮어쓰지 않습니다. 발송 모드가 생략되어도 기본값은 `smtp`입니다. `console`은 개발자가 명시적으로 설정한 경우에만 인증 코드를 로그에 출력합니다. SMTP 실패 시 콘솔 발송으로 전환하지 않습니다.

## 3. Docker에 설정 반영

저장소 루트에서 실행합니다.

```powershell
docker compose up -d --no-deps --force-recreate backend
```

DB가 실행 중이지 않은 첫 시작에서는 다음을 실행합니다.

```powershell
docker compose up --build -d
docker compose run --rm backend alembic upgrade head
```

환경 변수 변경은 `docker compose restart`만으로 반영되지 않습니다. 위처럼 컨테이너를 다시 생성해야 합니다. DB 테이블 변경은 이번 SMTP 전환에 필요하지 않습니다. 근거: [Docker 환경 변수 우선순위](https://docs.docker.com/compose/how-tos/environment-variables/envvars-precedence/), [restart 동작](https://docs.docker.com/reference/cli/docker/compose/restart/).

## 4. 실제 수신 확인

1. 서비스의 회원가입 화면에서 본인의 `@skku.edu` 이메일을 입력하고 인증 코드 발송을 누릅니다.
2. 메일함과 스팸함에서 `SKKU FINDER` 메일을 확인합니다. 제목과 본문에 한국어·영어 안내가 함께 있습니다.
3. 메일의 6자리 코드를 5분 안에 입력하고 가입을 진행합니다.
4. 같은 주소로 다시 요청하려면 60초 이상 기다립니다.

SMTP 서버가 수락하면 발송 API는 `202`를 반환합니다. 이는 수신함 도착까지 보장하지 않으므로 실제 메일 수신을 별도로 확인합니다. 수신 테스트에는 본인이 소유한 학교 이메일을 사용합니다.

문제가 있으면 아래에서 API 오류를 확인합니다. SMTP 모드에서는 인증 코드를 서버 로그에 출력하지 않습니다.

```powershell
docker compose logs --tail=100 backend
```

| 증상 | 확인할 내용 |
| --- | --- |
| `email_not_configured` / 503 | SMTP 호스트·발신 주소 누락, 사용자 이름·비밀번호 중 하나만 입력했는지 확인 |
| `email_delivery_failed` / 503 | 앱 비밀번호와 전체 Gmail 주소, 계정 정책, Docker의 외부 587 포트 연결 확인 |
| `invalid_university_email` / 400 | 수신 주소가 정확히 `@skku.edu`인지 확인 |
| `verification_resend_cooldown` / 429 | 60초 뒤 재요청 |
| API는 202인데 메일이 안 보임 | 수신 주소 오타, 스팸함, 발신 계정의 발송 제한 확인 |

발송 실패 시 사용할 수 있는 인증 요청을 저장하지 않아 즉시 재시도할 수 있습니다. 성공한 발송 뒤에는 기존 재요청 제한이 적용됩니다.

## 5. 실제 메일 없이 자동 검사

```powershell
docker compose run --rm --no-deps -e LANGSMITH_TRACING=false backend python -m pytest -q tests/test_smtp_client.py tests/test_email_service.py tests/test_auth_service.py tests/test_auth_api.py
```

SMTP 연결은 가짜 전송 객체로 대체하고 인증 데이터는 격리된 SQLite에 저장합니다. 실제 메일을 발송하거나 Docker PostgreSQL의 사용자 데이터를 수정하지 않습니다.
