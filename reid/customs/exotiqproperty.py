def lease_or_free_hold(value: str) -> str:
    if value == "For lease":
        return "Leasehold"
    elif value == "For sale":
        return "Freehold"
    return value
