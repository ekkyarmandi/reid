def fa_remover(fa_class: str) -> str:
    if not fa_class:
        return
    return fa_class.split(" ")[-1].lstrip("fa-")
