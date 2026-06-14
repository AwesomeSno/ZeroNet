import os
import time
import argparse
import socket
import uuid
import sys

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, ListItem, Label, Input, RichLog
from textual.containers import Container, Horizontal, Vertical
from textual.binding import Binding

from zeronet.network.connection import NetworkManager
from zeronet.network.discovery import DiscoveryService

# Textual App CSS for a beautiful, retro 90s terminal layout
CSS = """
Screen {
    background: #008080; /* Teal desktop background */
    align: center middle;
}

#main-container {
    width: 95%;
    height: 95%;
    background: #c0c0c0; /* Gray retro surface */
    border: double #ffffff;
    color: #000000;
}

#sidebar {
    width: 30%;
    height: 100%;
    border-right: double #808080;
    background: #c0c0c0;
    padding: 1;
}

#profile-info {
    height: auto;
    border-bottom: solid #808080;
    padding-bottom: 1;
    margin-bottom: 1;
    color: #000080;
    text-style: bold;
}

#contacts-title {
    color: #000000;
    text-style: bold;
    margin-bottom: 1;
}

#contacts-list {
    background: #ffffff;
    border: tall #808080;
    height: 70%;
    color: #000000;
}

#contacts-list ListItem {
    color: #000000;
    padding: 0 1;
}

#contacts-list ListItem:hover {
    background: #dfdfdf;
}

#contacts-list ListItem.-selected {
    background: #000080;
    color: #ffffff;
}

#chat-panel {
    width: 70%;
    height: 100%;
    background: #c0c0c0;
    padding: 1;
}

#chat-header {
    height: auto;
    border-bottom: solid #808080;
    padding-bottom: 1;
    margin-bottom: 1;
}

#chat-title {
    color: #000080;
    text-style: bold;
}

#chat-subtitle {
    color: #404040;
    font-size: 10;
}

#chat-log {
    background: #ffffff;
    border: tall #808080;
    height: 75%;
}

#chat-input-bar {
    layout: horizontal;
    height: auto;
    margin-top: 1;
}

#message-input {
    background: #ffffff;
    border: tall #808080;
    color: #000000;
    width: 100%;
}
"""

class ZeroNetTUI(App):
    CSS = CSS
    
    BINDINGS = [
        Binding("q", "quit", "Quit app", show=True),
        Binding("c", "create_group_shortcut", "Group Help", show=True)
    ]

    def __init__(self, username: str, port: int):
        super().__init__()
        self.username = username
        self.port = port
        
        # Generate unique ID
        self.device_id = f"tui_{uuid.uuid4().hex[:12]}_{username.replace(' ', '_')}"
        
        # Initialize networking
        self.network_manager = NetworkManager(username, self.device_id, default_port=port)
        self.discovery_service = DiscoveryService(self.network_manager)
        
        # Local state
        self.current_chat_target = None  # "peer:<peer_id>" or "group:<group_id>"
        self.chat_histories = {}         # target -> list of printable strings
        self.groups = {}                 # group_id -> {"name": name, "members": [...]}
        
        # Active file transfer
        self.active_incoming_offer = None # (peer_id, transfer_id, file_name, file_size)

    def compose(self) -> ComposeResult:
        with Container(id="main-container"):
            with Horizontal():
                # --- Left Sidebar ---
                with Vertical(id="sidebar"):
                    yield Label(f"User: {self.username}\nID: {self.device_id[:8]}...", id="profile-info")
                    yield Label("Contacts:", id="contacts-title")
                    yield ListView(id="contacts-list")
                    yield Label("[Q] Quit  [C] Groups", id="help-footer")
                    
                # --- Right Chat View ---
                with Vertical(id="chat-panel"):
                    with Vertical(id="chat-header"):
                        yield Label("Select a peer or group", id="chat-title")
                        yield Label("E2EE secured channel resolution", id="chat-subtitle")
                    yield RichLog(id="chat-log", highlight=True, markup=True)
                    with Horizontal(id="chat-input-bar"):
                        yield Input(placeholder="Type message or commands (/file, /group, /accept, /reject)...", id="message-input")

    def on_mount(self) -> None:
        """
        Starts networking and hooks callbacks when TUI loads.
        """
        # Hook callbacks
        c = self.network_manager.callbacks
        c.peer_discovered.append(self.on_peer_discovered_thread)
        c.peer_removed.append(self.on_peer_removed_thread)
        c.message_received.append(self.on_message_received_thread)
        c.group_message_received.append(self.on_group_message_received_thread)
        c.file_offer_received.append(self.on_file_offer_received_thread)
        c.file_offer_accepted.append(self.on_file_offer_accepted_thread)
        c.file_offer_rejected.append(self.on_file_offer_rejected_thread)
        c.file_progress.append(self.on_file_progress_thread)
        c.file_completed.append(self.on_file_completed_thread)
        c.file_failed.append(self.on_file_failed_thread)
        
        # Start networking
        self.network_manager.start()
        
        # Wait a fraction for port binding, then start discovery
        time.sleep(0.1)
        self.discovery_service.start()
        
        self.log_to_chat("[cyan]*** Welcome to ZeroNet TUI Messenger! ***[/]")
        self.log_to_chat("[cyan]*** Monospaced secure local P2P networking started ***[/]")
        
        # Refresh the sidebar initially
        self.refresh_sidebar()

    def log_to_chat(self, msg: str, target: str = None):
        """
        Appends a message to the memory history and logs to the screen if currently active.
        """
        time_str = time.strftime("%H:%M:%S")
        log_line = f"[gray][{time_str}][/] {msg}"
        
        if target:
            if target not in self.chat_histories:
                self.chat_histories[target] = []
            self.chat_histories[target].append(log_line)
            
            if self.current_chat_target == target:
                self.query_one("#chat-log", RichLog).write(log_line)
        else:
            self.query_one("#chat-log", RichLog).write(log_line)

    def refresh_sidebar(self):
        list_view = self.query_one("#contacts-list", ListView)
        list_view.clear()
        
        # Render groups
        for gid, ginfo in self.groups.items():
            item = ListItem(Label(f"👥 {ginfo['name']} ({len(ginfo['members'])} online)"), id=f"item-group-{gid}")
            item.name = f"group:{gid}"
            list_view.append(item)
            
        # Render discovered peers
        for pid, pinfo in self.network_manager.peers.items():
            indicator = "[+]" if pinfo["status"] == "online" else "[-]"
            item = ListItem(Label(f"{indicator} {pinfo['name']} ({pinfo['ip']})"), id=f"item-peer-{pid}")
            item.name = f"peer:{pid}"
            list_view.append(item)

    # --- LIST SELECTION EVENT ---
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not event.item:
            return
            
        target_key = getattr(event.item, "name", None)
        if not target_key:
            return
            
        self.current_chat_target = target_key
        
        # Update headers
        title = self.query_one("#chat-title", Label)
        subtitle = self.query_one("#chat-subtitle", Label)
        
        if target_key.startswith("peer:"):
            peer_id = target_key.split(":")[1]
            pinfo = self.network_manager.peers.get(peer_id)
            if pinfo:
                title.update(f"Chat: {pinfo['name']}")
                subtitle.update(f"Status: {pinfo['status'].upper()} | Secure Session Established")
                
        elif target_key.startswith("group:"):
            group_id = target_key.split(":")[1]
            ginfo = self.groups.get(group_id)
            if ginfo:
                title.update(f"Group: {ginfo['name']}")
                subtitle.update(f"{len(ginfo['members'])} members | Mesh E2EE active")
                
        # Reload history log
        log_widget = self.query_one("#chat-log", RichLog)
        log_widget.clear()
        
        history = self.chat_histories.get(target_key, [])
        for line in history:
            log_widget.write(line)

    # --- CLI / TUI COMMAND PARSER ---
    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
            
        input_widget = self.query_one("#message-input", Input)
        input_widget.value = ""
        
        # Handle slash commands
        if text.startswith("/"):
            self.handle_command(text)
            return
            
        if not self.current_chat_target:
            self.log_to_chat("[red]*** Please select a peer or group chat from the contact list first! ***[/]")
            return
            
        # Add to history locally
        target = self.current_chat_target
        self.log_to_chat(f"[red]<Me>[/] {text}", target=target)
        
        # Send
        if target.startswith("peer:"):
            peer_id = target.split(":")[1]
            try:
                self.network_manager.send_direct_message(peer_id, text)
            except Exception as e:
                self.log_to_chat(f"[red]*** Send failed: {e} ***[/]", target=target)
                
        elif target.startswith("group:"):
            group_id = target.split(":")[1]
            ginfo = self.groups.get(group_id)
            if ginfo:
                self.network_manager.send_group_message(group_id, ginfo["name"], ginfo["members"], text)

    def handle_command(self, cmd_text: str):
        parts = cmd_text.split(" ", 1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if command == "/group":
            # Command syntax: /group create <group_name> <peer_name_1> <peer_name_2>...
            subparts = args.split(" ")
            if len(subparts) < 3 or subparts[0] != "create":
                self.log_to_chat("[yellow]*** Group syntax: /group create <name> <peer_name_1> <peer_name_2>... ***[/]")
                return
                
            group_name = subparts[1]
            member_names = subparts[2:]
            
            # Resolve peer names to peer IDs
            member_ids = []
            for mname in member_names:
                resolved_id = None
                for pid, pinfo in self.network_manager.peers.items():
                    if pinfo["name"].lower() == mname.lower() and pinfo["status"] == "online":
                        resolved_id = pid
                        break
                if resolved_id:
                    member_ids.append(resolved_id)
                else:
                    self.log_to_chat(f"[red]*** Error: Online peer named '{mname}' not found. ***[/]")
                    
            if not member_ids:
                self.log_to_chat("[red]*** Error: Group must contain at least 1 online peer. ***[/]")
                return
                
            # Add self as member
            member_ids.append(self.network_manager.device_id)
            
            group_id = f"grp_{int(time.time())}"
            self.groups[group_id] = {
                "name": group_name,
                "members": member_ids
            }
            
            self.log_to_chat(f"[green]*** Group '{group_name}' successfully created! ***[/]")
            self.refresh_sidebar()
            
        elif command == "/file":
            if not self.current_chat_target or not self.current_chat_target.startswith("peer:"):
                self.log_to_chat("[red]*** File sharing is only supported inside direct chats! ***[/]")
                return
                
            file_path = args.strip()
            if not file_path:
                self.log_to_chat("[yellow]*** File syntax: /file <path_to_file> ***[/]")
                return
                
            peer_id = self.current_chat_target.split(":")[1]
            if not os.path.exists(file_path):
                self.log_to_chat(f"[red]*** Error: File path does not exist: {file_path} ***[/]")
                return
                
            try:
                transfer_id = self.network_manager.offer_file(peer_id, file_path)
                file_name = os.path.basename(file_path)
                size_mb = os.path.getsize(file_path) / (1024 * 1024)
                self.log_to_chat(f"[blue]*** File offered: {file_name} ({size_mb:.2f} MB). Waiting for acceptance... ***[/]", target=self.current_chat_target)
            except Exception as e:
                self.log_to_chat(f"[red]*** Error initiating file transfer: {e} ***[/]", target=self.current_chat_target)
                
        elif command == "/accept":
            if not self.active_incoming_offer:
                self.log_to_chat("[yellow]*** No active incoming file offer. ***[/]")
                return
                
            peer_id, transfer_id, file_name, file_size = self.active_incoming_offer
            self.active_incoming_offer = None
            
            # Save to current directory
            save_path = os.path.join(os.getcwd(), f"downloaded_{file_name}")
            self.log_to_chat(f"[green]*** Accept offer. Saving file stream to: {save_path} ***[/]")
            
            try:
                self.network_manager.accept_file(peer_id, transfer_id, save_path)
            except Exception as e:
                self.log_to_chat(f"[red]*** File accept error: {e} ***[/]")
                
        elif command == "/reject":
            if not self.active_incoming_offer:
                self.log_to_chat("[yellow]*** No active incoming file offer. ***[/]")
                return
                
            peer_id, transfer_id, file_name, file_size = self.active_incoming_offer
            self.active_incoming_offer = None
            
            self.network_manager.reject_file(peer_id, transfer_id)
            self.log_to_chat("[yellow]*** File offer rejected. ***[/]")
            
        else:
            self.log_to_chat("[yellow]*** Unknown command. Commands: /file, /group, /accept, /reject ***[/]")

    def action_create_group_shortcut(self) -> None:
        self.log_to_chat("[yellow]*** Group Commands Help: ***[/]")
        self.log_to_chat("[yellow]Create Group: /group create <name> <online_peer_name_1> <online_peer_name_2>...[/]")
        self.log_to_chat("[yellow]File Share:   /file <path> (inside peer chat view)[/]")

    # --- THREAD-SAFE CALLS TRIGGERED BY NETWORKING ---

    def on_peer_discovered_thread(self, peer_id: str, name: str, ip: str, port: int):
        self.call_from_thread(self.handle_peer_discovered, peer_id, name, ip, port)

    def on_peer_removed_thread(self, peer_id: str):
        self.call_from_thread(self.handle_peer_removed, peer_id)

    def on_message_received_thread(self, peer_id: str, peer_name: str, text: str, timestamp: float):
        self.call_from_thread(self.handle_message_received, peer_id, peer_name, text, timestamp)

    def on_group_message_received_thread(self, peer_id: str, peer_name: str, group_id: str, group_name: str, text: str, timestamp: float):
        self.call_from_thread(self.handle_group_message_received, peer_id, peer_name, group_id, group_name, text, timestamp)

    def on_file_offer_received_thread(self, peer_id: str, peer_name: str, file_name: str, file_size: int, transfer_id: str):
        self.call_from_thread(self.handle_file_offer_received, peer_id, peer_name, file_name, file_size, transfer_id)

    def on_file_offer_accepted_thread(self, peer_id: str, transfer_id: str, file_port: int):
        self.call_from_thread(self.handle_file_offer_accepted, peer_id, transfer_id, file_port)

    def on_file_offer_rejected_thread(self, peer_id: str, transfer_id: str):
        self.call_from_thread(self.handle_file_offer_rejected, peer_id, transfer_id)

    def on_file_progress_thread(self, transfer_id: str, bytes_transferred: int, bytes_total: int):
        self.call_from_thread(self.handle_file_progress, transfer_id, bytes_transferred, bytes_total)

    def on_file_completed_thread(self, transfer_id: str, file_path: str):
        self.call_from_thread(self.handle_file_completed, transfer_id, file_path)

    def on_file_failed_thread(self, transfer_id: str, error_msg: str):
        self.call_from_thread(self.handle_file_failed, transfer_id, error_msg)

    # --- UI UPDATE HANDLERS (RUN ON MAIN TUI EVENT LOOP) ---

    def handle_peer_discovered(self, peer_id: str, name: str, ip: str, port: int):
        self.log_to_chat(f"[green]*** Discovered peer online: {name} ({ip}:{port}) ***[/]")
        self.refresh_sidebar()

    def handle_peer_removed(self, peer_id: str):
        self.log_to_chat(f"[yellow]*** Peer resolved offline: {peer_id[:8]}... ***[/]")
        self.refresh_sidebar()

    def handle_message_received(self, peer_id: str, peer_name: str, text: str, timestamp: float):
        self.log_to_chat(f"[blue]<{peer_name}>[/] {text}", target=f"peer:{peer_id}")

    def handle_group_message_received(self, peer_id: str, peer_name: str, group_id: str, group_name: str, text: str, timestamp: float):
        target = f"group:{group_id}"
        if group_id not in self.groups:
            self.groups[group_id] = {
                "name": group_name,
                "members": [peer_id, self.network_manager.device_id]
            }
            self.refresh_sidebar()
            
        self.log_to_chat(f"[blue]<{peer_name}>[/] {text}", target=target)

    def handle_file_offer_received(self, peer_id: str, peer_name: str, file_name: str, file_size: int, transfer_id: str):
        size_mb = file_size / (1024 * 1024)
        self.active_incoming_offer = (peer_id, transfer_id, file_name, file_size)
        self.log_to_chat(f"[yellow]🚨 FILE OFFER: {peer_name} is offering '{file_name}' ({size_mb:.2f} MB) ***[/]")
        self.log_to_chat("[yellow]🚨 Type /accept to download or /reject to decline. ***[/]")

    def handle_file_offer_accepted(self, peer_id: str, transfer_id: str, file_port: int):
        self.log_to_chat("[green]*** Peer accepted file offer. Starting upload... ***[/]", target=self.current_chat_target)
        self.network_manager.start_file_upload(peer_id, transfer_id, file_port)

    def handle_file_offer_rejected(self, peer_id: str, transfer_id: str):
        self.log_to_chat("[yellow]*** File offer rejected by peer. ***[/]", target=self.current_chat_target)

    def handle_file_progress(self, transfer_id: str, bytes_transferred: int, bytes_total: int):
        pct = int((bytes_transferred / bytes_total) * 100) if bytes_total > 0 else 100
        # Print progress update
        if pct % 25 == 0:  # Avoid flooding log, print at 0%, 25%, 50%, 75%, 100%
            self.log_to_chat(f"[cyan]*** File transfer progress: {pct}% completed ***[/]")

    def handle_file_completed(self, transfer_id: str, file_path: str):
        self.log_to_chat(f"[green]*** File transfer completed successfully! Saved to: {file_path} ***[/]")

    def handle_file_failed(self, transfer_id: str, error_msg: str):
        self.log_to_chat(f"[red]*** File transfer failed: {error_msg} ***[/]")

    def on_unmount(self) -> None:
        self.discovery_service.stop()
        self.network_manager.stop()


def parse_args():
    parser = argparse.ArgumentParser(description="ZeroNet Secure TUI Messenger")
    parser.add_argument("--name", type=str, default=None, help="Display username (defaults to hostname)")
    parser.add_argument("--port", type=int, default=54321, help="TCP Listening Port")
    return parser.parse_args()

def main():
    args = parse_args()
    username = args.name
    if not username:
        username = socket.gethostname()
        
    app = ZeroNetTUI(username, args.port)
    app.run()

if __name__ == "__main__":
    main()
