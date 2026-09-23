"""CPU-only review-contract tests. No external data, inference models or service calls."""
import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BASE=Path(os.environ.get('DEMO_SOURCES_ROOT',Path(__file__).resolve().parents[1]))
ADAPTER=BASE/'deid'
sys.path.insert(0,str(ADAPTER))
spec=importlib.util.spec_from_file_location('review_adapter',ADAPTER/'service.py')
service=importlib.util.module_from_spec(spec);spec.loader.exec_module(service)

class ReviewContractTests(unittest.TestCase):
    def test_default_policy_and_all_modes_reconstruct_exact_output_with_unicode(self):
        text='😀 Synthetic-only: demo@example.invalid and (555) 234-9981.'
        for mode in service.ENGINES:
            with self.subTest(mode=mode):
                result=service._analyse(text,mode)
                self.assertTrue(result['entities'])
                cursor=0;parts=[]
                for entity in result['entities']:
                    start,end=entity['span']
                    self.assertEqual(entity['surface'],text[start:end])
                    self.assertIsInstance(entity['replacement'],str)
                    parts.extend((text[cursor:start],entity['replacement']));cursor=end
                parts.append(text[cursor:])
                self.assertEqual(''.join(parts),result['result_text'])
                self.assertNotIn(service.SALT,json.dumps(result))
                self.assertNotIn('salt',result)

    def test_email_span_uses_codepoints_after_non_bmp_character(self):
        text='😀 demo@example.invalid'
        result=service._analyse(text,'redact')
        email=next(e for e in result['entities']if e['label']=='EMAIL')
        self.assertEqual(email['span'][0],2)
        self.assertEqual(email['surface'],'demo@example.invalid')

    def test_overlapping_metadata_is_rejected(self):
        malformed={'entities':[{'span':[0,4],'label':'PERSON','action':'redact'},
                               {'span':[2,5],'label':'PERSON','action':'redact'}],
                   'result_text':'untrusted'}
        with patch.object(service.ENGINES['redact'],'deidentify',return_value=malformed):
            with self.assertRaisesRegex(ValueError,'Overlapping'):
                service._analyse('synthetic','redact')

    def test_mismatched_replacement_never_publishes_an_inconsistent_review(self):
        malformed={'entities':[{'span':[0,4],'label':'PERSON','action':'redact'}],
                   'result_text':'wrong output'}
        with patch.object(service.ENGINES['redact'],'deidentify',return_value=malformed):
            with self.assertRaisesRegex(ValueError,'do not match'):
                service._analyse('name','redact')

if __name__=='__main__':unittest.main()
