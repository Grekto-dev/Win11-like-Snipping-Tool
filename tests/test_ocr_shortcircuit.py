"""Never recognize a dense pass whose result the existing selection rule discards."""
import unittest
from unittest.mock import patch
import gi
gi.require_version('GdkPixbuf','2.0')
from gi.repository import GdkPixbuf
from captura import ocr_engine as E,services,textlayer


def table_words():
    return [[str(row * 10 + col), 20 + col * 240, 20 + row * 40,
             70 + col * 240, 40 + row * 40, 95.0, 1, 1, row + 1]
            for row in range(3) for col in range(2)]


class ShortCircuitTests(unittest.TestCase):
    def setUp(self):
        E.POOL.shutdown()
        E.POOL.cache.clear()
        E.POOL.requests.clear()
        self.addCleanup(E.POOL.shutdown)
        self.pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 1400, 400)
        self.pb.fill(0xffffffff)

    def read_with(self, sparse, reject_dense=False):
        calls=[]
        class FakeProc:
            dead=False
            def set_image(self,pb):
                pass
            def call(self,req):
                calls.append(req['psm'])
                if req['psm']==4 and reject_dense:
                    raise AssertionError('discarded dense pass was executed')
                return {'ok':True,'words':sparse if req['psm']==11 else [['dense',20,20,60,40,95.0,1,1,1]]}
        with patch.object(E,'pool_size',return_value=1), \
             patch.object(E.POOL,'ensure',return_value=[FakeProc()]), \
             patch.object(services,'ocr_language_spec',return_value='eng'):
            words=textlayer.ocr_pixbuf_words(self.pb)
        return calls,words

    def test_sparse_winner_never_runs_discarded_dense_pass_on_one_cpu(self):
        calls,words=self.read_with(table_words(),reject_dense=True)
        self.assertEqual(calls,[11])
        self.assertEqual([w.text for w in words],[r[0] for r in table_words()])
        self.assertIsNotNone(textlayer.detect_table(words))

    def test_non_table_keeps_both_original_passes_and_selects_dense(self):
        calls,words=self.read_with([['plain',20,20,60,40,95.0,1,1,1]])
        self.assertEqual(calls,[11,4])
        self.assertEqual([w.text for w in words],['dense'])

    def test_empty_sparse_still_runs_dense(self):
        calls,words=self.read_with([])
        self.assertEqual(calls,[11,4])
        self.assertEqual([w.text for w in words],['dense'])


    def test_full_pair_cache_is_not_confused_with_short_circuit_result(self):
        calls=[]
        class FakeProc:
            dead=False
            def set_image(self,pb):
                pass
            def call(self,req):
                calls.append(req['psm'])
                return {'ok':True,'words':table_words()}
        with patch.object(E,'pool_size',return_value=1), patch.object(E.POOL,'ensure',return_value=[FakeProc()]):
            selected=E.recognize_pair(self.pb,'eng',accept_sparse=lambda _rows:True)
            full=E.recognize_pair(self.pb,'eng')
        self.assertEqual(selected[1],[])
        self.assertTrue(full[1])
        self.assertEqual(calls,[11,11,4])

    def test_different_selectors_do_not_share_partial_cached_results(self):
        calls=[]
        class FakeProc:
            dead=False
            def set_image(self,pb):
                pass
            def call(self,req):
                calls.append(req['psm'])
                return {'ok':True,'words':table_words()}
        with patch.object(E,'pool_size',return_value=1), patch.object(E.POOL,'ensure',return_value=[FakeProc()]):
            E.recognize_pair(self.pb,'eng',accept_sparse=lambda _rows:True)
            full=E.recognize_pair(self.pb,'eng',accept_sparse=lambda _rows:False)
        self.assertTrue(full[1])
        self.assertEqual(calls,[11,11,4])

    def test_cancel_in_selector_never_starts_dense_recognition(self):
        calls=[]
        token=E.new_job('short-circuit-test')
        self.addCleanup(lambda:E.end_job(token))
        class FakeProc:
            dead=False
            def set_image(self,pb):
                pass
            def call(self,req):
                calls.append(req['psm'])
                return {'ok':True,'words':table_words()}
        def cancelled(_rows):
            token.cancel()
            return False
        with patch.object(E,'pool_size',return_value=1), patch.object(E.POOL,'ensure',return_value=[FakeProc()]):
            with self.assertRaises(E.Cancelled):
                E.recognize_pair(self.pb,'eng',token,accept_sparse=cancelled)
        self.assertEqual(calls,[11])


if __name__=='__main__':
    unittest.main()
