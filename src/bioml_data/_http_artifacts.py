"""HTTP retrieval into the immutable content-addressed artifact cache."""

import logging
import socket
from dataclasses import dataclass
from typing import Final, final, override

import httpx2

from bioml_data._artifacts import ArtifactCache, ArtifactReceipt, ArtifactRequest
from bioml_data._url_security import redact_url

_LOGGER: Final = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class HttpClientConfiguration:
    """Observable production defaults used by the HTTP client factory."""

    max_connections: int
    max_keepalive_connections: int
    keepalive_expiry: float
    connect_timeout: float
    read_timeout: float
    write_timeout: float
    pool_timeout: float
    retries: int
    follow_redirects: bool
    tcp_nodelay: bool


DEFAULT_HTTP_CLIENT_CONFIGURATION: Final = HttpClientConfiguration(
    max_connections=200,
    max_keepalive_connections=40,
    keepalive_expiry=30.0,
    connect_timeout=5.0,
    read_timeout=30.0,
    write_timeout=10.0,
    pool_timeout=10.0,
    retries=3,
    follow_redirects=True,
    tcp_nodelay=True,
)


@dataclass(frozen=True, slots=True)
class HttpArtifactDownload:
    """Pinned artifact expectation and its destination cache."""

    request: ArtifactRequest
    cache: ArtifactCache


@final
class ArtifactHttpError(Exception):
    """Raised when an upstream HTTP response rejects artifact retrieval."""

    __slots__ = ("source_uri", "status_code")

    source_uri: str
    status_code: int

    def __init__(self, source_uri: str, status_code: int) -> None:
        redacted_uri = redact_url(source_uri)
        super().__init__(redacted_uri, status_code)
        self.source_uri = redacted_uri
        self.status_code = status_code

    @override
    def __str__(self) -> str:
        return f"artifact HTTP status {self.status_code} from {self.source_uri}"


@final
class ArtifactTransportError(Exception):
    """Raised when no complete HTTP response can be obtained."""

    __slots__ = ("reason", "source_uri")

    reason: str
    source_uri: str

    def __init__(self, source_uri: str, reason: str) -> None:
        redacted_uri = redact_url(source_uri)
        super().__init__(redacted_uri, reason)
        self.source_uri = redacted_uri
        self.reason = reason

    @override
    def __str__(self) -> str:
        return f"artifact transport failed for {self.source_uri}: {self.reason}"


@final
class InsecureArtifactUrlError(Exception):
    """Raised before an artifact request can use a non-HTTPS URL."""

    __slots__ = ("source_uri",)

    source_uri: str

    def __init__(self, source_uri: str) -> None:
        redacted_uri = redact_url(source_uri)
        super().__init__(redacted_uri)
        self.source_uri = redacted_uri

    @override
    def __str__(self) -> str:
        return f"artifact URL requires HTTPS: {self.source_uri}"


def create_http_client(
    transport: httpx2.BaseTransport | None = None,
) -> httpx2.Client:
    """Create a sync HTTP client with canonical production defaults."""
    configuration = DEFAULT_HTTP_CLIENT_CONFIGURATION
    selected_transport = transport
    if selected_transport is None:
        selected_transport = httpx2.HTTPTransport(
            http2=True,
            retries=configuration.retries,
            limits=httpx2.Limits(
                max_connections=configuration.max_connections,
                max_keepalive_connections=(configuration.max_keepalive_connections),
                keepalive_expiry=configuration.keepalive_expiry,
            ),
            socket_options=(
                (
                    socket.IPPROTO_TCP,
                    socket.TCP_NODELAY,
                    int(configuration.tcp_nodelay),
                ),
            ),
        )
    return httpx2.Client(
        transport=selected_transport,
        timeout=httpx2.Timeout(
            connect=configuration.connect_timeout,
            read=configuration.read_timeout,
            write=configuration.write_timeout,
            pool=configuration.pool_timeout,
        ),
        follow_redirects=configuration.follow_redirects,
        event_hooks={
            "request": [_require_https, _log_request],
            "response": [_log_response],
        },
    )


def download_artifact(
    download: HttpArtifactDownload,
    *,
    transport: httpx2.BaseTransport | None = None,
) -> ArtifactReceipt:
    """Stream one pinned HTTP response through artifact verification."""
    try:
        with (
            create_http_client(transport) as client,
            client.stream("GET", download.request.source_uri) as response,
        ):
            if response.is_error:
                raise ArtifactHttpError(
                    source_uri=download.request.source_uri,
                    status_code=response.status_code,
                ) from None
            return download.cache.store(download.request, response.iter_bytes())
    except httpx2.TransportError as error:
        redacted_uri = redact_url(download.request.source_uri)
        _LOGGER.log(
            logging.ERROR,
            "http.transport_error",
            extra={
                "http_error_type": type(error).__name__,
                "http_url": redacted_uri,
            },
        )
        transport_failure = ArtifactTransportError(
            source_uri=redacted_uri,
            reason=type(error).__name__,
        )
    raise transport_failure from None


def _require_https(request: httpx2.Request) -> None:
    if request.url.scheme != "https":
        raise InsecureArtifactUrlError(source_uri=str(request.url))


def _log_request(request: httpx2.Request) -> None:
    _LOGGER.info(
        "http.request",
        extra={
            "http_method": request.method,
            "http_url": redact_url(str(request.url)),
        },
    )


def _log_response(response: httpx2.Response) -> None:
    _LOGGER.info(
        "http.response",
        extra={
            "http_method": response.request.method,
            "http_status": response.status_code,
            "http_url": redact_url(str(response.request.url)),
            "http_version": response.http_version,
        },
    )
