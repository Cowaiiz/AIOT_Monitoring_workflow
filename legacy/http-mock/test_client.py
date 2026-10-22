import unittest
from unittest.mock import patch
import client

class ClientTests(unittest.TestCase):
    def test_reproducible(self):
        a=client.generate();self.assertEqual(len(a),10000)
        self.assertEqual(len({r['source_id'] for r in a}),10)
        self.assertEqual(a,client.generate());self.assertNotEqual(a[:5],client.generate(seed=43)[:5])
    def test_fresh_time_and_new_run(self):
        rows=client.generate(2)
        with patch('client.time.time',return_value=1000): a=client.materialize(rows,'runA')
        with patch('client.time.time',return_value=2000): b=client.materialize(rows,'runB')
        self.assertNotEqual(a[0]['timestamp'],b[0]['timestamp']);self.assertNotEqual(a[0]['record_id'],b[0]['record_id'])
    def test_timeout_classification(self):
        with patch('client.request.urlopen',side_effect=TimeoutError('simulated timeout')):
            r=client.send('records',{})
        self.assertIsNone(r['http']);self.assertIn('TimeoutError',r['transport_error'])
    def test_metrics_include_transport_failure(self):
        rs=[{'latency_ms':10,'http':200,'transport_error':None,'body':{'results':[{'status':'normal'}]}}, {'latency_ms':30,'http':None,'transport_error':'timeout','body':None}]
        m=client.summarize(rs,2,2);self.assertEqual(m['latency_median_ms'],20);self.assertEqual(m['latency_p95_ms'],30);self.assertEqual(m['unexpected_request_error_rate'],.5)

if __name__=='__main__':unittest.main(verbosity=2)
