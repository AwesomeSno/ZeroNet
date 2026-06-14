import os
import time
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
                             QListWidget, QListWidgetItem, QLineEdit, QPushButton, 
                             QLabel, QTextBrowser, QFrame, QFileDialog, QDialog, 
                             QCheckBox, QDialogButtonBox, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSlot

from zeronet.ui.styles import MAIN_STYLE
from zeronet.ui.widgets import PeerListItemWidget, FileTransferWidget

class GroupCreationDialog(QDialog):
    """
    Classic Win95-style dialog to create group chats.
    """
    def __init__(self, peers: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Group Chat")
        self.setMinimumWidth(280)
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Group Name:"))
        self.group_name_input = QLineEdit()
        layout.addWidget(self.group_name_input)
        
        layout.addWidget(QLabel("Select Members:"))
        self.checkboxes = {}
        
        scroll = QListWidget()
        for peer_id, info in peers.items():
            if info.get("status") == "online":
                item = QListWidgetItem()
                cb = QCheckBox(f"{info['name']} ({info['ip']})")
                scroll.addItem(item)
                scroll.setItemWidget(item, cb)
                self.checkboxes[peer_id] = cb
                
        layout.addWidget(scroll)
        
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
        
        self.setWindowTitle("ZeroNet Messenger - [mIRC/ICQ Retro Edition]")
        self.setMinimumSize(780, 520)
        self.setStyleSheet(MAIN_STYLE)
        
        # Local state
        self.current_chat_target = None  # "peer:<peer_id>" or "group:<group_id>"
        
        # chat_histories maps target_key -> list of HTML message strings
        self.chat_histories = {}         
        self.groups = {}                 
        self.active_file_widgets = {}    
        
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)
        
        # --- SIDEBAR FRAME (Win95 Panel) ---
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(6, 6, 6, 6)
        sidebar_layout.setSpacing(6)
        
        # User details profile header
        profile_frame = QFrame()
        profile_frame.setObjectName("profile_frame")
        profile_layout = QVBoxLayout(profile_frame)
        profile_layout.setContentsMargins(0, 0, 0, 6)
        profile_layout.setSpacing(2)
        
        my_name_lbl = QLabel(self.network_manager.username)
        my_name_lbl.setObjectName("username_label")
        my_id_lbl = QLabel(f"ID: {self.network_manager.device_id[:8]}...")
        my_id_lbl.setStyleSheet("font-size: 10px; color: #505050;")
        
        profile_layout.addWidget(my_name_lbl)
        profile_layout.addWidget(my_id_lbl)
        sidebar_layout.addWidget(profile_frame)
        
        # Channels/Peers title label
        sidebar_layout.addWidget(QLabel("Contacts:"))
        
        # Contacts List
        self.peer_list_widget = QListWidget()
        self.peer_list_widget.itemSelectionChanged.connect(self.on_chat_target_selected)
        sidebar_layout.addWidget(self.peer_list_widget)
        
        # New Group Chat button
        new_group_btn = QPushButton("Create Group")
        new_group_btn.clicked.connect(self.on_create_group_clicked)
        sidebar_layout.addWidget(new_group_btn)
        
        main_layout.addWidget(sidebar)
        
        # --- CHAT PANEL FRAME (Win95 Panel) ---
        self.chat_panel = QFrame()
        self.chat_panel.setObjectName("chat_panel_frame")
        self.chat_layout = QVBoxLayout(self.chat_panel)
        self.chat_layout.setContentsMargins(6, 6, 6, 6)
        self.chat_layout.setSpacing(6)
        
        # Header bar
        self.header_frame = QFrame()
        self.header_frame.setObjectName("header_frame")
        self.header_layout = QVBoxLayout(self.header_frame)
        self.header_layout.setContentsMargins(0, 0, 0, 6)
        self.header_layout.setSpacing(2)
        
        self.header_title = QLabel("Select a peer or channel")
        self.header_title.setObjectName("chat_header_title")
        self.header_subtitle = QLabel("Start a conversation on the network")
        self.header_subtitle.setObjectName("chat_header_subtitle")
        
        self.header_layout.addWidget(self.header_title)
        self.header_layout.addWidget(self.header_subtitle)
        self.chat_layout.addWidget(self.header_frame)
        
        # Retro Chat logs (Plain text/HTML browser)
        self.chat_log = QTextBrowser()
        self.chat_log.setOpenExternalLinks(True)
        self.chat_layout.addWidget(self.chat_log)
        
        # File Transfers Panel
        self.transfers_widget = QWidget()
        self.transfers_layout = QVBoxLayout(self.transfers_widget)
        self.transfers_layout.setContentsMargins(0, 0, 0, 0)
        self.transfers_layout.setSpacing(4)
        self.chat_layout.addWidget(self.transfers_widget)
        
        # Message input area footer
        self.input_frame = QWidget()
        self.input_layout = QHBoxLayout(self.input_frame)
        self.input_layout.setContentsMargins(0, 0, 0, 0)
        self.input_layout.setSpacing(6)
        
        self.attach_btn = QPushButton("📎 File")
        self.attach_btn.clicked.connect(self.on_attach_clicked)
        self.input_layout.addWidget(self.attach_btn)
        
        self.msg_input = QLineEdit()
        self.msg_input.setPlaceholderText("Type message...")
        self.msg_input.returnPressed.connect(self.on_send_clicked)
        self.input_layout.addWidget(self.msg_input)
        
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self.on_send_clicked)
        self.input_layout.addWidget(self.send_btn)
        
        self.chat_layout.addWidget(self.input_frame)
        main_layout.addWidget(self.chat_panel)
        
        # Disable inputs at launch
        self.input_frame.setEnabled(False)
        self.chat_log.append("<font color='#000080'>*** Welcome to ZeroNet Messenger!</font>")
        self.chat_log.append("<font color='#000080'>*** Discovered nodes on your network will appear in the sidebar.</font>")

    def connect_signals(self):
        ns = self.network_manager.signals
        ns.peer_discovered_signal.connect(self.on_peer_discovered)
        ns.peer_removed_signal.connect(self.on_peer_removed)
        ns.message_received_signal.connect(self.on_message_received)
        ns.group_message_received_signal.connect(self.on_group_message_received)
        
        ns.file_offer_received_signal.connect(self.on_file_offer_received)
        ns.file_offer_accepted_signal.connect(self.on_file_offer_accepted)
        ns.file_offer_rejected_signal.connect(self.on_file_offer_rejected)
        ns.file_progress_signal.connect(self.on_file_progress)
        ns.file_completed_signal.connect(self.on_file_completed)
        ns.file_failed_signal.connect(self.on_file_failed)

    # --- UI EVENTS & SLOTS ---
    
    @pyqtSlot(str, str, str, int)
    def on_peer_discovered(self, peer_id: str, name: str, ip: str, port: int):
        self.refresh_list()

    @pyqtSlot(str)
    def on_peer_removed(self, peer_id: str):
        self.refresh_list()

    def refresh_list(self):
        selected_key = None
        selected_items = self.peer_list_widget.selectedItems()
        if selected_items:
            selected_key = selected_items[0].data(Qt.ItemDataRole.UserRole)
            
        self.peer_list_widget.clear()
        
        # Add Groups
        for gid, ginfo in self.groups.items():
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, f"group:{gid}")
            
            widget = PeerListItemWidget(f"👥 {ginfo['name']}", "Group Chat", len(ginfo['members']), "online")
            item.setSizeHint(widget.sizeHint())
            
            self.peer_list_widget.addItem(item)
            self.peer_list_widget.setItemWidget(item, widget)
            
            if selected_key == f"group:{gid}":
                item.setSelected(True)
                
        # Add Peers
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
                    self.header_subtitle.setText("Active | Secure E2EE Session")
                    self.input_frame.setEnabled(True)
                else:
                    self.header_subtitle.setText("Offline")
                    self.input_frame.setEnabled(False)
                    
        elif key.startswith("group:"):
            group_id = key.split(":")[1]
            ginfo = self.groups.get(group_id)
            if ginfo:
                self.header_title.setText(f"Group: {ginfo['name']}")
                self.header_subtitle.setText(f"{len(ginfo['members'])} members | Mesh Encrypted")
                self.input_frame.setEnabled(True)
                
        self.redraw_chat_history()

    def redraw_chat_history(self):
        self.chat_log.clear()
        target = self.current_chat_target
        if not target or target not in self.chat_histories:
            return
            
        for html_line in self.chat_histories[target]:
            self.chat_log.append(html_line)

    def append_and_send(self, sender: str, text: str, is_me: bool, target: str):
        time_str = time.strftime("%H:%M:%S")
        
        # Color codes: Red for you, blue for them, dark gray for timestamps
        timestamp_html = f"<font color='#505050'>[{time_str}]</font>"
        
        if is_me:
            msg_html = f"{timestamp_html} <b>&lt;<font color='#800000'>{sender}</font>&gt;</b> {text}"
        else:
            msg_html = f"{timestamp_html} <b>&lt;<font color='#000080'>{sender}</font>&gt;</b> {text}"
            
        if target not in self.chat_histories:
            self.chat_histories[target] = []
            
        self.chat_histories[target].append(msg_html)
        
        if self.current_chat_target == target:
            self.chat_log.append(msg_html)

    def on_send_clicked(self):
        text = self.msg_input.text().strip()
        if not text or not self.current_chat_target:
            return
            
        self.msg_input.clear()
        target = self.current_chat_target
        
        # Append locally
        self.append_and_send("Me", text, is_me=True, target=target)
        
        # Send
        if target.startswith("peer:"):
            peer_id = target.split(":")[1]
            try:
                self.network_manager.send_direct_message(peer_id, text)
            except Exception as e:
                QMessageBox.critical(self, "Send Error", f"Failed to send: {e}")
                
        elif target.startswith("group:"):
            group_id = target.split(":")[1]
            ginfo = self.groups.get(group_id)
            if ginfo:
                self.network_manager.send_group_message(group_id, ginfo["name"], ginfo["members"], text)

    def on_create_group_clicked(self):
        dialog = GroupCreationDialog(self.network_manager.peers, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            gname, members = dialog.get_data()
            if not gname or not members:
                return
                
            members.append(self.network_manager.device_id)
            group_id = f"grp_{int(time.time())}"
            self.groups[group_id] = {
                "name": gname,
                "members": members
            }
            
            self.refresh_list()
            
            # Auto-select new group
            for i in range(self.peer_list_widget.count()):
                item = self.peer_list_widget.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == f"group:{group_id}":
                    item.setSelected(True)
                    break

    def on_attach_clicked(self):
        if not self.current_chat_target or not self.current_chat_target.startswith("peer:"):
            return
            
        peer_id = self.current_chat_target.split(":")[1]
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Share")
        if not file_path:
            return
            
        try:
            transfer_id = self.network_manager.offer_file(peer_id, file_path)
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            w = FileTransferWidget(transfer_id, file_name, file_size, is_incoming=False, parent=self)
            self.active_file_widgets[transfer_id] = w
            self.transfers_layout.addWidget(w)
        except Exception as e:
            QMessageBox.critical(self, "File Error", f"Failed to start file transfer: {e}")

    # --- INCOMING SIGNALS ---

    @pyqtSlot(str, str, str, float)
    def on_message_received(self, peer_id: str, peer_name: str, text: str, timestamp: float):
        self.append_and_send(peer_name, text, is_me=False, target=f"peer:{peer_id}")

    @pyqtSlot(str, str, str, str, str, float)
    def on_group_message_received(self, peer_id: str, peer_name: str, group_id: str, group_name: str, text: str, timestamp: float):
        target = f"group:{group_id}"
        if group_id not in self.groups:
            self.groups[group_id] = {
                "name": group_name,
                "members": [peer_id, self.network_manager.device_id]
            }
            self.refresh_list()
            
        self.append_and_send(peer_name, text, is_me=False, target=target)

    @pyqtSlot(str, str, str, int, str)
    def on_file_offer_received(self, peer_id: str, peer_name: str, file_name: str, file_size: int, transfer_id: str):
        self.network_manager.file_transfers[transfer_id] = {
            "role": "receiver",
            "peer_id": peer_id,
            "file_name": file_name,
            "file_size": file_size,
            "status": "offered"
        }
        
        w = FileTransferWidget(transfer_id, file_name, file_size, is_incoming=True, parent=self)
        self.active_file_widgets[transfer_id] = w
        self.transfers_layout.addWidget(w)
        
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
            w.update_progress(w.file_size)
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(3000, w.deleteLater)

    @pyqtSlot(str, str)
    def on_file_failed(self, transfer_id: str, error_msg: str):
        w = self.active_file_widgets.get(transfer_id)
        if w:
            w.set_failed(error_msg)
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(6000, w.deleteLater)

    def closeEvent(self, event):
        self.discovery_service.stop()
        self.network_manager.stop()
        event.accept()
