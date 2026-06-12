from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


BudgetLineType = Literal["bill", "expense", "savings_contribution", "debt_payment"]
BudgetLineStatus = Literal["planned", "paid"]
ViewSlug = str
UserSlug = str


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    icon: str | None = Field(default=None, max_length=8)
    salary: float = 0


class UserOut(BaseModel):
    id: str
    name: str
    icon: str | None = None
    salary: float = 0


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    icon: str | None = Field(default=None, max_length=8)
    salary: float | None = None


class MonthCreate(BaseModel):
    period: str = Field(pattern=r"^\d{4}-\d{2}$")


class MonthOut(BaseModel):
    id: int
    period: str


class CategoryOut(BaseModel):
    id: int
    kind: str
    name: str


class RolloverRequest(BaseModel):
    source_period: str = Field(pattern=r"^\d{4}-\d{2}$")
    target_period: str = Field(pattern=r"^\d{4}-\d{2}$")


class IncomeLineCreate(BaseModel):
    user_id: UserSlug
    period: str = Field(pattern=r"^\d{4}-\d{2}$")
    name: str
    amount: float
    is_static: bool = False
    notes: str | None = None


class IncomeLineUpdate(BaseModel):
    name: str | None = None
    amount: float | None = None
    is_static: bool | None = None
    notes: str | None = None


class IncomeLineOut(BaseModel):
    id: int
    user_id: str
    period: str
    name: str
    amount: float
    is_static: bool
    notes: str | None


class BudgetLineCreate(BaseModel):
    user_id: UserSlug
    period: str = Field(pattern=r"^\d{4}-\d{2}$")
    type: BudgetLineType
    name: str
    amount: float
    due_day: int | None = Field(default=None, ge=1, le=31)
    payment_date: date | None = None
    status: BudgetLineStatus = "planned"
    paid_date: date | None = None
    is_static: bool = False
    notes: str | None = None
    linked_debt_id: int | None = None
    linked_savings_pot_id: int | None = None


class BudgetLineUpdate(BaseModel):
    type: BudgetLineType | None = None
    name: str | None = None
    amount: float | None = None
    due_day: int | None = Field(default=None, ge=1, le=31)
    payment_date: date | None = None
    status: BudgetLineStatus | None = None
    paid_date: date | None = None
    is_static: bool | None = None
    notes: str | None = None
    linked_debt_id: int | None = None
    linked_savings_pot_id: int | None = None


class BudgetLineOut(BaseModel):
    id: int
    user_id: str
    period: str
    type: str
    name: str
    amount: float
    due_day: int | None
    payment_date: date | None
    status: str
    paid_date: date | None
    is_static: bool
    notes: str | None
    linked_debt_id: int | None
    linked_savings_pot_id: int | None
    attachment_count: int


class DebtCreate(BaseModel):
    user_id: UserSlug
    name: str
    starting_balance: float
    notes: str | None = None


class DebtUpdate(BaseModel):
    name: str | None = None
    starting_balance: float | None = None
    notes: str | None = None


class DebtOut(BaseModel):
    id: int
    user_id: str
    name: str
    starting_balance: float
    paid_amount: float
    current_balance: float
    notes: str | None


class SavingsPotCreate(BaseModel):
    user_id: UserSlug
    name: str
    starting_balance: float = 0
    target_amount: float | None = None
    notes: str | None = None


class SavingsPotUpdate(BaseModel):
    name: str | None = None
    starting_balance: float | None = None
    target_amount: float | None = None
    notes: str | None = None


class SavingsPotOut(BaseModel):
    id: int
    user_id: str
    name: str
    starting_balance: float
    contributed_amount: float
    current_balance: float
    target_amount: float | None
    notes: str | None


class AttachmentOut(BaseModel):
    id: int
    budget_line_id: int
    original_filename: str
    content_type: str
    size_bytes: int
    created_at: datetime


class SummaryTotals(BaseModel):
    income: float
    bills: float
    expenses: float
    savings_contributions: float
    debt_payments: float
    outgoings: float
    leftover: float


class SummaryOut(BaseModel):
    period: str
    view: str
    totals: SummaryTotals
    by_user: dict[str, SummaryTotals] | None = None
