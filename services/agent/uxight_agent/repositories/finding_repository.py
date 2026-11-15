import json

from sqlalchemy import text

from ..db import engine
from ..diagnose.findings import Finding


class FindingRepository:
    """findings 테이블 (V7). 쓰는 쪽은 AI 모듈뿐이고 Spring 은 읽기만 한다."""

    def insert_all(self, run_id: int, findings: list[Finding]) -> None:
        # 회차의 진단을 한 트랜잭션에 넣는다 — 일부만 들어간 회차가 남지 않게.
        if not findings:
            return
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO findings (run_id, taxonomy, severity, evidence, summary) "
                    "VALUES (:run_id, :taxonomy, :severity, :evidence, :summary)"
                ),
                [
                    {
                        "run_id": run_id,
                        "taxonomy": f.taxonomy,
                        "severity": f.severity,
                        "evidence": json.dumps(f.evidence, ensure_ascii=False),
                        "summary": f.summary,
                    }
                    for f in findings
                ],
            )

    def get_by_run(self, run_id: int) -> list[dict]:
        """회차에 저장된 Friction을 실제 finding_id와 함께 조회한다."""
        with engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT finding_id, taxonomy, severity, evidence, summary "
                        "FROM findings WHERE run_id = :run_id "
                        "ORDER BY finding_id"
                    ),
                    {"run_id": run_id},
                )
                .mappings()
                .all()
            )

        return [
            {
                "finding_id": row["finding_id"],
                "taxonomy": row["taxonomy"],
                "severity": row["severity"],
                "evidence": (
                    json.loads(row["evidence"])
                    if isinstance(row["evidence"], str)
                    else row["evidence"]
                ),
                "summary": row["summary"],
            }
            for row in rows
        ]


finding_repository = FindingRepository()
