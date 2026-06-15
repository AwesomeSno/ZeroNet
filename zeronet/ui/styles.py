# PyQt6 QSS stylesheet for ZeroNet
# Implements a Windows 95 / ICQ retro theme with classic teal background,
# gray window borders, beveled buttons, and monospace fonts.

from zeronet.ui import main_window
MAIN_STYLE = """
/* General Application Styles */
QMainWindow {
    background-color: #008080; /* Classic Teal Desktop */
}

QWidget {
    background-color: #c0c0c0; /* Win95 Light Gray */
    color: #000000;
    font-family: 'Fixedsys', 'Courier New', 'MS Sans Serif', monospace;
    font-size: 12px;
}

/* Beveled Frames */
QFrame#sidebar, QFrame#chat_panel_frame {
    background-color: #c0c0c0;
    border: 2px solid;
    border-color: #ffffff #808080 #808080 #ffffff; /* Outset bevel */
    margin: 4px;
}

/* User profile header */
QFrame#profile_frame, QFrame#header_frame {
    background-color: #c0c0c0;
    border-bottom: 2px solid #808080;
    padding: 6px;
}

/* Inputs and Lists (white background, inset bevel) */
QLineEdit, QTextEdit, QListWidget {
    background-color: #ffffff;
    color: #000000;
    border: 2px solid;
    border-color: #808080 #ffffff #ffffff #808080; /* Inset bevel */
    padding: 4px;
    selection-background-color: #000080;
    selection-color: #ffffff;
}

QLineEdit:focus, QTextEdit:focus {
    border: 2px solid;
    border-color: #000000 #ffffff #ffffff #000000; /* Darker inset on focus */
}

/* Peer List Items */
QListWidget::item {
    padding: 6px;
    background-color: transparent;
}

QListWidget::item:hover {
    background-color: #dfdfdf;
}

QListWidget::item:selected {
    background-color: #000080; /* Classic Navy Blue */
    color: #ffffff;
}

/* Classic Windows 95 Buttons */
QPushButton {
    background-color: #c0c0c0;
    color: #000000;
    border: 2px solid;
    border-color: #ffffff #808080 #808080 #ffffff; /* Outset bevel */
    padding: 4px 12px;
    min-height: 20px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #d8d8d8;
}

QPushButton:pressed {
    background-color: #b0b0b0;
    border-color: #808080 #ffffff #ffffff #808080; /* Inset bevel when clicked */
    padding-left: 6px;
    padding-top: 6px;
}

QPushButton:disabled {
    color: #808080;
    border-color: #ffffff #808080 #808080 #ffffff;
}

/* Header Titles */
QLabel#chat_header_title {
    font-size: 14px;
    font-weight: bold;
    color: #000080; /* Navy blue title */
}

QLabel#chat_header_subtitle {
    font-size: 11px;
    color: #404040;
}

QLabel#username_label {
    font-size: 13px;
    font-weight: bold;
    color: #000080;
}

/* File Transfer Panels */
QFrame#file_panel {
    background-color: #c0c0c0;
    border: 2px solid;
    border-color: #ffffff #808080 #808080 #ffffff;
    margin: 4px;
    padding: 8px;
}

QProgressBar {
    border: 2px solid;
    border-color: #808080 #ffffff #ffffff #808080;
    text-align: center;
    background-color: #ffffff;
    color: #000000;
    font-weight: bold;
}

QProgressBar::chunk {
    background-color: #000080; /* Dark blue progress bar block */
}
"""
