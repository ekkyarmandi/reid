def get_balivillasales_price(text):
    # declare the variables
    data = {
        "idr": None,
        "usd": None,
        "lease_years": None,
        "availability": True,
    }
    # split input by "/"
    p = text.strip().lower().split("/")
    # assign the values
    if len(p) > 1:
        data["lease_years"] = p[-1]
    if "idr" in p[0]:
        data["idr"] = p[0]
    elif "usd" in p[0]:
        data["usd"] = p[0]
    if "sold" in p[0]:
        data["availability"] = False
    data["availability"] = "Available" if data["availability"] else "Sold"
    return data
