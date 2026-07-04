from .models import Account, Order, account_is_solvent
from .repository import AccountRepository, OrderRepository


class BillingService:
    def __init__(self, accounts: AccountRepository, orders: OrderRepository) -> None:
        self.accounts = accounts
        self.orders = orders

    def can_place_order(self, account_id: str, amount: int) -> bool:
        account = self.accounts.get(account_id)
        if account is None:
            return False
        return account_is_solvent(account) and account.balance >= amount

    def place_order(self, account_id: str, order: Order) -> bool:
        if not self.can_place_order(account_id, order.total):
            return False
        self.orders.add(order)
        account = self.accounts.get(account_id)
        if account is not None:
            account.balance -= order.total
        return True

    def refund(self, account_id: str, amount: int) -> None:
        account = self.accounts.get(account_id)
        if account is not None:
            account.balance += amount

    def statement(self, account_id: str) -> dict:
        account = self.accounts.get(account_id)
        if account is None:
            return {}
        return {
            "account": account.id,
            "balance": account.balance,
            "orders": len(self.orders.for_account(account_id)),
            "spent": self.orders.total_for(account_id),
        }


def summarize_accounts(accounts: list[Account]) -> dict:
    return {
        "count": len(accounts),
        "active": len([a for a in accounts if a.active]),
        "balance": sum(a.balance for a in accounts),
    }
