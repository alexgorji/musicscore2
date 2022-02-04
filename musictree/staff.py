from musicxml.xmlelement.xmlelement import XMLStaff

from musictree.exceptions import StaffHasNoParentError
from musictree.musictree import MusicTree
from musictree.xmlwrapper import XMLWrapper


class Staff(MusicTree, XMLWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self._xml_object = XMLStaff(*args, **kwargs)

    def add_child(self, child):
        self._check_child_to_be_added(child)
        if not self.up:
            raise StaffHasNoParentError('A child Voice can only be added to a Staff if staff has a Measure parent.')

        if child.value is not None and child.value != len(self.get_children()) + 1:
            raise ValueError(f'Voice number must be None or {len(self.get_children()) + 1}')
        if child.value is None:
            child.value = len(self.get_children()) + 1
        else:
            child.value = len(self.get_children()) + 1

        child._parent = self
        self._children.append(child)
        child.update_beats()
        return child
