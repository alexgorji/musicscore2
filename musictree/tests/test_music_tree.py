from unittest.mock import patch

from musictree.accidental import Accidental
from musictree.beat import Beat
from musictree.chord import Chord
from musictree.measure import Measure
from musictree.midi import Midi
from musictree.note import Note
from musictree.part import Part
from musictree.score import Score
from musictree.staff import Staff
from musictree.tests.util import IdTestCase
from musictree.voice import Voice


class TestMusicTree(IdTestCase):
    @patch.object(Chord, 'get_voice_number')
    def test_add_child_type(self, mock_chord_method):
        mock_chord_method.return_value = 1
        s = Score()
        p = Part('P1')
        m = Measure(1)
        st = Staff()
        v = Voice()
        b = Beat()
        c1 = Chord(60, 0.5)
        c2 = Chord(60, 0.25)
        assert p == s.add_child(p)
        assert m == p.add_child(m)
        assert st == m.add_child(st)
        assert v == st.add_child(v)
        assert b == v.add_child(b)
        assert c1 == b.add_child(c1)
        assert c2 == c1.add_child(c2)
        objects = [s, m, st, v, b, c1, c2]
        for parent in objects:
            with self.assertRaises(TypeError):
                parent.add_child(s)
        for parent in objects:
            if parent != s:
                with self.assertRaises(TypeError):
                    parent.add_child(p)
        for parent in objects:
            if parent != p:
                with self.assertRaises(TypeError):
                    parent.add_child(m)
