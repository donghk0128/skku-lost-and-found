# Phase 3–4: BigQuery Raw → dbt → 대시보드

설계 판단, 실패와 복구, EC2 적용 순서는 [분석 파이프라인 구축 기록](analytics-implementation-log.md)에 정리했다. 이 문서는 모델·지표 정의와 검증 범위를 기준으로 삼는다.

## 범위와 실행 순서

이 브랜치는 최신 `develop`의 Raw 다섯 테이블을 입력으로 삼는다. Airflow DAG는 `begin_analytics`가 대시보드 상태를 `RUNNING`으로 바꾼 뒤 다섯 Raw 동기화 작업을 실행한다. 모두 성공해야 `build_analytics`가 `dbt build`를 실행한다. dbt 모델 또는 검사가 실패하면 상태는 `FAILED`, 모두 통과하면 `READY`다. 대시보드는 가장 최근 상태가 `READY`일 때만 Mart를 읽는다. 원본 하드 삭제는 다음 성공한 Raw 적재에서 삭제되고, dbt 모델은 모두 뷰이므로 파생 결과에도 반영된다. 소프트 삭제 게시글은 `deleted_at`을 유지한다.

2026-11-28 BigQuery 메타데이터 조회에서는 Raw 행 수가 `event_logs=0`, `posts=83`, `return_pairs=0`, `recommendation_runs=6`, `recommendation_items=147`이었다. 메타데이터 조회만으로 원본 DB와의 동시 일치나 쿼리 결과의 정확성을 확인한 것은 아니다. 현재 이벤트·확인 쌍 지표는 빈 상태로 표시해야 한다.

운영 분석 데이터 세트 `skku_finder_analytics`는 Raw와 같은 `asia-northeast3`에 생성했다. 2026-11-29 사용자 승인 후 Airflow 서비스 계정 `skku-airflow-loader@project-2d59f32a-6674-4fa9-9a4.iam.gserviceaccount.com`에 **이 데이터 세트 한정** Data Editor (`WRITER`) 권한을 부여하고 재조회로 확인했다. 같은 계정의 로컬 ADC를 사용해 운영 Raw에 대한 `dbt build`를 실행했고, 12개 뷰 생성과 33개 데이터 검사가 모두 통과했다. EC2에서는 기존 Airflow 메타데이터를 유지하면서 별도 작업 폴더 `~/skku-dbt-capacity/airflow`의 Compose로 전환했다. 기존 WIF/ADC 설정을 재사용하고, 이미 검증한 dbt 포함 이미지를 Airflow 이미지로 지정했다. 운영 `pipeline_status` 테이블과 12개 분석 뷰가 만들어졌고, 수동 전체 DAG 실행이 `success`로 종료됐다.

로컬에서 dbt만 실행하려면 `dbt-bigquery`를 설치하고 `GCP_PROJECT_ID`, `BIGQUERY_DATASET`, `BIGQUERY_ANALYTICS_DATASET`, `BIGQUERY_LOCATION`, ADC를 설정한 뒤 `dbt build --project-dir dbt --profiles-dir dbt`를 실행한다. 이 직접 실행은 대시보드의 `pipeline_status`를 갱신하지 않으므로 검증 결과를 운영 대시보드로 공개하려면 Airflow DAG로 실행한다. 대시보드는 **로컬 Streamlit**으로 사용한다. `dashboard/.env.example`을 `dashboard/.env`로 복사해 프로젝트·분석 데이터 세트·호스트 ADC 파일 경로를 채운 뒤 `dashboard/`에서 `docker compose up --build -d`를 실행하고 `http://127.0.0.1:8501`을 연다. 서버에 상시 대시보드 컨테이너를 추가하지 않는다. 대시보드 계정에는 분석 데이터 세트의 읽기 권한과 BigQuery Job User만 부여하는 구성이 목표다. 서비스 운영 데이터와 실험 데이터는 별도 BigQuery 데이터 세트로 격리한다.

## 모델과 지표

| 모델 | 의미 |
| --- | --- |
| `stg_*` | Raw 다섯 테이블의 컬럼 정리. 원본 삭제가 보이도록 뷰 사용 |
| `int_recommendation_events` | 실행·후보·순위가 일치하는 실제 노출/클릭 이벤트만 연결 |
| `int_confirmed_pairs` | `CONFIRMED`이고 `confirmed_at`이 있는 반환 쌍만 유지 |
| `mart_service_daily` | KST 일별 화면/게시글 조회·생성, 검색·필터, 채팅 시작, 반환 신고, 쌍 확인 이벤트 수와 이벤트가 있는 사용자 수 |
| `mart_recommendation_daily` | KST 일별 후보 노출 수, 클릭 수, 클릭 수 ÷ 노출 수 |
| `mart_algorithm_daily` | 같은 지표를 실행 기록의 알고리즘 버전별로 집계 |
| `mart_confirmed_pair_rank` | 확인된 쌍의 게시글을 기준으로 생성된 각 추천 실행에서 상대 글의 순위. 없으면 `matched_rank`가 NULL |
| `mart_raw_health` | 다섯 원본 테이블의 현재 행 수와 원본에서 기록된 최신 시각 |
| `mart_post_inventory` | 분실·습득 유형별 진행 중·완료·삭제 게시글과 AI 보조 작성 건수. 삭제 표시된 글은 진행·완료·AI 보조 작성 건수에서 제외 |
| `mart_recommendation_generation` | 알고리즘 버전별 저장된 추천 실행·후보 수, 실행당 평균 후보 수, 후보가 0개인 실행 수. 실제 노출·클릭 수와 구분 |

클릭/노출의 분자는 수집된 `recommendation_click` 이벤트 수, 분모는 수집된 `recommendation_impression` 이벤트 수다. 분모가 0이면 NULL이다. 이 값은 후보 이벤트 비율이며 사용자별 전환율이 아니다. `recommendation_runs`는 캐시된 실행 ID를 재사용할 수 있으므로 노출의 분모로 쓰지 않는다. `chat_started`와 `return_completed`에는 추천 `run_id`가 없어 클릭→채팅→반환의 인과 전환율을 계산할 수 없다. 대시보드는 이들을 별도 전체 건수로 표시한다. 신규 가입, 임베딩 성공률도 Raw 다섯 테이블에 근거가 없어 표시하지 않는다.

`mart_confirmed_pair_rank`는 **사용자가 확인한 쌍과 추천 실행이 동시에 존재하는 경우**만 포함한다. 이 기록은 독립 검증된 실제 반환이 아니고, 쌍을 등록하지 않은 반환이 빠져 있다. 따라서 전체 서비스 `Recall@K`나 알고리즘 성과로 표현하지 않는다. 추후 지표로 쓰려면 확인된 쌍 중 평가 대상이 된 실행의 범위와 시점, 누락된 레이블의 편향을 함께 정의해야 한다.

이벤트 기록은 기능 성공 후 별도로 시도하므로 유실될 수 있다. 이벤트 수와 활성 사용자 수는 관찰 가능한 하한이다. `mart_raw_health.latest_source_at`은 마지막 *원본 변경 시각*이므로 새 행동이 없으면 오래된 값이 정상일 수 있다. 파이프라인 실행 최신성은 `pipeline_status.recorded_at`을 확인한다. 빈 테이블은 0행과 NULL 최신 시각으로 표시한다.

## 검증 기준과 아직 필요한 현장 확인

dbt는 Raw 키 유일성·필수 필드·반환 상태, 추천 실행/후보 참조, 후보 복합키와 순위 유일성, 추천 이벤트의 실행·후보·순위 일치, 확인된 반환 쌍의 게시글 유형을 검사한다. 한 검사라도 실패하면 대시보드 상태가 `READY`가 되지 않는다. 테스트용 데이터는 운영 Raw에 넣지 않고 별도 데이터 세트에서 실행한다.

2026-11-28 로컬 검증에서는 Airflow+dbt 이미지를 빌드했고 dbt 1.11.17/BigQuery adapter 1.11.3으로 12개 모델·33개 테스트·5개 원본을 경고 없이 파싱했다. 기존 로컬 ADC를 읽기 전용으로 마운트한 실제 BigQuery 연결에서도 `dbt compile`이 성공했다. 이 작업은 모델 SQL 컴파일이며 BigQuery에 뷰를 만들거나 테스트 쿼리를 실행한 것은 아니다. Airflow 3 DAG를 실제 로더로 읽어 import 오류가 없고, `begin_analytics` → Raw 다섯 작업 → `build_analytics` 의존성을 확인했다. 일회용 PostgreSQL 17/pgvector에 전체 Alembic 마이그레이션을 적용한 뒤 데이터가 든 `event_logs`·`return_pairs`, 게시글 수정·소프트 삭제, 원본 이벤트·게시글 하드 삭제의 추출·키 스캔을 실행했다. Airflow 테스트 10개가 통과했다. 부분 적재 후 삭제 단계가 한 번 실패하고 재실행하는 경로는 **모의 BigQuery 클라이언트**에서 검증했으므로 실제 BigQuery의 실패 복구 증거는 아니다. 일회용 DB는 검증 후 제거했다.

2026-11-29에는 EC2의 **별도 작업 폴더와 별도 Docker 이미지**에서 기존 Airflow 컨테이너를 교체하지 않고 `dbt compile`과 `dbt build`를 실행했다. 512 MiB 제한에서 컴파일 최대 RSS는 246.7 MiB, 운영 Raw를 입력으로 쓰되 별도 분석 테스트 데이터 세트에 뷰를 만든 `dbt build`는 45/45 성공·최대 RSS 252.5 MiB였다. 이어서 [합성 Raw SQL](synthetic-raw-fixture.sql)을 로컬 `bq`에서 직접 BigQuery의 별도 Raw 테스트 데이터 세트에 실행하고, 서버에서 45/45 재성공·최대 RSS 252.1 MiB를 확인했다. 이 합성 데이터는 EC2로 전송한 파일이 아니며 운영 Raw에도 넣지 않았다.

합성 Mart의 실제 조회 결과는 노출 2, 클릭 1, 클릭/노출 0.5였다. `fixture-v1`은 노출 1·클릭 1, `fixture-v2`는 노출 1·클릭 0이었다. 채팅 시작·반환 신고·확정 이벤트는 각각 1건이고, `PENDING` 반환 쌍은 확인된 쌍 모델에 포함되지 않았다. Raw 테스트 데이터 세트에서 확정 쌍과 관련 이벤트를 삭제한 뒤 파생 뷰의 쌍 순위와 확인 이벤트 수가 모두 0이 되는 것을 조회했고, 이후 합성 입력을 복원했다. 테스트 분석 데이터 세트에만 수동 `READY` 상태를 기록한 뒤 Streamlit AppTest로 대시보드를 실행해 예외 0개, 표 5개, **합성 검증 데이터 경고**를 확인했다. 이 수동 상태는 Airflow 통합 실행의 증거가 아니다.

두 테스트 데이터 세트는 `asia-northeast3`에 있고 테이블 기본 만료를 1일로 설정했다. 실제 청구액은 아직 확인하지 않았다. 2026-11-29 로컬 Streamlit 화면을 다시 검증해 합성 데이터 경고, 표 5개, 반환 쌍 ID를 노출하지 않는 집계 표시, 예외 0개를 확인했다. 운영 BigQuery 분석 데이터 세트에서의 독립 `dbt build`는 45/45 통과했다. EC2의 첫 DAG 실행은 새 로그 폴더를 쓸 수 없어 실패했다. 폴더 소유권을 Airflow 실행 계정으로 맞춘 뒤, 수동 전체 동기화의 Raw 다섯 작업이 모두 통과했다. 이어 dbt가 읽기 전용 프로젝트 마운트에 `target`과 `logs`를 쓰려다 실패한 것을 같은 조건의 로컬 Docker에서 재현했다. dbt 출력 경로를 `/tmp`로 바꿔 파싱·상태 게이트 테스트를 통과시켰고, 서버의 자동 재시도는 모델 12개·검사 33개 모두 성공해 DAG 전체가 `success`, `pipeline_status`가 `READY`로 끝났다. 종료 뒤 서버의 사용 가능 메모리는 750 MiB, 사용 중인 스왑은 426 MiB, 남은 디스크는 4.8 GiB였다. 운영 Mart의 행 수는 `event_logs=0`, `posts=83`, `return_pairs=0`, `recommendation_runs=6`, `recommendation_items=147`이다. 로컬 Streamlit을 운영 분석 데이터로 전환한 뒤 AppTest 예외 0개·성공 표시 1개와 HTTP 상태 `ok`를 확인했다. 현재 운영 데이터에는 이벤트와 확정 반환 쌍이 없어 관련 성과 표는 빈 상태가 정상이다. 두 번째 수동 전체 적재 후 최신 상태가 다시 `READY`가 됐고 Mart 행 수는 같았다. 공개 API `/api/v1/health`는 HTTP 200이었다. 이후 동일 시간 구간의 증분 재실행과 통제된 BigQuery 작업 사이 실패·복구를 테스트 데이터 세트에서 확인했다. Phase 2의 운영 원본 데이터 변경·삭제와 EC2 재부팅 복구는 아직 별도 관찰이 필요하다. 재부팅이나 운영 DB 변경을 수반하는 검증은 영향과 복구 절차를 먼저 정한다.

### 대시보드 보강과 실제 BigQuery 복구 시험 (2026-11-29)

운영 Raw에서 확인 가능한 게시글 현황과 추천 **생성** 현황을 추가했다. 합성 데이터 세트와 운영 데이터 세트에서 dbt 14개 뷰·37개 데이터 검사, 총 51/51이 각각 통과했다. 합성 데이터에서 두 유형의 완료 게시글이 각 1개, 두 알고리즘 버전의 추천 생성·후보가 각 1개임을 조회했다. 새 Streamlit 화면은 합성 데이터에서 표 7개·요약 수치 4개·경고 표시·예외 0개였고, 운영 데이터에서는 진행 중 게시글 83개, 추천 생성 기록 6건, 생성 후보 147건을 표시했다. 이 생성 기록은 사용자 화면 노출 수로 해석하지 않는다.

`airflow/tests/bigquery_recovery_probe.py`는 `_test_`가 포함된 BigQuery 데이터 세트에서만 실행되며, 고유한 임시 대상 테이블을 종료 시 삭제한다. EC2의 읽기 전용 운영 PostgreSQL을 입력으로 쓰고 테스트 분석 데이터 세트에 게시글 83행을 적재한 뒤 **같은 시작·종료 시각으로 증분 재실행**해 행 수가 유지됨을 확인했다. 실제 BigQuery `MERGE` 뒤 `DELETE` 직전에 의도적으로 예외를 주입하자 시험용 잔여 행 1개가 남았다. 같은 구간으로 재실행하자 잔여 행이 0개, 대상 83행이 됐다. 이는 실제 BigQuery 작업 사이에서 발생한 애플리케이션 실패의 복구 검증이다. BigQuery 서비스 자체 장애나 운영 Raw에서의 실패를 관찰한 것은 아니다. EC2 재부팅 후 자동 복구와 운영 원본의 새 수정·삭제는 아직 별도 검증 항목이다.
