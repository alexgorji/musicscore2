from musicxml.xsd.xsdtree import XSDTree


class XSDElement:
    def __init__(self, xsd_tree):
        self._xsd_tree = None
        self.xsd_tree = xsd_tree
        self._xml_elements = []

    @property
    def xsd_tree(self):
        return self._xsd_tree

    @xsd_tree.setter
    def xsd_tree(self, value):
        if not isinstance(value, XSDTree):
            raise TypeError
        if value.tag != 'element':
            raise ValueError
        self._xsd_tree = value

    @property
    def name(self):
        return self.xsd_tree.name

    def add_xml_element(self, el):
        if el.name != self.name:
            raise TypeError
        self._xml_elements.append(el)

    @property
    def xml_elements(self):
        return self._xml_elements