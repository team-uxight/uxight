"""GACA-170: 승인 패치의 실제 적용 결과를 저장한다."""

import json
from typing import Any

from sqlalchemy import text

from ..db import engine


class PatchVersionRepository:
    """patch_versions 테이블의 회차별 적용 결과 저장소."""

    def insert_all(
        self,
        run_id: int,
        results: list[dict[str, Any]],
    ) -> None:
        """동일 결과 재저장은 허용하고, 서로 다른 재저장은 거부한다."""
        if not results:
            return

        improvement_ids = [item["improvement_id"] for item in results]
        if len(improvement_ids) != len(set(improvement_ids)):
            raise ValueError("Duplicate improvement_id in patch results")

        rows = []
        for item in results:
            applied = item["applied"]
            fail_reason = item.get("fail_reason")

            if not isinstance(applied, bool):
                raise ValueError("applied must be a boolean")
            if applied and fail_reason is not None:
                raise ValueError("Successful patch cannot have fail_reason")
            if not applied and not fail_reason:
                raise ValueError("Failed patch must have fail_reason")

            rows.append(
                {
                    "run_id": run_id,
                    "improvement_id": item["improvement_id"],
                    "patch_kind": item["patch_kind"],
                    "patch": json.dumps(item["patch"], ensure_ascii=False),
                    "applied": applied,
                    "fail_reason": fail_reason,
                }
            )

        with engine.begin() as conn:
            # MySQL에서는 같은 run_id의 저장 작업을 직렬화한다.
            if conn.dialect.name == "mysql":
                locked = conn.execute(
                    text("SELECT run_id FROM runs WHERE run_id = :run_id FOR UPDATE"),
                    {"run_id": run_id},
                ).scalar_one_or_none()
                if locked is None:
                    raise ValueError(f"Run does not exist: {run_id}")

            existing_count = conn.execute(
                text("SELECT COUNT(*) FROM patch_versions WHERE run_id = :run_id"),
                {"run_id": run_id},
            ).scalar_one()

            if existing_count:
                existing_rows = (
                    conn.execute(
                        text(
                            "SELECT improvement_id, patch_kind, patch, "
                            "applied, fail_reason "
                            "FROM patch_versions "
                            "WHERE run_id = :run_id "
                            "ORDER BY improvement_id"
                        ),
                        {"run_id": run_id},
                    )
                    .mappings()
                    .all()
                )

                def normalized(row):
                    patch = row["patch"]
                    if isinstance(patch, (str, bytes)):
                        patch = json.loads(patch)
                    return (
                        row["improvement_id"],
                        row["patch_kind"],
                        patch,
                        bool(row["applied"]),
                        row["fail_reason"],
                    )

                expected = sorted(
                    (normalized(row) for row in rows),
                    key=lambda item: item[0],
                )
                actual = [normalized(row) for row in existing_rows]

                if actual == expected:
                    return

                raise ValueError(
                    f"Patch versions already exist for run_id={run_id} with different results"
                )

            conn.execute(
                text(
                    "INSERT INTO patch_versions "
                    "(run_id, improvement_id, patch_kind, patch, "
                    "applied, fail_reason) "
                    "VALUES "
                    "(:run_id, :improvement_id, :patch_kind, :patch, "
                    ":applied, :fail_reason)"
                ),
                rows,
            )


patch_version_repository = PatchVersionRepository()
