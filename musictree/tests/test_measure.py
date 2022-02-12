from unittest import TestCase

from musicxml.xmlelement.xmlelement import *
from quicktions import Fraction

from musictree.chord import Chord
from musictree.exceptions import VoiceIsAlreadyFullError
from musictree.measure import Measure, generate_measures
from musictree.part import Part
from musictree.staff import Staff
from musictree.tests.test_beat import create_voice
from musictree.tests.util import generate_all_quintuplets, generate_all_sextuplets, generate_all_triplets, IdTestCase
from musictree.time import Time
from musictree.voice import Voice


class TestMeasure(TestCase):

    def test_measure_default_init(self):
        expected = """<measure number="1">
  <attributes>
    <divisions>1</divisions>
    <key>
      <fifths>0</fifths>
    </key>
    <time>
      <beats>4</beats>
      <beat-type>4</beat-type>
    </time>
    <clef>
      <sign>G</sign>
      <line>2</line>
    </clef>
  </attributes>
</measure>
"""
        m = Measure(1)
        assert m.to_string() == expected

    def test_number(self):
        m = Measure(number=2)
        assert m.number == 2
        m.number = 4
        assert m.number == 4
        m.xml_object.number = '3'
        assert m.number == 3

    def test_measure_time_signature(self):
        m = Measure(1)
        expected = """<time>
      <beats>4</beats>
      <beat-type>4</beat-type>
    </time>
"""
        assert m.time.to_string() == expected
        m.time = Time(3, 4)
        expected = """<time>
  <beats>3</beats>
  <beat-type>4</beat-type>
</time>
"""
        assert m.time.to_string() == expected
        m = Measure(2, time=Time(5, 8, 2, 4))
        expected = """<time>
      <beats>5</beats>
      <beat-type>8</beat-type>
      <beats>2</beats>
      <beat-type>4</beat-type>
    </time>
"""
        assert m.time.to_string() == expected

    def test_measure_add_child_staff(self):
        m = Measure(1)
        assert m.get_children() == []
        st1 = m.add_child(Staff())
        assert st1.value is None
        assert m.get_children() == [st1]
        st2 = m.add_child(Staff())
        assert m.get_children() == [st1, st2]
        assert (st1.value, st2.value) == (1, 2)
        with self.assertRaises(ValueError):
            m.add_child(Staff(2))

        m = Measure(1)
        st1 = m.add_child(Staff(1))
        assert st1.value == 1

        m = Measure(1)
        with self.assertRaises(ValueError):
            m.add_child(Staff(2))

    def test_check_divisions(self):
        m = Measure(1)
        st = m.add_child(Staff())
        v1 = st.add_child(Voice(1))
        v2 = st.add_child(Voice(2))
        quarter_durations_1 = [1 / 3, 2 / 3, 2 / 5, 3 / 5, 1, 1 / 2, 1 / 2]
        quarter_durations_2 = [1, 9 / 7, 5 / 7, 2 / 3, 1 / 3]
        for qd in quarter_durations_1:
            v1.add_chord(Chord(60, qd))
        for qd in quarter_durations_2:
            v2.add_chord(Chord(70, qd))
        m.update_divisions()
        assert m.xml_object.xml_attributes.xml_divisions.value == 210

    def test_add_chord(self):
        m = Measure(1)
        chord = Chord(60, quarter_duration=2.5)
        chord.midis[0].accidental.show = False
        m.add_chord(chord)
        chord = Chord(61, quarter_duration=1.5)
        chord.midis[0].accidental.show = True
        m.add_chord(chord)

        m._update_xml_notes()
        for xml_note, duration in zip(m.find_children('XMLNote'), [4, 1, 1, 2]):
            assert xml_note.xml_duration.value == duration
        expected = """<measure number="1">
  <attributes>
    <divisions>2</divisions>
    <key>
      <fifths>0</fifths>
    </key>
    <time>
      <beats>4</beats>
      <beat-type>4</beat-type>
    </time>
    <clef>
      <sign>G</sign>
      <line>2</line>
    </clef>
  </attributes>
  <note>
    <pitch>
      <step>C</step>
      <octave>4</octave>
    </pitch>
    <duration>4</duration>
    <tie type="start" />
    <voice>1</voice>
    <type>half</type>
    <notations>
      <tied type="start" />
    </notations>
  </note>
  <note>
    <pitch>
      <step>C</step>
      <octave>4</octave>
    </pitch>
    <duration>1</duration>
    <tie type="stop" />
    <voice>1</voice>
    <type>eighth</type>
    <beam number="1">begin</beam>
    <notations>
      <tied type="stop" />
    </notations>
  </note>
  <note>
    <pitch>
      <step>C</step>
      <alter>1</alter>
      <octave>4</octave>
    </pitch>
    <duration>1</duration>
    <tie type="start" />
    <voice>1</voice>
    <type>eighth</type>
    <accidental>sharp</accidental>
    <beam number="1">end</beam>
    <notations>
      <tied type="start" />
    </notations>
  </note>
  <note>
    <pitch>
      <step>C</step>
      <alter>1</alter>
      <octave>4</octave>
    </pitch>
    <duration>2</duration>
    <tie type="stop" />
    <voice>1</voice>
    <type>quarter</type>
    <notations>
      <tied type="stop" />
    </notations>
  </note>
</measure>
"""
        assert m.to_string() == expected

    def test_get_staff(self):
        m = Measure(1)
        assert m.get_staff(staff_number=None) is None
        st = m.add_child(Staff())
        assert m.get_staff(staff_number=None) == st
        st.value = 1
        assert m.get_staff(staff_number=1) == st
        st = m.add_child(Staff())
        assert m.get_staff(staff_number=2) == st

    def test_add_staff(self):
        m = Measure(1)
        st = m.add_staff()
        assert m.get_staff(staff_number=None) == st

        st = m.add_staff()
        assert st.value is None

        st = m.add_staff(1)
        assert m.get_staff(staff_number=1) == st

        st = m.add_staff(5)
        assert m.get_staff(staff_number=5) == st
        assert len(m.get_children()) == 5
        assert [st.value for st in m.get_children()] == [1, 2, 3, 4, 5]

    def test_add_voice(self):
        m = Measure(1)
        v = m.add_voice(staff_number=None, voice_number=2)
        st = m.get_staff(staff_number=None)
        assert st.get_children()[-1] == v
        assert [v.value for v in st.get_children()] == [1, 2]

        v = m.add_voice(staff_number=2, voice_number=3)
        assert [st.value for st in m.get_children()] == [1, 2]
        assert [v.value for v in m.get_staff(2).get_children()] == [1, 2, 3]

    def test_get_voice(self):
        m = Measure(1)
        with self.assertRaises(TypeError):
            m.get_voice(None, 1)
        assert m.get_voice(staff_number=None, voice_number=1) is None
        st = m.add_child(Staff())
        assert m.get_voice(staff_number=None, voice_number=1) is None
        v = st.add_child(Voice())
        assert m.get_voice(staff_number=None, voice_number=1) == v
        assert m.get_voice(staff_number=1, voice_number=1) == v
        v = st.add_child(Voice())
        assert m.get_voice(staff_number=None, voice_number=2) == v

    def test_add_chord_voice_filled(self):
        m = Measure(1)
        ch = Chord(quarter_duration=2, midis=60)
        returned_chords = m.add_chord(ch)
        assert len(returned_chords) == 1
        assert returned_chords[0] == ch
        assert returned_chords[0].quarter_duration == 2
        assert m.get_children()[0].get_children()[0].left_over_chord is None
        ch = Chord(quarter_duration=2, midis=60)
        returned_chords = m.add_chord(ch)
        assert len(returned_chords) == 1
        assert returned_chords[0] == ch
        assert returned_chords[0].quarter_duration == 2
        assert m.get_children()[0].get_children()[0].left_over_chord is None
        with self.assertRaises(VoiceIsAlreadyFullError):
            m.add_chord(Chord(quarter_duration=2, midis=60))
        ch = Chord(quarter_duration=2, midis=60)
        returned_chords = m.add_chord(ch, voice_number=2)
        assert len(returned_chords) == 1
        assert [ch.voice for ch in m.get_chords()] == [1, 1, 2]

    def test_add_chord_left_over(self):
        m = Measure(1)
        ch = Chord(quarter_duration=5, midis=60)
        returned_chords = m.add_chord(ch)
        assert len(returned_chords) == 1
        assert returned_chords[0] == ch
        assert returned_chords[0].quarter_duration == 4
        assert m.get_voice(staff_number=1, voice_number=1).left_over_chord.quarter_duration == 1

    def test_attributes(self):
        """
        Test that a dot operator can directly reach the xml_object
        """
        m = Measure(1)
        m.xml_object.width = 5
        assert m.width == 5

        m.width = 7
        assert m.xml_object.width == 7

        with self.assertRaises(AttributeError):
            m.hello = 'bbb'
        m.xml_object.width = 10

        assert m.xml_object.width == 10
        assert m.width == 10

        m = Measure(1)
        m.width = 10
        assert m.width == 10
        assert m.xml_object.width == 10

    def test_barstyle(self):
        m = Measure(number='1')
        assert m.xml_barline is None
        m.xml_barline = XMLBarline()
        m.xml_barline.xml_bar_style = 'light-light'
        expected = """<measure number="1">
  <attributes>
    <divisions>1</divisions>
    <key>
      <fifths>0</fifths>
    </key>
    <time>
      <beats>4</beats>
      <beat-type>4</beat-type>
    </time>
    <clef>
      <sign>G</sign>
      <line>2</line>
    </clef>
  </attributes>
  <barline>
    <bar-style>light-light</bar-style>
  </barline>
</measure>
"""
        assert m.xml_object.to_string() == expected

    def test_update_beats_from_parent_measure(self):
        v = Voice()
        m = Measure(1)
        st = m.add_child(Staff())
        st.add_child(v)
        assert [child.quarter_duration.as_integer_ratio() for child in v.get_children()] == [(1, 1)] * 4

        m = Measure(1, time=Time(3, 4, 1, 8))
        st = m.add_child(Staff())
        st.add_child(v)
        assert [child.quarter_duration.as_integer_ratio() for child in v.get_children()] == [(1, 1)] * 3 + [(1, 2)]

        m.time = Time(2, 8)
        assert [child.quarter_duration.as_integer_ratio() for child in v.get_children()] == [(1, 2)] * 2

        m.time.signatures = [3, 4, 1, 8]
        assert [child.quarter_duration.as_integer_ratio() for child in v.get_children()] == [(1, 1)] * 3 + [(1, 2)]

        m.time.actual_signatures = [1, 8, 1, 8]
        assert [child.quarter_duration.as_integer_ratio() for child in v.get_children()] == [(1, 2)] * 2

    def test_generate_measures(self):
        times = [2 * Time(3, 8), (3, 4), 3 * [(1, 8)], Time(1, 8, 3, 4), Time(3, 4)]
        measures = generate_measures(times, 3)
        assert len(measures) == 8
        assert [m.time.signatures for m in measures] == [(3, 8), (3, 8), (3, 4), (1, 8), (1, 8), (1, 8), (1, 8, 3, 4), (3, 4)]
        assert [m.number for m in measures] == list(range(3, 11))

    def test_add_chord_staff_and_voice(self):
        m = Measure(1)
        m.add_chord(Chord(60, 1), staff_number=2, voice_number=2)
        assert m.get_staff(2) is not None
        assert m.get_voice(staff_number=2, voice_number=2) is not None
        m.add_chord(Chord(60, 1), staff_number=4, voice_number=5)
        assert m.get_voice(staff_number=3, voice_number=1) is not None
        assert m.get_voice(staff_number=3, voice_number=2) is None
        assert m.get_voice(staff_number=3, voice_number=5) is None
        assert m.get_voice(staff_number=4, voice_number=1) is not None
        assert m.get_voice(staff_number=4, voice_number=2) is not None
        assert m.get_voice(staff_number=4, voice_number=3) is not None
        assert m.get_voice(staff_number=4, voice_number=4) is not None
        assert m.get_voice(staff_number=4, voice_number=5) is not None


class TestTuplets(TestCase):

    def test_simple_triplet(self):
        expected_1 = """<note>
    <pitch>
      <step>C</step>
      <octave>4</octave>
    </pitch>
    <duration>1</duration>
    <voice>1</voice>
    <type>eighth</type>
    <time-modification>
      <actual-notes>3</actual-notes>
      <normal-notes>2</normal-notes>
      <normal-type>eighth</normal-type>
    </time-modification>
    <notations>
      <tuplet bracket="yes" number="1" type="start" />
    </notations>
  </note>
"""
        expected_2 = """<note>
    <pitch>
      <step>C</step>
      <octave>4</octave>
    </pitch>
    <duration>2</duration>
    <voice>1</voice>
    <type>quarter</type>
    <time-modification>
      <actual-notes>3</actual-notes>
      <normal-notes>2</normal-notes>
      <normal-type>eighth</normal-type>
    </time-modification>
    <notations>
      <tuplet number="1" type="stop" />
    </notations>
  </note>
"""
        m = Measure(1)
        ch1 = Chord(midis=60, quarter_duration=1 / 3)
        ch2 = Chord(midis=60, quarter_duration=2 / 3)
        for c in [ch1, ch2]:
            c.midis[0].accidental.show = False
            m.add_chord(c)
        m._update_xml_notes()
        assert ch1.notes[0].to_string() == expected_1
        assert ch2.notes[0].to_string() == expected_2

    def test_chord_simple_triplet(self):
        m = Measure(1)
        chords = [Chord(60, 1 / 3), Chord(61, 2 / 3)]

        for x in chords:
            m.add_chord(x)

        m._update_xml_notes()

        t1, t2 = [ch.notes[0].xml_notations.xml_tuplet for ch in chords]
        assert t1.type == 'start'
        assert t2.type == 'stop'
        for note in [ch.notes[0] for ch in chords]:
            assert note.xml_time_modification is not None
            assert note.xml_time_modification.xml_actual_notes.value == 3
            assert note.xml_time_modification.xml_normal_notes.value == 2
            assert note.xml_time_modification.xml_normal_type.value == 'eighth'

    def test_chord_quintuplet(self):
        measures = []
        for index, quintuplet in enumerate(generate_all_quintuplets()):
            m = Measure(index + 1)
            for q in quintuplet:
                m.add_chord(Chord(midis=60, quarter_duration=q))
            m._update_xml_notes()
            measures.append(m)

        for m in measures:
            for ch in m.get_chords():
                note = ch.notes[0]
                assert note.xml_time_modification is not None
                assert note.xml_time_modification.xml_actual_notes.value == 5
                assert note.xml_time_modification.xml_normal_notes.value == 4
                assert note.xml_time_modification.xml_normal_type.value == '16th'
            first_note = m.get_chords()[0].notes[0]
            last_note = m.get_chords()[-1].notes[0]
            t1, t2 = first_note.xml_notations.xml_tuplet, last_note.xml_notations.xml_tuplet
            assert t1.type == 'start'
            assert t2.type == 'stop'

    def test_chord_sextuplets_not_writable_1(self):
        m1 = Measure(1)
        quarter_durations = [Fraction(1, 6), Fraction(5, 6)]
        for q in quarter_durations:
            m1.add_chord(Chord(midis=60, quarter_duration=q))
        m1._update_xml_notes()
        b = m1.get_voice(staff_number=1, voice_number=1).get_children()[0]
        assert b.get_children() == m1.get_chords()
        n1, n2, n3 = [ch.notes[0] for ch in m1.get_chords()]
        assert n1.xml_notations.xml_tuplet.type == 'start'
        assert n3.xml_notations.xml_tuplet.type == 'stop'
        assert not n1.is_tied
        assert n2.is_tied
        assert n3.is_tied_to_previous
        assert n3.xml_dot is not None
        assert n3.midi.accidental.show is False

    def test_chord_sextuplets_not_writable_2(self):
        m1 = Measure(1)
        quarter_durations = [Fraction(5, 6), Fraction(1, 6)]
        for q in quarter_durations:
            m1.add_chord(Chord(midis=60, quarter_duration=q))
        m1._update_xml_notes()
        n1, n2, n3 = [ch.notes[0] for ch in m1.get_chords()]
        assert n1.xml_notations.xml_tuplet.type == 'start'
        assert n3.xml_notations.xml_tuplet.type == 'stop'
        assert n1.is_tied
        assert n2.is_tied_to_previous
        assert not n3.is_tied
        assert n1.xml_dot is not None
        assert n2.midi.accidental.show is False

    def test_chord_sextuplets(self):
        measures = []
        for index, sextuplet in enumerate(generate_all_sextuplets()):
            m = Measure(index + 1)
            for q in sextuplet:
                m.add_chord(Chord(midis=60, quarter_duration=q))
            m._update_xml_notes()
            measures.append(m)

        for m in measures:
            for ch in m.get_chords():
                note = ch.notes[0]
                assert note.xml_time_modification is not None
                assert note.xml_time_modification.xml_actual_notes.value == 6
                assert note.xml_time_modification.xml_normal_notes.value == 4
                assert note.xml_time_modification.xml_normal_type.value == '16th'
            first_note = m.get_chords()[0].notes[0]
            last_note = m.get_chords()[-1].notes[0]
            t1, t2 = first_note.xml_notations.xml_tuplet, last_note.xml_notations.xml_tuplet
            assert t1.type == 'start'
            assert t2.type == 'stop'

    def test_update_xml_brackets(self):
        v1 = create_voice()
        beats = v1.update_beats(1, 1, 1, 1)
        ch1, ch2, ch3 = chords = [Chord(60, 2 / 5), Chord(61, 2 / 5), Chord(62, 1 / 5)]
        for ch in chords:
            beats[0].add_child(ch)
        beats[0]._update_xml_notes()
        assert ch1.notes[0].xml_notations.xml_tuplet.type == 'start'
        assert ch1.notes[0].xml_notations.xml_tuplet.bracket == 'yes'
        assert ch1.notes[0].xml_notations.xml_tuplet.number == 1
        assert ch2.notes[0].xml_notations is None
        assert ch3.notes[0].xml_notations.xml_tuplet.type == 'stop'
        assert ch3.notes[0].xml_notations.xml_tuplet.number == 1

    def test_complex_tuplet(self):
        v1 = create_voice()
        beats = v1.update_beats(1)
        for quarter_duration in [1 / 6, 1 / 6, 1 / 6, 1 / 10, 3 / 10, 1 / 10]:
            v1.add_chord(Chord(60, quarter_duration))
        beats[0]._update_xml_notes()
        n1, n2, n3, n4, n5, n6 = [ch.notes[0] for ch in v1.get_chords()]
        for n in [n1, n2, n3]:
            assert (n.xml_time_modification.xml_actual_notes.value, n.xml_time_modification.xml_normal_notes.value,
                    n.xml_time_modification.xml_normal_type.value) == (3, 2, '16th')
        for n in [n4, n5, n6]:
            assert (n.xml_time_modification.xml_actual_notes.value, n.xml_time_modification.xml_normal_notes.value,
                    n.xml_time_modification.xml_normal_type.value) == (5, 4, '32nd')
        assert n1.xml_notations.xml_tuplet.type == 'start'
        assert n2.xml_notations is None
        assert n3.xml_notations.xml_tuplet.type == 'stop'
        assert n4.xml_notations.xml_tuplet.type == 'start'
        assert n5.xml_notations is None
        assert n6.xml_notations.xml_tuplet.type == 'stop'

    def test_group_beams_triplets(self):
        v1 = create_voice()
        beats = v1.update_beats(1, 1, 1)
        for quarter_duration in [q for group in generate_all_triplets() for q in group]:
            v1.add_chord(Chord(60, quarter_duration))
        for index, beat in enumerate(beats):
            beat._update_xml_notes()
            if index == 0:
                for i, c in enumerate(beat.get_children()):
                    beams = c.notes[0].find_children('XMLBeam')
                    assert len(beams) == 1
                    assert beams[0].number == 1
                    assert beams[0].value == 'begin' if i == 0 else 'continue' if i == 1 else 'end'
            else:
                for c in beat.get_children():
                    assert c.notes[0].find_child('XMLBeam') is None


class TestUpdateAccidentals(IdTestCase):
    def test_update_accidentals_simple(self):
        m = Measure(1)
        midis = [60, 61, 62, 60]
        for mi in midis:
            m.add_chord(Chord(mi, quarter_duration=1))
        m._update_xml_notes()
        assert [ch.midis[0].accidental.show for ch in m.get_chords()] == [False, True, False, True]

    def test_update_accidentals_with_last_steps(self):
        p = Part('P1')
        p.add_measure()
        p.add_measure()
        p.add_chord(Chord(midis=60, quarter_duration=2))
        p.add_chord(Chord(midis=61, quarter_duration=2))
        p.add_chord(Chord(midis=60, quarter_duration=4))
        for m in p.get_children():
            m._update_xml_notes()
        last_chord = p.get_children()[-1].get_children()[-1].get_chords()[0]
        assert last_chord.midis[0].accidental.sign == 'natural'
        assert last_chord.midis[0].accidental.show

    def test_quarter_duration(self):
        m = Measure(1)
        assert m.quarter_duration == 4
        m.time.signatures = (3, 4)
        assert m.quarter_duration == 3
        m.time.signatures = (2, 4, 1, 8)
        assert m.quarter_duration == 2.5

    def test_xml_notes_with_different_voices(self):
        m = Measure(1)
        m.add_chord(Chord(60, 4))
        m.add_chord(Chord(60, 4), voice_number=2)
        m._update_xml_notes()
        ch1, ch2 = m.get_chords()
        assert ch1.notes[0].xml_voice.value == '1'
        assert ch2.notes[0].xml_voice.value == '2'
        b = m.xml_object.find_child('XMLBackup')
        assert b is not None

    def test_xml_notes_with_different_staves(self):
        m = Measure(1)
        m.add_chord(Chord(72, 4), staff_number=1, voice_number=1)
        m.add_chord(Chord(60, 4), staff_number=1, voice_number=2)
        m.add_chord(Chord(48, 4), staff_number=2, voice_number=1)
        m.add_chord(Chord(36, 4), staff_number=2, voice_number=2)
        m._update_xml_notes()
        ch1, ch2, ch3, ch4 = m.get_chords()
        assert ch1.notes[0].xml_staff.value == 1
        assert ch2.notes[0].xml_staff.value == 1
        assert ch3.notes[0].xml_staff.value == 2
        assert ch4.notes[0].xml_staff.value == 2
        assert ch1.notes[0].xml_voice.value == '1'
        assert ch2.notes[0].xml_voice.value == '2'
        assert ch3.notes[0].xml_voice.value == '1'
        assert ch4.notes[0].xml_voice.value == '2'
        backups = m.xml_object.find_children('XMLBackup')
        assert len(backups) == 3
        assert m.xml_attributes.xml_staves.value == 2
        cl1, cl2 = m.xml_attributes.find_children('XMLClef')
        assert cl1.number == 1
        assert cl2.number == 2
        assert cl1.xml_sign.value == 'G'
        assert cl1.xml_line.value == 2
        assert cl2.xml_sign.value == 'F'
        assert cl2.xml_line.value == 4
