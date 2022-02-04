from typing import Union, List, Optional

from fractions import Fraction

from musictree.exceptions import NoteTypeError, ChordAlreadySplitError, ChordCannotSplitError, ChordHasNoParentError, \
    ChordHasNoQuarterDurationError, ChordQuarterDurationAlreadySetError, ChordCannotAddSelfAsChild
from musictree.midi import Midi
from musictree.musictree import MusicTree
from musictree.note import Note
from musictree.quarterduration import QuarterDurationMixin, QuarterDuration, _check_quarter_duration


class Chord(MusicTree, QuarterDurationMixin):
    """
    Chord is a sequence of one or more XMLNotes which occur at the same time in a XMLMeasure of a XMLPart.
    :param midis: midi, midis, midi value or midi values. 0 or [0] for a rest.
    :param quarter_duration: int or float for duration counted in quarters (crotchets). 0 for grace note (or chord).
    """
    _ATTRIBUTES = {'midis', 'quarter_duration', 'notes', '_note_attributes', 'offset', 'split', 'voice', 'ties'}

    def __init__(self, midis: Optional[Union[List[Union[float, int]], List[Midi], float, int, Midi]] = None,
                 quarter_duration: Optional[Union[float, int, 'Fraction', QuarterDuration]] = None, offset=0, **kwargs):
        self._voice = None
        self._midis = None
        self._notes = None
        self._offset = None
        self._ties = []

        self._note_attributes = kwargs
        self.offset = offset
        super().__init__(quarter_duration=quarter_duration)
        self._set_midis(midis)
        self.split = False

    def _check_child_to_be_added(self, child):
        if child == self:
            raise ChordCannotAddSelfAsChild
        super()._check_child_to_be_added(child)

    def _update_notes_quarter_duration(self):
        if self.notes is not None:
            for note in self.notes:
                note.quarter_duration = self.quarter_duration

    def _update_notes_pitch_or_rest(self):
        if self.notes:
            len_diff = len(self.notes) - len(self.midis)
            if len_diff > 0:
                to_be_removed = self.self.notes[len_diff:]
                self._notes = self.notes[:len_diff]
                for note in to_be_removed:
                    note.parent_chord = None
                    del note
            for index, m in enumerate(self.midis):
                if index < len(self.notes):
                    self.notes[index].midi = m
                else:
                    new_note = Note(parent_chord=self, midi=m, quarter_duration=self.quarter_duration)
                    self._notes.append(new_note)

    def _update_tie(self):
        if self.notes:
            if not self._ties:
                for note in self.notes:
                    note.remove_tie()
            else:
                if 'stop' in self._ties:
                    for note in self.notes:
                        note.stop_tie()
                if 'start' in self._ties:
                    for note in self.notes:
                        note.start_tie()

    def _set_midis(self, midis):
        if isinstance(midis, str):
            raise TypeError
        if hasattr(midis, '__iter__'):
            pass
        elif midis is None:
            midis = []
        else:
            midis = [midis]
        if len(midis) > 1 and 0 in midis:
            raise ValueError('Chord cannot accept a mixed list of midis of rests and pitches or a list of more than one rests.')

        if 0 in midis and self.quarter_duration == 0:
            raise ValueError('A rest cannot be a grace note')
        self._midis = [Midi(v) if not isinstance(v, Midi) else v for v in midis]
        self._update_notes_pitch_or_rest()

    @property
    def is_rest(self):
        if self._midis[0].value == 0:
            return True
        else:
            return False

    @property
    def midis(self):
        return self._midis

    @midis.setter
    def midis(self, val):
        self._set_midis(val)

    @property
    def notes(self):
        return self._notes

    @property
    def offset(self):
        return self._offset

    @offset.setter
    def offset(self, val):
        _check_quarter_duration(val)
        if isinstance(val, QuarterDuration):
            self._offset = val
        else:
            self._offset = QuarterDuration(val)

    @QuarterDurationMixin.quarter_duration.setter
    def quarter_duration(self, val):
        if self._quarter_duration is not None and self.up:
            raise ChordQuarterDurationAlreadySetError('Chord is already attached to a Beat. Quarter Duration cannot be changed any more.')
        if val is not None:
            if self.midis and self.is_rest and val == 0:
                raise ValueError('A rest cannot be a grace note')
            self._set_quarter_duration(val)
            self._update_notes_quarter_duration()

    @property
    def voice(self):
        if self._voice is None:
            if self.up and self.up.up:
                return self.up.up.value
            else:
                return 1
        return self._voice

    def add_tie(self, val):
        if val not in ['start', 'stop']:
            raise ValueError
        if val not in self._ties:
            self._ties.append(val)
            self._update_tie()

    def get_voice_number(self):
        return self.up.up.value

    def get_parent_measure(self):
        if isinstance(self.up, Chord):
            return self.up.up.up.up
        return self.up.up.up

    def split_beatwise(self, beats):
        voice_set = {beat.up for beat in beats}
        if len(voice_set) != 1:
            raise ChordCannotSplitError('Beats have must have a single Voice as common ancestor.')
        voice = voice_set.pop()
        if voice is None:
            raise ChordCannotSplitError('Beats have no parent.')
        if voice.get_children()[voice.get_children().index(beats[0]): voice.get_children().index(beats[-1]) + 1] != beats:
            raise ChordCannotSplitError()

        if beats[0] != voice.get_current_beat():
            raise ChordAlreadySplitError('First beat must be the next beat in voice which can accept chords.')
        if beats[-1] != voice.get_children()[-1]:
            raise ChordAlreadySplitError('Last beat must be the last beat in voice.')

        if self.get_children():
            raise ChordAlreadySplitError("Remove chord's children if you wish to split it again.")

        quarter_durations = self.quarter_duration.get_beatwise_sections(
            offset=beats[0].filled_quarter_duration, beats=beats)
        left_over_chord = None
        if quarter_durations[1] is None and len(quarter_durations[0]) == 1:
            self.split = True
            voice.fill_beats([self])
            # voice.get_current_beat().add_child(self)
            return [self]
        else:
            first_quarter_duration = quarter_durations[0][0]
            first_copied_chord = Chord(midis=self.midis, quarter_duration=first_quarter_duration)
            current_chord = first_copied_chord
            current_chord.split = True
            # voice.get_current_beat().add_child(current_chord)
            output = [first_copied_chord]
            for qd in quarter_durations[0][1:]:
                copied = Chord(midis=self.midis, quarter_duration=qd)
                copied.split = True
                # voice.get_current_beat().add_child(copied)
                current_chord.add_tie('start')
                copied.add_tie('stop')
                current_chord = copied
                output.append(current_chord)
            if quarter_durations[1]:
                left_over_chord = Chord(midis=self.midis, quarter_duration=quarter_durations[1])
                current_chord.add_tie('start')
                left_over_chord.add_tie('stop')
        for ch in output:
            self.add_child(ch)
        voice.left_over_chord = left_over_chord
        if left_over_chord:
            self.add_child(left_over_chord)
        return output

    def to_rest(self):
        self.midis = [0]

    def to_string(self):
        raise AttributeError("object 'Chord' cannot return a string.")

    def update_notes(self):
        if not self.up:
            raise ChordHasNoParentError('Chord needs a parent Beat to create notes.')
        self.get_parent_measure().update_divisions()
        self._notes = [Note(parent_chord=self, midi=midi, **self._note_attributes) for midi in self._midis]
        self._update_notes_quarter_duration()
        self._update_tie()

    def __setattr__(self, key, value):
        if key not in self._ATTRIBUTES.union(self.TREE_ATTRIBUTES) and key not in [f'_{attr}' for attr in
                                                                                   self._ATTRIBUTES.union(
                                                                                       self.TREE_ATTRIBUTES)] and key not in self.__dict__:
            if self.notes is not None:
                if isinstance(value, str) or not hasattr(value, '__iter__'):
                    value = [value] * len(self.notes)
                for n, v in zip(self.notes, value):
                    setattr(n, key, v)
        else:
            super().__setattr__(key, value)

    def __getattr__(self, item):
        if not self.notes:
            raise AttributeError(f"AttributeError: 'Chord' object has no attribute '{item}'")
        output = [getattr(n, item) for n in self.notes]
        if output and callable(output[0]):
            raise AttributeError(f"Chord cannot call Note method {item}. Call this method on each note separately")
        return output
        # return [getattr(n, item) for n in self.notes]
        # return [n.__getattr__(item) for n in self.notes]
