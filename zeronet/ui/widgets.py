from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
                             QFrame, QProgressBar, QPushButton)
from PyQt6.QtCore import Qt, QSize

class PeerListItemWidget(QWidget):
    """
    Retro ICQ-style peer row widget.
    Shows status as [+] or [-] with monospaced text.
    """
    def __init__(self, name: str, ip: str, port: int, status: str = "online", parent=None):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)
        
        # Status text prefix
        self.status_lbl = QLabel()
        self.status_lbl.setStyleSheet("font-weight: bold; background: transparent;")
        self.set_status(status)
        
        # Text details
        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)
        
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet("font-weight: bold; background: transparent;")
        
        self.ip_label = QLabel(f"{ip}:{port}")
        self.ip_label.setStyleSheet("font-size: 10px; color: #505050; background: transparent;")
        
        text_layout.addWidget(self.name_label)
        text_layout.addWidget(self.ip_label)
        
        layout.addWidget(self.status_lbl)
        layout.addLayout(text_layout)
        layout.addStretch()

    def set_status(self, status: str):
        if status == "online":
            self.status_lbl.setText("[+]")
            self.status_lbl.setStyleSheet("color: #008000; font-weight: bold; background: transparent;")
        else:
            self.status_lbl.setText("[-]")
            self.status_lbl.setStyleSheet("color: #808080; font-weight: bold; background: transparent;")


class FileTransferWidget(QFrame):
    """
    Classic Win95-style file transfer box.
    """
    def __init__(self, transfer_id: str, file_name: str, file_size: int, is_incoming: bool, parent=None):
        super().__init__(parent)
        self.transfer_id = transfer_id
        self.file_name = file_name
        self.file_size = file_size
        self.is_incoming = is_incoming
        
        self.setObjectName("file_panel")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        direction = "Incoming" if is_incoming else "Outgoing"
        size_mb = file_size / (1024 * 1024)
        self.title_label = QLabel(f"<b>{direction} File:</b> {file_name} ({size_mb:.2f} MB)")
        layout.addWidget(self.title_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Accept/Reject Action row
        self.actions_widget = QWidget()
        actions_layout = QHBoxLayout(self.actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(6)
        
        self.accept_btn = QPushButton("Accept")
        self.reject_btn = QPushButton("Reject")
        
        actions_layout.addWidget(self.accept_btn)
        actions_layout.addWidget(self.reject_btn)
        
        layout.addWidget(self.actions_widget)
        
        if not is_incoming:
            self.actions_widget.hide()

    def update_progress(self, bytes_transferred: int):
        pct = int((bytes_transferred / self.file_size) * 100) if self.file_size > 0 else 100
        self.progress_bar.setValue(pct)
        if pct >= 100:
            self.title_label.setText(f"Finished: {self.file_name}")
            self.actions_widget.hide()

    def set_failed(self, error_msg: str):
        self.title_label.setText(f"Failed: {self.file_name}")
        self.actions_widget.hide()
        
        error_label = QLabel(f"Error: {error_msg}")
        error_label.setStyleSheet("color: #800000; font-size: 10px;")
        self.layout().addWidget(error_label)
