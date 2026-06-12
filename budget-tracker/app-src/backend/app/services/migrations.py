from calendar import monthrange
from datetime import date

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


def _period_date(period: str, day: int | None) -> date | None:
    if not day:
        return None
    year_text, month_text = period.split("-")
    year = int(year_text)
    month = int(month_text)
    clamped_day = min(day, monthrange(year, month)[1])
    return date(year, month, clamped_day)


def ensure_budget_line_payment_date(engine: Engine) -> None:
    with engine.begin() as connection:
        rows = connection.execute(text("PRAGMA table_info(budget_lines)")).mappings().all()
        if not rows:
            return
        columns = {row["name"] for row in rows}
        if "payment_date" in columns:
            return

        connection.execute(text("ALTER TABLE budget_lines ADD COLUMN payment_date DATE"))
        line_rows = connection.execute(
            text(
                """
                SELECT budget_lines.id, budget_lines.paid_date, budget_lines.due_day, months.period
                FROM budget_lines
                JOIN months ON months.id = budget_lines.month_id
                """
            )
        ).mappings().all()
        for row in line_rows:
            payment_date = row["paid_date"] or _period_date(row["period"], row["due_day"])
            if payment_date:
                connection.execute(
                    text("UPDATE budget_lines SET payment_date = :payment_date WHERE id = :id"),
                    {"payment_date": str(payment_date), "id": row["id"]},
                )
