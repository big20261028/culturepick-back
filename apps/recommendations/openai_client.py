from __future__ import annotations

import json

from django.conf import settings


class OpenAIRecommendationError(Exception):
    pass


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


def request_openai_recommendations(*, user_request: str, profile_snapshot: dict, candidates: list[dict], limit: int):
    api_key = getattr(settings, "OPENAI_API_SECRET_KEY", "")
    model_name = getattr(settings, "OPENAI_RECOMMENDATION_MODEL", "gpt-4o-mini")
    if not api_key:
        raise OpenAIRecommendationError("OPENAI_API_SECRET_KEY or OPENAI_API_KEY is not configured.")
    if not candidates:
        raise OpenAIRecommendationError("No recommendation candidates available.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise OpenAIRecommendationError("openai package is not installed.") from exc

    client = OpenAI(api_key=api_key)
    payload = {
        "user_request": user_request,
        "profile": profile_snapshot,
        "limit": limit,
        "candidates": candidates,
    }

    system_prompt = (
        "You are a Korean performing-arts recommendation assistant. "
        "Recommend only from the provided candidates. "
        "Never invent a performance_id, title, venue, date, price, or external fact. "
        "Return concise Korean reasons grounded in candidate data and user preferences."
    )

    try:
        response = client.responses.create(
            model=model_name,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "performance_recommendation_response",
                    "schema": RECOMMENDATION_SCHEMA,
                    "strict": True,
                }
            },
        )
    except Exception as exc:
        raise OpenAIRecommendationError(f"OpenAI request failed: {exc}") from exc

    output_text = _extract_output_text(response)
    if not output_text:
        raise OpenAIRecommendationError("OpenAI response did not include output text.")

    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise OpenAIRecommendationError("OpenAI response was not valid JSON.") from exc

    raw = {
        "id": getattr(response, "id", ""),
        "model": getattr(response, "model", model_name),
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
