from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
                             QFrame, QProgressBar, QPushButton)
from PyQt6.QtCore import Qt, QSize
import time

class ChatBubble(QWidget):
    """
    A custom chat bubble widget that formats and displays messages.
    Supports left (received) or right (sent) alignment with distinct colors.
    """
    def __init__(self, sender_name: str, text: str, timestamp: float, is_sent: bool, parent=None):
        super().__init__(parent)
        self.is_sent = is_sent
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 5)
        
        # Outer container frame for styling
        self.bubble_frame = QFrame()
        self.bubble_frame.setObjectName("bubble_frame")
        
        # Bubble styling based on sent/received
        if is_sent:
            # Sent message style (neon blue/sky gradient fallback)
            self.bubble_frame.setStyleSheet("""
                QFrame#bubble_frame {
                    background-color: #0284c7;
                    border-radius: 12px;
                    border-bottom-right-radius: 2px;
                }
            """)
            main_layout.addStretch()
            main_layout.addWidget(self.bubble_frame)
        else:
            # Received message style (dark slate)
            self.bubble_frame.setStyleSheet("""
                QFrame#bubble_frame {
                    background-color: #334155;
                    border-radius: 12px;
                    border-bottom-left-radius: 2px;
                }
            """)
            main_layout.addWidget(self.bubble_frame)
            main_layout.addStretch()
            
        bubble_layout = QVBoxLayout(self.bubble_frame)
        bubble_layout.setContentsMargins(12, 8, 12, 8)
        bubble_layout.setSpacing(4)
        
        # Sender Name (for groups/received messages)
        self.name_label = QLabel(sender_name)
        self.name_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #38bdf8;")
        if is_sent:
            self.name_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #7dd3fc;")
            
        # Message Text
        self.text_label = QLabel(text)
        self.text_label.setWordWrap(True)
        self.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.text_label.setStyleSheet("color: #ffffff; font-size: 13px; background-color: transparent;")
        
        # Timestamp
        time_struct = time.localtime(timestamp)
        time_str = time.strftime("%H:%M", time_struct)
        self.time_label = QLabel(time_str)
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.time_label.setStyleSheet("font-size: 9px; color: #cbd5e1; background-color: transparent;")
        
        bubble_layout.addWidget(self.name_label)
        bubble_layout.addWidget(self.text_label)
        bubble_layout.addWidget(self.time_label)


class PeerListItemWidget(QWidget):
    """
    A beautiful peer row widget containing:
    - Status indicator (green dot for online, gray for offline)
    - Username
    - Subtitle showing IP:Port
    """
    def __init__(self, name: str, ip: str, port: int, status: str = "online", parent=None):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)
        
        # Status Dot
        self.status_dot = QFrame()
        self.status_dot.setFixedSize(QSize(10, 10))
        self.status_dot.setObjectName("status_dot")
        self.set_status(status)
        
        # Text details
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet("font-weight: 600; font-size: 13px; color: #f1f5f9; background: transparent;")
        
        self.ip_label = QLabel(f"{ip}:{port}")
        self.ip_label.setStyleSheet("font-size: 10px; color: #64748b; background: transparent;")
        
        text_layout.addWidget(self.name_label)
        text_layout.addWidget(self.ip_label)
        
        layout.addWidget(self.status_dot)
        layout.addLayout(text_layout)
        layout.addStretch()

    def set_status(self, status: str):
        if status == "online":
            self.status_dot.setStyleSheet("background-color: #10b981; border-radius: 5px;")
        else:
            self.status_dot.setStyleSheet("background-color: #64748b; border-radius: 5px;")


class FileTransferWidget(QFrame):
    """
    Displays active file upload/download state, progress, and actions (e.g. Accept/Reject).
    """
    def __init__(self, transfer_id: str, file_name: str, file_size: int, is_incoming: bool, parent=None):
        super().__init__(parent)
        self.transfer_id = transfer_id
        self.file_name = file_name
        self.file_size = file_size
        self.is_incoming = is_incoming
        
        self.setObjectName("file_panel")
        self.setStyleSheet("""
            QFrame#file_panel {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        
        # File Title
        direction = "Downloading" if is_incoming else "Uploading"
        size_mb = file_size / (1024 * 1024)
        self.title_label = QLabel(f"<b>{direction}:</b> {file_name} ({size_mb:.2f} MB)")
        self.title_label.setStyleSheet("color: #38bdf8;")
        layout.addWidget(self.title_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Accept/Reject Action row (Only visible for incoming transfers in "offered" state)
        self.actions_widget = QWidget()
        actions_layout = QHBoxLayout(self.actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)
        
        self.accept_btn = QPushButton("Accept")
        self.accept_btn.setStyleSheet("background-color: #0d9488;")
        self.reject_btn = QPushButton("Reject")
        self.reject_btn.setStyleSheet("background-color: #e11d48;")
        
        actions_layout.addWidget(self.accept_btn)
        actions_layout.addWidget(self.reject_btn)
        
        layout.addWidget(self.actions_widget)
        
        if not is_incoming:
            self.actions_widget.hide()

    def update_progress(self, bytes_transferred: int):
        pct = int((bytes_transferred / self.file_size) * 100) if self.file_size > 0 else 100
        self.progress_bar.setValue(pct)
        if pct >= 100:
            self.title_label.setText(f"<b>Completed:</b> {self.file_name}")
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #10b981; }")
            self.actions_widget.hide()

    def set_failed(self, error_msg: str):
        self.title_label.setText(f"<b>Failed:</b> {self.file_name}")
        self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #ef4444; }")
        self.actions_widget.hide()
        
        error_label = QLabel(f"Error: {error_msg}")
        error_label.setStyleSheet("color: #ef4444; font-size: 11px;")
        self.layout().addWidget(error_label)
