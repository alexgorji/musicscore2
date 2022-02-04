from musictree.util import isinstance_as_string
from tree.tree import Tree


class MusicTree(Tree):
    """
    MusicTree is the parent class of all music tree objects:
    Score (root)
    Part (1st layer)
    Measure (2nd layer)
    Staff (3rd layer)
    Voice (4th layer)
    Beat (5th layer)
    Chord (6th layer)
    Note (7th layer)
    Midi (8th layer)
    Midi can represent a pitch or a rest (value=0) and controls accidental sign of the pitch if necessary.
    Accidental (9th layer)
    """

    def _check_child_to_be_added(self, child):
        if not isinstance_as_string(child.__class__, 'MusicTree'):
            raise TypeError(f'MusicTree child must be of type MusicTree not {child.__class__}')

        parent_child = {'Score': 'Part', 'Part': 'Measure', 'Measure': 'Staff', 'Staff': 'Voice', 'Voice': 'Beat', 'Beat': 'Chord',
                        'Chord': 'Chord'}

        try:
            if not isinstance_as_string(child.__class__, parent_child[self.__class__.__name__]):
                raise TypeError(f'{self.__class__.__name__} accepts only children of type {parent_child[self.__class__.__name__]} not '
                                f'{child.__class__.__name__}')
        except KeyError:
            raise NotImplementedError(f'{self.__class__.__name__} add_child() not implemented.')
