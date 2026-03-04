import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: window
    visible: true
    width: 1000
    height: 700
    title: "MediaTools"
    color: "#1e1e1e" // Dark theme background
    minimumWidth: 800
    minimumHeight: 600

    // Font setting
    font.family: "Segoe UI"
    font.pixelSize: 14

    RowLayout {
        anchors.fill: parent
        spacing: 0

        // Navigation Sidebar
        Rectangle {
            id: sidebar
            Layout.fillHeight: true
            Layout.preferredWidth: 220
            color: "#252526"

            ColumnLayout {
                anchors.fill: parent
                // App Logo/Title
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 80
                    color: "transparent"

                    Text {
                        anchors.centerIn: parent
                        text: "MediaTools"
                        color: "#ffffff"
                        font.pixelSize: 22
                        font.bold: true
                    }
                }

                // Navigation Items
                ListView {
                    id: navList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: ListModel {
                        ListElement {
                            name: "媒体转换"
                            view: "views/MediaConverterView.qml"
                            icon: "🎬"
                        }
                        ListElement {
                            name: "ElevenLabs"
                            view: "views/ElevenLabsView.qml"
                            icon: "🎙️"
                        }
                        ListElement {
                            name: "场景分割"
                            view: "views/VideoCutView.qml"
                            icon: "✂️"
                        }
                        ListElement {
                            name: "云端同步"
                            view: "views/DownloadManagerView.qml"
                            icon: "☁️"
                        }
                        ListElement {
                            name: "视频下载"
                            view: "views/VideoDownloaderView.qml"
                            icon: "⬇️"
                        }
                    }

                    delegate: ItemDelegate {
                        width: ListView.view.width
                        height: 50

                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: 4
                            radius: 6
                            color: navList.currentIndex === index ? "#37373d" : (parent.hovered ? "#2a2d2e" : "transparent")

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 15
                                spacing: 10

                                Text {
                                    text: model.icon
                                    font.pixelSize: 18
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: model.name
                                    color: navList.currentIndex === index ? "#ffffff" : "#cccccc"
                                    font.pixelSize: 15
                                    font.bold: navList.currentIndex === index
                                }
                            }
                        }

                        onClicked: {
                            navList.currentIndex = index;
                            stackView.replace(model.view);
                        }
                    }
                }
            }
        }

        // Separator Line
        Rectangle {
            Layout.fillHeight: true
            Layout.preferredWidth: 1
            color: "#333333"
        }

        // Main Content Area
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "#1e1e1e"

            StackView {
                id: stackView
                anchors.fill: parent
                initialItem: "views/MediaConverterView.qml"

                pushEnter: Transition {
                    PropertyAnimation {
                        property: "opacity"
                        from: 0
                        to: 1
                        duration: 200
                    }
                }
                pushExit: Transition {
                    PropertyAnimation {
                        property: "opacity"
                        from: 1
                        to: 0
                        duration: 200
                    }
                }
                replaceEnter: Transition {
                    PropertyAnimation {
                        property: "opacity"
                        from: 0
                        to: 1
                        duration: 200
                    }
                }
                replaceExit: Transition {
                    PropertyAnimation {
                        property: "opacity"
                        from: 1
                        to: 0
                        duration: 200
                    }
                }
            }
        }
    }
}
