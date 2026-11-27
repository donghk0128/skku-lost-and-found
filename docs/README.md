# 프로젝트 문서 안내

이 폴더는 서비스의 API와 데이터 분석 흐름을 설명합니다. 처음 보는 사람은 아래 순서대로 읽으면 데이터가 어디에서 만들어지고 어떻게 분석 저장소로 옮겨지는지 따라갈 수 있습니다.

1. [백엔드 API](./api/backend-api.md): 클라이언트가 호출하는 주요 API와 요청·응답.
2. [이벤트 로그와 반환 정답 쌍](./analytics/event-logging.md): 분석에 사용할 이벤트와 확정 반환 데이터의 수집 기준.
3. [Airflow → BigQuery Raw](./analytics/airflow-bigquery-raw.md): Supabase PostgreSQL의 데이터를 하루 단위로 옮기는 방식, 인증·삭제 정책, 실제 검증 결과.

코드와 함께 읽는 설명은 해당 구현 옆에 둡니다. [백엔드 배포](../deploy/README.md), [추천 평가](../backend/evaluation/README.md), [프런트엔드](../frontend/README.md) 문서를 참고하세요.
