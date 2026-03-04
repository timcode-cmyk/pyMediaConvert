import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import QtMultimedia

Item {
    id: root

    // Properties for Data received from Bridge
    property string apiKey: ""
    property string defaultSavePath: ""
    property string ttsFileName: ""
    property string sfxFileName: ""
    property var models: []
    property var voices: []
    property int quotaUsage: 0
    property int quotaLimit: 0

    // Player State
    property bool isPlaying: false

    MediaPlayer {
        id: audioPlayer
        audioOutput: AudioOutput {}
        onPlaybackStateChanged: {
            isPlaying = playbackState === MediaPlayer.PlayingState;
        }
        onPositionChanged: {
            if (!sliderSeek.pressed && isPlaying) {
                sliderSeek.value = position;
                currentTimeLabel.text = formatTime(position);
            }
        }
        onDurationChanged: {
            sliderSeek.to = duration;
            totalTimeLabel.text = formatTime(duration);
        }
    }

    Component.onCompleted: {
        var settings = elevenLabsBridge.getInitialSettings();
        apiKey = settings.apiKey;
        apiKeyInput.text = apiKey;
        defaultSavePath = settings.defaultSavePath;
        ttsFileName = settings.ttsFileName;
        sfxFileName = settings.sfxFileName;

        if (apiKey !== "") {
            elevenLabsBridge.loadApiData(apiKey);
        }
    }

    Connections {
        target: elevenLabsBridge

        function onModelsLoaded(modelList) {
            root.models = modelList;
            modelCombo.model = root.models;
        }

        function onVoicesLoaded(voiceList) {
            root.voices = voiceList;
            voiceCombo.model = root.voices;
            if (voiceList.length > 0) {
                voiceCombo.currentIndex = 0;
            }
        }

        function onQuotaLoaded(usage, limit) {
            root.quotaUsage = usage;
            root.quotaLimit = limit;
        }

        function onGenerationSuccess(filePath, type) {
            audioPlayer.stop();
            audioPlayer.source = "file://" + filePath;
            mainStatusLabel.text = "已保存: " + filePath;

            // Refresh filenames
            var settings = elevenLabsBridge.getInitialSettings();
            ttsFileName = settings.ttsFileName;
            sfxFileName = settings.sfxFileName;

            if (type === 'tts')
                ttsOutputField.text = ttsFileName;
            if (type === 'sfx')
                sfxOutputField.text = sfxFileName;
        }

        function onGenerationError(msg) {
            mainStatusLabel.text = "错误: " + msg;
            mainStatusLabel.color = "#e53935"; // Red

            // Revert color after a few seconds
            statusResetTimer.start();
        }
    }

    Timer {
        id: statusResetTimer
        interval: 5000
        onTriggered: {
            mainStatusLabel.text = elevenLabsBridge.statusText;
            mainStatusLabel.color = "#007acc";
        }
    }

    function formatTime(ms) {
        var seconds = Math.floor((ms / 1000) % 60);
        var minutes = Math.floor((ms / 60000));
        return (minutes < 10 ? "0" : "") + minutes + ":" + (seconds < 10 ? "0" : "") + seconds;
    }

    Rectangle {
        anchors.fill: parent
        color: "#1e1e1e"

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 15

            // Title
            Text {
                text: "ElevenLabs 语音合成"
                color: "white"
                font.pixelSize: 28
                font.bold: true
                Layout.topMargin: 10
            }

            // API Config Group
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 100
                color: "#252526"
                radius: 8
                border.color: "#3e3e42"
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 15
                    spacing: 15

                    RowLayout {
                        spacing: 10
                        Text {
                            text: "API Key:"
                            color: "#cccccc"
                            font.pixelSize: 14
                        }

                        TextField {
                            id: apiKeyInput
                            Layout.fillWidth: true
                            echoMode: TextInput.Password
                            placeholderText: "sk-..."
                            color: "white"
                            background: Rectangle {
                                color: "#3c3c3c"
                                radius: 6
                            }
                        }

                        Button {
                            text: "💾 保存"
                            onClicked: elevenLabsBridge.saveApiKey(apiKeyInput.text)
                            background: Rectangle {
                                color: parent.hovered ? "#505050" : "#444444"
                                radius: 6
                            }
                            contentItem: Text {
                                text: parent.text
                                color: "white"
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        Button {
                            text: "🔄 刷新配置"
                            onClicked: elevenLabsBridge.loadApiData(apiKeyInput.text)
                            background: Rectangle {
                                color: parent.hovered ? "#006bb3" : "#007acc"
                                radius: 6
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
                        spacing: 10
                        Text {
                            text: "额度使用情况:"
                            color: "#cccccc"
                            font.pixelSize: 14
                        }

                        ProgressBar {
                            Layout.fillWidth: true
                            value: root.quotaLimit > 0 ? (root.quotaUsage / root.quotaLimit) : 0
                            background: Rectangle {
                                implicitHeight: 8
                                color: "#3c3c3c"
                                radius: 6
                            }
                            contentItem: Item {
                                Rectangle {
                                    width: parent.parent.visualPosition * parent.width
                                    height: parent.height
                                    radius: 6
                                    color: (parent.parent.value > 0.9) ? "#ef4444" : "#007acc"
                                }
                            }
                        }

                        Text {
                            text: (root.quotaLimit > 0 ? (root.quotaUsage + " / " + root.quotaLimit + " (" + Math.round(root.quotaUsage / root.quotaLimit * 100) + "%)") : "-- / --")
                            color: "white"
                        }
                    }
                }
            }

            // Tabs for TTS / SFX
            TabBar {
                id: bar
                Layout.fillWidth: true
                background: Rectangle {
                    color: "transparent"
                }

                TabButton {
                    id: ttsTab
                    text: "🗣️ 文本转语音 (TTS)"
                    width: Math.max(150, implicitWidth)
                    contentItem: Text {
                        text: parent.text
                        font.pixelSize: 14
                        color: parent.checked ? "white" : "#a0a0a0"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.bold: parent.checked
                    }
                    background: Rectangle {
                        color: ttsTab.checked ? "#252526" : "#2d2d30"
                        border.color: ttsTab.checked ? "#007acc" : "transparent"
                        border.width: ttsTab.checked ? 1 : 0
                        Rectangle {
                            height: 2
                            width: parent.width
                            color: "#007acc"
                            anchors.bottom: parent.bottom
                            visible: ttsTab.checked
                        }
                    }
                }
                TabButton {
                    id: sfxTab
                    text: "🎵 音效生成 (SFX)"
                    width: Math.max(150, implicitWidth)
                    contentItem: Text {
                        text: parent.text
                        font.pixelSize: 14
                        color: parent.checked ? "white" : "#a0a0a0"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.bold: parent.checked
                    }
                    background: Rectangle {
                        color: sfxTab.checked ? "#252526" : "#2d2d30"
                        border.color: sfxTab.checked ? "#007acc" : "transparent"
                        border.width: sfxTab.checked ? 1 : 0
                        Rectangle {
                            height: 2
                            width: parent.width
                            color: "#007acc"
                            anchors.bottom: parent.bottom
                            visible: sfxTab.checked
                        }
                    }
                }
            }

            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: bar.currentIndex

                // --- TTS TAB ---
                Rectangle {
                    color: "#252526"
                    border.color: "#3e3e42"
                    border.width: 1

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 15
                        spacing: 10

                        // Voice & Model Selection
                        RowLayout {
                            spacing: 10
                            Text {
                                text: "选择声音:"
                                color: "white"
                            }
                            ComboBox {
                                id: voiceCombo
                                Layout.fillWidth: true
                                textRole: "name"
                                valueRole: "voice_id"
                                background: Rectangle {
                                    color: "#3c3c3c"
                                    radius: 6
                                    implicitHeight: 32
                                }
                                contentItem: Text {
                                    text: voiceCombo.currentText
                                    color: "white"
                                    verticalAlignment: Text.AlignVCenter
                                    leftPadding: 10
                                }
                            }
                            ComboBox {
                                id: modelCombo
                                Layout.fillWidth: true
                                textRole: "name"
                                valueRole: "model_id"
                                background: Rectangle {
                                    color: "#3c3c3c"
                                    radius: 6
                                    implicitHeight: 32
                                }
                                contentItem: Text {
                                    text: modelCombo.currentText
                                    color: "white"
                                    verticalAlignment: Text.AlignVCenter
                                    leftPadding: 10
                                }
                            }
                            Button {
                                text: "🔊 试听"
                                background: Rectangle {
                                    color: parent.hovered ? "#505050" : "#444444"
                                    radius: 6
                                    implicitHeight: 32
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: "white"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: {
                                    if (voiceCombo.currentIndex >= 0) {
                                        var url = root.voices[voiceCombo.currentIndex].preview_url;
                                        if (url) {
                                            audioPlayer.stop();
                                            audioPlayer.source = url;
                                            audioPlayer.play();
                                        }
                                    }
                                }
                            }
                        }

                        // Text Input
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            color: "#1e1e1e"
                            border.color: "#3e3e42"

                            ScrollView {
                                anchors.fill: parent
                                TextArea {
                                    id: ttsTextInput
                                    placeholderText: "请输入文本内容... \n提示: 可使用 [happy], [sad] 等标签控制情绪 (仅限v3模型)"
                                    color: "white"
                                    font.pixelSize: 14
                                    wrapMode: Text.WordWrap
                                    background: null // transparent
                                }
                            }
                        }

                        // Subtitle Options
                        RowLayout {
                            spacing: 15
                            CheckBox {
                                id: chkTranslate
                                text: "自动翻译 (中)"
                                contentItem: Text {
                                    text: parent.text
                                    color: "white"
                                    leftPadding: parent.indicator.width + 5
                                }
                            }
                            CheckBox {
                                id: chkWordLevel
                                text: "逐词字幕"
                                contentItem: Text {
                                    text: parent.text
                                    color: "white"
                                    leftPadding: parent.indicator.width + 5
                                }
                            }
                            CheckBox {
                                id: chkExportXml
                                text: "导出 XML"
                                contentItem: Text {
                                    text: parent.text
                                    color: "white"
                                    leftPadding: parent.indicator.width + 5
                                }
                            }
                            CheckBox {
                                id: chkHighlight
                                text: "高亮关键词"
                                enabled: chkExportXml.checked
                                contentItem: Text {
                                    text: parent.text
                                    color: parent.enabled ? "white" : "#777"
                                    leftPadding: parent.indicator.width + 5
                                }
                            }

                            Item {
                                Layout.fillWidth: true
                            } // Spacer
                        }

                        // Output & Generate
                        RowLayout {
                            spacing: 10
                            Text {
                                text: "保存至:"
                                color: "white"
                            }
                            TextField {
                                id: ttsOutputField
                                text: root.defaultSavePath !== "" ? root.defaultSavePath + "/" + root.ttsFileName : root.ttsFileName
                                Layout.fillWidth: true
                                color: "white"
                                background: Rectangle {
                                    color: "#3c3c3c"
                                    radius: 6
                                }
                            }
                            Button {
                                text: "..."
                                onClicked: saveDialog.open()
                                background: Rectangle {
                                    color: "#444"
                                    radius: 6
                                    implicitWidth: 40
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: "white"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                            Button {
                                text: "生成语音"
                                enabled: !elevenLabsBridge.isBusy
                                background: Rectangle {
                                    color: parent.hovered ? "#006bb3" : "#007acc"
                                    radius: 6
                                    implicitWidth: 100
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: "white"
                                    font.bold: true
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: {
                                    elevenLabsBridge.generateTTS({
                                        api_key: apiKeyInput.text,
                                        voice_id: voiceCombo.currentValue,
                                        model_id: modelCombo.currentValue,
                                        text: ttsTextInput.text,
                                        save_path: ttsOutputField.text,
                                        translate: chkTranslate.checked,
                                        word_level: chkWordLevel.checked,
                                        export_xml: chkExportXml.checked,
                                        keyword_highlight: chkHighlight.checked
                                        // Optional: add settings from dialogs later
                                    });
                                }
                            }
                        }
                    }
                }

                // --- SFX TAB ---
                Rectangle {
                    color: "#252526"
                    border.color: "#3e3e42"
                    border.width: 1

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 15
                        spacing: 15

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: 15

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                color: "#1e1e1e"
                                border.color: "#3e3e42"

                                ScrollView {
                                    anchors.fill: parent
                                    TextArea {
                                        id: sfxPromptInput
                                        placeholderText: "描述音效，例如: footsteps on wood floor..."
                                        color: "white"
                                        font.pixelSize: 14
                                        wrapMode: Text.WordWrap
                                        background: null
                                    }
                                }
                            }

                            ColumnLayout {
                                Layout.alignment: Qt.AlignTop
                                Text {
                                    text: "时长 (秒):"
                                    color: "white"
                                }
                                SpinBox {
                                    id: sfxDurationSpin
                                    from: 1
                                    to: 22
                                    value: 5
                                    background: Rectangle {
                                        color: "#3c3c3c"
                                        radius: 6
                                    }
                                    // Make text white
                                    contentItem: TextInput {
                                        text: sfxDurationSpin.textFromValue(sfxDurationSpin.value, sfxDurationSpin.locale)
                                        color: "white"
                                        horizontalAlignment: Qt.AlignHCenter
                                        verticalAlignment: Qt.AlignVCenter
                                    }
                                }
                            }
                        }

                        // Output & Generate
                        RowLayout {
                            spacing: 10
                            Text {
                                text: "保存至:"
                                color: "white"
                            }
                            TextField {
                                id: sfxOutputField
                                text: root.defaultSavePath !== "" ? root.defaultSavePath + "/" + root.sfxFileName : root.sfxFileName
                                Layout.fillWidth: true
                                color: "white"
                                background: Rectangle {
                                    color: "#3c3c3c"
                                    radius: 6
                                }
                            }
                            Button {
                                text: "..."
                                onClicked: saveDialog.open()
                                background: Rectangle {
                                    color: "#444"
                                    radius: 6
                                    implicitWidth: 40
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: "white"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                            Button {
                                text: "生成音效"
                                enabled: !elevenLabsBridge.isBusy
                                background: Rectangle {
                                    color: parent.hovered ? "#006bb3" : "#007acc"
                                    radius: 6
                                    implicitWidth: 100
                                }
                                contentItem: Text {
                                    text: parent.text
                                    color: "white"
                                    font.bold: true
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                                onClicked: {
                                    elevenLabsBridge.generateSFX({
                                        api_key: apiKeyInput.text,
                                        prompt: sfxPromptInput.text,
                                        duration: sfxDurationSpin.value,
                                        save_path: sfxOutputField.text
                                    });
                                }
                            }
                        }
                    }
                }
            }

            // Bottom Player Panel
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 50
                color: "#252526"
                radius: 8
                border.color: "#3e3e42"
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 15

                    Button {
                        text: isPlaying ? "⏸ 暂停" : "▶ 播放"
                        enabled: audioPlayer.source.toString() !== ""
                        background: Rectangle {
                            color: parent.enabled ? (parent.hovered ? "#505050" : "#444444") : "#333"
                            radius: 6
                            implicitWidth: 80
                        }
                        contentItem: Text {
                            text: parent.text
                            color: parent.enabled ? "white" : "#777"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                        onClicked: {
                            if (isPlaying)
                                audioPlayer.pause();
                            else
                                audioPlayer.play();
                        }
                    }

                    Text {
                        id: currentTimeLabel
                        text: "00:00"
                        color: "white"
                    }

                    Slider {
                        id: sliderSeek
                        Layout.fillWidth: true
                        from: 0
                        to: 100
                        enabled: audioPlayer.source.toString() !== ""
                        onMoved: {
                            audioPlayer.position = value;
                            currentTimeLabel.text = root.formatTime(value);
                        }
                    }

                    Text {
                        id: totalTimeLabel
                        text: "00:00"
                        color: "white"
                    }

                    Text {
                        id: mainStatusLabel
                        text: elevenLabsBridge.statusText
                        color: "#007acc"
                        font.italic: true
                        Layout.preferredWidth: 150
                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideRight
                    }
                }
            }
        }
    }

    // Common Save Dialog
    FileDialog {
        id: saveDialog
        title: "选择保存路径"
        fileMode: FileDialog.SaveFile
        nameFilters: ["Audio (*.mp3)"]
        onAccepted: {
            var path = selectedFile.toString().replace("file://", "");
            if (bar.currentIndex === 0) {
                ttsOutputField.text = path;
            } else {
                sfxOutputField.text = path;
            }
        }
    }
}
