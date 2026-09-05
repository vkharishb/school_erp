from __future__ import annotations

from typing import Any

from sqlalchemy.engine import URL, make_url

_ASYNCPG_SSL_MODES = {"allow", "prefer", "require", "verify-ca", "verify-full"}


def prepare_asyncpg_database_url(database_url: str) -> tuple[URL, dict[str, Any]]:
    """Normalize PostgreSQL/libpq URLs for SQLAlchemy's asyncpg driver.

    ``sslmode`` and ``channel_binding`` are libpq parameters and cannot be
    passed through to ``asyncpg.connect``. Move TLS configuration into
    asyncpg's native ``ssl`` argument and remove unsupported query parameters.
    """
    url = make_url(database_url)

    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+asyncpg")

    query = dict(url.query)
    connect_args: dict[str, Any] = {}

    sslmode = query.get("sslmode")
    ssl_value = query.get("ssl")

    if sslmode:
        mode = str(sslmode).lower()
        if mode in _ASYNCPG_SSL_MODES:
            connect_args["ssl"] = mode
        elif mode in {"disable", "allow", "prefer"}:
            # ``disable`` is handled explicitly; ``allow``/``prefer`` use
            # asyncpg's documented mode values above.
            connect_args["ssl"] = mode
    elif ssl_value:
        connect_args["ssl"] = ssl_value

    url = url.difference_update_query(["sslmode", "channel_binding", "ssl"])
    return url, connect_args
