# SKKU Lost & Found

## 로컬 백엔드 실행

Docker Desktop을 실행한 뒤 저장소 최상위 폴더에서 명령을 실행합니다. Compose는 FastAPI 백엔드와 로컬 PostgreSQL을 함께 실행합니다. 로컬 실행에 팀 Supabase 접속 정보는 필요하지 않습니다.

```sh
docker compose up --build -d
docker compose run --rm backend alembic upgrade head
```

- API 상태 확인: http://127.0.0.1:8000/api/v1/health
- API 문서: http://127.0.0.1:8000/docs

테스트는 별도의 메모리 SQLite DB를 사용합니다.

```sh
docker compose run --rm backend python -m pytest -q
```

작업을 마치면 컨테이너를 종료합니다.

```sh
docker compose down
```

PostgreSQL 데이터는 Docker의 `postgres_data` 볼륨에 보관되어 컨테이너를 다시 시작해도 유지됩니다.

## 의존성 버전

- Python: 3.12.15
- PostgreSQL: 17.11
- `backend/requirements.txt`: 필요한 패키지와 허용 범위
- `backend/requirements.lock`: Docker 이미지가 설치하는 고정 버전