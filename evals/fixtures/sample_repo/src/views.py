from .models import Account, Order, account_is_solvent, order_summary


def render_account(account: Account) -> dict:
    return {
        "id": account.id,
        "email": account.email,
        "balance": account.balance,
        "solvent": account_is_solvent(account),
    }


def render_order(order: Order) -> dict:
    return {
        "id": order.id,
        "account": order.account_id,
        "total": order.total,
        "status": order.status,
        "summary": order_summary(order),
    }


def render_dashboard(accounts: list[Account], orders: list[Order]) -> dict:
    return {
        "accounts": [render_account(a) for a in accounts],
        "orders": [render_order(o) for o in orders],
        "count": len(accounts) + len(orders),
    }


def paginate(rows: list, page: int, size: int) -> list:
    start = page * size
    return rows[start : start + size]


def sort_orders(orders: list[Order]) -> list[Order]:
    return sorted(orders, key=lambda order: order.total, reverse=True)
