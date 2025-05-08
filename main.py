#!/usr/bin/env -S uv run --script
from datetime import datetime, timedelta
import random
import httpx
import logging
import uvicorn
from fastapi import FastAPI
import fastapi
import yaml
import tortoise
from tortoise.contrib.fastapi import register_tortoise

import migrations
import models
import settings


async def app_lifespan(app: FastAPI):
    """
    Initialize the database connection.
    """
    await tortoise.Tortoise.init(
        config=settings.TORTOISE_CONFIG,
    )
    yield
    await tortoise.Tortoise.close_connections()
    logger.info("Database connection closed.")


rules = yaml.safe_load(open("rules.yaml", "r"))
logger = logging.getLogger("uvicorn")
app = FastAPI(lifespan=app_lifespan)


@app.post("/")
async def push_queue(
    request: fastapi.Request, background_tasks: fastapi.BackgroundTasks
):
    """
    Push a message to the queue.
    """
    message = await request.json()
    logger.info(f"Received message: {message}")

    event = await models.Event.create(
        event=message.get("event"),
        source_ip=request.client.host,
        payload=message.get("payload"),
        status_id=models.EventStatus.PENDING_ID,
    )
    logger.info(f"Message saved to database.")

    background_tasks.add_task(process_event,event.id, background_tasks=background_tasks)

    return {"status": "queued"}


async def process_event(event_id: int, *, background_tasks: fastapi.BackgroundTasks):
    """
    Process the event and send it to the subscriptors.

    For each subscriptor of this event, create a PendingDelivery object.
    """
    event = await models.Event.get_or_none(id=event_id)
    if not event:
        logger.warning(f"process_event: Event with id {event_id} not found.")
        return

    rule = rules.get(event.event)
    for consumer in rule.get("consumers", []):
        consumer_id = consumer.get("id")

        pendingdelivery = await models.PendingDelivery.create(
            event=event,
            consumer=consumer_id,
            last_attempt=None,
            retry_timeout=None,
            retry_count=0,
        )
        background_tasks.add_task(delivery, pendingdelivery.id, background_tasks=background_tasks)


async def delivery(pendingdelivery_id: int, *, background_tasks: fastapi.BackgroundTasks):
    """
    Process the delivery of the event to the subscriptor.

    If failed, add to the counter and retry later
    """
    pendingdelivery = await models.PendingDelivery.get_or_none(id=pendingdelivery_id)
    if not pendingdelivery:
        logger.warning(
            f"delivery: PendingDelivery with id {pendingdelivery_id} not found."
        )
        return

    event = await models.Event.get_or_none(id=pendingdelivery.event_id)
    if not event:
        logger.warning(f"delivery: Event with id {event.id} not found.")
        return

    rule = rules.get(event.event)
    if not rule:
        logger.warning(f"delivery: No rule for event {event.event}.")
        return
    consumers = rule.get("consumers", [])
    for consumer in consumers:
        if consumer.get("id") == pendingdelivery.consumer:
            break
    else:
        logger.warning(
            f"delivery: No consumer {pendingdelivery.consumer} for event {event.event}."
        )
        return

    urls = consumer.get("url")
    if isinstance(urls, str):
        urls = [urls]

    url = random.choice(urls)
    if not url:
        logger.warning(f"delivery: No URL for consumer {pendingdelivery.consumer}.")
        return

    ok = await send_message(url, event.payload)
    if ok:
        logger.info(f"delivery: Message sent to {url}.")
        pendingdelivery.last_attempt = datetime.now()
        pendingdelivery.retry_timeout = None
        await pendingdelivery.save()
        return

    logger.warning(f"delivery: Message failed to send to {url}.")
    pendingdelivery.retry_count += 1
    pendingdelivery.last_attempt = datetime.now()
    pendingdelivery.retry_timeout = datetime.now() + timedelta(
        seconds=2**pendingdelivery.retry_count
    )
    await pendingdelivery.save()
    logger.info(
        f"delivery: Message failed to send to {url}. Retry in {pendingdelivery.retry_timeout}."
    )


async def send_message(subscriptor_url, payload):
    logger.info(f"Sending message to {subscriptor_url}")
    # async send message
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(subscriptor_url, json=payload)
            logger.info(f"Response from {subscriptor_url}: {response.status_code}")
            return True
        except httpx.RequestError as exc:
            logger.error(f"Request to {subscriptor_url} failed: {exc}")
            logger.warning("TODO handle retry logic")
            return False


@app.post("/logger")
async def logger_endpoint(request: fastapi.Request):
    """
    Log a message.
    """
    message = await request.json()
    logger.info(f"Received log message: {message}")
    return {"status": "ok"}


def main():
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info", reload=True)


if __name__ == "__main__":
    main()
