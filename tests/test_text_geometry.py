import os
import unittest

from captura import textlayer
from captura.textlayer import Word

IMG = os.path.expanduser("~/snip-tool-research/shots/ocr-input.png")


class GeometryTests(unittest.TestCase):
    WORDS = [Word("Contato:", (173, 247, 253, 262), (1, 1, 2)),
             Word("ana.silva@example.com", (262, 246, 500, 267), (1, 1, 2)),
             Word("Telefone:", (172, 286, 259, 302), (1, 1, 3)),
             Word("+55", (268, 287, 303, 302), (1, 1, 3))]

    def test_lines_group_in_reading_order_with_windows_padding(self):
        lines = textlayer.group_lines(self.WORDS)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].box, (162, 234, 510, 273))
        self.assertEqual([w.text for w in lines[1].words], ["Telefone:", "+55"])

    def test_selection_rect_is_one_per_line_and_covers_the_gap(self):
        rects = textlayer.sel_rects(self.WORDS)
        self.assertEqual(len(rects), 2)
        self.assertEqual(rects[0], (172, 243, 504, 268))

    def test_select_between_follows_reading_order(self):
        got = textlayer.select_between(self.WORDS, (300, 255), (200, 295))
        self.assertEqual([w.text for w in got], ["ana.silva@example.com", "Telefone:"])
        self.assertEqual([w.text for w in textlayer.select_between(self.WORDS, (0, 0), (9999, 9999))], [w.text for w in self.WORDS])


@unittest.skipUnless(os.path.exists(IMG) and textlayer.services.ocr_available(), "tesseract/imagem de teste ausentes")
class RealOcrTests(unittest.TestCase):
    def test_real_tesseract_reads_the_sample_with_boxes_and_sensitive_data(self):
        import cairo
        from gi.repository import Gdk, GdkPixbuf
        pb = GdkPixbuf.Pixbuf.new_from_file(IMG)
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, pb.get_width(), pb.get_height())
        cr = cairo.Context(s)
        Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0)
        cr.paint()
        words = textlayer.ocr_surface(s)
        text = textlayer.words_text(words)
        for expected in ("Relatório de visita", "ana.silva@example.com", "+55 11 99999-0000", "www.example.org/ajuda", "às 14h30"):
            self.assertIn(expected, text)
        found = textlayer.sensitive(words)
        self.assertEqual([w.text for w in found["email"]], ["ana.silva@example.com"])
        self.assertEqual("".join(w.text for w in found["phone"]), "+551199999-0000")
        for w in words:
            self.assertTrue(0 <= w.box[0] < w.box[2] <= pb.get_width() and 0 <= w.box[1] < w.box[3] <= pb.get_height())


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(os.path.exists(os.path.expanduser("~/snip-tool-research/shots/ocr-table.png")) and textlayer.services.ocr_available(), "tesseract/imagem ausentes")
class RealTableTests(unittest.TestCase):
    def test_real_ocr_reads_a_table_cell_by_cell_and_detects_it(self):
        import cairo
        from gi.repository import Gdk, GdkPixbuf
        pb = GdkPixbuf.Pixbuf.new_from_file(os.path.expanduser("~/snip-tool-research/shots/ocr-table.png"))
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, pb.get_width(), pb.get_height())
        cr = cairo.Context(s); Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0); cr.paint()
        words = textlayer.ocr_surface(s)
        rows = textlayer.detect_table(words)
        self.assertIsNotNone(rows)
        self.assertEqual(rows[0], ["Produto", "Qtd", "Preço"])
        self.assertEqual(rows[-1][0], "Mochila")
        self.assertEqual(rows[-1][2], "R$ 120,00")                        # o Tesseract às vezes não lê dígitos soltos ("1")
        self.assertGreaterEqual(len(textlayer.group_lines(words)), 10)    # uma caixa por célula (o Windows acha as 12)
