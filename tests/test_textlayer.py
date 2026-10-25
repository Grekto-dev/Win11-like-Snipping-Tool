import unittest
import cairo
import shutil
from captura import textlayer
from captura.textlayer import Word


TSV = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    "1\t1\t0\t0\t0\t0\t0\t0\t200\t100\t-1\t\n"
    "5\t1\t1\t1\t1\t1\t20\t10\t60\t20\t96\tContato:\n"
    "5\t1\t1\t1\t1\t2\t90\t10\t100\t20\t95\tana@example.com\n"
    "5\t1\t1\t1\t2\t1\t20\t50\t80\t20\t91\t+55\n"
    "5\t1\t1\t1\t2\t2\t110\t50\t70\t20\t92\t11999990000\n"
    "5\t1\t1\t1\t3\t1\t20\t80\t30\t20\t-1\t \n"
)


class TextLayerTests(unittest.TestCase):
    def test_tsv_words_are_scaled_back_to_image_coordinates(self):
        words = textlayer.parse_tsv(TSV, scale=2)
        self.assertEqual([w.text for w in words], ["Contato:", "ana@example.com", "+55", "11999990000"])
        self.assertEqual(words[0].box, (10, 5, 40, 15))
        self.assertEqual(words[0].line, (1, 1, 1))

    def test_text_is_reassembled_by_lines(self):
        words = textlayer.parse_tsv(TSV, scale=1)
        self.assertEqual(textlayer.words_text(words), "Contato: ana@example.com\n+55 11999990000")

    def test_sensitive_words_include_email_and_phone_groups(self):
        words = textlayer.parse_tsv(TSV, scale=1)
        hits = textlayer.sensitive(words)
        self.assertEqual([w.text for w in hits["email"]], ["ana@example.com"])
        self.assertEqual([w.text for w in hits["phone"]], ["+55", "11999990000"])

    def test_phone_split_across_short_tokens_is_one_group(self):
        words = [Word("Telefone:", (0, 0, 9, 9), (1, 1, 1)), Word("+55", (10, 0, 19, 9), (1, 1, 1)),
                 Word("11", (20, 0, 29, 9), (1, 1, 1)), Word("99999-0000", (30, 0, 39, 9), (1, 1, 1)),
                 Word("Ano", (0, 20, 9, 29), (1, 1, 2)), Word("2026", (10, 20, 19, 29), (1, 1, 2))]
        self.assertEqual([w.text for w in textlayer.sensitive(words)["phone"]], ["+55", "11", "99999-0000"])

    def test_words_in_rectangle_uses_overlap_not_only_center(self):
        words = textlayer.parse_tsv(TSV, scale=1)
        picked = textlayer.words_in_rect(words, (85, 5, 120, 35))
        self.assertEqual([w.text for w in picked], ["ana@example.com"])

    @unittest.skipUnless(shutil.which("tesseract"), "tesseract not installed")
    def test_real_tesseract_returns_word_boxes_for_rendered_text(self):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 520, 120)
        cr = cairo.Context(surface)
        cr.set_source_rgb(1, 1, 1); cr.paint(); cr.set_source_rgb(0, 0, 0)
        cr.select_font_face("DejaVu Sans"); cr.set_font_size(42)
        cr.move_to(20, 70); cr.show_text("Hello captura")
        words = textlayer.ocr_surface(surface)
        self.assertEqual([w.text.lower() for w in words], ["hello", "captura"])
        x0, y0, x1, y1 = words[0].box
        self.assertTrue(0 <= x0 < x1 < 260 and 20 <= y0 < y1 <= 90, words[0].box)


if __name__ == "__main__":
    unittest.main()
