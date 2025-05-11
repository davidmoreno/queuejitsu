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
from tortoise.expressions import Q

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

def serve(host="0.0.0.0", port=8000, log_level="info", reload=True):
    """
    Run the server.
    """
    # Set up logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run the server
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_level=log_level,
        reload=reload
    )


async def dispatch():
    """
    Dispatch pending events by sending them to their respective consumers.
    """
    logger.info("Dispatching pending events")

    await tortoise.Tortoise.init(config=settings.TORTOISE_CONFIG)

    # Get all pending deliveries that are ready to be sent (retry_timeout is None or in the past)
    pending_deliveries = await models.PendingDelivery.filter(
        Q(retry_timeout=None) |
        Q(retry_timeout__lte=datetime.now())
    )

    logger.info(f"Found {len(pending_deliveries)} deliveries to dispatch")

    for pending_delivery in pending_deliveries:
        await delivery(pending_delivery.id, background_tasks=None)

    await tortoise.Tortoise.close_connections()
    logger.info("Database connection closed")


async def list_events(event_type=None, consumer=None, output_format='yaml'):
    """
    Show the list of events to send in YAML-like or JSON format.

    Args:
        event_type: Filter by event type
        consumer: Filter by consumer
        output_format: Output format ('yaml' or 'json')
    """
    logger.info("Listing events")

    await tortoise.Tortoise.init(config=settings.TORTOISE_CONFIG)

    # Start building the query
    query = models.PendingDelivery.all().prefetch_related('event')

    # Apply filters if provided
    if event_type:
        query = query.filter(event__event=event_type)
    if consumer:
        query = query.filter(consumer=consumer)

    # Execute the query
    pending_deliveries = await query

    if output_format == 'json':
        import json

        # Create a list to store the results
        results = []
        for pd in pending_deliveries:
            results.append({
                'id': pd.id,
                'event': {
                    'id': pd.event.id,
                    'type': pd.event.event,
                    'payload': pd.event.payload,
                },
                'consumer': pd.consumer,
                'retry_count': pd.retry_count,
                'next_attempt': str(pd.retry_timeout) if pd.retry_timeout else 'ASAP',
                'last_attempt': str(pd.last_attempt) if pd.last_attempt else 'Never',
            })
        print(json.dumps(results, indent=2))
    else:
        print(f"pending_deliveries: # total: {len(pending_deliveries)}")
        for pd in pending_deliveries:
            event = pd.event
            print(f"  - id: {pd.id}")
            print(f"    event:")
            print(f"      id: {event.id}")
            print(f"      type: {event.event}")
            # Format payload as YAML with proper indentation
            if event.payload:
                print(f"      payload:")
                for line in str(event.payload).splitlines():
                    print(f"        {line}")
            else:
                print(f"      payload: null")
            print(f"    consumer: {pd.consumer}")
            print(f"    retry_count: {pd.retry_count}")
            print(f"    next_attempt: {str(pd.retry_timeout) if pd.retry_timeout else 'ASAP'}")
            print(f"    last_attempt: {str(pd.last_attempt) if pd.last_attempt else 'Never'}")

    await tortoise.Tortoise.close_connections()
    logger.info("Database connection closed")


def parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="Push queue manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands", required=True)

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Run the server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    serve_parser.add_argument("--log-level", default="info", help="Logging level")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    # Dispatch command
    dispatch_parser = subparsers.add_parser("dispatch", help="Dispatch pending events to consumers")

    # List command
    list_parser = subparsers.add_parser("list", help="List events")
    list_parser.add_argument("--event-type", help="Filter by event type")
    list_parser.add_argument("--consumer", help="Filter by consumer")
    list_parser.add_argument("--output-format", choices=["yaml", "json"], default="yaml", help="Output format")

    return parser.parse_args()




def dispatch_command():
    """
    Run the dispatch command handler.
    """
    import asyncio
    asyncio.run(dispatch())


def list_command(args):
    """
    List events command handler.
    """
    import asyncio
    print(f"# Filtering: event_type={args.event_type or 'all'}, consumer={args.consumer or 'all'}")
    asyncio.run(list_events(event_type=args.event_type, consumer=args.consumer, output_format=args.output_format))


def main():
    args = parse_args()

    # Execute the appropriate command based on the subcommand
    if args.command == "serve":
        serve(
            host=args.host,
            port=args.port,
            log_level=args.log_level,
            reload=args.reload
        )
        return 0
    elif args.command == "dispatch":
        dispatch_command()
        return 0
    elif args.command == "list":
        list_command(args)
        return 0
    else:
        # This should never happen due to required=True in subparsers
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
