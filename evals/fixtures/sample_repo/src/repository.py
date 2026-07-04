from .models import Account, Order


class AccountRepository:
    def __init__(self) -> None:
        self._rows: dict[str, Account] = {}

    def add(self, account: Account) -> None:
        self._rows[account.id] = account

    def get(self, account_id: str) -> Account | None:
        return self._rows.get(account_id)

    def remove(self, account_id: str) -> None:
        self._rows.pop(account_id, None)

    def all(self) -> list[Account]:
        return list(self._rows.values())

    def where_active(self) -> list[Account]:
        return [row for row in self._rows.values() if row.active]


class OrderRepository:
    def __init__(self) -> None:
        self._rows: dict[str, Order] = {}

    def add(self, order: Order) -> None:
        self._rows[order.id] = order

    def get(self, order_id: str) -> Order | None:
        return self._rows.get(order_id)

    def for_account(self, account_id: str) -> list[Order]:
        return [row for row in self._rows.values() if row.account_id == account_id]

    def total_for(self, account_id: str) -> int:
        return sum(row.total for row in self.for_account(account_id))
