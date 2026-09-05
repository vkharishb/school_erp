from app.db.url import prepare_asyncpg_database_url


def test_postgresql_url_is_converted_to_asyncpg_without_libpq_ssl_parameters():
    url, connect_args = prepare_asyncpg_database_url(
        "postgresql://user:pass@example.test/db?sslmode=require&channel_binding=require"
    )

    assert url.drivername == "postgresql+asyncpg"
    assert "sslmode" not in url.query
    assert "channel_binding" not in url.query
    assert connect_args == {"ssl": "require"}


def test_asyncpg_ssl_query_parameter_is_moved_to_connect_args():
    url, connect_args = prepare_asyncpg_database_url(
        "postgresql+asyncpg://user:pass@example.test/db?ssl=require"
    )

    assert "ssl" not in url.query
    assert connect_args == {"ssl": "require"}


def test_local_postgresql_url_needs_no_ssl_configuration():
    url, connect_args = prepare_asyncpg_database_url(
        "postgresql+asyncpg://user:pass@localhost:5432/schoolerp_test"
    )

    assert url.drivername == "postgresql+asyncpg"
    assert connect_args == {}
