import datetime as dt

from utils.data_provider import data_provider


def default_date_range(days: int = 7):
    latest_date = data_provider.get_latest_event_date()
    if latest_date is None:
        latest_date = dt.date.today()
    start_date = latest_date - dt.timedelta(days=days - 1)
    return start_date, latest_date
