import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from invoice_extractor.transport import request_object, MAX_RESPONSE_BYTES


def response(content):
    return io.BytesIO(
        json.dumps({"choices": [{"message": {"content": content}}]}).encode()
    )


class ProviderContractTests(unittest.TestCase):
    def test_valid_completion_is_decoded(self):
        with patch(
            "invoice_extractor.transport.urllib.request.urlopen",
            return_value=response('{"ok": true}'),
        ):
            self.assertEqual(
                request_object({}, "https://example.test/v1", "test-key"), {"ok": True}
            )

    def test_malformed_and_nonfinite_completions_are_rejected(self):
        for content in ["[]", "null", '{"number": NaN}', "not JSON"]:
            with (
                self.subTest(content=content),
                patch(
                    "invoice_extractor.transport.urllib.request.urlopen",
                    return_value=response(content),
                ),
                self.assertRaises(ValueError),
            ):
                request_object({}, "https://example.test/v1", "test-key")

    def test_missing_envelope_and_oversized_body_are_rejected(self):
        for body in [b"{}", b"x" * (MAX_RESPONSE_BYTES + 1)]:
            with (
                patch(
                    "invoice_extractor.transport.urllib.request.urlopen",
                    return_value=io.BytesIO(body),
                ),
                self.assertRaises(ValueError),
            ):
                request_object({}, "https://example.test/v1", "test-key")

    def test_transient_error_retries_with_backoff(self):
        error = HTTPError("https://example.test", 503, "Unavailable", {}, None)
        with (
            patch(
                "invoice_extractor.transport.urllib.request.urlopen",
                side_effect=[error, response("{}")],
            ) as opening,
            patch("invoice_extractor.transport.time.sleep") as sleep,
        ):
            self.assertEqual(
                request_object({}, "https://example.test/v1", "test-key"), {}
            )
            self.assertEqual(opening.call_count, 2)
            sleep.assert_called_once_with(0.25)

    def test_permanent_auth_failure_is_not_retried(self):
        error = HTTPError("https://example.test", 401, "Unauthorized", {}, None)
        with (
            patch(
                "invoice_extractor.transport.urllib.request.urlopen", side_effect=error
            ) as opening,
            self.assertRaises(HTTPError),
        ):
            request_object({}, "https://example.test/v1", "test-key")
        self.assertEqual(opening.call_count, 1)

    def test_timeout_has_a_bounded_retry_budget(self):
        with (
            patch(
                "invoice_extractor.transport.urllib.request.urlopen",
                side_effect=TimeoutError,
            ) as opening,
            patch("invoice_extractor.transport.time.sleep"),
            self.assertRaises(TimeoutError),
        ):
            request_object({}, "https://example.test/v1", "test-key")
        self.assertEqual(opening.call_count, 3)
