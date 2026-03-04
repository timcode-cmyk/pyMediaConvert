import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

Item {
    id: root

    property var videoListModel: []
    property bool isDownloading: false
    property bool isUpdating: false

    Connections {
        target: videoDownloaderBridge

        function onAnalyzeFinished(jsonStr) {
            btnAnalyze.enabled = true;
            statusLabel.text = "解析完成";
            try {
                var items = JSON.parse(jsonStr);
                var newModel = [];
                for (var i = 0; i < items.length; i++) {
                    var item = items[i];
                    // Keep track of check state in the model manually
                    item.checked = true;
                    item.status = "待下载";
                    item.ui_index = i;

                    if (item.duration) {
                        var m = Math.floor(item.duration / 60);
                        var s = Math.floor(item.duration % 60);
                        item.durationStr = m + ":" + (s < 10 ? "0" + s : s);
                    } else {
                        item.durationStr = "--:--";
                    }
                    newModel.push(item);
                }
                root.videoListModel = newModel;
                taskList.model = root.videoListModel;
                chkSelectAll.checked = true;
            } catch (e) {
                console.error("解析视频列表失败", e);
            }
        }

        function onAnalyzeError(err) {
            btnAnalyze.enabled = true;
            statusLabel.text = "解析失败: " + err;
            statusLabel.color = "#e53935";
            statusResetTimer.start();
        }

        function onDownloadProgress(jsonStr) {
            try {
                var data = JSON.parse(jsonStr);
                overallPB.value = (data.overall_percent || 0) / 100.0;

                var rawName = data.status || "";
                var displayName = rawName.length > 50 ? rawName.substring(0, 49) + "…" : rawName;
                var speed = data.speed || "-";
                statusLabel.text = "正在下载: " + displayName + " [速度: " + speed + "]";

                var idx = data.ui_index;
                if (idx !== undefined && idx >= 0 && idx < root.videoListModel.length) {
                    var item = root.videoListModel[idx];
                    if (data.file_complete) {
                        item.status = "完成";
                    } else {
                        item.status = (data.current_percent || 0).toFixed(1) + "%";
                    }
                    // Force replace to update view bindings
                    root.videoListModel[idx] = item;
                    // Tricky in QML without ListModel, we might need a signal to re-evaluate or use a trick.
                    // Instead of full replace, we re-assign to trigger binding if it was a property.
                    // For pure JS array model, replacing the whole array works, but can be heavy. Let's just reassign.
                    var temp = root.videoListModel;
                    root.videoListModel = temp;
                    taskList.model = root.videoListModel;
                }
            } catch (e) {}
        }

        function onDownloadFinished() {
            root.isDownloading = false;
            statusLabel.text = "所有任务完成";
            statusLabel.color = "#4caf50";
            overallPB.value = 1.0;
            statusResetTimer.start();
        }

        function onDownloadError(err) {
            root.isDownloading = false;
            statusLabel.text = "下载错误: " + err;
            statusLabel.color = "#e53935";
            statusResetTimer.start();
        }

        function onVersionChecked(local, remote, hasUpdate) {
            updateDialog.localVer = local || "未知";
            updateDialog.remoteVer = remote || "检查失败";
            updateDialog.hasUpdate = hasUpdate;

            if (hasUpdate && remote && local) {
                updateDialog.addLog("发现新版本: " + remote);
            }
        }

        function onCheckUpdateError(err) {
            updateDialog.remoteVer = "检查失败: " + err;
            updateDialog.hasUpdate = false;
        }

        function onUpdateProgress(msg) {
            updateDialog.addLog(msg);
        }

        function onUpdateFinished(success, msg, newVer) {
            root.isUpdating = false;
            btnAnalyze.enabled = true;
            updateDialog.btnUpdateEnabled = false;

            if (success) {
                updateDialog.localVer = newVer;
                updateDialog.addLog("✅ " + msg);
                updateDialog.addLog("更新成功！");
            } else {
                updateDialog.addLog("❌ " + msg);
                updateDialog.addLog("更新失败，已回滚。");
            }
        }

        function onUpdateError(err) {
            root.isUpdating = false;
            btnAnalyze.enabled = true;
            updateDialog.addLog("❌ 错误: " + err);
        }
    }

    Timer {
        id: statusResetTimer
        interval: 5000
        onTriggered: {
            if (!root.isDownloading) {
                statusLabel.text = "等待开始...";
                statusLabel.color = "#007acc";
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
                text: "网络视频下载 (yt-dlp)"
                color: "white"
                font.pixelSize: 28
                font.bold: true
                font.family: "Segoe UI"
            }

            // Task List Area
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#252526"
                radius: 8
                border.color: "#3e3e42"
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 15
                    spacing: 12

                    // URL Input Row
                    RowLayout {
                        spacing: 10
                        TextField {
                            id: urlInput
                            Layout.fillWidth: true
                            placeholderText: "粘贴 YouTube/Bilibili 等视频或播放列表链接..."
                            color: "white"
                            background: Rectangle {
                                color: "#3c3c3c"
                                radius: 4
                                implicitHeight: 40
                            }
                            font.pixelSize: 14
                            Keys.onReturnPressed: root.analyzeUrl()
                            Keys.onEnterPressed: root.analyzeUrl()
                        }
                        Button {
                            id: btnAnalyze
                            text: "🔍 解析链接"
                            onClicked: root.analyzeUrl()
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
                    }

                    // Table Tools
                    RowLayout {
                        CheckBox {
                            id: chkSelectAll
                            text: "全选/取消全选"
                            checked: true
                            onCheckedChanged: {
                                var temp = root.videoListModel;
                                for (var i = 0; i < temp.length; i++) {
                                    temp[i].checked = checked;
                                }
                                root.videoListModel = temp;
                                taskList.model = root.videoListModel;
                            }
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

                    // Table Header
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
                        }

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            spacing: 10

                            Text {
                                text: ""
                                Layout.preferredWidth: 30
                            } // Checkbox col
                            Text {
                                text: "标题"
                                color: "#cccccc"
                                font.bold: true
                                Layout.fillWidth: true
                                Layout.minimumWidth: 200
                            }
                            Text {
                                text: "时长"
                                color: "#cccccc"
                                font.bold: true
                                Layout.preferredWidth: 80
                                horizontalAlignment: Text.AlignRight
                            }
                            Text {
                                text: "状态/进度"
                                color: "#cccccc"
                                font.bold: true
                                Layout.preferredWidth: 100
                                horizontalAlignment: Text.AlignRight
                            }
                        }
                    }

                    // Task List
                    ListView {
                        id: taskList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: root.videoListModel

                        delegate: Rectangle {
                            width: taskList.width
                            height: 40
                            color: index % 2 === 0 ? "#252526" : "#2a2a2b"

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                spacing: 10

                                CheckBox {
                                    checked: modelData.checked
                                    onCheckedChanged: {
                                        var temp = root.videoListModel;
                                        temp[index].checked = checked;
                                        root.videoListModel = temp;
                                    }
                                    Layout.preferredWidth: 30
                                }

                                Text {
                                    text: modelData.title
                                    color: "white"
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 200
                                }

                                Text {
                                    text: modelData.durationStr
                                    color: "#cccccc"
                                    Layout.preferredWidth: 80
                                    horizontalAlignment: Text.AlignRight
                                }

                                Text {
                                    text: modelData.status
                                    color: modelData.status === "待下载" ? "#777" : (modelData.status === "完成" ? "#4caf50" : "#007acc")
                                    Layout.preferredWidth: 100
                                    horizontalAlignment: Text.AlignRight
                                }
                            }
                        }

                        Text {
                            anchors.centerIn: parent
                            text: "尚未解析任何连接"
                            color: "#777777"
                            font.pixelSize: 16
                            visible: root.videoListModel.length === 0
                        }
                    }
                }
            }

            // Downloader Settings & Status Area
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
                        text: "下载设置与控制"
                        color: "#cccccc"
                        font.pixelSize: 14
                        font.bold: true
                    }

                    // Download Options
                    RowLayout {
                        spacing: 15

                        Text {
                            text: "格式:"
                            color: "#bbbbbb"
                        }
                        ComboBox {
                            id: comboFormat
                            model: chkAudioOnly.checked ? ["mp3", "m4a", "wav"] : ["mp4", "mkv", "webm"]
                            background: Rectangle {
                                color: "#3c3c3c"
                                radius: 4
                            }
                            contentItem: Text {
                                text: comboFormat.currentText
                                color: "white"
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: 10
                            }
                            Layout.preferredWidth: 80
                        }

                        Text {
                            text: "画质:"
                            color: "#bbbbbb"
                            opacity: chkAudioOnly.checked ? 0.5 : 1.0
                        }
                        ComboBox {
                            id: comboQuality
                            model: ["best", "2160p", "1440p", "1080p", "720p", "480p"]
                            enabled: !chkAudioOnly.checked
                            background: Rectangle {
                                color: "#3c3c3c"
                                radius: 4
                            }
                            contentItem: Text {
                                text: comboQuality.currentText
                                color: "white"
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: 10
                            }
                            Layout.preferredWidth: 100
                        }

                        CheckBox {
                            id: chkAudioOnly
                            text: "仅下载音频"
                            contentItem: Text {
                                text: parent.text
                                color: "white"
                                leftPadding: parent.indicator.width + 5
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        Text {
                            text: "字幕:"
                            color: "#bbbbbb"
                            opacity: chkAudioOnly.checked ? 0.5 : 1.0
                        }
                        CheckBox {
                            id: chkSubs
                            text: "下载"
                            enabled: !chkAudioOnly.checked
                            contentItem: Text {
                                text: parent.text
                                color: "white"
                                leftPadding: parent.indicator.width + 5
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                        ComboBox {
                            id: comboSubLang
                            model: ["en", "zh-Hans", "zh-Hant", "ja", "ko", "auto"]
                            editable: true
                            enabled: !chkAudioOnly.checked
                            background: Rectangle {
                                color: "#3c3c3c"
                                radius: 4
                            }
                            contentItem: TextInput {
                                text: comboSubLang.currentText
                                color: "white"
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: 10
                            }
                            Layout.preferredWidth: 80
                        }

                        Text {
                            text: "线程:"
                            color: "#bbbbbb"
                        }
                        SpinBox {
                            id: spinConcurrency
                            from: 1
                            to: 8
                            value: 4
                            background: Rectangle {
                                color: "#3c3c3c"
                                radius: 4
                            }
                            contentItem: TextInput {
                                text: spinConcurrency.textFromValue(spinConcurrency.value, spinConcurrency.locale)
                                color: "white"
                                horizontalAlignment: Qt.AlignHCenter
                                verticalAlignment: Qt.AlignVCenter
                            }
                            Layout.preferredWidth: 100
                        }

                        Item {
                            Layout.fillWidth: true
                        }

                        Button {
                            text: "检查更新"
                            onClicked: {
                                updateDialog.addLog("正在检查版本信息...");
                                updateDialog.open();
                                videoDownloaderBridge.checkUpdate();
                            }
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

                    // Path Options
                    RowLayout {
                        spacing: 15

                        Text {
                            text: "保存目录:"
                            color: "#bbbbbb"
                        }
                        TextField {
                            id: savePathField
                            Layout.fillWidth: true
                            text: videoDownloaderBridge.defaultPath
                            onTextChanged: {
                                videoDownloaderBridge.setDefaultPath(text);
                            }
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

                    // Progress and Start
                    RowLayout {
                        spacing: 15
                        Layout.fillWidth: true

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 5

                            Text {
                                id: statusLabel
                                text: "等待开始..."
                                color: "#007acc"
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            ProgressBar {
                                id: overallPB
                                Layout.fillWidth: true
                                value: 0.0
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

                        Button {
                            text: root.isDownloading ? "🛑 停止下载" : "⬇️ 开始下载"
                            onClicked: root.toggleDownload()
                            background: Rectangle {
                                color: root.isDownloading ? "#8B0000" : (parent.hovered ? "#006bb3" : "#007acc")
                                radius: 4
                                implicitHeight: 45
                                implicitWidth: 140
                            }
                            contentItem: Text {
                                text: parent.text
                                color: "white"
                                font.bold: true
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }
            }
        }
    }

    // Dialogs
    FolderDialog {
        id: folderDialog
        title: "选择保存目录"
        onAccepted: {
            videoDownloaderBridge.setDefaultPath(selectedFolder.toString().replace("file://", ""));
        }
    }

    Dialog {
        id: updateDialog
        title: "yt-dlp 版本管理"
        modal: true
        width: 550
        height: 400
        anchors.centerIn: parent

        background: Rectangle {
            color: "#252526"
            border.color: "#3e3e42"
            border.width: 1
            radius: 8
        }

        property string localVer: videoDownloaderBridge.localVersion
        property string remoteVer: "正在检查..."
        property bool hasUpdate: false
        property bool btnUpdateEnabled: hasUpdate && !root.isUpdating && !root.isDownloading

        function addLog(msg) {
            var txt = updateLogText.text;
            if (txt !== "")
                txt += "\n";
            txt += msg;
            updateLogText.text = txt;
            updateLogText.cursorPosition = updateLogText.text.length; // auto scroll
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 15
            spacing: 15

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 80
                color: "#1e1e1e"
                border.color: "#3e3e42"
                radius: 4

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 10
                    RowLayout {
                        Text {
                            text: "当前本地版本:"
                            color: "#bbbbbb"
                            Layout.preferredWidth: 100
                        }
                        Text {
                            text: updateDialog.localVer
                            color: "white"
                        }
                    }
                    RowLayout {
                        Text {
                            text: "最新远程版本:"
                            color: "#bbbbbb"
                            Layout.preferredWidth: 100
                        }
                        Text {
                            text: updateDialog.remoteVer
                            color: "white"
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Item {
                    Layout.fillWidth: true
                }
                Button {
                    text: root.isUpdating ? "更新中..." : "立即更新"
                    enabled: updateDialog.btnUpdateEnabled
                    onClicked: {
                        root.isUpdating = true;
                        btnAnalyze.enabled = false;
                        videoDownloaderBridge.startUpdate();
                    }
                    background: Rectangle {
                        color: parent.enabled ? (parent.hovered ? "#006bb3" : "#007acc") : "#444"
                        radius: 4
                        implicitHeight: 35
                        implicitWidth: 100
                    }
                    contentItem: Text {
                        text: parent.text
                        color: parent.enabled ? "white" : "#888"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                }
            }

            Text {
                text: "更新日志:"
                color: "#bbbbbb"
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: "#1e1e1e"
                border.color: "#3e3e42"
                radius: 4

                ScrollView {
                    anchors.fill: parent
                    TextArea {
                        id: updateLogText
                        color: "#00FF00"
                        font.family: "Courier New"
                        readOnly: true
                        background: null
                    }
                }
            }
        }

        standardButtons: Dialog.Close
    }

    // Logic
    function analyzeUrl() {
        if (urlInput.text === "")
            return;
        btnAnalyze.enabled = false;
        statusLabel.text = "正在解析链接信息...";
        statusLabel.color = "#007acc";
        overallPB.value = 0;
        root.videoListModel = [];
        taskList.model = root.videoListModel;
        videoDownloaderBridge.analyzeUrl(urlInput.text);
    }

    function toggleDownload() {
        if (root.isDownloading) {
            statusLabel.text = "正在停止...";
            btnAnalyze.enabled = true;
            videoDownloaderBridge.stopDownload();
            // Assume it will stop soon and onDownloadError/Finished will be called
        } else {
            // Find selected items
            var itemsToDownload = [];
            for (var i = 0; i < root.videoListModel.length; i++) {
                if (root.videoListModel[i].checked) {
                    itemsToDownload.push({
                        "url": root.videoListModel[i].url,
                        "ui_index": i,
                        "title": root.videoListModel[i].title
                    });
                }
            }
            if (itemsToDownload.length === 0) {
                // Not the best way to show message but it works
                statusLabel.text = "请至少选择一个视频";
                statusLabel.color = "#ff9800";
                statusResetTimer.start();
                return;
            }

            var opts = {
                "out_dir": savePathField.text,
                "audio_only": chkAudioOnly.checked,
                "ext": comboFormat.currentText,
                "quality": chkAudioOnly.checked ? "" : comboQuality.currentText,
                "subtitles": chkSubs.checked,
                "sub_lang": comboSubLang.currentText,
                "concurrency": spinConcurrency.value
            };

            root.isDownloading = true;
            btnAnalyze.enabled = false;
            statusLabel.text = "准备下载...";
            overallPB.value = 0;
            videoDownloaderBridge.startDownload(JSON.stringify(itemsToDownload), JSON.stringify(opts));
        }
    }
}
