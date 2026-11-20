"""The Computer-to-UEX handoff exposed to Computer's model."""

import re

UEX_HANDOFF_TOOL_NAME = "transfer_to_uex"
UEX_HANDOFF_COMPLETED = "__wingman_uex_handoff_completed__"
_UEX_REQUEST_PATTERN = re.compile(
    r"\b(?:trade\s+routes?|commodit(?:y|ies)|market\s+(?:data|prices?|lookups?|search))\b",
    re.IGNORECASE,
)
_UEX_ECONOMY_LOOKUP_PATTERN = re.compile(
    r"\b(?:where\s+(?:can|do)\s+i\s+(?:buy|purchase)|where\s+to\s+(?:buy|purchase)|"
    r"purchase\s+price|buying\s+price|selling\s+price|shop\s+inventory|in[- ]game\s+price|"
    r"(?:ship|vehicle|commodity|item|component|weapon)\s+(?:price|cost|availability|stock)|"
    r"(?:price|cost)\s+(?:of|for)\s+(?:the\s+)?(?:ship|vehicle|commodity|item|component|weapon))\b",
    re.IGNORECASE,
)
_SHIP_RENTAL_PATTERN = re.compile(
    r"\b(?:ship|vehicle|spaceship)\b.{0,80}\b(?:rent(?:al|ing)?|lease)\b"
    r"|\b(?:rent(?:al|ing)?|lease)\b.{0,80}\b(?:ship|vehicle|spaceship|auec|in[- ]game)\b"
    r"|\b(?:where|how\s+much|price|cost|rental)\b.{0,80}\b(?:rent|lease)\b"
    r"|\b(?:rent|lease)\b.{0,80}\b(?:where|how\s+much|price|cost)\b",
    re.IGNORECASE,
)
_UEX_NAME = r"(?:u\s*e\s*x(?:c)?|u\s*x(?:\s+u\s*e\s*x(?:c)?)?)"
_UEX_HANDOFF_PATTERN = re.compile(
    rf"\b(?:pass|hand|transfer|send|switch|connect|route)\s+"
    rf"(?:(?:me|us|this|it|the\s+request|the\s+conversation)\s+)?"
    rf"(?:(?:over|through)\s+)?to\s+{_UEX_NAME}\b"
    rf"|\b(?:talk|speak|chat)\s+(?:to|with)\s+{_UEX_NAME}\b"
    rf"|\b(?:switch|connect|transfer)\s+to\s+{_UEX_NAME}\b",
    re.IGNORECASE,
)
_UEX_CONTEXT_PATTERN = re.compile(
    r"\b(?:ship|vehicle|cargo|scu|auec|budget|constellation|cutlass|"
    r"trade\s+request|one\s+hop|multi[- ]stop|system\s+jumps?)\b",
    re.IGNORECASE,
)
_SAVED_SHIP_CONTEXT_PATTERN = re.compile(
    r"\b(?:ship|vehicle|cargo|scu|constellation|cutlass)\b", re.IGNORECASE
)
_ONE_OFF_FINANCE_PATTERN = re.compile(r"\b(?:budget|auec|credit balance)\b", re.IGNORECASE)


def is_uex_request(text: str) -> bool:
    """Recognize UEX requests, ship rentals, and explicit transfers to UEX."""
    text = text or ""
    return bool(
        _UEX_REQUEST_PATTERN.search(text)
        or _UEX_ECONOMY_LOOKUP_PATTERN.search(text)
        or _SHIP_RENTAL_PATTERN.search(text)
        or _UEX_HANDOFF_PATTERN.search(text)
    )


def build_uex_handoff_request(
    request: str,
    recent_messages=(),
    persistent_facts=(),
) -> str:
    """Add relevant Computer context without forwarding unrelated memories.

    UEXC has its own conversation and memory, so it cannot see Computer's
    saved ship details or recent one-off trade constraints unless Core includes
    them in this handoff. Persistent financial facts are deliberately omitted:
    budgets are taken only from the recent conversation for the current request.
    """
    context: list[str] = []
    seen: set[str] = set()

    def add_line(line: str) -> None:
        line = " ".join((line or "").split())
        if not line:
            return
        key = line.casefold()
        if key in seen:
            return
        seen.add(key)
        context.append(line[:400])

    for fact in persistent_facts or ():
        content = fact.get("content") if isinstance(fact, dict) else getattr(fact, "content", "")
        if (
            content
            and _SAVED_SHIP_CONTEXT_PATTERN.search(content)
            and not _ONE_OFF_FINANCE_PATTERN.search(content)
        ):
            add_line(f"Saved ship detail: {content}")

    for message in list(recent_messages or ())[-20:]:
        role = message.get("role") if isinstance(message, dict) else getattr(message, "role", None)
        if role not in ("user", "assistant"):
            continue
        content = message.get("content", "") if isinstance(message, dict) else getattr(message, "content", "")
        if isinstance(content, list):
            content = " ".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        if not isinstance(content, str) or not _UEX_CONTEXT_PATTERN.search(content):
            continue
        normalized = " ".join(content.split()).casefold()
        if normalized == " ".join((request or "").split()).casefold():
            continue
        add_line(f"{('Computer' if role == 'assistant' else 'User')} said: {content}")

    if not context:
        return request

    context_text = "\n".join(f"- {line}" for line in context)[-1800:]
    return (
        f"User request: {request}\n\n"
        "Relevant context from Computer's recent conversation and confirmed saved "
        "ship details (for this request only):\n"
        f"{context_text}\n\n"
        "Use these details directly. For vehicle rentals, purchase prices, item/commodity "
        "prices, stock, locations, and routes, use UEXCorp as the primary source. Use "
        "StarHead only if UEXCorp does not contain the requested fact, and identify it "
        "as a fallback. Never use a StarHead purchase price to answer a rental question; "
        "a missing UEX record means unknown, not pledge-only. Do not ask for cargo, budget, "
        "or route stops for a simple rental lookup. Do not ask the user to repeat information "
        "already provided. Treat a budget or other explicitly one-off constraint as applying "
        "only to this request; do not save it as a lasting preference."
    )

UEX_HANDOFF_TOOL = {
    "type": "function",
    "function": {
        "name": UEX_HANDOFF_TOOL_NAME,
        "description": (
            "You MUST transfer Star Citizen trade, commodity, market, ship or item price, "
            "shop availability, purchase-location, rental, and active-route requests to the "
            "specialist Wingman UEX (the UEXC tab). Also transfer when the user explicitly "
            "asks to pass, switch, or connect them to UEX. Do not answer these requests "
            "yourself or use a UEXCorp skill here. "
            "Core forwards the user's current request verbatim to UEXC, which answers in "
            "its own Wingman conversation; do not ask the user to repeat it. "
            "Do not use for unrelated requests."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}
