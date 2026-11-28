# 분석 파이프라인 구축 기록

2026-11-28~29에 SKKU Finder의 PostgreSQL 원본에서 BigQuery Raw, dbt Mart, Airflow, 로컬 Streamlit 대시보드까지 연결한 과정과 판단 근거를 기록한다. 명령 출력에서 확인한 사실과 아직 검증하지 않은 사항을 구분한다. 모델 SQL과 지표 정의는 [dbt·대시보드 문서](dbt-dashboard.md), Phase 2의 초기 적재·인증 구성은 [Airflow·BigQuery Raw 문서](airflow-bigquery-raw.md), 수집 이벤트의 의미는 [이벤트 기록 문서](event-logging.md)를 기준으로 한다. 인증 파일 내용과 접속 문자열은 기록하지 않는다.

## 범위와 설계 판단

| 결정 | 관찰한 제약과 선택 근거 | 적용한 방식 |
| --- | --- | --- |
| 분석 데이터 경로 | 게시글·추천·이벤트의 구조화된 데이터를 배치로 집계한다. 이미지 저장 경로는 이 분석 작업의 입력이 아니다. | PostgreSQL → EC2 Airflow → BigQuery Raw 다섯 테이블 → dbt → Streamlit. 분석 적재에 S3 단계를 추가하지 않았다. 이미지 저장소 이전은 별도 작업이다. |
| Raw와 Mart 분리 | 운영 DB에는 서비스 기능용 데이터와 분석용 집계가 섞여 있다. | Raw는 허용한 다섯 테이블의 분석 가능 필드만 적재한다. dbt는 Staging·Intermediate·Mart 12개 뷰로 계산한다. |
| 뷰 사용 | 현재 데이터가 작고, 원본 하드 삭제가 다음 적재 후 파생 결과에도 반영돼야 한다. | Mart를 별도 복제 테이블이 아닌 BigQuery 뷰로 만들었다. 조회 시 원본을 다시 읽으므로 데이터가 커지면 쿼리 비용·속도를 재평가해야 한다. |
| 추천 지표 | `recommendation_runs`는 캐시된 실행 ID를 재사용할 수 있어 실제 화면 노출 수와 다르다. | 노출·클릭은 검증된 `event_logs`의 후보별 이벤트만 센다. 클릭÷노출은 후보 이벤트 비율이며 사용자 전환율이 아니다. |
| 반환 지표 | 채팅 완료가 항상 게시글 쌍의 확인을 뜻하지 않는다. `return_pairs`의 `PENDING`은 정답으로 볼 수 없다. | 양측 확인과 `confirmed_at`이 있는 `CONFIRMED` 쌍만 별도 Mart에 넣는다. 레이블 누락 편향 때문에 이를 전체 서비스 `Recall@K`로 부르지 않는다. |
| 빈 데이터 표시 | 운영 Raw의 `event_logs`와 `return_pairs`가 모두 0행이다. 실제 성과를 보여줄 근거가 없다. | 해당 Mart와 대시보드는 빈 상태를 명시한다. 합성 데이터를 별도 Raw·분석 데이터 세트에 넣고 경고 문구로 구분한다. |
| 배포 위치 | 기존 EC2는 RAM 약 1.9 GiB, 스왑 2 GiB이며 API와 Airflow가 함께 돈다. | dbt는 기존 Airflow 이미지에 포함하고 DAG에서 한 번에 하나씩 실행한다. Streamlit은 EC2에 상시 추가하지 않고 로컬 Docker에서 띄운다. |
| 공개 조건 | Raw만 성공하거나 dbt 검사가 실패한 시점의 Mart를 검증된 결과로 보여줄 수 없다. | DAG가 `RUNNING` → Raw 다섯 작업 → `dbt build` → `READY` 순으로 상태를 기록한다. dbt 실패는 `FAILED`; 대시보드는 가장 최근 상태가 `READY`일 때만 Mart를 읽는다. |
| GCP 권한 | 서비스 계정 키 생성이 조직 정책으로 막혀 있었고, 분석 결과의 쓰기 권한은 Raw와 구분해야 했다. | 기존 AWS 역할 → GCP Workload Identity Federation → Airflow 서비스 계정 경로를 재사용했다. 사용자 승인 후 분석 데이터 세트에만 BigQuery Data Editor를 부여했다. |

## 구현과 검증 순서

1. 최신 `develop`에서 `feat/analytics-marts-dashboard` 작업 브랜치를 만들었다. 기존 Phase 2 문서의 로컬 미커밋 변경은 보존하고 분석 브랜치에 필요한 내용을 반영했다. 운영 서버의 `develop` 체크아웃은 분석 브랜치로 바꾸지 않았다.
2. Raw 다섯 테이블을 dbt source로 선언하고 Staging 5개, Intermediate 2개, Mart 5개 뷰를 만들었다. Raw 키 유일성·필수값·참조 관계와 추천 이벤트의 실행·후보·순위 일치, 확정 반환 쌍의 게시글 유형 등을 검사하는 33개 테스트를 추가했다. 데이터가 오래됐다는 사실과 파이프라인이 오래 실행되지 않았다는 사실을 구분하기 위해 원본 최신 시각과 `pipeline_status.recorded_at`을 따로 표시한다.
3. Airflow DAG에 `begin_analytics`와 `build_analytics`를 넣고 Raw 다섯 작업이 모두 성공한 뒤 dbt를 실행하도록 연결했다. 로컬에서 DAG import와 의존성을 확인했다. 일회용 PostgreSQL 17/pgvector에 Alembic 마이그레이션을 적용해 값이 있는 이벤트·반환 쌍, 게시글 수정·소프트 삭제, 이벤트·게시글 하드 삭제의 추출·키 스캔을 확인했다. Airflow 테스트 10개가 통과했다. 부분 적재 후 삭제 단계 실패와 재실행은 모의 BigQuery 클라이언트에서만 검증했다.
4. EC2의 별도 작업 폴더와 이미지에서 운영 Airflow를 교체하지 않고 dbt를 먼저 시험했다. 512 MiB 컨테이너 제한에서 `parse` 최대 RSS 241.7 MiB, `compile` 246.7 MiB였다. 운영 Raw를 입력으로 별도 분석 테스트 데이터 세트에서 실행한 `dbt build`는 45/45 성공, 최대 RSS 252.5 MiB였다. 따라서 현재 작은 데이터에서는 실행 가능하다고 판단했지만 장기 용량을 보장하는 수치는 아니다.
5. 로컬의 합성 fixture SQL을 `bq`로 BigQuery의 별도 Raw 테스트 데이터 세트에 직접 실행했다. 파일을 EC2에 복사하거나 운영 Raw에 넣지 않았다. 합성 입력을 대상으로 한 EC2 `dbt build`는 45/45 성공, 최대 RSS 252.1 MiB였다. 실제 Mart 조회에서 노출 2, 클릭 1, 비율 0.5, 채팅·반환·확정 이벤트 각 1건을 확인했다. `PENDING` 쌍은 제외됐다. 확정 쌍과 관련 이벤트를 테스트 Raw에서 삭제하자 뷰의 쌍 순위와 확인 이벤트가 0이 됐고, fixture를 복원했다.
6. 합성 분석 데이터 세트에만 수동 `READY`를 기록해 Streamlit을 확인했다. AppTest에서 예외 0개, 표 5개, 합성 데이터 경고와 반환 쌍 ID를 노출하지 않는 집계 표시를 확인했다. 이 수동 상태는 Airflow 통합 실행의 증거로 쓰지 않았다.
7. 운영 분석 데이터 세트를 서울 리전에 만들고, 사용자 승인 후 Airflow 서비스 계정에 해당 데이터 세트 한정 `WRITER` 권한을 부여했다. 재조회로 반영을 확인했다. 로컬의 서비스 계정 가장 ADC로 운영 Raw → 운영 분석 데이터 세트 `dbt build`를 실행해 12개 뷰와 33개 테스트가 모두 성공했다. 이 독립 실행은 `pipeline_status`를 갱신하지 않으므로 대시보드 공개 완료로 취급하지 않았다.

## EC2 적용 중 실패와 복구

| 단계 | 증상과 확인 근거 | 원인 판단·조치 | 결과 |
| --- | --- | --- | --- |
| EC2 시험 폴더 생성 | `git fetch origin feat/analytics-marts-dashboard`는 성공했지만 `origin/feat/analytics-marts-dashboard`를 가리킨 `git worktree add`는 `invalid reference`로 실패했다. 이어 작업 폴더가 없어 Docker 빌드 컨텍스트를 찾지 못했고 이미지 실행도 실패했다. | 이 서버의 fetch가 원격 추적 브랜치를 만들지 않고 `FETCH_HEAD`만 갱신한 것을 확인했다. `git worktree add --detach ... FETCH_HEAD`로 수정하고 각 단계가 성공한 뒤 다음 명령을 실행했다. | 별도 worktree와 dbt 시험 이미지를 만들었다. 앞선 Docker 오류는 dbt 코드 오류가 아니라 잘못된 작업 경로에서 이어진 결과였다. |
| 배포 경로 확인 | 서버의 `~/skku-lost-and-found`는 `develop`이어서 새 `airflow/compose.yaml`이 없었다. 실행 중인 스케줄러의 Compose 작업 폴더는 `~/skku-airflow-trial/airflow`였다. | 기존 서비스 폴더를 덮지 않고 이미 dbt 용량 시험에 쓴 `~/skku-dbt-capacity` worktree를 최신 브랜치로 갱신했다. 기존 `.env`를 복사하고 WIF 구성 파일은 기존 경로에서 읽기 전용으로 마운트했다. `docker compose config --quiet`로 설정을 확인했다. | 원본 서버 체크아웃과 기존 Airflow 메타데이터 볼륨을 유지했다. |
| 이미지 교체 | 루트 디스크 여유가 약 4.8 GiB였고, dbt 포함 시험 이미지가 이미 있었다. | 기존 Airflow 이미지에 복구용 태그를 붙이고 시험을 통과한 이미지를 Airflow 태그로 지정해 `--no-build`로 재생성했다. | 이미지 재빌드 없이 Airflow API 서버·DAG processor·scheduler가 올라왔다. |
| 첫 전체 실행 | 수동 `full_refresh=true` 실행에서 `begin_analytics`가 실패했다. 새 작업 폴더에 task 로그가 없었고 DAG processor에는 `/opt/airflow/logs/dag_processor/...` 파일 생성 오류가 남았다. | Compose가 새 작업 폴더의 로그 경로를 마운트한 상태에서 Airflow 실행 계정이 로그를 쓸 수 없었다. 새 `logs` 폴더만 컨테이너 실행 UID/GID로 소유권을 바꾸고 processor와 scheduler를 재시작했다. | `logs_writable`을 확인했고 다음 실행에서 `begin_analytics`가 성공했다. 기존 폴더의 로그는 변경하지 않았다. |
| dbt 첫 시도 | 두 번째 전체 실행에서 Raw 다섯 작업은 성공했지만 `build_analytics`가 종료 코드 2로 재시도 대기에 들어갔다. 처음 task 로그에는 dbt의 상세 원인이 없었다. | dbt 프로젝트는 Compose에서 `:ro`로 연결했는데 코드가 기본 `logs`·`target` 경로를 사용했다. 같은 읽기 전용 마운트에서 기존 명령의 조용한 실패를 재현하고, 로그 경로만 바꿨을 때 `target` 생성의 `Read-only file system` 오류를 확인했다. `--log-path /tmp/dbt-logs --target-path /tmp/dbt-target --no-partial-parse`를 추가해 파싱과 회귀 테스트를 통과시켰다. | 서버 worktree의 bind mount 코드를 갱신한 후 자동 재시도에서 dbt 45/45 성공, DAG `success`, 최신 `pipeline_status=READY`가 됐다. |
| API 상태 확인 | 서버 호스트의 `127.0.0.1:8000/api/v1/health`는 연결되지 않았으나 백엔드 컨테이너는 `healthy`였다. | 운영 Compose는 백엔드 8000 포트를 호스트에 공개하지 않고 Caddy가 내부 네트워크에서 프록시한다. 실제 공개 주소의 `/api/v1/health`에 GET 요청을 보냈다. | 공개 API가 HTTP 200, `{"status":"ok"}`를 반환했다. 호스트의 8000 포트 연결 실패를 서비스 장애로 분류하지 않는다. |

## 확인된 결과와 남은 검증

- 첫 성공한 EC2 전체 실행은 Raw 다섯 작업과 dbt 뷰 12개·검사 33개를 통과했다. dbt 로그는 `PASS=45 WARN=0 ERROR=0 SKIP=0`이고 DAG가 `success`, 최신 상태가 `READY`였다. 실행 직후 가용 RAM은 750 MiB, 스왑 사용량은 426 MiB, 디스크 여유는 4.8 GiB였다.
- 운영 Mart의 Raw 행 수는 `event_logs=0`, `posts=83`, `return_pairs=0`, `recommendation_runs=6`, `recommendation_items=147`이다. 이벤트와 확정 반환 쌍 지표가 빈 상태인 것은 이 데이터에 부합한다. 사용자별 클릭→채팅→반환 인과 전환율, 신규 가입, 임베딩 성공률은 현재 Raw만으로 계산하지 않는다.
- 로컬 Streamlit을 운영 분석 데이터 세트로 전환했다. AppTest에서 예외 0개, 성공 표시 1개, 데이터 품질 표 1개와 나머지 빈 상태 안내 4개를 확인했고, HTTP health는 `ok`였다. 로컬 주소는 `http://127.0.0.1:8501`이다.
- 같은 원본을 대상으로 두 번째 수동 `full_refresh=true` 실행을 시작했고, 최신 `pipeline_status`가 다시 `READY`가 된 것을 확인했다. Mart의 Raw 행 수는 첫 성공 실행과 같은 `0/83/0/6/147`이었다(`event_logs/posts/return_pairs/recommendation_runs/recommendation_items` 순). 두 수동 실행은 `run_after`가 서로 달라 동일 시간 구간의 증분 재실행 증거로 쓰지 않는다. 두 번째 Airflow `dag_run`의 최종 상태는 서버 메타데이터에서 별도로 조회하지 않았다.
- 이후 테스트 데이터 세트에서 실제 BigQuery `MERGE`와 오류 주입 후 복구, 동일 구간 증분 재실행을 확인했다. 운영 DB의 새 수정·삭제 반영, 운영 Raw에서 발생한 실제 장애, EC2 재부팅 후 자동 복구는 아직 관찰하지 않았다. 격리 시험 결과를 운영 장애를 직접 겪은 증거로 표현하지 않는다.
- 비용은 서비스 계정 작업의 2026-11-27 기준 24시간 과금 대상 쿼리량 540 MiB와 Raw 저장량 약 24 KB를 기록했지만, 실제 청구액은 확인하지 않았다. 무료 한도와 다른 프로젝트 사용량은 청구 계정 전체 기준으로 봐야 한다.

## 대시보드 보강과 실제 BigQuery 재처리 시험 (2026-11-29)

운영 `event_logs`와 `return_pairs`가 비어 있어 행동·반환 성과를 더 그릴 근거는 없다. 대신 실제로 데이터가 있는 `posts`, `recommendation_runs`, `recommendation_items`에서 게시글 유형·상태별 현황과 알고리즘별 추천 생성·후보 현황을 추가했다. 생성 기록을 노출이나 클릭으로 표현하지 않도록 새 Mart와 화면에 구분 문구를 넣었다. 합성·운영 BigQuery에서 dbt 14개 뷰와 37개 테스트가 각각 51/51 통과했고, 로컬 운영 대시보드에는 진행 중 게시글 83개, 추천 생성 기록 6건, 생성 후보 147건이 표시됐다.

동일 구간 증분 재실행과 부분 실패 복구는 운영 Raw를 일부러 실패시키지 않고 `skku_finder_analytics_test_20261128`의 고유 임시 테이블에서 검증했다. EC2의 원본 PostgreSQL은 읽기 전용으로 접근했다. 임시 테이블에 게시글 83행을 전체 적재하고, 동일한 `start`·`end`로 증분 동기화를 다시 실행해 83행 유지와 키 일치를 확인했다. 이어 임시 행 하나를 넣고 **실제 BigQuery `MERGE` 성공 직후, `DELETE` 실행 직전에** 예외를 주입했다. 잔여 행 1개가 남음을 확인한 뒤 같은 구간을 재실행하자 83행과 잔여 행 0개로 복구됐다. 임시 테이블은 삭제됐다. 이는 실제 BigQuery 작업을 이용한 통제된 애플리케이션 오류 시험이다. 운영 데이터의 부분 실패나 BigQuery 서비스 장애 자체를 관찰한 것으로 쓰지 않는다.

## EC2 재부팅 검증 계획

- **예상 영향:** 재부팅 동안 공개 API와 Airflow가 잠시 중단된다. 진행 중인 DAG 작업이 있으면 실패하거나 재시도할 수 있으므로 실행 중인 작업이 0개일 때만 시작한다. 로컬 Streamlit은 EC2에 없지만 BigQuery의 최신 상태를 표시하므로, 재부팅 중 새 `READY`가 생기지는 않는다.
- **사전 확인:** `skku_raw_sync`의 `queued`·`running` 실행 수가 0인지, 백엔드·Caddy·Airflow 컨테이너가 정상인지, BigQuery 최신 상태가 `READY`인지 확인한다. 현재 Compose 설정과 WIF 파일의 기존 경로를 유지한다. 기존 Airflow 이미지는 `skku-analytics-airflow:pre-dbt-20261129` 태그로 보관했다.
- **재부팅 후 합격 기준:** SSH 재접속, 백엔드와 Caddy·Airflow 컨테이너 재시작, 공개 `/api/v1/health` HTTP 200, Airflow DAG 등록·최근 실행 상태 확인, BigQuery 최신 `READY`와 Mart 조회 성공을 확인한다. 필요하면 증분 수동 DAG를 한 번 실행해 새 `READY`를 확인한다.
- **복구 순서:** 백엔드가 뜨지 않으면 `~/skku-lost-and-found`의 `compose.deploy.yaml` 상태와 로그를 확인하고 `sudo docker compose -f compose.deploy.yaml up -d --no-build`로 기존 서비스를 다시 올린다. Airflow가 뜨지 않으면 `~/skku-dbt-capacity/airflow`에서 `sudo docker compose up -d --no-build`를 실행하고 scheduler·api-server·dag-processor 로그를 확인한다. 자동 재시작 실패 원인을 확인하기 전에는 메타데이터 볼륨이나 이미지를 삭제하지 않는다.
