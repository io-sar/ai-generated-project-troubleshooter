"""Valid raw data for domain models, as it arrives from a sample file or an LLM.

Each builder returns a fresh dict, so a test can break one field without affecting others.
"""

from typing import Any


def health_data(score: int = 55) -> dict[str, Any]:
    return {"score": score, "rationale": "Two milestones slipped this month."}


def risk_data(likelihood: int = 4, impact: int = 5) -> dict[str, Any]:
    return {
        "id": "R1",
        "description": "The vendor misses the API delivery date.",
        "likelihood": likelihood,
        "impact": impact,
        "owner": "Vendor manager",
        "mitigation": "Agree a weekly checkpoint with the vendor lead.",
        "escalation": "sponsor",
        "signal_ids": ["S1"],
    }


def sprint_data() -> dict[str, Any]:
    return {
        "goal": "Stop the slip from growing.",
        "actions": [
            {
                "description": "Freeze new scope.",
                "owner": "Product owner",
                "success_signal": "No new items enter the sprint.",
            }
        ],
    }


def report_data() -> dict[str, Any]:
    return {
        "health": {
            "schedule": health_data(30),
            "scope": health_data(55),
            "quality": health_data(75),
            "risk_control": health_data(45),
            "stakeholder_confidence": health_data(60),
        },
        "risks": [risk_data()],
        "recovery_plan": {
            "stabilize": sprint_data(),
            "recover": sprint_data(),
            "sustain": sprint_data(),
        },
        "stakeholder_updates": {
            "executive": "We are two weeks late and have a plan to recover.",
            "delivery_team": "Scope is frozen for the next sprint.",
            "customer": "The launch moves by two weeks.",
        },
        "decision_memo": {
            "context": "The vendor API is late.",
            "options": [
                {"title": "Wait for the vendor", "trade_offs": "Cheap, but the date slips."},
                {"title": "Build a stub", "trade_offs": "Keeps the date, costs a sprint."},
            ],
            "recommendation": "Build a stub.",
            "success_metrics": ["Integration tests pass by week 4."],
        },
        "raci": [
            {
                "activity": "Vendor follow-up",
                "assignments": [
                    {"role": "PM", "code": "A"},
                    {"role": "Vendor manager", "code": "R"},
                ],
            }
        ],
    }


def diagnosis_data() -> dict[str, Any]:
    return {
        "classification": "troubled",
        "summary": "Delivery depends on a vendor that is slipping.",
        "signals": [
            {
                "id": "S1",
                "observation": "The vendor has missed two dates.",
                "evidence": "The API was due in March and again in April.",
            }
        ],
        "things_to_watch": [],
    }
