import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import "Components"
import io.mrarm.mcpelauncher 1.0

Item {
    id: root
    objectName: "maccraftLogin"
    property GoogleLoginHelper googleLoginHelper
    property VersionManager versionManager
    property bool acquiringAccount: false
    signal finished

    Component.onCompleted: launcherSettings.trialMode = false

    Rectangle {
        anchors.fill: parent
        color: "#111a17"
        gradient: Gradient {
            GradientStop { position: 0; color: "#172b22" }
            GradientStop { position: 1; color: "#101612" }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: Math.min(parent.width * 0.07, 64)
        spacing: 48

        ColumnLayout {
            visible: root.width >= 850
            Layout.fillWidth: true
            Layout.preferredWidth: 390
            spacing: 20

            Rectangle {
                width: 64; height: 64; radius: 16; color: "#83e5a5"
                Text { anchors.centerIn: parent; text: "M"; color: "#102218"; font.pixelSize: 38; font.bold: true }
            }
            Text { text: "MacCraft"; font.pixelSize: 46; font.bold: true; color: "#f4fff7" }
            Text {
                text: "Your worlds.\nYour Mac."
                font.pixelSize: 38; font.bold: true; color: "#cce7d5"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }
            Text {
                text: "Minecraft Bedrock for Apple silicon."
                font.pixelSize: 17; color: "#9bb5a4"
                Layout.fillWidth: true; wrapMode: Text.WordWrap
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredWidth: 400
            Layout.maximumWidth: 460
            Layout.alignment: Qt.AlignHCenter | Qt.AlignVCenter
            implicitHeight: form.implicitHeight + 64
            color: "#1d2a23"; radius: 20
            border.color: "#354b3d"

            ColumnLayout {
                id: form
                anchors.fill: parent
                anchors.margins: 32
                spacing: 18

                Text { text: "Let’s get you playing."; font.pixelSize: 27; font.bold: true; color: "#f4fff7"; Layout.fillWidth: true; wrapMode: Text.WordWrap }
                Text {
                    text: "Sign in with the Google account that owns Minecraft on Google Play."
                    color: "#b8d0c0"; font.pixelSize: 16; lineHeight: 1.2
                    wrapMode: Text.WordWrap; Layout.fillWidth: true
                }
                MButton {
                    objectName: "googleSignInButton"
                    text: root.acquiringAccount ? "Signing in…" : "Sign in with Google"
                    Layout.fillWidth: true; implicitHeight: 52
                    enabled: !root.acquiringAccount
                    onClicked: {
                        root.acquiringAccount = true
                        googleLoginHelper.acquireAccount(window)
                    }
                    background: Rectangle { radius: 9; color: parent.down ? "#cad6cd" : "#f3f8f4"; opacity: parent.enabled ? 1 : 0.6 }
                    contentItem: Text { text: parent.text; color: "#18251d"; font.pixelSize: 16; font.bold: true; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                }
                Text {
                    text: "MacCraft downloads your Android copy from Google Play and installs it for you."
                    color: "#9bb5a4"; font.pixelSize: 14
                    wrapMode: Text.WordWrap; Layout.fillWidth: true
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: "#354b3d" }
                Text {
                    text: "You’ll need to own the Android edition. Microsoft/Xbox sign-in happens separately inside Minecraft."
                    color: "#9bb5a4"; font.pixelSize: 13
                    wrapMode: Text.WordWrap; Layout.fillWidth: true
                }
                Label {
                    text: "<a href='https://play.google.com/store/apps/details?id=com.mojang.minecraftpe'>View Minecraft on Google Play ↗</a>"
                    color: "#83e5a5"; linkColor: "#83e5a5"
                    font.pixelSize: 13; wrapMode: Text.WordWrap; Layout.fillWidth: true
                    onLinkActivated: function(link) { Qt.openUrlExternally(link) }
                }
            }
        }
    }
    Text {
        anchors.bottom: parent.bottom; anchors.bottomMargin: 16
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width - 40
        text: "Unofficial launcher. Not affiliated with Mojang, Microsoft, or Google."
        color: "#718a79"; font.pixelSize: 11
        horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
    }
    Connections {
        target: googleLoginHelper
        function onAccountAcquireFinished(account) {
            root.acquiringAccount = false
            if (account) root.finished()
        }
    }
    Connections {
        target: window
        function onClosing() { application.quit() }
    }
}
