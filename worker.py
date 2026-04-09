import asyncio
import json
import logging
import os
import signal
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("managed-agent-worker")


class RetryableMessageError(Exception):
    """Raised when a message should be retried."""


@dataclass(slots=True)
class QueueMessage:
    message_id: str
    payload: dict[str, Any]
    attempts: int = 0


class QueueConsumer(ABC):
    @abstractmethod
    async def poll_message(self) -> QueueMessage | None:
        """Return the next message from queue, or None when queue is empty."""

    @abstractmethod
    async def ack_message(self, message: QueueMessage) -> None:
        """Acknowledge successful message processing."""

    @abstractmethod
    async def nack_message(
        self,
        message: QueueMessage,
        *,
        requeue: bool,
        reason: str,
        delay_seconds: float = 0.0,
    ) -> None:
        """Reject a message, optionally requeueing it."""

    @abstractmethod
    async def close(self) -> None:
        """Free resources held by consumer."""


class InMemoryQueueConsumer(QueueConsumer):
    """Concrete queue adapter used as an integration placeholder in V1."""

    def __init__(self, seed_messages: list[dict[str, Any]] | None = None) -> None:
        self._queue: asyncio.Queue[QueueMessage] = asyncio.Queue()
        self._closed = False

        for idx, payload in enumerate(seed_messages or []):
            self._queue.put_nowait(
                QueueMessage(message_id=f"seed-{idx}", payload=payload, attempts=0)
            )

    async def poll_message(self) -> QueueMessage | None:
        if self._closed:
            return None
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def ack_message(self, message: QueueMessage) -> None:
        logger.info(
            json.dumps(
                {
                    "event": "message_acked",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "message_id": message.message_id,
                }
            )
        )

    async def nack_message(
        self,
        message: QueueMessage,
        *,
        requeue: bool,
        reason: str,
        delay_seconds: float = 0.0,
    ) -> None:
        message.attempts += 1
        logger.info(
            json.dumps(
                {
                    "event": "message_nacked",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "message_id": message.message_id,
                    "reason": reason,
                    "requeue": requeue,
                    "attempts": message.attempts,
                    "delay_seconds": delay_seconds,
                }
            )
        )

        if not requeue or self._closed:
            return

        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

        await self._queue.put(message)

    async def close(self) -> None:
        self._closed = True


def _build_consumer_from_env() -> QueueConsumer:
    seed_payloads = os.getenv("WORKER_BOOTSTRAP_MESSAGES", "[]")
    try:
        parsed_payloads = json.loads(seed_payloads)
        if not isinstance(parsed_payloads, list):
            raise ValueError("WORKER_BOOTSTRAP_MESSAGES must be a JSON list")
    except (json.JSONDecodeError, ValueError):
        logger.warning(
            json.dumps(
                {
                    "event": "bootstrap_messages_invalid",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "value": seed_payloads,
                    "fallback": "empty_queue",
                }
            )
        )
        parsed_payloads = []

    return InMemoryQueueConsumer(seed_messages=parsed_payloads)


def _is_valid_payload(payload: dict[str, Any]) -> bool:
    return isinstance(payload.get("task_id"), str) and bool(payload.get("goal"))


async def _process_message(message: QueueMessage) -> None:
    if message.payload.get("simulate_retry"):
        raise RetryableMessageError("transient_runtime_error")

    logger.info(
        json.dumps(
            {
                "event": "message_processed",
                "timestamp": datetime.now(UTC).isoformat(),
                "message_id": message.message_id,
                "task_id": message.payload.get("task_id"),
            }
        )
    )


async def consume_queue_forever(
    consumer: QueueConsumer,
    poll_interval_seconds: float = 1.0,
    max_retries: int = 3,
    max_retry_backoff_seconds: float = 30.0,
) -> None:
    """Worker loop with ack/nack, bounded retry, backoff and graceful shutdown."""
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Fallback for platforms where signal handlers are unsupported.
            pass

    logger.info(
        json.dumps(
            {
                "event": "worker_started",
                "timestamp": datetime.now(UTC).isoformat(),
                "poll_interval_seconds": poll_interval_seconds,
                "max_retries": max_retries,
            }
        )
    )

    try:
        while not stop_event.is_set():
            message = await consumer.poll_message()

            if message is None:
                logger.info(
                    json.dumps(
                        {
                            "event": "queue_poll_empty",
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    )
                )
                await asyncio.sleep(poll_interval_seconds)
                continue

            logger.info(
                json.dumps(
                    {
                        "event": "message_received",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "message_id": message.message_id,
                    }
                )
            )

            if not _is_valid_payload(message.payload):
                await consumer.nack_message(
                    message,
                    requeue=False,
                    reason="invalid_payload",
                )
                continue

            try:
                await _process_message(message)
                await consumer.ack_message(message)
            except RetryableMessageError as exc:
                next_attempt = message.attempts + 1
                should_requeue = next_attempt <= max_retries
                backoff_seconds = min(2 ** max(message.attempts, 0), max_retry_backoff_seconds)
                await consumer.nack_message(
                    message,
                    requeue=should_requeue,
                    reason=str(exc),
                    delay_seconds=backoff_seconds if should_requeue else 0.0,
                )

    finally:
        await consumer.close()
        logger.info(
            json.dumps(
                {
                    "event": "worker_stopped",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "reason": "graceful_shutdown",
                }
            )
        )


if __name__ == "__main__":
    queue_consumer = _build_consumer_from_env()
    asyncio.run(consume_queue_forever(queue_consumer))
