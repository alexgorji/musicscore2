from unittest import TestCase
from unittest.mock import patch

from musictree.beat import Beat
from musictree.chord import Chord
from musictree.measure import Measure
from musictree.part import Part
from musictree.staff import Staff
from musictree.voice import Voice


class TestStaff(TestCase):
    def test_staff_init(self):
        st = Staff()
        assert st.value is None
        assert st.xml_object.value is None
        st = Staff(3)
        assert st.xml_object.value == 3
        assert st.value == 3
        st.value = 2
        assert st.xml_object.value == 2
        st.xml_object.value = None
        assert st.value is None
        assert st.xml_object.value is None

    @patch('musictree.measure.Measure')
    def test_add_child(self, mock_measure):
        st = Staff()
        st._parent = mock_measure
        assert [child.value for child in st.get_children()] == []
        st.add_child(Voice())
        assert [child.value for child in st.get_children()] == [1]
        st.add_child(Voice())
        assert len(st.get_children()) == 2
        assert [child.value for child in st.get_children()] == [1, 2]

    @patch('musictree.measure.Measure')
    def test_add_voice(self, mock_measure):
        st = Staff()
        st._parent = mock_measure
        v = st.add_voice()
        assert st.get_children()[-1] == v
        assert len(st.get_children()) == 1
        assert v.value == 1
        v = st.add_voice(4)
        assert v.value == 4
        assert len(st.get_children()) == 4
        assert [v.value for v in st.get_children()] == [1, 2, 3, 4]

    def test_get_previous_staff(self):
        p = Part('P1')
        m1 = p.add_measure()
        m2 = p.add_measure()
        m1.add_staff(2)
        m2.add_staff(2)
        st11, st12 = m1.get_children()
        st21, st22 = m2.get_children()
        assert st11.get_previous_staff() is None
        assert st12.get_previous_staff() is None
        assert st21.get_previous_staff() == st11
        assert st22.get_previous_staff() == st12

    def test_get_last_steps_with_accidentals(self):
        m1 = Measure(1)
        m1.add_chord(Chord(midis=[61, 62, 63], quarter_duration=2))
        m1.add_chord(Chord(midis=[63, 64, 66], quarter_duration=2))
        assert m1.get_staff(1).get_last_steps_with_accidentals() == {'E', 'F'}
