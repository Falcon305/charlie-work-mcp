def charge(account):
    if is_enabled("legacy_billing_mode"):
        return legacy_charge(account)
    return charge_v2(account)
