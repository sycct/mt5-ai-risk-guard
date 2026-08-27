import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .models import AiRiskReport, Mt5Snapshot, RiskAssessment


class JsonlStorage:
    def __init__(self, log_dir: Path) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _append(self, filename: str, record: dict[str, Any]) -> None:
        with (self.log_dir / filename).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def save_snapshot(self, snapshot: Mt5Snapshot, assessment: RiskAssessment, report: AiRiskReport) -> None:
        m = assessment.metrics
        record = {"timestamp": snapshot.timestamp.isoformat(), "account": snapshot.account.login,
            "symbol": snapshot.symbol.symbol if snapshot.symbol else None, "balance": m.balance,
            "equity": m.equity, "floating_profit": m.floating_profit, "margin_level": m.margin_level,
            "total_lots": m.total_lots, "net_lots": m.net_lots, "risk_level": assessment.level.name,
            "hard_rule_hits": [x.model_dump(mode="json") for x in assessment.hard_rule_hits],
            "deepseek_summary": report.summary, "missing_capabilities": snapshot.missing_capabilities}
        self._append("risk_snapshots.jsonl", record)
        if assessment.level.name not in ("OK", "CAUTION"):
            self._append("alerts.jsonl", record)

    def audit(self, event: str, details: dict[str, Any]) -> None:
        self._append("audit.jsonl", {"timestamp": datetime.now().astimezone().isoformat(),
                                     "event": event, "details": details})

    def records_for(self, target: date) -> list[dict[str, Any]]:
        path = self.log_dir / "risk_snapshots.jsonl"
        if not path.exists(): return []
        records = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
                if datetime.fromisoformat(item["timestamp"]).astimezone().date() == target: records.append(item)
            except (ValueError, KeyError, json.JSONDecodeError): continue
        return records

