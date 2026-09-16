import asyncio

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine


async def main() -> None:
    settings = get_settings()

    database_name = (
        settings.database_url
        .rsplit("/", 1)[-1]
        .split("?", 1)[0]
        .lower()
    )

    if database_name != "schoolerp_test":
        raise RuntimeError(
            f"Refusing destructive CT reset on database: {database_name!r}. "
            "Expected exactly 'schoolerp_test'."
        )

    async with engine.begin() as connection:
        await connection.execute(
            text("DROP SCHEMA IF EXISTS public CASCADE")
        )
        await connection.execute(
            text("CREATE SCHEMA public")
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())