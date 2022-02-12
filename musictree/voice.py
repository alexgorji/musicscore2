from musicxml.xmlelement.xmlelement import XMLVoice

from musictree.beat import Beat
from musictree.exceptions import VoiceHasNoBeatsError, VoiceHasNoParentError, ChordHasNoQuarterDurationError, VoiceIsAlreadyFullError
from musictree.musictree import MusicTree
from musictree.xmlwrapper import XMLWrapper


class Voice(MusicTree, XMLWrapper):
    _ATTRIBUTES = {'value', '_chords', '_current_beat', 'left_over_chord', 'is_filled'}

    def __init__(self, value=None, *args, **kwargs):
        super().__init__()
        self._xml_object = XMLVoice(*args, **kwargs)
        self.value = value
        self._current_beat = None
        self.left_over_chord = None

    @property
    def is_filled(self):
        if self.get_children():
            return self.get_children()[-1].is_filled
        else:
            return False

    @property
    def value(self):
        object_value = self.xml_object.value
        if object_value is not None:
            return int(object_value)

    @value.setter
    def value(self, val):
        if val is not None:
            self.xml_object.value = str(val)
        else:
            self.xml_object.value = None

    def add_child(self, child):
        if not self.up:
            raise VoiceHasNoParentError('A child Beat can only be added to a Voice if voice has a Staff parent.')
        return super().add_child(child)

    def add_chord(self, chord):
        if not self.get_children():
            raise VoiceHasNoBeatsError
        if self.get_current_beat() is None:
            raise VoiceIsAlreadyFullError(f'Voice number {self.value} of Measure number {self.up.up.number} is full.')
        return self.get_current_beat().add_child(chord)

    def get_chords(self):
        return [ch for b in self.get_children() for ch in b.get_children()]

    def get_current_beat(self):
        if not self.get_children():
            raise ValueError('Voice has no beats.')
        else:
            for beat in self.get_children():
                if not beat.is_filled:
                    return beat

    def update_beats(self, *quarter_durations):
        if not quarter_durations:
            if self.up and self.up.up:
                quarter_durations = self.up.up.time.get_beats_quarter_durations()
            else:
                return
        else:
            if len(quarter_durations) == 1 and hasattr(quarter_durations[0], '__iter__'):
                quarter_durations = quarter_durations[0]

        self.remove_children()

        for quarter_duration in quarter_durations:
            self.add_child(Beat(quarter_duration))
        return self.get_children()
