import os
import time
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
                             QListWidget, QListWidgetItem, QLineEdit, QPushButton, 
                             QLabel, QScrollArea, QFrame, QFileDialog, QDialog, 
                             QCheckBox, QVBoxLayout, QDialogButtonBox, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSlot, QSize

from zeronet.ui.styles import MAIN_STYLE
from zeronet.ui.widgets import ChatBubble, PeerListItemWidget, FileTransferWidget

class GroupCreationDialog(QDialog):
    """
    Dialog allowing the user to select online peers to create a group chat.
    """
    def __init__(self, peers: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Group Chat")
        self.setMinimumWidth(300)
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("<b>Group Name:</b>"))
        self.group_name_input = QLineEdit()
        self.group_name_input.setPlaceholderName = "name"
        self.group_name_input.setPlaceholderText("Enter group name...")
        layout.addWidget(self.group_name_input)
        
        layout.addWidget(QLabel("<b>Select Members:</b>"))
        self.checkboxes = {}
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        for peer_id, info in peers.items():
            if info.get("status") == "online":
                cb = QCheckBox(f"{info['name']} ({info['ip']})")
                scroll_layout.addWidget(cb)
                self.checkboxes[peer_id] = cb
                
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Action Buttons
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal, self
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def get_data(self) -> tuple[str, list[str]]:
        group_name = self.group_name_input.text().strip()
        selected_members = [peer_id for peer_id, cb in self.checkboxes.items() if cb.isChecked()]
        return group_name, selected_members


class MainWindow(QMainWindow):
    def __init__(self, network_manager, discovery_service):
        super().__init__()
        self.network_manager = network_manager
        self.discovery_service = discovery_service
        
        self.setWindowTitle("ZeroNet Secure LAN Messenger")
        self.setMinimumSize(850, 600)
        self.setStyleSheet(MAIN_STYLE)
        
        # Local state
        self.current_chat_target = None  # Formatted as "peer:<peer_id>" or "group:<group_id>"
        self.chat_histories = {}         # key -> list of bubble data dicts
        self.groups = {}                 # group_id -> { "name": name, "members": [...] }
        self.active_file_widgets = {}    # transfer_id -> FileTransferWidget
        
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        # Main layout splitter
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- LEFT SIDEBAR PANEL ---
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(260)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        
        # User details profile header
        profile_frame = QFrame()
        profile_frame.setStyleSheet("background-color: #1e293b; border-bottom: 1px solid #334155; padding: 12px;")
        profile_layout = QVBoxLayout(profile_frame)
        profile_layout.setSpacing(4)
        
        my_name_lbl = QLabel(self.network_manager.username)
        my_name_lbl.setObjectName("username_label")
        my_id_lbl = QLabel(f"Device ID: {self.network_manager.device_id[:8]}...")
        my_id_lbl.setStyleSheet("font-size: 11px; color: #94a3b8;")
        
        profile_layout.addWidget(my_name_lbl)
        profile_layout.addWidget(my_id_lbl)
        sidebar_layout.addWidget(profile_frame)
        
        # Section title: Channels
        title_lbl = QLabel("CHANNELS & PEERS")
        title_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #64748b; margin: 15px 12px 5px 12px;")
        sidebar_layout.addWidget(title_lbl)
        
        # Channels/Peers QListWidget
        self.peer_list_widget = QListWidget()
        self.peer_list_widget.itemSelectionChanged.connect(self.on_chat_target_selected)
        sidebar_layout.addWidget(self.peer_list_widget)
        
        # Action Buttons footer
        action_footer = QFrame()
        action_footer.setStyleSheet("background-color: #1e293b; border-top: 1px solid #334155; padding: 10px;")
        action_layout = QVBoxLayout(action_footer)
        
        new_group_btn = QPushButton("Create Group Chat")
        new_group_btn.setObjectName("action_button")
        new_group_btn.clicked.connect(self.on_create_group_clicked)
        action_layout.addWidget(new_group_btn)
        
        sidebar_layout.addWidget(action_footer)
        main_layout.addWidget(sidebar)
        
        # --- RIGHT CHAT PANEL ---
        self.chat_panel = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_panel)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(0)
        
        # Header bar
        self.header_frame = QFrame()
        self.header_frame.setStyleSheet("background-color: #1e293b; border-bottom: 1px solid #334155; padding: 12px;")
        self.header_layout = QVBoxLayout(self.header_frame)
        self.header_layout.setSpacing(2)
        
        self.header_title = QLabel("Select a peer or channel")
        self.header_title.setObjectName("chat_header_title")
        self.header_subtitle = QLabel("Start a conversation on the network")
        self.header_subtitle.setObjectName("chat_header_subtitle")
        
        self.header_layout.addWidget(self.header_title)
        self.header_layout.addWidget(self.header_subtitle)
        self.chat_layout.addWidget(self.header_frame)
        
        # Chat history scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        self.history_widget = QWidget()
        self.history_layout = QVBoxLayout(self.history_widget)
        self.history_layout.addStretch()
        self.scroll_area.setWidget(self.history_widget)
        
        self.chat_layout.addWidget(self.scroll_area)
        
        # File Transfers Panel (Collapsible / hidden by default)
        self.transfers_widget = QWidget()
        self.transfers_layout = QVBoxLayout(self.transfers_widget)
        self.transfers_layout.setContentsMargins(10, 0, 10, 0)
        self.chat_layout.addWidget(self.transfers_widget)
        
        # Message input area footer
        self.input_frame = QFrame()
        self.input_frame.setObjectName("chat_input_frame")
        self.input_layout = QHBoxLayout(self.input_frame)
        self.input_layout.setContentsMargins(10, 10, 10, 10)
        
        self.attach_btn = QPushButton("📎 File")
        self.attach_btn.setFixedWidth(70)
        self.attach_btn.clicked.connect(self.on_attach_clicked)
        self.input_layout.addWidget(self.attach_btn)
        
        self.msg_input = QLineEdit()
        self.msg_input.setPlaceholderText("Type a secure message...")
        self.msg_input.returnPressed.connect(self.on_send_clicked)
        self.input_layout.addWidget(self.msg_input)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.on_send_clicked)
        self.input_layout.addWidget(self.send_btn)
        
        self.chat_layout.addWidget(self.input_frame)
        main_layout.addWidget(self.chat_panel)
        
        # Initially disable inputs
        self.input_frame.setEnabled(False)

    def connect_signals(self):
        # Network manager signals connection
        ns = self.network_manager.signals
        ns.peer_discovered_signal.connect(self.on_peer_discovered)
        ns.peer_removed_signal.connect(self.on_peer_removed)
        ns.message_received_signal.connect(self.on_message_received)
        ns.group_message_received_signal.connect(self.on_group_message_received)
        
        # File transfer signals
        ns.file_offer_received_signal.connect(self.on_file_offer_received)
        ns.file_offer_accepted_signal.connect(self.on_file_offer_accepted)
        ns.file_offer_rejected_signal.connect(self.on_file_offer_rejected)
        ns.file_progress_signal.connect(self.on_file_progress)
        ns.file_completed_signal.connect(self.on_file_completed)
        ns.file_failed_signal.connect(self.on_file_failed)

    # --- UI EVENTS & SLOTS ---
    
    @pyqtSlot(str, str, str, int)
    def on_peer_discovered(self, peer_id: str, name: str, ip: str, port: int):
        # Re-populate peer list preserving selection
        self.refresh_list()

    @pyqtSlot(str)
    def on_peer_removed(self, peer_id: str):
        self.refresh_list()

    def refresh_list(self):
        """
        Redraws items inside the peer list widget.
        """
        # Save currently selected key
        selected_key = None
        selected_items = self.peer_list_widget.selectedItems()
        if selected_items:
            selected_key = selected_items[0].data(Qt.ItemDataRole.UserRole)
            
        self.peer_list_widget.clear()
        
        # Add Groups first
        for gid, ginfo in self.groups.items():
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, f"group:{gid}")
            
            # Simple widget for group displaying list of members count
            widget = PeerListItemWidget(f"👥 {ginfo['name']}", "Group Chat", len(ginfo['members']), "online")
            item.setSizeHint(widget.sizeHint())
            
            self.peer_list_widget.addItem(item)
            self.peer_list_widget.setItemWidget(item, widget)
            
            if selected_key == f"group:{gid}":
                item.setSelected(True)
                
        # Add discovered individual peers
        for pid, pinfo in self.network_manager.peers.items():
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, f"peer:{pid}")
            
            widget = PeerListItemWidget(pinfo["name"], pinfo["ip"], pinfo["port"], pinfo["status"])
            item.setSizeHint(widget.sizeHint())
            
            self.peer_list_widget.addItem(item)
            self.peer_list_widget.setItemWidget(item, widget)
            
            if selected_key == f"peer:{pid}":
                item.setSelected(True)

    def on_chat_target_selected(self):
        selected_items = self.peer_list_widget.selectedItems()
        if not selected_items:
            self.current_chat_target = None
            self.input_frame.setEnabled(False)
            self.header_title.setText("Select a peer or channel")
            self.header_subtitle.setText("Start a conversation on the network")
            return
            
        key = selected_items[0].data(Qt.ItemDataRole.UserRole)
        self.current_chat_target = key
        self.input_frame.setEnabled(True)
        
        if key.startswith("peer:"):
            peer_id = key.split(":")[1]
            pinfo = self.network_manager.peers.get(peer_id)
            if pinfo:
                self.header_title.setText(pinfo["name"])
                if pinfo["status"] == "online":
                    self.header_subtitle.setText("🟢 Online | 🔒 End-to-End Encrypted (ECDH + Fernet)")
                    self.input_frame.setEnabled(True)
                else:
                    self.header_subtitle.setText("🔴 Offline")
                    self.input_frame.setEnabled(False)
                    
        elif key.startswith("group:"):
            group_id = key.split(":")[1]
            ginfo = self.groups.get(group_id)
            if ginfo:
                self.header_title.setText(f"👥 {ginfo['name']}")
                self.header_subtitle.setText(f"{len(ginfo['members'])} members | Mesh E2EE (Fernet)")
                self.input_frame.setEnabled(True)
                
        # Redraw chat bubbles for selected target
        self.redraw_chat_history()

    def redraw_chat_history(self):
        # Clear current history layout (except stretch spacer at start)
        for i in reversed(range(self.history_layout.count())):
            item = self.history_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
                
        # Get history list for target
        target = self.current_chat_target
        if not target or target not in self.chat_histories:
            return
            
        for msg in self.chat_histories[target]:
            bubble = ChatBubble(msg["sender_name"], msg["text"], msg["timestamp"], msg["is_sent"])
            self.history_layout.addWidget(bubble)
            
        # Scroll to bottom
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def on_send_clicked(self):
        text = self.msg_input.text().strip()
        if not text or not self.current_chat_target:
            return
            
        self.msg_input.clear()
        target = self.current_chat_target
        timestamp = time.time()
        
        # Append locally to history
        if target not in self.chat_histories:
            self.chat_histories[target] = []
            
        self.chat_histories[target].append({
            "sender_name": "Me",
            "text": text,
            "timestamp": timestamp,
            "is_sent": True
        })
        
        # Redraw bubble
        bubble = ChatBubble("Me", text, timestamp, is_sent=True)
        self.history_layout.addWidget(bubble)
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())
        
        # Send via network
        if target.startswith("peer:"):
            peer_id = target.split(":")[1]
            try:
                self.network_manager.send_direct_message(peer_id, text)
            except Exception as e:
                QMessageBox.critical(self, "Send Error", f"Failed to send message: {e}")
                
        elif target.startswith("group:"):
            group_id = target.split(":")[1]
            ginfo = self.groups.get(group_id)
            if ginfo:
                # Send to all members in mesh
                self.network_manager.send_group_message(group_id, ginfo["name"], ginfo["members"], text)

    def on_create_group_clicked(self):
        dialog = GroupCreationDialog(self.network_manager.peers, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            gname, members = dialog.get_data()
            if not gname:
                QMessageBox.warning(self, "Invalid Group", "Group name cannot be empty")
                return
            if not members:
                QMessageBox.warning(self, "Invalid Group", "Select at least 1 online peer")
                return
                
            # Add self as member
            members.append(self.network_manager.device_id)
            
            # Create group locally
            group_id = f"grp_{int(time.time())}"
            self.groups[group_id] = {
                "name": gname,
                "members": members
            }
            
            # Select group
            self.refresh_list()
            
            # Select the newly created group item
            for i in range(self.peer_list_widget.count()):
                item = self.peer_list_widget.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == f"group:{group_id}":
                    item.setSelected(True)
                    break

    def on_attach_clicked(self):
        if not self.current_chat_target or not self.current_chat_target.startswith("peer:"):
            QMessageBox.warning(self, "File Sharing", "File sharing is only supported in direct messages currently.")
            return
            
        peer_id = self.current_chat_target.split(":")[1]
        
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Share")
        if not file_path:
            return
            
        try:
            transfer_id = self.network_manager.offer_file(peer_id, file_path)
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            # Create progress panel
            w = FileTransferWidget(transfer_id, file_name, file_size, is_incoming=False, parent=self)
            self.active_file_widgets[transfer_id] = w
            self.transfers_layout.addWidget(w)
        except Exception as e:
            QMessageBox.critical(self, "File Error", f"Failed to start file transfer: {e}")

    # --- INCOMING NETWORK SIGNAL HANDLING ---

    @pyqtSlot(str, str, str, float)
    def on_message_received(self, peer_id: str, peer_name: str, text: str, timestamp: float):
        target = f"peer:{peer_id}"
        if target not in self.chat_histories:
            self.chat_histories[target] = []
            
        self.chat_histories[target].append({
            "sender_name": peer_name,
            "text": text,
            "timestamp": timestamp,
            "is_sent": False
        })
        
        if self.current_chat_target == target:
            bubble = ChatBubble(peer_name, text, timestamp, is_sent=False)
            self.history_layout.addWidget(bubble)
            self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    @pyqtSlot(str, str, str, str, str, float)
    def on_group_message_received(self, peer_id: str, peer_name: str, group_id: str, group_name: str, text: str, timestamp: float):
        # Auto-create group locally if not exists
        target = f"group:{group_id}"
        if group_id not in self.groups:
            # We don't have members list initially, so dynamically discover or list them
            # For simplicity, add peer_id and ourselves
            self.groups[group_id] = {
                "name": group_name,
                "members": [peer_id, self.network_manager.device_id]
            }
            self.refresh_list()
            
        if target not in self.chat_histories:
            self.chat_histories[target] = []
            
        self.chat_histories[target].append({
            "sender_name": peer_name,
            "text": text,
            "timestamp": timestamp,
            "is_sent": False
        })
        
        if self.current_chat_target == target:
            bubble = ChatBubble(peer_name, text, timestamp, is_sent=False)
            self.history_layout.addWidget(bubble)
            self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    @pyqtSlot(str, str, str, int, str)
    def on_file_offer_received(self, peer_id: str, peer_name: str, file_name: str, file_size: int, transfer_id: str):
        # Save transfer metadata locally
        self.network_manager.file_transfers[transfer_id] = {
            "role": "receiver",
            "peer_id": peer_id,
            "file_name": file_name,
            "file_size": file_size,
            "status": "offered"
        }
        
        # Display the file transfer panel widget
        w = FileTransferWidget(transfer_id, file_name, file_size, is_incoming=True, parent=self)
        self.active_file_widgets[transfer_id] = w
        self.transfers_layout.addWidget(w)
        
        # Connect Accept/Reject button clicks
        w.accept_btn.clicked.connect(lambda: self.on_accept_file_transfer(peer_id, transfer_id))
        w.reject_btn.clicked.connect(lambda: self.on_reject_file_transfer(peer_id, transfer_id))

    def on_accept_file_transfer(self, peer_id: str, transfer_id: str):
        w = self.active_file_widgets.get(transfer_id)
        if not w:
            return
            
        save_path, _ = QFileDialog.getSaveFileName(self, "Save File", w.file_name)
        if not save_path:
            return
            
        self.network_manager.accept_file(peer_id, transfer_id, save_path)
        w.accept_btn.setEnabled(False)
        w.reject_btn.setEnabled(False)

    def on_reject_file_transfer(self, peer_id: str, transfer_id: str):
        w = self.active_file_widgets.get(transfer_id)
        if w:
            w.deleteLater()
            del self.active_file_widgets[transfer_id]
        self.network_manager.reject_file(peer_id, transfer_id)

    @pyqtSlot(str, str, int)
    def on_file_offer_accepted(self, peer_id: str, transfer_id: str, file_port: int):
        # Start file streaming upload
        self.network_manager.start_file_upload(peer_id, transfer_id, file_port)

    @pyqtSlot(str, str)
    def on_file_offer_rejected(self, peer_id: str, transfer_id: str):
        w = self.active_file_widgets.get(transfer_id)
        if w:
            w.set_failed("Rejected by receiver")

    @pyqtSlot(str, int, int)
    def on_file_progress(self, transfer_id: str, bytes_transferred: int, bytes_total: int):
        w = self.active_file_widgets.get(transfer_id)
        if w:
            w.update_progress(bytes_transferred)

    @pyqtSlot(str, str)
    def on_file_completed(self, transfer_id: str, file_path: str):
        w = self.active_file_widgets.get(transfer_id)
        if w:
            # Let it sit for 3 seconds, then delete widget
            w.update_progress(w.file_size)
            # Remove from list after a short delay
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(4000, w.deleteLater)

    @pyqtSlot(str, str)
    def on_file_failed(self, transfer_id: str, error_msg: str):
        w = self.active_file_widgets.get(transfer_id)
        if w:
            w.set_failed(error_msg)
            # Delete after 8 seconds
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(8000, w.deleteLater)

    def closeEvent(self, event):
        """
        Stops networking threads on window close.
        """
        self.discovery_service.stop()
        self.network_manager.stop()
        event.accept()
