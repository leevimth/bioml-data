"""HTTP transport integration for content-addressed artifact ingest."""

import logging
import traceback
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import httpx2
import pytest
from pydantic import ValidationError

import bioml_data as bio
import bioml_data._http_artifacts as http_artifacts


def _request(content: bytes) -> bio.ArtifactRequest:
    return bio.ArtifactRequest(
        logical_name="fixture.bin",
        source_uri="https://example.test/artifacts/fixture.bin",
        accession="HTTP-TEST-001",
        release="fixture-v1",
        retrieved_at=datetime(2026, 8, 30, 16, tzinfo=UTC),
        expected_byte_size=len(content),
        expected_sha256=sha256(content).hexdigest(),
        tool_version="bioml-data/0.0.0",
    )


def test_http_fake_streams_verified_content_into_cache(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Given: a deterministic wire-level response and canonical client defaults.
    content = b"verified HTTP artifact"
    seen_requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen_requests.append(request)
        return httpx2.Response(200, content=content)

    transfer = bio.HttpArtifactDownload(
        request=_request(content),
        cache=bio.ArtifactCache(tmp_path / "cache"),
    )
    caplog.set_level(logging.INFO, logger="bioml_data._http_artifacts")

    # When: retrieval runs through an HTTP transport fake.
    receipt = bio.download_artifact(
        transfer,
        transport=httpx2.MockTransport(handler),
    )

    # Then: the cache receives verified bytes and both wire events are observable.
    assert receipt.content_path.read_bytes() == content
    assert receipt.artifact_id == f"sha256:{sha256(content).hexdigest()}"
    assert tuple(request.method for request in seen_requests) == ("GET",)
    assert tuple(record.msg for record in caplog.records) == (
        "http.request",
        "http.response",
    )
    assert bio.DEFAULT_HTTP_CLIENT_CONFIGURATION.max_connections == 200
    assert bio.DEFAULT_HTTP_CLIENT_CONFIGURATION.max_keepalive_connections == 40
    assert bio.DEFAULT_HTTP_CLIENT_CONFIGURATION.keepalive_expiry == 30.0
    assert bio.DEFAULT_HTTP_CLIENT_CONFIGURATION.connect_timeout == 5.0
    assert bio.DEFAULT_HTTP_CLIENT_CONFIGURATION.read_timeout == 30.0
    assert bio.DEFAULT_HTTP_CLIENT_CONFIGURATION.write_timeout == 10.0
    assert bio.DEFAULT_HTTP_CLIENT_CONFIGURATION.pool_timeout == 10.0
    assert bio.DEFAULT_HTTP_CLIENT_CONFIGURATION.retries == 3
    assert bio.DEFAULT_HTTP_CLIENT_CONFIGURATION.follow_redirects
    assert bio.DEFAULT_HTTP_CLIENT_CONFIGURATION.tcp_nodelay


def test_http_checksum_mismatch_is_not_published(tmp_path: Path) -> None:
    # Given: an HTTP response with the declared size but a different digest.
    expected = b"expected bytes"
    received = b"received bytes"
    transfer = bio.HttpArtifactDownload(
        request=_request(expected),
        cache=bio.ArtifactCache(tmp_path / "cache"),
    )
    transport = httpx2.MockTransport(
        lambda request: httpx2.Response(200, content=received),
    )

    # When: the response reaches checksum verification.
    with pytest.raises(bio.ChecksumMismatchError):
        _ = bio.download_artifact(transfer, transport=transport)

    # Then: no content-addressed artifact is published.
    assert tuple((tmp_path / "cache").rglob("blob")) == ()


def test_http_incomplete_response_is_not_published(tmp_path: Path) -> None:
    # Given: an HTTP response that ends before the pinned byte size.
    complete = b"complete bytes"
    transfer = bio.HttpArtifactDownload(
        request=_request(complete),
        cache=bio.ArtifactCache(tmp_path / "cache"),
    )
    transport = httpx2.MockTransport(
        lambda request: httpx2.Response(200, content=complete[:-2]),
    )

    # When: the truncated response reaches size verification.
    with pytest.raises(bio.IncompleteDownloadError):
        _ = bio.download_artifact(transfer, transport=transport)

    # Then: no content-addressed artifact is published.
    assert tuple((tmp_path / "cache").rglob("blob")) == ()


def test_http_error_is_typed_and_not_published(tmp_path: Path) -> None:
    # Given: an upstream server that returns an explicit error response.
    content = b"expected bytes"
    transfer = bio.HttpArtifactDownload(
        request=_request(content),
        cache=bio.ArtifactCache(tmp_path / "cache"),
    )
    transport = httpx2.MockTransport(
        lambda request: httpx2.Response(503, content=b"unavailable"),
    )

    # When: retrieval receives the failed status.
    with pytest.raises(bio.ArtifactHttpError) as captured:
        _ = bio.download_artifact(transfer, transport=transport)

    # Then: typed status evidence is retained and no artifact is published.
    assert captured.value.status_code == 503
    assert captured.value.source_uri == transfer.request.source_uri
    assert tuple((tmp_path / "cache").rglob("blob")) == ()


def test_http_status_wrapper_drops_signed_url_exception_chain(tmp_path: Path) -> None:
    # Given: a signed source URL whose server returns an error status.
    content = b"expected bytes"
    source_uri = "https://alice:password@example.test/file?token=top-secret"
    transfer = bio.HttpArtifactDownload(
        request=_request(content).model_copy(update={"source_uri": source_uri}),
        cache=bio.ArtifactCache(tmp_path / "cache"),
    )
    transport = httpx2.MockTransport(
        lambda request: httpx2.Response(503, content=b"unavailable"),
    )

    # When: the HTTP status is converted to the public typed wrapper.
    with pytest.raises(bio.ArtifactHttpError) as captured:
        _ = bio.download_artifact(transfer, transport=transport)

    # Then: no raw httpx2 exception chain or rendered traceback exposes the URL.
    rendered = "".join(traceback.format_exception(captured.value))
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert "alice" not in rendered
    assert "password" not in rendered
    assert "token" not in rendered
    assert "top-secret" not in rendered
    assert "https://example.test/file" in rendered


def test_artifact_source_url_requires_https() -> None:
    # Given: a source URL using cleartext HTTP.
    content = b"expected bytes"
    payload = _request(content).model_dump()
    payload["source_uri"] = "http://example.test/artifact.bin"

    # When: it crosses the artifact request boundary.
    with pytest.raises(ValidationError):
        _ = bio.ArtifactRequest.model_validate(payload)

    # Then: the boundary rejects non-HTTPS source URLs.


def test_redirect_downgrade_is_rejected_before_cleartext_request(
    tmp_path: Path,
) -> None:
    # Given: an HTTPS source that redirects to cleartext HTTP.
    content = b"redirected artifact"
    seen_urls: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen_urls.append(str(request.url))
        return httpx2.Response(
            302,
            headers={"location": "http://example.test/insecure.bin"},
        )

    transfer = bio.HttpArtifactDownload(
        request=_request(content),
        cache=bio.ArtifactCache(tmp_path / "cache"),
    )

    # When: the canonical redirect-following client resolves the downgrade.
    with pytest.raises(bio.InsecureArtifactUrlError):
        _ = bio.download_artifact(
            transfer,
            transport=httpx2.MockTransport(handler),
        )

    # Then: no cleartext request reaches the transport.
    assert seen_urls == [transfer.request.source_uri]


def test_https_redirect_is_followed_with_canonical_client(tmp_path: Path) -> None:
    # Given: an HTTPS redirect to a verified final response.
    content = b"redirected artifact"
    seen_urls: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen_urls.append(str(request.url))
        if request.url.path == "/artifacts/fixture.bin":
            return httpx2.Response(
                302,
                headers={"location": "https://cdn.example.test/final.bin"},
            )
        return httpx2.Response(200, content=content)

    transfer = bio.HttpArtifactDownload(
        request=_request(content),
        cache=bio.ArtifactCache(tmp_path / "cache"),
    )

    # When: retrieval follows the secure redirect.
    receipt = bio.download_artifact(
        transfer,
        transport=httpx2.MockTransport(handler),
    )

    # Then: both HTTPS requests occur and verified content is stored.
    assert seen_urls == [
        transfer.request.source_uri,
        "https://cdn.example.test/final.bin",
    ]
    assert receipt.content_path.read_bytes() == content


def test_transport_failure_redacts_signed_url_from_log_and_error(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Given: a signed source URL and a transport failure before a response.
    content = b"expected bytes"
    source_uri = "https://alice:password@example.test/file?token=top-secret"
    transfer = bio.HttpArtifactDownload(
        request=_request(content).model_copy(update={"source_uri": source_uri}),
        cache=bio.ArtifactCache(tmp_path / "cache"),
    )
    failure_reason = f"network unavailable for {source_uri}"

    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError(failure_reason, request=request)

    caplog.set_level(logging.ERROR, logger="bioml_data._http_artifacts")
    caplog.handler.setFormatter(logging.Formatter("%(message)s %(http_url)s"))

    # When: the failure is logged and converted to the typed boundary error.
    with pytest.raises(http_artifacts.ArtifactTransportError) as captured:
        _ = bio.download_artifact(
            transfer,
            transport=httpx2.MockTransport(handler),
        )

    # Then: neither the exception nor logs expose URL credentials or query data.
    rendered = "".join(traceback.format_exception(captured.value))
    combined = f"{rendered}\n{caplog.text}"
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    assert "alice" not in combined
    assert "password" not in combined
    assert "token" not in combined
    assert "top-secret" not in combined
    assert "https://example.test/file" in combined
