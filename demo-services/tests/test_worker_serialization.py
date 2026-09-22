import asyncio
import importlib.util
import threading
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

class SerializationTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_request_retains_slot_until_worker_finishes(self):
        for service in ('deid','fraud-graph','smt-verify'):
            with self.subTest(service=service):
                helper=BASE/service/'async_worker.py'
                spec=importlib.util.spec_from_file_location('helper_'+service.replace('-','_'),helper)
                module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                slot=asyncio.Semaphore(1);entered=threading.Event();release=threading.Event()
                def worker():
                    entered.set();release.wait(2);return 7
                request=asyncio.create_task(module.run_serialized(slot,worker))
                try:
                    for _ in range(100):
                        if entered.is_set():break
                        await asyncio.sleep(.005)
                    self.assertTrue(entered.is_set())
                    request.cancel()
                    with self.assertRaises(asyncio.CancelledError):await request
                    self.assertTrue(slot.locked(),'cancelled request released a still-running worker')
                    second=asyncio.create_task(module.run_serialized(slot,lambda:9))
                    await asyncio.sleep(.02);self.assertFalse(second.done())
                    release.set();self.assertEqual(await asyncio.wait_for(second,2),9)
                    self.assertFalse(slot.locked())
                finally:release.set()

    async def test_worker_exception_releases_slot_and_is_reported(self):
        helper=BASE/'deid'/'async_worker.py';spec=importlib.util.spec_from_file_location('failure_helper',helper);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        slot=asyncio.Semaphore(1)
        def fail():raise ValueError('synthetic failure')
        with self.assertRaisesRegex(ValueError,'synthetic failure'):
            await module.run_serialized(slot,fail)
        self.assertFalse(slot.locked())
