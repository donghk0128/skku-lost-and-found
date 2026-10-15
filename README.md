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

## 게시글 사진: 로컬 Docker 볼륨

Compose는 백엔드에 `post_images_data` 볼륨을 연결합니다. 사진 파일은 이 볼륨에 저장하고, 게시글과 파일의 연결 정보는 PostgreSQL의 `post_images` 테이블에 저장합니다. 사진 때문에 별도 저장소 서비스나 API 키를 설정할 필요는 없습니다. 위의 `docker compose up --build -d`와 `alembic upgrade head` 명령으로 준비됩니다.

사진을 올릴 때는 먼저 로그인해 게시글을 작성하고 Swagger의 `POST /api/v1/posts/{post_id}/images`에서 파일을 선택합니다. `GET /api/v1/posts/{post_id}/images`는 사진 목록과 읽기 주소를 반환합니다.

`docker compose down`으로 컨테이너를 중지해도 볼륨의 사진은 남습니다. 볼륨을 삭제하면 사진 파일은 사라지므로, 보관할 사진이 생긴 뒤에는 볼륨 삭제 전에 백업해야 합니다. 각 팀원의 볼륨은 각자의 컴퓨터에 따로 있습니다.

배포 시에는 사진 저장 부분(`backend/app/posts/storage.py`)을 Supabase Storage나 AWS S3 구현으로 교체할 수 있습니다. DB에는 공급자 URL 대신 `<게시글 ID>/<파일 ID>.png` 형태의 `storage_key`를 저장하므로 게시글 API 경로는 유지할 수 있습니다. 배포 서버의 저장소 키는 서버 환경 변수로만 제공하고, 보존할 로컬 사진이 있다면 별도로 옮겨야 합니다.

## 의존성 버전

- Python: 3.12.15
- PostgreSQL: 17.11
- `backend/requirements.txt`: 필요한 패키지와 허용 범위
- `backend/requirements.lock`: Docker 이미지가 설치하는 고정 버전
