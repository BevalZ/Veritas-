"""Versioned final risk scoring boundary."""

from .legacy import RISK_RULE_VERSION, apply_risk_rules

__all__ = ["RISK_RULE_VERSION", "apply_risk_rules"]
