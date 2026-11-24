# 후보순 평가 데이터 준비

## 실험 기록 위치

버전별 가설·실측 결과·해석은 [`experiments/`](experiments/)에 날짜별 Markdown으로 남깁니다. 첫 실험은 [`hybrid-v2 기준선`](experiments/2026-11-19-airpods-v2.md)과 [`hybrid-v3 재시험`](experiments/2026-11-19-airpods-v3.md)에 기록했습니다. 다음 실험에는 [`TEMPLATE.md`](experiments/TEMPLATE.md)를 복사해 사용합니다. Git에는 익명화한 결과와 설명을 올리고, 실제 게시글 UUID가 포함된 `labels.csv`는 올리지 않습니다. `result.json`은 개발 DB와 별도 보관한 뒤 공개할 때 식별 정보가 없는지 검토합니다.

이 파일은 서버에 자동으로 글을 등록하지 않습니다. 팀원이 웹의 **일반 작성**으로 아래 글을 등록한 뒤, 실제 ID로 정답표를 만듭니다. 글 제목에 공통 `[TEST]` 접두사를 붙이면 문자열 점수가 왜곡되므로 붙이지 않습니다. 실제 사용자가 적을 법한 표현을 사용합니다. 테스트 계정 두 개를 사용하면 한 계정은 기준 글, 다른 계정은 후보 글을 작성할 수 있습니다.

| 코드 | 유형 | 물품명 / 제목 | 설명 | 카테고리 | 장소·시간 | 정답 관계 |
|---|---|---|---|---|---|---|
| F1 | 습득 | 에어팟 / 삼성학술정보관 앞 검은 에어팟 습득 | 검은 케이스에 초록 스티커가 붙어 있습니다 | 전자기기 | 삼성학술정보관 앞, 11월 18일 14시 | L1과 같은 물건 |
| L1 | 분실 | 무선 이어폰 / 검은 에어팟을 잃어버렸습니다 | 케이스에 초록색 스티커가 있어요 | 전자기기 | 삼성학술정보관, 11월 18일 13~15시 | F1과 같은 물건 |
| L2 | 분실 | 에어팟 / 흰 에어팟 분실 | 흰색 케이스이며 표시가 없습니다 | 전자기기 | 학생회관, 11월 18일 14시 | F1의 혼동 후보 |
| L3 | 분실 | 지갑 / 검은 반지갑을 잃어버렸습니다 | 학생증이 들어 있습니다 | 지갑 | 삼성학술정보관 앞, 11월 18일 14시 | F1의 혼동 후보 |
| L4 | 분실 | 열쇠 / 파란 고리 열쇠 분실 | 열쇠 세 개가 달려 있습니다 | 열쇠 | 제2공학관, 11월 16일 10시 | F1의 다른 후보 |
| F2 | 습득 | 지갑 / 학생회관 앞 검은 지갑 습득 | 학생증과 카드가 들어 있습니다 | 지갑 | 학생회관, 11월 17일 18시 | L5와 같은 물건 |
| L5 | 분실 | 지갑 / 학생회관에서 검은 지갑 분실 | 학생증과 카드가 들어 있는 반지갑입니다 | 지갑 | 학생회관, 11월 17일 17~19시 | F2와 같은 물건 |
| F3 | 습득 | 지갑 / 도서관 검은 지갑 습득 | 현금만 들어 있습니다 | 지갑 | 삼성학술정보관, 11월 17일 18시 | L5의 혼동 후보 |
| F4 | 습득 | 열쇠 / 공학관 열쇠 꾸러미 습득 | 파란색 고리에 세 개의 열쇠 | 열쇠 | 제2공학관, 11월 16일 11시 | L5의 다른 후보 |

F1을 기준으로 **분실했어요** 탭의 L1~L4를, L5를 기준으로 **습득했어요** 탭의 F1~F4를 확인합니다. 장소는 가능하면 좌표까지 입력하고, 날짜·시간은 실제 입력한 값을 정답표에 같이 적습니다. `GEMINI_API_KEY`가 설정돼 있어도 호출 실패 시에는 벡터가 없을 수 있으므로 `post_embeddings` 존재 여부를 확인합니다. 이 예시는 기능 확인용 작은 시작 데이터입니다. 포트폴리오 지표에는 더 많은 정답 쌍과 혼동 후보를 추가하고, 알고리즘 변경 전에 평가 집합을 고정합니다.

`labels.csv`는 **비교할 모든 후보 쌍**을 다음 형식으로 작성합니다. `1`은 같은 물건, `0`은 다른 물건입니다. 예를 들어 F1 기준에는 L1~L4 네 줄을 모두 기록합니다. L5 기준에는 F1~F4 네 줄을 기록합니다. 등록 후 받은 실제 UUID를 넣습니다.

```csv
source_post_id,candidate_post_id,label
<F1의 UUID>,<L1의 UUID>,1
<F1의 UUID>,<L2의 UUID>,0
```

실험 명령은 백엔드 폴더에서 실행합니다.

```sh
python -m scripts.evaluate_matching --labels evaluation/labels.csv --output evaluation/result.json
```

EC2 배포 Compose를 쓰는 경우에는 서버의 저장소 루트에서 아래처럼 실행합니다. `backend/evaluation/labels.csv`를 서버에 준비한 뒤 실행하면 결과가 같은 폴더의 `result.json`에 남습니다. 실제 글 ID가 담긴 `labels.csv`는 Git에 추가하지 않습니다.

```sh
docker compose -f compose.deploy.yaml run --rm -v "$(pwd)/backend/evaluation:/app/evaluation" backend python -m scripts.evaluate_matching --labels /app/evaluation/labels.csv --output /app/evaluation/result.json
```

평가 도구는 DB를 읽기만 하며 Gemini 호출이나 게시글 수정은 하지 않습니다. 모든 비교 글에 호환되는 벡터가 있어야 각 방식의 지표를 공정하게 비교할 수 있습니다. 출력에는 실제 게시글 ID를 넣지 않고 익명 코드, 정답 여부, 개별 점수와 집계 지표를 남깁니다. 이 파일을 개발 DB와 별도로 보관하면 가중치 변경 전후를 다시 비교할 수 있습니다. `labels.csv`는 실제 게시글 ID가 들어 있으므로 Git에 올리지 않습니다. 포트폴리오에는 익명화한 입력 예시와 지표·해석을 함께 보관합니다.

## 고정 양방향 벤치마크 v1

[`benchmark_v1.json`](benchmark_v1.json)은 정답 12쌍, 게시글 24개를 정의합니다. 분실→습득 12질의와 습득→분실 12질의에서 각 질의는 반대 유형 12개를 모두 비교합니다(총 288쌍). 각 질의의 정답은 정확히 하나입니다. 물품명 동의어, 같은 카테고리의 다른 물건, 유사한 색·특징, 같은 건물의 다른 층, 좌표 누락을 포함합니다. 좌표는 **실제 건물 위치를 측량한 값이 아닌 통제된 시험점**입니다. 이 데이터와 결과를 실제 서비스 정확도 주장에 그대로 사용하지 않습니다.

`scripts.seed_matching_benchmark`는 기본적으로 데이터 검증만 합니다. `--apply`를 지정했을 때만 개발 PostgreSQL에 진행 중인 글을 만들고 Gemini 임베딩을 생성합니다. 기존 시험 계정 UUID를 `--lost-author-id`로 전달하고, 필요하면 `--found-author-id`를 따로 전달합니다. 운영 DB에는 실행하지 마세요. 서버의 백엔드 환경에 `DATABASE_URL`과 `GEMINI_API_KEY`가 있어야 합니다. 글 ID는 데이터셋과 코드에서 결정되므로 재실행 시 같은 글을 재사용하고, 일부만 있으면 중단합니다. 등록이 끝나면 Git에서 제외되는 `labels.csv`를 자동 생성합니다.

백엔드 디렉터리에서 실행하는 명령:

```sh
python -m scripts.seed_matching_benchmark
python -m scripts.seed_matching_benchmark --apply --lost-author-id <시험계정UUID>
python -m scripts.evaluate_matching --labels evaluation/labels.csv --output evaluation/result.json
```

평가 도구는 동일한 게시글·임베딩에 대해 `hybrid_v3`, `no_color`(색상 감점 없음), `no_color_low_text`(문자열 축소와 임베딩 가중치 증가), `missing_geo_reweighted`(v4: 대표 좌표가 없으면 위치 가중치 제외), `hybrid_v5`(복수 장소 중 최소 거리)의 전체·방향별 지표를 계산합니다. v3·v4 비교 점수는 대표 좌표 기준으로 재구성하므로 복수 장소를 가진 글에서도 v5와 비교할 수 있습니다. 기존 고정 벤치마크 v1에는 복수 장소가 없어 v4와 v5의 차이를 측정할 수 없습니다. `result.json`에는 게시글 UUID 대신 E1 등의 평가 코드가 표시됩니다.

`scripts.evaluate_location_scenarios`는 기존 `result.json`의 임베딩 점수와 정답표를
재사용해 [`location_scenarios_v1.json`](location_scenarios_v1.json)의 추가 핀을
가상으로 적용합니다. DB·Gemini 호출 없이 v4와 v5의 순위 변화를 살피는
반사실 스트레스 테스트이며, 실제 복수 장소 게시글에 대한 성능 지표는 아닙니다.
실행 방법과 해석은 [`2026-11-24 실험 기록`](experiments/2026-11-24-multi-location-v5.md)에 남깁니다.

## 복수 장소 평가셋 v1

[`benchmark_multi_location_v1.json`](benchmark_multi_location_v1.json)은 새 정답
8쌍과 게시글 16개를 정의합니다. 각 글은 반대 유형 후보 8개와 비교하므로
분실→습득과 습득→분실을 합쳐 128개 라벨이 생깁니다. `locations`는 순서가
있는 가능한 장소 목록이며 `anchor`가 있는 장소만 좌표 핀입니다. 첫 장소가
텍스트만 있어도 뒤 장소의 좌표가 v5에 들어가는 사례를 포함합니다. 좌표는
통제된 시험점이며 실제 건물 측량값이 아닙니다.

등록 전에는 아래 명령으로 파일만 검증합니다. 등록은 개발 DB에서만 실행하며,
기존 평가셋의 `labels.csv`와 덮어쓰지 않도록 별도 라벨·결과 파일을 사용합니다.
새 글 16개의 임베딩 생성에 Gemini 호출이 필요합니다. 서버 실행 절차는 별도
작업 디렉터리의 최신 브랜치 파일을 연결한 일회성 컨테이너를 기준으로 합니다.

```sh
python -m scripts.seed_matching_benchmark --dataset evaluation/benchmark_multi_location_v1.json --labels evaluation/multi_location_labels.csv
python -m scripts.seed_matching_benchmark --dataset evaluation/benchmark_multi_location_v1.json --labels evaluation/multi_location_labels.csv --apply --lost-author-id <시험계정UUID>
python -m scripts.evaluate_matching --labels evaluation/multi_location_labels.csv --output evaluation/multi_location_result.json
```

평가 명령은 DB를 읽기만 합니다. 화면에는 v4(`missing_geo_reweighted`)와
v5(`hybrid_v5`)의 전체·방향별 지표와 정답 순위 변화를 짧게 표시하고, 다른
방식과 각 비교 쌍의 상세 점수는 결과 JSON 파일에 보관합니다. 실행 전 가설과
해석 기준은 [`2026-11-24 실험 기록`](experiments/2026-11-24-multi-location-v5.md)에
정리했습니다.
