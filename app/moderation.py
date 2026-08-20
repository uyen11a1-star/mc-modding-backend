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


def pending(reason: str) -> dict:
    return {
        "status": "pending",
        "reason": reason,
        "confidence": None,
        "suggested_tags": [],
    }


def moderate_resource(metadata: dict) -> dict:
    """Return approved/rejected only from validated model output; otherwise stay pending."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return pending("Gemini moderation is not configured; resource remains pending.")

    api_base = os.getenv("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
    model = os.getenv("GEMINI_MODERATION_MODEL", "gemini-3.7-flash")
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
            "responseFormat": {
                "text": {"mimeType": "application/json", "schema": MODERATION_SCHEMA["schema"]}
            },
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
        result = json.loads(body["candidates"][0]["content"]["parts"][0]["text"])
        decision = result["decision"]
        confidence = float(result["confidence"])
        if decision not in {"approved", "rejected"} or not 0 <= confidence <= 1:
            return pending("AI returned an invalid moderation decision.")
        if confidence < 0.6:
            return pending("AI confidence is too low for automatic publication.")
        return {
            "status": decision,
            "reason": result["reason"],
            "confidence": confidence,
            "suggested_tags": result["suggestedTags"],
        }
    except error.HTTPError as exc:
        return pending(f"Gemini provider rejected the review request (HTTP {exc.code}).")
    except error.URLError:
        return pending("Gemini provider could not be reached; resource remains pending.")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return pending("Gemini returned an invalid moderation response; resource remains pending.")
    except Exception:
        return pending("Gemini moderation could not complete; resource remains pending.")
