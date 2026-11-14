# SKKU Lost & Found

성균관대학교 구성원을 위한 분실물·습득물 플랫폼입니다. 학교 이메일 인증, 게시글과 사진 관리, 모바일 UI를 기반으로 흩어진 분실물 정보를 한곳에서 검색하고 관리하는 것을 목표로 합니다.

AI 모듈은 자연어 대화를 바탕으로 게시글 초안을 생성하며 FastAPI와 Expo 작성 화면에 연결되어 있습니다.

## 구현 현황

| 영역 | 상태 | 내용 |
|---|---|---|
| 인증 | 구현 | 이메일 인증, 회원가입, 로그인, token 갱신 및 로그아웃 |
| 게시글 | 구현 | 분실·습득 게시글 CRUD, 카테고리와 상세 정보 |
| 사진 | 구현 | JPEG·PNG·WebP 업로드 및 로컬 볼륨 저장 |
| 모바일 UI | 진행 중 | 로그인, 홈, 검색·필터와 공통 UI |
| AI 게시글 작성 | 구현 | 자연어 게시글 초안, 장소 정규화, 한국어·영어 대화 |
| 매칭 | 구현 | 규칙 기반 유사 게시물 추천. 임베딩 매칭은 후속 작업 |
| 채팅·알림 | 계획 | 실제 1:1 채팅과 알림 |

## 기술 구성

- Backend: FastAPI, SQLAlchemy, Alembic, PostgreSQL
- Frontend: Expo, React Native, Expo Router, TypeScript
- AI: LangGraph, Pydantic, OpenAI Responses API
- Infrastructure: Docker, Docker Compose

```text
[Expo Client] → [FastAPI] → [Service / Repository] → [PostgreSQL]
                     └──────────────────────────────→ [Image Storage]

[Expo AI 작성 화면] → [FastAPI AI API] → [LangGraph / OpenAI]
```

## 디렉터리

```text
skku-lost-and-found/
├── backend/
│   ├── alembic/                  # DB migration
│   ├── app/
│   │   ├── auth/                 # 인증
│   │   ├── posts/                # 게시글과 사진
│   │   ├── users/                # 사용자
│   │   ├── ai/                   # AI API, workflow, provider 및 장소 사전
│   │   └── main.py
│   └── tests/
├── frontend/                     # Expo 애플리케이션
├── compose.yaml                  # 로컬 개발
├── compose.deploy.yaml           # EC2 배포
├── deploy/                       # Caddy 설정과 배포 안내
└── README.md
```

## 빠른 시작

### Backend

저장소 루트에서 실행합니다.

```sh
docker compose up --build -d
docker compose run --rm backend alembic upgrade head
```

- Health check: <http://127.0.0.1:8000/api/v1/health>
- API docs: <http://127.0.0.1:8000/docs>

백엔드 환경 변수는 `backend/.env.example`을 참고합니다. 실제 secret이 포함된 `.env`는 커밋하지 않습니다.

이메일 인증은 기본적으로 SMTP로 실제 메일을 발송합니다. `backend/.env`에 발신 계정과 앱 비밀번호를 설정합니다.

### Frontend

```sh
cd frontend
npm install
npx expo start
```

## 테스트

Backend:

```sh
docker compose run --rm backend python -m pytest -q
```

Frontend:

```sh
cd frontend
npx expo lint
npx tsc --noEmit
```

## 현재 제한 사항

- 프런트엔드는 일부 화면이 백엔드 API와 연결되지 않았습니다.
- AI 출력은 확정 정보가 아닌 사용자가 검토할 초안입니다.
- 임베딩 매칭, 실제 채팅과 알림은 아직 구현되지 않았습니다.
- EC2의 사진은 Docker 볼륨에 저장됩니다. 서버 간 공유 이미지 저장소는 제공하지 않습니다.

## 문서

- [AI 게시글 작성 모듈](./backend/app/ai/README.md)
- [게시글 API](./backend/app/posts/README.md)
- [채팅 모듈](./backend/app/chat/README.md)
- [Frontend](./frontend/README.md)
- [EC2 백엔드 배포](./deploy/README.md)
- API 명세: Backend 실행 후 <http://127.0.0.1:8000/docs>
