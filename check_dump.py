import xml.etree.ElementTree as ET
try:
    tree = ET.parse('ui_dump.xml')
    root = tree.getroot()
    for elem in root.iter():
        text = elem.attrib.get('text', '')
        desc = elem.attrib.get('content-desc', '')
        if text or desc:
            print(text[:30] + ' | ' + desc[:30])
except Exception as e:
    print(e)
