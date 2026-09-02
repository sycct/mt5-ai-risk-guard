from .models import Mt5Snapshot, RiskAssessment, RiskLevel, ShadowAction, ShadowDecision


def evaluate_shadow_actions(
    snapshot: Mt5Snapshot,
    assessment: RiskAssessment,
    ea_magic: int,
    confirmation_count: int,
    confirmation_required: int = 2,
) -> ShadowDecision:
    """Build an auditable action proposal without invoking any trading capability."""
    blocked: list[str] = []
    if assessment.level is RiskLevel.DATA_UNAVAILABLE:
        blocked.append("risk_data_unavailable")
    if snapshot.missing_capabilities:
        blocked.append("missing_capabilities")
    if assessment.metrics.data_quality_issues:
        blocked.append("data_quality_issues")

    ea_positions = [position for position in snapshot.positions if position.magic == ea_magic]
    ea_orders = [order for order in snapshot.pending_orders if order.magic == ea_magic]
    if assessment.level >= RiskLevel.WARNING and not ea_positions and not ea_orders:
        blocked.append("no_matching_ea_exposure")

    actions: list[ShadowAction] = []
    if assessment.level >= RiskLevel.WARNING and not blocked:
        actions.extend([
            ShadowAction(action="notify_human", target="account",
                         rationale="hard_rule_level_at_least_warning"),
            ShadowAction(action="pause_ea_new_entries", target=f"magic:{ea_magic}",
                         target_count=len(ea_positions),
                         rationale="prevent_additional_ea_exposure"),
        ])
        if assessment.level >= RiskLevel.DANGER and ea_orders:
            actions.append(ShadowAction(
                action="delete_ea_pending_orders", target=f"magic:{ea_magic}",
                target_count=len(ea_orders), rationale="danger_level_with_ea_pending_orders",
            ))

    confirmed = confirmation_count >= confirmation_required
    if actions and not confirmed:
        blocked.append("confirmation_pending")
    return ShadowDecision(
        timestamp=snapshot.timestamp,
        risk_level=assessment.level,
        eligible=bool(actions) and confirmed and not blocked,
        confirmation_count=confirmation_count,
        confirmation_required=confirmation_required,
        proposed_actions=actions,
        blocked_reasons=blocked,
        trigger_hits=[hit.message for hit in assessment.hard_rule_hits
                      if hit.level == assessment.level],
    )
