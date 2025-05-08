from datetime import datetime
from tortoise import fields
from tortoise.models import Model


class EventStatus(Model):
    id: int = fields.IntField(pk=True)
    name: str = fields.CharField(max_length=255)
    
    PENDING_ID = 10
    PROCESSING_ID = 20
    DELIVERING_ID = 30
    DELIVERED_ID = 40
    FAILED_ID = 50

    @classmethod
    async def create_fixture(cls):
        await cls.create(id=10, name="Pending")
        await cls.create(id=20, name="Processing")
        await cls.create(id=30, name="Delivering")
        await cls.create(id=40, name="Delivered")
        await cls.create(id=50, name="Failed")

class Event(Model):
    id: int = fields.IntField(pk=True)
    event: str = fields.CharField(max_length=255)
    source_ip: str = fields.CharField(max_length=255)
    payload: dict = fields.JSONField()
    timestamp: datetime = fields.DatetimeField(auto_now_add=True)
    status: EventStatus = fields.ForeignKeyField("models.EventStatus", related_name="events")

class PendingDelivery(Model):
    id: int = fields.IntField(pk=True)
    event: Event = fields.ForeignKeyField("models.Event", related_name="pending_deliveries")
    consumer: str = fields.CharField(max_length=255)
    last_attempt: datetime = fields.DatetimeField(null=True)
    retry_timeout: datetime = fields.DatetimeField(null=True)
    retry_count: int = fields.IntField(default=0)

    