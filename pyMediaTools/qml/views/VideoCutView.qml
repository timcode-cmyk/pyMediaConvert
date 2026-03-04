import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Item {
    id: root

    // Bridge connection
    Connections {
        target: videoCutBridge
        function onProcessingFinished(success, msg) {
            if (success) {
                // Show success
            } else {
                if (msg !== "") {
                    mainStatusLabel.text = msg;
                    mainStatusLabel.color = "#e53935";
                    statusResetTimer.start();
                }
            }
        }
    }

    Timer {
        id: statusResetTimer
        interval: 5000
        onTriggered: {
            mainStatusLabel.text = videoCutBridge.statusText;
            mainStatusLabel.color = "#007acc";
        }
    }

    // Default settings
    property var watermarkSettings: {
        "font_name": "",
        "font_size": "24",
        "font_color": "white",
        "x": "W-tw-10",
        "y": "40",
        "text": "AI Created"
    }

    property var availableFonts: []

    Component.onCompleted: {
        var settings = videoCutBridge.getInitialSettings();
        availableFonts = settings.availableFonts;
        watermarkSettings.font_name = settings.defaultFont;
    }

    Rectangle {
        anchors.fill: parent
        color: "#1e1e1e"

        ScrollView {
            anchors.fill: parent
            anchors.margins: 30
            contentWidth: -1

            ColumnLayout {
                width: parent.width
                spacing: 25

                // Title
                Text {
                    text: "视频智能切分"
                    color: "white"
                    font.pixelSize: 28
                    font.bold: true
                    font.family: "Segoe UI"
                }

                // STEP 1: Paths
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
                            text: "STEP 1: 文件路径"
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

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 40
                                color: "#3c3c3c"
                                radius: 4

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
                                            outputField.text = videoCutBridge.generateOutputPath(text);
                                        }
                                    }
                                }

                                Text {
                                    anchors.centerIn: parent
                                    text: "📂 拖放文件夹/文件"
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
                                onClicked: inputDialog.open()
                                background: Rectangle {
                                    color: parent.hovered ? "#505050" : "#444444"
                                    radius: 4
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: "white"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
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
                                radius: 4

                                TextInput {
                                    id: outputField
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 10
                                    verticalAlignment: Text.AlignVCenter
                                    color: "white"
                                    font.pixelSize: 14
                                    clip: true
                                    readOnly: true
                                }
                            }
                        }
                    }
                }

                // STEP 2: Parameters
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 120
                    color: "#252526"
                    radius: 8
                    border.color: "#3e3e42"
                    border.width: 1

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 15
                        spacing: 15

                        Text {
                            text: "STEP 2: 参数设置"
                            color: "#cccccc"
                            font.pixelSize: 14
                            font.bold: true
                        }

                        RowLayout {
                            spacing: 15

                            // Threshold
                            Text {
                                text: "场景检测阈值:"
                                color: "white"
                            }
                            Slider {
                                id: thresholdSlider
                                from: 0
                                to: 100
                                value: 20
                                Layout.preferredWidth: 150
                            }
                            Text {
                                text: Math.round(thresholdSlider.value) + "%"
                                color: "white"
                                Layout.preferredWidth: 30
                            }

                            // Frame Export
                            CheckBox {
                                id: chkExportFrame
                                text: "导出静帧"
                                checked: true
                                contentItem: Text {
                                    text: parent.text
                                    color: "white"
                                    leftPadding: parent.indicator.width + 5
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                            Text {
                                text: "偏移量:"
                                color: "white"
                                opacity: chkExportFrame.checked ? 1.0 : 0.5
                            }
                            SpinBox {
                                id: spinFrameOffset
                                from: 0
                                to: 1000
                                value: 10
                                enabled: chkExportFrame.checked
                                background: Rectangle {
                                    color: "#3c3c3c"
                                    radius: 4
                                }
                                contentItem: TextInput {
                                    text: spinFrameOffset.textFromValue(spinFrameOffset.value, spinFrameOffset.locale)
                                    color: "white"
                                    horizontalAlignment: Qt.AlignHCenter
                                    verticalAlignment: Qt.AlignVCenter
                                }
                            }

                            Item {
                                Layout.fillWidth: true
                            }
                        }

                        RowLayout {
                            spacing: 15
                            CheckBox {
                                id: chkAddWatermark
                                text: "添加水印"
                                checked: false
                                contentItem: Text {
                                    text: parent.text
                                    color: "white"
                                    leftPadding: parent.indicator.width + 5
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                            TextField {
                                id: txtWatermarkText
                                text: "AI Created"
                                enabled: chkAddWatermark.checked
                                color: "white"
                                background: Rectangle {
                                    color: "#3c3c3c"
                                    radius: 4
                                    implicitHeight: 32
                                }
                                Layout.fillWidth: true
                            }
                            Button {
                                text: "⚙️ 水印设置"
                                enabled: chkAddWatermark.checked
                                onClicked: watermarkDialog.open()
                                background: Rectangle {
                                    color: parent.enabled ? (parent.hovered ? "#505050" : "#444444") : "#333"
                                    radius: 4
                                    implicitHeight: 32
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: parent.enabled ? "white" : "#777"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }
                    }
                }

                // STEP 3: Naming
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 170
                    color: "#252526"
                    radius: 8
                    border.color: "#3e3e42"
                    border.width: 1

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 15
                        spacing: 10

                        Text {
                            text: "STEP 3: 片段重命名 (可选)"
                            color: "#cccccc"
                            font.pixelSize: 14
                            font.bold: true
                        }

                        RowLayout {
                            spacing: 10
                            Text {
                                text: "人员ID:"
                                color: "white"
                            }
                            TextField {
                                id: txtPersonId
                                placeholderText: "例如: Tim"
                                color: "white"
                                background: Rectangle {
                                    color: "#3c3c3c"
                                    radius: 4
                                }
                                Layout.fillWidth: true
                            }
                        }

                        Text {
                            text: "自定义片段名称 (每行对应一个片段):"
                            color: "white"
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            color: "#1e1e1e"
                            border.color: "#3e3e42"

                            ScrollView {
                                anchors.fill: parent
                                TextArea {
                                    id: txtRenameLines
                                    placeholderText: "第一段视频的名称\n第二段视频的名称\n..."
                                    color: "white"
                                    background: null
                                }
                            }
                        }
                        Text {
                            text: "命名规则: 日期_人员ID_自定义名称_序号.mp4"
                            color: "#777"
                            font.pixelSize: 12
                        }
                    }
                }

                // STEP 4: Status & Progress
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
                            text: "STEP 4: 状态与控制"
                            color: "#cccccc"
                            font.pixelSize: 14
                            font.bold: true
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            Text {
                                text: "总进度:"
                                color: "#bbbbbb"
                                Layout.preferredWidth: 80
                            }
                            ProgressBar {
                                id: overallPB
                                Layout.fillWidth: true
                                value: videoCutBridge.overallProgress / 100.0
                                background: Rectangle {
                                    implicitHeight: 8
                                    color: "#3c3c3c"
                                    radius: 4
                                }
                                contentItem: Item {
                                    Rectangle {
                                        width: parent.parent.visualPosition * parent.width
                                        height: parent.height
                                        radius: 4
                                        color: "#007acc"
                                    }
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            Text {
                                text: "当前进度:"
                                color: "#bbbbbb"
                                Layout.preferredWidth: 80
                            }
                            ProgressBar {
                                id: filePB
                                Layout.fillWidth: true
                                value: videoCutBridge.fileProgress / 100.0
                                background: Rectangle {
                                    implicitHeight: 8
                                    color: "#3c3c3c"
                                    radius: 4
                                }
                                contentItem: Item {
                                    Rectangle {
                                        width: parent.parent.visualPosition * parent.width
                                        height: parent.height
                                        radius: 4
                                        color: "#4caf50"
                                    }
                                }
                            }
                        }

                        Text {
                            id: mainStatusLabel
                            Layout.fillWidth: true
                            text: videoCutBridge.statusText
                            color: "#007acc"
                            font.pixelSize: 13
                            elide: Text.ElideRight
                        }
                    }
                }

                // Action
                Button {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 50
                    text: videoCutBridge.isProcessing ? "🛑 停止处理" : "🚀 开始处理"
                    background: Rectangle {
                        color: videoCutBridge.isProcessing ? (parent.hovered ? "#c13b3b" : "#e53935") : (parent.hovered ? "#006bb3" : "#007acc")
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
                        if (videoCutBridge.isProcessing) {
                            videoCutBridge.stopProcessing();
                        } else {
                            if (inputField.text === "")
                                return;
                            videoCutBridge.startProcessing({
                                "input_path": inputField.text,
                                "output_path": outputField.text,
                                "threshold": thresholdSlider.value,
                                "export_frame": chkExportFrame.checked,
                                "frame_offset": spinFrameOffset.value,
                                "add_watermark": chkAddWatermark.checked,
                                "watermark_text": txtWatermarkText.text,
                                "watermark_params": root.watermarkSettings,
                                "person_id": txtPersonId.text,
                                "rename_lines": txtRenameLines.text.split("\n")
                            });
                        }
                    }
                }

                Item {
                    Layout.fillHeight: true
                }
            }
        }
    }

    // Dialogs
    FileDialog {
        id: inputDialog
        title: "选择输入视频"
        onAccepted: {
            inputField.text = selectedFile.toString().replace("file://", "");
        }
    }

    Dialog {
        id: watermarkDialog
        title: "水印详细设置"
        modal: true
        width: 400
        height: 300
        anchors.centerIn: parent

        background: Rectangle {
            color: "#252526"
            border.color: "#3e3e42"
            border.width: 1
            radius: 8
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 15
            spacing: 15

            RowLayout {
                Text {
                    text: "字体文件:"
                    color: "white"
                    Layout.preferredWidth: 80
                }
                ComboBox {
                    id: fontCombo
                    Layout.fillWidth: true
                    model: root.availableFonts
                    currentIndex: root.availableFonts.indexOf(root.watermarkSettings.font_name)
                    background: Rectangle {
                        color: "#3c3c3c"
                        radius: 4
                    }
                    contentItem: Text {
                        text: fontCombo.currentText
                        color: "white"
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: 10
                    }
                }
            }

            RowLayout {
                Text {
                    text: "字体大小:"
                    color: "white"
                    Layout.preferredWidth: 80
                }
                SpinBox {
                    id: spinFontSize
                    from: 8
                    to: 200
                    value: parseInt(root.watermarkSettings.font_size)
                    Layout.fillWidth: true
                    background: Rectangle {
                        color: "#3c3c3c"
                        radius: 4
                    }
                    contentItem: TextInput {
                        text: spinFontSize.textFromValue(spinFontSize.value, spinFontSize.locale)
                        color: "white"
                        horizontalAlignment: Qt.AlignHCenter
                        verticalAlignment: Qt.AlignVCenter
                    }
                }
            }

            RowLayout {
                Text {
                    text: "字体颜色:"
                    color: "white"
                    Layout.preferredWidth: 80
                }
                TextField {
                    id: txtFontColor
                    text: root.watermarkSettings.font_color
                    color: "white"
                    background: Rectangle {
                        color: "#3c3c3c"
                        radius: 4
                    }
                    Layout.fillWidth: true
                }
            }

            RowLayout {
                Text {
                    text: "X 坐标:"
                    color: "white"
                    Layout.preferredWidth: 80
                }
                TextField {
                    id: txtX
                    text: root.watermarkSettings.x
                    color: "white"
                    background: Rectangle {
                        color: "#3c3c3c"
                        radius: 4
                    }
                    Layout.fillWidth: true
                }
            }

            RowLayout {
                Text {
                    text: "Y 坐标:"
                    color: "white"
                    Layout.preferredWidth: 80
                }
                TextField {
                    id: txtY
                    text: root.watermarkSettings.y
                    color: "white"
                    background: Rectangle {
                        color: "#3c3c3c"
                        radius: 4
                    }
                    Layout.fillWidth: true
                }
            }

            Item {
                Layout.fillHeight: true
            }
        }

        standardButtons: Dialog.Ok | Dialog.Cancel
        onAccepted: {
            root.watermarkSettings.font_name = fontCombo.currentText;
            root.watermarkSettings.font_size = spinFontSize.value.toString();
            root.watermarkSettings.font_color = txtFontColor.text;
            root.watermarkSettings.x = txtX.text;
            root.watermarkSettings.y = txtY.text;
        }
    }
}
