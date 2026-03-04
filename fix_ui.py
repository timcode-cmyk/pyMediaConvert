import re
import glob
import os

files = glob.glob('pyMediaTools/qml/views/*.qml') + ['pyMediaTools/qml/main.qml']

for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Remove Segoe UI causing text clipping on mac
    content = re.sub(r'\s*font\.family:\s*"Segoe UI"\n', '\n', content)
    
    # Button radius standard: 6 instead of 4
    content = re.sub(r'radius:\s*4\b', 'radius: 6', content)

    # Convert anchors.fill: parent inside ScrollView to just Layout.fillWidth and layout margins
    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)

print("done")
