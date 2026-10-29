# SKKU Lost & Found

성균관대학교 구성원을 위한 분실물·습득물 플랫폼입니다. 학교 이메일 인증, 게시글과 사진 관리, 모바일 UI를 기반으로 흩어진 분실물 정보를 한곳에서 검색하고 관리하는 것을 목표로 합니다.

AI 모듈은 자연어 게시글 작성과 사진 속성 추출을 독립형 Streamlit 환경에서 검증하고 있으며, 아직 공용 백엔드와 프런트엔드에는 연결되지 않았습니다.

## 구현 현황

| 영역 | 상태 | 내용 |
|---|---|---|
| 인증 | 구현 | 이메일 인증, 회원가입, 로그인, token 갱신 및 로그아웃 |
| 게시글 | 구현 | 분실·습득 게시글 CRUD, 카테고리와 상세 정보 |
| 사진 | 구현 | JPEG·PNG·WebP 업로드 및 로컬 볼륨 저장 |
| 모바일 UI | 진행 중 | 로그인, 홈, 검색·필터와 공통 UI |
| AI 프로토타입 | 구현 | 자연어 게시글 초안, 사진 속성 추출, Ollama·OpenAI 평가 |
| 서비스 AI 연결 | 계획 | 검증된 AI 흐름을 FastAPI와 Expo에 연결 |
| 매칭·채팅·알림 | 계획 | 유사 게시물 추천, 1:1 채팅과 반환 상태 관리 |

## 기술 구성

- Backend: FastAPI, SQLAlchemy, Alembic, PostgreSQL
- Frontend: Expo, React Native, Expo Router, TypeScript
- AI: Streamlit, Pydantic, Ollama, OpenAI Responses API
- Infrastructure: Docker, Docker Compose

```text
[Expo Client] → [FastAPI] → [Service / Repository] → [PostgreSQL]
                     └──────────────────────────────→ [Image Storage]

[Standalone Streamlit] → [Ollama or OpenAI]
```

AI Streamlit은 현재 운영 API 및 DB와 분리되어 있습니다.

## 디렉터리

```text
skku-lost-and-found/
├── backend/
│   ├── alembic/                  # DB migration
│   ├── app/
│   │   ├── auth/                 # 인증
│   │   ├── posts/                # 게시글과 사진
│   │   ├── users/                # 사용자
│   │   ├── integrations/ai/      # AI prototype 및 평가
│   │   └── main.py
│   └── tests/
├── frontend/                     # Expo 애플리케이션
├── compose.yaml
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

### Frontend

```sh
cd frontend
npm install
npx expo start
```

### AI prototype

```powershell
cd backend/app/integrations/ai
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

Ollama를 사용할 경우 필요한 모델을 먼저 준비합니다.

```powershell
ollama pull llama3.2:3b
ollama pull moondream
```

OpenAI 사용 시 AI 폴더의 `.env.example`을 기준으로 `.env`를 구성합니다. 모델 평가 방법과 실제 측정 결과는 [AI README](./backend/app/integrations/ai/README.md)를 참고하세요.

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

AI prototype:

```powershell
cd backend/app/integrations/ai
python -m pytest -q
```

## 현재 제한 사항

- 프런트엔드는 일부 화면이 백엔드 API와 연결되지 않았습니다.
- AI 기능은 독립형 평가 단계이며 게시글 저장 흐름에 연결되지 않았습니다.
- AI 출력은 확정 정보가 아닌 사용자가 검토할 초안입니다.
- 유사 게시물 매칭, 채팅, 알림과 반환 완료 흐름은 아직 구현되지 않았습니다.
- 운영 배포 설정과 공유 이미지 저장소는 제공하지 않습니다.

## 문서

- [AI 프로토타입 및 평가](./backend/app/integrations/ai/README.md)
- [게시글 API](./backend/app/posts/README.md)
- [채팅 모듈](./backend/app/chat/README.md)
- [Frontend](./frontend/README.md)
- API 명세: Backend 실행 후 <http://127.0.0.1:8000/docs>
