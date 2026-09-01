from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .models import AiRiskReport, Mt5Snapshot, RiskAssessment, RiskLevel

COLORS = {RiskLevel.DATA_UNAVAILABLE: "bold magenta", RiskLevel.OK: "green", RiskLevel.CAUTION: "yellow", RiskLevel.WARNING: "bright_yellow",
          RiskLevel.DANGER: "red", RiskLevel.EMERGENCY: "bold white on red"}


def render_report(console: Console, snapshot: Mt5Snapshot, assessment: RiskAssessment, report: AiRiskReport) -> None:
    m, color = assessment.metrics, COLORS[assessment.level]
    console.print(Panel(f"[bold]{assessment.level.name}[/bold]\n{report.summary}", title="MT5 风控", style=color))
    table = Table("指标", "当前值")
    for name, value in (("余额", m.balance), ("净值", m.equity), ("信用额", m.credit),
                        ("账户利润", m.account_profit), ("持仓浮动盈亏", m.positions_floating_profit),
                        ("净值-余额", m.equity_balance_gap), ("净值对账误差", m.reconciliation_error),
                        ("净值回撤 %", m.equity_drawdown_percent), ("保证金比例", m.margin_level),
                        ("总手数", m.total_lots), ("净手数", m.net_lots),
                        ("持仓 / 挂单", f"{m.total_positions_count} / {m.pending_orders_count}")):
        table.add_row(name, "未知" if value is None else str(round(value, 4) if isinstance(value, float) else value))
    console.print(table)
    console.print("[bold]主要风险：[/bold] " + "；".join(report.main_risks))
    console.print("[bold]建议：[/bold] " + "；".join(report.recommended_actions))
    console.print("[bold]不要做：[/bold] " + "；".join(report.do_not_do))
    if snapshot.missing_capabilities:
        console.print("[yellow]当前 MCP 未提供或读取失败：[/yellow]" + ", ".join(snapshot.missing_capabilities))
    if m.data_quality_issues:
        console.print("[bold yellow]数据质量问题：[/bold yellow]" + ", ".join(m.data_quality_issues))
    console.print("[dim]只读监控：未执行任何交易动作。[/dim]")


def write_daily_report(records: list[dict[str, Any]], target: date, report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"{target.isoformat()}-risk-report.md"
    levels = Counter(x.get("risk_level", "UNKNOWN") for x in records)
    highest = max(records, key=lambda x: RiskLevel[x.get("risk_level", "OK")]) if records else None
    lines = [f"# {target.isoformat()} MT5 风控日报", "", "> 本报告仅用于只读风险监控，不构成收益承诺或自动交易指令。", "",
             f"- 检查次数：{len(records)}", f"- 等级分布：{dict(levels)}",
             f"- 最高风险：{highest['risk_level'] if highest else '无记录'}", "", "## 检查记录", "",
             "| 时间 | 等级 | 净值 | 回撤相关浮盈亏 | 保证金比例 | 总手数 | 净手数 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for x in records:
        lines.append(f"| {x.get('timestamp')} | {x.get('risk_level')} | {x.get('equity')} | {x.get('floating_profit')} | {x.get('margin_level')} | {x.get('total_lots')} | {x.get('net_lots')} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
