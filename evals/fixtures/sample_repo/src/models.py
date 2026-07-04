from dataclasses import dataclass


@dataclass
class Account:
    id: str
    email: str
    balance: int
    active: bool


@dataclass
class Order:
    id: str
    account_id: str
    total: int
    status: str


def account_is_solvent(account: Account) -> bool:
    return account.active and account.balance >= 0


def order_summary(order: Order) -> str:
    return f"order {order.id} for account {order.account_id} totalling {order.total}"


def apply_discount(order: Order, percent: int) -> Order:
    reduced = int(order.total * (100 - percent) / 100)
    return Order(id=order.id, account_id=order.account_id, total=reduced, status=order.status)


def merge_orders(orders: list[Order]) -> int:
    return sum(order.total for order in orders)


def active_accounts(accounts: list[Account]) -> list[Account]:
    return [account for account in accounts if account.active]


def total_balance(accounts: list[Account]) -> int:
    return sum(account.balance for account in accounts)
