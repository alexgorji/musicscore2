from musicxml.util.core import convert_to_xml_class_name
import xml.etree.ElementTree as ET
from musicxml.xmlelement.xmlelement import *


def _et_xml_to_music_xml(node):
    output = eval(convert_to_xml_class_name(node.tag))()
    for k, v in node.attrib.items():
        setattr(output, k, v)
    if node.text:
        text = node.text.strip()
        if text:
            try:
                output.value = text
            except TypeError:
                try:
                    output.value = int(text)
                except ValueError:
                    output.value = float(text)
    return output


def _parse_node(xml_node):
    print('parsing node:', xml_node)
    print(type(xml_node))
    output = _et_xml_to_music_xml(xml_node)
    print('output', output)
    for child in xml_node:
        output.add_child(_parse_node(child))
    return output


def parse_musicxml(file_path):
    with open(file_path) as file:
        xml = ET.parse(file)

    return _parse_node(xml.getroot())