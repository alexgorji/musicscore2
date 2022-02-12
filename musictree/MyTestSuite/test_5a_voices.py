from pathlib import Path

from musictree.chord import Chord
from musictree.measure import Measure
from musictree.part import Part
from musictree.score import Score
from musictree.staff import Staff
from musictree.tests.util import IdTestCase


class TestHelloPianoStaves(IdTestCase):
    def test_export_hello_world_piano_staves(self):
        """
        Tester creates a timewise score
        """
        s = Score()
        """
        He adds a part
        """
        p = s.add_child(Part('P1', name='Music'))
        """
        He adds some chords for two voices
        """
        for qd in 4 * [1]:
            p.add_chord(Chord(60, qd), voice_number=3)
        for qd in 8 * [1 / 2]:
            p.add_chord(Chord(72, qd), voice_number=2)
        for qd in 12 * [1 / 3]:
            p.add_chord(Chord(84, qd), voice_number=1)
        s.update_xml_notes()
        """
        ... and exports the xml
        """
        xml_path = Path(__file__).with_suffix('.xml')
        s.export_xml(xml_path)
