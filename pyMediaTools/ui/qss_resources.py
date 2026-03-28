# AUTO-GENERATED: QSS resources embedded as Python strings for better portability (e.g. Nuitka/PyInstaller)

DARK_STYLE = """
/* Main Application Background */
QMainWindow {
    background-color: transparent;
}

#MainContainer {
    background-color: #1E1E1E;
    border-radius: 12px;
    border: 1px solid #303031;
}

/* Sidebar Styling */
#Sidebar {
    background-color: #252526;
    border-right: 1px solid #303031;
    border-top-left-radius: 12px;
    border-bottom-left-radius: 12px;
}

/* Sidebar Buttons */
#SidebarButton {
    text-align: left;
    padding: 12px 20px;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    color: #CCCCCC;
    background-color: transparent;
    margin: 4px 10px;
}

#SidebarButton:hover {
    background-color: #2A2D2E;
    color: #FFFFFF;
}

#SidebarButton[active="true"] {
    background-color: #37373D;
    color: #FFFFFF;
    font-weight: bold;
    border-left: 4px solid #007ACC;
    border-radius: 4px;
}

/* Sidebar Title/Logo Area */
#SidebarTitle {
    font-size: 18px;
    font-weight: bold;
    color: #FFFFFF;
    padding: 20px 10px;
}

/* Header Styling */
#Header {
    background-color: transparent;
}

#HeaderTitleText, #HeaderTitle {
    color: #D4D4D4;
    padding-top: 5px;
}

#HeaderIcons {
    color: #858585;
}

#HeaderSearch {
    background-color: #3C3C3C;
    border: 1px solid #3C3C3C;
    border-radius: 18px;
    padding: 8px 15px;
    font-size: 13px;
    color: #CCCCCC;
}

#HeaderSearch:focus {
    border: 1px solid #007ACC;
}

/* Base Card Style for internal widgets */
QWidget#MainContentArea > QWidget {
    background-color: transparent;
}

/* Styling internal groupboxes/cards to look like dashboard panels */
QGroupBox {
    background-color: #252526;
    border-radius: 8px;
    border: 1px solid #303031;
    margin-top: 2ex; /* space for title */
    font-weight: bold;
    color: #D4D4D4;
    padding: 15px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 15px;
    top: 5px;
    padding: 0 5px;
    color: #858585;
}

QTabWidget::pane {
    border: 1px solid #303031;
    background-color: #252526;
    border-radius: 8px;
}

QTabBar::tab {
    background: #2D2D2D;
    border: 1px solid #303031;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    color: #858585;
}

QTabBar::tab:selected {
    background: #1E1E1E;
    border-bottom-color: #1E1E1E;
    color: #007ACC;
    font-weight: bold;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

/* --- Window Controls (macOS Traffic Lights) --- */
#WindowClose { background-color: #FF5F56; border-radius: 6px; border: none; }
#WindowClose:hover { background-color: #E04E47; }
#WindowMin { background-color: #FFBD2E; border-radius: 6px; border: none; }
#WindowMin:hover { background-color: #E0A428; }
#WindowMax { background-color: #27C93F; border-radius: 6px; border: none; }
#WindowMax:hover { background-color: #1EA632; }

/* --- Window Controls (Windows Style) --- */
#WinMin, #WinMax, #WinClose {
    background: transparent;
    border: none;
    color: #CCCCCC;
    font-size: 16px;
    padding: 5px 10px;
    min-width: 30px;
}
#WinMin:hover, #WinMax:hover { background-color: #37373D; }
#WinClose:hover { background-color: #E81123; color: white; }
"""

LIGHT_STYLE = """
/* Main Application Background */
QMainWindow {
    background-color: #F0F4FA;
}

/* Sidebar Styling */
#Sidebar {
    background-color: #FFFFFF;
    border-right: 1px solid #E5E9F2;
}

/* Sidebar Buttons */
#SidebarButton {
    text-align: left;
    padding: 12px 20px;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    color: #4A5568;
    background-color: transparent;
    margin: 4px 10px;
}

#SidebarButton:hover {
    background-color: #F7FAFC;
    color: #2B6CB0;
}

#SidebarButton[active="true"] {
    background-color: #EBF4FF;
    color: #3182CE;
    font-weight: bold;
    border-left: 4px solid #3182CE;
    border-radius: 4px;
}

/* Sidebar Title/Logo Area */
#SidebarTitle {
    font-size: 18px;
    font-weight: bold;
    color: #2D3748;
    padding: 20px 10px;
}

/* Header Styling */
#Header {
    background-color: transparent;
}

#HeaderTitle {
    color: #2D3748;
}

#HeaderIcons {
    color: #4A5568;
}

#HeaderSearch {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 18px;
    padding: 8px 15px;
    font-size: 13px;
    color: #4A5568;
}

#HeaderSearch:focus {
    border: 1px solid #3182CE;
}

/* Base Card Style for internal widgets */
QWidget#MainContentArea > QWidget {
    background-color: transparent;
}

/* Styling internal groupboxes/cards to look like dashboard panels */
QGroupBox {
    background-color: #FFFFFF;
    border-radius: 12px;
    border: 1px solid #E2E8F0;
    margin-top: 2ex; /* space for title */
    font-weight: bold;
    color: #2D3748;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 15px;
    top: 5px;
    padding: 0 5px;
    color: #4A5568;
}

QTabWidget::pane {
    border: 1px solid #E2E8F0;
    background-color: #FFFFFF;
    border-radius: 8px;
}

QTabBar::tab {
    background: #EDF2F7;
    border: 1px solid #E2E8F0;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    color: #4A5568;
}

QTabBar::tab:selected {
    background: #FFFFFF;
    border-bottom-color: #FFFFFF;
    color: #2B6CB0;
    font-weight: bold;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}
"""
