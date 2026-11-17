"""The Computer-to-UEX handoff exposed to Computer's model."""

import re

UEX_HANDOFF_TOOL_NAME = "transfer_to_uex"
UEX_HANDOFF_COMPLETED = "__wingman_uex_handoff_completed__"
_UEX_REQUEST_PATTERN = re.compile(
    r"\b(?:trade\s+routes?|commodit(?:y|ies)|market\s+(?:data|prices?|lookups?|search))\b",
    re.IGNORECASE,
)


def is_uex_request(text: str) -> bool:
    """Recognize explicit Star Citizen UEX and trade-market requests."""
    return bool(_UEX_REQUEST_PATTERN.search(text or ""))

UEX_HANDOFF_TOOL = {
    "type": "function",
    "function": {
        "name": UEX_HANDOFF_TOOL_NAME,
        "description": (
            "You MUST transfer any Star Citizen UEX Corp trade, route, commodity price, "
            "market-data, or active-route request to the specialist Wingman UEX (the UEXC "
            "tab). Do not answer these requests yourself or use a UEXCorp skill here. "
            "Core forwards the user's current request verbatim to UEXC, which answers in "
            "its own Wingman conversation; do not ask the user to repeat it. "
            "Do not use for unrelated requests."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}
