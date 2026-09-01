# MT5 AI Risk Guard

面向 Windows Server VPS 上 MT5 黄金网格/狙击手 EA 的**只读风控监控器**。它通过本地 MCP 动态发现并读取账户、行情、持仓、挂单和历史数据，以确定性硬规则给出风险等级，并可让 DeepSeek 生成中文解释。项目目标是降低风险、保留审计线索，不承诺盈利。

当前仅实现第一阶段：`inspect`、单次检查、循环监控、硬规则、DeepSeek 报告、日志和日报。代码中没有下单、平仓、删单或暂停 EA 的实现。

## 安装

需要 Python 3.11+，建议在运行 MT5 的同一台 Windows VPS 上执行：

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

也可以使用传统 requirements 文件安装：

```powershell
python -m pip install -r requirements.txt
# 开发和运行测试时：
python -m pip install -r requirements-dev.txt
```

编辑 `.env`。API Key 只从环境变量或未纳入 Git 的 `.env` 读取：

```env
MT5_MCP_URL=http://127.0.0.1:22346/mcp
MT5_MCP_API_KEY=your_key
MT5_MCP_AUTH_HEADER=Authorization
MT5_MCP_AUTH_SCHEME=Bearer
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

若服务使用 `X-API-Key: key`，设置 `MT5_MCP_AUTH_HEADER=X-API-Key` 且将 `MT5_MCP_AUTH_SCHEME` 留空。首先确认 MT5 已启动、MCP 服务已启用、端口可从本机访问。客户端使用 MCP Streamable HTTP JSON-RPC 初始化会话，并根据名称、描述及输入 schema 动态匹配能力，不依赖固定 MT5 工具名。

## 使用

```powershell
python -m risk_guard inspect
python -m risk_guard once
python -m risk_guard watch --interval 60
python -m risk_guard report --date today
python -m risk_guard report --date 2026-08-27
```

`inspect` 仅列出 tools/resources 和推断映射。`once` 读取一次并写日志。`watch` 在连接或 DeepSeek 临时不可用时记录错误并继续下一周期；按 Ctrl+C 停止。`report` 从本地 JSONL 生成 `reports/YYYY-MM-DD-risk-report.md`。

日志包括：

- `logs/risk_snapshots.jsonl`：每次成功检查
- `logs/alerts.jsonl`：WARNING 及以上告警
- `logs/audit.jsonl`：检查与故障审计
- `logs/risk_guard.log`：运行日志

认证值在 MCP debug 日志中会脱敏；仍不要把原始密钥放进工具参数、注释或提交记录。

## 风险规则与安全边界

风险等级依次为 OK、CAUTION、WARNING、DANGER、EMERGENCY。每一级分别比较净值回撤、总手数、净手数和保证金比例，取所有触发项中的最高等级。默认阈值针对约 50,000～60,000 USC 账户，只是保守起点，不替代经纪商规则或人工判断。

可在 `.env` 覆盖回撤阈值（例如 `WARNING_DRAWDOWN=5`）。其他阈值集中在 `risk_guard/risk_rules.py` 的 `DEFAULT_THRESHOLDS`；修改后应运行测试并按账户币种、合约规格、杠杆和策略回测校准。

DeepSeek 只负责定性解释，不负责复述或计算账户数值，也不能提出对冲、加仓、补仓、具体平仓或减仓策略。风险等级不能低于硬规则等级；关键指标和账户币种由程序直接展示，建议采用与风险等级对应的确定性规则。无 Key、网络失败、包含数字或响应无效时立即使用硬规则报告，不重复调用。缺失的 MCP 能力/字段会明确列出并保留为 `None`，不会编造。

所有交易开关默认关闭，且第一阶段若设置 `TRADE_ACTIONS_ENABLED=true` 会直接拒绝启动。自动平仓可能在滑点、点差扩大、网络抖动或错误映射工具时放大损失，也可能破坏对冲结构，因此不应作为默认行为；高风险场景应先由人核对账户和行情。

## 测试与无 MT5 演示

```powershell
pytest
python tests/mock_mcp_server.py --port 22346
```

另开终端，使用 `.env.example` 的本地地址执行 `inspect` 或 `once`。Mock 只提供读取工具。

## 常见问题

### 连接不上 `127.0.0.1:22346`

确认 Python 与 MT5/MCP 在同一台主机、MT5 终端和 MCP 已启动、端口一致，并检查 Windows 防火墙及端口占用。`127.0.0.1` 指当前运行 Python 的机器，不是远端 VPS。

### API Key 错误

核对 Key、header 名和 scheme。Bearer 常用 `Authorization` + `Bearer`；`X-API-Key` 通常需要空 scheme。不要在值中重复写两次 `Bearer`。

### MCP 没有某个工具

运行 `inspect` 查看实际暴露内容。报告会注明缺失能力；可根据该 MCP 的真实命名扩展 `ToolRegistry.KEYWORDS`，不应猜造字段。

### DeepSeek 返回非 JSON

客户端要求 `json_object`；响应无效时立即降级为硬规则报告，监控不会因此停止。也应确认所选模型支持 JSON 输出；模型名由服务端实际可用型号决定。

### Codex Cloud 无法访问本地 MT5

云端进程的 `127.0.0.1` 不是你的 VPS。应把本项目部署到 MT5 所在 VPS；不要为了方便把未经保护的 MCP 端口直接暴露到公网。

### 为什么只读模式更安全

动态发现可能遇到不同厂商的命名和返回结构，模型输出也可能不稳定。只读模式让硬规则和 AI 的错误最多形成提示，无法直接改变账户，同时保留日志供人工复核。后续提醒渠道可独立接入 Telegram、邮件或桌面通知。
