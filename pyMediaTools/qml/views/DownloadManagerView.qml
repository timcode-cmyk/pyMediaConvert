import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Item {
    id: root

    property var tasksModel: []

    Connections {
        target: downloadManagerBridge
        function onTasksUpdated(tasksJson) {
            try {
                root.tasksModel = JSON.parse(tasksJson);
            } catch (e) {
                console.error("Error parsing tasks JSON:", e);
                root.tasksModel = [];
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        color: "#1e1e1e"

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 30
            spacing: 20

            // Title
            Text {
                text: "下载管理器 (aria2)"
                color: "white"
                font.pixelSize: 28
                font.bold: true
                font.family: "Segoe UI"
            }

            // Top Settings Panel
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 140
                color: "#252526"
                radius: 8
                border.color: "#3e3e42"
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 15
                    spacing: 12

                    Text {
                        text: "⚙️ 下载设置"
                        color: "#cccccc"
                        font.pixelSize: 14
                        font.bold: true
                    }

                    RowLayout {
                        spacing: 15

                        Text {
                            text: "保存目录:"
                            color: "#bbbbbb"
                        }
                        TextField {
                            id: savePathField
                            Layout.fillWidth: true
                            text: downloadManagerBridge.downloadPath
                            readOnly: true
                            color: "white"
                            background: Rectangle {
                                color: "#3c3c3c"
                                radius: 4
                            }
                        }
                        Button {
                            text: "浏览..."
                            onClicked: folderDialog.open()
                            background: Rectangle {
                                color: parent.hovered ? "#505050" : "#444444"
                                radius: 4
                                implicitHeight: 32
                                implicitWidth: 80
                            }
                            contentItem: Text {
                                text: parent.text
                                color: "white"
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }

                    RowLayout {
                        spacing: 15

                        Text {
                            text: "同时下载数:"
                            color: "#bbbbbb"
                        }
                        SpinBox {
                            id: spinConcurrent
                            from: 1
                            to: 8
                            value: 4
                            onValueChanged: downloadManagerBridge.setConcurrentLimit(value)
                            background: Rectangle {
                                color: "#3c3c3c"
                                radius: 4
                            }
                            contentItem: TextInput {
                                text: spinConcurrent.textFromValue(spinConcurrent.value, spinConcurrent.locale)
                                color: "white"
                                horizontalAlignment: Qt.AlignHCenter
                                verticalAlignment: Qt.AlignVCenter
                            }
                        }

                        CheckBox {
                            id: chkAccel
                            text: "启用分块加速"
                            checked: true
                            contentItem: Text {
                                text: parent.text
                                color: "white"
                                leftPadding: parent.indicator.width + 5
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        Item {
                            Layout.fillWidth: true
                        }
                    }
                }
            }

            // Controls & Overall Progress
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Button {
                    text: "▶️ 全部开始"
                    onClicked: downloadManagerBridge.unpauseAll()
                    background: Rectangle {
                        color: parent.hovered ? "#3d8b40" : "#4caf50"
                        radius: 4
                        implicitHeight: 32
                        implicitWidth: 100
                    }
                    contentItem: Text {
                        text: parent.text
                        color: "white"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                Button {
                    text: "⏸️ 全部暂停"
                    onClicked: downloadManagerBridge.pauseAll()
                    background: Rectangle {
                        color: parent.hovered ? "#d3801a" : "#ff9800"
                        radius: 4
                        implicitHeight: 32
                        implicitWidth: 100
                    }
                    contentItem: Text {
                        text: parent.text
                        color: "white"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                Button {
                    text: "🧹 清空已完成/失败"
                    onClicked: downloadManagerBridge.purgeDownloadResult()
                    background: Rectangle {
                        color: parent.hovered ? "#505050" : "#444444"
                        radius: 4
                        implicitHeight: 32
                        implicitWidth: 140
                    }
                    contentItem: Text {
                        text: parent.text
                        color: "white"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                Item {
                    Layout.fillWidth: true
                }

                ColumnLayout {
                    spacing: 5
                    RowLayout {
                        Text {
                            text: "总进度:"
                            color: "#bbbbbb"
                        }
                        ProgressBar {
                            Layout.preferredWidth: 200
                            value: downloadManagerBridge.totalProgress / 100.0
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
                    Text {
                        text: "总速度: " + downloadManagerBridge.totalSpeed
                        color: "#4caf50"
                        font.pixelSize: 12
                        Layout.alignment: Qt.AlignRight
                    }
                }
            }

            // Add Task Area
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                TextField {
                    id: urlInput
                    Layout.fillWidth: true
                    placeholderText: "在此粘贴 URL 链接..."
                    color: "white"
                    placeholderTextColor: "#777777"
                    background: Rectangle {
                        color: "#3c3c3c"
                        radius: 4
                        implicitHeight: 40
                    }
                    font.pixelSize: 14

                    Keys.onEnterPressed: addTask()
                    Keys.onReturnPressed: addTask()
                }

                Button {
                    text: "➕ 新建下载"
                    onClicked: addTask()
                    background: Rectangle {
                        color: parent.hovered ? "#006bb3" : "#007acc"
                        radius: 4
                        implicitHeight: 40
                        implicitWidth: 120
                    }
                    contentItem: Text {
                        text: parent.text
                        color: "white"
                        font.bold: true
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }

                function addTask() {
                    if (urlInput.text === "")
                        return;
                    var success = downloadManagerBridge.addNewTask(urlInput.text, chkAccel.checked);
                    if (success) {
                        urlInput.text = "";
                    } else {
                        // Error handling could go here
                        console.log("Failed to add task");
                    }
                }
            }

            // Task List
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#252526"
                border.color: "#3e3e42"
                radius: 4

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 0

                    // Header
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 30
                        color: "#333333"
                        radius: 4
                        Rectangle {
                            anchors.bottom: parent.bottom
                            width: parent.width
                            height: 1
                            color: "#3e3e42"
                        } // bottom border separator

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: 10

                            Text {
                                text: "文件名"
                                color: "#cccccc"
                                font.bold: true
                                Layout.fillWidth: true
                                Layout.minimumWidth: 200
                            }
                            Text {
                                text: "进度"
                                color: "#cccccc"
                                font.bold: true
                                Layout.preferredWidth: 120
                            }
                            Text {
                                text: "大小"
                                color: "#cccccc"
                                font.bold: true
                                Layout.preferredWidth: 80
                                horizontalAlignment: Text.AlignRight
                            }
                            Text {
                                text: "速度"
                                color: "#cccccc"
                                font.bold: true
                                Layout.preferredWidth: 80
                                horizontalAlignment: Text.AlignRight
                            }
                            Text {
                                text: "状态"
                                color: "#cccccc"
                                font.bold: true
                                Layout.preferredWidth: 80
                                horizontalAlignment: Text.AlignRight
                            }
                        }
                    }

                    // List
                    ListView {
                        id: taskList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: root.tasksModel

                        delegate: Rectangle {
                            width: taskList.width
                            height: 40
                            color: index % 2 === 0 ? "#252526" : "#2a2a2b"

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                spacing: 10

                                // Name
                                Text {
                                    text: modelData.name
                                    color: "white"
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 200
                                }

                                // Progress
                                ProgressBar {
                                    Layout.preferredWidth: 120
                                    value: modelData.progress / 100.0
                                    background: Rectangle {
                                        implicitHeight: 6
                                        color: "#1e1e1e"
                                        radius: 3
                                    }
                                    contentItem: Item {
                                        Rectangle {
                                            width: parent.parent.visualPosition * parent.width
                                            height: parent.height
                                            radius: 3
                                            color: modelData.status === "error" ? "#e53935" : (modelData.status === "complete" ? "#4caf50" : "#007acc")
                                        }
                                    }
                                }

                                // Size
                                Text {
                                    text: modelData.size
                                    color: "#cccccc"
                                    Layout.preferredWidth: 80
                                    horizontalAlignment: Text.AlignRight
                                }

                                // Speed
                                Text {
                                    text: modelData.status === "active" ? modelData.speed : "-"
                                    color: "#4caf50"
                                    Layout.preferredWidth: 80
                                    horizontalAlignment: Text.AlignRight
                                }

                                // Status
                                Text {
                                    text: modelData.status
                                    color: {
                                        if (modelData.status === "active")
                                            return "#007acc";
                                        if (modelData.status === "complete")
                                            return "#4caf50";
                                        if (modelData.status === "error")
                                            return "#e53935";
                                        if (modelData.status === "paused")
                                            return "#ff9800";
                                        return "#777777";
                                    }
                                    Layout.preferredWidth: 80
                                    horizontalAlignment: Text.AlignRight
                                }
                            }

                            // Context Menu
                            MouseArea {
                                anchors.fill: parent
                                acceptedButtons: Qt.RightButton
                                onClicked: function (mouse) {
                                    if (mouse.button === Qt.RightButton) {
                                        contextMenu.taskGid = modelData.gid;
                                        contextMenu.taskStatus = modelData.status;
                                        contextMenu.popup();
                                    }
                                }
                            }
                        }

                        Text {
                            anchors.centerIn: parent
                            text: "没有下载任务"
                            color: "#777777"
                            font.pixelSize: 16
                            visible: root.tasksModel.length === 0
                        }
                    }
                }
            }
        }
    }

    Menu {
        id: contextMenu
        property string taskGid: ""
        property string taskStatus: ""

        MenuItem {
            text: "暂停任务"
            visible: contextMenu.taskStatus === "active" || contextMenu.taskStatus === "waiting"
            onTriggered: downloadManagerBridge.pauseTask(contextMenu.taskGid)
        }
        MenuItem {
            text: "继续任务"
            visible: contextMenu.taskStatus === "paused"
            onTriggered: downloadManagerBridge.unpauseTask(contextMenu.taskGid)
        }
        MenuSeparator {
            visible: (contextMenu.taskStatus === "active" || contextMenu.taskStatus === "waiting" || contextMenu.taskStatus === "paused")
        }
        MenuItem {
            text: "彻底删除任务"
            onTriggered: downloadManagerBridge.removeTask(contextMenu.taskGid)
        }
    }

    FolderDialog {
        id: folderDialog
        title: "选择下载保存目录"
        onAccepted: {
            downloadManagerBridge.setDownloadPath(selectedFolder.toString().replace("file://", ""));
        }
    }
}
