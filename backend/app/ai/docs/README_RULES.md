# README 작성 규칙

README는 사람을 위한 프로젝트 안내서입니다. 에이전트의 작업 규칙은 `AGENTS.md`에 두고 README에는 프로젝트 이해, 실행과 운영에 필요한 사실만 작성합니다.

## 1. 근거 자료

README 작성 전에 실제 저장소에서 다음 항목을 확인합니다.

- 프로젝트 루트의 디렉터리와 파일
- `pyproject.toml`, `requirements*.txt`, `package.json`, lock 파일
- `Dockerfile`, Compose 파일, 배포 스크립트
- `.env.example`, 설정 모듈과 환경 변수 참조
- `main.py`, `app.py`, `__main__.py`, package script 등 진입점
- API router, DB model, migration과 테스트
- 현재 Git diff와 구현 상태

## 2. 필수 원칙

1. 실제 파일, 코드와 설정으로 확인한 정보만 작성합니다.
2. 존재하지 않는 파일, 환경 변수, 명령, 링크와 배포 환경을 만들지 않습니다.
3. 목표 기능은 `계획`, `진행 중`, `구현` 상태를 구분합니다.
4. 실행 명령은 저장소 루트를 기준으로 복사해 실행할 수 있게 작성합니다.
5. 테스트 결과는 실제 실행한 명령과 결과만 기록합니다.
6. 비밀값은 예시에도 넣지 않고 `.env.example` 수준의 placeholder를 사용합니다.
7. 디렉터리 트리는 핵심 구조만 보여 주되 표시한 경로는 모두 존재해야 합니다.
8. 고유명사와 코드 식별자를 제외하고 한국어로 간결하게 작성합니다.
9. 동일한 상세 설명이 별도 문서에 있으면 중복하지 말고 상대 링크를 제공합니다.
10. 템플릿의 `{placeholder}`, 안내 주석과 빈 섹션은 최종 문서에 남기지 않습니다.

## 3. 권장 구조

프로젝트 특성에 맞지 않는 하위 항목은 생략할 수 있습니다.

```markdown
# 1. 프로젝트 이름

배경, 해결하려는 문제와 목표를 3~6줄로 설명합니다.

## 구현 현황
| 영역 | 상태 | 내용 |
|---|---|---|

# 2. Problem Definition
## 2.1 주요 문제
## 2.2 제약 사항
## 2.3 기술 선택 근거

# 3. Architecture Overview
## 3.1 현재 시스템 구조
## 3.2 데이터 또는 요청 흐름
## 3.3 주요 의존성

# 4. Directory Structure
## 4.1 Project Tree
## 4.2 Folder Roles

# 5. Configuration
## 5.1 Environment Variables
## 5.2 Config Files
## 5.3 Development vs Production

# 6. Quick Start
## 6.1 Requirements
## 6.2 Installation
## 6.3 Run
## 6.4 Test & Verification

# 7. Operations Guide
## 7.1 Deployment
## 7.2 Restart
## 7.3 Logs
## 7.4 Routine Tasks

# 8. Troubleshooting & Caveats
## 8.1 Common Issues
## 8.2 Known Caveats

# Documentation
```

## 4. 작성 기준

### 프로젝트 소개

- 대상 사용자와 해결할 문제를 먼저 설명합니다.
- 홍보성 표현보다 현재 제공하는 가치를 씁니다.
- 장기 비전은 현재 구현처럼 표현하지 않습니다.

### Architecture

- 코드 계층, 요청 흐름, DB와 외부 서비스를 실제 구조대로 표시합니다.
- 현재 구조와 목표 구조가 다르면 별도로 나눕니다.
- ASCII diagram은 관계를 이해하는 데 도움이 될 때만 사용합니다.

### Configuration

환경 변수 표에는 다음 정보를 포함합니다.

| Name | Required | Description | Safe example |
|---|---|---|---|
| `ENV_NAME` | Yes/No | 용도 | 비밀이 아닌 예시 |

- 코드 기본값과 `.env.example`이 다르면 그 차이를 명시합니다.
- 실제 토큰, 비밀번호, 개인 이메일과 운영 DB 주소는 쓰지 않습니다.

### Quick Start

- 설치, migration, 실행, 상태 확인 순서로 작성합니다.
- 개발·staging·production 명령이 실제로 각각 존재할 때만 구분합니다.
- OS별 차이가 확인된 경우에만 별도 명령을 제공합니다.

### Operations

- 실제 Compose 또는 배포 스크립트를 기준으로 작성합니다.
- 로그가 표준 출력이면 존재하지 않는 로그 파일 경로를 만들지 않습니다.
- 볼륨 삭제처럼 데이터 손실 가능성이 있는 작업은 경고와 백업 조건을 먼저 씁니다.

### Troubleshooting

각 항목은 증상, 원인, 해결 순서로 작성합니다. 코드에서 확인되지 않은 해결책은 단정하지 않습니다.

## 5. 완료 점검

```sh
rg -n "\{[^}]+\}|TODO|TBD" README.md
git diff --check -- README.md
git diff -- README.md
```

추가로 다음을 확인합니다.

- 모든 상대 링크와 경로가 존재합니다.
- 명령의 실행 위치가 명확합니다.
- 구현 상태와 로드맵이 구분되어 있습니다.
- 테스트 성공 여부가 실제 결과와 일치합니다.
- 문서에 비밀값과 개인 정보가 없습니다.
