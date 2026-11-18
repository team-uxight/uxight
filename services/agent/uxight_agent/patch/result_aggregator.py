"""GACA-170: Persona별 승인 패치 적용 결과를 회차 단위로 집계한다."""

from typing import Any

# patch_versions.fail_reason(TEXT)에 넣는 길이 상한. 넘으면 자르고 끝에 표시한다.
_MAX_FAIL_REASON = 2000
_TRUNCATED = " ... (truncated)"


def aggregate_patch_results(
    approved_patches: list[dict[str, Any]],
    persona_results: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """개선안별로 모든 Persona의 적용 결과를 보수적으로 집계한다.

    - 모든 Persona에서 실제 적용 성공이 확인되면 성공
    - 적용 실패가 한 번이라도 있으면 실패
    - 해당 Persona에서 적용 기록이 없으면 미방문으로 처리
    - 같은 실패 사유는 한 번만 적고 그 사유를 겪은 Persona 번호를 모은다
    """
    aggregated: list[dict[str, Any]] = []

    for patch in approved_patches:
        improvement_id = patch["improvement_id"]
        failures: list[str] = []
        # 실패 사유 → 그 사유를 겪은 Persona 번호 (처음 나온 순서)
        reasons: dict[str, list[int]] = {}

        if not persona_results:
            failures.append("No persona execution results")

        for persona_id, results in persona_results.items():
            attempts = [result for result in results if result["improvement_id"] == improvement_id]

            if not attempts:
                reasons.setdefault("target page not visited", []).append(persona_id)
                continue

            for attempt in attempts:
                if not attempt["applied"]:
                    reason = attempt.get("fail_reason") or "Unknown failure"
                    personas = reasons.setdefault(reason, [])
                    if persona_id not in personas:
                        personas.append(persona_id)

        for reason, personas in reasons.items():
            failures.append(f"persona={','.join(map(str, personas))}: {reason}")

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
