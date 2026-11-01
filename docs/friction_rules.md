# GACA-68 — Friction 판정 규칙 및 심각도

## 1. 목적과 구현 범위

Persona Agent의 행동 로그(`steps.jsonl`)에서 사용성 문제의 신호를 Python 규칙으로 탐지한다.

- Friction 유형: `navigation_confusion`, `interaction_failure`, `task_failure`, `excessive_steps`
- 판정 결과: 유형, 심각도, 근거 step 번호, 판정 사유
- 구현: `services/agent/uxight_agent/watcher/friction_rules.py`
- 테스트: `services/agent/tests/test_friction_rules.py`
- 탐지 함수: `detect_frictions(steps, status=None, excessive_steps_threshold=10)`

현재 구현은 독립적인 Python 판정 함수다. LLM 보조 분석, `findings` DB 저장 및 진단 파이프라인 연결은 아직 구현 범위에 포함되지 않는다.

## 2. Friction 판정 규칙

| 유형 | 판정 조건 | 심각도 |
| --- | --- | --- |
| `navigation_confusion` | `back` 행동 2회 이상 또는 연속 중복을 제외한 이전 URL 재방문 2회 이상 | Medium |
| `interaction_failure` | 동일 URL·화면 해시·대상에서 3회 연속 클릭 | Medium |
| `interaction_failure` | `ELEMENT_NOT_INTERACTABLE`, `ELEMENT_NOT_FOUND`, `BROWSER_ACTION_FAILED` 발생 | Medium |
| `task_failure` | 실행 상태가 `fail` 또는 `max_steps` | High |
| `task_failure` | Agent가 `done`을 선언했지만 `url_reached=False` | Medium |
| `excessive_steps` | 목표 URL에 도달한 실행이 11~15단계 사용 | Low |
| `excessive_steps` | 목표 URL에 도달한 실행이 16단계 이상 사용 | Medium |

### 판정 세부 원칙

- `navigation_confusion`은 동일 URL에 머무르는 행동을 재방문으로 세지 않는다.
- `interaction_failure`의 반복 클릭 규칙은 URL과 화면 해시가 동일해야 성립한다.
- `PARSE_FAILED`, `DOMAIN_BLOCKED`는 브라우저 조작 실패 코드로 분류하지 않는다.
- `fail`이나 `max_steps`는 `task_failure`로 판정한다. 단, Agent 또는 LLM 오류가 원인일 수 있으므로 웹사이트 UX 결함으로 단정하지 않는다.
- Agent의 `done`과 URL 미도달이 충돌하면 확정적인 실패가 아닌 **판정 불일치 신호**로 보고 사람의 검토가 필요하다고 표시한다.
- `url_reached=None`은 URL 성공 조건이 설정되지 않았거나 판정할 수 없는 상태이므로 `False`와 구분한다.
- `excessive_steps`는 URL 도달이 `True`이고 상태가 `fail` 또는 `max_steps`가 아닐 때만 판정한다.
- 여러 Friction이 발견되면 High → Medium → Low 순으로 반환한다. 심각도가 같으면 탐지 함수의 원래 순서를 유지한다.
- Friction이 없으면 빈 목록을 반환한다.

## 3. 심각도 기준

| 심각도 | 의미 | 현재 적용 사례 |
| --- | --- | --- |
| High | 실행 자체가 실패했거나 단계 제한에 도달함 | `fail`, `max_steps` |
| Medium | 반복 탐색·조작 실패·완료 판정 불일치 또는 매우 긴 경로 | 탐색 혼란, 조작 실패, 판정 불일치, 16단계 이상 |
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
| 5 | `fail` | `task_failure` (High, LLM 응답 파싱 오류) |

### 주요 근거

- Persona 2: 뒤로 가기 4회, 이전 페이지 재방문 4회, 목표 도달까지 12단계 사용.
- Persona 3: `ELEMENT_NOT_INTERACTABLE` 오류 발생. Agent는 완료를 선언했으나 목표 URL에는 도달하지 못함.
- Persona 4: 최대 단계에 도달하여 종료. 뒤로 가기와 재방문이 반복되고 `ELEMENT_NOT_FOUND` 오류가 발생함.
- Persona 5: `PARSE_FAILED`로 실행 실패. 웹사이트 자체의 UX 문제라고 단정할 수 없음.

샘플 로그는 별도 테스트 fixture이며, 해당 fixture가 없는 환경에서는 관련 테스트 5개를 건너뛴다.

## 5. 공식 아키텍처와의 관계

`docs/architecture.md`의 D21에 따라 Agent의 `done` 판단을 주 기준으로, 목표 URL 도달 여부를 보조 기준으로 취급한다.

현재 구현은 두 판단이 불일치할 때 `task_failure` 유형의 Medium 신호를 생성한다. 이는 UX 결함의 확정 판정이 아니며, 후속 진단 또는 사람 검토가 필요하다.

URL이 변하지 않는 화면 전환이나 페이지 내부 작업은 URL만으로 성공 여부를 판단하기 어렵다. 따라서 URL 기반 규칙의 결과는 제한적으로 해석해야 한다.

## 6. 테스트 결과 및 남은 작업

`uv run pytest tests/test_friction_rules.py -v`

- 결과: **18 passed**
- 검증: 샘플 Persona 5개, 과제 완료 판정, 탐색 혼란, 반복 클릭, 브라우저 오류, 오탐 방지, 과도한 단계 경계값
- 남은 연동: Watcher 실행 결과 연결, LLM 보조 판정, `findings` 저장 및 진단 단계 연결
