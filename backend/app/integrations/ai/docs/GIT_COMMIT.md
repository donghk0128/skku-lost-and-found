# Git Commit Message Convention

커밋 메시지는 변경 의도를 빠르게 파악할 수 있도록 Gitmoji와 Conventional Commits 형식을 사용합니다.

## 작성 전 확인

커밋을 요청받았을 때만 커밋하며, 먼저 다음 내용을 확인합니다.

```sh
git status --short
git diff --staged --stat
git diff --staged
```

- staged 변경만 커밋 메시지의 근거로 사용합니다.
- 관련 없는 변경을 한 커밋에 포함하지 않습니다.
- 테스트를 실행하지 않았거나 실패했다면 커밋 메시지에서 성공했다고 표현하지 않습니다.
- 비밀값과 개인 정보가 staged 파일에 포함되지 않았는지 확인합니다.

## 형식

```text
<gitmoji> <type>(<scope>): <subject>

<body>

<footer>
```

`scope`, `body`, `footer`는 필요할 때만 사용합니다. 제목은 영어로 작성합니다.

## 제목 규칙

- 하나의 Gitmoji로 시작합니다.
- 허용된 `type`을 사용합니다.
- 명령형 현재 시제로 작성합니다. 예: `add`, `fix`, `update`
- 첫 글자를 대문자로 쓰지 않습니다.
- 마침표로 끝내지 않습니다.
- 50자 이내를 권장합니다.
- `scope`는 실제 변경 모듈명으로 작성합니다. 예: `auth`, `posts`, `frontend`, `docs`

## Type과 Gitmoji

| Gitmoji | Type | 용도 |
|---|---|---|
| ✨ | `feat` | 사용자 기능 추가 |
| 🐛 | `fix` | 버그 수정 |
| 📝 | `docs` | 문서 변경 |
| 🎨 | `style` | 동작을 바꾸지 않는 형식 변경 |
| ♻️ | `refactor` | 기능 변경 없는 구조 개선 |
| ⚡ | `perf` | 성능 개선 |
| ✅ | `test` | 테스트 추가 또는 수정 |
| 🔧 | `chore` | 빌드, 설정, 보조 도구 변경 |
| 🔖 | `release` | 릴리스 |

## 본문과 Footer

- 본문에는 구현 방법의 나열보다 변경 이유와 이전 동작과의 차이를 작성합니다.
- 호환성을 깨는 변경은 `BREAKING CHANGE:`로 표시합니다.
- 이슈가 확인된 경우에만 `Closes #123` 또는 `Fixes #123`을 사용합니다.

## 예시

```text
✨ feat(posts): add image upload endpoint

Allow authors to attach persisted images to lost-and-found posts.

Closes #78
```

```text
📝 docs(readme): document local development flow
```

## 금지 사항

- diff에 없는 변경을 메시지에 포함하지 않습니다.
- 여러 Gitmoji 또는 여러 type을 한 제목에 사용하지 않습니다.
- `update files`, `fix stuff`처럼 범위가 불명확한 제목을 사용하지 않습니다.
- 사용자의 명시적 요청 없이 `git commit`, `push`, rebase를 실행하지 않습니다.
