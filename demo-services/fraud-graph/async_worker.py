"""Keep non-thread-safe CPU workers serialized even when an HTTP request is cancelled."""
import asyncio

async def run_serialized(slot, function, *args, queue_timeout=None, **kwargs):
    await asyncio.wait_for(slot.acquire(), timeout=queue_timeout)
    try:
        worker = asyncio.create_task(asyncio.to_thread(function, *args, **kwargs))
    except BaseException:
        slot.release()
        raise
    def finished(task):
        slot.release()
        if not task.cancelled():
            task.exception()  # Retrieve failures if the HTTP waiter was cancelled.
    worker.add_done_callback(finished)
    return await asyncio.shield(worker)
