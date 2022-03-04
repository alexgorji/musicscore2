import copy
import xml.etree.ElementTree as ET
from typing import Optional, List, Callable, Union

from musicxml.exceptions import XSDWrongAttribute, XSDAttributeRequiredException, XMLElementChildrenRequired
from musicxml.generate_classes.utils import musicxml_xsd_et_root, ns
from tree.tree import Tree
from musicxml.util.core import cap_first, replace_key_underline_with_hyphen
from musicxml.xmlelement.containers import containers
from musicxml.xmlelement.exceptions import XMLElementCannotHaveChildrenError
from musicxml.xmlelement.xmlchildcontainer import DuplicationXSDSequence
from musicxml.xsd.xsdcomplextype import *
from musicxml.xsd.xsdsimpletype import *
from musicxml.xsd.xsdtree import XSDTree


class XMLElement(Tree):
    """
    Parent class of all xml elements.
    """
    _PROPERTIES = {'xsd_tree', 'compact_repr', 'is_leaf', 'level', 'attributes', 'child_container_tree', 'possible_children_names',
                  'et_xml_element', 'name', 'type_', 'value_', 'parent_xsd_element'}
    TYPE = None
    _SEARCH_FOR_ELEMENT = ''

    def __init__(self, value_=None, **kwargs):
        self.xsd_tree = XSDTree(musicxml_xsd_et_root.find(self._SEARCH_FOR_ELEMENT))
        self._type = None
        super().__init__()
        self._value_ = None
        self._attributes = {}
        self._et_xml_element = None
        self._child_container_tree = None
        self._unordered_children = []
        self.value_ = value_
        self._set_attributes(kwargs)

        self._create_child_container_tree()

    def _check_attribute(self, name, value):
        attributes = self.TYPE.get_xsd_attributes()
        allowed_attributes = [attribute.name for attribute in attributes]
        if name not in [attribute.name for attribute in self.TYPE.get_xsd_attributes()]:
            raise XSDWrongAttribute(f"{self.__class__.__name__} has no attribute {name}. Allowed attributes are: {allowed_attributes}")
        for attribute in attributes:
            if attribute.name == name:
                return attribute(value)

    def _check_child_to_be_added(self, child):
        if not isinstance(child, XMLElement):
            raise TypeError

    def _check_required_attributes(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            required_attributes = [attribute for attribute in self.TYPE.get_xsd_attributes() if attribute.is_required]
            for required_attribute in required_attributes:
                if required_attribute.name not in self.attributes:
                    raise XSDAttributeRequiredException(f"{self.__class__.__name__} requires attribute: {required_attribute.name}")

    def _check_required_value(self):
        if self.TYPE.XSD_TREE.is_simple_type and self.value_ is None:
            raise ValueError(f"{self.__class__.__name__} needs a value.")

    def _convert_attribute_to_child(self, name, value):
        if not name.startswith('xml_'):
            raise NameError
        child_name = name.replace('xml_', '')

        if '-'.join(child_name.split('_')) not in self.possible_children_names:
            raise NameError

        child_class_name = 'XML' + ''.join([cap_first(partial) for partial in child_name.split('_')])
        child_class = eval(child_class_name)

        found_child = self.find_child(child_class_name)
        if isinstance(value, child_class):
            if found_child:
                self.replace_child(found_child, value)
            else:
                self.add_child(value)
        elif value is None:
            if found_child:
                self.remove(found_child)
        else:
            if found_child:
                found_child.value_ = value
            else:
                self.add_child(child_class(value))

    def _create_child_container_tree(self):
        try:
            if self.TYPE.XSD_TREE.is_complex_type:
                self._child_container_tree = copy.copy(containers[self.TYPE.__name__])
                self._child_container_tree._parent_xml_element = self
        except KeyError:
            pass

    def _create_et_xml_element(self):
        self._et_xml_element = ET.Element(self.name, {k: str(v) for k, v in self.attributes.items()})
        if self.value_ is not None:
            self._et_xml_element.text = str(self.value_)
        for child in self.get_children():
            self._et_xml_element.append(child.et_xml_element)
        ET.indent(self._et_xml_element, space="  ", level=self.level)

    def _final_checks(self, intelligent_choice=False):
        self._check_required_value()
        if self._child_container_tree:
            required_children = self._child_container_tree.get_required_element_names(intelligent_choice=intelligent_choice)
            if required_children:
                raise XMLElementChildrenRequired(f"{self.__class__.__name__} requires at least following children: {required_children}")

        self._check_required_attributes()

        for child in self.get_children():
            child._final_checks(intelligent_choice=intelligent_choice)

    def _get_attributes_error_message(self, wrong_name):
        attributes = self.TYPE.get_xsd_attributes()
        allowed_attributes = [attribute.name for attribute in attributes]
        return f"{self.__class__.__name__} has no attribute {wrong_name}. Allowed attributes are: " \
               f"{sorted(allowed_attributes)} or possible " \
               f"children as attributes: {sorted(['xml_' + '_'.join(ch.split('-')) for ch in self.possible_children_names])}"

    def _set_attributes(self, val):
        if val is None:
            return

        if self.TYPE.XSD_TREE.is_simple_type:
            if val:
                raise XSDWrongAttribute(f'{self.__class__.__name__} has no attributes.')

        elif not isinstance(val, dict):
            raise TypeError

        new_attributes = replace_key_underline_with_hyphen(dict_=val)
        none_values_dict = {k: v for k, v in new_attributes.items() if v is None}
        for key in none_values_dict:
            new_attributes.pop(key)
            try:
                self.attributes.pop(key)
            except KeyError:
                pass
        for key in new_attributes:
            self._check_attribute(key, new_attributes[key])
        self._attributes = {**self._attributes, **new_attributes}

    @property
    def attributes(self):
        """
        :return: a dictionary of attributes like {'font-family': 'Arial'}

        >>> t = XMLText(value_='hello', font_family = 'Arial')
        >>> t.attributes
        {'font-family': 'Arial'}
        >>> t.to_string()
        <text font-family="Arial">hello</text>
        """

        return self._attributes

    @property
    def child_container_tree(self):
        """
        :return: A ChildContainerTree object which is used to manage and control XMLElements children. The nodes of a ChildContainerTree
                 have a core content property of types XSDSequence, XSDChoice, XSDGroup or XSDElement. XSDElement are the content type of
                 ChildContainerTree leaves where one or more XMLElements of a single type (depending on maxOccur attribute of element)
                 can be added to its xml_elements list. An interaction of xsd indicators (sequence, choice and group) with xsd elements
                 makes it possible to add XMLElement's Children in the right order and control all xsd rules which apply to musicxml. A
                 variety of exceptions help user to control the xml structure of the exported file which they are intending to use as a
                 musicxml format file.
        """
        return self._child_container_tree

    @property
    def et_xml_element(self):
        """
        :return:  A xml.etree.ElementTree.Element which is used to write the musicxml file.
        """
        self._create_et_xml_element()
        return self._et_xml_element

    @property
    def name(self):
        return self.xsd_tree.get_attributes()['name']

    @property
    def possible_children_names(self):
        if not self.child_container_tree:
            return {}
        else:
            return {leaf.content.name for leaf in self.child_container_tree.iterate_leaves()}

    @property
    def value_(self):
        """
        :return: A validated value of XMLElement which will be translated to its text in xml format.
        """
        return self._value

    @value_.setter
    def value_(self, val):
        """
        :param val: Value to be validated and added to XMLElement. This value will be translated to xml element's text in xml format.
        """
        self.TYPE(val, parent=self)
        self._value = val

    @classmethod
    def get_xsd(cls):
        """
        :return: Snippet of musicxml xsd file which is relevant for this XMLElement.
        """
        return cls.xsd_tree.get_xsd()

    def add_child(self, child: 'XMLElement', forward: Optional[int] = None) -> 'XMLElement':
        """
        :param XMLElement child: XMLElement child to be added to XMLElement's ChildContainerTree and _unordered_children.
        :param int forward: If there are more than one XSDElement leaves in self.child_container_tree, forward can be used to determine
                            manually which of these equivocal xsd elements is going to be used to attach the child.
        :return: Added child.
        """
        if not self._child_container_tree:
            raise XMLElementCannotHaveChildrenError()
        self._child_container_tree.add_element(child, forward)
        self._unordered_children.append(child)
        child._parent = self
        return child

    def get_children(self, ordered: bool = True) -> List['XMLElement']:
        """
        :param bool ordered: True or False.
        :return: XMLElement added children. If ordered is False the _unordered_children is returned as a more light weighted way of
                 getting children instead of using the leaves of ChildContainerTree.
        """
        if ordered is False:
            return self._unordered_children
        if self._child_container_tree:
            return [xml_element for leaf in self._child_container_tree.iterate_leaves() for xml_element in leaf.content.xml_elements if
                    leaf.content.xml_elements]
        else:
            return []

    def find_child(self, name: Union['XMLElement', str], ordered: bool = False) -> 'XMLElement':
        """
        :param XMLElement/String name: Child or it's name as string.
        :param bool ordered: get_children mode to be used to find first appearance of child.
        :return: found child.
        """
        if isinstance(name, type):
            name = name.__name__
        for ch in self.get_children(ordered=ordered):
            if ch.__class__.__name__ == name:
                return ch

    def find_children(self, name: Union['XMLElement', str], ordered: bool = False) -> List['XMLElement']:
        """
        :param XMLElement/String name: Child or it's name as string.
        :param bool ordered: get_children mode to be used to find children.
        :return: found children.
        """
        if isinstance(name, type):
            name = name.__name__
        return [ch for ch in self.get_children(ordered=ordered) if ch.__class__.__name__ == name]

    def remove(self, child: 'XMLElement') -> None:
        """
        :param XMLElement child: child to be removed. This method must be used to remove a child properly from ChildContainerTree and
                                 reset its behaviour.
        :return: None
        """

        def remove_duplictation():
            for node in parent_container.reversed_path_to_root():
                if node.up:
                    if isinstance(node.up.content, DuplicationXSDSequence) and len(node.up.get_children()) > 1:
                        remove_duplicate = False
                        for leaf in node.iterate_leaves():
                            if leaf != parent_container and leaf.content.xml_elements:
                                break
                            remove_duplicate = True
                        if remove_duplicate:
                            node.up.remove(node)

        self._unordered_children.remove(child)

        parent_container = child.parent_xsd_element.parent_container.get_parent()
        if parent_container.chosen_child == child.parent_xsd_element.parent_container:
            parent_container.chosen_child = None
            parent_container.requirements_not_fulfilled = True

        child.parent_xsd_element.xml_elements.remove(child)
        child.parent_xsd_element = None
        child._parent = None
        del child
        remove_duplictation()

    def replace_child(self, old: Union['XMLElement', Callable], new: 'XMLElement', index: int = 0) -> None:
        """
        :param XMLElement or function old: A child or function which is used to find a child to be replaced.
        :param XMLElement new: child to be replaced with.
        :param int index: index of old in list of old appearances
        :return: None
        """
        if hasattr(old, '__call__'):
            list_of_olds = [ch for ch in self.get_children(ordered=True) if old(ch)]
        else:
            list_of_olds = [ch for ch in self.get_children(ordered=True) if ch == old]

        if not list_of_olds:
            raise ValueError(f"{old} not in list.")
        self._check_child_to_be_added(new)
        old_index = self._unordered_children.index(list_of_olds[index])
        old_child = self._unordered_children[old_index]
        self._unordered_children.remove(old_child)
        self._unordered_children.insert(old_index, new)

        parent_xsd_element = old_child.parent_xsd_element
        new.parent_xsd_element = parent_xsd_element
        parent_xsd_element._xml_elements = [new if el == old_child else el for el in parent_xsd_element.xml_elements]
        new._parent = self
        old._parent = None

    def to_string(self, intelligent_choice: bool = False) -> str:
        """
        :param bool intelligent_choice: Set to True if you wish to use intelligent choice in final checks to be able to change the
                                         attachment order of XMLElement children in self.child_container_tree if an Exception was thrown
                                         and other choices can still be checked. (No GUARANTEE!)
        :return: String in xml format.
        """
        self._final_checks(intelligent_choice=intelligent_choice)
        self._create_et_xml_element()

        return ET.tostring(self.et_xml_element, encoding='unicode') + '\n'

    def __setattr__(self, key, value):
        if key[0] == '_' or key in self._PROPERTIES:
            super().__setattr__(key, value)
        elif key.startswith('xml_'):
            try:
                self._convert_attribute_to_child(name=key, value=value)
            except NameError:
                raise AttributeError(self._get_attributes_error_message(key))
        else:
            try:
                self._set_attributes({key: value})
            except XSDWrongAttribute:
                raise AttributeError(self._get_attributes_error_message(key))

    def __getattr__(self, item):
        try:
            return self.attributes['-'.join(item.split('_'))]
        except KeyError:
            attributes = self.TYPE.get_xsd_attributes()
            allowed_attributes = ['_'.join(attribute.name.split('-')) for attribute in attributes]
            if item in allowed_attributes:
                return None
            else:
                if item.startswith('xml'):
                    child_name = item.replace('xml_', '')
                    for child in self.get_children(ordered=False):
                        if child.name == '-'.join(child_name.split('_')):
                            return child
                    if '-'.join(child_name.split('_')) in self.possible_children_names:
                        return None
                raise AttributeError(self._get_attributes_error_message(item))


class XMLScorePartwise(XMLElement):
    """
    The score-partwise element is the root element for a partwise MusicXML score. It includes a score-header group followed by a series of parts with measures inside. The document-attributes attribute group includes the version attribute.
"""
    TYPE = XSDComplexTypeScorePartwise
    _SEARCH_FOR_ELEMENT = f".//{ns}element[@name='score-partwise']"

    def write(self, path, intelligent_choice=False):
        with open(path, 'w') as file:
            file.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
            file.write(self.to_string(intelligent_choice=intelligent_choice))


class XMLPart(XMLElement):
    TYPE = XSDComplexTypePart
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='score-partwise']//{*}element[@name='part']"


class XMLMeasure(XMLElement):
    TYPE = XSDComplexTypeMeasure
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='score-partwise']//{*}element[@name='measure']"


class XMLDirective(XMLElement):
    TYPE = XSDComplexTypeDirective
    _SEARCH_FOR_ELEMENT = ".//{*}complexType[@name='attributes']//{*}element[@name='directive']"

# -----------------------------------------------------
# AUTOMATICALLY GENERATED WITH generate_xml_elements.py
# -----------------------------------------------------


class XMLP(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='p'][@type='empty']"


class XMLPp(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='pp'][@type='empty']"


class XMLPpp(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='ppp'][@type='empty']"


class XMLPppp(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='pppp'][@type='empty']"


class XMLPpppp(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='ppppp'][@type='empty']"


class XMLPppppp(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='pppppp'][@type='empty']"


class XMLF(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='f'][@type='empty']"


class XMLFf(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='ff'][@type='empty']"


class XMLFff(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='fff'][@type='empty']"


class XMLFfff(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='ffff'][@type='empty']"


class XMLFffff(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='fffff'][@type='empty']"


class XMLFfffff(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='ffffff'][@type='empty']"


class XMLMp(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='mp'][@type='empty']"


class XMLMf(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='mf'][@type='empty']"


class XMLSf(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='sf'][@type='empty']"


class XMLSfp(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='sfp'][@type='empty']"


class XMLSfpp(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='sfpp'][@type='empty']"


class XMLFp(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='fp'][@type='empty']"


class XMLRf(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='rf'][@type='empty']"


class XMLRfz(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='rfz'][@type='empty']"


class XMLSfz(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='sfz'][@type='empty']"


class XMLSffz(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='sffz'][@type='empty']"


class XMLFz(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='fz'][@type='empty']"


class XMLN(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='n'][@type='empty']"


class XMLPf(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='pf'][@type='empty']"


class XMLSfzp(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='sfzp'][@type='empty']"


class XMLOtherDynamics(XMLElement):
    """
    ``complexType``: The other-text type represents a text element with a smufl attribute group. This type is used by MusicXML direction extension elements to allow specification of specific SMuFL glyphs without needed to add every glyph as a MusicXML element.
    """
    
    TYPE = XSDComplexTypeOtherText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='other-dynamics'][@type='other-text']"


class XMLMidiChannel(XMLElement):
    """
    The midi-channel element specifies a MIDI 1.0 channel numbers ranging from 1 to 16.
    
    ``simpleType``: The midi-16 type is used to express MIDI 1.0 values that range from 1 to 16.
    """
    
    TYPE = XSDSimpleTypeMidi16
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='midi-channel'][@type='midi-16']"


class XMLMidiName(XMLElement):
    """
    The midi-name element corresponds to a ProgramName meta-event within a Standard MIDI File.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='midi-name'][@type='xs:string']"


class XMLMidiBank(XMLElement):
    """
    The midi-bank element specifies a MIDI 1.0 bank number ranging from 1 to 16,384.
    
    ``simpleType``: The midi-16384 type is used to express MIDI 1.0 values that range from 1 to 16,384.
    """
    
    TYPE = XSDSimpleTypeMidi16384
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='midi-bank'][@type='midi-16384']"


class XMLMidiProgram(XMLElement):
    """
    The midi-program element specifies a MIDI 1.0 program number ranging from 1 to 128.
    
    ``simpleType``: The midi-128 type is used to express MIDI 1.0 values that range from 1 to 128.
    """
    
    TYPE = XSDSimpleTypeMidi128
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='midi-program'][@type='midi-128']"


class XMLMidiUnpitched(XMLElement):
    """
    For unpitched instruments, the midi-unpitched element specifies a MIDI 1.0 note number ranging from 1 to 128. It is usually used with MIDI banks for percussion. Note that MIDI 1.0 note numbers are generally specified from 0 to 127 rather than the 1 to 128 numbering used in this element.
    
    ``simpleType``: The midi-128 type is used to express MIDI 1.0 values that range from 1 to 128.
    """
    
    TYPE = XSDSimpleTypeMidi128
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='midi-unpitched'][@type='midi-128']"


class XMLVolume(XMLElement):
    """
    The volume element value is a percentage of the maximum ranging from 0 to 100, with decimal values allowed. This corresponds to a scaling value for the MIDI 1.0 channel volume controller.
    
    ``simpleType``: The percent type specifies a percentage from 0 to 100.
    """
    
    TYPE = XSDSimpleTypePercent
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='volume'][@type='percent']"


class XMLPan(XMLElement):
    """
    The pan and elevation elements allow placing of sound in a 3-D space relative to the listener. Both are expressed in degrees ranging from -180 to 180. For pan, 0 is straight ahead, -90 is hard left, 90 is hard right, and -180 and 180 are directly behind the listener.
    
    ``simpleType``: The rotation-degrees type specifies rotation, pan, and elevation values in degrees. Values range from -180 to 180.
    """
    
    TYPE = XSDSimpleTypeRotationDegrees
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='pan'][@type='rotation-degrees']"


class XMLElevation(XMLElement):
    """
    The elevation and pan elements allow placing of sound in a 3-D space relative to the listener. Both are expressed in degrees ranging from -180 to 180. For elevation, 0 is level with the listener, 90 is directly above, and -90 is directly below.
    
    ``simpleType``: The rotation-degrees type specifies rotation, pan, and elevation values in degrees. Values range from -180 to 180.
    """
    
    TYPE = XSDSimpleTypeRotationDegrees
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='elevation'][@type='rotation-degrees']"


class XMLDisplayText(XMLElement):
    """
    ``complexType``: The formatted-text type represents a text element with text-formatting attributes.
    """
    
    TYPE = XSDComplexTypeFormattedText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='display-text'][@type='formatted-text']"


class XMLAccidentalText(XMLElement):
    """
    ``complexType``: The accidental-text type represents an element with an accidental value and text-formatting attributes.
    
    ``simpleContent``: The accidental-value type represents notated accidentals supported by MusicXML. In the MusicXML 2.0 DTD this was a string with values that could be included. The XSD strengthens the data typing to an enumerated list. The quarter- and three-quarters- accidentals are Tartini-style quarter-tone accidentals. The -down and -up accidentals are quarter-tone accidentals that include arrows pointing down or up. The slash- accidentals are used in Turkish classical music. The numbered sharp and flat accidentals are superscripted versions of the accidental signs, used in Turkish folk music. The sori and koron accidentals are microtonal sharp and flat accidentals used in Iranian and Persian music. The other accidental covers accidentals other than those listed here. It is usually used in combination with the smufl attribute to specify a particular SMuFL accidental. The smufl attribute may be used with any accidental value to help specify the appearance of symbols that share the same MusicXML semantics.
        
        Permitted Values: ['sharp', 'natural', 'flat', 'double-sharp', 'sharp-sharp', 'flat-flat', 'natural-sharp', 'natural-flat', 'quarter-flat', 'quarter-sharp', 'three-quarters-flat', 'three-quarters-sharp', 'sharp-down', 'sharp-up', 'natural-down', 'natural-up', 'flat-down', 'flat-up', 'double-sharp-down', 'double-sharp-up', 'flat-flat-down', 'flat-flat-up', 'arrow-down', 'arrow-up', 'triple-sharp', 'triple-flat', 'slash-quarter-sharp', 'slash-sharp', 'slash-flat', 'double-slash-flat', 'sharp-1', 'sharp-2', 'sharp-3', 'sharp-5', 'flat-1', 'flat-2', 'flat-3', 'flat-4', 'sori', 'koron', 'other']
    
    """
    
    TYPE = XSDComplexTypeAccidentalText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='accidental-text'][@type='accidental-text']"


class XMLIpa(XMLElement):
    """
    The ipa element represents International Phonetic Alphabet (IPA) sounds for vocal music. String content is limited to IPA 2015 symbols represented in Unicode 13.0.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='ipa'][@type='xs:string']"


class XMLMute(XMLElement):
    """
    ``simpleType``: The mute type represents muting for different instruments, including brass, winds, and strings. The on and off values are used for undifferentiated mutes. The remaining values represent specific mutes.
        
        Permitted Values: ['on', 'off', 'straight', 'cup', 'harmon-no-stem', 'harmon-stem', 'bucket', 'plunger', 'hat', 'solotone', 'practice', 'stop-mute', 'stop-hand', 'echo', 'palm']
    
    """
    
    TYPE = XSDSimpleTypeMute
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='mute'][@type='mute']"


class XMLSemiPitched(XMLElement):
    """
    ``simpleType``: The semi-pitched type represents categories of indefinite pitch for percussion instruments.
        
        Permitted Values: ['high', 'medium-high', 'medium', 'medium-low', 'low', 'very-low']
    
    """
    
    TYPE = XSDSimpleTypeSemiPitched
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='semi-pitched'][@type='semi-pitched']"


class XMLOtherPlay(XMLElement):
    """
    ``complexType``: The other-play element represents other types of playback. The required type attribute indicates the type of playback to which the element content applies.
    """
    
    TYPE = XSDComplexTypeOtherPlay
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='other-play'][@type='other-play']"


class XMLDivisions(XMLElement):
    """
    Musical notation duration is commonly represented as fractions. The divisions element indicates how many divisions per quarter note are used to indicate a note's duration. For example, if duration = 1 and divisions = 2, this is an eighth note duration. Duration and divisions are used directly for generating sound output, so they must be chosen to take tuplets into account. Using a divisions element lets us use just one number to represent a duration for each note in the score, while retaining the full power of a fractional representation. If maximum compatibility with Standard MIDI 1.0 files is important, do not have the divisions value exceed 16383.
    
    ``simpleType``: The positive-divisions type restricts divisions values to positive numbers.
    """
    
    TYPE = XSDSimpleTypePositiveDivisions
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='divisions'][@type='positive-divisions']"


class XMLKey(XMLElement):
    """
    The key element represents a key signature. Both traditional and non-traditional key signatures are supported. The optional number attribute refers to staff numbers. If absent, the key signature applies to all staves in the part.
    
    ``complexType``: The key type represents a key signature. Both traditional and non-traditional key signatures are supported. The optional number attribute refers to staff numbers. If absent, the key signature applies to all staves in the part. Key signatures appear at the start of each system unless the print-object attribute has been set to "no".

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Choice@minOccurs=1@maxOccurs=1
               Group@name=traditional-key@minOccurs=1@maxOccurs=1
                   Sequence@minOccurs=1@maxOccurs=1
                       Element@name=cancel@minOccurs=0@maxOccurs=1
                       Element@name=fifths@minOccurs=1@maxOccurs=1
                       Element@name=mode@minOccurs=0@maxOccurs=1
               Group@name=non-traditional-key@minOccurs=0@maxOccurs=unbounded
                   Sequence@minOccurs=1@maxOccurs=1
                       Element@name=key-step@minOccurs=1@maxOccurs=1
                       Element@name=key-alter@minOccurs=1@maxOccurs=1
                       Element@name=key-accidental@minOccurs=0@maxOccurs=1
           Element@name=key-octave@minOccurs=0@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypeKey
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='key'][@type='key']"


class XMLTime(XMLElement):
    """
    Time signatures are represented by the beats element for the numerator and the beat-type element for the denominator.
    
    ``complexType``: Time signatures are represented by the beats element for the numerator and the beat-type element for the denominator. The symbol attribute is used to indicate common and cut time symbols as well as a single number display. Multiple pairs of beat and beat-type elements are used for composite time signatures with multiple denominators, such as 2/4 + 3/8. A composite such as 3+2/8 requires only one beat/beat-type pair.
    
    The print-object attribute allows a time signature to be specified but not printed, as is the case for excerpts from the middle of a score. The value is "yes" if not present. The optional number attribute refers to staff numbers within the part. If absent, the time signature applies to all staves in the part.

    ``XSD structure:``

    .. code-block::

       Choice@minOccurs=1@maxOccurs=1
           Sequence@minOccurs=1@maxOccurs=1
               Group@name=time-signature@minOccurs=1@maxOccurs=unbounded
                   Sequence@minOccurs=1@maxOccurs=1
                       Element@name=beats@minOccurs=1@maxOccurs=1
                       Element@name=beat-type@minOccurs=1@maxOccurs=1
               Element@name=interchangeable@minOccurs=0@maxOccurs=1
           Element@name=senza-misura@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeTime
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='time'][@type='time']"


class XMLStaves(XMLElement):
    """
    The staves element is used if there is more than one staff represented in the given part (e.g., 2 staves for typical piano parts). If absent, a value of 1 is assumed. Staves are ordered from top to bottom in a part in numerical order, with staff 1 above staff 2.
    """
    
    TYPE = XSDSimpleTypeNonNegativeInteger
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='staves'][@type='xs:nonNegativeInteger']"


class XMLPartSymbol(XMLElement):
    """
    The part-symbol element indicates how a symbol for a multi-staff part is indicated in the score.
    
    ``complexType``: The part-symbol type indicates how a symbol for a multi-staff part is indicated in the score; brace is the default value. The top-staff and bottom-staff attributes are used when the brace does not extend across the entire part. For example, in a 3-staff organ part, the top-staff will typically be 1 for the right hand, while the bottom-staff will typically be 2 for the left hand. Staff 3 for the pedals is usually outside the brace. By default, the presence of a part-symbol element that does not extend across the entire part also indicates a corresponding change in the common barlines within a part.
    
    ``simpleContent``: The group-symbol-value type indicates how the symbol for a group or multi-staff part is indicated in the score.
        
        Permitted Values: ['none', 'brace', 'line', 'bracket', 'square']
    
    """
    
    TYPE = XSDComplexTypePartSymbol
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='part-symbol'][@type='part-symbol']"


class XMLInstruments(XMLElement):
    """
    The instruments element is only used if more than one instrument is represented in the part (e.g., oboe I and II where they play together most of the time). If absent, a value of 1 is assumed.
    """
    
    TYPE = XSDSimpleTypeNonNegativeInteger
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='instruments'][@type='xs:nonNegativeInteger']"


class XMLClef(XMLElement):
    """
    Clefs are represented by a combination of sign, line, and clef-octave-change elements.
    
    ``complexType``: Clefs are represented by a combination of sign, line, and clef-octave-change elements. The optional number attribute refers to staff numbers within the part. A value of 1 is assumed if not present.
    
    Sometimes clefs are added to the staff in non-standard line positions, either to indicate cue passages, or when there are multiple clefs present simultaneously on one staff. In this situation, the additional attribute is set to "yes" and the line value is ignored. The size attribute is used for clefs where the additional attribute is "yes". It is typically used to indicate cue clefs.
    
    Sometimes clefs at the start of a measure need to appear after the barline rather than before, as for cues or for use after a repeated section. The after-barline attribute is set to "yes" in this situation. The attribute is ignored for mid-measure clefs.
    
    Clefs appear at the start of each system unless the print-object attribute has been set to "no" or the additional attribute has been set to "yes".

    ``XSD structure:``

    .. code-block::

       Group@name=clef@minOccurs=1@maxOccurs=1
           Sequence@minOccurs=1@maxOccurs=1
               Element@name=sign@minOccurs=1@maxOccurs=1
               Element@name=line@minOccurs=0@maxOccurs=1
               Element@name=clef-octave-change@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeClef
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='clef'][@type='clef']"


class XMLStaffDetails(XMLElement):
    """
    The staff-details element is used to indicate different types of staves.
    
    ``complexType``: The staff-details element is used to indicate different types of staves. The optional number attribute specifies the staff number from top to bottom on the system, as with clef. The print-object attribute is used to indicate when a staff is not printed in a part, usually in large scores where empty parts are omitted. It is yes by default. If print-spacing is yes while print-object is no, the score is printed in cutaway format where vertical space is left for the empty part.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=staff-type@minOccurs=0@maxOccurs=1
           Sequence@minOccurs=0@maxOccurs=1
               Element@name=staff-lines@minOccurs=1@maxOccurs=1
               Element@name=line-detail@minOccurs=0@maxOccurs=unbounded
           Element@name=staff-tuning@minOccurs=0@maxOccurs=unbounded
           Element@name=capo@minOccurs=0@maxOccurs=1
           Element@name=staff-size@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeStaffDetails
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='staff-details'][@type='staff-details']"


class XMLTranspose(XMLElement):
    """
    If the part is being encoded for a transposing instrument in written vs. concert pitch, the transposition must be encoded in the transpose element using the transpose type.
    
    ``complexType``: The transpose type represents what must be added to a written pitch to get a correct sounding pitch. The optional number attribute refers to staff numbers, from top to bottom on the system. If absent, the transposition applies to all staves in the part. Per-staff transposition is most often used in parts that represent multiple instruments.

    ``XSD structure:``

    .. code-block::

       Group@name=transpose@minOccurs=1@maxOccurs=1
           Sequence@minOccurs=1@maxOccurs=1
               Element@name=diatonic@minOccurs=0@maxOccurs=1
               Element@name=chromatic@minOccurs=1@maxOccurs=1
               Element@name=octave-change@minOccurs=0@maxOccurs=1
               Element@name=double@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeTranspose
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='transpose'][@type='transpose']"


class XMLForPart(XMLElement):
    """
    The for-part element is used in a concert score to indicate the transposition for a transposed part created from that score. It is only used in score files that contain a concert-score element in the defaults. This allows concert scores with transposed parts to be represented in a single uncompressed MusicXML file.
    
    ``complexType``: The for-part type is used in a concert score to indicate the transposition for a transposed part created from that score. It is only used in score files that contain a concert-score element in the defaults. This allows concert scores with transposed parts to be represented in a single uncompressed MusicXML file.
    
    The optional number attribute refers to staff numbers, from top to bottom on the system. If absent, the child elements apply to all staves in the created part.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=part-clef@minOccurs=0@maxOccurs=1
           Element@name=part-transpose@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeForPart
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='for-part'][@type='for-part']"


class XMLMeasureStyle(XMLElement):
    """
    A measure-style indicates a special way to print partial to multiple measures within a part. This includes multiple rests over several measures, repeats of beats, single, or multiple measures, and use of slash notation.
    
    ``complexType``: A measure-style indicates a special way to print partial to multiple measures within a part. This includes multiple rests over several measures, repeats of beats, single, or multiple measures, and use of slash notation.
    
    The multiple-rest and measure-repeat elements indicate the number of measures covered in the element content. The beat-repeat and slash elements can cover partial measures. All but the multiple-rest element use a type attribute to indicate starting and stopping the use of the style. The optional number attribute specifies the staff number from top to bottom on the system, as with clef.

    ``XSD structure:``

    .. code-block::

       Choice@minOccurs=1@maxOccurs=1
           Element@name=multiple-rest@minOccurs=1@maxOccurs=1
           Element@name=measure-repeat@minOccurs=1@maxOccurs=1
           Element@name=beat-repeat@minOccurs=1@maxOccurs=1
           Element@name=slash@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeMeasureStyle
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='measure-style'][@type='measure-style']"


class XMLPartClef(XMLElement):
    """
    The part-clef element is used for transpositions that also include a change of clef, as for instruments such as bass clarinet.
    
    ``complexType``: The child elements of the part-clef type have the same meaning as for the clef type. However that meaning applies to a transposed part created from the existing score file.

    ``XSD structure:``

    .. code-block::

       Group@name=clef@minOccurs=1@maxOccurs=1
           Sequence@minOccurs=1@maxOccurs=1
               Element@name=sign@minOccurs=1@maxOccurs=1
               Element@name=line@minOccurs=0@maxOccurs=1
               Element@name=clef-octave-change@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypePartClef
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='part-clef'][@type='part-clef']"


class XMLPartTranspose(XMLElement):
    """
    The chromatic element in a part-transpose element will usually have a non-zero value, since octave transpositions can be represented in concert scores using the transpose element.
    
    ``complexType``: The child elements of the part-transpose type have the same meaning as for the transpose type. However that meaning applies to a transposed part created from the existing score file.

    ``XSD structure:``

    .. code-block::

       Group@name=transpose@minOccurs=1@maxOccurs=1
           Sequence@minOccurs=1@maxOccurs=1
               Element@name=diatonic@minOccurs=0@maxOccurs=1
               Element@name=chromatic@minOccurs=1@maxOccurs=1
               Element@name=octave-change@minOccurs=0@maxOccurs=1
               Element@name=double@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypePartTranspose
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='part-transpose'][@type='part-transpose']"


class XMLTimeRelation(XMLElement):
    """
    ``simpleType``: The time-relation type indicates the symbol used to represent the interchangeable aspect of dual time signatures.
        
        Permitted Values: ['parentheses', 'bracket', 'equals', 'slash', 'space', 'hyphen']
    
    """
    
    TYPE = XSDSimpleTypeTimeRelation
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='time-relation'][@type='time-relation']"


class XMLKeyOctave(XMLElement):
    """
    The optional list of key-octave elements is used to specify in which octave each element of the key signature appears.
    
    ``complexType``: The key-octave type specifies in which octave an element of a key signature appears. The content specifies the octave value using the same values as the display-octave element. The number attribute is a positive integer that refers to the key signature element in left-to-right order. If the cancel attribute is set to yes, then this number refers to the canceling key signature specified by the cancel element in the parent key element. The cancel attribute cannot be set to yes if there is no corresponding cancel element within the parent key element. It is no by default.
    
    ``simpleContent``: Octaves are represented by the numbers 0 to 9, where 4 indicates the octave started by middle C.
    """
    
    TYPE = XSDComplexTypeKeyOctave
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='key-octave'][@type='key-octave']"


class XMLMultipleRest(XMLElement):
    """
    ``complexType``: The text of the multiple-rest type indicates the number of measures in the multiple rest. Multiple rests may use the 1-bar / 2-bar / 4-bar rest symbols, or a single shape. The use-symbols attribute indicates which to use; it is no if not specified.
    """
    
    TYPE = XSDComplexTypeMultipleRest
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='multiple-rest'][@type='multiple-rest']"


class XMLMeasureRepeat(XMLElement):
    """
    ``complexType``: The measure-repeat type is used for both single and multiple measure repeats. The text of the element indicates the number of measures to be repeated in a single pattern. The slashes attribute specifies the number of slashes to use in the repeat sign. It is 1 if not specified. The text of the element is ignored when the type is stop.
    
    The stop type indicates the first measure where the repeats are no longer displayed. Both the start and the stop of the measure-repeat should be specified unless the repeats are displayed through the end of the part.
    
    The measure-repeat element specifies a notation style for repetitions. The actual music being repeated needs to be repeated within each measure of the MusicXML file. This element specifies the notation that indicates the repeat.
    
    ``simpleContent``: The positive-integer-or-empty values can be either a positive integer or an empty string.
    """
    
    TYPE = XSDComplexTypeMeasureRepeat
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='measure-repeat'][@type='measure-repeat']"


class XMLBeatRepeat(XMLElement):
    """
    ``complexType``: The beat-repeat type is used to indicate that a single beat (but possibly many notes) is repeated. The slashes attribute specifies the number of slashes to use in the symbol. The use-dots attribute indicates whether or not to use dots as well (for instance, with mixed rhythm patterns). The value for slashes is 1 and the value for use-dots is no if not specified.
    
    The stop type indicates the first beat where the repeats are no longer displayed. Both the start and stop of the beat being repeated should be specified unless the repeats are displayed through the end of the part.
    
    The beat-repeat element specifies a notation style for repetitions. The actual music being repeated needs to be repeated within the MusicXML file. This element specifies the notation that indicates the repeat.

    ``XSD structure:``

    .. code-block::

       Group@name=slash@minOccurs=0@maxOccurs=1
           Sequence@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=0@maxOccurs=1
                   Element@name=slash-type@minOccurs=1@maxOccurs=1
                   Element@name=slash-dot@minOccurs=0@maxOccurs=unbounded
               Element@name=except-voice@minOccurs=0@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypeBeatRepeat
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='beat-repeat'][@type='beat-repeat']"


class XMLSlash(XMLElement):
    """
    ``complexType``: The slash type is used to indicate that slash notation is to be used. If the slash is on every beat, use-stems is no (the default). To indicate rhythms but not pitches, use-stems is set to yes. The type attribute indicates whether this is the start or stop of a slash notation style. The use-dots attribute works as for the beat-repeat element, and only has effect if use-stems is no.

    ``XSD structure:``

    .. code-block::

       Group@name=slash@minOccurs=0@maxOccurs=1
           Sequence@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=0@maxOccurs=1
                   Element@name=slash-type@minOccurs=1@maxOccurs=1
                   Element@name=slash-dot@minOccurs=0@maxOccurs=unbounded
               Element@name=except-voice@minOccurs=0@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypeSlash
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='slash'][@type='slash']"


class XMLStaffType(XMLElement):
    """
    ``simpleType``: The staff-type value can be ossia, editorial, cue, alternate, or regular. An ossia staff represents music that can be played instead of what appears on the regular staff. An editorial staff also represents musical alternatives, but is created by an editor rather than the composer. It can be used for suggested interpretations or alternatives from other sources. A cue staff represents music from another part. An alternate staff shares the same music as the prior staff, but displayed differently (e.g., treble and bass clef, standard notation and tablature). It is not included in playback. An alternate staff provides more information to an application reading a file than encoding the same music in separate parts, so its use is preferred in this situation if feasible. A regular staff is the standard default staff-type.
        
        Permitted Values: ['ossia', 'editorial', 'cue', 'alternate', 'regular']
    
    """
    
    TYPE = XSDSimpleTypeStaffType
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='staff-type'][@type='staff-type']"


class XMLStaffLines(XMLElement):
    """
    The staff-lines element specifies the number of lines and is usually used for a non 5-line staff. If the staff-lines element is present, the appearance of each line may be individually specified with a line-detail element.
    """
    
    TYPE = XSDSimpleTypeNonNegativeInteger
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='staff-lines'][@type='xs:nonNegativeInteger']"


class XMLLineDetail(XMLElement):
    """
    ``complexType``: If the staff-lines element is present, the appearance of each line may be individually specified with a line-detail type. Staff lines are numbered from bottom to top. The print-object attribute allows lines to be hidden within a staff. This is used in special situations such as a widely-spaced percussion staff where a note placed below the higher line is distinct from a note placed above the lower line. Hidden staff lines are included when specifying clef lines and determining display-step / display-octave values, but are not counted as lines for the purposes of the system-layout and staff-layout elements.
    """
    
    TYPE = XSDComplexTypeLineDetail
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='line-detail'][@type='line-detail']"


class XMLStaffTuning(XMLElement):
    """
    ``complexType``: The staff-tuning type specifies the open, non-capo tuning of the lines on a tablature staff.

    ``XSD structure:``

    .. code-block::

       Group@name=tuning@minOccurs=1@maxOccurs=1
           Sequence@minOccurs=1@maxOccurs=1
               Element@name=tuning-step@minOccurs=1@maxOccurs=1
               Element@name=tuning-alter@minOccurs=0@maxOccurs=1
               Element@name=tuning-octave@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeStaffTuning
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='staff-tuning'][@type='staff-tuning']"


class XMLCapo(XMLElement):
    """
    The capo element indicates at which fret a capo should be placed on a fretted instrument. This changes the open tuning of the strings specified by staff-tuning by the specified number of half-steps.
    """
    
    TYPE = XSDSimpleTypeNonNegativeInteger
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='capo'][@type='xs:nonNegativeInteger']"


class XMLStaffSize(XMLElement):
    """
    ``complexType``: The staff-size element indicates how large a staff space is on this staff, expressed as a percentage of the work's default scaling. Values less than 100 make the staff space smaller while values over 100 make the staff space larger. A staff-type of cue, ossia, or editorial implies a staff-size of less than 100, but the exact value is implementation-dependent unless specified here. Staff size affects staff height only, not the relationship of the staff to the left and right margins.
    
    In some cases, a staff-size different than 100 also scales the notation on the staff, such as with a cue staff. In other cases, such as percussion staves, the lines may be more widely spaced without scaling the notation on the staff. The scaling attribute allows these two cases to be distinguished. It specifies the percentage scaling that applies to the notation. Values less that 100 make the notation smaller while values over 100 make the notation larger. The staff-size content and scaling attribute are both non-negative decimal values.
    
    ``simpleContent``: The non-negative-decimal type specifies a non-negative decimal value.
    """
    
    TYPE = XSDComplexTypeStaffSize
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='staff-size'][@type='staff-size']"


class XMLInterchangeable(XMLElement):
    """
    ``complexType``: The interchangeable type is used to represent the second in a pair of interchangeable dual time signatures, such as the 6/8 in 3/4 (6/8). A separate symbol attribute value is available compared to the time element's symbol attribute, which applies to the first of the dual time signatures.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=time-relation@minOccurs=0@maxOccurs=1
           Group@name=time-signature@minOccurs=1@maxOccurs=unbounded
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=beats@minOccurs=1@maxOccurs=1
                   Element@name=beat-type@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeInterchangeable
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='interchangeable'][@type='interchangeable']"


class XMLSenzaMisura(XMLElement):
    """
    A senza-misura element explicitly indicates that no time signature is present. The optional element content indicates the symbol to be used, if any, such as an X. The time element's symbol attribute is not used when a senza-misura element is present.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='senza-misura'][@type='xs:string']"


class XMLBarStyle(XMLElement):
    """
    ``complexType``: The bar-style-color type contains barline style and color information.
    
    ``simpleContent``: The bar-style type represents barline style information. Choices are regular, dotted, dashed, heavy, light-light, light-heavy, heavy-light, heavy-heavy, tick (a short stroke through the top line), short (a partial barline between the 2nd and 4th lines), and none.
        
        Permitted Values: ['regular', 'dotted', 'dashed', 'heavy', 'light-light', 'light-heavy', 'heavy-light', 'heavy-heavy', 'tick', 'short', 'none']
    
    """
    
    TYPE = XSDComplexTypeBarStyleColor
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='bar-style'][@type='bar-style-color']"


class XMLWavyLine(XMLElement):
    """
    ``complexType``: Wavy lines are one way to indicate trills and vibrato. When used with a barline element, they should always have type="continue" set. The smufl attribute specifies a particular wavy line glyph from the SMuFL Multi-segment lines range.
    """
    
    TYPE = XSDComplexTypeWavyLine
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='wavy-line'][@type='wavy-line']"


class XMLSegno(XMLElement):
    """
    ``complexType``: The segno type is the visual indicator of a segno sign. The exact glyph can be specified with the smufl attribute. A sound element is also needed to guide playback applications reliably.
    """
    
    TYPE = XSDComplexTypeSegno
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='segno'][@type='segno']"


class XMLCoda(XMLElement):
    """
    ``complexType``: The coda type is the visual indicator of a coda sign. The exact glyph can be specified with the smufl attribute. A sound element is also needed to guide playback applications reliably.
    """
    
    TYPE = XSDComplexTypeCoda
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='coda'][@type='coda']"


class XMLFermata(XMLElement):
    """
    ``complexType``: The fermata text content represents the shape of the fermata sign. An empty fermata element represents a normal fermata. The fermata type is upright if not specified.
    
    ``simpleContent``: The fermata-shape type represents the shape of the fermata sign. The empty value is equivalent to the normal value.
        
        Permitted Values: ['normal', 'angled', 'square', 'double-angled', 'double-square', 'double-dot', 'half-curve', 'curlew', '']
    
    """
    
    TYPE = XSDComplexTypeFermata
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='fermata'][@type='fermata']"


class XMLEnding(XMLElement):
    """
    ``complexType``: The ending type represents multiple (e.g. first and second) endings. Typically, the start type is associated with the left barline of the first measure in an ending. The stop and discontinue types are associated with the right barline of the last measure in an ending. Stop is used when the ending mark concludes with a downward jog, as is typical for first endings. Discontinue is used when there is no downward jog, as is typical for second endings that do not conclude a piece. The length of the jog can be specified using the end-length attribute. The text-x and text-y attributes are offsets that specify where the baseline of the start of the ending text appears, relative to the start of the ending line.
    
    The number attribute indicates which times the ending is played, similar to the time-only attribute used by other elements. While this often represents the numeric values for what is under the ending line, it can also indicate whether an ending is played during a larger dal segno or da capo repeat. Single endings such as "1" or comma-separated multiple endings such as "1,2" may be used. The ending element text is used when the text displayed in the ending is different than what appears in the number attribute. The print-object attribute is used to indicate when an ending is present but not printed, as is often the case for many parts in a full score.
    """
    
    TYPE = XSDComplexTypeEnding
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='ending'][@type='ending']"


class XMLRepeat(XMLElement):
    """
    ``complexType``: The repeat type represents repeat marks. The start of the repeat has a forward direction while the end of the repeat has a backward direction. The times and after-jump attributes are only used with backward repeats that are not part of an ending. The times attribute indicates the number of times the repeated section is played. The after-jump attribute indicates if the repeats are played after a jump due to a da capo or dal segno.
    """
    
    TYPE = XSDComplexTypeRepeat
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='repeat'][@type='repeat']"


class XMLAccordionHigh(XMLElement):
    """
    The accordion-high element indicates the presence of a dot in the high (4') section of the registration symbol. This element is omitted if no dot is present.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='accordion-high'][@type='empty']"


class XMLAccordionMiddle(XMLElement):
    """
    The accordion-middle element indicates the presence of 1 to 3 dots in the middle (8') section of the registration symbol. This element is omitted if no dots are present.
    
    ``simpleType``: The accordion-middle type may have values of 1, 2, or 3, corresponding to having 1 to 3 dots in the middle section of the accordion registration symbol. This type is not used if no dots are present.
    """
    
    TYPE = XSDSimpleTypeAccordionMiddle
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='accordion-middle'][@type='accordion-middle']"


class XMLAccordionLow(XMLElement):
    """
    The accordion-low element indicates the presence of a dot in the low (16') section of the registration symbol. This element is omitted if no dot is present.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='accordion-low'][@type='empty']"


class XMLBassSeparator(XMLElement):
    """
    The optional bass-separator element indicates that text, rather than a line or slash, separates the bass from what precedes it.
    
    ``complexType``: The style-text type represents a text element with a print-style attribute group.
    """
    
    TYPE = XSDComplexTypeStyleText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='bass-separator'][@type='style-text']"


class XMLBassStep(XMLElement):
    """
    ``complexType``: The bass-step type represents the pitch step of the bass of the current chord within the harmony element. The text attribute indicates how the bass should appear in a score if not using the element contents.
    
    ``simpleContent``: The step type represents a step of the diatonic scale, represented using the English letters A through G.
        
        Permitted Values: ['A', 'B', 'C', 'D', 'E', 'F', 'G']
    
    """
    
    TYPE = XSDComplexTypeBassStep
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='bass-step'][@type='bass-step']"


class XMLBassAlter(XMLElement):
    """
    The bass-alter element represents the chromatic alteration of the bass of the current chord within the harmony element. In some chord styles, the text for the bass-step element may include bass-alter information. In that case, the print-object attribute of the bass-alter element can be set to no. The location attribute indicates whether the alteration should appear to the left or the right of the bass-step; it is right if not specified.
    
    ``complexType``: The harmony-alter type represents the chromatic alteration of the root, numeral, or bass of the current harmony-chord group within the harmony element. In some chord styles, the text of the preceding element may include alteration information. In that case, the print-object attribute of this type can be set to no. The location attribute indicates whether the alteration should appear to the left or the right of the preceding element. Its default value varies by element.
    
    ``simpleContent``: The semitones type is a number representing semitones, used for chromatic alteration. A value of -1 corresponds to a flat and a value of 1 to a sharp. Decimal values like 0.5 (quarter tone sharp) are used for microtones.
    """
    
    TYPE = XSDComplexTypeHarmonyAlter
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='bass-alter'][@type='harmony-alter']"


class XMLDegreeValue(XMLElement):
    """
    ``complexType``: The content of the degree-value type is a number indicating the degree of the chord (1 for the root, 3 for third, etc). The text attribute specifies how the value of the degree should be displayed. The symbol attribute indicates that a symbol should be used in specifying the degree. If the symbol attribute is present, the value of the text attribute follows the symbol.
    """
    
    TYPE = XSDComplexTypeDegreeValue
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='degree-value'][@type='degree-value']"


class XMLDegreeAlter(XMLElement):
    """
    ``complexType``: The degree-alter type represents the chromatic alteration for the current degree. If the degree-type value is alter or subtract, the degree-alter value is relative to the degree already in the chord based on its kind element. If the degree-type value is add, the degree-alter is relative to a dominant chord (major and perfect intervals except for a minor seventh). The plus-minus attribute is used to indicate if plus and minus symbols should be used instead of sharp and flat symbols to display the degree alteration. It is no if not specified.
    
    ``simpleContent``: The semitones type is a number representing semitones, used for chromatic alteration. A value of -1 corresponds to a flat and a value of 1 to a sharp. Decimal values like 0.5 (quarter tone sharp) are used for microtones.
    """
    
    TYPE = XSDComplexTypeDegreeAlter
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='degree-alter'][@type='degree-alter']"


class XMLDegreeType(XMLElement):
    """
    ``complexType``: The degree-type type indicates if this degree is an addition, alteration, or subtraction relative to the kind of the current chord. The value of the degree-type element affects the interpretation of the value of the degree-alter element. The text attribute specifies how the type of the degree should be displayed.
    
    ``simpleContent``: The degree-type-value type indicates whether the current degree element is an addition, alteration, or subtraction to the kind of the current chord in the harmony element.
        
        Permitted Values: ['add', 'alter', 'subtract']
    
    """
    
    TYPE = XSDComplexTypeDegreeType
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='degree-type'][@type='degree-type']"


class XMLDirectionType(XMLElement):
    """
    ``complexType``: Textual direction types may have more than 1 component due to multiple fonts. The dynamics element may also be used in the notations element. Attribute groups related to print suggestions apply to the individual direction-type, not to the overall direction.

    ``XSD structure:``

    .. code-block::

       Choice@minOccurs=1@maxOccurs=1
           Element@name=rehearsal@minOccurs=1@maxOccurs=unbounded
           Element@name=segno@minOccurs=1@maxOccurs=unbounded
           Element@name=coda@minOccurs=1@maxOccurs=unbounded
           Choice@minOccurs=1@maxOccurs=unbounded
               Element@name=words@minOccurs=1@maxOccurs=1
               Element@name=symbol@minOccurs=1@maxOccurs=1
           Element@name=wedge@minOccurs=1@maxOccurs=1
           Element@name=dynamics@minOccurs=1@maxOccurs=unbounded
           Element@name=dashes@minOccurs=1@maxOccurs=1
           Element@name=bracket@minOccurs=1@maxOccurs=1
           Element@name=pedal@minOccurs=1@maxOccurs=1
           Element@name=metronome@minOccurs=1@maxOccurs=1
           Element@name=octave-shift@minOccurs=1@maxOccurs=1
           Element@name=harp-pedals@minOccurs=1@maxOccurs=1
           Element@name=damp@minOccurs=1@maxOccurs=1
           Element@name=damp-all@minOccurs=1@maxOccurs=1
           Element@name=eyeglasses@minOccurs=1@maxOccurs=1
           Element@name=string-mute@minOccurs=1@maxOccurs=1
           Element@name=scordatura@minOccurs=1@maxOccurs=1
           Element@name=image@minOccurs=1@maxOccurs=1
           Element@name=principal-voice@minOccurs=1@maxOccurs=1
           Element@name=percussion@minOccurs=1@maxOccurs=unbounded
           Element@name=accordion-registration@minOccurs=1@maxOccurs=1
           Element@name=staff-divide@minOccurs=1@maxOccurs=1
           Element@name=other-direction@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeDirectionType
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='direction-type'][@type='direction-type']"


class XMLOffset(XMLElement):
    """
    ``complexType``: An offset is represented in terms of divisions, and indicates where the direction will appear relative to the current musical location. The current musical location is always within the current measure, even at the end of a measure.
    
    The offset affects the visual appearance of the direction. If the sound attribute is "yes", then the offset affects playback and listening too. If the sound attribute is "no", then any sound or listening associated with the direction takes effect at the current location. The sound attribute is "no" by default for compatibility with earlier versions of the MusicXML format. If an element within a direction includes a default-x attribute, the offset value will be ignored when determining the appearance of that element.
    
    ``simpleContent``: The divisions type is used to express values in terms of the musical divisions defined by the divisions element. It is preferred that these be integer values both for MIDI interoperability and to avoid roundoff errors.
    """
    
    TYPE = XSDComplexTypeOffset
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='offset'][@type='offset']"


class XMLSound(XMLElement):
    """
    ``complexType``: The sound element contains general playback parameters. They can stand alone within a part/measure, or be a component element within a direction.
    
    Tempo is expressed in quarter notes per minute. If 0, the sound-generating program should prompt the user at the time of compiling a sound (MIDI) file.
    
    Dynamics (or MIDI velocity) are expressed as a percentage of the default forte value (90 for MIDI 1.0).
    
    Dacapo indicates to go back to the beginning of the movement. When used it always has the value "yes".
    
    Segno and dalsegno are used for backwards jumps to a segno sign; coda and tocoda are used for forward jumps to a coda sign. If there are multiple jumps, the value of these parameters can be used to name and distinguish them. If segno or coda is used, the divisions attribute can also be used to indicate the number of divisions per quarter note. Otherwise sound and MIDI generating programs may have to recompute this.
    
    By default, a dalsegno or dacapo attribute indicates that the jump should occur the first time through, while a tocoda attribute indicates the jump should occur the second time through. The time that jumps occur can be changed by using the time-only attribute.
    
    The forward-repeat attribute indicates that a forward repeat sign is implied but not displayed. It is used for example in two-part forms with repeats, such as a minuet and trio where no repeat is displayed at the start of the trio. This usually occurs after a barline. When used it always has the value of "yes".
    
    The fine attribute follows the final note or rest in a movement with a da capo or dal segno direction. If numeric, the value represents the actual duration of the final note or rest, which can be ambiguous in written notation and different among parts and voices. The value may also be "yes" to indicate no change to the final duration.
    
    If the sound element applies only particular times through a repeat, the time-only attribute indicates which times to apply the sound element.
    
    Pizzicato in a sound element effects all following notes. Yes indicates pizzicato, no indicates arco.
    
    The pan and elevation attributes are deprecated in Version 2.0. The pan and elevation elements in the midi-instrument element should be used instead. The meaning of the pan and elevation attributes is the same as for the pan and elevation elements. If both are present, the mid-instrument elements take priority.
    
    The damper-pedal, soft-pedal, and sostenuto-pedal attributes effect playback of the three common piano pedals and their MIDI controller equivalents. The yes value indicates the pedal is depressed; no indicates the pedal is released. A numeric value from 0 to 100 may also be used for half pedaling. This value is the percentage that the pedal is depressed. A value of 0 is equivalent to no, and a value of 100 is equivalent to yes.
    
    Instrument changes, MIDI devices, MIDI instruments, and playback techniques are changed using the instrument-change, midi-device, midi-instrument, and play elements. When there are multiple instances of these elements, they should be grouped together by instrument using the id attribute values.
    
    The offset element is used to indicate that the sound takes place offset from the current score position. If the sound element is a child of a direction element, the sound offset element overrides the direction offset element if both elements are present. Note that the offset reflects the intended musical position for the change in sound. It should not be used to compensate for latency issues in particular hardware configurations.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Sequence@minOccurs=0@maxOccurs=unbounded
               Element@name=instrument-change@minOccurs=0@maxOccurs=1
               Element@name=midi-device@minOccurs=0@maxOccurs=1
               Element@name=midi-instrument@minOccurs=0@maxOccurs=1
               Element@name=play@minOccurs=0@maxOccurs=1
           Element@name=swing@minOccurs=0@maxOccurs=1
           Element@name=offset@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeSound
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='sound'][@type='sound']"


class XMLListening(XMLElement):
    """
    ``complexType``: The listen and listening types, new in Version 4.0, specify different ways that a score following or machine listening application can interact with a performer. The listening type handles interactions that change the state of the listening application from the specified point in the performance onward. If multiple child elements of the same type are present, they should have distinct player and/or time-only attributes.
    
    The offset element is used to indicate that the listening change takes place offset from the current score position. If the listening element is a child of a direction element, the listening offset element overrides the direction offset element if both elements are present. Note that the offset reflects the intended musical position for the change in state. It should not be used to compensate for latency issues in particular hardware configurations.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Choice@minOccurs=1@maxOccurs=unbounded
               Element@name=sync@minOccurs=1@maxOccurs=1
               Element@name=other-listening@minOccurs=1@maxOccurs=1
           Element@name=offset@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeListening
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='listening'][@type='listening']"


class XMLRehearsal(XMLElement):
    """
    The rehearsal element specifies letters, numbers, and section names that are notated in the score for reference during rehearsal. The enclosure is square if not specified. The language is Italian ("it") if not specified. Left justification is used if not specified.
    
    ``complexType``: The formatted-text-id type represents a text element with text-formatting and id attributes.
    """
    
    TYPE = XSDComplexTypeFormattedTextId
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='rehearsal'][@type='formatted-text-id']"


class XMLWords(XMLElement):
    """
    The words element specifies a standard text direction. The enclosure is none if not specified. The language is Italian ("it") if not specified. Left justification is used if not specified.
    
    ``complexType``: The formatted-text-id type represents a text element with text-formatting and id attributes.
    """
    
    TYPE = XSDComplexTypeFormattedTextId
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='words'][@type='formatted-text-id']"


class XMLSymbol(XMLElement):
    """
    The symbol element specifies a musical symbol using a canonical SMuFL glyph name. It is used when an occasional musical symbol is interspersed into text. It should not be used in place of semantic markup, such as metronome marks that mix text and symbols. Left justification is used if not specified. Enclosure is none if not specified.
    
    ``complexType``: The formatted-symbol-id type represents a SMuFL musical symbol element with formatting and id attributes.
    
    ``simpleContent``: The smufl-glyph-name type is used for attributes that reference a specific Standard Music Font Layout (SMuFL) character. The value is a SMuFL canonical glyph name, not a code point. For instance, the value for a standard piano pedal mark would be keyboardPedalPed, not U+E650.
    """
    
    TYPE = XSDComplexTypeFormattedSymbolId
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='symbol'][@type='formatted-symbol-id']"


class XMLWedge(XMLElement):
    """
    ``complexType``: The wedge type represents crescendo and diminuendo wedge symbols. The type attribute is crescendo for the start of a wedge that is closed at the left side, and diminuendo for the start of a wedge that is closed on the right side. Spread values are measured in tenths; those at the start of a crescendo wedge or end of a diminuendo wedge are ignored. The niente attribute is yes if a circle appears at the point of the wedge, indicating a crescendo from nothing or diminuendo to nothing. It is no by default, and used only when the type is crescendo, or the type is stop for a wedge that began with a diminuendo type. The line-type is solid if not specified.
    """
    
    TYPE = XSDComplexTypeWedge
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='wedge'][@type='wedge']"


class XMLDynamics(XMLElement):
    """
    ``complexType``: Dynamics can be associated either with a note or a general musical direction. To avoid inconsistencies between and amongst the letter abbreviations for dynamics (what is sf vs. sfz, standing alone or with a trailing dynamic that is not always piano), we use the actual letters as the names of these dynamic elements. The other-dynamics element allows other dynamic marks that are not covered here. Dynamics elements may also be combined to create marks not covered by a single element, such as sfmp.
    
    These letter dynamic symbols are separated from crescendo, decrescendo, and wedge indications. Dynamic representation is inconsistent in scores. Many things are assumed by the composer and left out, such as returns to original dynamics. The MusicXML format captures what is in the score, but does not try to be optimal for analysis or synthesis of dynamics.
    
    The placement attribute is used when the dynamics are associated with a note. It is ignored when the dynamics are associated with a direction. In that case the direction element's placement attribute is used instead.

    ``XSD structure:``

    .. code-block::

       Choice@minOccurs=0@maxOccurs=unbounded
           Element@name=p@minOccurs=1@maxOccurs=1
           Element@name=pp@minOccurs=1@maxOccurs=1
           Element@name=ppp@minOccurs=1@maxOccurs=1
           Element@name=pppp@minOccurs=1@maxOccurs=1
           Element@name=ppppp@minOccurs=1@maxOccurs=1
           Element@name=pppppp@minOccurs=1@maxOccurs=1
           Element@name=f@minOccurs=1@maxOccurs=1
           Element@name=ff@minOccurs=1@maxOccurs=1
           Element@name=fff@minOccurs=1@maxOccurs=1
           Element@name=ffff@minOccurs=1@maxOccurs=1
           Element@name=fffff@minOccurs=1@maxOccurs=1
           Element@name=ffffff@minOccurs=1@maxOccurs=1
           Element@name=mp@minOccurs=1@maxOccurs=1
           Element@name=mf@minOccurs=1@maxOccurs=1
           Element@name=sf@minOccurs=1@maxOccurs=1
           Element@name=sfp@minOccurs=1@maxOccurs=1
           Element@name=sfpp@minOccurs=1@maxOccurs=1
           Element@name=fp@minOccurs=1@maxOccurs=1
           Element@name=rf@minOccurs=1@maxOccurs=1
           Element@name=rfz@minOccurs=1@maxOccurs=1
           Element@name=sfz@minOccurs=1@maxOccurs=1
           Element@name=sffz@minOccurs=1@maxOccurs=1
           Element@name=fz@minOccurs=1@maxOccurs=1
           Element@name=n@minOccurs=1@maxOccurs=1
           Element@name=pf@minOccurs=1@maxOccurs=1
           Element@name=sfzp@minOccurs=1@maxOccurs=1
           Element@name=other-dynamics@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeDynamics
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='dynamics'][@type='dynamics']"


class XMLDashes(XMLElement):
    """
    ``complexType``: The dashes type represents dashes, used for instance with cresc. and dim. marks.
    """
    
    TYPE = XSDComplexTypeDashes
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='dashes'][@type='dashes']"


class XMLBracket(XMLElement):
    """
    ``complexType``: Brackets are combined with words in a variety of modern directions. The line-end attribute specifies if there is a jog up or down (or both), an arrow, or nothing at the start or end of the bracket. If the line-end is up or down, the length of the jog can be specified using the end-length attribute. The line-type is solid if not specified.
    """
    
    TYPE = XSDComplexTypeBracket
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='bracket'][@type='bracket']"


class XMLPedal(XMLElement):
    """
    ``complexType``: The pedal type represents piano pedal marks, including damper and sostenuto pedal marks. The line attribute is yes if pedal lines are used. The sign attribute is yes if Ped, Sost, and * signs are used. For compatibility with older versions, the sign attribute is yes by default if the line attribute is no, and is no by default if the line attribute is yes. If the sign attribute is set to yes and the type is start or sostenuto, the abbreviated attribute is yes if the short P and S signs are used, and no if the full Ped and Sost signs are used. It is no by default. Otherwise the abbreviated attribute is ignored. The alignment attributes are ignored if the sign attribute is no.
    """
    
    TYPE = XSDComplexTypePedal
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='pedal'][@type='pedal']"


class XMLMetronome(XMLElement):
    """
    ``complexType``: The metronome type represents metronome marks and other metric relationships. The beat-unit group and per-minute element specify regular metronome marks. The metronome-note and metronome-relation elements allow for the specification of metric modulations and other metric relationships, such as swing tempo marks where two eighths are equated to a quarter note / eighth note triplet. Tied notes can be represented in both types of metronome marks by using the beat-unit-tied and metronome-tied elements. The parentheses attribute indicates whether or not to put the metronome mark in parentheses; its value is no if not specified. The print-object attribute is set to no in cases where the metronome element represents a relationship or range that is not displayed in the music notation.

    ``XSD structure:``

    .. code-block::

       Choice@minOccurs=1@maxOccurs=1
           Sequence@minOccurs=1@maxOccurs=1
               Group@name=beat-unit@minOccurs=1@maxOccurs=1
                   Sequence@minOccurs=1@maxOccurs=1
                       Element@name=beat-unit@minOccurs=1@maxOccurs=1
                       Element@name=beat-unit-dot@minOccurs=0@maxOccurs=unbounded
               Element@name=beat-unit-tied@minOccurs=0@maxOccurs=unbounded
               Choice@minOccurs=1@maxOccurs=1
                   Element@name=per-minute@minOccurs=1@maxOccurs=1
                   Sequence@minOccurs=1@maxOccurs=1
                       Group@name=beat-unit@minOccurs=1@maxOccurs=1
                           Sequence@minOccurs=1@maxOccurs=1
                               Element@name=beat-unit@minOccurs=1@maxOccurs=1
                               Element@name=beat-unit-dot@minOccurs=0@maxOccurs=unbounded
                       Element@name=beat-unit-tied@minOccurs=0@maxOccurs=unbounded
           Sequence@minOccurs=1@maxOccurs=1
               Element@name=metronome-arrows@minOccurs=0@maxOccurs=1
               Element@name=metronome-note@minOccurs=1@maxOccurs=unbounded
               Sequence@minOccurs=0@maxOccurs=1
                   Element@name=metronome-relation@minOccurs=1@maxOccurs=1
                   Element@name=metronome-note@minOccurs=1@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypeMetronome
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='metronome'][@type='metronome']"


class XMLOctaveShift(XMLElement):
    """
    ``complexType``: The octave shift type indicates where notes are shifted up or down from their true pitched values because of printing difficulty. Thus a treble clef line noted with 8va will be indicated with an octave-shift down from the pitch data indicated in the notes. A size of 8 indicates one octave; a size of 15 indicates two octaves.
    """
    
    TYPE = XSDComplexTypeOctaveShift
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='octave-shift'][@type='octave-shift']"


class XMLHarpPedals(XMLElement):
    """
    ``complexType``: The harp-pedals type is used to create harp pedal diagrams. The pedal-step and pedal-alter elements use the same values as the step and alter elements. For easiest reading, the pedal-tuning elements should follow standard harp pedal order, with pedal-step values of D, C, B, E, F, G, and A.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=pedal-tuning@minOccurs=1@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypeHarpPedals
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='harp-pedals'][@type='harp-pedals']"


class XMLDamp(XMLElement):
    """
    The damp element specifies a harp damping mark.
    
    ``complexType``: The empty-print-style-align-id type represents an empty element with print-style-align and optional-unique-id attribute groups.
    """
    
    TYPE = XSDComplexTypeEmptyPrintStyleAlignId
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='damp'][@type='empty-print-style-align-id']"


class XMLDampAll(XMLElement):
    """
    The damp-all element specifies a harp damping mark for all strings.
    
    ``complexType``: The empty-print-style-align-id type represents an empty element with print-style-align and optional-unique-id attribute groups.
    """
    
    TYPE = XSDComplexTypeEmptyPrintStyleAlignId
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='damp-all'][@type='empty-print-style-align-id']"


class XMLEyeglasses(XMLElement):
    """
    The eyeglasses element represents the eyeglasses symbol, common in commercial music.
    
    ``complexType``: The empty-print-style-align-id type represents an empty element with print-style-align and optional-unique-id attribute groups.
    """
    
    TYPE = XSDComplexTypeEmptyPrintStyleAlignId
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='eyeglasses'][@type='empty-print-style-align-id']"


class XMLStringMute(XMLElement):
    """
    ``complexType``: The string-mute type represents string mute on and mute off symbols.
    """
    
    TYPE = XSDComplexTypeStringMute
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='string-mute'][@type='string-mute']"


class XMLScordatura(XMLElement):
    """
    ``complexType``: Scordatura string tunings are represented by a series of accord elements, similar to the staff-tuning elements. Strings are numbered from high to low.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=accord@minOccurs=1@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypeScordatura
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='scordatura'][@type='scordatura']"


class XMLImage(XMLElement):
    """
    ``complexType``: The image type is used to include graphical images in a score.
    """
    
    TYPE = XSDComplexTypeImage
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='image'][@type='image']"


class XMLPrincipalVoice(XMLElement):
    """
    ``complexType``: The principal-voice type represents principal and secondary voices in a score, either for analysis or for square bracket symbols that appear in a score. The element content is used for analysis and may be any text value. The symbol attribute indicates the type of symbol used. When used for analysis separate from any printed score markings, it should be set to none. Otherwise if the type is stop it should be set to plain.
    """
    
    TYPE = XSDComplexTypePrincipalVoice
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='principal-voice'][@type='principal-voice']"


class XMLPercussion(XMLElement):
    """
    ``complexType``: The percussion element is used to define percussion pictogram symbols. Definitions for these symbols can be found in Kurt Stone's "Music Notation in the Twentieth Century" on pages 206-212 and 223. Some values are added to these based on how usage has evolved in the 30 years since Stone's book was published.

    ``XSD structure:``

    .. code-block::

       Choice@minOccurs=1@maxOccurs=1
           Element@name=glass@minOccurs=1@maxOccurs=1
           Element@name=metal@minOccurs=1@maxOccurs=1
           Element@name=wood@minOccurs=1@maxOccurs=1
           Element@name=pitched@minOccurs=1@maxOccurs=1
           Element@name=membrane@minOccurs=1@maxOccurs=1
           Element@name=effect@minOccurs=1@maxOccurs=1
           Element@name=timpani@minOccurs=1@maxOccurs=1
           Element@name=beater@minOccurs=1@maxOccurs=1
           Element@name=stick@minOccurs=1@maxOccurs=1
           Element@name=stick-location@minOccurs=1@maxOccurs=1
           Element@name=other-percussion@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypePercussion
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='percussion'][@type='percussion']"


class XMLAccordionRegistration(XMLElement):
    """
    ``complexType``: The accordion-registration type is used for accordion registration symbols. These are circular symbols divided horizontally into high, middle, and low sections that correspond to 4', 8', and 16' pipes. Each accordion-high, accordion-middle, and accordion-low element represents the presence of one or more dots in the registration diagram. An accordion-registration element needs to have at least one of the child elements present.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=accordion-high@minOccurs=0@maxOccurs=1
           Element@name=accordion-middle@minOccurs=0@maxOccurs=1
           Element@name=accordion-low@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeAccordionRegistration
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='accordion-registration'][@type='accordion-registration']"


class XMLStaffDivide(XMLElement):
    """
    ``complexType``: The staff-divide element represents the staff division arrow symbols found at SMuFL code points U+E00B, U+E00C, and U+E00D.
    """
    
    TYPE = XSDComplexTypeStaffDivide
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='staff-divide'][@type='staff-divide']"


class XMLOtherDirection(XMLElement):
    """
    ``complexType``: The other-direction type is used to define any direction symbols not yet in the MusicXML format. The smufl attribute can be used to specify a particular direction symbol, allowing application interoperability without requiring every SMuFL glyph to have a MusicXML element equivalent. Using the other-direction type without the smufl attribute allows for extended representation, though without application interoperability.
    """
    
    TYPE = XSDComplexTypeOtherDirection
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='other-direction'][@type='other-direction']"


class XMLFrameStrings(XMLElement):
    """
    The frame-strings element gives the overall size of the frame in vertical lines (strings).
    """
    
    TYPE = XSDSimpleTypePositiveInteger
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='frame-strings'][@type='xs:positiveInteger']"


class XMLFrameFrets(XMLElement):
    """
    The frame-frets element gives the overall size of the frame in horizontal spaces (frets).
    """
    
    TYPE = XSDSimpleTypePositiveInteger
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='frame-frets'][@type='xs:positiveInteger']"


class XMLFirstFret(XMLElement):
    """
    ``complexType``: The first-fret type indicates which fret is shown in the top space of the frame; it is fret 1 if the element is not present. The optional text attribute indicates how this is represented in the fret diagram, while the location attribute indicates whether the text appears to the left or right of the frame.
    """
    
    TYPE = XSDComplexTypeFirstFret
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='first-fret'][@type='first-fret']"


class XMLFrameNote(XMLElement):
    """
    ``complexType``: The frame-note type represents each note included in the frame. An open string will have a fret value of 0, while a muted string will not be associated with a frame-note element.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=string@minOccurs=1@maxOccurs=1
           Element@name=fret@minOccurs=1@maxOccurs=1
           Element@name=fingering@minOccurs=0@maxOccurs=1
           Element@name=barre@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeFrameNote
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='frame-note'][@type='frame-note']"


class XMLString(XMLElement):
    """
    ``complexType``: The string type is used with tablature notation, regular notation (where it is often circled), and chord diagrams. String numbers start with 1 for the highest pitched full-length string.
    
    ``simpleContent``: The string-number type indicates a string number. Strings are numbered from high to low, with 1 being the highest pitched full-length string.
    """
    
    TYPE = XSDComplexTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='string'][@type='string']"


class XMLFret(XMLElement):
    """
    ``complexType``: The fret element is used with tablature notation and chord diagrams. Fret numbers start with 0 for an open string and 1 for the first fret.
    """
    
    TYPE = XSDComplexTypeFret
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='fret'][@type='fret']"


class XMLFingering(XMLElement):
    """
    ``complexType``: Fingering is typically indicated 1,2,3,4,5. Multiple fingerings may be given, typically to substitute fingerings in the middle of a note. The substitution and alternate values are "no" if the attribute is not present. For guitar and other fretted instruments, the fingering element represents the fretting finger; the pluck element represents the plucking finger.
    """
    
    TYPE = XSDComplexTypeFingering
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='fingering'][@type='fingering']"


class XMLBarre(XMLElement):
    """
    ``complexType``: The barre element indicates placing a finger over multiple strings on a single fret. The type is "start" for the lowest pitched string (e.g., the string with the highest MusicXML number) and is "stop" for the highest pitched string.
    """
    
    TYPE = XSDComplexTypeBarre
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='barre'][@type='barre']"


class XMLFeature(XMLElement):
    """
    ``complexType``: The feature type is a part of the grouping element used for musical analysis. The type attribute represents the type of the feature and the element content represents its value. This type is flexible to allow for different analyses.
    """
    
    TYPE = XSDComplexTypeFeature
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='feature'][@type='feature']"


class XMLFrame(XMLElement):
    """
    ``complexType``: The frame type represents a frame or fretboard diagram used together with a chord symbol. The representation is based on the NIFF guitar grid with additional information. The frame type's unplayed attribute indicates what to display above a string that has no associated frame-note element. Typical values are x and the empty string. If the attribute is not present, the display of the unplayed string is application-defined.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=frame-strings@minOccurs=1@maxOccurs=1
           Element@name=frame-frets@minOccurs=1@maxOccurs=1
           Element@name=first-fret@minOccurs=0@maxOccurs=1
           Element@name=frame-note@minOccurs=1@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypeFrame
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='frame'][@type='frame']"


class XMLPedalTuning(XMLElement):
    """
    ``complexType``: The pedal-tuning type specifies the tuning of a single harp pedal.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=pedal-step@minOccurs=1@maxOccurs=1
           Element@name=pedal-alter@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypePedalTuning
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='pedal-tuning'][@type='pedal-tuning']"


class XMLSync(XMLElement):
    """
    ``complexType``: The sync type specifies the style that a score following application should use the synchronize an accompaniment with a performer. If this type is not included in a score, default synchronization depends on the application.
    
    The optional latency attribute specifies a time in milliseconds that the listening application should expect from the performer. The optional player and time-only attributes restrict the element to apply to a single player or set of times through a repeated section, respectively.
    """
    
    TYPE = XSDComplexTypeSync
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='sync'][@type='sync']"


class XMLOtherListening(XMLElement):
    """
    ``complexType``: The other-listening type represents other types of listening control and interaction. The required type attribute indicates the type of listening to which the element content applies. The optional player and time-only attributes restrict the element to apply to a single player or set of times through a repeated section, respectively.
    """
    
    TYPE = XSDComplexTypeOtherListening
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='other-listening'][@type='other-listening']"


class XMLBeatUnitTied(XMLElement):
    """
    ``complexType``: The beat-unit-tied type indicates a beat-unit within a metronome mark that is tied to the preceding beat-unit. This allows two or more tied notes to be associated with a per-minute value in a metronome mark, whereas the metronome-tied element is restricted to metric relationship marks.

    ``XSD structure:``

    .. code-block::

       Group@name=beat-unit@minOccurs=1@maxOccurs=1
           Sequence@minOccurs=1@maxOccurs=1
               Element@name=beat-unit@minOccurs=1@maxOccurs=1
               Element@name=beat-unit-dot@minOccurs=0@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypeBeatUnitTied
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='beat-unit-tied'][@type='beat-unit-tied']"


class XMLPerMinute(XMLElement):
    """
    ``complexType``: The per-minute type can be a number, or a text description including numbers. If a font is specified, it overrides the font specified for the overall metronome element. This allows separate specification of a music font for the beat-unit and a text font for the numeric value, in cases where a single metronome font is not used.
    """
    
    TYPE = XSDComplexTypePerMinute
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='per-minute'][@type='per-minute']"


class XMLMetronomeArrows(XMLElement):
    """
    If the metronome-arrows element is present, it indicates that metric modulation arrows are displayed on both sides of the metronome mark.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='metronome-arrows'][@type='empty']"


class XMLMetronomeNote(XMLElement):
    """
    ``complexType``: The metronome-note type defines the appearance of a note within a metric relationship mark.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=metronome-type@minOccurs=1@maxOccurs=1
           Element@name=metronome-dot@minOccurs=0@maxOccurs=unbounded
           Element@name=metronome-beam@minOccurs=0@maxOccurs=unbounded
           Element@name=metronome-tied@minOccurs=0@maxOccurs=1
           Element@name=metronome-tuplet@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeMetronomeNote
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='metronome-note'][@type='metronome-note']"


class XMLMetronomeRelation(XMLElement):
    """
    The metronome-relation element describes the relationship symbol that goes between the two sets of metronome-note elements. The currently allowed value is equals, but this may expand in future versions. If the element is empty, the equals value is used.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='metronome-relation'][@type='xs:string']"


class XMLMetronomeType(XMLElement):
    """
    The metronome-type element works like the type element in defining metric relationships.
    
    ``simpleType``: The note-type-value type is used for the MusicXML type element and represents the graphic note type, from 1024th (shortest) to maxima (longest).
        
        Permitted Values: ['1024th', '512th', '256th', '128th', '64th', '32nd', '16th', 'eighth', 'quarter', 'half', 'whole', 'breve', 'long', 'maxima']
    
    """
    
    TYPE = XSDSimpleTypeNoteTypeValue
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='metronome-type'][@type='note-type-value']"


class XMLMetronomeDot(XMLElement):
    """
    The metronome-dot element works like the dot element in defining metric relationships.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='metronome-dot'][@type='empty']"


class XMLMetronomeBeam(XMLElement):
    """
    ``complexType``: The metronome-beam type works like the beam type in defining metric relationships, but does not include all the attributes available in the beam type.
    
    ``simpleContent``: The beam-value type represents the type of beam associated with each of 8 beam levels (up to 1024th notes) available for each note.
        
        Permitted Values: ['begin', 'continue', 'end', 'forward hook', 'backward hook']
    
    """
    
    TYPE = XSDComplexTypeMetronomeBeam
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='metronome-beam'][@type='metronome-beam']"


class XMLMetronomeTied(XMLElement):
    """
    ``complexType``: The metronome-tied indicates the presence of a tie within a metric relationship mark. As with the tied element, both the start and stop of the tie should be specified, in this case within separate metronome-note elements.
    """
    
    TYPE = XSDComplexTypeMetronomeTied
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='metronome-tied'][@type='metronome-tied']"


class XMLMetronomeTuplet(XMLElement):
    """
    ``complexType``: The metronome-tuplet type uses the same element structure as the time-modification element along with some attributes from the tuplet element.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=actual-notes@minOccurs=1@maxOccurs=1
           Element@name=normal-notes@minOccurs=1@maxOccurs=1
           Sequence@minOccurs=0@maxOccurs=1
               Element@name=normal-type@minOccurs=1@maxOccurs=1
               Element@name=normal-dot@minOccurs=0@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypeMetronomeTuplet
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='metronome-tuplet'][@type='metronome-tuplet']"


class XMLNumeralRoot(XMLElement):
    """
    ``complexType``: The numeral-root type represents the Roman numeral or Nashville number as a positive integer from 1 to 7. The text attribute indicates how the numeral should appear in the score. A numeral-root value of 5 with a kind of major would have a text attribute of "V" if displayed as a Roman numeral, and "5" if displayed as a Nashville number. If the text attribute is not specified, the display is application-dependent.
    
    ``simpleContent``: The numeral-value type represents a Roman numeral or Nashville number value as a positive integer from 1 to 7.
    """
    
    TYPE = XSDComplexTypeNumeralRoot
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='numeral-root'][@type='numeral-root']"


class XMLNumeralAlter(XMLElement):
    """
    The numeral-alter element represents an alteration to the numeral-root, similar to the alter element for a pitch. The print-object attribute can be used to hide an alteration in cases such as when the MusicXML encoding of a 6 or 7 numeral-root in a minor key requires an alteration that is not displayed. The location attribute indicates whether the alteration should appear to the left or the right of the numeral-root. It is left by default.
    
    ``complexType``: The harmony-alter type represents the chromatic alteration of the root, numeral, or bass of the current harmony-chord group within the harmony element. In some chord styles, the text of the preceding element may include alteration information. In that case, the print-object attribute of this type can be set to no. The location attribute indicates whether the alteration should appear to the left or the right of the preceding element. Its default value varies by element.
    
    ``simpleContent``: The semitones type is a number representing semitones, used for chromatic alteration. A value of -1 corresponds to a flat and a value of 1 to a sharp. Decimal values like 0.5 (quarter tone sharp) are used for microtones.
    """
    
    TYPE = XSDComplexTypeHarmonyAlter
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='numeral-alter'][@type='harmony-alter']"


class XMLNumeralKey(XMLElement):
    """
    ``complexType``: The numeral-key type is used when the key for the numeral is different than the key specified by the key signature. The numeral-fifths element specifies the key in the same way as the fifths element. The numeral-mode element specifies the mode similar to the mode element, but with a restricted set of values

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=numeral-fifths@minOccurs=1@maxOccurs=1
           Element@name=numeral-mode@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeNumeralKey
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='numeral-key'][@type='numeral-key']"


class XMLNumeralFifths(XMLElement):
    """
    ``simpleType``: The fifths type represents the number of flats or sharps in a traditional key signature. Negative numbers are used for flats and positive numbers for sharps, reflecting the key's placement within the circle of fifths (hence the type name).
    """
    
    TYPE = XSDSimpleTypeFifths
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='numeral-fifths'][@type='fifths']"


class XMLNumeralMode(XMLElement):
    """
    ``simpleType``: The numeral-mode type specifies the mode similar to the mode type, but with a restricted set of values. The different minor values are used to interpret numeral-root values of 6 and 7 when present in a minor key. The harmonic minor value sharpens the 7 and the melodic minor value sharpens both 6 and 7. If a minor mode is used without qualification, either in the mode or numeral-mode elements, natural minor is used.
        
        Permitted Values: ['major', 'minor', 'natural minor', 'melodic minor', 'harmonic minor']
    
    """
    
    TYPE = XSDSimpleTypeNumeralMode
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='numeral-mode'][@type='numeral-mode']"


class XMLPedalStep(XMLElement):
    """
    The pedal-step element defines the pitch step for a single harp pedal.
    
    ``simpleType``: The step type represents a step of the diatonic scale, represented using the English letters A through G.
        
        Permitted Values: ['A', 'B', 'C', 'D', 'E', 'F', 'G']
    
    """
    
    TYPE = XSDSimpleTypeStep
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='pedal-step'][@type='step']"


class XMLPedalAlter(XMLElement):
    """
    The pedal-alter element defines the chromatic alteration for a single harp pedal.
    
    ``simpleType``: The semitones type is a number representing semitones, used for chromatic alteration. A value of -1 corresponds to a flat and a value of 1 to a sharp. Decimal values like 0.5 (quarter tone sharp) are used for microtones.
    """
    
    TYPE = XSDSimpleTypeSemitones
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='pedal-alter'][@type='semitones']"


class XMLGlass(XMLElement):
    """
    ``complexType``: The glass type represents pictograms for glass percussion instruments. The smufl attribute is used to distinguish different SMuFL glyphs for wind chimes in the Chimes pictograms range, including those made of materials other than glass.
    
    ``simpleContent``: The glass-value type represents pictograms for glass percussion instruments.
        
        Permitted Values: ['glass harmonica', 'glass harp', 'wind chimes']
    
    """
    
    TYPE = XSDComplexTypeGlass
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='glass'][@type='glass']"


class XMLMetal(XMLElement):
    """
    ``complexType``: The metal type represents pictograms for metal percussion instruments. The smufl attribute is used to distinguish different SMuFL stylistic alternates.
    
    ``simpleContent``: The metal-value type represents pictograms for metal percussion instruments. The hi-hat value refers to a pictogram like Stone's high-hat cymbals but without the long vertical line at the bottom.
        
        Permitted Values: ['agogo', 'almglocken', 'bell', 'bell plate', 'bell tree', 'brake drum', 'cencerro', 'chain rattle', 'Chinese cymbal', 'cowbell', 'crash cymbals', 'crotale', 'cymbal tongs', 'domed gong', 'finger cymbals', 'flexatone', 'gong', 'hi-hat', 'high-hat cymbals', 'handbell', 'jaw harp', 'jingle bells', 'musical saw', 'shell bells', 'sistrum', 'sizzle cymbal', 'sleigh bells', 'suspended cymbal', 'tam tam', 'tam tam with beater', 'triangle', 'Vietnamese hat']
    
    """
    
    TYPE = XSDComplexTypeMetal
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='metal'][@type='metal']"


class XMLWood(XMLElement):
    """
    ``complexType``: The wood type represents pictograms for wood percussion instruments. The smufl attribute is used to distinguish different SMuFL stylistic alternates.
    
    ``simpleContent``: The wood-value type represents pictograms for wood percussion instruments. The maraca and maracas values distinguish the one- and two-maraca versions of the pictogram.
        
        Permitted Values: ['bamboo scraper', 'board clapper', 'cabasa', 'castanets', 'castanets with handle', 'claves', 'football rattle', 'guiro', 'log drum', 'maraca', 'maracas', 'quijada', 'rainstick', 'ratchet', 'reco-reco', 'sandpaper blocks', 'slit drum', 'temple block', 'vibraslap', 'whip', 'wood block']
    
    """
    
    TYPE = XSDComplexTypeWood
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='wood'][@type='wood']"


class XMLPitched(XMLElement):
    """
    ``complexType``: The pitched-value type represents pictograms for pitched percussion instruments. The smufl attribute is used to distinguish different SMuFL glyphs for a particular pictogram within the Tuned mallet percussion pictograms range.
    
    ``simpleContent``: The pitched-value type represents pictograms for pitched percussion instruments. The chimes and tubular chimes values distinguish the single-line and double-line versions of the pictogram.
        
        Permitted Values: ['celesta', 'chimes', 'glockenspiel', 'lithophone', 'mallet', 'marimba', 'steel drums', 'tubaphone', 'tubular chimes', 'vibraphone', 'xylophone']
    
    """
    
    TYPE = XSDComplexTypePitched
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='pitched'][@type='pitched']"


class XMLMembrane(XMLElement):
    """
    ``complexType``: The membrane type represents pictograms for membrane percussion instruments. The smufl attribute is used to distinguish different SMuFL stylistic alternates.
    
    ``simpleContent``: The membrane-value type represents pictograms for membrane percussion instruments.
        
        Permitted Values: ['bass drum', 'bass drum on side', 'bongos', 'Chinese tomtom', 'conga drum', 'cuica', 'goblet drum', 'Indo-American tomtom', 'Japanese tomtom', 'military drum', 'snare drum', 'snare drum snares off', 'tabla', 'tambourine', 'tenor drum', 'timbales', 'tomtom']
    
    """
    
    TYPE = XSDComplexTypeMembrane
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='membrane'][@type='membrane']"


class XMLEffect(XMLElement):
    """
    ``complexType``: The effect type represents pictograms for sound effect percussion instruments. The smufl attribute is used to distinguish different SMuFL stylistic alternates.
    
    ``simpleContent``: The effect-value type represents pictograms for sound effect percussion instruments. The cannon, lotus flute, and megaphone values are in addition to Stone's list.
        
        Permitted Values: ['anvil', 'auto horn', 'bird whistle', 'cannon', 'duck call', 'gun shot', 'klaxon horn', 'lions roar', 'lotus flute', 'megaphone', 'police whistle', 'siren', 'slide whistle', 'thunder sheet', 'wind machine', 'wind whistle']
    
    """
    
    TYPE = XSDComplexTypeEffect
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='effect'][@type='effect']"


class XMLTimpani(XMLElement):
    """
    ``complexType``: The timpani type represents the timpani pictogram. The smufl attribute is used to distinguish different SMuFL stylistic alternates.
    """
    
    TYPE = XSDComplexTypeTimpani
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='timpani'][@type='timpani']"


class XMLBeater(XMLElement):
    """
    ``complexType``: The beater type represents pictograms for beaters, mallets, and sticks that do not have different materials represented in the pictogram.
    
    ``simpleContent``: The beater-value type represents pictograms for beaters, mallets, and sticks that do not have different materials represented in the pictogram. The finger and hammer values are in addition to Stone's list.
        
        Permitted Values: ['bow', 'chime hammer', 'coin', 'drum stick', 'finger', 'fingernail', 'fist', 'guiro scraper', 'hammer', 'hand', 'jazz stick', 'knitting needle', 'metal hammer', 'slide brush on gong', 'snare stick', 'spoon mallet', 'superball', 'triangle beater', 'triangle beater plain', 'wire brush']
    
    """
    
    TYPE = XSDComplexTypeBeater
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='beater'][@type='beater']"


class XMLStick(XMLElement):
    """
    ``complexType``: The stick type represents pictograms where the material of the stick, mallet, or beater is included.The parentheses and dashed-circle attributes indicate the presence of these marks around the round beater part of a pictogram. Values for these attributes are "no" if not present.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=stick-type@minOccurs=1@maxOccurs=1
           Element@name=stick-material@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeStick
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='stick'][@type='stick']"


class XMLStickLocation(XMLElement):
    """
    ``simpleType``: The stick-location type represents pictograms for the location of sticks, beaters, or mallets on cymbals, gongs, drums, and other instruments.
        
        Permitted Values: ['center', 'rim', 'cymbal bell', 'cymbal edge']
    
    """
    
    TYPE = XSDSimpleTypeStickLocation
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='stick-location'][@type='stick-location']"


class XMLOtherPercussion(XMLElement):
    """
    The other-percussion element represents percussion pictograms not defined elsewhere.
    
    ``complexType``: The other-text type represents a text element with a smufl attribute group. This type is used by MusicXML direction extension elements to allow specification of specific SMuFL glyphs without needed to add every glyph as a MusicXML element.
    """
    
    TYPE = XSDComplexTypeOtherText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='other-percussion'][@type='other-text']"


class XMLMeasureLayout(XMLElement):
    """
    ``complexType``: The measure-layout type includes the horizontal distance from the previous measure. It applies to the current measure only.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=measure-distance@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeMeasureLayout
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='measure-layout'][@type='measure-layout']"


class XMLMeasureNumbering(XMLElement):
    """
    ``complexType``: The measure-numbering type describes how frequently measure numbers are displayed on this part. The text attribute from the measure element is used for display, or the number attribute if the text attribute is not present. Measures with an implicit attribute set to "yes" never display a measure number, regardless of the measure-numbering setting.
    
    The optional staff attribute refers to staff numbers within the part, from top to bottom on the system. It indicates which staff is used as the reference point for vertical positioning. A value of 1 is assumed if not present.
    
    The optional multiple-rest-always and multiple-rest-range attributes describe how measure numbers are shown on multiple rests when the measure-numbering value is not set to none. The multiple-rest-always attribute is set to yes when the measure number should always be shown, even if the multiple rest starts midway through a system when measure numbering is set to system level. The multiple-rest-range attribute is set to yes when measure numbers on multiple rests display the range of numbers for the first and last measure, rather than just the number of the first measure.
    
    ``simpleContent``: The measure-numbering-value type describes how measure numbers are displayed on this part: no numbers, numbers every measure, or numbers every system.
        
        Permitted Values: ['none', 'measure', 'system']
    
    """
    
    TYPE = XSDComplexTypeMeasureNumbering
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='measure-numbering'][@type='measure-numbering']"


class XMLPartNameDisplay(XMLElement):
    """
    ``complexType``: The name-display type is used for exact formatting of multi-font text in part and group names to the left of the system. The print-object attribute can be used to determine what, if anything, is printed at the start of each system. Enclosure for the display-text element is none by default. Language for the display-text element is Italian ("it") by default.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Choice@minOccurs=0@maxOccurs=unbounded
               Element@name=display-text@minOccurs=1@maxOccurs=1
               Element@name=accidental-text@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeNameDisplay
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='part-name-display'][@type='name-display']"


class XMLPartAbbreviationDisplay(XMLElement):
    """
    ``complexType``: The name-display type is used for exact formatting of multi-font text in part and group names to the left of the system. The print-object attribute can be used to determine what, if anything, is printed at the start of each system. Enclosure for the display-text element is none by default. Language for the display-text element is Italian ("it") by default.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Choice@minOccurs=0@maxOccurs=unbounded
               Element@name=display-text@minOccurs=1@maxOccurs=1
               Element@name=accidental-text@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeNameDisplay
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='part-abbreviation-display'][@type='name-display']"


class XMLRootStep(XMLElement):
    """
    ``complexType``: The root-step type represents the pitch step of the root of the current chord within the harmony element. The text attribute indicates how the root should appear in a score if not using the element contents.
    
    ``simpleContent``: The step type represents a step of the diatonic scale, represented using the English letters A through G.
        
        Permitted Values: ['A', 'B', 'C', 'D', 'E', 'F', 'G']
    
    """
    
    TYPE = XSDComplexTypeRootStep
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='root-step'][@type='root-step']"


class XMLRootAlter(XMLElement):
    """
    The root-alter element represents the chromatic alteration of the root of the current chord within the harmony element. In some chord styles, the text for the root-step element may include root-alter information. In that case, the print-object attribute of the root-alter element can be set to no. The location attribute indicates whether the alteration should appear to the left or the right of the root-step; it is right by default.
    
    ``complexType``: The harmony-alter type represents the chromatic alteration of the root, numeral, or bass of the current harmony-chord group within the harmony element. In some chord styles, the text of the preceding element may include alteration information. In that case, the print-object attribute of this type can be set to no. The location attribute indicates whether the alteration should appear to the left or the right of the preceding element. Its default value varies by element.
    
    ``simpleContent``: The semitones type is a number representing semitones, used for chromatic alteration. A value of -1 corresponds to a flat and a value of 1 to a sharp. Decimal values like 0.5 (quarter tone sharp) are used for microtones.
    """
    
    TYPE = XSDComplexTypeHarmonyAlter
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='root-alter'][@type='harmony-alter']"


class XMLAccord(XMLElement):
    """
    ``complexType``: The accord type represents the tuning of a single string in the scordatura element. It uses the same group of elements as the staff-tuning element. Strings are numbered from high to low.

    ``XSD structure:``

    .. code-block::

       Group@name=tuning@minOccurs=1@maxOccurs=1
           Sequence@minOccurs=1@maxOccurs=1
               Element@name=tuning-step@minOccurs=1@maxOccurs=1
               Element@name=tuning-alter@minOccurs=0@maxOccurs=1
               Element@name=tuning-octave@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeAccord
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='accord'][@type='accord']"


class XMLInstrumentChange(XMLElement):
    """
    ``complexType``: The instrument-change element type represents a change to the virtual instrument sound for a given score-instrument. The id attribute refers to the score-instrument affected by the change. All instrument-change child elements can also be initially specified within the score-instrument element.

    ``XSD structure:``

    .. code-block::

       Group@name=virtual-instrument-data@minOccurs=1@maxOccurs=1
           Sequence@minOccurs=1@maxOccurs=1
               Element@name=instrument-sound@minOccurs=0@maxOccurs=1
               Choice@minOccurs=0@maxOccurs=1
                   Element@name=solo@minOccurs=1@maxOccurs=1
                   Element@name=ensemble@minOccurs=1@maxOccurs=1
               Element@name=virtual-instrument@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeInstrumentChange
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='instrument-change'][@type='instrument-change']"


class XMLMidiDevice(XMLElement):
    """
    ``complexType``: The midi-device type corresponds to the DeviceName meta event in Standard MIDI Files. The optional port attribute is a number from 1 to 16 that can be used with the unofficial MIDI 1.0 port (or cable) meta event. Unlike the DeviceName meta event, there can be multiple midi-device elements per MusicXML part. The optional id attribute refers to the score-instrument assigned to this device. If missing, the device assignment affects all score-instrument elements in the score-part.
    """
    
    TYPE = XSDComplexTypeMidiDevice
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='midi-device'][@type='midi-device']"


class XMLMidiInstrument(XMLElement):
    """
    ``complexType``: The midi-instrument type defines MIDI 1.0 instrument playback. The midi-instrument element can be a part of either the score-instrument element at the start of a part, or the sound element within a part. The id attribute refers to the score-instrument affected by the change.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=midi-channel@minOccurs=0@maxOccurs=1
           Element@name=midi-name@minOccurs=0@maxOccurs=1
           Element@name=midi-bank@minOccurs=0@maxOccurs=1
           Element@name=midi-program@minOccurs=0@maxOccurs=1
           Element@name=midi-unpitched@minOccurs=0@maxOccurs=1
           Element@name=volume@minOccurs=0@maxOccurs=1
           Element@name=pan@minOccurs=0@maxOccurs=1
           Element@name=elevation@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeMidiInstrument
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='midi-instrument'][@type='midi-instrument']"


class XMLPlay(XMLElement):
    """
    ``complexType``: The play type specifies playback techniques to be used in conjunction with the instrument-sound element. When used as part of a sound element, it applies to all notes going forward in score order. In multi-instrument parts, the affected instrument should be specified using the id attribute. When used as part of a note element, it applies to the current note only.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Choice@minOccurs=0@maxOccurs=unbounded
               Element@name=ipa@minOccurs=1@maxOccurs=1
               Element@name=mute@minOccurs=1@maxOccurs=1
               Element@name=semi-pitched@minOccurs=1@maxOccurs=1
               Element@name=other-play@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypePlay
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='play'][@type='play']"


class XMLSwing(XMLElement):
    """
    ``complexType``: The swing element specifies whether or not to use swing playback, where consecutive on-beat / off-beat eighth or 16th notes are played with unequal nominal durations. 
    
    The straight element specifies that no swing is present, so consecutive notes have equal durations.
    
    The first and second elements are positive integers that specify the ratio between durations of consecutive notes. For example, a first element with a value of 2 and a second element with a value of 1 applied to eighth notes specifies a quarter note / eighth note tuplet playback, where the first note is twice as long as the second note. Ratios should be specified with the smallest integers possible. For example, a ratio of 6 to 4 should be specified as 3 to 2 instead.
    
    The optional swing-type element specifies the note type, either eighth or 16th, to which the ratio is applied. The value is eighth if this element is not present.
    
    The optional swing-style element is a string describing the style of swing used.
    
    The swing element has no effect for playback of grace notes, notes where a type element is not present, and notes where the specified duration is different than the nominal value associated with the specified type. If a swung note has attack and release attributes, those values modify the swung playback.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Choice@minOccurs=1@maxOccurs=1
               Element@name=straight@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=first@minOccurs=1@maxOccurs=1
                   Element@name=second@minOccurs=1@maxOccurs=1
                   Element@name=swing-type@minOccurs=0@maxOccurs=1
           Element@name=swing-style@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeSwing
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='swing'][@type='swing']"


class XMLStickType(XMLElement):
    """
    ``simpleType``: The stick-type type represents the shape of pictograms where the material in the stick, mallet, or beater is represented in the pictogram.
        
        Permitted Values: ['bass drum', 'double bass drum', 'glockenspiel', 'gum', 'hammer', 'superball', 'timpani', 'wound', 'xylophone', 'yarn']
    
    """
    
    TYPE = XSDSimpleTypeStickType
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='stick-type'][@type='stick-type']"


class XMLStickMaterial(XMLElement):
    """
    ``simpleType``: The stick-material type represents the material being displayed in a stick pictogram.
        
        Permitted Values: ['soft', 'medium', 'hard', 'shaded', 'x']
    
    """
    
    TYPE = XSDSimpleTypeStickMaterial
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='stick-material'][@type='stick-material']"


class XMLStraight(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='straight'][@type='empty']"


class XMLFirst(XMLElement):
    """
    
    """
    
    TYPE = XSDSimpleTypePositiveInteger
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='first'][@type='xs:positiveInteger']"


class XMLSecond(XMLElement):
    """
    
    """
    
    TYPE = XSDSimpleTypePositiveInteger
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='second'][@type='xs:positiveInteger']"


class XMLSwingType(XMLElement):
    """
    ``simpleType``: The swing-type-value type specifies the note type, either eighth or 16th, to which the ratio defined in the swing element is applied.
        
        Permitted Values: ['16th', 'eighth']
    
    """
    
    TYPE = XSDSimpleTypeSwingTypeValue
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='swing-type'][@type='swing-type-value']"


class XMLSwingStyle(XMLElement):
    """
    
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='swing-style'][@type='xs:string']"


class XMLEncodingDate(XMLElement):
    """
    ``simpleType``: Calendar dates are represented yyyy-mm-dd format, following ISO 8601. This is a W3C XML Schema date type, but without the optional timezone data.
        
            
    Pattern: [^:Z]*
    
    """
    
    TYPE = XSDSimpleTypeYyyyMmDd
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='encoding-date'][@type='yyyy-mm-dd']"


class XMLEncoder(XMLElement):
    """
    ``complexType``: The typed-text type represents a text element with a type attribute.
    """
    
    TYPE = XSDComplexTypeTypedText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='encoder'][@type='typed-text']"


class XMLSoftware(XMLElement):
    """
    
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='software'][@type='xs:string']"


class XMLEncodingDescription(XMLElement):
    """
    
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='encoding-description'][@type='xs:string']"


class XMLSupports(XMLElement):
    """
    ``complexType``: The supports type indicates if a MusicXML encoding supports a particular MusicXML element. This is recommended for elements like beam, stem, and accidental, where the absence of an element is ambiguous if you do not know if the encoding supports that element. For Version 2.0, the supports element is expanded to allow programs to indicate support for particular attributes or particular values. This lets applications communicate, for example, that all system and/or page breaks are contained in the MusicXML file.
    """
    
    TYPE = XSDComplexTypeSupports
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='supports'][@type='supports']"


class XMLCreator(XMLElement):
    """
    The creator element is borrowed from Dublin Core. It is used for the creators of the score. The type attribute is used to distinguish different creative contributions. Thus, there can be multiple creators within an identification. Standard type values are composer, lyricist, and arranger. Other type values may be used for different types of creative roles. The type attribute should usually be used even if there is just a single creator element. The MusicXML format does not use the creator / contributor distinction from Dublin Core.
    
    ``complexType``: The typed-text type represents a text element with a type attribute.
    """
    
    TYPE = XSDComplexTypeTypedText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='creator'][@type='typed-text']"


class XMLRights(XMLElement):
    """
    The rights element is borrowed from Dublin Core. It contains copyright and other intellectual property notices. Words, music, and derivatives can have different types, so multiple rights elements with different type attributes are supported. Standard type values are music, words, and arrangement, but other types may be used. The type attribute is only needed when there are multiple rights elements.
    
    ``complexType``: The typed-text type represents a text element with a type attribute.
    """
    
    TYPE = XSDComplexTypeTypedText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='rights'][@type='typed-text']"


class XMLEncoding(XMLElement):
    """
    ``complexType``: The encoding element contains information about who did the digital encoding, when, with what software, and in what aspects. Standard type values for the encoder element are music, words, and arrangement, but other types may be used. The type attribute is only needed when there are multiple encoder elements.

    ``XSD structure:``

    .. code-block::

       Choice@minOccurs=0@maxOccurs=unbounded
           Element@name=encoding-date@minOccurs=1@maxOccurs=1
           Element@name=encoder@minOccurs=1@maxOccurs=1
           Element@name=software@minOccurs=1@maxOccurs=1
           Element@name=encoding-description@minOccurs=1@maxOccurs=1
           Element@name=supports@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeEncoding
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='encoding'][@type='encoding']"


class XMLSource(XMLElement):
    """
    The source for the music that is encoded. This is similar to the Dublin Core source element.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='source'][@type='xs:string']"


class XMLRelation(XMLElement):
    """
    A related resource for the music that is encoded. This is similar to the Dublin Core relation element. Standard type values are music, words, and arrangement, but other types may be used.
    
    ``complexType``: The typed-text type represents a text element with a type attribute.
    """
    
    TYPE = XSDComplexTypeTypedText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='relation'][@type='typed-text']"


class XMLMiscellaneous(XMLElement):
    """
    ``complexType``: If a program has other metadata not yet supported in the MusicXML format, it can go in the miscellaneous element. The miscellaneous type puts each separate part of metadata into its own miscellaneous-field type.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=miscellaneous-field@minOccurs=0@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypeMiscellaneous
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='miscellaneous'][@type='miscellaneous']"


class XMLMiscellaneousField(XMLElement):
    """
    ``complexType``: If a program has other metadata not yet supported in the MusicXML format, each type of metadata can go in a miscellaneous-field element. The required name attribute indicates the type of metadata the element content represents.
    """
    
    TYPE = XSDComplexTypeMiscellaneousField
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='miscellaneous-field'][@type='miscellaneous-field']"


class XMLLineWidth(XMLElement):
    """
    ``complexType``: The line-width type indicates the width of a line type in tenths. The type attribute defines what type of line is being defined. Values include beam, bracket, dashes, enclosure, ending, extend, heavy barline, leger, light barline, octave shift, pedal, slur middle, slur tip, staff, stem, tie middle, tie tip, tuplet bracket, and wedge. The text content is expressed in tenths.
    
    ``simpleContent``: The tenths type is a number representing tenths of interline staff space (positive or negative). Both integer and decimal values are allowed, such as 5 for a half space and 2.5 for a quarter space. Interline space is measured from the middle of a staff line.
    
    Distances in a MusicXML file are measured in tenths of staff space. Tenths are then scaled to millimeters within the scaling element, used in the defaults element at the start of a score. Individual staves can apply a scaling factor to adjust staff size. When a MusicXML element or attribute refers to tenths, it means the global tenths defined by the scaling element, not the local tenths as adjusted by the staff-size element.
    """
    
    TYPE = XSDComplexTypeLineWidth
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='line-width'][@type='line-width']"


class XMLNoteSize(XMLElement):
    """
    ``complexType``: The note-size type indicates the percentage of the regular note size to use for notes with a cue and large size as defined in the type element. The grace type is used for notes of cue size that that include a grace element. The cue type is used for all other notes with cue size, whether defined explicitly or implicitly via a cue element. The large type is used for notes of large size. The text content represent the numeric percentage. A value of 100 would be identical to the size of a regular note as defined by the music font.
    
    ``simpleContent``: The non-negative-decimal type specifies a non-negative decimal value.
    """
    
    TYPE = XSDComplexTypeNoteSize
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='note-size'][@type='note-size']"


class XMLDistance(XMLElement):
    """
    ``complexType``: The distance element represents standard distances between notation elements in tenths. The type attribute defines what type of distance is being defined. Valid values include hyphen (for hyphens in lyrics) and beam.
    
    ``simpleContent``: The tenths type is a number representing tenths of interline staff space (positive or negative). Both integer and decimal values are allowed, such as 5 for a half space and 2.5 for a quarter space. Interline space is measured from the middle of a staff line.
    
    Distances in a MusicXML file are measured in tenths of staff space. Tenths are then scaled to millimeters within the scaling element, used in the defaults element at the start of a score. Individual staves can apply a scaling factor to adjust staff size. When a MusicXML element or attribute refers to tenths, it means the global tenths defined by the scaling element, not the local tenths as adjusted by the staff-size element.
    """
    
    TYPE = XSDComplexTypeDistance
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='distance'][@type='distance']"


class XMLGlyph(XMLElement):
    """
    ``complexType``: The glyph element represents what SMuFL glyph should be used for different variations of symbols that are semantically identical. The type attribute specifies what type of glyph is being defined. The element value specifies what SMuFL glyph to use, including recommended stylistic alternates. The SMuFL glyph name should match the type. For instance, a type of quarter-rest would use values restQuarter, restQuarterOld, or restQuarterZ. A type of g-clef-ottava-bassa would use values gClef8vb, gClef8vbOld, or gClef8vbCClef. A type of octave-shift-up-8 would use values ottava, ottavaBassa, ottavaBassaBa, ottavaBassaVb, or octaveBassa.
    
    ``simpleContent``: The smufl-glyph-name type is used for attributes that reference a specific Standard Music Font Layout (SMuFL) character. The value is a SMuFL canonical glyph name, not a code point. For instance, the value for a standard piano pedal mark would be keyboardPedalPed, not U+E650.
    """
    
    TYPE = XSDComplexTypeGlyph
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='glyph'][@type='glyph']"


class XMLOtherAppearance(XMLElement):
    """
    ``complexType``: The other-appearance type is used to define any graphical settings not yet in the current version of the MusicXML format. This allows extended representation, though without application interoperability.
    """
    
    TYPE = XSDComplexTypeOtherAppearance
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='other-appearance'][@type='other-appearance']"


class XMLMeasureDistance(XMLElement):
    """
    The measure-distance element specifies the horizontal distance from the previous measure. This value is only used for systems where there is horizontal whitespace in the middle of a system, as in systems with codas. To specify the measure width, use the width attribute of the measure element.
    
    ``simpleType``: The tenths type is a number representing tenths of interline staff space (positive or negative). Both integer and decimal values are allowed, such as 5 for a half space and 2.5 for a quarter space. Interline space is measured from the middle of a staff line.
    
    Distances in a MusicXML file are measured in tenths of staff space. Tenths are then scaled to millimeters within the scaling element, used in the defaults element at the start of a score. Individual staves can apply a scaling factor to adjust staff size. When a MusicXML element or attribute refers to tenths, it means the global tenths defined by the scaling element, not the local tenths as adjusted by the staff-size element.
    """
    
    TYPE = XSDSimpleTypeTenths
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='measure-distance'][@type='tenths']"


class XMLPageHeight(XMLElement):
    """
    ``simpleType``: The tenths type is a number representing tenths of interline staff space (positive or negative). Both integer and decimal values are allowed, such as 5 for a half space and 2.5 for a quarter space. Interline space is measured from the middle of a staff line.
    
    Distances in a MusicXML file are measured in tenths of staff space. Tenths are then scaled to millimeters within the scaling element, used in the defaults element at the start of a score. Individual staves can apply a scaling factor to adjust staff size. When a MusicXML element or attribute refers to tenths, it means the global tenths defined by the scaling element, not the local tenths as adjusted by the staff-size element.
    """
    
    TYPE = XSDSimpleTypeTenths
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='page-height'][@type='tenths']"


class XMLPageWidth(XMLElement):
    """
    ``simpleType``: The tenths type is a number representing tenths of interline staff space (positive or negative). Both integer and decimal values are allowed, such as 5 for a half space and 2.5 for a quarter space. Interline space is measured from the middle of a staff line.
    
    Distances in a MusicXML file are measured in tenths of staff space. Tenths are then scaled to millimeters within the scaling element, used in the defaults element at the start of a score. Individual staves can apply a scaling factor to adjust staff size. When a MusicXML element or attribute refers to tenths, it means the global tenths defined by the scaling element, not the local tenths as adjusted by the staff-size element.
    """
    
    TYPE = XSDSimpleTypeTenths
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='page-width'][@type='tenths']"


class XMLPageMargins(XMLElement):
    """
    ``complexType``: Page margins are specified either for both even and odd pages, or via separate odd and even page number values. The type attribute is not needed when used as part of a print element. If omitted when the page-margins type is used in the defaults element, "both" is the default value.

    ``XSD structure:``

    .. code-block::

       Group@name=all-margins@minOccurs=1@maxOccurs=1
           Sequence@minOccurs=1@maxOccurs=1
               Group@name=left-right-margins@minOccurs=1@maxOccurs=1
                   Sequence@minOccurs=1@maxOccurs=1
                       Element@name=left-margin@minOccurs=1@maxOccurs=1
                       Element@name=right-margin@minOccurs=1@maxOccurs=1
               Element@name=top-margin@minOccurs=1@maxOccurs=1
               Element@name=bottom-margin@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypePageMargins
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='page-margins'][@type='page-margins']"


class XMLMillimeters(XMLElement):
    """
    ``simpleType``: The millimeters type is a number representing millimeters. This is used in the scaling element to provide a default scaling from tenths to physical units.
    """
    
    TYPE = XSDSimpleTypeMillimeters
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='millimeters'][@type='millimeters']"


class XMLTenths(XMLElement):
    """
    ``simpleType``: The tenths type is a number representing tenths of interline staff space (positive or negative). Both integer and decimal values are allowed, such as 5 for a half space and 2.5 for a quarter space. Interline space is measured from the middle of a staff line.
    
    Distances in a MusicXML file are measured in tenths of staff space. Tenths are then scaled to millimeters within the scaling element, used in the defaults element at the start of a score. Individual staves can apply a scaling factor to adjust staff size. When a MusicXML element or attribute refers to tenths, it means the global tenths defined by the scaling element, not the local tenths as adjusted by the staff-size element.
    """
    
    TYPE = XSDSimpleTypeTenths
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='tenths'][@type='tenths']"


class XMLStaffDistance(XMLElement):
    """
    ``simpleType``: The tenths type is a number representing tenths of interline staff space (positive or negative). Both integer and decimal values are allowed, such as 5 for a half space and 2.5 for a quarter space. Interline space is measured from the middle of a staff line.
    
    Distances in a MusicXML file are measured in tenths of staff space. Tenths are then scaled to millimeters within the scaling element, used in the defaults element at the start of a score. Individual staves can apply a scaling factor to adjust staff size. When a MusicXML element or attribute refers to tenths, it means the global tenths defined by the scaling element, not the local tenths as adjusted by the staff-size element.
    """
    
    TYPE = XSDSimpleTypeTenths
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='staff-distance'][@type='tenths']"


class XMLLeftDivider(XMLElement):
    """
    ``complexType``: The empty-print-style-align-object type represents an empty element with print-object and print-style-align attribute groups.
    """
    
    TYPE = XSDComplexTypeEmptyPrintObjectStyleAlign
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='left-divider'][@type='empty-print-object-style-align']"


class XMLRightDivider(XMLElement):
    """
    ``complexType``: The empty-print-style-align-object type represents an empty element with print-object and print-style-align attribute groups.
    """
    
    TYPE = XSDComplexTypeEmptyPrintObjectStyleAlign
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='right-divider'][@type='empty-print-object-style-align']"


class XMLSystemMargins(XMLElement):
    """
    ``complexType``: System margins are relative to the page margins. Positive values indent and negative values reduce the margin size.

    ``XSD structure:``

    .. code-block::

       Group@name=left-right-margins@minOccurs=1@maxOccurs=1
           Sequence@minOccurs=1@maxOccurs=1
               Element@name=left-margin@minOccurs=1@maxOccurs=1
               Element@name=right-margin@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeSystemMargins
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='system-margins'][@type='system-margins']"


class XMLSystemDistance(XMLElement):
    """
    ``simpleType``: The tenths type is a number representing tenths of interline staff space (positive or negative). Both integer and decimal values are allowed, such as 5 for a half space and 2.5 for a quarter space. Interline space is measured from the middle of a staff line.
    
    Distances in a MusicXML file are measured in tenths of staff space. Tenths are then scaled to millimeters within the scaling element, used in the defaults element at the start of a score. Individual staves can apply a scaling factor to adjust staff size. When a MusicXML element or attribute refers to tenths, it means the global tenths defined by the scaling element, not the local tenths as adjusted by the staff-size element.
    """
    
    TYPE = XSDSimpleTypeTenths
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='system-distance'][@type='tenths']"


class XMLTopSystemDistance(XMLElement):
    """
    ``simpleType``: The tenths type is a number representing tenths of interline staff space (positive or negative). Both integer and decimal values are allowed, such as 5 for a half space and 2.5 for a quarter space. Interline space is measured from the middle of a staff line.
    
    Distances in a MusicXML file are measured in tenths of staff space. Tenths are then scaled to millimeters within the scaling element, used in the defaults element at the start of a score. Individual staves can apply a scaling factor to adjust staff size. When a MusicXML element or attribute refers to tenths, it means the global tenths defined by the scaling element, not the local tenths as adjusted by the staff-size element.
    """
    
    TYPE = XSDSimpleTypeTenths
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='top-system-distance'][@type='tenths']"


class XMLSystemDividers(XMLElement):
    """
    ``complexType``: The system-dividers element indicates the presence or absence of system dividers (also known as system separation marks) between systems displayed on the same page. Dividers on the left and right side of the page are controlled by the left-divider and right-divider elements respectively. The default vertical position is half the system-distance value from the top of the system that is below the divider. The default horizontal position is the left and right system margin, respectively.
    
    When used in the print element, the system-dividers element affects the dividers that would appear between the current system and the previous system.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=left-divider@minOccurs=1@maxOccurs=1
           Element@name=right-divider@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeSystemDividers
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='system-dividers'][@type='system-dividers']"


class XMLAccent(XMLElement):
    """
    The accent element indicates a regular horizontal accent mark.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='accent'][@type='empty-placement']"


class XMLStrongAccent(XMLElement):
    """
    The strong-accent element indicates a vertical accent mark.
    
    ``complexType``: The strong-accent type indicates a vertical accent mark. The type attribute indicates if the point of the accent is down or up.
    """
    
    TYPE = XSDComplexTypeStrongAccent
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='strong-accent'][@type='strong-accent']"


class XMLStaccato(XMLElement):
    """
    The staccato element is used for a dot articulation, as opposed to a stroke or a wedge.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='staccato'][@type='empty-placement']"


class XMLTenuto(XMLElement):
    """
    The tenuto element indicates a tenuto line symbol.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='tenuto'][@type='empty-placement']"


class XMLDetachedLegato(XMLElement):
    """
    The detached-legato element indicates the combination of a tenuto line and staccato dot symbol.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='detached-legato'][@type='empty-placement']"


class XMLStaccatissimo(XMLElement):
    """
    The staccatissimo element is used for a wedge articulation, as opposed to a dot or a stroke.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='staccatissimo'][@type='empty-placement']"


class XMLSpiccato(XMLElement):
    """
    The spiccato element is used for a stroke articulation, as opposed to a dot or a wedge.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='spiccato'][@type='empty-placement']"


class XMLScoop(XMLElement):
    """
    The scoop element is an indeterminate slide attached to a single note. The scoop appears before the main note and comes from below the main pitch.
    
    ``complexType``: The empty-line type represents an empty element with line-shape, line-type, line-length, dashed-formatting, print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyLine
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='scoop'][@type='empty-line']"


class XMLPlop(XMLElement):
    """
    The plop element is an indeterminate slide attached to a single note. The plop appears before the main note and comes from above the main pitch.
    
    ``complexType``: The empty-line type represents an empty element with line-shape, line-type, line-length, dashed-formatting, print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyLine
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='plop'][@type='empty-line']"


class XMLDoit(XMLElement):
    """
    The doit element is an indeterminate slide attached to a single note. The doit appears after the main note and goes above the main pitch.
    
    ``complexType``: The empty-line type represents an empty element with line-shape, line-type, line-length, dashed-formatting, print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyLine
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='doit'][@type='empty-line']"


class XMLFalloff(XMLElement):
    """
    The falloff element is an indeterminate slide attached to a single note. The falloff appears after the main note and goes below the main pitch.
    
    ``complexType``: The empty-line type represents an empty element with line-shape, line-type, line-length, dashed-formatting, print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyLine
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='falloff'][@type='empty-line']"


class XMLBreathMark(XMLElement):
    """
    ``complexType``: The breath-mark element indicates a place to take a breath.
    
    ``simpleContent``: The breath-mark-value type represents the symbol used for a breath mark.
        
        Permitted Values: ['', 'comma', 'tick', 'upbow', 'salzedo']
    
    """
    
    TYPE = XSDComplexTypeBreathMark
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='breath-mark'][@type='breath-mark']"


class XMLCaesura(XMLElement):
    """
    ``complexType``: The caesura element indicates a slight pause. It is notated using a "railroad tracks" symbol or other variations specified in the element content.
    
    ``simpleContent``: The caesura-value type represents the shape of the caesura sign.
        
        Permitted Values: ['normal', 'thick', 'short', 'curved', 'single', '']
    
    """
    
    TYPE = XSDComplexTypeCaesura
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='caesura'][@type='caesura']"


class XMLStress(XMLElement):
    """
    The stress element indicates a stressed note.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='stress'][@type='empty-placement']"


class XMLUnstress(XMLElement):
    """
    The unstress element indicates an unstressed note. It is often notated using a u-shaped symbol.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='unstress'][@type='empty-placement']"


class XMLSoftAccent(XMLElement):
    """
    The soft-accent element indicates a soft accent that is not as heavy as a normal accent. It is often notated as <>. It can be combined with other articulations to implement the first eight symbols in the SMuFL Articulation supplement range.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='soft-accent'][@type='empty-placement']"


class XMLOtherArticulation(XMLElement):
    """
    The other-articulation element is used to define any articulations not yet in the MusicXML format. The smufl attribute can be used to specify a particular articulation, allowing application interoperability without requiring every SMuFL articulation to have a MusicXML element equivalent. Using the other-articulation element without the smufl attribute allows for extended representation, though without application interoperability.
    
    ``complexType``: The other-placement-text type represents a text element with print-style, placement, and smufl attribute groups. This type is used by MusicXML notation extension elements to allow specification of specific SMuFL glyphs without needed to add every glyph as a MusicXML element.
    """
    
    TYPE = XSDComplexTypeOtherPlacementText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='other-articulation'][@type='other-placement-text']"


class XMLArrowDirection(XMLElement):
    """
    ``simpleType``: The arrow-direction type represents the direction in which an arrow points, using Unicode arrow terminology.
        
        Permitted Values: ['left', 'up', 'right', 'down', 'northwest', 'northeast', 'southeast', 'southwest', 'left right', 'up down', 'northwest southeast', 'northeast southwest', 'other']
    
    """
    
    TYPE = XSDSimpleTypeArrowDirection
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='arrow-direction'][@type='arrow-direction']"


class XMLArrowStyle(XMLElement):
    """
    ``simpleType``: The arrow-style type represents the style of an arrow, using Unicode arrow terminology. Filled and hollow arrows indicate polygonal single arrows. Paired arrows are duplicate single arrows in the same direction. Combined arrows apply to double direction arrows like left right, indicating that an arrow in one direction should be combined with an arrow in the other direction.
        
        Permitted Values: ['single', 'double', 'filled', 'hollow', 'paired', 'combined', 'other']
    
    """
    
    TYPE = XSDSimpleTypeArrowStyle
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='arrow-style'][@type='arrow-style']"


class XMLArrowhead(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='arrowhead'][@type='empty']"


class XMLCircularArrow(XMLElement):
    """
    ``simpleType``: The circular-arrow type represents the direction in which a circular arrow points, using Unicode arrow terminology.
        
        Permitted Values: ['clockwise', 'anticlockwise']
    
    """
    
    TYPE = XSDSimpleTypeCircularArrow
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='circular-arrow'][@type='circular-arrow']"


class XMLBendAlter(XMLElement):
    """
    The bend-alter element indicates the number of semitones in the bend, similar to the alter element. As with the alter element, numbers like 0.5 can be used to indicate microtones. Negative values indicate pre-bends or releases. The pre-bend and release elements are used to distinguish what is intended. Because the bend-alter element represents the number of steps in the bend, a release after a bend has a negative bend-alter value, not a zero value.
    
    ``simpleType``: The semitones type is a number representing semitones, used for chromatic alteration. A value of -1 corresponds to a flat and a value of 1 to a sharp. Decimal values like 0.5 (quarter tone sharp) are used for microtones.
    """
    
    TYPE = XSDSimpleTypeSemitones
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='bend-alter'][@type='semitones']"


class XMLPreBend(XMLElement):
    """
    The pre-bend element indicates that a bend is a pre-bend rather than a normal bend or a release.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='pre-bend'][@type='empty']"


class XMLRelease(XMLElement):
    """
    ``complexType``: The release type indicates that a bend is a release rather than a normal bend or pre-bend. The offset attribute specifies where the release starts in terms of divisions relative to the current note. The first-beat and last-beat attributes of the parent bend element are relative to the original note position, not this offset value.
    """
    
    TYPE = XSDComplexTypeRelease
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='release'][@type='release']"


class XMLWithBar(XMLElement):
    """
    The with-bar element indicates that the bend is to be done at the bridge with a whammy or vibrato bar. The content of the element indicates how this should be notated. Content values of "scoop" and "dip" refer to the SMuFL guitarVibratoBarScoop and guitarVibratoBarDip glyphs.
    
    ``complexType``: The placement-text type represents a text element with print-style and placement attribute groups.
    """
    
    TYPE = XSDComplexTypePlacementText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='with-bar'][@type='placement-text']"


class XMLPrefix(XMLElement):
    """
    Values for the prefix element include plus and the accidental values sharp, flat, natural, double-sharp, flat-flat, and sharp-sharp. The prefix element may contain additional values for symbols specific to particular figured bass styles.
    
    ``complexType``: The style-text type represents a text element with a print-style attribute group.
    """
    
    TYPE = XSDComplexTypeStyleText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='prefix'][@type='style-text']"


class XMLFigureNumber(XMLElement):
    """
    A figure-number is a number. Overstrikes of the figure number are represented in the suffix element.
    
    ``complexType``: The style-text type represents a text element with a print-style attribute group.
    """
    
    TYPE = XSDComplexTypeStyleText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='figure-number'][@type='style-text']"


class XMLSuffix(XMLElement):
    """
    Values for the suffix element include plus and the accidental values sharp, flat, natural, double-sharp, flat-flat, and sharp-sharp. Suffixes include both symbols that come after the figure number and those that overstrike the figure number. The suffix values slash, back-slash, and vertical are used for slashed numbers indicating chromatic alteration. The orientation and display of the slash usually depends on the figure number. The suffix element may contain additional values for symbols specific to particular figured bass styles.
    
    ``complexType``: The style-text type represents a text element with a print-style attribute group.
    """
    
    TYPE = XSDComplexTypeStyleText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='suffix'][@type='style-text']"


class XMLExtend(XMLElement):
    """
    ``complexType``: The extend type represents lyric word extension / melisma lines as well as figured bass extensions. The optional type and position attributes are added in Version 3.0 to provide better formatting control.
    """
    
    TYPE = XSDComplexTypeExtend
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='extend'][@type='extend']"


class XMLFigure(XMLElement):
    """
    ``complexType``: The figure type represents a single figure within a figured-bass element.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=prefix@minOccurs=0@maxOccurs=1
           Element@name=figure-number@minOccurs=0@maxOccurs=1
           Element@name=suffix@minOccurs=0@maxOccurs=1
           Element@name=extend@minOccurs=0@maxOccurs=1
           Group@name=editorial@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Group@name=footnote@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=footnote@minOccurs=1@maxOccurs=1
                   Group@name=level@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=level@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeFigure
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='figure'][@type='figure']"


class XMLHarmonClosed(XMLElement):
    """
    ``complexType``: The harmon-closed type represents whether the harmon mute is closed, open, or half-open. The optional location attribute indicates which portion of the symbol is filled in when the element value is half.
    
    ``simpleContent``: The harmon-closed-value type represents whether the harmon mute is closed, open, or half-open.
        
        Permitted Values: ['yes', 'no', 'half']
    
    """
    
    TYPE = XSDComplexTypeHarmonClosed
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='harmon-closed'][@type='harmon-closed']"


class XMLNatural(XMLElement):
    """
    The natural element indicates that this is a natural harmonic. These are usually notated at base pitch rather than sounding pitch.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='natural'][@type='empty']"


class XMLArtificial(XMLElement):
    """
    The artificial element indicates that this is an artificial harmonic.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='artificial'][@type='empty']"


class XMLBasePitch(XMLElement):
    """
    The base pitch is the pitch at which the string is played before touching to create the harmonic.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='base-pitch'][@type='empty']"


class XMLTouchingPitch(XMLElement):
    """
    The touching-pitch is the pitch at which the string is touched lightly to produce the harmonic.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='touching-pitch'][@type='empty']"


class XMLSoundingPitch(XMLElement):
    """
    The sounding-pitch is the pitch which is heard when playing the harmonic.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='sounding-pitch'][@type='empty']"


class XMLHoleType(XMLElement):
    """
    The content of the optional hole-type element indicates what the hole symbol represents in terms of instrument fingering or other techniques.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='hole-type'][@type='xs:string']"


class XMLHoleClosed(XMLElement):
    """
    ``complexType``: The hole-closed type represents whether the hole is closed, open, or half-open. The optional location attribute indicates which portion of the hole is filled in when the element value is half.
    
    ``simpleContent``: The hole-closed-value type represents whether the hole is closed, open, or half-open.
        
        Permitted Values: ['yes', 'no', 'half']
    
    """
    
    TYPE = XSDComplexTypeHoleClosed
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='hole-closed'][@type='hole-closed']"


class XMLHoleShape(XMLElement):
    """
    The optional hole-shape element indicates the shape of the hole symbol; the default is a circle.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='hole-shape'][@type='xs:string']"


class XMLAssess(XMLElement):
    """
    ``complexType``: By default, an assessment application should assess all notes without a cue child element, and not assess any note with a cue child element. The assess type allows this default assessment to be overridden for individual notes. The optional player and time-only attributes restrict the type to apply to a single player or set of times through a repeated section, respectively. If missing, the type applies to all players or all times through the repeated section, respectively. The player attribute references the id attribute of a player element defined within the matching score-part.
    """
    
    TYPE = XSDComplexTypeAssess
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='assess'][@type='assess']"


class XMLWait(XMLElement):
    """
    ``complexType``: The wait type specifies a point where the accompaniment should wait for a performer event before continuing. This typically happens at the start of new sections or after a held note or indeterminate music. These waiting points cannot always be inferred reliably from the contents of the displayed score. The optional player and time-only attributes restrict the type to apply to a single player or set of times through a repeated section, respectively.
    """
    
    TYPE = XSDComplexTypeWait
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='wait'][@type='wait']"


class XMLOtherListen(XMLElement):
    """
    ``complexType``: The other-listening type represents other types of listening control and interaction. The required type attribute indicates the type of listening to which the element content applies. The optional player and time-only attributes restrict the element to apply to a single player or set of times through a repeated section, respectively.
    """
    
    TYPE = XSDComplexTypeOtherListening
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='other-listen'][@type='other-listening']"


class XMLSyllabic(XMLElement):
    """
    ``simpleType``: Lyric hyphenation is indicated by the syllabic type. The single, begin, end, and middle values represent single-syllable words, word-beginning syllables, word-ending syllables, and mid-word syllables, respectively.
        
        Permitted Values: ['single', 'begin', 'end', 'middle']
    
    """
    
    TYPE = XSDSimpleTypeSyllabic
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='syllabic'][@type='syllabic']"


class XMLText(XMLElement):
    """
    ``complexType``: The text-element-data type represents a syllable or portion of a syllable for lyric text underlay. A hyphen in the string content should only be used for an actual hyphenated word. Language names for text elements come from ISO 639, with optional country subcodes from ISO 3166.
    """
    
    TYPE = XSDComplexTypeTextElementData
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='text'][@type='text-element-data']"


class XMLElision(XMLElement):
    """
    ``complexType``: The elision type represents an elision between lyric syllables. The text content specifies the symbol used to display the elision. Common values are a no-break space (Unicode 00A0), an underscore (Unicode 005F), or an undertie (Unicode 203F). If the text content is empty, the smufl attribute is used to specify the symbol to use. Its value is a SMuFL canonical glyph name that starts with lyrics. The SMuFL attribute is ignored if the elision glyph is already specified by the text content. If neither text content nor a smufl attribute are present, the elision glyph is application-specific.
    """
    
    TYPE = XSDComplexTypeElision
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='elision'][@type='elision']"


class XMLLaughing(XMLElement):
    """
    The laughing element represents a laughing voice.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='laughing'][@type='empty']"


class XMLHumming(XMLElement):
    """
    The humming element represents a humming voice.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='humming'][@type='empty']"


class XMLEndLine(XMLElement):
    """
    The end-line element comes from RP-017 for Standard MIDI File Lyric meta-events. It facilitates lyric display for Karaoke and similar applications.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='end-line'][@type='empty']"


class XMLEndParagraph(XMLElement):
    """
    The end-paragraph element comes from RP-017 for Standard MIDI File Lyric meta-events. It facilitates lyric display for Karaoke and similar applications.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='end-paragraph'][@type='empty']"


class XMLTied(XMLElement):
    """
    ``complexType``: The tied element represents the notated tie. The tie element represents the tie sound.
    
    The number attribute is rarely needed to disambiguate ties, since note pitches will usually suffice. The attribute is implied rather than defaulting to 1 as with most elements. It is available for use in more complex tied notation situations.
    
    Ties that join two notes of the same pitch together should be represented with a tied element on the first note with type="start" and a tied element on the second note with type="stop".  This can also be done if the two notes being tied are enharmonically equivalent, but have different step values. It is not recommended to use tied elements to join two notes with enharmonically inequivalent pitches.
    
    Ties that indicate that an instrument should be undamped are specified with a single tied element with type="let-ring".
    
    Ties that are visually attached to only one note, other than undamped ties, should be specified with two tied elements on the same note, first type="start" then type="stop". This can be used to represent ties into or out of repeated sections or codas.
    """
    
    TYPE = XSDComplexTypeTied
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='tied'][@type='tied']"


class XMLSlur(XMLElement):
    """
    ``complexType``: Slur types are empty. Most slurs are represented with two elements: one with a start type, and one with a stop type. Slurs can add more elements using a continue type. This is typically used to specify the formatting of cross-system slurs, or to specify the shape of very complex slurs.
    """
    
    TYPE = XSDComplexTypeSlur
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='slur'][@type='slur']"


class XMLTuplet(XMLElement):
    """
    ``complexType``: A tuplet element is present when a tuplet is to be displayed graphically, in addition to the sound data provided by the time-modification elements. The number attribute is used to distinguish nested tuplets. The bracket attribute is used to indicate the presence of a bracket. If unspecified, the results are implementation-dependent. The line-shape attribute is used to specify whether the bracket is straight or in the older curved or slurred style. It is straight by default.
    
    Whereas a time-modification element shows how the cumulative, sounding effect of tuplets and double-note tremolos compare to the written note type, the tuplet element describes how this is displayed. The tuplet element also provides more detailed representation information than the time-modification element, and is needed to represent nested tuplets and other complex tuplets accurately.
    
    The show-number attribute is used to display either the number of actual notes, the number of both actual and normal notes, or neither. It is actual by default. The show-type attribute is used to display either the actual type, both the actual and normal types, or neither. It is none by default.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=tuplet-actual@minOccurs=0@maxOccurs=1
           Element@name=tuplet-normal@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeTuplet
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='tuplet'][@type='tuplet']"


class XMLGlissando(XMLElement):
    """
    ``complexType``: Glissando and slide types both indicate rapidly moving from one pitch to the other so that individual notes are not discerned. A glissando sounds the distinct notes in between the two pitches and defaults to a wavy line. The optional text is printed alongside the line.
    """
    
    TYPE = XSDComplexTypeGlissando
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='glissando'][@type='glissando']"


class XMLSlide(XMLElement):
    """
    ``complexType``: Glissando and slide types both indicate rapidly moving from one pitch to the other so that individual notes are not discerned. A slide is continuous between the two pitches and defaults to a solid line. The optional text for a is printed alongside the line.
    """
    
    TYPE = XSDComplexTypeSlide
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='slide'][@type='slide']"


class XMLOrnaments(XMLElement):
    """
    ``complexType``: Ornaments can be any of several types, followed optionally by accidentals. The accidental-mark element's content is represented the same as an accidental element, but with a different name to reflect the different musical meaning.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=0@maxOccurs=unbounded
           Choice@minOccurs=1@maxOccurs=1
               Element@name=trill-mark@minOccurs=1@maxOccurs=1
               Element@name=turn@minOccurs=1@maxOccurs=1
               Element@name=delayed-turn@minOccurs=1@maxOccurs=1
               Element@name=inverted-turn@minOccurs=1@maxOccurs=1
               Element@name=delayed-inverted-turn@minOccurs=1@maxOccurs=1
               Element@name=vertical-turn@minOccurs=1@maxOccurs=1
               Element@name=inverted-vertical-turn@minOccurs=1@maxOccurs=1
               Element@name=shake@minOccurs=1@maxOccurs=1
               Element@name=wavy-line@minOccurs=1@maxOccurs=1
               Element@name=mordent@minOccurs=1@maxOccurs=1
               Element@name=inverted-mordent@minOccurs=1@maxOccurs=1
               Element@name=schleifer@minOccurs=1@maxOccurs=1
               Element@name=tremolo@minOccurs=1@maxOccurs=1
               Element@name=haydn@minOccurs=1@maxOccurs=1
               Element@name=other-ornament@minOccurs=1@maxOccurs=1
           Element@name=accidental-mark@minOccurs=0@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypeOrnaments
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='ornaments'][@type='ornaments']"


class XMLTechnical(XMLElement):
    """
    ``complexType``: Technical indications give performance information for individual instruments.

    ``XSD structure:``

    .. code-block::

       Choice@minOccurs=0@maxOccurs=unbounded
           Element@name=up-bow@minOccurs=1@maxOccurs=1
           Element@name=down-bow@minOccurs=1@maxOccurs=1
           Element@name=harmonic@minOccurs=1@maxOccurs=1
           Element@name=open-string@minOccurs=1@maxOccurs=1
           Element@name=thumb-position@minOccurs=1@maxOccurs=1
           Element@name=fingering@minOccurs=1@maxOccurs=1
           Element@name=pluck@minOccurs=1@maxOccurs=1
           Element@name=double-tongue@minOccurs=1@maxOccurs=1
           Element@name=triple-tongue@minOccurs=1@maxOccurs=1
           Element@name=stopped@minOccurs=1@maxOccurs=1
           Element@name=snap-pizzicato@minOccurs=1@maxOccurs=1
           Element@name=fret@minOccurs=1@maxOccurs=1
           Element@name=string@minOccurs=1@maxOccurs=1
           Element@name=hammer-on@minOccurs=1@maxOccurs=1
           Element@name=pull-off@minOccurs=1@maxOccurs=1
           Element@name=bend@minOccurs=1@maxOccurs=1
           Element@name=tap@minOccurs=1@maxOccurs=1
           Element@name=heel@minOccurs=1@maxOccurs=1
           Element@name=toe@minOccurs=1@maxOccurs=1
           Element@name=fingernails@minOccurs=1@maxOccurs=1
           Element@name=hole@minOccurs=1@maxOccurs=1
           Element@name=arrow@minOccurs=1@maxOccurs=1
           Element@name=handbell@minOccurs=1@maxOccurs=1
           Element@name=brass-bend@minOccurs=1@maxOccurs=1
           Element@name=flip@minOccurs=1@maxOccurs=1
           Element@name=smear@minOccurs=1@maxOccurs=1
           Element@name=open@minOccurs=1@maxOccurs=1
           Element@name=half-muted@minOccurs=1@maxOccurs=1
           Element@name=harmon-mute@minOccurs=1@maxOccurs=1
           Element@name=golpe@minOccurs=1@maxOccurs=1
           Element@name=other-technical@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeTechnical
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='technical'][@type='technical']"


class XMLArticulations(XMLElement):
    """
    ``complexType``: Articulations and accents are grouped together here.

    ``XSD structure:``

    .. code-block::

       Choice@minOccurs=0@maxOccurs=unbounded
           Element@name=accent@minOccurs=1@maxOccurs=1
           Element@name=strong-accent@minOccurs=1@maxOccurs=1
           Element@name=staccato@minOccurs=1@maxOccurs=1
           Element@name=tenuto@minOccurs=1@maxOccurs=1
           Element@name=detached-legato@minOccurs=1@maxOccurs=1
           Element@name=staccatissimo@minOccurs=1@maxOccurs=1
           Element@name=spiccato@minOccurs=1@maxOccurs=1
           Element@name=scoop@minOccurs=1@maxOccurs=1
           Element@name=plop@minOccurs=1@maxOccurs=1
           Element@name=doit@minOccurs=1@maxOccurs=1
           Element@name=falloff@minOccurs=1@maxOccurs=1
           Element@name=breath-mark@minOccurs=1@maxOccurs=1
           Element@name=caesura@minOccurs=1@maxOccurs=1
           Element@name=stress@minOccurs=1@maxOccurs=1
           Element@name=unstress@minOccurs=1@maxOccurs=1
           Element@name=soft-accent@minOccurs=1@maxOccurs=1
           Element@name=other-articulation@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeArticulations
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='articulations'][@type='articulations']"


class XMLArpeggiate(XMLElement):
    """
    ``complexType``: The arpeggiate type indicates that this note is part of an arpeggiated chord. The number attribute can be used to distinguish between two simultaneous chords arpeggiated separately (different numbers) or together (same number). The direction attribute is used if there is an arrow on the arpeggio sign. By default, arpeggios go from the lowest to highest note.  The length of the sign can be determined from the position attributes for the arpeggiate elements used with the top and bottom notes of the arpeggiated chord. If the unbroken attribute is set to yes, it indicates that the arpeggio continues onto another staff within the part. This serves as a hint to applications and is not required for cross-staff arpeggios.
    """
    
    TYPE = XSDComplexTypeArpeggiate
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='arpeggiate'][@type='arpeggiate']"


class XMLNonArpeggiate(XMLElement):
    """
    ``complexType``: The non-arpeggiate type indicates that this note is at the top or bottom of a bracket indicating to not arpeggiate these notes. Since this does not involve playback, it is only used on the top or bottom notes, not on each note as for the arpeggiate type.
    """
    
    TYPE = XSDComplexTypeNonArpeggiate
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='non-arpeggiate'][@type='non-arpeggiate']"


class XMLAccidentalMark(XMLElement):
    """
    ``complexType``: An accidental-mark can be used as a separate notation or as part of an ornament. When used in an ornament, position and placement are relative to the ornament, not relative to the note.
    
    ``simpleContent``: The accidental-value type represents notated accidentals supported by MusicXML. In the MusicXML 2.0 DTD this was a string with values that could be included. The XSD strengthens the data typing to an enumerated list. The quarter- and three-quarters- accidentals are Tartini-style quarter-tone accidentals. The -down and -up accidentals are quarter-tone accidentals that include arrows pointing down or up. The slash- accidentals are used in Turkish classical music. The numbered sharp and flat accidentals are superscripted versions of the accidental signs, used in Turkish folk music. The sori and koron accidentals are microtonal sharp and flat accidentals used in Iranian and Persian music. The other accidental covers accidentals other than those listed here. It is usually used in combination with the smufl attribute to specify a particular SMuFL accidental. The smufl attribute may be used with any accidental value to help specify the appearance of symbols that share the same MusicXML semantics.
        
        Permitted Values: ['sharp', 'natural', 'flat', 'double-sharp', 'sharp-sharp', 'flat-flat', 'natural-sharp', 'natural-flat', 'quarter-flat', 'quarter-sharp', 'three-quarters-flat', 'three-quarters-sharp', 'sharp-down', 'sharp-up', 'natural-down', 'natural-up', 'flat-down', 'flat-up', 'double-sharp-down', 'double-sharp-up', 'flat-flat-down', 'flat-flat-up', 'arrow-down', 'arrow-up', 'triple-sharp', 'triple-flat', 'slash-quarter-sharp', 'slash-sharp', 'slash-flat', 'double-slash-flat', 'sharp-1', 'sharp-2', 'sharp-3', 'sharp-5', 'flat-1', 'flat-2', 'flat-3', 'flat-4', 'sori', 'koron', 'other']
    
    """
    
    TYPE = XSDComplexTypeAccidentalMark
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='accidental-mark'][@type='accidental-mark']"


class XMLOtherNotation(XMLElement):
    """
    ``complexType``: The other-notation type is used to define any notations not yet in the MusicXML format. It handles notations where more specific extension elements such as other-dynamics and other-technical are not appropriate. The smufl attribute can be used to specify a particular notation, allowing application interoperability without requiring every SMuFL glyph to have a MusicXML element equivalent. Using the other-notation type without the smufl attribute allows for extended representation, though without application interoperability.
    """
    
    TYPE = XSDComplexTypeOtherNotation
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='other-notation'][@type='other-notation']"


class XMLGrace(XMLElement):
    """
    ``complexType``: The grace type indicates the presence of a grace note. The slash attribute for a grace note is yes for slashed grace notes. The steal-time-previous attribute indicates the percentage of time to steal from the previous note for the grace note. The steal-time-following attribute indicates the percentage of time to steal from the following note for the grace note, as for appoggiaturas. The make-time attribute indicates to make time, not steal time; the units are in real-time divisions for the grace note.
    """
    
    TYPE = XSDComplexTypeGrace
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='grace'][@type='grace']"


class XMLTie(XMLElement):
    """
    ``complexType``: The tie element indicates that a tie begins or ends with this note. If the tie element applies only particular times through a repeat, the time-only attribute indicates which times to apply it. The tie element indicates sound; the tied element indicates notation.
    """
    
    TYPE = XSDComplexTypeTie
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='tie'][@type='tie']"


class XMLCue(XMLElement):
    """
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='cue'][@type='empty']"


class XMLInstrument(XMLElement):
    """
    ``complexType``: The instrument type distinguishes between score-instrument elements in a score-part. The id attribute is an IDREF back to the score-instrument ID. If multiple score-instruments are specified in a score-part, there should be an instrument element for each note in the part. Notes that are shared between multiple score-instruments can have more than one instrument element.
    """
    
    TYPE = XSDComplexTypeInstrument
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='instrument'][@type='instrument']"


class XMLType(XMLElement):
    """
    ``complexType``: The note-type type indicates the graphic note type. Values range from 1024th to maxima. The size attribute indicates full, cue, grace-cue, or large size. The default is full for regular notes, grace-cue for notes that contain both grace and cue elements, and cue for notes that contain either a cue or a grace element, but not both.
    
    ``simpleContent``: The note-type-value type is used for the MusicXML type element and represents the graphic note type, from 1024th (shortest) to maxima (longest).
        
        Permitted Values: ['1024th', '512th', '256th', '128th', '64th', '32nd', '16th', 'eighth', 'quarter', 'half', 'whole', 'breve', 'long', 'maxima']
    
    """
    
    TYPE = XSDComplexTypeNoteType
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='type'][@type='note-type']"


class XMLDot(XMLElement):
    """
    One dot element is used for each dot of prolongation. The placement attribute is used to specify whether the dot should appear above or below the staff line. It is ignored for notes that appear on a staff space.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='dot'][@type='empty-placement']"


class XMLAccidental(XMLElement):
    """
    ``complexType``: The accidental type represents actual notated accidentals. Editorial and cautionary indications are indicated by attributes. Values for these attributes are "no" if not present. Specific graphic display such as parentheses, brackets, and size are controlled by the level-display attribute group.
    
    ``simpleContent``: The accidental-value type represents notated accidentals supported by MusicXML. In the MusicXML 2.0 DTD this was a string with values that could be included. The XSD strengthens the data typing to an enumerated list. The quarter- and three-quarters- accidentals are Tartini-style quarter-tone accidentals. The -down and -up accidentals are quarter-tone accidentals that include arrows pointing down or up. The slash- accidentals are used in Turkish classical music. The numbered sharp and flat accidentals are superscripted versions of the accidental signs, used in Turkish folk music. The sori and koron accidentals are microtonal sharp and flat accidentals used in Iranian and Persian music. The other accidental covers accidentals other than those listed here. It is usually used in combination with the smufl attribute to specify a particular SMuFL accidental. The smufl attribute may be used with any accidental value to help specify the appearance of symbols that share the same MusicXML semantics.
        
        Permitted Values: ['sharp', 'natural', 'flat', 'double-sharp', 'sharp-sharp', 'flat-flat', 'natural-sharp', 'natural-flat', 'quarter-flat', 'quarter-sharp', 'three-quarters-flat', 'three-quarters-sharp', 'sharp-down', 'sharp-up', 'natural-down', 'natural-up', 'flat-down', 'flat-up', 'double-sharp-down', 'double-sharp-up', 'flat-flat-down', 'flat-flat-up', 'arrow-down', 'arrow-up', 'triple-sharp', 'triple-flat', 'slash-quarter-sharp', 'slash-sharp', 'slash-flat', 'double-slash-flat', 'sharp-1', 'sharp-2', 'sharp-3', 'sharp-5', 'flat-1', 'flat-2', 'flat-3', 'flat-4', 'sori', 'koron', 'other']
    
    """
    
    TYPE = XSDComplexTypeAccidental
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='accidental'][@type='accidental']"


class XMLTimeModification(XMLElement):
    """
    ``complexType``: Time modification indicates tuplets, double-note tremolos, and other durational changes. A time-modification element shows how the cumulative, sounding effect of tuplets and double-note tremolos compare to the written note type represented by the type and dot elements. Nested tuplets and other notations that use more detailed information need both the time-modification and tuplet elements to be represented accurately.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=actual-notes@minOccurs=1@maxOccurs=1
           Element@name=normal-notes@minOccurs=1@maxOccurs=1
           Sequence@minOccurs=0@maxOccurs=1
               Element@name=normal-type@minOccurs=1@maxOccurs=1
               Element@name=normal-dot@minOccurs=0@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypeTimeModification
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='time-modification'][@type='time-modification']"


class XMLStem(XMLElement):
    """
    ``complexType``: Stems can be down, up, none, or double. For down and up stems, the position attributes can be used to specify stem length. The relative values specify the end of the stem relative to the program default. Default values specify an absolute end stem position. Negative values of relative-y that would flip a stem instead of shortening it are ignored. A stem element associated with a rest refers to a stemlet.
    
    ``simpleContent``: The stem-value type represents the notated stem direction.
        
        Permitted Values: ['down', 'up', 'double', 'none']
    
    """
    
    TYPE = XSDComplexTypeStem
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='stem'][@type='stem']"


class XMLNotehead(XMLElement):
    """
    ``complexType``: The notehead type indicates shapes other than the open and closed ovals associated with note durations. 
    
    The smufl attribute can be used to specify a particular notehead, allowing application interoperability without requiring every SMuFL glyph to have a MusicXML element equivalent. This attribute can be used either with the "other" value, or to refine a specific notehead value such as "cluster". Noteheads in the SMuFL Note name noteheads and Note name noteheads supplement ranges (U+E150–U+E1AF and U+EEE0–U+EEFF) should not use the smufl attribute or the "other" value, but instead use the notehead-text element.
    
    For the enclosed shapes, the default is to be hollow for half notes and longer, and filled otherwise. The filled attribute can be set to change this if needed.
    
    If the parentheses attribute is set to yes, the notehead is parenthesized. It is no by default.
    
    ``simpleContent``: The notehead-value type indicates shapes other than the open and closed ovals associated with note durations. 
    
    The values do, re, mi, fa, fa up, so, la, and ti correspond to Aikin's 7-shape system.  The fa up shape is typically used with upstems; the fa shape is typically used with downstems or no stems.
    
    The arrow shapes differ from triangle and inverted triangle by being centered on the stem. Slashed and back slashed notes include both the normal notehead and a slash. The triangle shape has the tip of the triangle pointing up; the inverted triangle shape has the tip of the triangle pointing down. The left triangle shape is a right triangle with the hypotenuse facing up and to the left.
    
    The other notehead covers noteheads other than those listed here. It is usually used in combination with the smufl attribute to specify a particular SMuFL notehead. The smufl attribute may be used with any notehead value to help specify the appearance of symbols that share the same MusicXML semantics. Noteheads in the SMuFL Note name noteheads and Note name noteheads supplement ranges (U+E150–U+E1AF and U+EEE0–U+EEFF) should not use the smufl attribute or the "other" value, but instead use the notehead-text element.
        
        Permitted Values: ['slash', 'triangle', 'diamond', 'square', 'cross', 'x', 'circle-x', 'inverted triangle', 'arrow down', 'arrow up', 'circled', 'slashed', 'back slashed', 'normal', 'cluster', 'circle dot', 'left triangle', 'rectangle', 'none', 'do', 're', 'mi', 'fa', 'fa up', 'so', 'la', 'ti', 'other']
    
    """
    
    TYPE = XSDComplexTypeNotehead
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='notehead'][@type='notehead']"


class XMLNoteheadText(XMLElement):
    """
    ``complexType``: The notehead-text type represents text that is displayed inside a notehead, as is done in some educational music. It is not needed for the numbers used in tablature or jianpu notation. The presence of a TAB or jianpu clefs is sufficient to indicate that numbers are used. The display-text and accidental-text elements allow display of fully formatted text and accidentals.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Choice@minOccurs=1@maxOccurs=unbounded
               Element@name=display-text@minOccurs=1@maxOccurs=1
               Element@name=accidental-text@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeNoteheadText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='notehead-text'][@type='notehead-text']"


class XMLBeam(XMLElement):
    """
    ``complexType``: Beam values include begin, continue, end, forward hook, and backward hook. Up to eight concurrent beams are available to cover up to 1024th notes. Each beam in a note is represented with a separate beam element, starting with the eighth note beam using a number attribute of 1.
    
    Note that the beam number does not distinguish sets of beams that overlap, as it does for slur and other elements. Beaming groups are distinguished by being in different voices and/or the presence or absence of grace and cue elements.
    
    Beams that have a begin value can also have a fan attribute to indicate accelerandos and ritardandos using fanned beams. The fan attribute may also be used with a continue value if the fanning direction changes on that note. The value is "none" if not specified.
    
    The repeater attribute has been deprecated in MusicXML 3.0. Formerly used for tremolos, it needs to be specified with a "yes" value for each beam using it.
    
    ``simpleContent``: The beam-value type represents the type of beam associated with each of 8 beam levels (up to 1024th notes) available for each note.
        
        Permitted Values: ['begin', 'continue', 'end', 'forward hook', 'backward hook']
    
    """
    
    TYPE = XSDComplexTypeBeam
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='beam'][@type='beam']"


class XMLNotations(XMLElement):
    """
    ``complexType``: Notations refer to musical notations, not XML notations. Multiple notations are allowed in order to represent multiple editorial levels. The print-object attribute, added in Version 3.0, allows notations to represent details of performance technique, such as fingerings, without having them appear in the score.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Group@name=editorial@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Group@name=footnote@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=footnote@minOccurs=1@maxOccurs=1
                   Group@name=level@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=level@minOccurs=1@maxOccurs=1
           Choice@minOccurs=0@maxOccurs=unbounded
               Element@name=tied@minOccurs=1@maxOccurs=1
               Element@name=slur@minOccurs=1@maxOccurs=1
               Element@name=tuplet@minOccurs=1@maxOccurs=1
               Element@name=glissando@minOccurs=1@maxOccurs=1
               Element@name=slide@minOccurs=1@maxOccurs=1
               Element@name=ornaments@minOccurs=1@maxOccurs=1
               Element@name=technical@minOccurs=1@maxOccurs=1
               Element@name=articulations@minOccurs=1@maxOccurs=1
               Element@name=dynamics@minOccurs=1@maxOccurs=1
               Element@name=fermata@minOccurs=1@maxOccurs=1
               Element@name=arpeggiate@minOccurs=1@maxOccurs=1
               Element@name=non-arpeggiate@minOccurs=1@maxOccurs=1
               Element@name=accidental-mark@minOccurs=1@maxOccurs=1
               Element@name=other-notation@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeNotations
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='notations'][@type='notations']"


class XMLLyric(XMLElement):
    """
    ``complexType``: The lyric type represents text underlays for lyrics. Two text elements that are not separated by an elision element are part of the same syllable, but may have different text formatting. The MusicXML XSD is more strict than the DTD in enforcing this by disallowing a second syllabic element unless preceded by an elision element. The lyric number indicates multiple lines, though a name can be used as well. Common name examples are verse and chorus.
    
    Justification is center by default; placement is below by default. Vertical alignment is to the baseline of the text and horizontal alignment matches justification. The print-object attribute can override a note's print-lyric attribute in cases where only some lyrics on a note are printed, as when lyrics for later verses are printed in a block of text rather than with each note. The time-only attribute precisely specifies which lyrics are to be sung which time through a repeated section.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Choice@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=syllabic@minOccurs=0@maxOccurs=1
                   Element@name=text@minOccurs=1@maxOccurs=1
                   Sequence@minOccurs=0@maxOccurs=unbounded
                       Sequence@minOccurs=0@maxOccurs=1
                           Element@name=elision@minOccurs=1@maxOccurs=1
                           Element@name=syllabic@minOccurs=0@maxOccurs=1
                       Element@name=text@minOccurs=1@maxOccurs=1
                   Element@name=extend@minOccurs=0@maxOccurs=1
               Element@name=extend@minOccurs=1@maxOccurs=1
               Element@name=laughing@minOccurs=1@maxOccurs=1
               Element@name=humming@minOccurs=1@maxOccurs=1
           Element@name=end-line@minOccurs=0@maxOccurs=1
           Element@name=end-paragraph@minOccurs=0@maxOccurs=1
           Group@name=editorial@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Group@name=footnote@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=footnote@minOccurs=1@maxOccurs=1
                   Group@name=level@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=level@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeLyric
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='lyric'][@type='lyric']"


class XMLListen(XMLElement):
    """
    ``complexType``: The listen and listening types, new in Version 4.0, specify different ways that a score following or machine listening application can interact with a performer. The listen type handles interactions that are specific to a note. If multiple child elements of the same type are present, they should have distinct player and/or time-only attributes.

    ``XSD structure:``

    .. code-block::

       Choice@minOccurs=1@maxOccurs=unbounded
           Element@name=assess@minOccurs=1@maxOccurs=1
           Element@name=wait@minOccurs=1@maxOccurs=1
           Element@name=other-listen@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeListen
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='listen'][@type='listen']"


class XMLTrillMark(XMLElement):
    """
    The trill-mark element represents the trill-mark symbol.
    
    ``complexType``: The empty-trill-sound type represents an empty element with print-style, placement, and trill-sound attributes.
    """
    
    TYPE = XSDComplexTypeEmptyTrillSound
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='trill-mark'][@type='empty-trill-sound']"


class XMLTurn(XMLElement):
    """
    The turn element is the normal turn shape which goes up then down.
    
    ``complexType``: The horizontal-turn type represents turn elements that are horizontal rather than vertical. These are empty elements with print-style, placement, trill-sound, and slash attributes. If the slash attribute is yes, then a vertical line is used to slash the turn. It is no if not specified.
    """
    
    TYPE = XSDComplexTypeHorizontalTurn
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='turn'][@type='horizontal-turn']"


class XMLDelayedTurn(XMLElement):
    """
    The delayed-turn element indicates a normal turn that is delayed until the end of the current note.
    
    ``complexType``: The horizontal-turn type represents turn elements that are horizontal rather than vertical. These are empty elements with print-style, placement, trill-sound, and slash attributes. If the slash attribute is yes, then a vertical line is used to slash the turn. It is no if not specified.
    """
    
    TYPE = XSDComplexTypeHorizontalTurn
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='delayed-turn'][@type='horizontal-turn']"


class XMLInvertedTurn(XMLElement):
    """
    The inverted-turn element has the shape which goes down and then up.
    
    ``complexType``: The horizontal-turn type represents turn elements that are horizontal rather than vertical. These are empty elements with print-style, placement, trill-sound, and slash attributes. If the slash attribute is yes, then a vertical line is used to slash the turn. It is no if not specified.
    """
    
    TYPE = XSDComplexTypeHorizontalTurn
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='inverted-turn'][@type='horizontal-turn']"


class XMLDelayedInvertedTurn(XMLElement):
    """
    The delayed-inverted-turn element indicates an inverted turn that is delayed until the end of the current note.
    
    ``complexType``: The horizontal-turn type represents turn elements that are horizontal rather than vertical. These are empty elements with print-style, placement, trill-sound, and slash attributes. If the slash attribute is yes, then a vertical line is used to slash the turn. It is no if not specified.
    """
    
    TYPE = XSDComplexTypeHorizontalTurn
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='delayed-inverted-turn'][@type='horizontal-turn']"


class XMLVerticalTurn(XMLElement):
    """
    The vertical-turn element has the turn symbol shape arranged vertically going from upper left to lower right.
    
    ``complexType``: The empty-trill-sound type represents an empty element with print-style, placement, and trill-sound attributes.
    """
    
    TYPE = XSDComplexTypeEmptyTrillSound
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='vertical-turn'][@type='empty-trill-sound']"


class XMLInvertedVerticalTurn(XMLElement):
    """
    The inverted-vertical-turn element has the turn symbol shape arranged vertically going from upper right to lower left.
    
    ``complexType``: The empty-trill-sound type represents an empty element with print-style, placement, and trill-sound attributes.
    """
    
    TYPE = XSDComplexTypeEmptyTrillSound
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='inverted-vertical-turn'][@type='empty-trill-sound']"


class XMLShake(XMLElement):
    """
    The shake element has a similar appearance to an inverted-mordent element.
    
    ``complexType``: The empty-trill-sound type represents an empty element with print-style, placement, and trill-sound attributes.
    """
    
    TYPE = XSDComplexTypeEmptyTrillSound
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='shake'][@type='empty-trill-sound']"


class XMLMordent(XMLElement):
    """
    The mordent element represents the sign with the vertical line. The choice of which mordent sign is inverted differs between MusicXML and SMuFL. The long attribute is "no" by default.
    
    ``complexType``: The mordent type is used for both represents the mordent sign with the vertical line and the inverted-mordent sign without the line. The long attribute is "no" by default. The approach and departure attributes are used for compound ornaments, indicating how the beginning and ending of the ornament look relative to the main part of the mordent.
    """
    
    TYPE = XSDComplexTypeMordent
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='mordent'][@type='mordent']"


class XMLInvertedMordent(XMLElement):
    """
    The inverted-mordent element represents the sign without the vertical line. The choice of which mordent is inverted differs between MusicXML and SMuFL. The long attribute is "no" by default.
    
    ``complexType``: The mordent type is used for both represents the mordent sign with the vertical line and the inverted-mordent sign without the line. The long attribute is "no" by default. The approach and departure attributes are used for compound ornaments, indicating how the beginning and ending of the ornament look relative to the main part of the mordent.
    """
    
    TYPE = XSDComplexTypeMordent
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='inverted-mordent'][@type='mordent']"


class XMLSchleifer(XMLElement):
    """
    The name for this ornament is based on the German, to avoid confusion with the more common slide element defined earlier.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='schleifer'][@type='empty-placement']"


class XMLTremolo(XMLElement):
    """
    ``complexType``: The tremolo ornament can be used to indicate single-note, double-note, or unmeasured tremolos. Single-note tremolos use the single type, double-note tremolos use the start and stop types, and unmeasured tremolos use the unmeasured type. The default is "single" for compatibility with Version 1.1. The text of the element indicates the number of tremolo marks and is an integer from 0 to 8. Note that the number of attached beams is not included in this value, but is represented separately using the beam element. The value should be 0 for unmeasured tremolos.
    
    When using double-note tremolos, the duration of each note in the tremolo should correspond to half of the notated type value. A time-modification element should also be added with an actual-notes value of 2 and a normal-notes value of 1. If used within a tuplet, this 2/1 ratio should be multiplied by the existing tuplet ratio.
    
    The smufl attribute specifies the glyph to use from the SMuFL Tremolos range for an unmeasured tremolo. It is ignored for other tremolo types. The SMuFL buzzRoll glyph is used by default if the attribute is missing.
    
    Using repeater beams for indicating tremolos is deprecated as of MusicXML 3.0.
    
    ``simpleContent``: The number of tremolo marks is represented by a number from 0 to 8: the same as beam-level with 0 added.
    """
    
    TYPE = XSDComplexTypeTremolo
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='tremolo'][@type='tremolo']"


class XMLHaydn(XMLElement):
    """
    The haydn element represents the Haydn ornament. This is defined in SMuFL as ornamentHaydn.
    
    ``complexType``: The empty-trill-sound type represents an empty element with print-style, placement, and trill-sound attributes.
    """
    
    TYPE = XSDComplexTypeEmptyTrillSound
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='haydn'][@type='empty-trill-sound']"


class XMLOtherOrnament(XMLElement):
    """
    The other-ornament element is used to define any ornaments not yet in the MusicXML format. The smufl attribute can be used to specify a particular ornament, allowing application interoperability without requiring every SMuFL ornament to have a MusicXML element equivalent. Using the other-ornament element without the smufl attribute allows for extended representation, though without application interoperability.
    
    ``complexType``: The other-placement-text type represents a text element with print-style, placement, and smufl attribute groups. This type is used by MusicXML notation extension elements to allow specification of specific SMuFL glyphs without needed to add every glyph as a MusicXML element.
    """
    
    TYPE = XSDComplexTypeOtherPlacementText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='other-ornament'][@type='other-placement-text']"


class XMLStep(XMLElement):
    """
    ``simpleType``: The step type represents a step of the diatonic scale, represented using the English letters A through G.
        
        Permitted Values: ['A', 'B', 'C', 'D', 'E', 'F', 'G']
    
    """
    
    TYPE = XSDSimpleTypeStep
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='step'][@type='step']"


class XMLAlter(XMLElement):
    """
    ``simpleType``: The semitones type is a number representing semitones, used for chromatic alteration. A value of -1 corresponds to a flat and a value of 1 to a sharp. Decimal values like 0.5 (quarter tone sharp) are used for microtones.
    """
    
    TYPE = XSDSimpleTypeSemitones
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='alter'][@type='semitones']"


class XMLOctave(XMLElement):
    """
    ``simpleType``: Octaves are represented by the numbers 0 to 9, where 4 indicates the octave started by middle C.
    """
    
    TYPE = XSDSimpleTypeOctave
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='octave'][@type='octave']"


class XMLUpBow(XMLElement):
    """
    The up-bow element represents the symbol that is used both for up-bowing on bowed instruments, and up-stroke on plucked instruments.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='up-bow'][@type='empty-placement']"


class XMLDownBow(XMLElement):
    """
    The down-bow element represents the symbol that is used both for down-bowing on bowed instruments, and down-stroke on plucked instruments.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='down-bow'][@type='empty-placement']"


class XMLHarmonic(XMLElement):
    """
    ``complexType``: The harmonic type indicates natural and artificial harmonics. Allowing the type of pitch to be specified, combined with controls for appearance/playback differences, allows both the notation and the sound to be represented. Artificial harmonics can add a notated touching pitch; artificial pinch harmonics will usually not notate a touching pitch. The attributes for the harmonic element refer to the use of the circular harmonic symbol, typically but not always used with natural harmonics.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Choice@minOccurs=0@maxOccurs=1
               Element@name=natural@minOccurs=1@maxOccurs=1
               Element@name=artificial@minOccurs=1@maxOccurs=1
           Choice@minOccurs=0@maxOccurs=1
               Element@name=base-pitch@minOccurs=1@maxOccurs=1
               Element@name=touching-pitch@minOccurs=1@maxOccurs=1
               Element@name=sounding-pitch@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeHarmonic
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='harmonic'][@type='harmonic']"


class XMLOpenString(XMLElement):
    """
    The open-string element represents the zero-shaped open string symbol.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='open-string'][@type='empty-placement']"


class XMLThumbPosition(XMLElement):
    """
    The thumb-position element represents the thumb position symbol. This is a circle with a line, where the line does not come within the circle. It is distinct from the snap pizzicato symbol, where the line comes inside the circle.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='thumb-position'][@type='empty-placement']"


class XMLPluck(XMLElement):
    """
    The pluck element is used to specify the plucking fingering on a fretted instrument, where the fingering element refers to the fretting fingering. Typical values are p, i, m, a for pulgar/thumb, indicio/index, medio/middle, and anular/ring fingers.
    
    ``complexType``: The placement-text type represents a text element with print-style and placement attribute groups.
    """
    
    TYPE = XSDComplexTypePlacementText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='pluck'][@type='placement-text']"


class XMLDoubleTongue(XMLElement):
    """
    The double-tongue element represents the double tongue symbol (two dots arranged horizontally).
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='double-tongue'][@type='empty-placement']"


class XMLTripleTongue(XMLElement):
    """
    The triple-tongue element represents the triple tongue symbol (three dots arranged horizontally).
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='triple-tongue'][@type='empty-placement']"


class XMLStopped(XMLElement):
    """
    The stopped element represents the stopped symbol, which looks like a plus sign. The smufl attribute distinguishes different SMuFL glyphs that have a similar appearance such as handbellsMalletBellSuspended and guitarClosePedal. If not present, the default glyph is brassMuteClosed.
    
    ``complexType``: The empty-placement-smufl type represents an empty element with print-style, placement, and smufl attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacementSmufl
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='stopped'][@type='empty-placement-smufl']"


class XMLSnapPizzicato(XMLElement):
    """
    The snap-pizzicato element represents the snap pizzicato symbol. This is a circle with a line, where the line comes inside the circle. It is distinct from the thumb-position symbol, where the line does not come inside the circle.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='snap-pizzicato'][@type='empty-placement']"


class XMLHammerOn(XMLElement):
    """
    ``complexType``: The hammer-on and pull-off elements are used in guitar and fretted instrument notation. Since a single slur can be marked over many notes, the hammer-on and pull-off elements are separate so the individual pair of notes can be specified. The element content can be used to specify how the hammer-on or pull-off should be notated. An empty element leaves this choice up to the application.
    """
    
    TYPE = XSDComplexTypeHammerOnPullOff
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='hammer-on'][@type='hammer-on-pull-off']"


class XMLPullOff(XMLElement):
    """
    ``complexType``: The hammer-on and pull-off elements are used in guitar and fretted instrument notation. Since a single slur can be marked over many notes, the hammer-on and pull-off elements are separate so the individual pair of notes can be specified. The element content can be used to specify how the hammer-on or pull-off should be notated. An empty element leaves this choice up to the application.
    """
    
    TYPE = XSDComplexTypeHammerOnPullOff
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='pull-off'][@type='hammer-on-pull-off']"


class XMLBend(XMLElement):
    """
    ``complexType``: The bend type is used in guitar notation and tablature. A single note with a bend and release will contain two bend elements: the first to represent the bend and the second to represent the release. The shape attribute distinguishes between the angled bend symbols commonly used in standard notation and the curved bend symbols commonly used in both tablature and standard notation.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=bend-alter@minOccurs=1@maxOccurs=1
           Choice@minOccurs=0@maxOccurs=1
               Element@name=pre-bend@minOccurs=1@maxOccurs=1
               Element@name=release@minOccurs=1@maxOccurs=1
           Element@name=with-bar@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeBend
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='bend'][@type='bend']"


class XMLTap(XMLElement):
    """
    ``complexType``: The tap type indicates a tap on the fretboard. The text content allows specification of the notation; + and T are common choices. If the element is empty, the hand attribute is used to specify the symbol to use. The hand attribute is ignored if the tap glyph is already specified by the text content. If neither text content nor the hand attribute are present, the display is application-specific.
    """
    
    TYPE = XSDComplexTypeTap
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='tap'][@type='tap']"


class XMLHeel(XMLElement):
    """
    ``complexType``: The heel and toe elements are used with organ pedals. The substitution value is "no" if the attribute is not present.
    """
    
    TYPE = XSDComplexTypeHeelToe
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='heel'][@type='heel-toe']"


class XMLToe(XMLElement):
    """
    ``complexType``: The heel and toe elements are used with organ pedals. The substitution value is "no" if the attribute is not present.
    """
    
    TYPE = XSDComplexTypeHeelToe
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='toe'][@type='heel-toe']"


class XMLFingernails(XMLElement):
    """
    The fingernails element is used in notation for harp and other plucked string instruments.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='fingernails'][@type='empty-placement']"


class XMLHole(XMLElement):
    """
    ``complexType``: The hole type represents the symbols used for woodwind and brass fingerings as well as other notations.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=hole-type@minOccurs=0@maxOccurs=1
           Element@name=hole-closed@minOccurs=1@maxOccurs=1
           Element@name=hole-shape@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeHole
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='hole'][@type='hole']"


class XMLArrow(XMLElement):
    """
    ``complexType``: The arrow element represents an arrow used for a musical technical indication. It can represent both Unicode and SMuFL arrows. The presence of an arrowhead element indicates that only the arrowhead is displayed, not the arrow stem. The smufl attribute distinguishes different SMuFL glyphs that have an arrow appearance such as arrowBlackUp, guitarStrumUp, or handbellsSwingUp. The specified glyph should match the descriptive representation.

    ``XSD structure:``

    .. code-block::

       Choice@minOccurs=1@maxOccurs=1
           Sequence@minOccurs=1@maxOccurs=1
               Element@name=arrow-direction@minOccurs=1@maxOccurs=1
               Element@name=arrow-style@minOccurs=0@maxOccurs=1
               Element@name=arrowhead@minOccurs=0@maxOccurs=1
           Element@name=circular-arrow@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeArrow
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='arrow'][@type='arrow']"


class XMLHandbell(XMLElement):
    """
    ``complexType``: The handbell element represents notation for various techniques used in handbell and handchime music.
    
    ``simpleContent``: The handbell-value type represents the type of handbell technique being notated.
        
        Permitted Values: ['belltree', 'damp', 'echo', 'gyro', 'hand martellato', 'mallet lift', 'mallet table', 'martellato', 'martellato lift', 'muted martellato', 'pluck lift', 'swing']
    
    """
    
    TYPE = XSDComplexTypeHandbell
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='handbell'][@type='handbell']"


class XMLBrassBend(XMLElement):
    """
    The brass-bend element represents the u-shaped bend symbol used in brass notation, distinct from the bend element used in guitar music.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='brass-bend'][@type='empty-placement']"


class XMLFlip(XMLElement):
    """
    The flip element represents the flip symbol used in brass notation.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='flip'][@type='empty-placement']"


class XMLSmear(XMLElement):
    """
    The smear element represents the tilde-shaped smear symbol used in brass notation.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='smear'][@type='empty-placement']"


class XMLOpen(XMLElement):
    """
    The open element represents the open symbol, which looks like a circle. The smufl attribute can be used to distinguish different SMuFL glyphs that have a similar appearance such as brassMuteOpen and guitarOpenPedal. If not present, the default glyph is brassMuteOpen.
    
    ``complexType``: The empty-placement-smufl type represents an empty element with print-style, placement, and smufl attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacementSmufl
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='open'][@type='empty-placement-smufl']"


class XMLHalfMuted(XMLElement):
    """
    The half-muted element represents the half-muted symbol, which looks like a circle with a plus sign inside. The smufl attribute can be used to distinguish different SMuFL glyphs that have a similar appearance such as brassMuteHalfClosed and guitarHalfOpenPedal. If not present, the default glyph is brassMuteHalfClosed.
    
    ``complexType``: The empty-placement-smufl type represents an empty element with print-style, placement, and smufl attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacementSmufl
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='half-muted'][@type='empty-placement-smufl']"


class XMLHarmonMute(XMLElement):
    """
    ``complexType``: The harmon-mute type represents the symbols used for harmon mutes in brass notation.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=harmon-closed@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeHarmonMute
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='harmon-mute'][@type='harmon-mute']"


class XMLGolpe(XMLElement):
    """
    The golpe element represents the golpe symbol that is used for tapping the pick guard in guitar music.
    
    ``complexType``: The empty-placement type represents an empty element with print-style and placement attributes.
    """
    
    TYPE = XSDComplexTypeEmptyPlacement
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='golpe'][@type='empty-placement']"


class XMLOtherTechnical(XMLElement):
    """
    The other-technical element is used to define any technical indications not yet in the MusicXML format. The smufl attribute can be used to specify a particular glyph, allowing application interoperability without requiring every SMuFL technical indication to have a MusicXML element equivalent. Using the other-technical element without the smufl attribute allows for extended representation, though without application interoperability.
    
    ``complexType``: The other-placement-text type represents a text element with print-style, placement, and smufl attribute groups. This type is used by MusicXML notation extension elements to allow specification of specific SMuFL glyphs without needed to add every glyph as a MusicXML element.
    """
    
    TYPE = XSDComplexTypeOtherPlacementText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='other-technical'][@type='other-placement-text']"


class XMLActualNotes(XMLElement):
    """
    The actual-notes element describes how many notes are played in the time usually occupied by the number in the normal-notes element.
    """
    
    TYPE = XSDSimpleTypeNonNegativeInteger
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='actual-notes'][@type='xs:nonNegativeInteger']"


class XMLNormalNotes(XMLElement):
    """
    The normal-notes element describes how many notes are usually played in the time occupied by the number in the actual-notes element.
    """
    
    TYPE = XSDSimpleTypeNonNegativeInteger
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='normal-notes'][@type='xs:nonNegativeInteger']"


class XMLNormalType(XMLElement):
    """
    If the type associated with the number in the normal-notes element is different than the current note type (e.g., a quarter note within an eighth note triplet), then the normal-notes type (e.g. eighth) is specified in the normal-type and normal-dot elements.
    
    ``simpleType``: The note-type-value type is used for the MusicXML type element and represents the graphic note type, from 1024th (shortest) to maxima (longest).
        
        Permitted Values: ['1024th', '512th', '256th', '128th', '64th', '32nd', '16th', 'eighth', 'quarter', 'half', 'whole', 'breve', 'long', 'maxima']
    
    """
    
    TYPE = XSDSimpleTypeNoteTypeValue
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='normal-type'][@type='note-type-value']"


class XMLNormalDot(XMLElement):
    """
    The normal-dot element is used to specify dotted normal tuplet types.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='normal-dot'][@type='empty']"


class XMLTupletActual(XMLElement):
    """
    The tuplet-actual element provide optional full control over how the actual part of the tuplet is displayed, including number and note type (with dots). If any of these elements are absent, their values are based on the time-modification element.
    
    ``complexType``: The tuplet-portion type provides optional full control over tuplet specifications. It allows the number and note type (including dots) to be set for the actual and normal portions of a single tuplet. If any of these elements are absent, their values are based on the time-modification element.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=tuplet-number@minOccurs=0@maxOccurs=1
           Element@name=tuplet-type@minOccurs=0@maxOccurs=1
           Element@name=tuplet-dot@minOccurs=0@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypeTupletPortion
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='tuplet-actual'][@type='tuplet-portion']"


class XMLTupletNormal(XMLElement):
    """
    The tuplet-normal element provide optional full control over how the normal part of the tuplet is displayed, including number and note type (with dots). If any of these elements are absent, their values are based on the time-modification element.
    
    ``complexType``: The tuplet-portion type provides optional full control over tuplet specifications. It allows the number and note type (including dots) to be set for the actual and normal portions of a single tuplet. If any of these elements are absent, their values are based on the time-modification element.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=tuplet-number@minOccurs=0@maxOccurs=1
           Element@name=tuplet-type@minOccurs=0@maxOccurs=1
           Element@name=tuplet-dot@minOccurs=0@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypeTupletPortion
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='tuplet-normal'][@type='tuplet-portion']"


class XMLTupletNumber(XMLElement):
    """
    ``complexType``: The tuplet-number type indicates the number of notes for this portion of the tuplet.
    """
    
    TYPE = XSDComplexTypeTupletNumber
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='tuplet-number'][@type='tuplet-number']"


class XMLTupletType(XMLElement):
    """
    ``complexType``: The tuplet-type type indicates the graphical note type of the notes for this portion of the tuplet.
    
    ``simpleContent``: The note-type-value type is used for the MusicXML type element and represents the graphic note type, from 1024th (shortest) to maxima (longest).
        
        Permitted Values: ['1024th', '512th', '256th', '128th', '64th', '32nd', '16th', 'eighth', 'quarter', 'half', 'whole', 'breve', 'long', 'maxima']
    
    """
    
    TYPE = XSDComplexTypeTupletType
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='tuplet-type'][@type='tuplet-type']"


class XMLTupletDot(XMLElement):
    """
    ``complexType``: The tuplet-dot type is used to specify dotted tuplet types.
    """
    
    TYPE = XSDComplexTypeTupletDot
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='tuplet-dot'][@type='tuplet-dot']"


class XMLCreditType(XMLElement):
    """
    
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='credit-type'][@type='xs:string']"


class XMLLink(XMLElement):
    """
    ``complexType``: The link type serves as an outgoing simple XLink. If a relative link is used within a document that is part of a compressed MusicXML file, the link is relative to the root folder of the zip file.
    """
    
    TYPE = XSDComplexTypeLink
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='link'][@type='link']"


class XMLBookmark(XMLElement):
    """
    ``complexType``: The bookmark type serves as a well-defined target for an incoming simple XLink.
    """
    
    TYPE = XSDComplexTypeBookmark
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='bookmark'][@type='bookmark']"


class XMLCreditImage(XMLElement):
    """
    ``complexType``: The image type is used to include graphical images in a score.
    """
    
    TYPE = XSDComplexTypeImage
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='credit-image'][@type='image']"


class XMLCreditWords(XMLElement):
    """
    ``complexType``: The formatted-text-id type represents a text element with text-formatting and id attributes.
    """
    
    TYPE = XSDComplexTypeFormattedTextId
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='credit-words'][@type='formatted-text-id']"


class XMLCreditSymbol(XMLElement):
    """
    ``complexType``: The formatted-symbol-id type represents a SMuFL musical symbol element with formatting and id attributes.
    
    ``simpleContent``: The smufl-glyph-name type is used for attributes that reference a specific Standard Music Font Layout (SMuFL) character. The value is a SMuFL canonical glyph name, not a code point. For instance, the value for a standard piano pedal mark would be keyboardPedalPed, not U+E650.
    """
    
    TYPE = XSDComplexTypeFormattedSymbolId
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='credit-symbol'][@type='formatted-symbol-id']"


class XMLScaling(XMLElement):
    """
    ``complexType``: Margins, page sizes, and distances are all measured in tenths to keep MusicXML data in a consistent coordinate system as much as possible. The translation to absolute units is done with the scaling type, which specifies how many millimeters are equal to how many tenths. For a staff height of 7 mm, millimeters would be set to 7 while tenths is set to 40. The ability to set a formula rather than a single scaling factor helps avoid roundoff errors.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=millimeters@minOccurs=1@maxOccurs=1
           Element@name=tenths@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeScaling
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='scaling'][@type='scaling']"


class XMLConcertScore(XMLElement):
    """
    The presence of a concert-score element indicates that a score is displayed in concert pitch. It is used for scores that contain parts for transposing instruments.
    
    A document with a concert-score element may not contain any transpose elements that have non-zero values for either the diatonic or chromatic elements. Concert scores may include octave transpositions, so transpose elements with a double element or a non-zero octave-change element value are permitted.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='concert-score'][@type='empty']"


class XMLAppearance(XMLElement):
    """
    ``complexType``: The appearance type controls general graphical settings for the music's final form appearance on a printed page of display. This includes support for line widths, definitions for note sizes, and standard distances between notation elements, plus an extension element for other aspects of appearance.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=line-width@minOccurs=0@maxOccurs=unbounded
           Element@name=note-size@minOccurs=0@maxOccurs=unbounded
           Element@name=distance@minOccurs=0@maxOccurs=unbounded
           Element@name=glyph@minOccurs=0@maxOccurs=unbounded
           Element@name=other-appearance@minOccurs=0@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypeAppearance
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='appearance'][@type='appearance']"


class XMLMusicFont(XMLElement):
    """
    ``complexType``: The empty-font type represents an empty element with font attributes.
    """
    
    TYPE = XSDComplexTypeEmptyFont
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='music-font'][@type='empty-font']"


class XMLWordFont(XMLElement):
    """
    ``complexType``: The empty-font type represents an empty element with font attributes.
    """
    
    TYPE = XSDComplexTypeEmptyFont
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='word-font'][@type='empty-font']"


class XMLLyricFont(XMLElement):
    """
    ``complexType``: The lyric-font type specifies the default font for a particular name and number of lyric.
    """
    
    TYPE = XSDComplexTypeLyricFont
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='lyric-font'][@type='lyric-font']"


class XMLLyricLanguage(XMLElement):
    """
    ``complexType``: The lyric-language type specifies the default language for a particular name and number of lyric.
    """
    
    TYPE = XSDComplexTypeLyricLanguage
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='lyric-language'][@type='lyric-language']"


class XMLGroupName(XMLElement):
    """
    ``complexType``: The group-name type describes the name or abbreviation of a part-group element. Formatting attributes in the group-name type are deprecated in Version 2.0 in favor of the new group-name-display and group-abbreviation-display elements.
    """
    
    TYPE = XSDComplexTypeGroupName
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='group-name'][@type='group-name']"


class XMLGroupNameDisplay(XMLElement):
    """
    Formatting specified in the group-name-display element overrides formatting specified in the group-name element.
    
    ``complexType``: The name-display type is used for exact formatting of multi-font text in part and group names to the left of the system. The print-object attribute can be used to determine what, if anything, is printed at the start of each system. Enclosure for the display-text element is none by default. Language for the display-text element is Italian ("it") by default.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Choice@minOccurs=0@maxOccurs=unbounded
               Element@name=display-text@minOccurs=1@maxOccurs=1
               Element@name=accidental-text@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeNameDisplay
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='group-name-display'][@type='name-display']"


class XMLGroupAbbreviation(XMLElement):
    """
    ``complexType``: The group-name type describes the name or abbreviation of a part-group element. Formatting attributes in the group-name type are deprecated in Version 2.0 in favor of the new group-name-display and group-abbreviation-display elements.
    """
    
    TYPE = XSDComplexTypeGroupName
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='group-abbreviation'][@type='group-name']"


class XMLGroupAbbreviationDisplay(XMLElement):
    """
    Formatting specified in the group-abbreviation-display element overrides formatting specified in the group-abbreviation element.
    
    ``complexType``: The name-display type is used for exact formatting of multi-font text in part and group names to the left of the system. The print-object attribute can be used to determine what, if anything, is printed at the start of each system. Enclosure for the display-text element is none by default. Language for the display-text element is Italian ("it") by default.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Choice@minOccurs=0@maxOccurs=unbounded
               Element@name=display-text@minOccurs=1@maxOccurs=1
               Element@name=accidental-text@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeNameDisplay
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='group-abbreviation-display'][@type='name-display']"


class XMLGroupSymbol(XMLElement):
    """
    ``complexType``: The group-symbol type indicates how the symbol for a group is indicated in the score. It is none if not specified.
    
    ``simpleContent``: The group-symbol-value type indicates how the symbol for a group or multi-staff part is indicated in the score.
        
        Permitted Values: ['none', 'brace', 'line', 'bracket', 'square']
    
    """
    
    TYPE = XSDComplexTypeGroupSymbol
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='group-symbol'][@type='group-symbol']"


class XMLGroupBarline(XMLElement):
    """
    ``complexType``: The group-barline type indicates if the group should have common barlines.
    
    ``simpleContent``: The group-barline-value type indicates if the group should have common barlines.
        
        Permitted Values: ['yes', 'no', 'Mensurstrich']
    
    """
    
    TYPE = XSDComplexTypeGroupBarline
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='group-barline'][@type='group-barline']"


class XMLGroupTime(XMLElement):
    """
    The group-time element indicates that the displayed time signatures should stretch across all parts and staves in the group.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='group-time'][@type='empty']"


class XMLInstrumentLink(XMLElement):
    """
    ``complexType``: Multiple part-link elements can link a condensed part within a score file to multiple MusicXML parts files. For example, a "Clarinet 1 and 2" part in a score file could link to separate "Clarinet 1" and "Clarinet 2" part files. The instrument-link type distinguish which of the score-instruments within a score-part are in which part file. The instrument-link id attribute refers to a score-instrument id attribute.
    """
    
    TYPE = XSDComplexTypeInstrumentLink
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='instrument-link'][@type='instrument-link']"


class XMLGroupLink(XMLElement):
    """
    Multiple part-link elements can reference different types of linked documents, such as parts and condensed score. The optional group-link elements identify the groups used in the linked document. The content of a group-link element should match the content of a group element in the linked document.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='group-link'][@type='xs:string']"


class XMLPlayerName(XMLElement):
    """
    The player-name element is typically used within a software application, rather than appearing on the printed page of a score.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='player-name'][@type='xs:string']"


class XMLInstrumentName(XMLElement):
    """
    The instrument-name element is typically used within a software application, rather than appearing on the printed page of a score.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='instrument-name'][@type='xs:string']"


class XMLInstrumentAbbreviation(XMLElement):
    """
    The optional instrument-abbreviation element is typically used within a software application, rather than appearing on the printed page of a score.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='instrument-abbreviation'][@type='xs:string']"


class XMLIdentification(XMLElement):
    """
    ``complexType``: Identification contains basic metadata about the score. It includes information that may apply at a score-wide, movement-wide, or part-wide level. The creator, rights, source, and relation elements are based on Dublin Core.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=creator@minOccurs=0@maxOccurs=unbounded
           Element@name=rights@minOccurs=0@maxOccurs=unbounded
           Element@name=encoding@minOccurs=0@maxOccurs=1
           Element@name=source@minOccurs=0@maxOccurs=1
           Element@name=relation@minOccurs=0@maxOccurs=unbounded
           Element@name=miscellaneous@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeIdentification
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='identification'][@type='identification']"


class XMLPartLink(XMLElement):
    """
    ``complexType``: The part-link type allows MusicXML data for both score and parts to be contained within a single compressed MusicXML file. It links a score-part from a score document to MusicXML documents that contain parts data. In the case of a single compressed MusicXML file, the link href values are paths that are relative to the root folder of the zip file.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=instrument-link@minOccurs=0@maxOccurs=unbounded
           Element@name=group-link@minOccurs=0@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypePartLink
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='part-link'][@type='part-link']"


class XMLPartName(XMLElement):
    """
    ``complexType``: The part-name type describes the name or abbreviation of a score-part element. Formatting attributes for the part-name element are deprecated in Version 2.0 in favor of the new part-name-display and part-abbreviation-display elements.
    """
    
    TYPE = XSDComplexTypePartName
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='part-name'][@type='part-name']"


class XMLPartAbbreviation(XMLElement):
    """
    ``complexType``: The part-name type describes the name or abbreviation of a score-part element. Formatting attributes for the part-name element are deprecated in Version 2.0 in favor of the new part-name-display and part-abbreviation-display elements.
    """
    
    TYPE = XSDComplexTypePartName
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='part-abbreviation'][@type='part-name']"


class XMLGroup(XMLElement):
    """
    The group element allows the use of different versions of the part for different purposes. Typical values include score, parts, sound, and data. Ordering information can be derived from the ordering within a MusicXML score or opus.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='group'][@type='xs:string']"


class XMLScoreInstrument(XMLElement):
    """
    ``complexType``: The score-instrument type represents a single instrument within a score-part. As with the score-part type, each score-instrument has a required ID attribute, a name, and an optional abbreviation.
    
    A score-instrument type is also required if the score specifies MIDI 1.0 channels, banks, or programs. An initial midi-instrument assignment can also be made here. MusicXML software should be able to automatically assign reasonable channels and instruments without these elements in simple cases, such as where part names match General MIDI instrument names.
    
    The score-instrument element can also distinguish multiple instruments of the same type that are on the same part, such as Clarinet 1 and Clarinet 2 instruments within a Clarinets 1 and 2 part.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=instrument-name@minOccurs=1@maxOccurs=1
           Element@name=instrument-abbreviation@minOccurs=0@maxOccurs=1
           Group@name=virtual-instrument-data@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=instrument-sound@minOccurs=0@maxOccurs=1
                   Choice@minOccurs=0@maxOccurs=1
                       Element@name=solo@minOccurs=1@maxOccurs=1
                       Element@name=ensemble@minOccurs=1@maxOccurs=1
                   Element@name=virtual-instrument@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeScoreInstrument
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='score-instrument'][@type='score-instrument']"


class XMLPlayer(XMLElement):
    """
    ``complexType``: The player type allows for multiple players per score-part for use in listening applications. One player may play multiple instruments, while a single instrument may include multiple players in divisi sections.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=player-name@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypePlayer
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='player'][@type='player']"


class XMLVirtualLibrary(XMLElement):
    """
    The virtual-library element indicates the virtual instrument library name.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='virtual-library'][@type='xs:string']"


class XMLVirtualName(XMLElement):
    """
    The virtual-name element indicates the library-specific name for the virtual instrument.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='virtual-name'][@type='xs:string']"


class XMLWorkNumber(XMLElement):
    """
    The work-number element specifies the number of a work, such as its opus number.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='work-number'][@type='xs:string']"


class XMLWorkTitle(XMLElement):
    """
    The work-title element specifies the title of a work, not including its opus or other work number.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='work-title'][@type='xs:string']"


class XMLOpus(XMLElement):
    """
    ``complexType``: The opus type represents a link to a MusicXML opus document that composes multiple MusicXML scores into a collection.
    """
    
    TYPE = XSDComplexTypeOpus
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='opus'][@type='opus']"


class XMLFootnote(XMLElement):
    """
    ``complexType``: The formatted-text type represents a text element with text-formatting attributes.
    """
    
    TYPE = XSDComplexTypeFormattedText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='footnote'][@type='formatted-text']"


class XMLLevel(XMLElement):
    """
    ``complexType``: The level type is used to specify editorial information for different MusicXML elements. The content contains identifying and/or descriptive text about the editorial status of the parent element.
    
    If the reference attribute is yes, this indicates editorial information that is for display only and should not affect playback. For instance, a modern edition of older music may set reference="yes" on the attributes containing the music's original clef, key, and time signature. It is no if not specified.
    
    The type attribute indicates whether the editorial information applies to the start of a series of symbols, the end of a series of symbols, or a single symbol. It is single if not specified for compatibility with earlier MusicXML versions.
    """
    
    TYPE = XSDComplexTypeLevel
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='level'][@type='level']"


class XMLStaff(XMLElement):
    """
    Staff assignment is only needed for music notated on multiple staves. Used by both notes and directions. Staff values are numbers, with 1 referring to the top-most staff in a part.
    """
    
    TYPE = XSDSimpleTypePositiveInteger
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='staff'][@type='xs:positiveInteger']"


class XMLTuningStep(XMLElement):
    """
    The tuning-step element is represented like the step element, with a different name to reflect its different function in string tuning.
    
    ``simpleType``: The step type represents a step of the diatonic scale, represented using the English letters A through G.
        
        Permitted Values: ['A', 'B', 'C', 'D', 'E', 'F', 'G']
    
    """
    
    TYPE = XSDSimpleTypeStep
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='tuning-step'][@type='step']"


class XMLTuningAlter(XMLElement):
    """
    The tuning-alter element is represented like the alter element, with a different name to reflect its different function in string tuning.
    
    ``simpleType``: The semitones type is a number representing semitones, used for chromatic alteration. A value of -1 corresponds to a flat and a value of 1 to a sharp. Decimal values like 0.5 (quarter tone sharp) are used for microtones.
    """
    
    TYPE = XSDSimpleTypeSemitones
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='tuning-alter'][@type='semitones']"


class XMLTuningOctave(XMLElement):
    """
    The tuning-octave element is represented like the octave element, with a different name to reflect its different function in string tuning.
    
    ``simpleType``: Octaves are represented by the numbers 0 to 9, where 4 indicates the octave started by middle C.
    """
    
    TYPE = XSDSimpleTypeOctave
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='tuning-octave'][@type='octave']"


class XMLInstrumentSound(XMLElement):
    """
    The instrument-sound element describes the default timbre of the score-instrument. This description is independent of a particular virtual or MIDI instrument specification and allows playback to be shared more easily between applications and libraries.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='instrument-sound'][@type='xs:string']"


class XMLSolo(XMLElement):
    """
    The solo element is present if performance is intended by a solo instrument.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='solo'][@type='empty']"


class XMLEnsemble(XMLElement):
    """
    The ensemble element is present if performance is intended by an ensemble such as an orchestral section. The text of the ensemble element contains the size of the section, or is empty if the ensemble size is not specified.
    
    ``simpleType``: The positive-integer-or-empty values can be either a positive integer or an empty string.
    """
    
    TYPE = XSDSimpleTypePositiveIntegerOrEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='ensemble'][@type='positive-integer-or-empty']"


class XMLVirtualInstrument(XMLElement):
    """
    ``complexType``: The virtual-instrument element defines a specific virtual instrument used for an instrument sound.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=virtual-library@minOccurs=0@maxOccurs=1
           Element@name=virtual-name@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeVirtualInstrument
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='virtual-instrument'][@type='virtual-instrument']"


class XMLVoice(XMLElement):
    """
    
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='voice'][@type='xs:string']"


class XMLSign(XMLElement):
    """
    The sign element represents the clef symbol.
    
    ``simpleType``: The clef-sign type represents the different clef symbols. The jianpu sign indicates that the music that follows should be in jianpu numbered notation, just as the TAB sign indicates that the music that follows should be in tablature notation. Unlike TAB, a jianpu sign does not correspond to a visual clef notation.
    
    The none sign is deprecated as of MusicXML 4.0. Use the clef element's print-object attribute instead. When the none sign is used, notes should be displayed as if in treble clef.
        
        Permitted Values: ['G', 'F', 'C', 'percussion', 'TAB', 'jianpu', 'none']
    
    """
    
    TYPE = XSDSimpleTypeClefSign
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='sign'][@type='clef-sign']"


class XMLLine(XMLElement):
    """
    Line numbers are counted from the bottom of the staff. They are only needed with the G, F, and C signs in order to position a pitch correctly on the staff. Standard values are 2 for the G sign (treble clef), 4 for the F sign (bass clef), and 3 for the C sign (alto clef). Line values can be used to specify positions outside the staff, such as a C clef positioned in the middle of a grand staff.
    
    ``simpleType``: The staff-line-position type indicates the line position on a given staff. Staff lines are numbered from bottom to top, with 1 being the bottom line on a staff. A staff-line-position value can extend beyond the range of the lines on the current staff.
    """
    
    TYPE = XSDSimpleTypeStaffLinePosition
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='line'][@type='staff-line-position']"


class XMLClefOctaveChange(XMLElement):
    """
    The clef-octave-change element is used for transposing clefs. A treble clef for tenors would have a value of -1.
    """
    
    TYPE = XSDSimpleTypeInteger
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='clef-octave-change'][@type='xs:integer']"


class XMLKeyStep(XMLElement):
    """
    Non-traditional key signatures are represented using a list of altered tones. The key-step element indicates the pitch step to be altered, represented using the same names as in the step element.
    
    ``simpleType``: The step type represents a step of the diatonic scale, represented using the English letters A through G.
        
        Permitted Values: ['A', 'B', 'C', 'D', 'E', 'F', 'G']
    
    """
    
    TYPE = XSDSimpleTypeStep
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='key-step'][@type='step']"


class XMLKeyAlter(XMLElement):
    """
    Non-traditional key signatures are represented using a list of altered tones. The key-alter element represents the alteration for a given pitch step, represented with semitones in the same manner as the alter element.
    
    ``simpleType``: The semitones type is a number representing semitones, used for chromatic alteration. A value of -1 corresponds to a flat and a value of 1 to a sharp. Decimal values like 0.5 (quarter tone sharp) are used for microtones.
    """
    
    TYPE = XSDSimpleTypeSemitones
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='key-alter'][@type='semitones']"


class XMLKeyAccidental(XMLElement):
    """
    Non-traditional key signatures are represented using a list of altered tones. The key-accidental element indicates the accidental to be displayed in the key signature, represented in the same manner as the accidental element. It is used for disambiguating microtonal accidentals.
    
    ``complexType``: The key-accidental type indicates the accidental to be displayed in a non-traditional key signature, represented in the same manner as the accidental type without the formatting attributes.
    
    ``simpleContent``: The accidental-value type represents notated accidentals supported by MusicXML. In the MusicXML 2.0 DTD this was a string with values that could be included. The XSD strengthens the data typing to an enumerated list. The quarter- and three-quarters- accidentals are Tartini-style quarter-tone accidentals. The -down and -up accidentals are quarter-tone accidentals that include arrows pointing down or up. The slash- accidentals are used in Turkish classical music. The numbered sharp and flat accidentals are superscripted versions of the accidental signs, used in Turkish folk music. The sori and koron accidentals are microtonal sharp and flat accidentals used in Iranian and Persian music. The other accidental covers accidentals other than those listed here. It is usually used in combination with the smufl attribute to specify a particular SMuFL accidental. The smufl attribute may be used with any accidental value to help specify the appearance of symbols that share the same MusicXML semantics.
        
        Permitted Values: ['sharp', 'natural', 'flat', 'double-sharp', 'sharp-sharp', 'flat-flat', 'natural-sharp', 'natural-flat', 'quarter-flat', 'quarter-sharp', 'three-quarters-flat', 'three-quarters-sharp', 'sharp-down', 'sharp-up', 'natural-down', 'natural-up', 'flat-down', 'flat-up', 'double-sharp-down', 'double-sharp-up', 'flat-flat-down', 'flat-flat-up', 'arrow-down', 'arrow-up', 'triple-sharp', 'triple-flat', 'slash-quarter-sharp', 'slash-sharp', 'slash-flat', 'double-slash-flat', 'sharp-1', 'sharp-2', 'sharp-3', 'sharp-5', 'flat-1', 'flat-2', 'flat-3', 'flat-4', 'sori', 'koron', 'other']
    
    """
    
    TYPE = XSDComplexTypeKeyAccidental
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='key-accidental'][@type='key-accidental']"


class XMLSlashType(XMLElement):
    """
    The slash-type element indicates the graphical note type to use for the display of repetition marks.
    
    ``simpleType``: The note-type-value type is used for the MusicXML type element and represents the graphic note type, from 1024th (shortest) to maxima (longest).
        
        Permitted Values: ['1024th', '512th', '256th', '128th', '64th', '32nd', '16th', 'eighth', 'quarter', 'half', 'whole', 'breve', 'long', 'maxima']
    
    """
    
    TYPE = XSDSimpleTypeNoteTypeValue
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='slash-type'][@type='note-type-value']"


class XMLSlashDot(XMLElement):
    """
    The slash-dot element is used to specify any augmentation dots in the note type used to display repetition marks.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='slash-dot'][@type='empty']"


class XMLExceptVoice(XMLElement):
    """
    The except-voice element is used to specify a combination of slash notation and regular notation. Any note elements that are in voices specified by the except-voice elements are displayed in normal notation, in addition to the slash notation that is always displayed.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='except-voice'][@type='xs:string']"


class XMLBeats(XMLElement):
    """
    The beats element indicates the number of beats, as found in the numerator of a time signature.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='beats'][@type='xs:string']"


class XMLBeatType(XMLElement):
    """
    The beat-type element indicates the beat unit, as found in the denominator of a time signature.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='beat-type'][@type='xs:string']"


class XMLCancel(XMLElement):
    """
    ``complexType``: A cancel element indicates that the old key signature should be cancelled before the new one appears. This will always happen when changing to C major or A minor and need not be specified then. The cancel value matches the fifths value of the cancelled key signature (e.g., a cancel of -2 will provide an explicit cancellation for changing from B flat major to F major). The optional location attribute indicates where the cancellation appears relative to the new key signature.
    
    ``simpleContent``: The fifths type represents the number of flats or sharps in a traditional key signature. Negative numbers are used for flats and positive numbers for sharps, reflecting the key's placement within the circle of fifths (hence the type name).
    """
    
    TYPE = XSDComplexTypeCancel
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='cancel'][@type='cancel']"


class XMLFifths(XMLElement):
    """
    ``simpleType``: The fifths type represents the number of flats or sharps in a traditional key signature. Negative numbers are used for flats and positive numbers for sharps, reflecting the key's placement within the circle of fifths (hence the type name).
    """
    
    TYPE = XSDSimpleTypeFifths
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='fifths'][@type='fifths']"


class XMLMode(XMLElement):
    """
    ``simpleType``: The mode type is used to specify major/minor and other mode distinctions. Valid mode values include major, minor, dorian, phrygian, lydian, mixolydian, aeolian, ionian, locrian, and none.
    """
    
    TYPE = XSDSimpleTypeMode
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='mode'][@type='mode']"


class XMLDiatonic(XMLElement):
    """
    The diatonic element specifies the number of pitch steps needed to go from written to sounding pitch. This allows for correct spelling of enharmonic transpositions. This value does not include octave-change values; the values for both elements need to be added to the written pitch to get the correct sounding pitch.
    """
    
    TYPE = XSDSimpleTypeInteger
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='diatonic'][@type='xs:integer']"


class XMLChromatic(XMLElement):
    """
    The chromatic element represents the number of semitones needed to get from written to sounding pitch. This value does not include octave-change values; the values for both elements need to be added to the written pitch to get the correct sounding pitch.
    
    ``simpleType``: The semitones type is a number representing semitones, used for chromatic alteration. A value of -1 corresponds to a flat and a value of 1 to a sharp. Decimal values like 0.5 (quarter tone sharp) are used for microtones.
    """
    
    TYPE = XSDSimpleTypeSemitones
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='chromatic'][@type='semitones']"


class XMLOctaveChange(XMLElement):
    """
    The octave-change element indicates how many octaves to add to get from written pitch to sounding pitch. The octave-change element should be included when using transposition intervals of an octave or more, and should not be present for intervals of less than an octave.
    """
    
    TYPE = XSDSimpleTypeInteger
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='octave-change'][@type='xs:integer']"


class XMLDouble(XMLElement):
    """
    If the double element is present, it indicates that the music is doubled one octave from what is currently written.
    
    ``complexType``: The double type indicates that the music is doubled one octave from what is currently written. If the above attribute is set to yes, the doubling is one octave above what is written, as for mixed flute / piccolo parts in band literature. Otherwise the doubling is one octave below what is written, as for mixed cello / bass parts in orchestral literature.
    """
    
    TYPE = XSDComplexTypeDouble
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='double'][@type='double']"


class XMLBeatUnit(XMLElement):
    """
    The beat-unit element indicates the graphical note type to use in a metronome mark.
    
    ``simpleType``: The note-type-value type is used for the MusicXML type element and represents the graphic note type, from 1024th (shortest) to maxima (longest).
        
        Permitted Values: ['1024th', '512th', '256th', '128th', '64th', '32nd', '16th', 'eighth', 'quarter', 'half', 'whole', 'breve', 'long', 'maxima']
    
    """
    
    TYPE = XSDSimpleTypeNoteTypeValue
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='beat-unit'][@type='note-type-value']"


class XMLBeatUnitDot(XMLElement):
    """
    The beat-unit-dot element is used to specify any augmentation dots for a metronome mark note.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='beat-unit-dot'][@type='empty']"


class XMLRoot(XMLElement):
    """
    ``complexType``: The root type indicates a pitch like C, D, E vs. a scale degree like 1, 2, 3. It is used with chord symbols in popular music. The root element has a root-step and optional root-alter element similar to the step and alter elements, but renamed to distinguish the different musical meanings.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=root-step@minOccurs=1@maxOccurs=1
           Element@name=root-alter@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeRoot
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='root'][@type='root']"


class XMLNumeral(XMLElement):
    """
    ``complexType``: The numeral type represents the Roman numeral or Nashville number part of a harmony. It requires that the key be specified in the encoding, either with a key or numeral-key element.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=numeral-root@minOccurs=1@maxOccurs=1
           Element@name=numeral-alter@minOccurs=0@maxOccurs=1
           Element@name=numeral-key@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeNumeral
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='numeral'][@type='numeral']"


class XMLFunction(XMLElement):
    """
    The function element represents classical functional harmony with an indication like I, II, III rather than C, D, E. It represents the Roman numeral part of a functional harmony rather than the complete function itself. It has been deprecated as of MusicXML 4.0 in favor of the numeral element.
    
    ``complexType``: The style-text type represents a text element with a print-style attribute group.
    """
    
    TYPE = XSDComplexTypeStyleText
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='function'][@type='style-text']"


class XMLKind(XMLElement):
    """
    ``complexType``: Kind indicates the type of chord. Degree elements can then add, subtract, or alter from these starting points
    
    The attributes are used to indicate the formatting of the symbol. Since the kind element is the constant in all the harmony-chord groups that can make up a polychord, many formatting attributes are here.
    
    The use-symbols attribute is yes if the kind should be represented when possible with harmony symbols rather than letters and numbers. These symbols include:
    
    	major: a triangle, like Unicode 25B3
    	minor: -, like Unicode 002D
    	augmented: +, like Unicode 002B
    	diminished: °, like Unicode 00B0
    	half-diminished: ø, like Unicode 00F8
    
    For the major-minor kind, only the minor symbol is used when use-symbols is yes. The major symbol is set using the symbol attribute in the degree-value element. The corresponding degree-alter value will usually be 0 in this case.
    
    The text attribute describes how the kind should be spelled in a score. If use-symbols is yes, the value of the text attribute follows the symbol. The stack-degrees attribute is yes if the degree elements should be stacked above each other. The parentheses-degrees attribute is yes if all the degrees should be in parentheses. The bracket-degrees attribute is yes if all the degrees should be in a bracket. If not specified, these values are implementation-specific. The alignment attributes are for the entire harmony-chord group of which this kind element is a part.
    
    The text attribute may use strings such as "13sus" that refer to both the kind and one or more degree elements. In this case, the corresponding degree elements should have the print-object attribute set to "no" to keep redundant alterations from being displayed.
    
    ``simpleContent``: A kind-value indicates the type of chord. Degree elements can then add, subtract, or alter from these starting points. Values include:
    
    Triads:
        major (major third, perfect fifth)
        minor (minor third, perfect fifth)
        augmented (major third, augmented fifth)
        diminished (minor third, diminished fifth)
    Sevenths:
        dominant (major triad, minor seventh)
        major-seventh (major triad, major seventh)
        minor-seventh (minor triad, minor seventh)
        diminished-seventh (diminished triad, diminished seventh)
        augmented-seventh (augmented triad, minor seventh)
        half-diminished (diminished triad, minor seventh)
        major-minor (minor triad, major seventh)
    Sixths:
        major-sixth (major triad, added sixth)
        minor-sixth (minor triad, added sixth)
    Ninths:
        dominant-ninth (dominant-seventh, major ninth)
        major-ninth (major-seventh, major ninth)
        minor-ninth (minor-seventh, major ninth)
    11ths (usually as the basis for alteration):
        dominant-11th (dominant-ninth, perfect 11th)
        major-11th (major-ninth, perfect 11th)
        minor-11th (minor-ninth, perfect 11th)
    13ths (usually as the basis for alteration):
        dominant-13th (dominant-11th, major 13th)
        major-13th (major-11th, major 13th)
        minor-13th (minor-11th, major 13th)
    Suspended:
        suspended-second (major second, perfect fifth)
        suspended-fourth (perfect fourth, perfect fifth)
    Functional sixths:
        Neapolitan
        Italian
        French
        German
    Other:
        pedal (pedal-point bass)
        power (perfect fifth)
        Tristan
    
    The "other" kind is used when the harmony is entirely composed of add elements.
    
    The "none" kind is used to explicitly encode absence of chords or functional harmony. In this case, the root, numeral, or function element has no meaning. When using the root or numeral element, the root-step or numeral-step text attribute should be set to the empty string to keep the root or numeral from being displayed.
        
        Permitted Values: ['major', 'minor', 'augmented', 'diminished', 'dominant', 'major-seventh', 'minor-seventh', 'diminished-seventh', 'augmented-seventh', 'half-diminished', 'major-minor', 'major-sixth', 'minor-sixth', 'dominant-ninth', 'major-ninth', 'minor-ninth', 'dominant-11th', 'major-11th', 'minor-11th', 'dominant-13th', 'major-13th', 'minor-13th', 'suspended-second', 'suspended-fourth', 'Neapolitan', 'Italian', 'French', 'German', 'pedal', 'power', 'Tristan', 'other', 'none']
    
    """
    
    TYPE = XSDComplexTypeKind
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='kind'][@type='kind']"


class XMLInversion(XMLElement):
    """
    ``complexType``: The inversion type represents harmony inversions. The value is a number indicating which inversion is used: 0 for root position, 1 for first inversion, etc.  The text attribute indicates how the inversion should be displayed in a score.
    """
    
    TYPE = XSDComplexTypeInversion
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='inversion'][@type='inversion']"


class XMLBass(XMLElement):
    """
    ``complexType``: The bass type is used to indicate a bass note in popular music chord symbols, e.g. G/C. It is generally not used in functional harmony, as inversion is generally not used in pop chord symbols. As with root, it is divided into step and alter elements, similar to pitches. The arrangement attribute specifies where the bass is displayed relative to what precedes it.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=bass-separator@minOccurs=0@maxOccurs=1
           Element@name=bass-step@minOccurs=1@maxOccurs=1
           Element@name=bass-alter@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeBass
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='bass'][@type='bass']"


class XMLDegree(XMLElement):
    """
    ``complexType``: The degree type is used to add, alter, or subtract individual notes in the chord. The print-object attribute can be used to keep the degree from printing separately when it has already taken into account in the text attribute of the kind element. The degree-value and degree-type text attributes specify how the value and type of the degree should be displayed.
    
    A harmony of kind "other" can be spelled explicitly by using a series of degree elements together with a root.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=degree-value@minOccurs=1@maxOccurs=1
           Element@name=degree-alter@minOccurs=1@maxOccurs=1
           Element@name=degree-type@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeDegree
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='degree'][@type='degree']"


class XMLTopMargin(XMLElement):
    """
    ``simpleType``: The tenths type is a number representing tenths of interline staff space (positive or negative). Both integer and decimal values are allowed, such as 5 for a half space and 2.5 for a quarter space. Interline space is measured from the middle of a staff line.
    
    Distances in a MusicXML file are measured in tenths of staff space. Tenths are then scaled to millimeters within the scaling element, used in the defaults element at the start of a score. Individual staves can apply a scaling factor to adjust staff size. When a MusicXML element or attribute refers to tenths, it means the global tenths defined by the scaling element, not the local tenths as adjusted by the staff-size element.
    """
    
    TYPE = XSDSimpleTypeTenths
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='top-margin'][@type='tenths']"


class XMLBottomMargin(XMLElement):
    """
    ``simpleType``: The tenths type is a number representing tenths of interline staff space (positive or negative). Both integer and decimal values are allowed, such as 5 for a half space and 2.5 for a quarter space. Interline space is measured from the middle of a staff line.
    
    Distances in a MusicXML file are measured in tenths of staff space. Tenths are then scaled to millimeters within the scaling element, used in the defaults element at the start of a score. Individual staves can apply a scaling factor to adjust staff size. When a MusicXML element or attribute refers to tenths, it means the global tenths defined by the scaling element, not the local tenths as adjusted by the staff-size element.
    """
    
    TYPE = XSDSimpleTypeTenths
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='bottom-margin'][@type='tenths']"


class XMLPageLayout(XMLElement):
    """
    ``complexType``: Page layout can be defined both in score-wide defaults and in the print element. Page margins are specified either for both even and odd pages, or via separate odd and even page number values. The type is not needed when used as part of a print element. If omitted when used in the defaults element, "both" is the default.
    
    If no page-layout element is present in the defaults element, default page layout values are chosen by the application.
    
    When used in the print element, the page-layout element affects the appearance of the current page only. All other pages use the default values as determined by the defaults element. If any child elements are missing from the page-layout element in a print element, the values determined by the defaults element are used there as well.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Sequence@minOccurs=0@maxOccurs=1
               Element@name=page-height@minOccurs=1@maxOccurs=1
               Element@name=page-width@minOccurs=1@maxOccurs=1
           Element@name=page-margins@minOccurs=0@maxOccurs=2
    """
    
    TYPE = XSDComplexTypePageLayout
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='page-layout'][@type='page-layout']"


class XMLSystemLayout(XMLElement):
    """
    ``complexType``: A system is a group of staves that are read and played simultaneously. System layout includes left and right margins and the vertical distance from the previous system. The system distance is measured from the bottom line of the previous system to the top line of the current system. It is ignored for the first system on a page. The top system distance is measured from the page's top margin to the top line of the first system. It is ignored for all but the first system on a page.
    
    Sometimes the sum of measure widths in a system may not equal the system width specified by the layout elements due to roundoff or other errors. The behavior when reading MusicXML files in these cases is application-dependent. For instance, applications may find that the system layout data is more reliable than the sum of the measure widths, and adjust the measure widths accordingly.
    
    When used in the defaults element, the system-layout element defines a default appearance for all systems in the score. If no system-layout element is present in the defaults element, default system layout values are chosen by the application.
    
    When used in the print element, the system-layout element affects the appearance of the current system only. All other systems use the default values as determined by the defaults element. If any child elements are missing from the system-layout element in a print element, the values determined by the defaults element are used there as well. This type of system-layout element need only be read from or written to the first visible part in the score.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=system-margins@minOccurs=0@maxOccurs=1
           Element@name=system-distance@minOccurs=0@maxOccurs=1
           Element@name=top-system-distance@minOccurs=0@maxOccurs=1
           Element@name=system-dividers@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeSystemLayout
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='system-layout'][@type='system-layout']"


class XMLStaffLayout(XMLElement):
    """
    ``complexType``: Staff layout includes the vertical distance from the bottom line of the previous staff in this system to the top line of the staff specified by the number attribute. The optional number attribute refers to staff numbers within the part, from top to bottom on the system. A value of 1 is used if not present.
    
    When used in the defaults element, the values apply to all systems in all parts. When used in the print element, the values apply to the current system only. This value is ignored for the first staff in a system.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=staff-distance@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeStaffLayout
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='staff-layout'][@type='staff-layout']"


class XMLLeftMargin(XMLElement):
    """
    ``simpleType``: The tenths type is a number representing tenths of interline staff space (positive or negative). Both integer and decimal values are allowed, such as 5 for a half space and 2.5 for a quarter space. Interline space is measured from the middle of a staff line.
    
    Distances in a MusicXML file are measured in tenths of staff space. Tenths are then scaled to millimeters within the scaling element, used in the defaults element at the start of a score. Individual staves can apply a scaling factor to adjust staff size. When a MusicXML element or attribute refers to tenths, it means the global tenths defined by the scaling element, not the local tenths as adjusted by the staff-size element.
    """
    
    TYPE = XSDSimpleTypeTenths
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='left-margin'][@type='tenths']"


class XMLRightMargin(XMLElement):
    """
    ``simpleType``: The tenths type is a number representing tenths of interline staff space (positive or negative). Both integer and decimal values are allowed, such as 5 for a half space and 2.5 for a quarter space. Interline space is measured from the middle of a staff line.
    
    Distances in a MusicXML file are measured in tenths of staff space. Tenths are then scaled to millimeters within the scaling element, used in the defaults element at the start of a score. Individual staves can apply a scaling factor to adjust staff size. When a MusicXML element or attribute refers to tenths, it means the global tenths defined by the scaling element, not the local tenths as adjusted by the staff-size element.
    """
    
    TYPE = XSDSimpleTypeTenths
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='right-margin'][@type='tenths']"


class XMLDuration(XMLElement):
    """
    Duration is a positive number specified in division units. This is the intended duration vs. notated duration (for instance, differences in dotted notes in Baroque-era music). Differences in duration specific to an interpretation or performance should be represented using the note element's attack and release attributes.
    
    The duration element moves the musical position when used in backup elements, forward elements, and note elements that do not contain a chord child element.
    
    ``simpleType``: The positive-divisions type restricts divisions values to positive numbers.
    """
    
    TYPE = XSDSimpleTypePositiveDivisions
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='duration'][@type='positive-divisions']"


class XMLDisplayStep(XMLElement):
    """
    ``simpleType``: The step type represents a step of the diatonic scale, represented using the English letters A through G.
        
        Permitted Values: ['A', 'B', 'C', 'D', 'E', 'F', 'G']
    
    """
    
    TYPE = XSDSimpleTypeStep
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='display-step'][@type='step']"


class XMLDisplayOctave(XMLElement):
    """
    ``simpleType``: Octaves are represented by the numbers 0 to 9, where 4 indicates the octave started by middle C.
    """
    
    TYPE = XSDSimpleTypeOctave
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='display-octave'][@type='octave']"


class XMLChord(XMLElement):
    """
    The chord element indicates that this note is an additional chord tone with the preceding note.
    
    The duration of a chord note does not move the musical position within a measure. That is done by the duration of the first preceding note without a chord element. Thus the duration of a chord note cannot be longer than the preceding note.
    							
    In most cases the duration will be the same as the preceding note. However it can be shorter in situations such as multiple stops for string instruments.
    
    ``complexType``: The empty type represents an empty element with no attributes.
    """
    
    TYPE = XSDComplexTypeEmpty
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='chord'][@type='empty']"


class XMLPitch(XMLElement):
    """
    ``complexType``: Pitch is represented as a combination of the step of the diatonic scale, the chromatic alteration, and the octave.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=step@minOccurs=1@maxOccurs=1
           Element@name=alter@minOccurs=0@maxOccurs=1
           Element@name=octave@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypePitch
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='pitch'][@type='pitch']"


class XMLUnpitched(XMLElement):
    """
    ``complexType``: The unpitched type represents musical elements that are notated on the staff but lack definite pitch, such as unpitched percussion and speaking voice. If the child elements are not present, the note is placed on the middle line of the staff. This is generally used with a one-line staff. Notes in percussion clef should always use an unpitched element rather than a pitch element.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Group@name=display-step-octave@minOccurs=0@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=display-step@minOccurs=1@maxOccurs=1
                   Element@name=display-octave@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeUnpitched
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='unpitched'][@type='unpitched']"


class XMLRest(XMLElement):
    """
    ``complexType``: The rest element indicates notated rests or silences. Rest elements are usually empty, but placement on the staff can be specified using display-step and display-octave elements. If the measure attribute is set to yes, this indicates this is a complete measure rest.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Group@name=display-step-octave@minOccurs=0@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=display-step@minOccurs=1@maxOccurs=1
                   Element@name=display-octave@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeRest
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='rest'][@type='rest']"


class XMLNote(XMLElement):
    """
    ``complexType``: Notes are the most common type of MusicXML data. The MusicXML format distinguishes between elements used for sound information and elements used for notation information (e.g., tie is used for sound, tied for notation). Thus grace notes do not have a duration element. Cue notes have a duration element, as do forward elements, but no tie elements. Having these two types of information available can make interchange easier, as some programs handle one type of information more readily than the other.
    
    The print-leger attribute is used to indicate whether leger lines are printed. Notes without leger lines are used to indicate indeterminate high and low notes. By default, it is set to yes. If print-object is set to no, print-leger is interpreted to also be set to no if not present. This attribute is ignored for rests.
    
    The dynamics and end-dynamics attributes correspond to MIDI 1.0's Note On and Note Off velocities, respectively. They are expressed in terms of percentages of the default forte value (90 for MIDI 1.0).
    
    The attack and release attributes are used to alter the starting and stopping time of the note from when it would otherwise occur based on the flow of durations - information that is specific to a performance. They are expressed in terms of divisions, either positive or negative. A note that starts a tie should not have a release attribute, and a note that stops a tie should not have an attack attribute. The attack and release attributes are independent of each other. The attack attribute only changes the starting time of a note, and the release attribute only changes the stopping time of a note.
    
    If a note is played only particular times through a repeat, the time-only attribute shows which times to play the note.
    
    The pizzicato attribute is used when just this note is sounded pizzicato, vs. the pizzicato element which changes overall playback between pizzicato and arco.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Choice@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Group@name=full-note@minOccurs=1@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=chord@minOccurs=0@maxOccurs=1
                           Choice@minOccurs=1@maxOccurs=1
                               Element@name=pitch@minOccurs=1@maxOccurs=1
                               Element@name=unpitched@minOccurs=1@maxOccurs=1
                               Element@name=rest@minOccurs=1@maxOccurs=1
                   Group@name=duration@minOccurs=1@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=duration@minOccurs=1@maxOccurs=1
                   Element@name=tie@minOccurs=0@maxOccurs=2
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=cue@minOccurs=1@maxOccurs=1
                   Group@name=full-note@minOccurs=1@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=chord@minOccurs=0@maxOccurs=1
                           Choice@minOccurs=1@maxOccurs=1
                               Element@name=pitch@minOccurs=1@maxOccurs=1
                               Element@name=unpitched@minOccurs=1@maxOccurs=1
                               Element@name=rest@minOccurs=1@maxOccurs=1
                   Group@name=duration@minOccurs=1@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=duration@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=grace@minOccurs=1@maxOccurs=1
                   Choice@minOccurs=1@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Group@name=full-note@minOccurs=1@maxOccurs=1
                               Sequence@minOccurs=1@maxOccurs=1
                                   Element@name=chord@minOccurs=0@maxOccurs=1
                                   Choice@minOccurs=1@maxOccurs=1
                                       Element@name=pitch@minOccurs=1@maxOccurs=1
                                       Element@name=unpitched@minOccurs=1@maxOccurs=1
                                       Element@name=rest@minOccurs=1@maxOccurs=1
                           Element@name=tie@minOccurs=0@maxOccurs=2
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=cue@minOccurs=1@maxOccurs=1
                           Group@name=full-note@minOccurs=1@maxOccurs=1
                               Sequence@minOccurs=1@maxOccurs=1
                                   Element@name=chord@minOccurs=0@maxOccurs=1
                                   Choice@minOccurs=1@maxOccurs=1
                                       Element@name=pitch@minOccurs=1@maxOccurs=1
                                       Element@name=unpitched@minOccurs=1@maxOccurs=1
                                       Element@name=rest@minOccurs=1@maxOccurs=1
           Element@name=instrument@minOccurs=0@maxOccurs=unbounded
           Group@name=editorial-voice@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Group@name=footnote@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=footnote@minOccurs=1@maxOccurs=1
                   Group@name=level@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=level@minOccurs=1@maxOccurs=1
                   Group@name=voice@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=voice@minOccurs=1@maxOccurs=1
           Element@name=type@minOccurs=0@maxOccurs=1
           Element@name=dot@minOccurs=0@maxOccurs=unbounded
           Element@name=accidental@minOccurs=0@maxOccurs=1
           Element@name=time-modification@minOccurs=0@maxOccurs=1
           Element@name=stem@minOccurs=0@maxOccurs=1
           Element@name=notehead@minOccurs=0@maxOccurs=1
           Element@name=notehead-text@minOccurs=0@maxOccurs=1
           Group@name=staff@minOccurs=0@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=staff@minOccurs=1@maxOccurs=1
           Element@name=beam@minOccurs=0@maxOccurs=8
           Element@name=notations@minOccurs=0@maxOccurs=unbounded
           Element@name=lyric@minOccurs=0@maxOccurs=unbounded
           Element@name=play@minOccurs=0@maxOccurs=1
           Element@name=listen@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeNote
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='note'][@type='note']"


class XMLBackup(XMLElement):
    """
    ``complexType``: The backup and forward elements are required to coordinate multiple voices in one part, including music on multiple staves. The backup type is generally used to move between voices and staves. Thus the backup element does not include voice or staff elements. Duration values should always be positive, and should not cross measure boundaries or mid-measure changes in the divisions value.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Group@name=duration@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=duration@minOccurs=1@maxOccurs=1
           Group@name=editorial@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Group@name=footnote@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=footnote@minOccurs=1@maxOccurs=1
                   Group@name=level@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=level@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeBackup
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='backup'][@type='backup']"


class XMLForward(XMLElement):
    """
    ``complexType``: The backup and forward elements are required to coordinate multiple voices in one part, including music on multiple staves. The forward element is generally used within voices and staves. Duration values should always be positive, and should not cross measure boundaries or mid-measure changes in the divisions value.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Group@name=duration@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=duration@minOccurs=1@maxOccurs=1
           Group@name=editorial-voice@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Group@name=footnote@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=footnote@minOccurs=1@maxOccurs=1
                   Group@name=level@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=level@minOccurs=1@maxOccurs=1
                   Group@name=voice@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=voice@minOccurs=1@maxOccurs=1
           Group@name=staff@minOccurs=0@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=staff@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeForward
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='forward'][@type='forward']"


class XMLDirection(XMLElement):
    """
    ``complexType``: A direction is a musical indication that is not necessarily attached to a specific note. Two or more may be combined to indicate words followed by the start of a dashed line, the end of a wedge followed by dynamics, etc. For applications where a specific direction is indeed attached to a specific note, the direction element can be associated with the first note element that follows it in score order that is not in a different voice.
    
    By default, a series of direction-type elements and a series of child elements of a direction-type within a single direction element follow one another in sequence visually. For a series of direction-type children, non-positional formatting attributes are carried over from the previous element by default.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=direction-type@minOccurs=1@maxOccurs=unbounded
           Element@name=offset@minOccurs=0@maxOccurs=1
           Group@name=editorial-voice-direction@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Group@name=footnote@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=footnote@minOccurs=1@maxOccurs=1
                   Group@name=level@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=level@minOccurs=1@maxOccurs=1
                   Group@name=voice@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=voice@minOccurs=1@maxOccurs=1
           Group@name=staff@minOccurs=0@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=staff@minOccurs=1@maxOccurs=1
           Element@name=sound@minOccurs=0@maxOccurs=1
           Element@name=listening@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeDirection
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='direction'][@type='direction']"


class XMLAttributes(XMLElement):
    """
    ``complexType``: The attributes element contains musical information that typically changes on measure boundaries. This includes key and time signatures, clefs, transpositions, and staving. When attributes are changed mid-measure, it affects the music in score order, not in MusicXML document order.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Group@name=editorial@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Group@name=footnote@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=footnote@minOccurs=1@maxOccurs=1
                   Group@name=level@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=level@minOccurs=1@maxOccurs=1
           Element@name=divisions@minOccurs=0@maxOccurs=1
           Element@name=key@minOccurs=0@maxOccurs=unbounded
           Element@name=time@minOccurs=0@maxOccurs=unbounded
           Element@name=staves@minOccurs=0@maxOccurs=1
           Element@name=part-symbol@minOccurs=0@maxOccurs=1
           Element@name=instruments@minOccurs=0@maxOccurs=1
           Element@name=clef@minOccurs=0@maxOccurs=unbounded
           Element@name=staff-details@minOccurs=0@maxOccurs=unbounded
           Choice@minOccurs=1@maxOccurs=1
               Element@name=transpose@minOccurs=0@maxOccurs=unbounded
               Element@name=for-part@minOccurs=0@maxOccurs=unbounded
           Element@name=directive@minOccurs=0@maxOccurs=unbounded
           Element@name=measure-style@minOccurs=0@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypeAttributes
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='attributes'][@type='attributes']"


class XMLHarmony(XMLElement):
    """
    ``complexType``: The harmony type represents harmony analysis, including chord symbols in popular music as well as functional harmony analysis in classical music.
    
    If there are alternate harmonies possible, this can be specified using multiple harmony elements differentiated by type. Explicit harmonies have all note present in the music; implied have some notes missing but implied; alternate represents alternate analyses.
    
    The print-object attribute controls whether or not anything is printed due to the harmony element. The print-frame attribute controls printing of a frame or fretboard diagram. The print-style attribute group sets the default for the harmony, but individual elements can override this with their own print-style values. The arrangement attribute specifies how multiple harmony-chord groups are arranged relative to each other. Harmony-chords with vertical arrangement are separated by horizontal lines. Harmony-chords with diagonal or horizontal arrangement are separated by diagonal lines or slashes.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Group@name=harmony-chord@minOccurs=1@maxOccurs=unbounded
               Sequence@minOccurs=1@maxOccurs=1
                   Choice@minOccurs=1@maxOccurs=1
                       Element@name=root@minOccurs=1@maxOccurs=1
                       Element@name=numeral@minOccurs=1@maxOccurs=1
                       Element@name=function@minOccurs=1@maxOccurs=1
                   Element@name=kind@minOccurs=1@maxOccurs=1
                   Element@name=inversion@minOccurs=0@maxOccurs=1
                   Element@name=bass@minOccurs=0@maxOccurs=1
                   Element@name=degree@minOccurs=0@maxOccurs=unbounded
           Element@name=frame@minOccurs=0@maxOccurs=1
           Element@name=offset@minOccurs=0@maxOccurs=1
           Group@name=editorial@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Group@name=footnote@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=footnote@minOccurs=1@maxOccurs=1
                   Group@name=level@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=level@minOccurs=1@maxOccurs=1
           Group@name=staff@minOccurs=0@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=staff@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeHarmony
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='harmony'][@type='harmony']"


class XMLFiguredBass(XMLElement):
    """
    ``complexType``: The figured-bass element represents figured bass notation. Figured bass elements take their position from the first regular note (not a grace note or chord note) that follows in score order. The optional duration element is used to indicate changes of figures under a note.
    
    Figures are ordered from top to bottom. The value of parentheses is "no" if not present.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=figure@minOccurs=1@maxOccurs=unbounded
           Group@name=duration@minOccurs=0@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=duration@minOccurs=1@maxOccurs=1
           Group@name=editorial@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Group@name=footnote@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=footnote@minOccurs=1@maxOccurs=1
                   Group@name=level@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=level@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeFiguredBass
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='figured-bass'][@type='figured-bass']"


class XMLPrint(XMLElement):
    """
    ``complexType``: The print type contains general printing parameters, including layout elements. The part-name-display and part-abbreviation-display elements may also be used here to change how a part name or abbreviation is displayed over the course of a piece. They take effect when the current measure or a succeeding measure starts a new system.
    
    Layout group elements in a print element only apply to the current page, system, or staff. Music that follows continues to take the default values from the layout determined by the defaults element.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Group@name=layout@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=page-layout@minOccurs=0@maxOccurs=1
                   Element@name=system-layout@minOccurs=0@maxOccurs=1
                   Element@name=staff-layout@minOccurs=0@maxOccurs=unbounded
           Element@name=measure-layout@minOccurs=0@maxOccurs=1
           Element@name=measure-numbering@minOccurs=0@maxOccurs=1
           Element@name=part-name-display@minOccurs=0@maxOccurs=1
           Element@name=part-abbreviation-display@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypePrint
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='print'][@type='print']"


class XMLBarline(XMLElement):
    """
    ``complexType``: If a barline is other than a normal single barline, it should be represented by a barline type that describes it. This includes information about repeats and multiple endings, as well as line style. Barline data is on the same level as the other musical data in a score - a child of a measure in a partwise score, or a part in a timewise score. This allows for barlines within measures, as in dotted barlines that subdivide measures in complex meters. The two fermata elements allow for fermatas on both sides of the barline (the lower one inverted).
    
    Barlines have a location attribute to make it easier to process barlines independently of the other musical data in a score. It is often easier to set up measures separately from entering notes. The location attribute must match where the barline element occurs within the rest of the musical data in the score. If location is left, it should be the first element in the measure, aside from the print, bookmark, and link elements. If location is right, it should be the last element, again with the possible exception of the print, bookmark, and link elements. If no location is specified, the right barline is the default. The segno, coda, and divisions attributes work the same way as in the sound element. They are used for playback when barline elements contain segno or coda child elements.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=bar-style@minOccurs=0@maxOccurs=1
           Group@name=editorial@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Group@name=footnote@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=footnote@minOccurs=1@maxOccurs=1
                   Group@name=level@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=level@minOccurs=1@maxOccurs=1
           Element@name=wavy-line@minOccurs=0@maxOccurs=1
           Element@name=segno@minOccurs=0@maxOccurs=1
           Element@name=coda@minOccurs=0@maxOccurs=1
           Element@name=fermata@minOccurs=0@maxOccurs=2
           Element@name=ending@minOccurs=0@maxOccurs=1
           Element@name=repeat@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeBarline
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='barline'][@type='barline']"


class XMLGrouping(XMLElement):
    """
    ``complexType``: The grouping type is used for musical analysis. When the type attribute is "start" or "single", it usually contains one or more feature elements. The number attribute is used for distinguishing between overlapping and hierarchical groupings. The member-of attribute allows for easy distinguishing of what grouping elements are in what hierarchy. Feature elements contained within a "stop" type of grouping may be ignored.
    
    This element is flexible to allow for different types of analyses. Future versions of the MusicXML format may add elements that can represent more standardized categories of analysis data, allowing for easier data sharing.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=feature@minOccurs=0@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypeGrouping
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='grouping'][@type='grouping']"


class XMLPartGroup(XMLElement):
    """
    ``complexType``: The part-group element indicates groupings of parts in the score, usually indicated by braces and brackets. Braces that are used for multi-staff parts should be defined in the attributes element for that part. The part-group start element appears before the first score-part in the group. The part-group stop element appears after the last score-part in the group.
    
    The number attribute is used to distinguish overlapping and nested part-groups, not the sequence of groups. As with parts, groups can have a name and abbreviation. Values for the child elements are ignored at the stop of a group.
    
    A part-group element is not needed for a single multi-staff part. By default, multi-staff parts include a brace symbol and (if appropriate given the bar-style) common barlines. The symbol formatting for a multi-staff part can be more fully specified using the part-symbol element.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=group-name@minOccurs=0@maxOccurs=1
           Element@name=group-name-display@minOccurs=0@maxOccurs=1
           Element@name=group-abbreviation@minOccurs=0@maxOccurs=1
           Element@name=group-abbreviation-display@minOccurs=0@maxOccurs=1
           Element@name=group-symbol@minOccurs=0@maxOccurs=1
           Element@name=group-barline@minOccurs=0@maxOccurs=1
           Element@name=group-time@minOccurs=0@maxOccurs=1
           Group@name=editorial@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Group@name=footnote@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=footnote@minOccurs=1@maxOccurs=1
                   Group@name=level@minOccurs=0@maxOccurs=1
                       Sequence@minOccurs=1@maxOccurs=1
                           Element@name=level@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypePartGroup
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='part-group'][@type='part-group']"


class XMLWork(XMLElement):
    """
    ``complexType``: Works are optionally identified by number and title. The work type also may indicate a link to the opus document that composes multiple scores into a collection.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=work-number@minOccurs=0@maxOccurs=1
           Element@name=work-title@minOccurs=0@maxOccurs=1
           Element@name=opus@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeWork
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='work'][@type='work']"


class XMLMovementNumber(XMLElement):
    """
    The movement-number element specifies the number of a movement.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='movement-number'][@type='xs:string']"


class XMLMovementTitle(XMLElement):
    """
    The movement-title element specifies the title of a movement, not including its number.
    """
    
    TYPE = XSDSimpleTypeString
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='movement-title'][@type='xs:string']"


class XMLDefaults(XMLElement):
    """
    ``complexType``: The defaults type specifies score-wide defaults for scaling; whether or not the file is a concert score; layout; and default values for the music font, word font, lyric font, and lyric language. Except for the concert-score element, if any defaults are missing, the choice of what to use is determined by the application.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=scaling@minOccurs=0@maxOccurs=1
           Element@name=concert-score@minOccurs=0@maxOccurs=1
           Group@name=layout@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=page-layout@minOccurs=0@maxOccurs=1
                   Element@name=system-layout@minOccurs=0@maxOccurs=1
                   Element@name=staff-layout@minOccurs=0@maxOccurs=unbounded
           Element@name=appearance@minOccurs=0@maxOccurs=1
           Element@name=music-font@minOccurs=0@maxOccurs=1
           Element@name=word-font@minOccurs=0@maxOccurs=1
           Element@name=lyric-font@minOccurs=0@maxOccurs=unbounded
           Element@name=lyric-language@minOccurs=0@maxOccurs=unbounded
    """
    
    TYPE = XSDComplexTypeDefaults
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='defaults'][@type='defaults']"


class XMLCredit(XMLElement):
    """
    ``complexType``: The credit type represents the appearance of the title, composer, arranger, lyricist, copyright, dedication, and other text, symbols, and graphics that commonly appear on the first page of a score. The credit-words, credit-symbol, and credit-image elements are similar to the words, symbol, and image elements for directions. However, since the credit is not part of a measure, the default-x and default-y attributes adjust the origin relative to the bottom left-hand corner of the page. The enclosure for credit-words and credit-symbol is none by default.
    
    By default, a series of credit-words and credit-symbol elements within a single credit element follow one another in sequence visually. Non-positional formatting attributes are carried over from the previous element by default.
    
    The page attribute for the credit element specifies the page number where the credit should appear. This is an integer value that starts with 1 for the first page. Its value is 1 by default. Since credits occur before the music, these page numbers do not refer to the page numbering specified by the print element's page-number attribute.
    
    The credit-type element indicates the purpose behind a credit. Multiple types of data may be combined in a single credit, so multiple elements may be used. Standard values include page number, title, subtitle, composer, arranger, lyricist, rights, and part name.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=credit-type@minOccurs=0@maxOccurs=unbounded
           Element@name=link@minOccurs=0@maxOccurs=unbounded
           Element@name=bookmark@minOccurs=0@maxOccurs=unbounded
           Choice@minOccurs=1@maxOccurs=1
               Element@name=credit-image@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Choice@minOccurs=1@maxOccurs=1
                       Element@name=credit-words@minOccurs=1@maxOccurs=1
                       Element@name=credit-symbol@minOccurs=1@maxOccurs=1
                   Sequence@minOccurs=0@maxOccurs=unbounded
                       Element@name=link@minOccurs=0@maxOccurs=unbounded
                       Element@name=bookmark@minOccurs=0@maxOccurs=unbounded
                       Choice@minOccurs=1@maxOccurs=1
                           Element@name=credit-words@minOccurs=1@maxOccurs=1
                           Element@name=credit-symbol@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeCredit
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='credit'][@type='credit']"


class XMLPartList(XMLElement):
    """
    ``complexType``: The part-list identifies the different musical parts in this document. Each part has an ID that is used later within the musical data. Since parts may be encoded separately and combined later, identification elements are present at both the score and score-part levels. There must be at least one score-part, combined as desired with part-group elements that indicate braces and brackets. Parts are ordered from top to bottom in a score based on the order in which they appear in the part-list.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Group@name=part-group@minOccurs=0@maxOccurs=unbounded
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=part-group@minOccurs=1@maxOccurs=1
           Group@name=score-part@minOccurs=1@maxOccurs=1
               Sequence@minOccurs=1@maxOccurs=1
                   Element@name=score-part@minOccurs=1@maxOccurs=1
           Choice@minOccurs=0@maxOccurs=unbounded
               Group@name=part-group@minOccurs=1@maxOccurs=1
                   Sequence@minOccurs=1@maxOccurs=1
                       Element@name=part-group@minOccurs=1@maxOccurs=1
               Group@name=score-part@minOccurs=1@maxOccurs=1
                   Sequence@minOccurs=1@maxOccurs=1
                       Element@name=score-part@minOccurs=1@maxOccurs=1
    """
    
    TYPE = XSDComplexTypePartList
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='part-list'][@type='part-list']"


class XMLScorePart(XMLElement):
    """
    Each MusicXML part corresponds to a track in a Standard MIDI Format 1 file. The score-instrument elements are used when there are multiple instruments per track. The midi-device element is used to make a MIDI device or port assignment for the given track. Initial midi-instrument assignments may be made here as well.
    
    ``complexType``: The score-part type collects part-wide information for each part in a score. Often, each MusicXML part corresponds to a track in a Standard MIDI Format 1 file. In this case, the midi-device element is used to make a MIDI device or port assignment for the given track or specific MIDI instruments. Initial midi-instrument assignments may be made here as well. The score-instrument elements are used when there are multiple instruments per track.

    ``XSD structure:``

    .. code-block::

       Sequence@minOccurs=1@maxOccurs=1
           Element@name=identification@minOccurs=0@maxOccurs=1
           Element@name=part-link@minOccurs=0@maxOccurs=unbounded
           Element@name=part-name@minOccurs=1@maxOccurs=1
           Element@name=part-name-display@minOccurs=0@maxOccurs=1
           Element@name=part-abbreviation@minOccurs=0@maxOccurs=1
           Element@name=part-abbreviation-display@minOccurs=0@maxOccurs=1
           Element@name=group@minOccurs=0@maxOccurs=unbounded
           Element@name=score-instrument@minOccurs=0@maxOccurs=unbounded
           Element@name=player@minOccurs=0@maxOccurs=unbounded
           Sequence@minOccurs=0@maxOccurs=unbounded
               Element@name=midi-device@minOccurs=0@maxOccurs=1
               Element@name=midi-instrument@minOccurs=0@maxOccurs=1
    """
    
    TYPE = XSDComplexTypeScorePart
    _SEARCH_FOR_ELEMENT = ".//{*}element[@name='score-part'][@type='score-part']"

__all__=['XMLScorePartwise', 'XMLPart', 'XMLMeasure', 'XMLDirective', 'XMLP', 'XMLPp', 'XMLPpp', 'XMLPppp', 'XMLPpppp', 'XMLPppppp', 'XMLF', 'XMLFf', 'XMLFff', 'XMLFfff', 'XMLFffff', 'XMLFfffff', 'XMLMp', 'XMLMf', 'XMLSf', 'XMLSfp', 'XMLSfpp', 'XMLFp', 'XMLRf', 'XMLRfz', 'XMLSfz', 'XMLSffz', 'XMLFz', 'XMLN', 'XMLPf', 'XMLSfzp', 'XMLOtherDynamics', 'XMLMidiChannel', 'XMLMidiName', 'XMLMidiBank', 'XMLMidiProgram', 'XMLMidiUnpitched', 'XMLVolume', 'XMLPan', 'XMLElevation', 'XMLDisplayText', 'XMLAccidentalText', 'XMLIpa', 'XMLMute', 'XMLSemiPitched', 'XMLOtherPlay', 'XMLDivisions', 'XMLKey', 'XMLTime', 'XMLStaves', 'XMLPartSymbol', 'XMLInstruments', 'XMLClef', 'XMLStaffDetails', 'XMLTranspose', 'XMLForPart', 'XMLMeasureStyle', 'XMLPartClef', 'XMLPartTranspose', 'XMLTimeRelation', 'XMLKeyOctave', 'XMLMultipleRest', 'XMLMeasureRepeat', 'XMLBeatRepeat', 'XMLSlash', 'XMLStaffType', 'XMLStaffLines', 'XMLLineDetail', 'XMLStaffTuning', 'XMLCapo', 'XMLStaffSize', 'XMLInterchangeable', 'XMLSenzaMisura', 'XMLBarStyle', 'XMLWavyLine', 'XMLSegno', 'XMLCoda', 'XMLFermata', 'XMLEnding', 'XMLRepeat', 'XMLAccordionHigh', 'XMLAccordionMiddle', 'XMLAccordionLow', 'XMLBassSeparator', 'XMLBassStep', 'XMLBassAlter', 'XMLDegreeValue', 'XMLDegreeAlter', 'XMLDegreeType', 'XMLDirectionType', 'XMLOffset', 'XMLSound', 'XMLListening', 'XMLRehearsal', 'XMLWords', 'XMLSymbol', 'XMLWedge', 'XMLDynamics', 'XMLDashes', 'XMLBracket', 'XMLPedal', 'XMLMetronome', 'XMLOctaveShift', 'XMLHarpPedals', 'XMLDamp', 'XMLDampAll', 'XMLEyeglasses', 'XMLStringMute', 'XMLScordatura', 'XMLImage', 'XMLPrincipalVoice', 'XMLPercussion', 'XMLAccordionRegistration', 'XMLStaffDivide', 'XMLOtherDirection', 'XMLFrameStrings', 'XMLFrameFrets', 'XMLFirstFret', 'XMLFrameNote', 'XMLString', 'XMLFret', 'XMLFingering', 'XMLBarre', 'XMLFeature', 'XMLFrame', 'XMLPedalTuning', 'XMLSync', 'XMLOtherListening', 'XMLBeatUnitTied', 'XMLPerMinute', 'XMLMetronomeArrows', 'XMLMetronomeNote', 'XMLMetronomeRelation', 'XMLMetronomeType', 'XMLMetronomeDot', 'XMLMetronomeBeam', 'XMLMetronomeTied', 'XMLMetronomeTuplet', 'XMLNumeralRoot', 'XMLNumeralAlter', 'XMLNumeralKey', 'XMLNumeralFifths', 'XMLNumeralMode', 'XMLPedalStep', 'XMLPedalAlter', 'XMLGlass', 'XMLMetal', 'XMLWood', 'XMLPitched', 'XMLMembrane', 'XMLEffect', 'XMLTimpani', 'XMLBeater', 'XMLStick', 'XMLStickLocation', 'XMLOtherPercussion', 'XMLMeasureLayout', 'XMLMeasureNumbering', 'XMLPartNameDisplay', 'XMLPartAbbreviationDisplay', 'XMLRootStep', 'XMLRootAlter', 'XMLAccord', 'XMLInstrumentChange', 'XMLMidiDevice', 'XMLMidiInstrument', 'XMLPlay', 'XMLSwing', 'XMLStickType', 'XMLStickMaterial', 'XMLStraight', 'XMLFirst', 'XMLSecond', 'XMLSwingType', 'XMLSwingStyle', 'XMLEncodingDate', 'XMLEncoder', 'XMLSoftware', 'XMLEncodingDescription', 'XMLSupports', 'XMLCreator', 'XMLRights', 'XMLEncoding', 'XMLSource', 'XMLRelation', 'XMLMiscellaneous', 'XMLMiscellaneousField', 'XMLLineWidth', 'XMLNoteSize', 'XMLDistance', 'XMLGlyph', 'XMLOtherAppearance', 'XMLMeasureDistance', 'XMLPageHeight', 'XMLPageWidth', 'XMLPageMargins', 'XMLMillimeters', 'XMLTenths', 'XMLStaffDistance', 'XMLLeftDivider', 'XMLRightDivider', 'XMLSystemMargins', 'XMLSystemDistance', 'XMLTopSystemDistance', 'XMLSystemDividers', 'XMLAccent', 'XMLStrongAccent', 'XMLStaccato', 'XMLTenuto', 'XMLDetachedLegato', 'XMLStaccatissimo', 'XMLSpiccato', 'XMLScoop', 'XMLPlop', 'XMLDoit', 'XMLFalloff', 'XMLBreathMark', 'XMLCaesura', 'XMLStress', 'XMLUnstress', 'XMLSoftAccent', 'XMLOtherArticulation', 'XMLArrowDirection', 'XMLArrowStyle', 'XMLArrowhead', 'XMLCircularArrow', 'XMLBendAlter', 'XMLPreBend', 'XMLRelease', 'XMLWithBar', 'XMLPrefix', 'XMLFigureNumber', 'XMLSuffix', 'XMLExtend', 'XMLFigure', 'XMLHarmonClosed', 'XMLNatural', 'XMLArtificial', 'XMLBasePitch', 'XMLTouchingPitch', 'XMLSoundingPitch', 'XMLHoleType', 'XMLHoleClosed', 'XMLHoleShape', 'XMLAssess', 'XMLWait', 'XMLOtherListen', 'XMLSyllabic', 'XMLText', 'XMLElision', 'XMLLaughing', 'XMLHumming', 'XMLEndLine', 'XMLEndParagraph', 'XMLTied', 'XMLSlur', 'XMLTuplet', 'XMLGlissando', 'XMLSlide', 'XMLOrnaments', 'XMLTechnical', 'XMLArticulations', 'XMLArpeggiate', 'XMLNonArpeggiate', 'XMLAccidentalMark', 'XMLOtherNotation', 'XMLGrace', 'XMLTie', 'XMLCue', 'XMLInstrument', 'XMLType', 'XMLDot', 'XMLAccidental', 'XMLTimeModification', 'XMLStem', 'XMLNotehead', 'XMLNoteheadText', 'XMLBeam', 'XMLNotations', 'XMLLyric', 'XMLListen', 'XMLTrillMark', 'XMLTurn', 'XMLDelayedTurn', 'XMLInvertedTurn', 'XMLDelayedInvertedTurn', 'XMLVerticalTurn', 'XMLInvertedVerticalTurn', 'XMLShake', 'XMLMordent', 'XMLInvertedMordent', 'XMLSchleifer', 'XMLTremolo', 'XMLHaydn', 'XMLOtherOrnament', 'XMLStep', 'XMLAlter', 'XMLOctave', 'XMLUpBow', 'XMLDownBow', 'XMLHarmonic', 'XMLOpenString', 'XMLThumbPosition', 'XMLPluck', 'XMLDoubleTongue', 'XMLTripleTongue', 'XMLStopped', 'XMLSnapPizzicato', 'XMLHammerOn', 'XMLPullOff', 'XMLBend', 'XMLTap', 'XMLHeel', 'XMLToe', 'XMLFingernails', 'XMLHole', 'XMLArrow', 'XMLHandbell', 'XMLBrassBend', 'XMLFlip', 'XMLSmear', 'XMLOpen', 'XMLHalfMuted', 'XMLHarmonMute', 'XMLGolpe', 'XMLOtherTechnical', 'XMLActualNotes', 'XMLNormalNotes', 'XMLNormalType', 'XMLNormalDot', 'XMLTupletActual', 'XMLTupletNormal', 'XMLTupletNumber', 'XMLTupletType', 'XMLTupletDot', 'XMLCreditType', 'XMLLink', 'XMLBookmark', 'XMLCreditImage', 'XMLCreditWords', 'XMLCreditSymbol', 'XMLScaling', 'XMLConcertScore', 'XMLAppearance', 'XMLMusicFont', 'XMLWordFont', 'XMLLyricFont', 'XMLLyricLanguage', 'XMLGroupName', 'XMLGroupNameDisplay', 'XMLGroupAbbreviation', 'XMLGroupAbbreviationDisplay', 'XMLGroupSymbol', 'XMLGroupBarline', 'XMLGroupTime', 'XMLInstrumentLink', 'XMLGroupLink', 'XMLPlayerName', 'XMLInstrumentName', 'XMLInstrumentAbbreviation', 'XMLIdentification', 'XMLPartLink', 'XMLPartName', 'XMLPartAbbreviation', 'XMLGroup', 'XMLScoreInstrument', 'XMLPlayer', 'XMLVirtualLibrary', 'XMLVirtualName', 'XMLWorkNumber', 'XMLWorkTitle', 'XMLOpus', 'XMLFootnote', 'XMLLevel', 'XMLStaff', 'XMLTuningStep', 'XMLTuningAlter', 'XMLTuningOctave', 'XMLInstrumentSound', 'XMLSolo', 'XMLEnsemble', 'XMLVirtualInstrument', 'XMLVoice', 'XMLSign', 'XMLLine', 'XMLClefOctaveChange', 'XMLKeyStep', 'XMLKeyAlter', 'XMLKeyAccidental', 'XMLSlashType', 'XMLSlashDot', 'XMLExceptVoice', 'XMLBeats', 'XMLBeatType', 'XMLCancel', 'XMLFifths', 'XMLMode', 'XMLDiatonic', 'XMLChromatic', 'XMLOctaveChange', 'XMLDouble', 'XMLBeatUnit', 'XMLBeatUnitDot', 'XMLRoot', 'XMLNumeral', 'XMLFunction', 'XMLKind', 'XMLInversion', 'XMLBass', 'XMLDegree', 'XMLTopMargin', 'XMLBottomMargin', 'XMLPageLayout', 'XMLSystemLayout', 'XMLStaffLayout', 'XMLLeftMargin', 'XMLRightMargin', 'XMLDuration', 'XMLDisplayStep', 'XMLDisplayOctave', 'XMLChord', 'XMLPitch', 'XMLUnpitched', 'XMLRest', 'XMLNote', 'XMLBackup', 'XMLForward', 'XMLDirection', 'XMLAttributes', 'XMLHarmony', 'XMLFiguredBass', 'XMLPrint', 'XMLBarline', 'XMLGrouping', 'XMLPartGroup', 'XMLWork', 'XMLMovementNumber', 'XMLMovementTitle', 'XMLDefaults', 'XMLCredit', 'XMLPartList', 'XMLScorePart']
