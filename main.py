#!/usr/bin/env -S uv run --script
import httpx
import logging
import uvicorn
from fastapi import FastAPI
import fastapi
import yaml

rules = yaml.safe_load(open("rules.yaml", "r"))
logger = logging.getLogger("uvicorn")
app = FastAPI()


@app.post("/")
async def push_queue(request: fastapi.Request, background_tasks: fastapi.BackgroundTasks):
    """
    Push a message to the queue.
    """
    message = await request.json()
    logger.info(f"Received message: {message}")

    event = message.get("event")
    payload = message.get("payload")
    subscriptors = rules.get(event, [])
    if not subscriptors:
        logger.warning(f"No subscriptors for event: {event}")
        return {"status": "no_subscriptors"}

    for subscriptor in subscriptors:
        subscriptor_url = subscriptor.get("url")
        if not subscriptor_url:
            logger.warning(f"No URL for subscriptor: {subscriptor}")
            continue

        # Here you would send the message to the subscriptor
        # For example, using httpx or requests library

        background_tasks.add_task(send_message,subscriptor_url, payload)

    logger.info(f"Subscriptors for event {event}: {len(subscriptors)}")
    return {"status": "ok"}


async def send_message(subscriptor_url, payload):
    logger.info(f"Sending message to {subscriptor_url}")
    # async send message
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(subscriptor_url, json=payload)
            logger.info(f"Response from {subscriptor_url}: {response.status_code}")
        except httpx.RequestError as exc:
            logger.error(f"Request to {subscriptor_url} failed: {exc}")
            logger.warning("TODO handle retry logic")


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
