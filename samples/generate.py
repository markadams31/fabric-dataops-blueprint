"""Deterministic synthetic retail data (the jaffle-shop shape).

Regenerate with:  uv run python samples/generate.py
Committed output in samples/data/ so a fork needs no generation step.
"""

import csv
import pathlib
import random

OUT = pathlib.Path(__file__).parent / "data"
FIRST = ["ava", "liam", "mia", "noah", "zoe", "eli", "ivy", "max", "ada", "leo"]
LAST = ["smith", "jones", "taylor", "brown", "wilson", "chen", "singh", "nguyen"]
STATUS = ["completed", "completed", "completed", "shipped", "returned", "placed"]
METHOD = ["credit_card", "bank_transfer", "coupon", "gift_card"]


def main() -> None:
    rng = random.Random(42)
    OUT.mkdir(exist_ok=True)

    with open(OUT / "customers.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "first_name", "last_name"])
        for i in range(1, 101):
            w.writerow([i, rng.choice(FIRST), rng.choice(LAST)])

    orders = []
    with open(OUT / "orders.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "user_id", "order_date", "status"])
        for i in range(1, 301):
            day = rng.randint(0, 364)
            date = f"2025-{day // 31 + 1:02d}-{day % 28 + 1:02d}"
            orders.append(i)
            w.writerow([i, rng.randint(1, 100), date, rng.choice(STATUS)])

    with open(OUT / "payments.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "order_id", "payment_method", "amount"])
        pid = 0
        for oid in orders:
            for _ in range(rng.choice([1, 1, 1, 2])):
                pid += 1
                w.writerow([pid, oid, rng.choice(METHOD), round(rng.uniform(5, 300), 2)])

    print(f"wrote {len(list(OUT.glob('*.csv')))} files to {OUT}")


if __name__ == "__main__":
    main()
