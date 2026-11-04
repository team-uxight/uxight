# GACA-68 — Friction 판정 규칙 및 심각도

## 1. 목적과 구현 범위

Persona Agent의 행동 로그(`steps.jsonl`)에서 사용성 문제의 신호를 Python 규칙으로 탐지한다.

- Friction 유형: `navigation_confusion`, `interaction_failure`, `task_failure`, `excessive_steps`
- 판정 결과: 유형, 심각도, 근거 step 번호, 판정 사유
- 구현: `services/agent/uxight_agent/watcher/friction_rules.py`
- 테스트: `services/agent/tests/test_friction_rules.py`
- 탐지 함수: `detect_frictions(steps, status=None, excessive_steps_threshold=10)`

회차가 끝나면 이 규칙으로 진단을 만들어 `findings` 에 저장한다(GACA-165). LLM 보조 분석은 아직 구현 범위에 포함되지 않는다.

## 2. Friction 판정 규칙

| 유형 | 판정 조건 | 심각도 |
| --- | --- | --- |
| `navigation_confusion` | `back` 행동 2회 이상 또는 연속 중복을 제외한 이전 URL 재방문 2회 이상 | Medium |
| `interaction_failure` | 동일 URL·화면 해시·대상에서 3회 연속 클릭 | Medium |
| `interaction_failure` | `ELEMENT_NOT_INTERACTABLE`, `ELEMENT_NOT_FOUND`, `BROWSER_ACTION_FAILED` 발생 | Medium |
| `task_failure` | 목표 URL에 한 번도 닿지 못하고 `max_steps` · `stuck` · `timeout` 으로 끝남 | High |
| `task_failure` | 목표 URL에 한 번도 닿지 못하고 `done` · `token_limit` 으로 끝남 | Medium |
| `excessive_steps` | 처음 닿기까지 11~15단계 사용 | Low |
| `excessive_steps` | 처음 닿기까지 16단계 이상 사용 | Medium |
| `excessive_steps` | 어렵게 성공이고 처음 닿은 뒤 더 움직인 step 이 있음. 그 step 이 근거다 | 끝까지 쓴 step 이 15개 이하면 Low, 16개 이상이면 Medium |

### Persona 결과 넷 (11/03 결정)

| 결과 | 조건 | Friction |
| --- | --- | --- |
| 성공 | 닿음, `done` 으로 끝남 | 과제 실패 없음 |
| 어렵게 성공 | 닿음, `max_steps` · `stuck` · `timeout` · `token_limit` 으로 끝남 | 과제 실패 없음. 처음 닿은 뒤 step 이 과도한 단계의 근거다. 길 찾기 혼란은 전체 step 을 본다 |
| 실패 | 한 번도 못 닿음 | 과제 실패 |
| 판정 안 함 | `fail` · `cancelled` 로 끝남, 또는 도달 기록이 모두 비어 있음 | Friction 없음 |

### 판정 세부 원칙

- `navigation_confusion`은 동일 URL에 머무르는 행동을 재방문으로 세지 않는다.
- `interaction_failure`의 반복 클릭 규칙은 URL과 화면 해시가 동일해야 성립한다.
- `PARSE_FAILED`, `DOMAIN_BLOCKED`는 브라우저 조작 실패 코드로 분류하지 않는다.
- 과제 실패를 붙일지는 닿았는지로 정하고, 끝난 이유는 심각도와 사유에만 쓴다.
- `fail`은 Agent 또는 LLM 오류가 원인일 수 있으므로 Friction을 만들지 않는다.
- Agent의 `done`과 URL 미도달이 충돌하면 확정적인 실패가 아닌 **판정 불일치 신호**로 보고 사람의 검토가 필요하다고 표시한다.
- `url_reached=None`은 URL 성공 조건이 설정되지 않았거나 판정할 수 없는 상태이므로 `False`와 구분한다.
- `excessive_steps`는 URL 도달이 `True`인 실행만 판정한다.
- 여러 Friction이 발견되면 High → Medium → Low 순으로 반환한다. 심각도가 같으면 탐지 함수의 원래 순서를 유지한다.
- Friction이 없으면 빈 목록을 반환한다.

## 3. 심각도 기준

| 심각도 | 의미 | 현재 적용 사례 |
| --- | --- | --- |
| High | 목표에 못 닿고 상한이나 같은 화면 반복으로 끝남 | `max_steps`, `stuck`, `timeout` |
| Medium | 반복 탐색·조작 실패·완료 판정 불일치 또는 매우 긴 경로 | 탐색 혼란, 조작 실패, 판정 불일치, 못 닿은 `token_limit`, 16단계 이상 |
| Low | 성공했으나 기준보다 많은 단계 사용 | 11~15단계 |
| None | 탐지된 Friction 없음 | 정상 완료 등 |

위 기준과 임계값은 GACA-68의 초기 규칙이며, 실제 사용자 데이터에 따라 조정할 수 있다.

## 4. 샘플 Persona 로그 적용 결과

검증 대상: `services/agent/tests/fixtures/runs/9001/`

| Persona | 실행 상태 | 탐지 결과 |
| --- | --- | --- |
| 1 | `done` | Friction 없음 |
| 2 | `done` | `navigation_confusion` (Medium), `excessive_steps` (Low) |
| 3 | `done` | `interaction_failure` (Medium), `task_failure` (Medium, 판정 불일치) |
| 4 | `max_steps` | `task_failure` (High), `navigation_confusion` (Medium), `interaction_failure` (Medium) |
| 5 | `fail` | Friction 없음 (판정 안 함) |

### 주요 근거

- Persona 2: 뒤로 가기 4회, 이전 페이지 재방문 4회, 목표 도달까지 12단계 사용.
- Persona 3: `ELEMENT_NOT_INTERACTABLE` 오류 발생. Agent는 완료를 선언했으나 목표 URL에는 도달하지 못함.
- Persona 4: 최대 단계에 도달하여 종료. 뒤로 가기와 재방문이 반복되고 `ELEMENT_NOT_FOUND` 오류가 발생함.
- Persona 5: `PARSE_FAILED`로 실행 실패. 웹사이트 자체의 UX 문제라고 단정할 수 없어 판정하지 않음.

샘플 로그는 별도 테스트 fixture이며, 해당 fixture가 없는 환경에서는 관련 테스트 5개를 건너뛴다.

## 5. 공식 아키텍처와의 관계

성공은 규칙으로 판정하고 Agent의 `done`은 끝냈다는 선언으로만 본다(결정 로그 10/11 T27). 결과는 목표 URL 도달 여부와 끝난 이유로 넷으로 나눈다(결정 로그 11/03 T42).

못 닿았는데 `done`을 내면 `task_failure` 유형의 Medium 신호를 생성한다. 이는 UX 결함의 확정 판정이 아니며, 후속 진단 또는 사람 검토가 필요하다.

URL이 변하지 않는 화면 전환이나 페이지 내부 작업은 URL만으로 성공 여부를 판단하기 어렵다. 따라서 URL 기반 규칙의 결과는 제한적으로 해석해야 한다.

## 6. 테스트 결과 및 남은 작업

`uv run pytest tests/test_friction_rules.py -v`

- 결과: **44 passed**
- 검증: 샘플 Persona 5개, Persona 결과 넷, 탐색 혼란, 반복 클릭, 브라우저 오류, 오탐 방지, 과도한 단계 경계값
- 남은 연동: LLM 보조 판정
