from fractions import Fraction
from unittest import TestCase
from unittest.mock import Mock, patch

from musictree.accidental import Accidental
from musictree.chord import Chord
from musictree.exceptions import ChordHasNoParentError, ChordQuarterDurationAlreadySetError, NoteTypeError, ChordCannotAddSelfAsChild
from musictree.midi import Midi
from musictree.tests.util import check_notes


def get_chord_midi_values(chord):
    return [m.value for m in chord._midis]


class TestTreeChord(TestCase):
    def setUp(self) -> None:
        self.mock_beat = Mock()
        self.mock_voice = Mock()
        self.mock_staff = Mock()
        self.mock_measure = Mock()

        self.mock_voice.value = 1
        self.mock_beat.up = self.mock_voice
        self.mock_voice.up = self.mock_staff
        self.mock_staff.up = self.mock_measure
        self.mock_measure.get_divisions.return_value = 1

    def tearDown(self) -> None:
        patch.stopall()

    def test_mocks(self):
        assert self.mock_voice.value == 1
        assert self.mock_beat.up.value == 1
        ch = Chord()
        ch._parent = self.mock_beat
        assert ch.up == self.mock_beat
        assert ch.up.up == self.mock_voice
        assert ch.up.up.up == self.mock_staff
        assert ch.up.up.up.up == self.mock_measure
        assert ch.get_parent_measure() == self.mock_measure

    def test_chord_init_midis(self):
        """
        Test all possible types of input midis
        """
        ch = Chord(70, 1)
        assert get_chord_midi_values(ch) == [70]
        ch = Chord([70, 50], 1)
        assert get_chord_midi_values(ch) == [70, 50]
        ch = Chord(0, 1)
        assert get_chord_midi_values(ch) == [0]
        ch = Chord(Midi(90, accidental=Accidental(mode='enharmonic_1')), 1)
        assert get_chord_midi_values(ch) == [90]
        ch = Chord([Midi(90, accidental=Accidental(mode='enharmonic_1')), 70], 1)
        assert get_chord_midi_values(ch) == [90, 70]

        with self.assertRaises(ValueError):
            Chord([0, 60], 1)

        """
        A grace note cannot be a rest.
        """
        with self.assertRaises(ValueError):
            Chord(0, 0)

    def test_chord_needs_parent_error(self):
        ch = Chord(70, 1)
        with self.assertRaises(ChordHasNoParentError):
            ch.update_notes()
        ch._parent = self.mock_beat
        ch.update_notes()

    def test_chord_update_notes(self):
        ch1 = Chord()
        assert ch1.notes is None
        with self.assertRaises(ChordHasNoParentError):
            ch1.update_notes()
        ch1.quarter_duration = 1
        ch1.midis = [70]
        ch1._parent = self.mock_beat
        ch1.update_notes()
        check_notes(ch1.notes, [70], [1])
        with self.assertRaises(ChordQuarterDurationAlreadySetError):
            ch1.quarter_duration = 1.5
        ch2 = Chord(quarter_duration=2.5, midis=[71])
        ch2._parent = self.mock_beat
        with self.assertRaises(NoteTypeError):
            ch2.update_notes()

    def test_init_quarter_durations(self):
        """
        Test values of quarter_duration
        """
        ch = Chord(90, 1.25)
        assert ch.quarter_duration == 1.25
        ch = Chord(80, 1.2)
        assert ch.quarter_duration == Fraction(1.2)
        assert ch.quarter_duration == 1.2
        assert ch.quarter_duration == Fraction(6 / 5)
        assert ch.quarter_duration == 6 / 5
        ch = Chord(80, 8)
        assert ch.quarter_duration == 8
        with self.assertRaises(TypeError):
            ch = Chord(80, '1.2')

    def test_is_rest(self):
        """
        Test is_rest property
        """
        assert Chord(0, 1).is_rest
        assert not Chord(50, 1).is_rest

    def test_chord_attributes(self):
        """
        Test that a dot operator can set and get note attributes
        """
        c = Chord([60, 61, 62], 2)
        c._parent = self.mock_beat
        c.update_notes()
        c.relative_x = 10
        assert c.relative_x == [10, 10, 10]
        c.relative_y = [None, 20, 10]
        assert c.relative_y == [None, 20, 10]
        c.relative_y = [10]
        assert c.relative_y == [10, 20, 10]
        c.default_y = [10]
        assert c.default_y == [10, None, None]

    def test_chord_one_note(self):
        c = Chord(70, 4, relative_x=10)
        c._parent = self.mock_beat
        c.update_notes()
        expected = """<note relative-x="10">
    <pitch>
        <step>B</step>
        <alter>-1</alter>
        <octave>4</octave>
    </pitch>
    <duration>4</duration>
    <voice>1</voice>
    <type>whole</type>
    <accidental>flat</accidental>
</note>
"""
        assert c.notes[0].to_string() == expected
        c.midis[0].value = 72
        expected = """<note relative-x="10">
    <pitch>
        <step>C</step>
        <octave>5</octave>
    </pitch>
    <duration>4</duration>
    <voice>1</voice>
    <type>whole</type>
</note>
"""
        assert c.notes[0].to_string() == expected
        # change chord's midi (zero)
        c.midis[0].value = 0

        expected = """<note relative-x="10">
    <rest />
    <duration>4</duration>
    <voice>1</voice>
    <type>whole</type>
</note>
"""
        assert c.notes[0].to_string() == expected
        c = Chord(midis=0, quarter_duration=2)
        # change chord's duration (not zero)
        c.quarter_duration = 1
        c._parent = self.mock_beat
        c.update_notes()
        expected = """<note>
    <rest />
    <duration>1</duration>
    <voice>1</voice>
    <type>quarter</type>
</note>
"""
        assert c.notes[0].to_string() == expected
        c = Chord(0, 1)
        # change chord's duration (zero)
        with self.assertRaises(ValueError):
            c.quarter_duration = 0
        c.midis[0].value = 60
        c.quarter_duration = 0
        c._parent = self.mock_beat
        c.update_notes()
        expected = """<note>
    <grace />
    <pitch>
        <step>C</step>
        <octave>4</octave>
    </pitch>
    <voice>1</voice>
</note>
"""
        assert c.notes[0].to_string() == expected
        # change chord's attributes?
        c.notes[0].relative_x = 20
        c.notes[0].relative_y = 15
        expected = """<note relative-x="20" relative-y="15">
    <grace />
    <pitch>
        <step>C</step>
        <octave>4</octave>
    </pitch>
    <voice>1</voice>
</note>
"""
        assert c.notes[0].to_string() == expected

    def test_chord_single_non_rest(self):
        """
        Test a chord with a non rest single midi
        """
        c = Chord(72, 2)
        c._parent = self.mock_beat
        c.update_notes()

        c.xml_type = '16th'
        c.xml_stem = 'up'
        c.xml_staff = 1

        expected = """<note>
    <pitch>
        <step>C</step>
        <octave>5</octave>
    </pitch>
    <duration>2</duration>
    <voice>1</voice>
    <type>16th</type>
    <stem>up</stem>
    <staff>1</staff>
</note>
"""
        assert c.notes[0].to_string() == expected
        c.midis[0].value = 61
        expected = """<pitch>
    <step>C</step>
    <alter>1</alter>
    <octave>4</octave>
</pitch>
"""
        assert c.notes[0].xml_pitch.to_string() == expected
        c.midis[0].value = 0
        assert c.notes[0].xml_pitch is None
        assert c.notes[0].xml_rest is not None
        assert c.is_rest

    def test_chord_single_non_rest_midi_with_accidental(self):
        """
        Test chord with a non rest single midi with accidental set.
        """
        chord = Chord(Midi(70, accidental=Accidental(mode='sharp')), 1)
        chord._parent = self.mock_beat
        chord.update_notes()
        expected = """<pitch>
        <step>A</step>
        <alter>1</alter>
        <octave>4</octave>
    </pitch>
"""
        assert chord.notes[0].xml_pitch.to_string() == expected

    def test_chord_as_rest(self):
        """
        Test chord with a rest midi
        """
        chord = Chord(0, 2)
        chord._parent = self.mock_beat
        expected = """<note>
    <rest />
    <duration>2</duration>
    <voice>1</voice>
    <type>half</type>
</note>
"""
        chord.update_notes()
        assert chord.notes[0].to_string() == expected
        chord.midis = [60, 61]
        expected = """<pitch>
        <step>C</step>
        <octave>4</octave>
    </pitch>
"""
        assert chord.notes[0].xml_pitch.to_string() == expected
        expected = """<pitch>
        <step>C</step>
        <alter>1</alter>
        <octave>4</octave>
    </pitch>
"""
        assert chord.notes[1].xml_pitch.to_string() == expected

    def test_chord_to_rest(self):
        chord = Chord(60, 2)
        chord._parent = self.mock_beat
        chord.update_notes()
        chord.to_rest()
        expected = """<note>
    <rest />
    <duration>2</duration>
    <voice>1</voice>
    <type>half</type>
</note>
"""
        assert chord.notes[0].to_string() == expected
        assert len(chord.notes) == 1

    def test_chord_with_multiple_midis(self):
        """
        Test chord with a list of midis
        """

        chord = Chord([60, 62, 63], 2)
        chord._parent = self.mock_beat
        chord.update_notes()
        chord.xml_stem = 'up'
        expected_1 = """<note>
    <pitch>
        <step>C</step>
        <octave>4</octave>
    </pitch>
    <duration>2</duration>
    <voice>1</voice>
    <type>half</type>
    <stem>up</stem>
</note>
"""
        expected_2 = """<note>
    <pitch>
        <step>D</step>
        <octave>4</octave>
    </pitch>
    <duration>2</duration>
    <voice>1</voice>
    <type>half</type>
    <stem>up</stem>
</note>
"""
        expected_3 = """<note>
    <pitch>
        <step>E</step>
        <alter>-1</alter>
        <octave>4</octave>
    </pitch>
    <duration>2</duration>
    <voice>1</voice>
    <type>half</type>
    <accidental>flat</accidental>
    <stem>up</stem>
</note>
"""
        for note, expected in zip(chord.notes, [expected_1, expected_2, expected_3]):
            assert note.to_string() == expected

    def test_chord_tie_untie(self):
        ch1 = Chord(midis=[60, 61], quarter_duration=1)
        ch2 = Chord(midis=[60, 61], quarter_duration=1)
        ch1.add_tie('start')
        ch2.add_tie('stop')
        ch1._parent = self.mock_beat
        ch2._parent = self.mock_beat
        ch1.update_notes()
        ch2.update_notes()
        assert [n.is_tied for n in ch1.notes] == [True, True]
        assert [n.is_tied for n in ch2.notes] == [False, False]
        assert [n.is_tied_to_previous for n in ch2.notes] == [True, True]

        ch1 = Chord(midis=[60, 61], quarter_duration=1)
        ch2 = Chord(midis=[60, 61], quarter_duration=1)
        ch1._parent = self.mock_beat
        ch2._parent = self.mock_beat
        ch1.update_notes()
        ch2.update_notes()

        ch1.add_tie('start')
        ch2.add_tie('stop')

        assert [n.is_tied for n in ch1.notes] == [True, True]
        assert [n.is_tied for n in ch2.notes] == [False, False]
        assert [n.is_tied_to_previous for n in ch2.notes] == [True, True]

    def test_chord_self_as_child(self):
        ch1 = Chord(midis=[60, 61], quarter_duration=1)
        ch2 = Chord(midis=[60, 61], quarter_duration=0.5)
        ch1.add_child(ch2)
        with self.assertRaises(ChordCannotAddSelfAsChild):
            ch1.add_child(ch1)

    def test_chord_copy(self):
        self.fail('Incomplete')
        # ch1 = Chord(midis=[60, 61], quarter_duration=1)

    def test_chord_split_copy(self):
        self.fail('Incomplete')
