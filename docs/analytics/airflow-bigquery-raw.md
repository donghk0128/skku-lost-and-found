# Phase 2: PostgreSQL → Airflow → BigQuery Raw

## 현재 상태와 범위

Phase 1의 이벤트 로그와 반환 정답 쌍 변경 사항은 `develop`에 병합됐다. Phase 2 브랜치는 아직 PR을 올리지 않았다. EC2에서는 이 브랜치의 특정 커밋을 분리된 작업 디렉터리에서 시험 운영 중이며, 기존 백엔드 배포에 Airflow가 포함된 것은 아니다.

EC2의 Docker에서 실행하는 DAG는 허용 목록에 있는 다섯 테이블, `event_logs`, `posts`, `return_pairs`, `recommendation_runs`, `recommendation_items`만 읽는다. BigQuery Raw에는 ID, 이벤트·분류·상태 값, 시각, 순위 점수 등을 저장한다. 비밀번호, 토큰, 이메일, 연락처, 채팅 내용, 게시글 제목·설명, 위치 문자열·좌표, 이미지 데이터·스토리지 키, 임베딩, 검색어는 조회하지 않는다. 이벤트의 `properties`는 JSON 문자열로 복사하며, Phase 1에서 허용 키를 제한한다. `return_pairs`에는 승인 대기 행도 들어가므로, 확정된 반환을 집계할 때는 `status = 'CONFIRMED'`로 걸러야 한다.

적재 대상은 서울 리전(`asia-northeast3`)의 `project-2d59f32a-6674-4fa9-9a4.skku_finder_raw` 데이터 세트다. 첫 적재 전에 데이터 세트 위치를 확인했다.

## Raw 데이터 삭제 정책 (2026-11-26 합의)

Phase 2의 다섯 Raw 테이블은 Supabase PostgreSQL을 원본으로 삼는다. 회원 탈퇴 등을 통해 원본 행이 실제로 삭제되면 다음 **성공한 동기화**에서 대응하는 BigQuery Raw 행도 삭제한다. 하루 단위의 최종 일치 방식이므로 탈퇴 요청 즉시 BigQuery 행을 지우는 구조는 아니다. 소프트 삭제된 게시글은 원본과 마찬가지로 `deleted_at` 값을 가진 채 Raw에 남는다. 삭제된 사용자의 이벤트나 추천 행을 분석용으로 예외 보존하지 않는다.

이 정책의 범위는 Raw 테이블이다. Phase 3 전에 파생 모델과 실제 집계 통계가 탈퇴를 어떻게 반영할지 결정해야 하며, 사용자별 행을 묵시적으로 남겨서는 안 된다. 실사용자 데이터를 운영하기 전에는 보관 기간과 운영상 삭제 완료 기한도 정해야 한다. BigQuery의 time travel 및 fail-safe 보관 때문에 활성 테이블의 행 삭제가 모든 저장 계층에서 즉시 물리적으로 지워졌다는 뜻은 아니다.

## 실행 준비와 인증

1. GCP 프로젝트와 BigQuery 데이터 세트를 만들거나 선택하고, 데이터 세트 위치를 `BIGQUERY_LOCATION`에 설정한다. 데이터 세트 생성, IAM 변경, 과금될 수 있는 작업은 팀과 확인한다.
2. 원본 DB에는 애플리케이션 스키마의 `USAGE`와 다섯 테이블에 필요한 `SELECT`만 가진 전용 계정을 사용한다. SSL 연결 문자열을 설정한다. 이 계정은 테이블 소유권이나 쓰기 권한이 없어야 한다. 적재 코드에서도 읽기 전용 트랜잭션을 강제한다.
3. GCP 서비스 계정 `skku-airflow-loader`에는 프로젝트 범위의 BigQuery Job User와 **Raw 데이터 세트에 한정된** BigQuery Data Editor를 부여한다. 프로젝트 정책이 사용자 관리 서비스 계정 키 생성을 차단하므로 이를 해제하지 않는다.
   - 로컬 개발에서는 Google Cloud CLI를 설치하고, 로그인한 개발자에게 이 서비스 계정에 한정된 Service Account Token Creator 권한을 부여한다. `gcloud auth application-default login --impersonate-service-account skku-airflow-loader@project-2d59f32a-6674-4fa9-9a4.iam.gserviceaccount.com`으로 단기 토큰을 사용하는 ADC 파일을 만든다. Git에서 제외된 `.env`의 `GCP_ADC_FILE`에 호스트의 ADC 파일 경로를 지정하면 Compose가 컨테이너에 읽기 전용으로 마운트한다. 이 파일에도 사용자 갱신 자격증명이 있으므로 공유하거나 커밋하지 않는다.
   - EC2 시험 운영은 JSON 서비스 계정 키 대신 AWS → GCP Workload Identity Federation을 사용한다. EC2의 `skku-airflow-ec2` 역할이 `skku-airflow` 풀의 `aws-ec2` 공급업체를 거쳐 `skku-airflow-loader`를 가장하도록 제한했다. `--aws --enable-imdsv2` 옵션으로 자격증명 *구성 파일*을 만들고 Git에서 제외된 `airflow/secrets/`에 복사한 뒤 `GCP_ADC_FILE`로 마운트했다.
4. `airflow/.env.example`을 `airflow/.env`로 복사하고 실제 설정값을 채운다. `.env`와 `secrets/`는 Git에서 제외한다. 자격증명을 DAG 코드나 로그에 넣지 않는다. `openssl rand -hex 32`로 `AIRFLOW_JWT_SECRET`을 한 번 생성한다. API 서버와 스케줄러가 동일한 값을 사용해야 작업 실행을 인증할 수 있다. 스케줄러는 Compose 서비스 이름으로 별도 API 서버에 연결한다.
5. `airflow/`에서 `docker compose up --build`를 실행한다. 로컬 Airflow UI는 `127.0.0.1:8080`에만 바인딩된다. DAG는 처음에 일시 중지 상태다. 원본 DB 권한, BigQuery 데이터 세트, 인증, 예상 비용을 확인한 후 활성화한다.

현재 Compose 파일은 **EC2 시험 운영용**이며 운영 환경의 보안·복구 구성을 완성한 배포 계획은 아니다. Airflow는 Supabase와 분리된 PostgreSQL 메타데이터 DB를 사용한다. EC2에서는 DAG 프로세서가 로그를 쓰도록 호스트의 `airflow/logs` 소유자를 이미지의 Airflow 사용자(`50000:0`)로 맞춰야 했다. 스케줄러의 `AIRFLOW__CORE__EXECUTION_API_SERVER_URL`은 별도 API 서버를 가리켜야 하고 모든 Airflow 서비스가 같은 JWT 비밀값을 사용해야 한다. 이 설정이 없을 때는 동기화 함수에 들어가기 전 작업이 실패했다.

## 적재와 복구 방식

DAG는 UTC 기준 매일 실행하고 동시에 활성화되는 실행은 하나로 제한한다. 첫 실행에서는 BigQuery 대상 테이블이 없으므로 전체 적재한다. 수동 실행에 `{"full_refresh": true}`를 전달해도 다섯 Raw 테이블을 전체 갱신한다. 이후 실행에서는 해당 실행 구간에 변경된 행을 하루 겹치는 기간까지 읽고, 원본 키를 기준으로 BigQuery `MERGE`를 수행한다. `catchup`이 켜져 있어 Airflow가 중단됐다가 재개되면 놓친 일별 구간도 예약한다. 과거 구간 재실행에도 같은 병합 경로를 사용한다.

적재기는 반복 읽기 가능한 동일한 DB 스냅샷에서 **원본 키 전체**도 조회한다. PostgreSQL에서 사라진 키의 BigQuery 행을 삭제하므로, 수정 시각만으로는 알 수 없는 회원 탈퇴 등의 하드 삭제를 반영한다. 소프트 삭제된 게시글은 `deleted_at` 값과 함께 남는다. 각 테이블 적재 뒤 원본·대상 행 수, 대상 키의 유일성, 양방향 키 집합 차이를 확인한다. 검증 실패 시 작업을 실패 처리하고 재시도한다. 첫 실행이 실패하면 불완전한 대상 테이블을 제거하여 재시도 때 다시 전체 적재하게 한다.

전체 키 조회와 BigQuery 삭제 쿼리의 비용은 데이터가 커질수록 늘어난다. 현재 규모에서는 정확성을 위해 이 방식을 택했으며, 규모가 커지면 변경 데이터 캡처(CDC)나 삭제 표시 기록을 고려해야 한다. 스냅샷 이후 도착한 원본 데이터는 후속 구간에서 반영된다. 놓친 과거 구간이나 과거 데이터 수정이 의심되면 해당 구간을 재실행하거나 전체 갱신한다. SQL 조회와 BigQuery 작업은 배치 처리이며 실시간 스트리밍은 아니다.

## 검증 결과와 남은 확인

- `0018_return_pairs`까지 마이그레이션한 격리된 PostgreSQL 컨테이너에서 다섯 원본 쿼리를 실행했다. 통합 검증은 전체·증분 추출, 게시글 수정, 하드 삭제된 이벤트 키를 다뤘고 테스트용 트랜잭션은 롤백했다. 이 검증에는 `RUN_SOURCE_INTEGRATION_TESTS=1`과 폐기 가능한 `SOURCE_DATABASE_URL`이 필요하다.
- 로컬의 서비스 계정 가장 ADC로 Airflow 이미지에서 BigQuery 대상 데이터 세트를 읽고, 처리 바이트가 0인 드라이런 쿼리를 제출했다. 이 단계에서 Raw 테이블은 만들지 않았다.
- 2026-11-27 KST, EC2 시험 환경에서 읽기 전용 Supabase 계정으로 다섯 원본 쿼리를 실행했다. 같은 Airflow 이미지에서 AWS → GCP 연동 인증으로 대상 데이터 세트를 읽고 처리 바이트가 0인 BigQuery 쿼리 작업을 제출했다.
- 첫 예약 실행(UTC `2026-11-25`)은 다섯 Raw 테이블을 만들고 성공했다. 다음 예약 실행(UTC `2026-11-26`)은 증분 경로를 실행해 성공했다. 18시간 연속 가동 후 UTC `2026-11-27`의 자동 실행도 성공했다. 각 작업은 행 수, 대상 키 유일성, 양방향 키 차이를 검사한다. 2026-11-27에 별도로 다시 조회한 원본·대상 행 수도 일치했다.

  | 테이블 | Supabase | BigQuery |
  | --- | ---: | ---: |
  | `event_logs` | 0 | 0 |
  | `posts` | 83 | 83 |
  | `return_pairs` | 0 | 0 |
  | `recommendation_runs` | 5 | 5 |
  | `recommendation_items` | 103 | 103 |

- 첫 두 실행 이후 공개 API 상태 확인은 HTTP 200이었다. `t3.small`(스왑 2 GiB, 루트 볼륨 20 GiB)의 적재 후 측정값은 사용 가능한 RAM 611 MiB, 사용 중인 스왑 269 MiB, 남은 디스크 5.4 GiB였다. Airflow 컨테이너 재시작이나 OOM 종료는 없었다. **현재 데이터 규모에서의 시험 운영 가능성**을 보여주지만 데이터 증가나 재부팅 후 안정성을 보장하지는 않는다.
- 2026-11-27 UTC 09:32에 백엔드는 `healthy`, 공개 API 상태 확인은 HTTP 200이었다. Airflow 서비스는 18시간 연속 실행 중이었고 사용 가능한 RAM은 777 MiB, 사용 중인 스왑은 460 MiB, 남은 디스크는 5.2 GiB였다. EC2의 Airflow 이미지에서 Raw 경계와 증분 삭제 로직에 관한 단위 테스트 4개가 모두 통과했다.
- 같은 날 CLI로 만든 수동 실행은 Airflow가 `data_interval_start`를 작업 컨텍스트에 넣지 않아 동기화 함수 호출 전에 실패했다. 수동 실행의 기준 시각을 사용하도록 DAG를 로컬에서 수정했고, 해당 시각 계산을 별도로 검증했다. 수정된 DAG는 아직 EC2에 반영하지 않았으므로 수동 재실행 검증은 남아 있다. 정기 실행에는 영향이 없었다.
- 실제 수정 행, 동일 구간 재실행, 과거 데이터 정정, 소프트·하드 삭제, 데이터가 들어 있는 `event_logs`와 `return_pairs`, 적재 실패 후 복구는 추가 확인이 필요하다. 재부팅 후 자동 복구도 관찰해야 한다. 공유 서비스 데이터가 바뀌는 검증은 격리된 테스트 데이터로 수행한다.
- 2026-11-27 조회 시 최근 24시간의 이 서비스 계정 작업은 69건(쿼리 56건, 적재 13건)이었다. BigQuery가 보고한 쿼리 처리량은 245,035바이트, 과금 기준 처리량은 566,231,040바이트(540 MiB)였다. 다섯 Raw 테이블의 현재 저장량 합계는 24,350바이트였다. 이 수치에는 시험 작업도 섞일 수 있으므로 일별 DAG만의 비용이나 실제 청구액으로 해석하지 않는다. 운영 비용은 이후 [BigQuery 요금 안내](https://cloud.google.com/bigquery/pricing)와 실제 청구 내역을 함께 확인한다.
