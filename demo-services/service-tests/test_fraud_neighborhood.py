"""Bounded graph snapshots from actual synthetic graph state; no model training."""
import unittest
from unittest.mock import patch
from test_fraud_snapshot_routes import service


class NeighborhoodTests(unittest.TestCase):
    def setUp(self):
        self.store = service.GraphStore()
        self.store.graph.add_edge('SENDER', 'RECEIVER', count=3)
        for i in range(40):
            self.store.graph.add_edge('SENDER', f'N{i:02}', count=i+1)
            self.store.graph.add_edge(f'N{i:02}', 'RECEIVER', count=2)
        self.patch = patch.object(service, 'store', self.store)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_bounded_actual_nodes_and_edges_keep_the_scored_pair(self):
        result = service._neighborhood_snapshot('SENDER', 'RECEIVER')
        ids = {n['id'] for n in result['nodes']}
        self.assertLessEqual(len(ids), 18)
        self.assertLessEqual(len(result['edges']), 36)
        self.assertTrue({'SENDER', 'RECEIVER'} <= ids)
        self.assertTrue(result['truncated'])
        self.assertTrue(any(e['source']=='SENDER' and e['target']=='RECEIVER' for e in result['edges']))
        for edge in result['edges']:
            self.assertTrue(self.store.graph.has_edge(edge['source'], edge['target']))
            self.assertEqual(edge['count'], self.store.graph[edge['source']][edge['target']]['count'])
        self.assertEqual(result, service._neighborhood_snapshot('SENDER', 'RECEIVER'))

    def test_self_transfer_is_one_focus_and_no_fabricated_edge(self):
        self.store.graph.clear()
        self.store.graph.add_edge('SAME', 'SAME', count=2)
        result = service._neighborhood_snapshot('SAME', 'SAME')
        self.assertEqual(result['nodes'][0]['role'], 'both')
        self.assertEqual(len(result['nodes']), 1)
        self.assertEqual(result['edges'], [{'source':'SAME','target':'SAME','count':2,'submitted_pair':True}])

    def test_score_captures_graph_before_a_reseed(self):
        req=service.ScoreRequest(sender_id='SENDER',receiver_id='RECEIVER',amount=10)
        with patch.object(service.scorer,'score',return_value={'risk_score':.5}), patch.object(service,'RESEED_AFTER',1), patch.object(service,'_visitor_events',0), patch.object(service,'_rebuilds',0), patch.object(service,'_seed_graph',side_effect=self.store.graph.clear):
            response=service._score(req)
        self.assertTrue(response['graph_reset_after_snapshot'])
        self.assertIn('SENDER',{n['id'] for n in response['neighborhood']['nodes']})
        self.assertEqual(response['graph']['nodes_total'],0)
        self.assertEqual(response['neighborhood']['snapshot'],'after_transaction_before_reseed')
