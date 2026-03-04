import re

def process_file(file_path, replacements):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    for (old, new) in replacements:
        content = content.replace(old, new)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

process_file('pyMediaTools/qml/views/DownloadManagerView.qml', [
    ('implicitHeight: 32', 'implicitHeight: 36'),
    ('implicitHeight: 40\n                        implicitWidth: 120', 'implicitHeight: 46\n                        implicitWidth: 140')
])

process_file('pyMediaTools/qml/views/ElevenLabsView.qml', [
    ('implicitHeight: 40\n                                        implicitWidth: 120', 'implicitHeight: 46\n                                        implicitWidth: 140')
])

process_file('pyMediaTools/qml/views/VideoDownloaderView.qml', [
    ('implicitHeight: 32', 'implicitHeight: 36'),
    ('implicitHeight: 45\n                                implicitWidth: 140', 'implicitHeight: 46\n                                implicitWidth: 160')
])

print("Heights adjusted")
