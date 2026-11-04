# 파일별 변경 기록

## 2026-11-04 — 이메일 인증 안내 및 사용자 이름 표기 정리

### 작업 기준

- 서비스는 이메일로 가입·로그인하며, 영어와 한국어 문구를 함께 관리한다.
- 사용자 검증 전에는 커밋·푸시하지 않는다. 이번 작업에서는 브랜치 생성 및 PR 생성도 하지 않았다.
- 아래 기록은 검토용 변경 내역이며 Git 커밋이 아니다.

### DB 및 전송 값 확인

- 실행 중인 Docker PostgreSQL에서 `users` 테이블의 열 이름과 자료형만 조회했다.
- `users.id`는 내부 식별용 UUID이며, 가입 화면의 기존 ID 입력값은 `nickname` 열에 저장된다.
- 가입 요청은 `email`, `nickname`, `password`를 전송하고 로그인 요청은 `email`, `password`를 전송한다.
- 따라서 사용자 이름 표기 변경에 DB 열이나 API 요청 필드를 바꿀 필요가 없음을 확인하고 2번 작업을 진행했다.

### 파일별 수정

| 파일 | 변경 내용 |
| --- | --- |
| `frontend/src/components/signup-screen.tsx` | 이메일 입력 단계의 도메인 예시 안내 줄 제거. 입력칸 예시 주소를 `example@skku.edu`로 수정. 가입 ID 라벨·접근성 이름·입력 안내·오류 안내를 사용자 이름 번역으로 연결. 화면 내부 상태·검증·포커스 명칭을 `username`으로 정리. 정규화된 값은 기존대로 `nickname`으로 전송하며 2~10자 검증 유지. |
| `frontend/src/i18n/en.ts` | 가입 관련 ID 문구를 Username으로 변경하고 라벨 번역 추가. 가입 관련 번역 키 정리. 로그인 Find ID는 사용자 후속 요청에 따라 원래대로 유지. |
| `frontend/src/i18n/ko.ts` | 가입 관련 아이디 문구를 사용자 이름으로 변경하고 라벨 번역 추가. 가입 관련 번역 키 정리. 로그인 아이디 찾기는 사용자 후속 요청에 따라 원래대로 유지. |
| `docs/change-log.md` | 요청 사항, DB 확인 근거, 파일별 변경 및 검증 결과 기록. |

### 검증 결과

- TypeScript 검사(`tsc --noEmit`): 통과.
- 린트(`npm run lint`): 오류 0개. 이번에 수정하지 않은 파일의 기존 Hook 의존성 경고 5개 확인.
- 변경 공백 검사(`git diff --check`): 통과.
- 프런트엔드에서 기존 가입 ID 번역 키와 `g.skku.edu` 안내가 남아 있지 않음을 확인. 로그인 `아이디 찾기` / `Find ID` 및 해당 번역 키는 사용자 후속 요청에 따라 원래대로 복원. `frontend/src/app/login.tsx`에는 최종 변경 사항 없음. 신분증 카테고리의 `ID cards`는 의미가 달라 유지.
- 실제 브라우저·기기에서의 화면 및 가입 동작 검증은 수행하지 않았다.

## 2026-11-04 — Docker SMTP 인증 메일 발송

### 변경 내용

- 기존 SMTP 구현을 사용하되 기본 발송 모드를 SMTP로 전환했다.
- Compose의 `EMAIL_DELIVERY_MODE`와 `ALLOWED_EMAIL_DOMAIN` 덮어쓰기를 제거하여 `backend/.env` 값이 적용되게 했다.
- SMTP 실패 시 오류를 반환하며, 콘솔에 코드를 출력하는 대체 경로는 사용하지 않는다. 개발용 `console` 모드는 명시적으로 선택할 때만 사용한다.
- 이메일은 한국어·영어 안내를 함께 포함하며 설정된 인증 유효 시간을 표시한다.
- 이메일 로그인 방식, DB 구조, 기존 가입 API 요청 형식, 로그인 화면의 아이디 찾기 문구는 유지했다.

### 파일별 수정

| 파일 | 변경 내용 |
| --- | --- |
| `compose.yaml` | 이메일 발송 모드와 허용 도메인을 덮어쓰던 항목 제거. 기존 `backend/.env` 연결 사용. |
| `backend/app/core/config.py` | 기본 모드 `smtp`, 기본 발신자 이름 `SKKU FINDER`로 변경. |
| `backend/app/email/smtp_client.py` | 사용자 이름·비밀번호의 불완전한 설정 검사. 제목·본문에 한국어·영어 안내 추가. 유효 시간을 설정값과 일치시킴. |
| `backend/.env.example` | Gmail SMTP 호스트, SMTP 모드, 발신자 이름 및 앱 비밀번호·STARTTLS 설명 정리. |
| `backend/.env` (Git 제외 로컬 파일) | 발송 모드를 `smtp`, 발신자 이름을 `SKKU FINDER`로 변경. 기존 SMTP 자격 증명과 다른 환경 설정 보존. 비밀값은 이 기록에 포함하지 않음. |
| `backend/tests/test_smtp_client.py` | TLS·로그인·메일 전송 및 한영 안내·설정 유효 시간·설정 누락 검사. |
| `backend/tests/test_email_service.py` | 기본 SMTP 선택, 명시적 콘솔 선택, SMTP 실패 시 콘솔 대체·코드 로그 없음 검사 추가. |
| `backend/tests/test_auth_service.py` | 발송 실패 시 인증 요청 미저장 및 즉시 재시도 가능, 성공 후 재요청 간격 제한 검사 추가. |
| `docs/email-setup.md` | Google 계정 준비, 실제 환경 설정, Docker 반영, 실제 수신 확인 및 문제 해결 안내 추가. |
| `README.md` | 기본 SMTP 발송 설명과 설정 안내 링크 추가. |
| `docs/change-log.md` | 이번 작업 내역 및 검증 결과 기록. |

### 검증 및 실행 상태

- Docker에서 SMTP·이메일 서비스·인증 서비스·인증 API 테스트 실행: **19개 통과**, 외부 라이브러리 사용 중단 예정 경고 2개. 가짜 전송 및 격리된 SQLite를 사용하여 실제 메일이나 기존 PostgreSQL 사용자 데이터에 영향 없음.
- Docker 백엔드 컨테이너 재생성 후 실제 설정 확인: `smtp`, `smtp.gmail.com:587`, TLS 활성화, 만료 5분, 재요청 60초, 허용 도메인 `skku.edu`.
- API 상태 확인: HTTP 200.
- 실행 중인 Docker에서 Gmail SMTP STARTTLS 연결 성공. 계정 로그인 및 실제 메일 발송은 수행하지 않았으므로 앱 비밀번호의 유효성과 수신함 도착은 미검증.
- `backend/.env`의 Git 제외 상태 및 `git diff --check` 통과 확인.
- 커밋·푸시·브랜치·PR 생성 없음.

## 2026-11-04 — 검증 완료 및 원격 반영 승인

- 사용자가 검증 완료 후 현재 작업을 원격 `main`에 직접 반영하도록 승인했다.
- 회원가입 문구, SMTP 이메일 발송, 현재 `.env.example`, 설정 안내 및 파일별 변경 기록을 함께 커밋한다.
- 실제 `backend/.env` 및 비밀값은 커밋 대상에서 제외한다.
- 별도 브랜치와 PR 없이 기존 `main`을 갱신하는 방식으로 진행한다.
