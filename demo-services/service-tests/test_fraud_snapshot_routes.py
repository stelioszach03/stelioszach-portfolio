"""Actual ASGI routes with an isolated synthetic store; no model training or network."""
import asyncio
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

SERVICE = Path(__file__).resolve().parents[1] / 'fraud-graph'
sys.path.insert(0, str(SERVICE))
spec = importlib.util.spec_from_file_location('review_fraud_service', SERVICE / 'service.py')
service = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = service
spec.loader.exec_module(service)


class SnapshotRoutes(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_routes_wait_for_existing_score_slot(self):
        for route in ['/api/examples', '/api/graph']:
            with self.subTest(route=route):
                slot = asyncio.Semaphore(1)
                await slot.acquire()
                with patch.object(service, '_score_slot', slot), patch.object(service.store, 'summary', return_value={'events_total': 2}) as summary:
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app), base_url='http://test') as client:
                        request = asyncio.create_task(client.get(route))
                        try:
                            await asyncio.sleep(.04)
                            self.assertFalse(summary.called, 'snapshot raced the active scorer')
                            self.assertFalse(request.done())
                        finally:
                            slot.release()
                        response = await asyncio.wait_for(request, 2)
                        self.assertEqual(response.status_code, 200)
                        payload = response.json()
                        self.assertEqual((payload.get('graph') or payload)['events_total'], 2)
                        self.assertNotIn('held_out_accuracy', payload.get('model', {}))

    async def test_busy_snapshot_routes_return_503(self):
        for route in ['/api/examples', '/api/graph']:
            with self.subTest(route=route):
                slot = asyncio.Semaphore(1)
                await slot.acquire()
                with patch.object(service, '_score_slot', slot), patch.object(service, 'QUEUE_WAIT_S', .01), patch.object(service.store, 'summary', return_value={'events_total': 2}) as summary:
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=service.app), base_url='http://test') as client:
                        try:
                            response = await client.get(route)
                            self.assertEqual(response.status_code, 503)
                            self.assertEqual(response.json()['detail'], 'scorer busy, retry shortly')
                            self.assertFalse(summary.called)
                        finally:
                            slot.release()


if __name__ == '__main__':
    unittest.main()
