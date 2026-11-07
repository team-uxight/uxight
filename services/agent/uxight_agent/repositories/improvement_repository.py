"""GACA-168: UX 개선안 DB 저장소."""

import json
from typing import Any

from sqlalchemy import text

from ..db import engine


class ImprovementRepository:
    """improvements 테이블(V8). AI 모듈이 저장하고 Spring이 조회한다."""

    def insert_all(
        self,
        run_id: int,
        improvements: list[dict[str, Any]],
    ) -> None:
        """검증된 개선안 목록을 하나의 트랜잭션으로 저장한다."""
        if not improvements:
            return

        if len(improvements) > 3:
            raise ValueError("A run can have at most 3 improvements")

        numbers = [item["option_no"] for item in improvements]
        if numbers != list(range(1, len(improvements) + 1)):
            raise ValueError("option_no must be consecutive, starting at 1")

        rows = [
            {
                "run_id": run_id,
                "finding_ids": json.dumps(
                    item["finding_ids"], ensure_ascii=False
                ),
                "option_no": item["option_no"],
                "patch_kind": item["patch_kind"],
                "patch": json.dumps(
                    item["patch"], ensure_ascii=False
                ),
                "rationale": item["rationale"],
                "expected_effect": item["expected_effect"],
                "fix_cost": None,
            }
            for item in improvements
        ]

        with engine.begin() as conn:
            existing = conn.execute(
                text(
                    "SELECT COUNT(*) FROM improvements "
                    "WHERE run_id = :run_id"
                ),
                {"run_id": run_id},
            ).scalar_one()

            if existing:
                raise ValueError(
                    f"Improvements already exist for run_id={run_id}"
                )

            conn.execute(
                text(
                    "INSERT INTO improvements "
                    "(run_id, finding_ids, option_no, patch_kind, patch, "
                    "rationale, expected_effect, fix_cost) "
                    "VALUES "
                    "(:run_id, :finding_ids, :option_no, :patch_kind, :patch, "
                    ":rationale, :expected_effect, :fix_cost)"
                ),
                rows,
            )


improvement_repository = ImprovementRepository()
