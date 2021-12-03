from contextlib import redirect_stdout
from pathlib import Path
from unittest import TestCase
import xml.etree.ElementTree as ET

from musicxml.xmlelement import XMLElementTreeElement

xsd_path = Path(__file__).parent.parent / 'musicxml_4_0.xsd'


class TestXMLElementTreeElement(TestCase):
    def setUp(self) -> None:
        with open(xsd_path) as file:
            xmltree = ET.parse(file)
        self.root = xmltree.getroot()
        ns = '{http://www.w3.org/2001/XMLSchema}'
        self.simple_type_element = self.root.find(f"{ns}simpleType[@name='above-below']")
        self.complex_type_element = self.root.find(f"{ns}complexType[@name='fingering']")

    def test_write_all_tags(self):
        with open(Path(__file__).parent / 'musicxml_4_0_summary.txt', 'w+') as f:
            tree = XMLElementTreeElement(self.root)
            with redirect_stdout(f):
                print('All tags: ' + str({node.tag for node in tree.traverse()}))
                for child in tree.get_children():
                    print('============')
                    print([node.compact_repr for node in child.traverse()])

    def test_self_simple_type_element(self):
        assert self.simple_type_element.tag == '{http://www.w3.org/2001/XMLSchema}simpleType'
        assert self.simple_type_element.attrib['name'] == 'above-below'

    def test_xml_property(self):
        """
        Test that a XMLElementGenerator must get an xml element
        :return: 
        """""
        with self.assertRaises(TypeError):
            XMLElementTreeElement()
        with self.assertRaises(TypeError):
            XMLElementTreeElement('Naja')

        xml_element = XMLElementTreeElement(self.simple_type_element)
        assert isinstance(xml_element.xml_element_tree_element, ET.Element)

    def test_xml_element_tag(self):
        xml_element = XMLElementTreeElement(self.simple_type_element)
        assert xml_element.tag == 'simpleType'

    def test_xml_element_class_name(self):
        xml_element = XMLElementTreeElement(self.simple_type_element)
        assert xml_element.class_name == 'XMLSimpleTypeAboveBelow'

    def test_xml_element_class(self):
        from musicxml.xmlelement import XMLSimpleTypeAboveBelow

    def test_get_doc(self):
        xml_element = XMLElementTreeElement(self.simple_type_element)
        assert xml_element.get_doc() == 'The above-below type is used to indicate whether one element appears above or below another element.'

    def test_name(self):
        xml_element = XMLElementTreeElement(self.simple_type_element)
        assert xml_element.name == 'above-below'

    def test_traverse(self):
        expected = ['complexType', 'annotation', 'documentation', 'simpleContent', 'extension', 'attribute',
                    'attribute', 'attributeGroup', 'attributeGroup']
        assert [node.tag for node in XMLElementTreeElement(self.complex_type_element).traverse()] == expected

    def test_get_children(self):
        xml = """<xs:extension xmlns:xs="http://www.w3.org/2001/XMLSchema" 
                    base="xs:string">
        				<xs:attribute name="substitution" type="yes-no"/>
        				<xs:attribute name="alternate" type="yes-no"/>
        				<xs:attributeGroup ref="print-style"/>
        				<xs:attributeGroup ref="placement"/>
        		</xs:extension>"""
        el = XMLElementTreeElement(ET.fromstring(xml))
        assert [child.tag for child in el.get_children()] == ['attribute', 'attribute', 'attributeGroup',
                                                              'attributeGroup']

    def test_iterate_leaves(self):
        el = XMLElementTreeElement(self.complex_type_element)
        assert [child.tag for child in el.iterate_leaves()] == ['documentation', 'attribute', 'attribute',
                                                                'attributeGroup',
                                                                'attributeGroup']

    def test_compact_repr(self):
        el = XMLElementTreeElement(self.complex_type_element)

        assert [node.compact_repr for node in el.traverse()] == ['complexType@name=fingering', 'annotation',
                                                                 'documentation', 'simpleContent',
                                                                 'extension@base=xs:string',
                                                                 'attribute@name=substitution@type=yes-no',
                                                                 'attribute@name=alternate@type=yes-no',
                                                                 'attributeGroup@ref=print-style',
                                                                 'attributeGroup@ref=placement']

    def test_str(self):
        el = XMLElementTreeElement(self.complex_type_element)
        assert str(el) == "XMLElementTreeElement complexType@name=fingering"

    def test_repr(self):
        el = XMLElementTreeElement(self.complex_type_element)
        assert [repr(node) for node in el.traverse()] == ['XMLElementTreeElement(tag=complexType, name=fingering)',
                                                          'XMLElementTreeElement(tag=annotation)',
                                                          'XMLElementTreeElement(tag=documentation)',
                                                          'XMLElementTreeElement(tag=simpleContent)',
                                                          'XMLElementTreeElement(tag=extension, base=xs:string)',
                                                          'XMLElementTreeElement(tag=attribute, name=substitution type=yes-no)',
                                                          'XMLElementTreeElement(tag=attribute, name=alternate type=yes-no)',
                                                          'XMLElementTreeElement(tag=attributeGroup, ref=print-style)',
                                                          'XMLElementTreeElement(tag=attributeGroup, ref=placement)']

    def test_get_attributes(self):
        el = XMLElementTreeElement(self.complex_type_element)
        assert [{}, {'name': 'substitution', 'type': 'yes-no'}, {'name': 'alternate', 'type': 'yes-no'},
                {'ref': 'print-style'}, {'ref': 'placement'}] == [leaf.get_attributes() for leaf in el.iterate_leaves()]

    def test_get_parent(self):
        grandparent = XMLElementTreeElement(self.complex_type_element)
        parent = grandparent.get_children()[1]
        child = parent.get_children()[0]
        grandchild = child.get_children()[0]

        assert grandchild.get_parent() == child
        assert child.get_parent() == parent
        assert parent.get_parent() == grandparent
        assert grandparent.get_parent() is None

    def test_get_xsd(self):
        expected_1 = """<xs:simpleType xmlns:xs="http://www.w3.org/2001/XMLSchema" name="above-below">
		<xs:annotation>
			<xs:documentation>The above-below type is used to indicate whether one element appears above or below another element.</xs:documentation>
		</xs:annotation>
		<xs:restriction base="xs:token">
			<xs:enumeration value="above" />
			<xs:enumeration value="below" />
		</xs:restriction>
	</xs:simpleType>
"""
        expected_2 = """<xs:complexType xmlns:xs="http://www.w3.org/2001/XMLSchema" name="fingering">
		<xs:annotation>
			<xs:documentation>Fingering is typically indicated 1,2,3,4,5. Multiple fingerings may be given, typically to substitute fingerings in the middle of a note. The substitution and alternate values are "no" if the attribute is not present. For guitar and other fretted instruments, the fingering element represents the fretting finger; the pluck element represents the plucking finger.</xs:documentation>
		</xs:annotation>
		<xs:simpleContent>
			<xs:extension base="xs:string">
				<xs:attribute name="substitution" type="yes-no" />
				<xs:attribute name="alternate" type="yes-no" />
				<xs:attributeGroup ref="print-style" />
				<xs:attributeGroup ref="placement" />
			</xs:extension>
		</xs:simpleContent>
	</xs:complexType>
"""
        assert XMLElementTreeElement(self.simple_type_element).get_xsd() == expected_1
        assert XMLElementTreeElement(self.complex_type_element).get_xsd() == expected_2

    def test_restriction(self):
        pass
