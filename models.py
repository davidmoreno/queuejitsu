from datetime import datetime

class PendingEvent:
    event: str
    url: str
    payload: dict
    last_attempt: datetime
    retry_timeout: datetime
    retry_count: int

