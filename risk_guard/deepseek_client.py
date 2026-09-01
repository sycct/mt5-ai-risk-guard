import json
import logging

from openai import AsyncOpenAI
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from .models import AiRiskReport, Mt5Snapshot, RiskAssessment, RiskLevel
from .risk_rules import ACTIONS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是 MT5 黄金网格 EA 风控分析助手。
你的任务是根据账户、持仓、挂单、点差、保证金比例、总手数、净手数、浮亏和历史交易情况，判断当前爆仓风险。
你不能承诺盈利。你不能建议继续无限加仓。
如果出现单边行情、净手数过大、保证金比例下降、浮亏扩大，应优先建议停止 EA、删除挂单、降低仓位或人工处理。
你只能生成分析和建议，不能直接下达或执行交易指令。你的输出必须是 JSON。
不得猜测余额与净值差额来自隔夜利息、手续费、信用额或账户调整；只能引用输入中实际存在的字段。
如果 data_quality_issues 非空，必须明确指出数据无法完全对账，且不得虚构原因。
字段必须是 risk_level、summary、main_risks、recommended_actions、do_not_do、reasoning_brief。"""


class InvalidAiResponse(RuntimeError): pass


class DeepSeekRiskAnalyst:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    @retry(stop=stop_after_attempt(2), wait=wait_fixed(1),
           retry=retry_if_exception_type((InvalidAiResponse, json.JSONDecodeError, ValidationError)), reraise=True)
    async def analyze(self, snapshot: Mt5Snapshot, assessment: RiskAssessment) -> AiRiskReport:
        payload = {
            "hard_rule_level": assessment.level.name,
            "metrics": assessment.metrics.model_dump(mode="json"),
            "hard_rule_hits": [x.model_dump(mode="json") for x in assessment.hard_rule_hits],
            "history": snapshot.history.model_dump(mode="json") if snapshot.history else None,
            "missing_capabilities": snapshot.missing_capabilities,
        }
        response = await self.client.chat.completions.create(
            model=self.model, response_format={"type": "json_object"}, temperature=0.1,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        )
        content = response.choices[0].message.content
        if not content: raise InvalidAiResponse("DeepSeek returned empty content")
        try: report = AiRiskReport.model_validate_json(content)
        except (ValidationError, json.JSONDecodeError) as exc: raise InvalidAiResponse(str(exc)) from exc
        if report.risk_level < assessment.level:
            report.risk_level = assessment.level
            report.summary = f"硬规则等级为 {assessment.level.name}，不得由 AI 下调。{report.summary}"
        return report


def hard_rule_fallback(assessment: RiskAssessment, reason: str | None = None) -> AiRiskReport:
    risks = [hit.message for hit in assessment.hard_rule_hits if hit.level == assessment.level]
    summary = f"硬规则判定当前风险等级为 {assessment.level.name}。"
    if assessment.level is RiskLevel.DATA_UNAVAILABLE:
        summary = "关键 MT5 账户数据不可用，无法得出可靠风险等级。"
        risks = ["账户余额、净值或持仓能力缺失"]
    if reason: summary += " AI 分析暂不可用，已使用确定性规则报告。"
    return AiRiskReport(risk_level=assessment.level, summary=summary,
        main_risks=risks or ["当前硬规则未触发"], recommended_actions=ACTIONS[assessment.level],
        do_not_do=["不要无限加仓", "不要仅凭 AI 输出执行交易动作"],
        reasoning_brief="风险等级取所有已触发硬阈值中的最高等级；缺失数据不作臆测。")
