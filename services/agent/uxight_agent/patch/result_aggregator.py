"""GACA-170: Persona별 승인 패치 적용 결과를 회차 단위로 집계한다."""

from typing import Any

# patch_versions.fail_reason(TEXT)에 넣는 길이 상한. 넘으면 자르고 끝에 표시한다.
_MAX_FAIL_REASON = 2000
_TRUNCATED = " ... (truncated)"


def aggregate_patch_results(
    approved_patches: list[dict[str, Any]],
    persona_results: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """개선안별로 회차의 모든 Persona 적용 결과를 모은다.

    - 패치가 한 번 이상 들어갔고 넣다가 실패한 기록이 없으면 적용(applied = True)
    - 넣다가 실패한 기록이 한 번이라도 있으면 실패. 같은 사유는 한 번만 적고 그 사유를 겪은
      Persona 번호를 모은다
    - 패치 페이지에 들르지 않은 Persona 는 실패로 세지 않고 사유에도 넣지 않는다
    - 아무도 그 페이지에 들르지 않았으면 실패이고 사유는 'target page not visited by any persona'
    """
    aggregated: list[dict[str, Any]] = []

    for patch in approved_patches:
        improvement_id = patch["improvement_id"]
        failures: list[str] = []
        # 실패 사유 → 그 사유를 겪은 Persona 번호 (처음 나온 순서)
        reasons: dict[str, list[int]] = {}
        applied_count = 0

        if not persona_results:
            failures.append("No persona execution results")

        for persona_id, results in persona_results.items():
            for attempt in results:
                if attempt["improvement_id"] != improvement_id:
                    continue
                if attempt["applied"]:
                    applied_count += 1
                    continue
                reason = attempt.get("fail_reason") or "Unknown failure"
                personas = reasons.setdefault(reason, [])
                if persona_id not in personas:
                    personas.append(persona_id)

        for reason, personas in reasons.items():
            failures.append(f"persona={','.join(map(str, personas))}: {reason}")

        if persona_results and not failures and applied_count == 0:
            failures.append("target page not visited by any persona")

        fail_reason = "; ".join(failures) if failures else None
        if fail_reason and len(fail_reason) > _MAX_FAIL_REASON:
            fail_reason = fail_reason[: _MAX_FAIL_REASON - len(_TRUNCATED)] + _TRUNCATED

        aggregated.append(
            {
                "improvement_id": improvement_id,
                "patch_kind": patch["patch_kind"],
                "patch": patch["patch"],
                "applied": not failures,
                "fail_reason": fail_reason,
            }
        )

    return aggregated
