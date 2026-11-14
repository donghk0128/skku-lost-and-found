# 게시글 추천과 임베딩

`GET /api/v1/posts/{post_id}/recommendations`는 분실 글에 습득 글을, 습득 글에 분실 글을 추천합니다. `OPEN`이고 삭제되지 않은 후보만 사용하며 기본 5개, 최대 20개를 돌려줍니다. 응답의 `score`는 순위용 점수이지 같은 물건일 확률이 아닙니다.

## 추천이 만들어지는 과정

1. 게시글을 등록하면 제목·물건명·설명을 Gemini `gemini-embedding-001`에 보내 768차원 벡터를 한 번 만듭니다. 글의 텍스트가 바뀌면 다시 만들고, 장소·상태 등만 바뀌면 기존 벡터를 재사용합니다.
2. 벡터는 PostgreSQL의 `post_embeddings` 테이블에 저장합니다. 추천 요청 때 Gemini API를 다시 호출하지 않습니다.
3. 기존 규칙 점수(글자·카테고리·시간·거리)로 후보를 정렬해 상위 50개만 남깁니다. 이 후보 중 양쪽 글에 벡터가 있으면 pgvector의 코사인 유사도를 더합니다. 최종 점수는 `규칙 70% + 임베딩 30%`입니다.
4. 벡터가 없거나 Gemini 요청이 실패한 글은 기존 규칙 점수로 추천합니다. 삭제·완료된 글은 추천 후보에서 제외됩니다.

현재는 규칙 점수를 위해 후보 전체를 읽지만 벡터 계산은 최대 50개만 합니다. 글이 많아지면 DB에서 후보를 먼저 좁히고 벡터 인덱스를 검토해야 합니다. 모델을 바꾸면 서로 다른 모델의 벡터를 비교할 수 없으므로 기존 글도 다시 임베딩해야 합니다.

## 로컬 개발과 서버 설정

- 로컬 `compose.yaml`은 pgvector가 포함된 PostgreSQL 17 이미지를 사용합니다. EC2의 배포 Compose에는 DB가 없고 팀 Supabase PostgreSQL에 연결합니다.
- **두 DB에 각각** `alembic upgrade head`를 실행해 `0005_create_post_embeddings` 마이그레이션을 적용합니다. 마이그레이션은 `vector` 확장을 활성화하고 벡터 테이블을 만듭니다.
- `backend/.env`의 `GEMINI_API_KEY`에 Gemini API 키를 넣으면 새 게시글부터 임베딩됩니다. 키가 없으면 규칙 추천만 사용합니다. 키는 프론트 환경 변수나 Git에 넣지 않습니다.
- 배포 전에는 기존 로컬 PostgreSQL Docker 볼륨을 백업하세요. `docker compose down -v`는 기존 DB 데이터를 지우므로 사용하지 않습니다.

기능 도입 전에 작성한 글에는 벡터가 없습니다. 기존 글은 규칙 기반 점수로 추천하며, 새로 등록하거나 텍스트를 수정한 글부터 임베딩을 만듭니다.

로컬 테스트에서는 API 키를 비워 외부 Gemini 호출을 막습니다. 실제 pgvector 연산과 마이그레이션은 PostgreSQL 환경에서 별도로 확인해야 합니다.

```sh
docker compose run --rm -e GEMINI_API_KEY= backend python -m pytest -q
```
