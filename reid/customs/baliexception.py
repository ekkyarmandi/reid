def try_pass(func):
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
        except:
            result = None
        return result

    return wrapper
