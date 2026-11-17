"""GACA-170: Persona별 승인 패치 적용 결과를 회차 단위로 집계한다."""

from typing import Any


def aggregate_patch_results(
    approved_patches: list[dict[str, Any]],
    persona_results: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """개선안별로 모든 Persona의 적용 결과를 보수적으로 집계한다.

    - 모든 Persona에서 실제 적용 성공이 확인되면 성공
    - 적용 실패가 한 번이라도 있으면 실패
    - 해당 Persona에서 적용 기록이 없으면 미방문으로 처리
    """
    aggregated: list[dict[str, Any]] = []

    for patch in approved_patches:
        improvement_id = patch["improvement_id"]
        failures: list[str] = []

        if not persona_results:
            failures.append("No persona execution results")

        for persona_id, results in persona_results.items():
            attempts = [result for result in results if result["improvement_id"] == improvement_id]

            if not attempts:
                failures.append(f"persona={persona_id}: target page not visited")
                continue

            for attempt in attempts:
                if not attempt["applied"]:
                    reason = attempt.get("fail_reason") or "Unknown failure"
                    failures.append(f"persona={persona_id}: {reason}")

        aggregated.append(
            {
                "improvement_id": improvement_id,
                "patch_kind": patch["patch_kind"],
                "patch": patch["patch"],
                "applied": not failures,
                "fail_reason": "; ".join(failures) if failures else None,
            }
        )

    return aggregated
