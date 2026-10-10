# 판정 · 진단 모델 비교

가상 사용자(탐색)는 `openai/gpt-5.6-luna` 로 정했다. **판정 · 진단**에 쓸 모델을 근거를 갖고 고르려고, 같은 문제집을 모델마다 돌려 비교한다.

## 문제집 (`cases/`, 과제마다 10문제)

| 과제 | 모델이 하는 일 | 채점 |
| --- | --- | --- |
| `judge` 성공 판정 | Task · 성공 기준 · 최종 화면 · 마지막 행동을 보고 성공했는지. **가상 사용자의 "찾았다" 는 믿지 않는다** | `success` 일치 |
| `task_check` 실행 전 Task 확인 | Task 문장이 모호하면(대상이 여럿 · 조건 빠짐 · 상태를 바꾸는 요청) 되물을 질문 | `ambiguous` 일치 |
| `friction` Friction 분류 | step 로그에서 가장 두드러진 문제 — 헤맴 · 반응 없음 · 실패 · 너무 많은 step · 없음 | `type` 일치 (심각도는 참고) |

문제는 학교 사본의 실제 페이지 글과 Task 후보로 만들었다. **정답(`label`)은 PM 초안 — 돌리기 전에 PM 이 확인한다**(특히 `friction` 의 심각도). 실제 실행 로그가 쌓이면(S3) 그걸로 한 번 더 돌린다.

## 돌리기

```sh
# 저장소 루트의 .env 를 터미널에 올린다 (LLM_* = MLAPI). OpenRouter 는 OPENROUTER_BASE_URL · OPENROUTER_API_KEY
set -a; . ../../.env; set +a
uv run python -m uxight_agent.bakeoff --repeat 3 \
  --model luna=openai/gpt-5.6-luna \
  --model terra=<Terra 모델 ID>@OPENROUTER \
  --model sol=<Sol 모델 ID>@OPENROUTER \
  --model astra=<GPT-6 Astra 모델 ID>@OPENROUTER
```

`--model 이름=모델ID@접두어` 에서 접두어가 X 면 `X_BASE_URL` · `X_API_KEY` 를 쓴다(없으면 `LLM`). 단가가 기본표에 없는 모델은 `LLM_PRICES='{"모델ID": [입력, 출력]}'`(USD / 100만 토큰)로 준다.

결과는 `eval/results/<시각>/` (커밋하지 않는다): `summary.md` 표 · `calls.jsonl` 문제별 답 · `usage.jsonl` 토큰.

## 고르는 규칙 (제안 — PM 확정)

1. 성공 판정 정답률 90% 이상 · 형식 준수 100% · Friction 유형 정답률 70% 이상을 넘는 모델 중
2. 호출당 비용이 가장 싼 것. Luna 가 넘으면 Luna 하나로 간다 (배포 · 키 · 단가가 하나).
3. 일관성(같은 문제를 3번 물었을 때 같은 답)이 낮은 모델은 정답률이 높아도 뺀다 — 판정이 흔들리면 실험 결과를 못 믿는다.
