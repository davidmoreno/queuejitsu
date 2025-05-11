# QueueJitsu

A robust event bus based on REST API and YAML configuration for reliable message routing.

## Overview

QueueJitsu is a lightweight yet powerful event bus system that:

- Receives events via REST API
- Stores events persistently for reliability
- Routes messages to consumers based on YAML configuration
- Handles retries with exponential backoff when deliveries fail
- Supports different delivery guarantees (any, fifo, fifo with groups)

## Features

- **REST-based**: Simple HTTP endpoints for sending and receiving events
- **YAML configuration**: Easy to define routing rules without code changes
- **Persistent storage**: Events are stored until successfully delivered
- **Flexible routing**: Configure multiple consumers for each event type
- **Advanced retry logic**: Exponential backoff for failed deliveries
- **Multiple delivery guarantees**: Choose between best-effort or ordered delivery
- **Command-line tools**: Simple commands for operating the system

## Usage

### Running the server

```bash
./main.py serve --host 0.0.0.0 --port 8000 --log-level info
```

### Dispatching pending events

```bash
./main.py dispatch
```

### Listing events

```bash
./main.py list [--event-type TYPE] [--consumer CONSUMER] [--output-format yaml|json]
```

## Configuration

Define your event routing in `rules.yaml`:

```yaml
my.event.type:
  consumers:
    - id: consumer1
      url: "http://consumer1.example.com/endpoint"
      delivery_order: any

    - id: consumer2
      url: "http://consumer2.example.com/endpoint"
      delivery_order: fifo
      add_to_payload:
        extra_field: true
```

## License

AGPL v3
