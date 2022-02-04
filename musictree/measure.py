from musicxml.xmlelement.xmlelement import XMLMeasure, XMLAttributes, XMLDivisions, XMLKey, XMLClef

from musictree.musictree import MusicTree
from musictree.staff import Staff
from musictree.time import Time
from musictree.util import lcm
from musictree.voice import Voice
from musictree.xmlwrapper import XMLWrapper


class Measure(MusicTree, XMLWrapper):
    _ATTRIBUTES = {'number', 'time'}

    def __init__(self, number, time=None, *args, **kwargs):
        super().__init__()
        self._xml_object = XMLMeasure(*args, **kwargs)
        self.number = number
        self._time = None
        self.time = time
        self._set_attributes()

    def _set_attributes(self):
        self.xml_object.xml_attributes = XMLAttributes()
        self.xml_object.xml_attributes.xml_divisions = 1
        self.xml_object.xml_attributes.xml_key = XMLKey()
        self.xml_object.xml_attributes.xml_key.xml_fifths = 0
        self.xml_object.xml_attributes.xml_time = self.time.xml_object
        self.xml_object.xml_attributes.xml_clef = XMLClef()
        self.xml_object.xml_attributes.xml_clef.xml_sign = 'G'
        self.xml_object.xml_attributes.xml_clef.xml_line = 2

    def _get_chords(self):
        beats = [b for staff in self.get_children() for voice in staff.get_children() for b in voice.get_children()]
        chords = [ch for b in beats for ch in b.get_children()]
        return chords

    def update_divisions(self):
        chord_divisions = {ch.quarter_duration.denominator for ch in self._get_chords()}
        divisions = lcm(list(chord_divisions))
        self.xml_object.xml_attributes.xml_divisions = divisions

    def _update_voice_beats(self):
        for staff in self.get_children():
            for voice in staff.get_children():
                voice.update_beats()

    def update_xml_notes(self):
        current_xml_notes = self.xml_object.find_children('XMLNote')
        for note in current_xml_notes:
            note.up.remove(note)
        self.update_divisions()
        for chord in self._get_chords():
            if not chord.notes:
                chord.update_notes()
        current_notes = [note for chord in self._get_chords() for note in chord.notes]
        for note in current_notes:
            self.xml_object.add_child(note.xml_object)

    @property
    def number(self):
        return int(self.xml_object.number)

    @number.setter
    def number(self, val):
        self.xml_object.number = str(val)

    @property
    def time(self):
        return self._time

    @time.setter
    def time(self, val):
        if val is not None and not isinstance(val, Time):
            raise TypeError()
        if val is None:
            val = Time()
        self._time = val
        self._time.parent_measure = self
        self._update_voice_beats()

    def add_child(self, child):
        self._check_child_to_be_added(child)
        if child.value is not None and child.value != len(self.get_children()) + 1:
            raise ValueError(f'Staff number must be None or {len(self.get_children()) + 1}')
        if child.value is None:
            if not self.get_children():
                pass
            elif len(self.get_children()) == 1:
                self.get_children()[0].value = 1
                child.value = len(self.get_children()) + 1
            else:
                child.value = len(self.get_children()) + 1

        child._parent = self
        self._children.append(child)
        return child
        # Must be called from within voice, if voice is filled.

    def add_chord(self, chord, staff=1, voice=1):
        for x in range(staff - len(self.get_children())):
            self.add_child(Staff())
        staff = self.get_children()[staff - 1]
        for x in range(voice - len(staff.get_children())):
            staff.add_child(Voice())
        voice = staff.get_children()[voice - 1]
        return voice.add_chord(chord)

    def get_divisions(self):
        return self.xml_object.xml_attributes.xml_divisions.value
