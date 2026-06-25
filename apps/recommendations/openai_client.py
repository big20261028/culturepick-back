from __future__ import annotations

import json

from django.conf import settings


class OpenAIRecommendationError(Exception):
    pass


SUPPORTED_AI_PROVIDERS = {"openai", "gms"}
DEFAULT_GMS_OPENAI_BASE_URL = "https://gms.ssafy.io/gmsapi/api.openai.com/v1"


RECOMMENDATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "recommendations": {
            "type": "array",
            "maxItems": 10,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "performance_id": {"type": "string"},
                    "rank": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["performance_id", "rank", "reason"],
            },
        },
    },
    "required": ["summary", "recommendations"],
}


def get_recommendation_provider_name() -> str:
    provider = getattr(settings, "AI_RECOMMENDATION_PROVIDER", "openai")
    provider = (provider or "openai").strip().lower()
    if provider not in SUPPORTED_AI_PROVIDERS:
        raise OpenAIRecommendationError(
            f"Unsupported AI_RECOMMENDATION_PROVIDER: {provider}. "
            f"Choose one of {', '.join(sorted(SUPPORTED_AI_PROVIDERS))}."
        )
    return provider


def _provider_config() -> dict:
    provider = get_recommendation_provider_name()
    if provider == "gms":
        return {
            "provider": provider,
            "api_key": getattr(settings, "GMS_API_KEY", ""),
            "model": getattr(settings, "GMS_RECOMMENDATION_MODEL", "gpt-4.1"),
            "base_url": getattr(settings, "GMS_OPENAI_BASE_URL", DEFAULT_GMS_OPENAI_BASE_URL),
        }
    return {
        "provider": provider,
        "api_key": getattr(settings, "OPENAI_API_SECRET_KEY", ""),
        "model": getattr(settings, "OPENAI_RECOMMENDATION_MODEL", "gpt-4o-mini"),
        "base_url": "",
    }


def request_openai_recommendations(*, user_request: str, profile_snapshot: dict, candidates: list[dict], limit: int):
    config = _provider_config()
    provider = config["provider"]
    api_key = config["api_key"]
    model_name = config["model"]
    if not api_key:
        if provider == "gms":
            raise OpenAIRecommendationError("GMS_API_KEY or GMS_KEY is not configured.")
        raise OpenAIRecommendationError("OPENAI_API_SECRET_KEY or OPENAI_API_KEY is not configured.")
    if not candidates:
        raise OpenAIRecommendationError("No recommendation candidates available.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise OpenAIRecommendationError("openai package is not installed.") from exc

    client_kwargs = {"api_key": api_key}
    if config["base_url"]:
        client_kwargs["base_url"] = config["base_url"]
    client = OpenAI(**client_kwargs)
    compact_profile = {
        "is_personalized": profile_snapshot.get("is_personalized", False),
        "has_request_signal": profile_snapshot.get("has_request_signal", False),
        "request_intent": profile_snapshot.get("request_intent", {}),
        "constraint_notes": profile_snapshot.get("constraint_notes", []),
        "conversation_context": profile_snapshot.get("conversation_context", {}),
        "top_user_signals": (profile_snapshot.get("source_summary") or {}).get("top_signals", []),
    }
    payload = {
        "user_request": user_request,
        "profile": compact_profile,
        "limit": limit,
        "candidates": candidates,
    }

    system_prompt = (
        "You are a Korean performing-arts recommendation assistant. "
        "Use only the candidates. Do not invent facts. "
        "Return friendly Korean JSON for a frontend card UI. "
        "summary: one natural sentence under 100 Korean chars that reflects the user's request. "
        "Each reason must be one string with 2 short Korean sentences under 220 Korean chars total. "
        "In each reason, include why it matches the user request, one concrete clue from the candidate, "
        "and a useful viewing opinion or caveat. "
        "If exact constraints cannot be verified, say what data is missing and why the candidate is still the closest match. "
        "If constraint_notes exist, mention the relaxed or missing condition naturally. "
        "For accessibility, say data is unavailable unless a candidate explicitly proves support. "
        "Keep the tone warm and confident, not generic."
    )

    try:
        request_kwargs = {
            "model": model_name,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "performance_recommendation_response",
                    "schema": RECOMMENDATION_SCHEMA,
                    "strict": True,
                }
            },
        }
        max_output_tokens = getattr(settings, "AI_RECOMMENDATION_MAX_OUTPUT_TOKENS", 450)
        if max_output_tokens:
            request_kwargs["max_output_tokens"] = max_output_tokens
        temperature = getattr(settings, "AI_RECOMMENDATION_TEMPERATURE", None)
        if temperature is not None:
            request_kwargs["temperature"] = temperature
        response = client.responses.create(**request_kwargs)
    except Exception as exc:
        raise OpenAIRecommendationError(f"{provider} request failed: {exc}") from exc

    output_text = _extract_output_text(response)
    if not output_text:
        raise OpenAIRecommendationError(f"{provider} response did not include output text.")

    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise OpenAIRecommendationError(f"{provider} response was not valid JSON.") from exc

    raw = {
        "provider": provider,
        "id": getattr(response, "id", ""),
        "model": getattr(response, "model", model_name),
        "usage": _to_jsonable(getattr(response, "usage", None)),
        "output_text": output_text,
    }
    return parsed, raw, model_name


def _extract_output_text(response) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return output_text

    chunks = []
    for output in getattr(response, "output", []) or []:
        for content in getattr(output, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                chunks.append(text)
    return "".join(chunks)


def _to_jsonable(value):
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return value
    return {
        key: getattr(value, key)
        for key in dir(value)
        if not key.startswith("_") and isinstance(getattr(value, key), (int, float, str, bool, type(None)))
    }
