"""Versioned final risk scoring boundary."""

from .legacy import apply_risk_rules
from .versions import RISK_RULE_VERSION

__all__ = ["RISK_RULE_VERSION", "apply_risk_rules"]
