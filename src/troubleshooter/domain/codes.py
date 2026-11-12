"""Fixed values used across the report.

Values are stored as these codes (in samples, LLM output and session state) and are
translated only for display, so a code must never change once samples are recorded.
"""

from enum import StrEnum


class Dimension(StrEnum):
    SCHEDULE = "schedule"
    SCOPE = "scope"
    QUALITY = "quality"
    RISK_CONTROL = "risk_control"
    STAKEHOLDER_CONFIDENCE = "stakeholder_confidence"


class HealthLabel(StrEnum):
    GOOD = "good"
    PROBLEMATIC = "problematic"
    AT_RISK = "at_risk"


class EscalationLevel(StrEnum):
    TEAM = "team"
    PM = "pm"
    SPONSOR = "sponsor"
    STEERING = "steering"


class RaciCode(StrEnum):
    RESPONSIBLE = "R"
    ACCOUNTABLE = "A"
    CONSULTED = "C"
    INFORMED = "I"


class InputClassification(StrEnum):
    """What stage 1 decided the visitor's text is. Only TROUBLED goes on to stage 2."""

    TROUBLED = "troubled"
    HEALTHY = "healthy"
    TOO_THIN = "too_thin"
    OFF_TOPIC = "off_topic"
