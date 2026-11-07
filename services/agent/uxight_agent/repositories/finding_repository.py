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


finding_repository = FindingRepository()
