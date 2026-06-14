# PyQt6 stylesheet for ZeroNet
# Implements a premium, modern dark mode with neon cyan accents,
# glassmorphic card stylings, and clean rounded components.

MAIN_STYLE = """
/* General Application Styles */
QWidget {
    background-color: #0f172a;
    color: #f8fafc;
    font-family: 'Segoe UI', -apple-system, Roboto, Helvetica, sans-serif;
    font-size: 13px;
}

/* Sidebar Styling */
QFrame#sidebar {
    background-color: #1e293b;
    border-right: 1px solid #334155;
}

/* Sidebar List Widget */
QListWidget {
    background-color: transparent;
    border: none;
    outline: 0;
}

QListWidget::item {
    padding: 12px;
    border-radius: 8px;
    margin: 4px 8px;
    background-color: #33415533;
    color: #cbd5e1;
}

QListWidget::item:hover {
    background-color: #33415588;
    color: #f8fafc;
}

QListWidget::item:selected {
    background-color: #0284c7;
    color: #ffffff;
    font-weight: bold;
}

/* Chat Input Pane */
QFrame#chat_input_frame {
    background-color: #1e293b;
    border-top: 1px solid #334155;
    padding: 8px;
}

QTextEdit#message_input {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f8fafc;
}

QTextEdit#message_input:focus {
    border: 1px solid #38bdf8;
}

/* Scroll Area for Messages */
QScrollArea {
    border: none;
    background-color: #0f172a;
}

QScrollArea > QWidget > QWidget {
    background-color: #0f172a;
}

/* Standard Buttons */
QPushButton {
    background-color: #0284c7;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #0ea5e9;
}

QPushButton:pressed {
    background-color: #0369a1;
}

QPushButton:disabled {
    background-color: #1e293b;
    color: #64748b;
    border: 1px solid #334155;
}

/* Accent Button */
QPushButton#action_button {
    background-color: #0d9488;
}

QPushButton#action_button:hover {
    background-color: #14b8a6;
}

QPushButton#action_button:pressed {
    background-color: #0f766e;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #0f172a;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Headers and Labels */
QLabel#chat_header_title {
    font-size: 16px;
    font-weight: bold;
    color: #f8fafc;
}

QLabel#chat_header_subtitle {
    font-size: 11px;
    color: #94a3b8;
}

QLabel#username_label {
    font-size: 14px;
    font-weight: bold;
    color: #38bdf8;
}

/* File Transfer Info Panel */
QFrame#file_panel {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    margin: 8px;
    padding: 12px;
}

QProgressBar {
    border: 1px solid #334155;
    border-radius: 4px;
    text-align: center;
    background-color: #0f172a;
    color: #ffffff;
    font-weight: bold;
}

QProgressBar::chunk {
    background-color: #0d9488;
    border-radius: 3px;
}
"""
