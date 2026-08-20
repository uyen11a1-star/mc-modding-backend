"""Structured, fail-closed metadata moderation for Minecraft resources."""

import json
import os
import time
from urllib import error, request


MODERATION_SCHEMA = {
    "name": "resource_moderation",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "decision": {"type": "string", "enum": ["approved", "rejected"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string", "minLength": 1, "maxLength": 600},
            "suggestedTags": {
                "type": "array",
                "items": {"type": "string", "maxLength": 40},
                "maxItems": 8,
            },
            "riskFlags": {
                "type": "array",
                "items": {"type": "string", "maxLength": 60},
                "maxItems": 8,
            },
        },
        "required": ["decision", "confidence", "reason", "suggestedTags", "riskFlags"],
        "additionalProperties": False,
    },
}

# Gemini GenerateContent supports a defined JSON Schema subset. Keep provider-only
# constraints compatible here and enforce additional limits after parsing.
GEMINI_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["approved", "rejected"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
        "suggestedTags": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "riskFlags": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
    },
    "required": ["decision", "confidence", "reason", "suggestedTags", "riskFlags"],
    "additionalProperties": False,
}


def pending(reason: str) -> dict:
    return {
        "status": "pending",
        "reason": reason,
        "confidence": None,
        "suggested_tags": [],
    }


def provider_error_reason(exc: error.HTTPError) -> str:
    """Return a bounded provider error description without exposing credentials."""
    detail = ""
    try:
        response = json.loads(exc.read().decode("utf-8"))
        detail = str(response.get("error", {}).get("message", ""))
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
        detail = ""
    normalized = " ".join(detail.split())[:280]
    suffix = f": {normalized}" if normalized else ""
    return f"Gemini provider rejected the review request (HTTP {exc.code}){suffix}"


def moderate_resource(metadata: dict) -> dict:
    """Return approved/rejected only from validated model output; otherwise stay pending."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return pending("Gemini moderation is not configured; resource remains pending.")

    api_base = os.getenv("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    model = os.getenv("GEMINI_MODERATION_MODEL", "gemini-2.5-flash")
    system = (
        "You moderate Minecraft resource metadata. Evaluate only supplied text and file name, "
        "never infer file bytes. Reject scams, malware claims, credential theft, impersonation, "
        "harmful/off-topic material, or suspicious download instructions. Approve legitimate, "
        "relevant Minecraft metadata. Return only the required JSON."
    )
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": f"{system}\n\nResource metadata:\n"
                        f"{json.dumps(metadata, ensure_ascii=False)}"
                    }
                ],
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 500,
            "responseMimeType": "application/json",
            "responseJsonSchema": GEMINI_RESPONSE_SCHEMA,
        },
    }
    req = request.Request(
        f"{api_base}/models/{model}:generateContent",
        data=json.dumps(payload).encode("utf-8"),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        body = None
        for attempt in range(2):
            try:
                with request.urlopen(req, timeout=20) as response:  # nosec B310 -- configured HTTPS endpoint
                    body = json.loads(response.read().decode("utf-8"))
                break
            except error.HTTPError as exc:
                if exc.code == 503 and attempt == 0:
                    time.sleep(1)
                    continue
                raise
        if body is None:
            return pending("Gemini moderation could not complete; resource remains pending.")
        parts = body["candidates"][0]["content"]["parts"]
        output_texts = [
            part["text"]
            for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str) and not part.get("thought", False)
        ]
        if not output_texts:
            return pending("Gemini returned no structured moderation response.")
        result = json.loads(output_texts[-1])
        decision = result["decision"]
        confidence = float(result["confidence"])
        reason = result["reason"]
        suggested_tags = result["suggestedTags"]
        if (
            decision not in {"approved", "rejected"}
            or not 0 <= confidence <= 1
            or not isinstance(reason, str)
            or not 1 <= len(reason) <= 600
            or not isinstance(suggested_tags, list)
            or len(suggested_tags) > 8
            or not all(isinstance(tag, str) and len(tag) <= 40 for tag in suggested_tags)
        ):
            return pending("AI returned an invalid moderation decision.")
        if confidence < 0.6:
            return pending("AI confidence is too low for automatic publication.")
        return {
            "status": decision,
            "reason": reason,
            "confidence": confidence,
            "suggested_tags": suggested_tags,
        }
    except error.HTTPError as exc:
        return pending(provider_error_reason(exc))
    except error.URLError:
        return pending("Gemini provider could not be reached; resource remains pending.")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return pending("Gemini returned an invalid moderation response; resource remains pending.")
    except Exception:
        return pending("Gemini moderation could not complete; resource remains pending.")
