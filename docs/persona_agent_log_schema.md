# Persona Agent 행동 로그 명세

> Persona Agent가 Task를 수행하며 남기는 step 로그(steps.jsonl)의 형식. Friction Detector의 입력이자 관리자 step 로그 조회 API의 원본이다.
> 상태: AI–BE 합의안(2026-10-10 기준). 미결 항목은 8절.
> 관련 문서: design-decision.md, schema_blueprint.sql, 서비스 REST API 설계, uxight-api.yaml, docs/architecture.md

## 1. 파일 구조

    data/runs/
    └── <run_id>/
        └── <persona_id>/
            ├── steps.jsonl
            ├── step-1.png
            └── step-<n>.png

- run_id와 persona_id는 DB의 숫자 ID다(`runs.run_id`, `personas.persona_id`). 예: `data/runs/101/2/`
- steps.jsonl의 한 줄은 step 하나의 JSON 객체다(UTF-8).
- 스크린샷은 마스킹과 블러를 거친 이미지만 저장한다.

## 2. 쓰기와 읽기 규칙

- 파일은 Python만 쓴다. Spring은 이 디렉터리를 읽기 전용으로 마운트해 읽는다.
- 실행하지 않은 step(가드 차단, Action 파싱 실패)도 한 줄로 기록한다.
- step 번호는 Persona 실행마다 1부터 빠짐없이 이어진다. 스크린샷 파일 이름, `run_personas.steps`, `findings.evidence`의 step 구간, max_steps 한도가 이 번호를 같이 쓴다.
- Python은 스크린샷 파일을 먼저 쓰고, 그다음 그 step의 줄을 줄바꿈까지 한 번에 추가한다.
- Spring은 마지막 줄이 완성되지 않았으면(줄바꿈으로 끝나지 않았거나 JSON으로 읽히지 않으면) 쓰는 중인 줄로 보고 건너뛴다.
- Spring은 파일 경로를 run_id, persona_id, step 숫자로 직접 만든다. 로그 안의 `observation.screenshot`이나 `run_personas.log_path`를 경로로 쓰지 않는다.
- Action 파싱은 최대 2회 재시도하며, 3회 연속 실패하면 Persona 실행을 실패(`fail`)로 처리한다.

## 3. Step 객체

모든 필드는 항상 기록한다. 값이 없으면 필드를 생략하지 않고 null로 쓴다.

### 3.1 최상위 필드

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| run_id | integer | 회차 ID |
| persona_id | integer | Persona ID(`personas.persona_id`) |
| step | integer | step 번호. 1부터 이어지며 가드 차단과 Action 파싱 실패 step을 포함 |
| ts | string | 기록 시각. 시간대를 포함한 ISO 8601 형식 |
| url | string | 행동 전 페이지 URL |
| observation | object | 관측 정보(3.2) |
| reasoning | string/null | Agent의 판단 근거. Action 파싱 실패 시 null |
| action | object/null | Agent의 행동(3.3). Action 파싱 실패 시 null |
| result | object | 행동 실행 결과(3.4) |
| blocked | object | 차단 여부와 사유(3.5) |
| latency_ms | object | 소요 시간(3.6) |
| tokens | object | LLM 토큰 사용량(3.6) |
| model | string/null | 호출한 모델 식별자 |
| task | object | Task 판정 정보(3.7) |

### 3.2 observation

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| mode | string | 관측 방식. som 또는 dom |
| screenshot | string/null | 마스킹된 스크린샷의 상대 경로(`data/runs/` 기준). 스크린샷이 없으면 null |
| elements_hash | string | 관측된 요소 목록의 해시. 같은 정규화 규칙으로 만들어 화면 반복 탐지에 쓴다 |
| element_count | integer | 관측된 요소 수 |

### 3.3 action

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| kind | string | 행동 종류. click, type, scroll, back, done(4절) |
| target | integer/null | 대상 요소 번호. click, type에서만 값이 있음 |
| text | string/null | 입력 내용. type에서만 값이 있으며 민감정보를 마스킹한 값 |
| direction | string/null | 스크롤 방향. up 또는 down. scroll에서만 값이 있음 |

### 3.4 result

result는 브라우저 행동의 실행 결과이며, Task 달성 여부와는 별개다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| ok | boolean | 브라우저 행동 실행 성공 여부 |
| url_after | string | 행동 뒤 페이지 URL. 실행하지 않은 step이면 url과 같음 |
| error | string/null | 오류 설명 |
| error_code | string/null | step 실행 결과 코드 |

- error_code의 목록은 AI 측이 Python Driver 구현에 맞춰 정한다. 이 값은 Spring API의 오류 코드(8.4 오류 코드 및 오류 파일 설계, 분류-ERR-번호)와 별개이며, Spring은 해석하지 않고 그대로 전달한다.

### 3.5 blocked

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| is | boolean | 실행하지 않은 step이면 true. 가드 차단과 Action 파싱 실패가 해당함 |
| reason | string/null | 차단 사유. is가 false면 null |

- reason의 값: schema, domain, destructive, limit, rate, parse_failed. 각 값의 정의는 architecture.md를 따른다.
- 차단된 행동은 브라우저에서 실행하지 않는다.

### 3.6 latency_ms, tokens

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| latency_ms.llm | integer | LLM 호출 시간(ms) |
| latency_ms.browser | integer | 브라우저 행동 수행 시간(ms) |
| tokens.prompt | integer | 입력 토큰 |
| tokens.completion | integer | 출력 토큰 |

- 호출하거나 실행하지 않았으면 0을 기록한다. 예를 들어 차단된 step의 latency_ms.browser는 0이다.

### 3.7 task

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| url_reached | boolean/null | 행동 뒤 URL(result.url_after)이 성공 URL(`tasks.success_url`)과 일치하는지. 판정하지 못하면 null |

- Agent의 완료 선언은 `action.kind = 'done'`으로 알 수 있으므로, 완료 여부를 나타내는 별도 필드(agent_done)는 두지 않는다.

## 4. Action 종류

| kind | target | text | direction | 의미 |
| --- | --- | --- | --- | --- |
| click | 필수 | null | null | 요소 클릭 |
| type | 필수 | 필수 | null | 요소에 문자열 입력 |
| scroll | null | null | 필수 | 화면 스크롤 |
| back | null | null | null | 이전 페이지 이동 |
| done | null | null | null | 성공 기준 충족 선언 |

- LLM 출력은 위 5종으로 제한한다. 임의의 JavaScript 코드, 브라우저 셀렉터, 직접 이동할 URL은 Action으로 받지 않는다.

## 5. 예시

각 예시는 형식 설명용이며 서로 이어진 기록이 아니다. 시간, 토큰, URL은 가상 데이터이고, error_code 값은 가칭이다. 실제 파일에서는 객체 하나가 한 줄이다(5.6).

### 5.1 정상 행동

```json
{
  "run_id": 101,
  "persona_id": 2,
  "step": 7,
  "ts": "2026-10-10T20:10:31+09:00",
  "url": "https://shop.example.com/cart",
  "observation": {
    "mode": "som",
    "screenshot": "101/2/step-7.png",
    "elements_hash": "ab31f9",
    "element_count": 18
  },
  "reasoning": "결제를 진행하기 위해 '주문하기' 버튼을 누른다.",
  "action": {"kind": "click", "target": 5, "text": null, "direction": null},
  "result": {
    "ok": true,
    "url_after": "https://shop.example.com/order",
    "error": null,
    "error_code": null
  },
  "blocked": {"is": false, "reason": null},
  "latency_ms": {"llm": 1240, "browser": 430},
  "tokens": {"prompt": 1240, "completion": 83},
  "model": "configured-step-model",
  "task": {"url_reached": false}
}
```

### 5.2 가드 차단

허용 도메인 밖으로 이동하려는 행동을 가드가 차단한 경우. 브라우저 행동은 실행하지 않는다.

```json
{
  "run_id": 101,
  "persona_id": 2,
  "step": 8,
  "ts": "2026-10-10T20:10:35+09:00",
  "url": "https://shop.example.com/order",
  "observation": {
    "mode": "som",
    "screenshot": "101/2/step-8.png",
    "elements_hash": "c9d2e4",
    "element_count": 22
  },
  "reasoning": "결제 수단 안내를 보기 위해 외부 안내 링크를 누른다.",
  "action": {"kind": "click", "target": 12, "text": null, "direction": null},
  "result": {
    "ok": false,
    "url_after": "https://shop.example.com/order",
    "error": "Action blocked by domain policy",
    "error_code": "ACTION_BLOCKED"
  },
  "blocked": {"is": true, "reason": "domain"},
  "latency_ms": {"llm": 1180, "browser": 0},
  "tokens": {"prompt": 1310, "completion": 79},
  "model": "configured-step-model",
  "task": {"url_reached": false}
}
```

### 5.3 Action 파싱 실패

LLM 출력이 Action 스키마에 맞지 않고, 재시도 후에도 유효한 Action을 얻지 못한 경우.

```json
{
  "run_id": 101,
  "persona_id": 3,
  "step": 4,
  "ts": "2026-10-10T20:11:02+09:00",
  "url": "https://shop.example.com/products",
  "observation": {
    "mode": "som",
    "screenshot": "101/3/step-4.png",
    "elements_hash": "5e7a10",
    "element_count": 31
  },
  "reasoning": null,
  "action": null,
  "result": {
    "ok": false,
    "url_after": "https://shop.example.com/products",
    "error": "Action JSON parsing failed",
    "error_code": "PARSE_FAILED"
  },
  "blocked": {"is": true, "reason": "parse_failed"},
  "latency_ms": {"llm": 2050, "browser": 0},
  "tokens": {"prompt": 1420, "completion": 156},
  "model": "configured-step-model",
  "task": {"url_reached": false}
}
```

### 5.4 브라우저 실행 실패

대상 요소가 실행 시점에 존재하지 않는 경우. 차단은 아니므로 blocked.is는 false다.

```json
{
  "run_id": 101,
  "persona_id": 2,
  "step": 9,
  "ts": "2026-10-10T20:10:41+09:00",
  "url": "https://shop.example.com/order",
  "observation": {
    "mode": "som",
    "screenshot": "101/2/step-9.png",
    "elements_hash": "c9d2e4",
    "element_count": 22
  },
  "reasoning": "배송지 입력란을 선택한다.",
  "action": {"kind": "click", "target": 9, "text": null, "direction": null},
  "result": {
    "ok": false,
    "url_after": "https://shop.example.com/order",
    "error": "Target element not found",
    "error_code": "ELEMENT_NOT_FOUND"
  },
  "blocked": {"is": false, "reason": null},
  "latency_ms": {"llm": 1105, "browser": 3000},
  "tokens": {"prompt": 1295, "completion": 71},
  "model": "configured-step-model",
  "task": {"url_reached": false}
}
```

### 5.5 성공 기준 충족 선언(done)

성공 URL에 도달한 상태에서 Agent가 done으로 종료하는 경우. 이 Persona 실행은 `run_personas.status = 'done'`으로 기록된다.

```json
{
  "run_id": 101,
  "persona_id": 2,
  "step": 15,
  "ts": "2026-10-10T20:11:30+09:00",
  "url": "https://shop.example.com/order/complete",
  "observation": {
    "mode": "som",
    "screenshot": "101/2/step-15.png",
    "elements_hash": "f04b77",
    "element_count": 9
  },
  "reasoning": "주문 완료 화면이 표시되어 Task를 마친다.",
  "action": {"kind": "done", "target": null, "text": null, "direction": null},
  "result": {
    "ok": true,
    "url_after": "https://shop.example.com/order/complete",
    "error": null,
    "error_code": null
  },
  "blocked": {"is": false, "reason": null},
  "latency_ms": {"llm": 980, "browser": 0},
  "tokens": {"prompt": 1150, "completion": 42},
  "model": "configured-step-model",
  "task": {"url_reached": true}
}
```

### 5.6 실제 파일의 한 줄

5.1을 steps.jsonl에 기록하면 다음과 같다. 줄 끝에 줄바꿈이 있다.

```
{"run_id":101,"persona_id":2,"step":7,"ts":"2026-10-10T20:10:31+09:00","url":"https://shop.example.com/cart","observation":{"mode":"som","screenshot":"101/2/step-7.png","elements_hash":"ab31f9","element_count":18},"reasoning":"결제를 진행하기 위해 '주문하기' 버튼을 누른다.","action":{"kind":"click","target":5,"text":null,"direction":null},"result":{"ok":true,"url_after":"https://shop.example.com/order","error":null,"error_code":null},"blocked":{"is":false,"reason":null},"latency_ms":{"llm":1240,"browser":430},"tokens":{"prompt":1240,"completion":83},"model":"configured-step-model","task":{"url_reached":false}}
```

## 6. DB 기록과 조회

### 6.1 Task 판정과 run_personas

- 메인 기준: `run_personas.status = 'done'`. Agent가 done 행동으로 성공 기준 충족을 선언하고 종료한 경우다.
- 보조 기준: `run_personas.url_reached`. Persona 실행 중 한 번이라도 `task.url_reached`가 true였으면 true다. 마지막 URL로 정하면, 성공 페이지에 도달한 뒤 떠난 Persona가 실패로 기록되어 아래 표의 사람 검토 대상을 놓친다.

| done | url_reached | 해석 |
| --- | --- | --- |
| true | true | 성공 |
| true | false | Agent 착각이거나 URL 규칙이 못 잡는 성공. 사람 검토 대상 |
| false | true | 목표에 도달했지만 Persona가 인지하지 못함. 사람 검토 대상 |
| false | false | 실패 |

- run_personas에는 컬럼을 추가하지 않는다. Python은 `steps`, `tokens`, `cost_usd`를 step마다 갱신하며, `steps`는 steps.jsonl의 줄 수와 같다.
- 차단 수, 파싱 실패 수, 소요 시간은 컬럼으로 두지 않는다. Friction Detector는 steps.jsonl을 직접 읽고, 소요 시간은 `started_at`과 `finished_at`으로 계산한다.
- 스키마는 BE가 Flyway migration으로 관리한다. Python은 DDL을 실행하지 않고, 확정된 스키마에 맞춰 INSERT와 UPDATE만 한다.

### 6.2 Spring 조회 응답

| 엔드포인트 | 응답 |
| --- | --- |
| `GET /api/admin/runs/{runId}/personas/{personaId}/steps` | step 로그 목록(JSON) |
| `GET /api/admin/runs/{runId}/personas/{personaId}/steps/{step}/screenshot` | 스크린샷(image/png) |

Spring은 steps.jsonl을 그대로 넘기지 않고, 아래 키만 골라 camelCase로 바꿔 응답한다.

| 응답 키 | 원래 필드 |
| --- | --- |
| step, ts, url, reasoning | 같은 이름 |
| action | action의 kind, target, text, direction |
| result | result의 ok, url_after, error, error_code(urlAfter, errorCode로 바뀜) |
| blocked | blocked.is |
| blockedReason | blocked.reason |
| urlReached | task.url_reached |
| hasScreenshot | observation.screenshot이 null이 아닌지 |

- 넘기지 않는 필드: run_id, persona_id(경로 변수에 있음), observation의 mode, elements_hash, element_count, 스크린샷 경로, latency_ms, tokens, model.
- ts는 문자열 그대로 전달하므로 시간대가 포함된다.
- 기록된 step 전체를 반환한다(페이지네이션 없음).
- Persona 실행이 running이고 아직 기록된 step이 없으면 빈 목록을 응답한다. 그 밖에 로그나 스크린샷이 없으면 404(LOG-ERR-001, LOG-ERR-002)로 응답한다.

5.1을 조회하면 목록의 한 항목은 다음과 같다.

```json
{
  "step": 7,
  "ts": "2026-10-10T20:10:31+09:00",
  "url": "https://shop.example.com/cart",
  "reasoning": "결제를 진행하기 위해 '주문하기' 버튼을 누른다.",
  "action": {"kind": "click", "target": 5, "text": null, "direction": null},
  "result": {
    "ok": true,
    "urlAfter": "https://shop.example.com/order",
    "error": null,
    "errorCode": null
  },
  "blocked": false,
  "blockedReason": null,
  "urlReached": false,
  "hasScreenshot": true
}
```

## 7. 보안

- 자격증명은 LLM 프롬프트, 관측, 로그, 스크린샷 어디에도 남기지 않는다. 로그인은 Agent 루프 시작 전에 고정 스크립트가 수행한다.
- 비밀번호 계열 입력값은 마스킹하고, 해당 화면 영역은 블러한다. 마스킹과 블러는 Python이 저장하기 전에 한 번 하고, Spring은 다시 하지 않는다.
- 행동 로그와 전체 스크린샷은 관리자 API로만 제공한다. 리서처는 진단 근거와 Before/After 범위의 스크린샷만 조회할 수 있다.

## 8. 미결 항목

- `action.success`(Agent 자체 성공 주장): done이 성공 기준 충족 선언이면 done일 때 항상 true라서 중복이므로, BE는 빼는 것을 제안한다. AI 측이 done과 success=false 조합으로 '포기'를 표현하려는 것이라면, 포기를 기록할 status를 따로 정해야 한다. 포기를 done으로 기록하면 성공률에 성공으로 집계된다.
- error_code 목록: AI 측이 정해 공유한다. 이 문서의 ACTION_BLOCKED, PARSE_FAILED, ELEMENT_NOT_FOUND는 가칭이다.
- latency_ms, tokens의 측정 실패 표현(null 허용 여부): AI 측이 정한다. 프론트엔드에 넘기지 않으므로 BE와는 무관하다.
- 마스킹 범위: BE는 기존 범위(비밀번호 계열 입력값과 그 영역) 유지를 제안한다. 일반 입력값까지 넓혀야 한다면 AI 측이 대상 범위를 구체적으로 정한다.
