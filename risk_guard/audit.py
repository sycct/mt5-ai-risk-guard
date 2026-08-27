class SafetyError(RuntimeError):
    pass


def ensure_trade_actions_disabled(trade_actions_enabled: bool) -> None:
    if trade_actions_enabled:
        raise SafetyError("Trade actions are disabled by default")

