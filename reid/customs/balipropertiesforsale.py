from datetime import datetime as dt


def to_mmddyy(str):
    input_datetime = dt.strptime(str, "%Y-%m-%d %H:%M:%S")
    return input_datetime.strftime("%m/%d/%y")
