"""Bounded OpenAI-compatible JSON transport with retryable-failure handling."""

import json
import time
import urllib.error
import urllib.request

MAX_RESPONSE_BYTES = 1_048_576


def _invalid_constant(value):
    raise ValueError(f"Nonfinite JSON number: {value}")


def request_object(payload, base_url, api_key, timeout=45):
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload, allow_nan=False).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
            break
        except urllib.error.HTTPError as error:
            retryable = error.code in {429, 500, 502, 503, 504}
            error.close()
            if not retryable or attempt == 2:
                raise
            time.sleep(0.25 * 2**attempt)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(0.25 * 2**attempt)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("Provider response exceeds the supported size")
    try:
        envelope = json.loads(body, parse_constant=_invalid_constant)
        content = envelope["choices"][0]["message"]["content"]
        result = json.loads(content, parse_constant=_invalid_constant)
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise ValueError("Provider returned an invalid JSON completion") from error
    if not isinstance(result, dict):
        raise ValueError("Provider completion must be a JSON object")
    return result
