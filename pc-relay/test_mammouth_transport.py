import os
from types import SimpleNamespace

import mammouth_client


def _fake_completed(stdout_text, returncode=0, stderr_text=""):
    return SimpleNamespace(
        stdout=stdout_text.encode("utf-8"),
        stderr=stderr_text.encode("utf-8"),
        returncode=returncode,
    )


def test_split_curl_response_real_newline():
    body, status = mammouth_client._split_curl_response(
        '{"choices":[]}\nBAZOR_HTTP_STATUS:200'
    )
    assert body == '{"choices":[]}'
    assert status == 200


def test_split_curl_response_literal_backslash_n():
    body, status = mammouth_client._split_curl_response(
        '{"choices":[]}\\nBAZOR_HTTP_STATUS:201'
    )
    assert body == '{"choices":[]}'
    assert status == 201


def test_single_attempt_accepts_http_200(monkeypatch):
    monkeypatch.setenv("MAMMOUTH_API_KEY", "unit-test-key")

    def fake_run(*args, **kwargs):
        return _fake_completed(
            '{"choices":[{"message":{"content":"MAMMOUTH_TRANSPORT_OK"}}],'
            '"model":"mammouth-recommended"}\nBAZOR_HTTP_STATUS:200'
        )

    monkeypatch.setattr(mammouth_client.subprocess, "run", fake_run)
    result = mammouth_client._single_chat_attempt(
        "ping", "recommended", "mammouth-recommended", 32, "test-correlation"
    )
    assert result["ok"] is True
    assert result["http_status"] == 200
    assert result["answer"] == "MAMMOUTH_TRANSPORT_OK"


def test_single_attempt_rejects_http_error(monkeypatch):
    monkeypatch.setenv("MAMMOUTH_API_KEY", "unit-test-key")

    def fake_run(*args, **kwargs):
        return _fake_completed(
            '{"error":{"message":"invalid api key"}}\nBAZOR_HTTP_STATUS:401'
        )

    monkeypatch.setattr(mammouth_client.subprocess, "run", fake_run)
    result = mammouth_client._single_chat_attempt(
        "ping", "recommended", "mammouth-recommended", 32, "test-correlation"
    )
    assert result["ok"] is False
    assert result["http_status"] == 401
    assert result["error"] == "mammouth_http"
    assert "invalid api key" in result.get("detail", "")


if __name__ == "__main__":
    # Petit smoke-test sans réseau, utilisable même sans pytest.
    body, status = mammouth_client._split_curl_response(
        '{"choices":[]}\nBAZOR_HTTP_STATUS:200'
    )
    assert body == '{"choices":[]}' and status == 200
    print("MAMMOUTH_TRANSPORT_PARSER_OK")
