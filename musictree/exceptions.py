class MusicTreeException(Exception):
    pass


class NoteException(MusicTreeException):
    pass


class NoteHasNoParentChordError(NoteException):
    pass


class NoteTypeError(NoteException):
    pass


class ChordException(MusicTreeException):
    pass


class ChordAlreadySplitError(ChordException):
    pass


class ChordCannotSplitError(ChordException):
    pass


class ChordHasNoParentError(ChordException):
    pass


class ChordHasNoQuarterDurationError(ChordException):
    pass


class ChordQuarterDurationAlreadySetError(ChordException):
    pass


class ChordHasNoMidisError(ChordException):
    pass


class ChordCannotAddSelfAsChild(ChordException, ValueError):
    pass


class BeatException(MusicTreeException):
    pass


class BeatWrongDurationError(BeatException, ValueError):
    pass


class BeatIsFullError(BeatException):
    pass


class BeatHasNoParentError(BeatException):
    pass


class VoiceException(MusicTreeException):
    pass


class VoiceHasNoBeatsError(VoiceException):
    pass


class VoiceHasNoParentError(VoiceException):
    pass


class StaffException(MusicTreeException):
    pass


class StaffHasNoParentError(StaffException):
    pass


class MeasureException(MusicTreeException):
    pass


class IdException(MusicTreeException):
    pass


class IdHasAlreadyParentOfSameTypeError(IdException):
    pass


class IdWithSameValueExistsError(IdException):
    pass
