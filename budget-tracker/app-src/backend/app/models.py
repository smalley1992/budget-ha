from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    icon: Mapped[str | None] = mapped_column(String(8), nullable=True, default="")
    salary_cents: Mapped[int] = mapped_column(Integer, default=0)


class Month(Base):
    __tablename__ = "months"

    id: Mapped[int] = mapped_column(primary_key=True)
    period: Mapped[str] = mapped_column(String(7), unique=True, index=True)


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("kind", "name", name="uq_category_kind_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(120))


class IncomeLine(Base):
    __tablename__ = "income_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    month_id: Mapped[int] = mapped_column(ForeignKey("months.id"))
    name: Mapped[str] = mapped_column(String(160))
    amount_cents: Mapped[int] = mapped_column(Integer)
    is_static: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user: Mapped[User] = relationship()
    month: Mapped[Month] = relationship()


class BudgetLine(Base):
    __tablename__ = "budget_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    month_id: Mapped[int] = mapped_column(ForeignKey("months.id"))
    type: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(160))
    amount_cents: Mapped[int] = mapped_column(Integer)
    due_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="planned", index=True)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_static: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    linked_debt_id: Mapped[int | None] = mapped_column(ForeignKey("debts.id"), nullable=True)
    linked_savings_pot_id: Mapped[int | None] = mapped_column(ForeignKey("savings_pots.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user: Mapped[User] = relationship()
    month: Mapped[Month] = relationship()
    linked_debt: Mapped["Debt | None"] = relationship()
    linked_savings_pot: Mapped["SavingsPot | None"] = relationship()
    attachments: Mapped[list["Attachment"]] = relationship(cascade="all, delete-orphan")


class Debt(Base):
    __tablename__ = "debts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(160))
    starting_balance_cents: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user: Mapped[User] = relationship()
    transactions: Mapped[list["DebtTransaction"]] = relationship(cascade="all, delete-orphan")


class DebtTransaction(Base):
    __tablename__ = "debt_transactions"
    __table_args__ = (UniqueConstraint("budget_line_id", name="uq_debt_transaction_budget_line"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    debt_id: Mapped[int] = mapped_column(ForeignKey("debts.id"))
    budget_line_id: Mapped[int] = mapped_column(ForeignKey("budget_lines.id"))
    amount_cents: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SavingsPot(Base):
    __tablename__ = "savings_pots"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(160))
    starting_balance_cents: Mapped[int] = mapped_column(Integer)
    target_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    user: Mapped[User] = relationship()
    transactions: Mapped[list["SavingsTransaction"]] = relationship(cascade="all, delete-orphan")


class SavingsTransaction(Base):
    __tablename__ = "savings_transactions"
    __table_args__ = (UniqueConstraint("budget_line_id", name="uq_savings_transaction_budget_line"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    savings_pot_id: Mapped[int] = mapped_column(ForeignKey("savings_pots.id"))
    budget_line_id: Mapped[int] = mapped_column(ForeignKey("budget_lines.id"))
    amount_cents: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    budget_line_id: Mapped[int] = mapped_column(ForeignKey("budget_lines.id"))
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
