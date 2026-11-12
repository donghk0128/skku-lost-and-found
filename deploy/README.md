# EC2 백엔드 배포

백엔드는 평소 각자의 컴퓨터에서 개발하고 테스트합니다. 팀에서 배포할 코드를 `main`에 반영하면, 배포 담당자가 EC2에서 최신 코드를 받아 서버를 다시 실행합니다. GitHub에 코드를 올리는 것만으로 EC2 서버가 자동 업데이트되지는 않습니다.

## 로컬과 EC2에서 쓰는 파일

- 로컬: 저장소 루트에서 `docker compose up --build -d`를 실행합니다. 기본 파일인 `compose.yaml`이 PostgreSQL과 FastAPI를 함께 띄웁니다.
- EC2: `docker compose -f compose.deploy.yaml up -d --build`를 실행합니다. FastAPI와 Caddy를 띄우며, DB는 `backend/.env`에 적힌 팀 Supabase PostgreSQL을 사용합니다.
- `deploy/Caddyfile`은 Caddy가 받은 HTTPS 요청을 FastAPI로 전달하는 설정입니다. 프론트는 Caddy의 공개 주소로 요청하고, FastAPI의 8000번 포트는 인터넷에 열지 않습니다.

두 환경 모두 같은 백엔드 코드와 Dockerfile을 사용합니다. 달라지는 것은 실행 구성과 DB 연결 주소입니다. EC2의 업로드 사진은 Docker 볼륨에 저장되므로 서버를 교체하거나 삭제할 때는 사진 볼륨을 별도로 확인해야 합니다.

## 팀에서 변경 사항을 반영하는 순서

1. 각자 기능 브랜치에서 수정하고 로컬에서 테스트합니다.
2. PR을 `develop`에 병합합니다. 여러 기능을 함께 확인한 뒤 배포할 때 `develop`을 `main`에 병합합니다.
3. 배포 담당자가 EC2에서 `main`을 받아 Compose로 백엔드를 다시 만듭니다.
4. 공개 주소의 `/api/v1/health`와 변경된 API를 확인합니다.

프론트에서 배포 서버를 사용하려면 `frontend/.env.local`의 `EXPO_PUBLIC_API_URL`을 `https://skku-finder-api.duckdns.org/api/v1`로 설정하고 Expo를 다시 시작합니다. 로컬 백엔드를 테스트할 때는 각자 로컬 주소를 사용하면 됩니다.

## EC2에 한 번 설정할 것

- DuckDNS의 `skku-finder-api.duckdns.org`를 EC2 공인 IPv4에 연결합니다. EC2를 중지했다가 켜서 IP가 바뀌면 DuckDNS도 갱신합니다.
- 보안 그룹에서는 HTTP 80과 HTTPS 443을 공개하고, SSH 22는 접속할 사람의 IP로 제한합니다. 백엔드 8000과 DB 5432는 공개하지 않습니다.
- EC2의 `backend/.env`에는 팀 Supabase의 Session pooler 주소를 `DATABASE_URL=postgresql+psycopg://...?...sslmode=require` 형식으로 넣고, JWT·SMTP·AI 설정도 입력합니다. 필요한 항목은 `backend/.env.example`을 참고합니다.
- 저장소 루트의 `.env`에는 `APP_DOMAIN=skku-finder-api.duckdns.org`를 넣습니다. 두 `.env` 파일 모두 Git에 올리지 않습니다.
- 기존 사진 볼륨 `skku-post-images`와 Caddy 인증서 볼륨 `skku-caddy-data`, `skku-caddy-config`를 유지합니다. `compose.deploy.yaml`은 이 볼륨들이 이미 있다고 가정합니다.

현재 AI 게시글 작성은 OpenAI API 또는 Ollama 방식입니다. OpenAI를 쓸 때는 EC2의 `backend/.env`에 실제 키와 모델 설정이 필요합니다. Gemini로 바꾸려면 주소만 수정하는 것으로는 부족하고 백엔드 연동 코드도 바꿔야 합니다.

## 처음 Compose 배포로 전환할 때

배포 파일이 `main`에 반영된 뒤 EC2의 `~/skku-lost-and-found`에서 실행합니다. 위의 `.env` 파일과 Docker 볼륨을 먼저 확인하세요.

```sh
git pull --ff-only origin main
sudo docker volume ls --format '{{.Name}}' | grep -E '^skku-(post-images|caddy-data|caddy-config)$'
sudo docker compose -f compose.deploy.yaml config --quiet
sudo docker stop skku-caddy skku-finder-api
sudo docker rm skku-caddy skku-finder-api
sudo docker compose -f compose.deploy.yaml up -d --build
curl -fsS https://skku-finder-api.duckdns.org/api/v1/health
```

앞의 `stop`과 `rm`은 현재 수동으로 띄운 컨테이너를 Compose 관리로 옮기는 첫 배포에만 필요합니다. 컨테이너를 삭제해도 Docker 볼륨은 유지되지만, `docker compose down -v`나 볼륨 삭제 명령은 실행하지 마세요.

## 이후 `main`을 다시 배포할 때

```sh
cd ~/skku-lost-and-found
git pull --ff-only origin main
sudo docker compose -f compose.deploy.yaml build backend
sudo docker compose -f compose.deploy.yaml run --rm backend alembic current
# 새 DB 마이그레이션을 확인한 뒤 필요한 경우 실행
sudo docker compose -f compose.deploy.yaml run --rm backend alembic upgrade head
sudo docker compose -f compose.deploy.yaml up -d --no-deps --force-recreate backend
curl -fsS https://skku-finder-api.duckdns.org/api/v1/health
```

새 웹 프론트 주소가 생기면 `backend/.env`의 `CORS_ALLOWED_ORIGINS`에 그 출처를 추가합니다. SMTP·AI 키나 모델 설정처럼 `.env` 값을 바꾼 뒤에도 백엔드 컨테이너를 다시 만들어야 반영됩니다. EC2는 메모리와 디스크가 작으므로 배포 전 여유 공간을 확인하세요.
