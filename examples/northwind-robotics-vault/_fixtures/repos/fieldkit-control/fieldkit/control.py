"""Synthetic control-loop helpers for the Vaultwright example repo."""


def route_inspection(confidence: float, defect_detected: bool) -> str:
    if defect_detected:
        return "reject"
    if confidence < 0.85:
        return "review"
    return "accept"
