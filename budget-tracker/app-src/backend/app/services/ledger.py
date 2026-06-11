from sqlalchemy.orm import Session

from .. import models


def sync_budget_line_ledger(db: Session, line: models.BudgetLine) -> None:
    debt_tx = (
        db.query(models.DebtTransaction)
        .filter(models.DebtTransaction.budget_line_id == line.id)
        .one_or_none()
    )
    savings_tx = (
        db.query(models.SavingsTransaction)
        .filter(models.SavingsTransaction.budget_line_id == line.id)
        .one_or_none()
    )

    should_debt = line.status == "paid" and line.type == "debt_payment" and line.linked_debt_id is not None
    if should_debt:
        if debt_tx is None:
            db.add(
                models.DebtTransaction(
                    debt_id=line.linked_debt_id,
                    budget_line_id=line.id,
                    amount_cents=line.amount_cents,
                )
            )
        else:
            debt_tx.debt_id = line.linked_debt_id
            debt_tx.amount_cents = line.amount_cents
    elif debt_tx is not None:
        db.delete(debt_tx)

    should_savings = (
        line.status == "paid"
        and line.type == "savings_contribution"
        and line.linked_savings_pot_id is not None
    )
    if should_savings:
        if savings_tx is None:
            db.add(
                models.SavingsTransaction(
                    savings_pot_id=line.linked_savings_pot_id,
                    budget_line_id=line.id,
                    amount_cents=line.amount_cents,
                )
            )
        else:
            savings_tx.savings_pot_id = line.linked_savings_pot_id
            savings_tx.amount_cents = line.amount_cents
    elif savings_tx is not None:
        db.delete(savings_tx)


def remove_budget_line_ledger(db: Session, budget_line_id: int) -> None:
    for model in (models.DebtTransaction, models.SavingsTransaction):
        tx = db.query(model).filter(model.budget_line_id == budget_line_id).one_or_none()
        if tx is not None:
            db.delete(tx)
