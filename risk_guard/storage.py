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
            "account_currency": snapshot.account.currency,
            "symbol": snapshot.symbol.symbol if snapshot.symbol else None, "balance": m.balance,
            "equity": m.equity, "credit": m.credit, "account_profit": m.account_profit,
            "account_commission": m.account_commission,
            "floating_profit": m.floating_profit,
            "positions_floating_profit": m.positions_floating_profit,
            "equity_balance_gap": m.equity_balance_gap,
            "reconciliation_error": m.reconciliation_error,
            "data_quality_issues": m.data_quality_issues,
            "margin": snapshot.account.margin, "free_margin": snapshot.account.free_margin,
            "margin_level": m.margin_level, "total_lots": m.total_lots, "net_lots": m.net_lots,
            "total_positions_count": m.total_positions_count,
            "pending_orders_count": m.pending_orders_count,
            "ea_positions_count": m.ea_positions_count,
            "ea_pending_orders_count": m.ea_pending_orders_count,
            "today_closed_profit": snapshot.history.today_closed_profit if snapshot.history else None,
            "today_gross_profit": snapshot.history.today_gross_profit if snapshot.history else None,
            "today_gross_loss": snapshot.history.today_gross_loss if snapshot.history else None,
            "today_trade_count": snapshot.history.today_trade_count if snapshot.history else None,
            "risk_level": assessment.level.name,
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
