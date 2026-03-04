import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs

Item {
    id: root

    property var modes: []
    property int selectedModeIndex: 0
    property string currentModeKey: ""

    Component.onCompleted: {
        modes = mediaConverterBridge.getModes();
        if (modes.length > 0) {
            currentModeKey = modes[0].key;
            descLabel.text = "说明: " + modes[0].desc + "\n支持格式: " + modes[0].exts;
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "#1e1e1e"

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 30
            spacing: 20

            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: -1 // Disable horizontal scrolling
                clip: true

                ColumnLayout {
                    width: parent.width
                    spacing: 25

                    // Title
                    Text {
                        text: "媒体转换工具"
                        color: "white"
                        font.pixelSize: 28
                        font.bold: true
                    }

                    // STEP 1: Mode Selection
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 110
                        color: "#252526"
                        radius: 8
                        border.color: "#3e3e42"
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 15
                            spacing: 10

                            Text {
                                text: "STEP 1: 选择转换模式"
                                color: "#cccccc"
                                font.pixelSize: 14
                                font.bold: true
                            }

                            ComboBox {
                                id: modeCombo
                                Layout.fillWidth: true
                                model: root.modes
                                textRole: "label"

                                contentItem: Text {
                                    text: modeCombo.displayText
                                    color: "white"
                                    font.pixelSize: 14
                                    verticalAlignment: Text.AlignVCenter
                                    leftPadding: 10
                                }
                                background: Rectangle {
                                    implicitHeight: 40
                                    color: "#3c3c3c"
                                    radius: 6
                                }

                                onCurrentIndexChanged: {
                                    if (currentIndex >= 0 && root.modes.length > 0) {
                                        root.currentModeKey = root.modes[currentIndex].key;
                                        descLabel.text = "说明: " + root.modes[currentIndex].desc + "\n支持格式: " + root.modes[currentIndex].exts;
                                    }
                                }
                            }

                            Text {
                                id: descLabel
                                Layout.fillWidth: true
                                color: "#a0a0a0"
                                font.pixelSize: 13
                                wrapMode: Text.WordWrap
                            }
                        }
                    }

                    // STEP 2: File Paths
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 180
                        color: "#252526"
                        radius: 8
                        border.color: "#3e3e42"
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 15
                            spacing: 12

                            Text {
                                text: "STEP 2: 文件路径"
                                color: "#cccccc"
                                font.pixelSize: 14
                                font.bold: true
                            }

                            // Input Layout
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 10

                                Text {
                                    text: "输入源:"
                                    color: "#bbbbbb"
                                    font.pixelSize: 14
                                    Layout.preferredWidth: 60
                                }

                                // Input Field & Drop Area
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 40
                                    color: "#3c3c3c"
                                    radius: 6

                                    TextInput {
                                        id: inputField
                                        anchors.fill: parent
                                        anchors.leftMargin: 10
                                        anchors.rightMargin: 10
                                        verticalAlignment: Text.AlignVCenter
                                        color: "white"
                                        font.pixelSize: 14
                                        clip: true

                                        onTextChanged: {
                                            if (text !== "") {
                                                outputField.text = mediaConverterBridge.getDefaultOutput(text);
                                            }
                                        }
                                    }

                                    Text {
                                        anchors.centerIn: parent
                                        text: "📂 拖放文件夹/文件到此处，或点击右侧按钮"
                                        color: "#777777"
                                        font.pixelSize: 13
                                        visible: inputField.text === ""
                                    }

                                    DropArea {
                                        anchors.fill: parent
                                        onDropped: function (drop) {
                                            if (drop.hasUrls) {
                                                inputField.text = drop.urls[0].toString().replace("file://", "");
                                            }
                                        }
                                    }
                                }

                                Button {
                                    text: "浏览..."
                                    Layout.preferredWidth: 80
                                    Layout.preferredHeight: 40
                                    background: Rectangle {
                                        color: parent.hovered ? "#505050" : "#444444"
                                        radius: 6
                                    }
                                    contentItem: Text {
                                        text: parent.text
                                        color: "white"
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                        font.pixelSize: 14
                                    }
                                    onClicked: inputDialog.open()
                                }
                            }

                            // Output Layout
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 10

                                Text {
                                    text: "输出目录:"
                                    color: "#bbbbbb"
                                    font.pixelSize: 14
                                    Layout.preferredWidth: 60
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 40
                                    color: "#3c3c3c"
                                    radius: 6

                                    TextInput {
                                        id: outputField
                                        anchors.fill: parent
                                        anchors.leftMargin: 10
                                        anchors.rightMargin: 10
                                        verticalAlignment: Text.AlignVCenter
                                        color: "white"
                                        font.pixelSize: 14
                                        clip: true
                                    }
                                }

                                Button {
                                    text: "浏览..."
                                    Layout.preferredWidth: 80
                                    Layout.preferredHeight: 40
                                    background: Rectangle {
                                        color: parent.hovered ? "#505050" : "#444444"
                                        radius: 6
                                    }
                                    contentItem: Text {
                                        text: parent.text
                                        color: "white"
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                        font.pixelSize: 14
                                    }
                                    onClicked: outputDialog.open()
                                }
                            }
                        }
                    }

                    // STEP 3: Status & Controls
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 150
                        color: "#252526"
                        radius: 8
                        border.color: "#3e3e42"
                        border.width: 1

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 15
                            spacing: 12

                            Text {
                                text: "STEP 3: 状态与控制"
                                color: "#cccccc"
                                font.pixelSize: 14
                                font.bold: true
                            }

                            // Overall Progress
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 10

                                Text {
                                    text: "总进度:"
                                    color: "#bbbbbb"
                                    Layout.preferredWidth: 60
                                }

                                ProgressBar {
                                    id: overallPB
                                    Layout.fillWidth: true
                                    value: mediaConverterBridge.overallProgress / 100.0
                                    background: Rectangle {
                                        implicitHeight: 8
                                        color: "#3c3c3c"
                                        radius: 6
                                    }
                                    contentItem: Item {
                                        Rectangle {
                                            width: overallPB.visualPosition * parent.width
                                            height: parent.height
                                            radius: 6
                                            color: "#007acc"
                                        }
                                    }
                                }

                                Text {
                                    text: mediaConverterBridge.overallProgressText
                                    color: "white"
                                    Layout.preferredWidth: 80
                                    horizontalAlignment: Text.AlignRight
                                }
                            }

                            // File Progress
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 10

                                Text {
                                    text: "当前文件:"
                                    color: "#bbbbbb"
                                    Layout.preferredWidth: 60
                                }

                                ProgressBar {
                                    id: filePB
                                    Layout.fillWidth: true
                                    value: mediaConverterBridge.fileProgress / 100.0
                                    background: Rectangle {
                                        implicitHeight: 8
                                        color: "#3c3c3c"
                                        radius: 6
                                    }
                                    contentItem: Item {
                                        Rectangle {
                                            width: filePB.visualPosition * parent.width
                                            height: parent.height
                                            radius: 6
                                            color: "#4caf50" // Green for individual files
                                        }
                                    }
                                }

                                Text {
                                    text: mediaConverterBridge.fileProgressText
                                    color: "white"
                                    Layout.preferredWidth: 80
                                    horizontalAlignment: Text.AlignRight
                                }
                            }

                            // Status Label
                            Text {
                                id: mainStatusLabel
                                Layout.fillWidth: true
                                text: mediaConverterBridge.statusText
                                color: "#007acc"
                                font.pixelSize: 13
                                elide: Text.ElideRight
                            }
                        }
                    } // end STEP 4

                    // Padding at bottom
                    Item {
                        Layout.fillHeight: true
                    }
                } // end inner ColumnLayout
            } // end ScrollView

            // Action Button
            Button {
                id: actionButton
                Layout.fillWidth: true
                Layout.preferredHeight: 50
                text: mediaConverterBridge.isConverting ? "🛑 停止转换" : "🚀 开始转换"

                background: Rectangle {
                    color: mediaConverterBridge.isConverting ? (parent.hovered ? "#c13b3b" : "#e53935") : (parent.hovered ? "#006bb3" : "#007acc")
                    radius: 8
                }
                contentItem: Text {
                    text: parent.text
                    color: "white"
                    font.pixelSize: 18
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }

                onClicked: {
                    if (mediaConverterBridge.isConverting) {
                        mediaConverterBridge.stopConversion();
                    } else {
                        if (inputField.text === "" || outputField.text === "") {
                            // show error
                            mainStatusLabel.text = "错误: 请选择输入和输出路径";
                            mainStatusLabel.color = "#e53935";
                            return;
                        }
                        mainStatusLabel.color = "#007acc";
                        mediaConverterBridge.startConversion(inputField.text, outputField.text, root.currentModeKey);
                    }
                }
            }
        } // end ColumnLayout
    } // end Rectangle

    // Dialogs
    FileDialog {
        id: inputDialog
        title: "选择输入文件/文件夹"
        onAccepted: {
            inputField.text = selectedFile.toString().replace("file://", "");
        }
    }

    FolderDialog {
        id: outputDialog
        title: "选择输出目录"
        onAccepted: {
            outputField.text = selectedFolder.toString().replace("file://", "");
        }
    }
}
