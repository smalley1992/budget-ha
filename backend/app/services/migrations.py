from sqlalchemy import text
from sqlalchemy.engine import Engine


def ensure_user_profile_columns(engine: Engine) -> None:
    with engine.begin() as connection:
        rows = connection.execute(text("PRAGMA table_info(users)")).mappings().all()
        columns = {row["name"] for row in rows}
        if rows and "icon" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN icon VARCHAR(8) DEFAULT ''"))
        if rows and "salary_cents" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN salary_cents INTEGER DEFAULT 0"))
