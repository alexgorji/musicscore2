from musicxml.xmlelement.xmlelement import XMLMeasure, XMLAttributes, XMLDivisions, XMLKey, XMLClef, XMLBackup

from musictree.musictree import MusicTree
from musictree.staff import Staff
from musictree.time import Time, flatten_times
from musictree.util import lcm
from musictree.voice import Voice
from musictree.xmlwrapper import XMLWrapper


class Measure(MusicTree, XMLWrapper):
    _ATTRIBUTES = {'number', 'time', 'quarter_duration'}

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

    def _update_attributes(self):
        self.xml_object.xml_attributes.xml_key = XMLKey()
        self.xml_object.xml_attributes.xml_key.xml_fifths = 0
        self.xml_object.xml_attributes.xml_time = self.time.xml_object
        if len(self.get_children()) > 1:
            self.xml_object.xml_attributes.xml_staves = len(self.get_children())

        if len(self.get_children()) == 1:
            self.xml_object.xml_attributes.xml_clef = XMLClef()
            self.xml_object.xml_attributes.xml_clef.xml_sign = 'G'
            self.xml_object.xml_attributes.xml_clef.xml_line = 2
        elif len(self.get_children()) == 2:
            for n in range(1, 3):
                cl = self.xml_object.xml_attributes.add_child(XMLClef(number=n))
                if n == 1:
                    cl.xml_sign = 'G'
                    cl.xml_line = 2
                else:
                    cl.xml_sign = 'F'
                    cl.xml_line = 4
        else:
            raise NotImplementedError()

    def _update_voice_beats(self):
        for staff in self.get_children():
            for voice in staff.get_children():
                voice.update_beats()

    def _update_accidentals(self):
        def chord_is_in_a_repetition(chord):
            if chord.quarter_duration <= 1.5:
                my_index = chord.up.up.get_chords().index(chord)
                if my_index > 0:
                    previous_chord = chord.up.up.get_chords()[my_index - 1]
                    if previous_chord.quarter_duration < -1.5 and chord.has_same_pitches(previous_chord):
                        return True
            return False

        for staff in self.get_children():
            previous_staff = staff.get_previous_staff()
            steps_with_accidentals = set()
            relevant_chords = [ch for ch in staff.get_chords() if not ch.is_rest]
            relevant_chords_not_tied = [ch for ch in relevant_chords if 'stop' not in ch._ties]
            for chord in relevant_chords:
                for midi in chord.midis:
                    step = midi.accidental.get_pitch_parameters()[0]
                    if midi.accidental.show is None:
                        if midi.accidental.sign == 'natural':
                            if step in steps_with_accidentals:
                                midi.accidental.show = True
                                steps_with_accidentals.remove(step)
                            elif chord == relevant_chords_not_tied[0] and previous_staff and step in \
                                    previous_staff.get_last_steps_with_accidentals():
                                midi.accidental.show = True
                            else:
                                midi.accidental.show = False
                        else:
                            if chord_is_in_a_repetition(chord):
                                midi.accidental.show = False
                            else:
                                midi.accidental.show = True
                                if step not in steps_with_accidentals:
                                    steps_with_accidentals.add(step)
                    elif midi.accidental.sign != 'natural' and step not in steps_with_accidentals:
                        steps_with_accidentals.add(step)

    def _update_xml_notes(self):
        self._update_attributes()

        def reset_notes():
            current_xml_notes = self.xml_object.find_children('XMLNote')
            current_xml_backups = self.xml_object.find_children('XMLBackup')
            for note in current_xml_notes:
                note.up.remove(note)
            for backup in current_xml_backups:
                backup.up.remove(backup)

        def add_backup():
            b = XMLBackup()
            d = self.quarter_duration * self.get_divisions()
            if int(d) != d:
                raise ValueError
            b.xml_duration = int(d)
            self.xml_object.add_child(b)

        reset_notes()
        self.update_divisions()
        for beat in [b for staff in self.get_children() for voice in staff.get_children() for b in voice.get_children()]:
            beat._update_xml_notes()
        self._update_accidentals()
        for staff in self.get_children():
            if staff != self.get_children()[0]:
                add_backup()
            for index, voice in enumerate(staff.get_children()):
                chords = voice.get_chords()
                if index != 0:
                    add_backup()
                for note in [note for chord in chords for note in chord.notes]:
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

    @property
    def quarter_duration(self):
        return sum(self.time.get_beats_quarter_durations())

    def add_child(self, child):
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
        return super().add_child(child)

    def add_chord(self, chord, *, staff_number=None, voice_number=1):
        voice = self.add_voice(staff_number=staff_number, voice_number=voice_number)
        return voice.add_chord(chord)

    def add_staff(self, staff_number=1):
        if staff_number is None:
            staff_number = 1
        staff_object = self.get_staff(staff_number=staff_number)
        if staff_object is None:
            for _ in range(staff_number - len(self.get_children())):
                new_staff = self.add_child(Staff())
                new_staff.add_child(Voice())
            return new_staff
        return staff_object

    def add_voice(self, *, staff_number=1, voice_number=1):
        if staff_number is None:
            staff_number = 1
        voice_object = self.get_voice(staff_number=staff_number, voice_number=voice_number)
        if voice_object is None:
            staff_object = self.add_staff(staff_number=staff_number)
            return staff_object.add_voice(voice_number=voice_number)
        return voice_object

    def get_chords(self):
        beats = [b for staff in self.get_children() for voice in staff.get_children() for b in voice.get_children()]
        chords = [ch for b in beats for ch in b.get_children()]
        return chords

    def get_divisions(self):
        return self.xml_object.xml_attributes.xml_divisions.value

    def get_staff(self, staff_number=1):
        if staff_number is None:
            staff_number = 1
        try:
            return self.get_children()[staff_number - 1]
        except IndexError:
            return None

    def get_voice(self, *, staff_number=1, voice_number=1):
        staff_object = self.get_staff(staff_number=staff_number)
        if staff_object:
            for child in staff_object.get_children():
                if child.value == voice_number:
                    return child

    def update_divisions(self):
        chord_divisions = {ch.quarter_duration.denominator for ch in self.get_chords()}
        divisions = lcm(list(chord_divisions))
        self.xml_object.xml_attributes.xml_divisions = divisions

    def update_chord_accidentals(self):
        for staff in self.get_children():
            for chord in staff.get_chords():
                if 'stop' in chord._ties:
                    for midi in chord.midis:
                        midi.accidental.show = False
                for midi in chord.midis:
                    if midi.accidental.sign == 'natural':
                        midi.accidental.show = False


def generate_measures(times, first_number=1):
    """
    :param [Time, ratio] times: list containing time objects or ratios (1, 4)
    :param int first_number: first measure number
    :return [Measure]: measures
    """
    times = flatten_times(times)
    output = []
    for index, time in enumerate(times):
        output.append(Measure(first_number + index, time=time))
    return output
