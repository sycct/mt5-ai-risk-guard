import asyncio
import logging
from datetime import date, datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from .config import Settings, get_settings
from .deepseek_client import DeepSeekRiskAnalyst, hard_rule_fallback
from .mcp_client import Mt5McpClient, ToolRegistry
from .models import RiskLevel
from .mt5_adapter import Mt5Adapter
from .reporter import COLORS, render_report, write_daily_report
from .risk_engine import calculate_metrics
from .risk_rules import DEFAULT_THRESHOLDS, Thresholds, evaluate_rules
from .storage import JsonlStorage

app = typer.Typer(help="MT5 MCP + DeepSeek 只读风控监控系统", no_args_is_help=True)
console = Console()


def _logging(settings: Settings) -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.DEBUG if settings.mt5_mcp_debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[RichHandler(console=console, show_path=False),
                  logging.FileHandler(settings.log_dir / "risk_guard.log", encoding="utf-8")], force=True)


def _client(settings: Settings) -> Mt5McpClient:
    return Mt5McpClient(settings.mt5_mcp_url, settings.auth_headers(),
                        settings.mt5_mcp_timeout_seconds, settings.mt5_mcp_debug)


def _thresholds(settings: Settings) -> dict:
    result = dict(DEFAULT_THRESHOLDS)
    overrides = {level: value for level, value in zip(result, (settings.caution_drawdown,
        settings.warning_drawdown, settings.danger_drawdown, settings.emergency_drawdown))}
    for level, value in overrides.items():
        old = result[level]; result[level] = Thresholds(value, old.total_lots, old.net_lots, old.margin_level)
    return result


async def _inspect() -> None:
    settings = get_settings(); _logging(settings)
    async with _client(settings) as client:
        tools = await client.list_tools()
        try: resources = await client.list_resources()
        except Exception as exc:
            logging.warning("MCP resources/list 不可用: %s", exc); resources = []
        table = Table("工具", "推断能力", "描述")
        registry = ToolRegistry(tools)
        mapping: dict[str, list[str]] = {}
        for tool_name, capability in (
            (registry.find_account_tool(), "账户"), (registry.find_positions_tool(), "持仓"),
            (registry.find_orders_tool(), "挂单"), (registry.find_symbol_info_tool(), "品种/行情"),
            (registry.find_history_tool(), "历史"),
        ):
            if tool_name:
                mapping.setdefault(tool_name, []).append(capability)
        for tool in tools:
            table.add_row(tool.name, "/".join(mapping.get(tool.name, ["未映射"])), tool.description)
        console.print(table)
        resource_table = Table("Resource URI", "名称", "描述")
        for resource in resources: resource_table.add_row(resource.uri, resource.name, resource.description)
        console.print(resource_table)
        console.print("[green]只完成能力发现，未调用任何交易动作。[/green]")


async def _check_once(quiet: bool = False):
    settings = get_settings(); _logging(settings); storage = JsonlStorage(settings.log_dir)
    try:
        async with _client(settings) as client:
            snapshot = await Mt5Adapter(client, settings.mt5_symbol).fetch_snapshot()
    except Exception as exc:
        storage.audit("mcp_unavailable", {"error_type": type(exc).__name__, "message": str(exc)})
        console.print(f"[red]MT5 MCP 暂不可用：{exc}[/red]")
        return None
    critical_missing = [name for name in snapshot.missing_capabilities
                        if name in ("account", "account_data", "positions")]
    assessment = evaluate_rules(calculate_metrics(snapshot, settings.ea_magic), _thresholds(settings),
                                critical_missing)
    report = hard_rule_fallback(assessment)
    if settings.deepseek_api_key and assessment.level is not RiskLevel.DATA_UNAVAILABLE:
        try: report = await DeepSeekRiskAnalyst(settings.deepseek_api_key, settings.deepseek_base_url, settings.deepseek_model).analyze(snapshot, assessment)
        except Exception as exc:
            logging.warning("DeepSeek 不可用，使用硬规则报告: %s", exc)
            report = hard_rule_fallback(assessment, str(exc))
    else:
        logging.info("未配置 DEEPSEEK_API_KEY，使用硬规则报告")
    storage.save_snapshot(snapshot, assessment, report)
    storage.audit("risk_check", {"risk_level": assessment.level.name, "read_only": True})
    if not quiet: render_report(console, snapshot, assessment, report)
    return assessment


@app.command()
def inspect() -> None:
    """发现并打印 MCP tools/resources；不执行交易动作。"""
    try: asyncio.run(_inspect())
    except Exception as exc:
        console.print(f"[red]检查 MCP 失败：{exc}[/red]"); raise typer.Exit(1)


@app.command()
def once() -> None:
    """执行一次只读风险检查。"""
    asyncio.run(_check_once())


@app.command()
def watch(interval: Annotated[int, typer.Option(min=1, help="检查间隔（秒）")] = 60) -> None:
    """周期执行只读风险检查；Ctrl+C 停止。"""
    async def loop() -> None:
        next_check = asyncio.get_running_loop().time()
        while True:
            result = await _check_once(quiet=True)
            now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
            if result:
                color = COLORS[result.level]
                console.print(f"[{color}]{now} 风险等级：{result.level.name}[/{color}]")
                if result.level.name in ("WARNING", "DANGER", "EMERGENCY"):
                    console.print(f"[bold red]⚠ 高风险提示：{result.level.name}，请人工检查账户。[/bold red]")
                elif result.level is RiskLevel.DATA_UNAVAILABLE:
                    console.print("[bold magenta]关键数据不可用：本次检查不能作为风控依据。[/bold magenta]")
            next_check += interval
            await asyncio.sleep(max(0, next_check - asyncio.get_running_loop().time()))
    try: asyncio.run(loop())
    except KeyboardInterrupt: console.print("\n[yellow]监控已停止。[/yellow]")


@app.command()
def report(date_value: Annotated[str, typer.Option("--date", help="today 或 YYYY-MM-DD")] = "today") -> None:
    """根据本地快照生成 Markdown 日报。"""
    settings = get_settings(); _logging(settings)
    try: target = date.today() if date_value.lower() == "today" else date.fromisoformat(date_value)
    except ValueError: console.print("[red]日期必须为 today 或 YYYY-MM-DD[/red]"); raise typer.Exit(2)
    path = write_daily_report(JsonlStorage(settings.log_dir).records_for(target), target, settings.report_dir)
    console.print(f"[green]报告已生成：{path}[/green]")


if __name__ == "__main__":
    app()
