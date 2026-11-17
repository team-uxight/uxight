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
                "finding_ids": json.dumps(item["finding_ids"], ensure_ascii=False),
                "option_no": item["option_no"],
                "patch_kind": item["patch_kind"],
                "patch": json.dumps(item["patch"], ensure_ascii=False),
                "rationale": item["rationale"],
                "expected_effect": item["expected_effect"],
                "fix_cost": None,
            }
            for item in improvements
        ]

        with engine.begin() as conn:
            existing = conn.execute(
                text("SELECT COUNT(*) FROM improvements WHERE run_id = :run_id"),
                {"run_id": run_id},
            ).scalar_one()

            if existing:
                raise ValueError(f"Improvements already exist for run_id={run_id}")

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

    def get_approved_patches(self, run_id: int) -> list[dict[str, Any]]:
        """현재 회차에 적용할 승인 패치를 오래된 순서부터 조회한다."""
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        """
                    WITH RECURSIVE run_chain AS (
                        SELECT run_id, parent_run_id, improvement_id, 0 AS depth
                        FROM runs
                        WHERE run_id = :run_id

                        UNION ALL

                        SELECT parent.run_id, parent.parent_run_id,
                               parent.improvement_id, child.depth + 1
                        FROM runs AS parent
                        JOIN run_chain AS child
                            ON parent.run_id = child.parent_run_id
                    )
                    SELECT
                        i.improvement_id,
                        i.patch_kind,
                        i.patch,
                        i.run_id AS source_run_id
                    FROM run_chain AS rc
                    JOIN improvements AS i
                        ON i.improvement_id = rc.improvement_id
                    JOIN approvals AS a
                        ON a.improvement_id = i.improvement_id
                    WHERE a.decision = 'approve'
                    ORDER BY rc.depth DESC
                    """
                    ),
                    {"run_id": run_id},
                )
                .mappings()
                .all()
            )

        return [
            {
                "improvement_id": row["improvement_id"],
                "source_run_id": row["source_run_id"],
                "patch_kind": row["patch_kind"],
                "patch": (
                    json.loads(row["patch"]) if isinstance(row["patch"], str) else row["patch"]
                ),
            }
            for row in rows
        ]


improvement_repository = ImprovementRepository()
