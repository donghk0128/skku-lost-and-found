# Pull Request 생성 가이드

이 문서는 에이전트가 현재 브랜치의 실제 변경을 분석해 검토 가능한 PR 제목과 본문을 작성하는 절차를 정의합니다. PR 생성 또는 원격 작업은 사용자가 명시적으로 요청한 경우에만 수행합니다.

## 1. 기준 브랜치 결정

먼저 현재 브랜치와 사용 가능한 브랜치를 확인합니다.

```sh
git branch --show-current
git branch --all
git status --short
```

기본 기준은 다음과 같습니다.

| 현재 브랜치 | 기준 브랜치 |
|---|---|
| `feat/*`, `feature/*` | `develop` |
| `develop` | `main` |
| `fix/*`, `hotfix/*` | `main` |
| 그 외 | 자동 결정하지 말고 실제 분기점 또는 사용자 지정 확인 |

- 기준 브랜치가 존재하지 않으면 임의로 만들지 않습니다.
- 네트워크 작업인 `fetch`, `pull`, `push`는 요청 범위와 권한을 확인한 뒤 실행합니다.
- PR 본문 작성만 요청된 경우 rebase나 브랜치 변경을 수행하지 않습니다.

## 2. 변경 분석

`<base>`를 확인된 기준 브랜치로 바꾸어 실행합니다.

```sh
git log --oneline <base>..HEAD
git log --format="%h|%s|%b" <base>..HEAD
git diff --name-status <base>...HEAD
git diff --stat <base>...HEAD
git diff <base>...HEAD
```

확인할 내용:

- 사용자가 체감하는 기능 변화
- 버그 수정과 이전 동작
- API, DB migration, 환경 변수와 호환성 변화
- 보안 또는 데이터 손실 위험
- 테스트 추가 여부와 실제 검증 결과
- 리뷰어가 집중해야 할 복잡한 로직

커밋 제목만으로 판단하지 말고 최종 diff를 기준으로 작성합니다.

## 3. PR 제목

[GIT_COMMIT.md](./GIT_COMMIT.md)의 제목 형식을 사용합니다.

```text
<gitmoji> <type>(<scope>): <subject>
```

여러 커밋이 있으면 PR의 주된 사용자 가치 또는 변경 목적을 대표하는 하나의 제목을 선택합니다.

## 4. PR 본문 템플릿

해당 내용이 없는 섹션은 억지로 채우지 말고 생략합니다.

```markdown
# Pull Request

## Summary
- 변경 목적
- 핵심 결과

## Review Points
- 리뷰가 필요한 파일 또는 로직과 이유

## Changes
### Features
- 기능 변경

### Fixes
- 버그 수정

### Refactoring & Chores
- 구조, 설정 또는 문서 변경

## Test & Verification
- `실제로 실행한 명령`: 결과
- 실행하지 못한 검증과 이유

## Risks & Follow-ups
- migration, 환경 변수, 호환성 또는 후속 작업

## Checklist
- [ ] 제목이 커밋 규칙을 따릅니다.
- [ ] 최종 diff를 검토했습니다.
- [ ] 검증 결과를 사실대로 기록했습니다.
- [ ] 비밀값과 불필요한 디버그 코드를 포함하지 않았습니다.
```

## 5. 분류 규칙

| Type | Section |
|---|---|
| `feat` | Features |
| `fix` | Fixes |
| `refactor`, `chore`, `style`, `docs` | Refactoring & Chores |
| `perf` | Performance 섹션을 추가 |
| `test` | Test & Verification |
| `release` | Summary 및 Risks & Follow-ups |

## 6. 작성 원칙

- PR 본문은 한국어로, 코드 식별자와 명령은 원문으로 작성합니다.
- 커밋 해시 나열보다 동작 변화와 검토 포인트를 우선합니다.
- 실행하지 않은 테스트에 체크 표시를 하지 않습니다.
- 존재하지 않는 이슈, 배포 결과, 스크린샷과 링크를 만들지 않습니다.
- 자동 생성 문구나 템플릿 안내 주석은 최종 본문에서 제거합니다.
- PR을 실제 생성했다면 대상 브랜치와 URL을 결과에 포함합니다.
