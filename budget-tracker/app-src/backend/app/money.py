from decimal import Decimal, ROUND_HALF_UP


def to_cents(value: int | float | str | Decimal | None) -> int:
    if value is None:
        return 0
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(amount * 100)


def from_cents(value: int | None) -> float:
    return float(Decimal(value or 0) / Decimal(100))
