import os
import threading
import time
import argparse
import socket
import uuid
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(message)s"
)

from textual.app import App, ComposeResult
from textual.widgets import (
    Header, Footer, ListView, ListItem, Label, Input, RichLog, Static,
    ProgressBar
)
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.binding import Binding
from textual.timer import Timer
from textual import on

from zeronet.network.connection import NetworkManager
from zeronet.network.discovery import DiscoveryService, get_local_ip
from textual.suggester import Suggester

class FilePathSuggester(Suggester):
    async def get_suggestion(self, value: str) -> str | None:
        if not value.startswith("/file "):
            return None
        path_part = value[6:]
        if not path_part:
            return "/file ~/"
        if path_part == "~":
            return "/file ~/"

        is_home_rel = path_part.startswith("~/")
        expanded = os.path.expanduser(path_part)
        
        if path_part.endswith('/') or (os.path.exists(expanded) and os.path.isdir(expanded)):
            dirname = expanded
            basename = ""
        else:
            dirname = os.path.dirname(expanded)
            basename = os.path.basename(expanded)

        if not dirname:
            dirname = "."

        try:
            if not os.path.exists(dirname) or not os.path.isdir(dirname):
                return None
            items = os.listdir(dirname)
            matches = []
            for item in items:
                if item.startswith('.') and not basename.startswith('.'):
                    continue
                if item.lower().startswith(basename.lower()):
                    full_path = os.path.join(dirname, item)
                    suffix = "/" if os.path.isdir(full_path) else ""
                    matches.append(item + suffix)
            if not matches:
                return None
            matches.sort()
            best_match = matches[0]
            
            if is_home_rel:
                home_dir = os.path.expanduser("~")
                if path_part.endswith('/') or (os.path.exists(expanded) and os.path.isdir(expanded)):
                    rel_dir = os.path.relpath(expanded, home_dir)
                    if rel_dir == ".":
                        suggestion = "~/" + best_match
                    else:
                        suggestion = "~/" + rel_dir.rstrip('/') + "/" + best_match
                else:
                    rel_dir = os.path.relpath(dirname, home_dir)
                    if rel_dir == ".":
                        suggestion = "~/" + best_match
                    else:
                        suggestion = "~/" + rel_dir.rstrip('/') + "/" + best_match
            else:
                if path_part.endswith('/') or (os.path.exists(expanded) and os.path.isdir(expanded)):
                    suggestion = path_part.rstrip('/') + "/" + best_match
                else:
                    if '/' in path_part:
                        last_slash = path_part.rfind('/')
                        suggestion = path_part[:last_slash + 1] + best_match
                    else:
                        suggestion = best_match
            return f"/file {suggestion}"
        except Exception:
            return None

# ─── Textual CSS ──────────────────────────────────────────────────────────────
CSS = """
Screen {
    background: #0d1117;
}

/* ─── Title Bar ─────────────────────────────────────────────────────── */
#title-bar {
    dock: top;
    height: 3;
    background: #161b22;
    border-bottom: solid #30363d;
    padding: 0 2;
}

#title-logo {
    width: auto;
    color: #58a6ff;
    text-style: bold;
    padding: 1 1;
}

#title-status {
    width: 1fr;
    color: #8b949e;
    text-align: right;
    padding: 1 1;
}

/* ─── Main Layout ───────────────────────────────────────────────────── */
#main-layout {
    height: 1fr;
}

/* ─── Sidebar ───────────────────────────────────────────────────────── */
#sidebar {
    width: 34;
    min-width: 28;
    height: 100%;
    background: #161b22;
    border-right: solid #30363d;
}

#sidebar-header {
    height: auto;
    padding: 1 2;
    background: #1c2128;
    border-bottom: solid #30363d;
}

#profile-name {
    color: #f0f6fc;
    text-style: bold;
}

#profile-details {
    color: #8b949e;
}

#network-info {
    color: #3fb950;
}

#section-peers {
    height: auto;
    padding: 1 2 0 2;
    color: #484f58;
    text-style: bold;
}

#contacts-list {
    background: #161b22;
    height: 1fr;
    scrollbar-color: #30363d;
    scrollbar-color-hover: #484f58;
    scrollbar-color-active: #6e7681;
}

#contacts-list > ListItem {
    padding: 0 2;
    height: 3;
    color: #c9d1d9;
    background: #161b22;
}

#contacts-list > ListItem:hover {
    background: #1c2128;
}

#contacts-list > ListItem.-selected {
    background: #1f6feb22;
    color: #58a6ff;
}

#sidebar-footer {
    height: auto;
    padding: 1 2;
    background: #1c2128;
    border-top: solid #30363d;
    color: #484f58;
}

/* ─── Chat Panel ────────────────────────────────────────────────────── */
#chat-panel {
    width: 1fr;
    background: #0d1117;
}

#chat-header {
    dock: top;
    height: 4;
    padding: 1 2;
    background: #161b22;
    border-bottom: solid #30363d;
}

#chat-header-text {
    width: 1fr;
}

#chat-title {
    color: #f0f6fc;
    text-style: bold;
}

#chat-subtitle {
    color: #3fb950;
}

#encryption-badge {
    width: auto;
    color: #3fb950;
    padding: 1 0;
}

#chat-log {
    background: #0d1117;
    padding: 0 2;
    scrollbar-color: #30363d;
    scrollbar-color-hover: #484f58;
    scrollbar-color-active: #6e7681;
}

#chat-input-bar {
    dock: bottom;
    height: 3;
    background: #1c2128;
    border-top: solid #3fb950;
    padding: 0 1;
}

#input-prefix {
    width: auto;
    color: #3fb950;
    padding: 0 1 0 0;
    text-style: bold;
}

#message-input {
    background: #0d1117;
    border: none;
    color: #f0f6fc;
    width: 1fr;
}

#message-input:focus {
    border: none;
}

/* ─── Status Bar ────────────────────────────────────────────────────── */
#status-bar {
    dock: bottom;
    height: 1;
    background: #1f6feb;
    color: #ffffff;
    padding: 0 2;
    text-style: bold;
}

/* ─── Notification Toast ────────────────────────────────────────────── */
#notification-bar {
    dock: top;
    height: auto;
    display: none;
    background: #1c2128;
    border-bottom: solid #e3b341;
    color: #e3b341;
    padding: 0 2;
    text-style: bold;
}

#notification-bar.visible {
    display: block;
}
"""


class ZeroNetTUI(App):
    CSS = CSS

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True, priority=True),
        Binding("ctrl+h", "show_help", "Help", show=True),
        Binding("ctrl+g", "create_group_shortcut", "New Group", show=True),
        Binding("ctrl+p", "show_peers", "Peers", show=True),
        Binding("ctrl+l", "clear_chat", "Clear", show=True),
        Binding("escape", "focus_input", "Focus Input", show=False),
        Binding("tab", "toggle_focus", "Switch Focus", show=False),
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
        self.unread_counts = {}          # target -> int

        # Active file transfer
        self.active_incoming_offer = None  # (peer_id, transfer_id, file_name, file_size)

        # Timers
        self._refresh_timer = None
        self._notification_timer = None

        # Uptime tracking
        self._start_time = time.time()

        # Message count tracking
        self._msg_sent = 0
        self._msg_received = 0

        # Tips cycling
        self._tips = [
            "💡 Type your message in the input bar at the bottom and press Enter",
            "💡 Use /help to see all available commands",
            "💡 Click a peer in the left sidebar to start chatting",
            "💡 Use /file ~/path/to/file to send a file to a peer",
            "💡 Use /group create teamname alice bob to start a group chat",
            "💡 Press Tab to switch focus between sidebar and input",
            "💡 Use /peers to see all discovered devices on your network",
            "💡 Press Ctrl+Q to quit, Ctrl+H for help",
            "💡 Use /status to see session statistics and encryption info",
            "💡 Use /ping alice to check if a peer is reachable",
        ]
        self._tip_index = 0

    def compose(self) -> ComposeResult:
        # ─── Title Bar ──────────────────────────────────────────────
        with Horizontal(id="title-bar"):
            yield Static("◆ ZeroNet", id="title-logo")
            yield Static("Initializing…", id="title-status")

        # ─── Main Layout ────────────────────────────────────────────
        with Horizontal(id="main-layout"):
            # ─── Sidebar ────────────────────────────────────────────
            with Vertical(id="sidebar"):
                with Vertical(id="sidebar-header"):
                    yield Static(f"⬡ {self.username}", id="profile-name")
                    yield Static(f"ID: {self.device_id[:16]}…", id="profile-details")
                    yield Static("", id="network-info")
                yield Static("─── NETWORK ──────────────", id="section-peers")
                yield ListView(id="contacts-list")
                yield Static("Tab: switch │ Esc: input", id="sidebar-footer")

            # ─── Chat Panel ─────────────────────────────────────────
            with Container(id="chat-panel"):
                with Horizontal(id="chat-header"):
                    with Vertical(id="chat-header-text"):
                        yield Static("Select a contact", id="chat-title")
                        yield Static("End-to-end encrypted", id="chat-subtitle")
                    yield Static("🔒 E2EE", id="encryption-badge")
                yield RichLog(id="chat-log", highlight=True, markup=True)
                with Horizontal(id="chat-input-bar"):
                    yield Static("▸ TYPE HERE:", id="input-prefix")
                    yield Input(
                        placeholder="Type a message and press Enter… (/help for commands)",
                        id="message-input",
                        suggester=FilePathSuggester()
                    )

        # ─── Status Bar ─────────────────────────────────────────────
        yield Static("ZeroNet v0.1.0 │ Starting…", id="status-bar")

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

        # Start discovery service in a separate thread so it doesn't block Textual's event loop
        def run_discovery():
            time.sleep(0.2)
            self.discovery_service.start()

        t = threading.Thread(target=run_discovery)
        t.daemon = True
        t.start()

        # Welcome banner - defer slightly to ensure RichLog is fully ready
        self.set_timer(0.2, self._print_welcome)

        # Update network info
        try:
            local_ip = get_local_ip()
        except Exception:
            local_ip = "unknown"
        net_info = self.query_one("#network-info", Static)
        net_info.update(f"● {local_ip}:{self.network_manager.port}")

        # Update title status
        title_status = self.query_one("#title-status", Static)
        title_status.update(f"● Online │ {local_ip}")

        # Start periodic refresh (every 3 seconds)
        self._refresh_timer = self.set_interval(3.0, self._periodic_refresh)

        self.query_one("#message-input", Input).focus()

    def _print_welcome(self):
        """Print the welcome banner with clear instructions."""
        log = self.query_one("#chat-log", RichLog)
        log.write("")
        log.write("[bold #58a6ff]  ╔═══════════════════════════════════════════════════════╗[/]")
        log.write("[bold #58a6ff]  ║                                                       ║[/]")
        log.write("[bold #58a6ff]  ║   ◆  Z E R O N E T   M E S S E N G E R                ║[/]")
        log.write("[bold #58a6ff]  ║                                                       ║[/]")
        log.write("[bold #58a6ff]  ║   Peer-to-Peer  •  End-to-End Encrypted               ║[/]")
        log.write("[bold #58a6ff]  ║   Zero Configuration  •  No Server Required           ║[/]")
        log.write("[bold #58a6ff]  ║                                                       ║[/]")
        log.write("[bold #58a6ff]  ╚═══════════════════════════════════════════════════════╝[/]")
        log.write("")
        log.write("[bold #3fb950]  ─── Getting Started ────────────────────────────────────[/]")
        log.write("")
        log.write("  [bold #f0f6fc]Step 1.[/]  [#c9d1d9]Wait for peers to appear in the LEFT SIDEBAR[/]")
        log.write("          [#8b949e](devices running ZeroNet on your network auto-discover)[/]")
        log.write("")
        log.write("  [bold #f0f6fc]Step 2.[/]  [#c9d1d9]CLICK a peer name in the sidebar to open their chat[/]")
        log.write("")
        log.write("  [bold #f0f6fc]Step 3.[/]  [#c9d1d9]TYPE your message in the [bold #3fb950]▸ INPUT BAR[/][#c9d1d9] at the bottom[/]")
        log.write("          [#8b949e](the green-bordered box at the very bottom of the screen)[/]")
        log.write("")
        log.write("  [bold #f0f6fc]Step 4.[/]  [#c9d1d9]Press [bold]ENTER[/][#c9d1d9] to send your message[/]")
        log.write("")
        log.write("[#484f58]  ┌─ Quick Commands ────────────────────────────────────────┐[/]")
        log.write("[#484f58]  │[/]  [bold #c9d1d9]/help[/]    [#6e7681]Show all commands and shortcuts[/]         [#484f58]│[/]")
        log.write("[#484f58]  │[/]  [bold #c9d1d9]/peers[/]   [#6e7681]List all devices on your network[/]        [#484f58]│[/]")
        log.write("[#484f58]  │[/]  [bold #c9d1d9]/file[/]    [#6e7681]Send a file  (e.g. /file ~/photo.jpg)[/]  [#484f58]│[/]")
        log.write("[#484f58]  │[/]  [bold #c9d1d9]/group[/]   [#6e7681]Create group chat with peers[/]            [#484f58]│[/]")
        log.write("[#484f58]  │[/]  [bold #c9d1d9]Ctrl+Q[/]   [#6e7681]Quit application[/]                        [#484f58]│[/]")
        log.write("[#484f58]  └────────────────────────────────────────────────────────┘[/]")
        log.write("")
        log.write("[#8b949e]  🔍 Scanning your local network for peers via mDNS…[/]")
        log.write("")

    def _format_uptime(self) -> str:
        """Format uptime as a human-readable string."""
        elapsed = int(time.time() - self._start_time)
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    def _periodic_refresh(self) -> None:
        """Periodically refresh sidebar and status bar with cycling tips."""
        self.refresh_sidebar()

        online = sum(1 for p in self.network_manager.peers.values() if p["status"] == "online")
        offline = sum(1 for p in self.network_manager.peers.values() if p["status"] != "online")
        try:
            local_ip = get_local_ip()
        except Exception:
            local_ip = "?"

        # Get current tip
        tip = self._tips[self._tip_index % len(self._tips)]
        self._tip_index += 1

        # Build status bar with cycling tip
        parts = [
            f"{local_ip}:{self.network_manager.port}",
            f"🔒 E2EE",
            f"{online}↑ {offline}↓",
            f"↑{self._msg_sent} ↓{self._msg_received}",
            tip,
        ]
        status = self.query_one("#status-bar", Static)
        status.update(" │ ".join(parts))

        # Update peer section label
        section = self.query_one("#section-peers", Static)
        total = len(self.network_manager.peers)
        group_count = len(self.groups)
        label_parts = []
        if total > 0:
            label_parts.append(f"{online}↑ {offline}↓")
        if group_count > 0:
            label_parts.append(f"{group_count} grp")
        suffix = f" ({', '.join(label_parts)})" if label_parts else ""
        section.update(f"─── NETWORK{suffix} ─────")

    def log_to_chat(self, msg: str, target: str = None):
        """
        Appends a message to the memory history and logs to the screen if currently active.
        """
        time_str = time.strftime("%H:%M:%S")
        log_line = f"[#484f58]{time_str}[/] {msg}"

        if target:
            if target not in self.chat_histories:
                self.chat_histories[target] = []
            
            is_first = len(self.chat_histories[target]) == 0
            self.chat_histories[target].append(log_line)

            if self.current_chat_target == target:
                log_widget = self.query_one("#chat-log", RichLog)
                if is_first:
                    log_widget.clear()
                log_widget.write(log_line)
            else:
                # Increment unread count and update sidebar
                self.unread_counts[target] = self.unread_counts.get(target, 0) + 1
                self.refresh_sidebar()
        else:
            self.query_one("#chat-log", RichLog).write(log_line)

    def refresh_sidebar(self):
        list_view = self.query_one("#contacts-list", ListView)

        # Remember current selection index
        current_index = list_view.index

        # remove_children() is synchronous - avoids DuplicateIds race with async clear()
        list_view.remove_children()

        # Render groups first
        for gid, ginfo in self.groups.items():
            target_key = f"group:{gid}"
            unread = self.unread_counts.get(target_key, 0)
            badge = f" [bold #f85149]({unread})[/]" if unread > 0 else ""
            active = " [#58a6ff]◂[/]" if self.current_chat_target == target_key else ""
            members_online = 0
            for mid in ginfo.get("members", []):
                pinfo = self.network_manager.peers.get(mid)
                if pinfo and pinfo["status"] == "online":
                    members_online += 1

            label_text = (
                f"[#a371f7]◈[/] [bold #c9d1d9]{ginfo['name']}[/] "
                f"[#484f58]{members_online}/{len(ginfo['members'])}[/]"
                f"{badge}{active}"
            )
            item = ListItem(Label(label_text), name=target_key)
            list_view.append(item)

        # Render online peers first, then offline
        sorted_peers = sorted(
            self.network_manager.peers.items(),
            key=lambda x: (0 if x[1]["status"] == "online" else 1, x[1]["name"].lower())
        )

        for pid, pinfo in sorted_peers:
            target_key = f"peer:{pid}"
            unread = self.unread_counts.get(target_key, 0)
            badge = f" [bold #f85149]({unread})[/]" if unread > 0 else ""
            active = " [#58a6ff]◂[/]" if self.current_chat_target == target_key else ""

            if pinfo["status"] == "online":
                indicator = "[bold #3fb950]●[/]"
                name_color = "#c9d1d9"
            else:
                indicator = "[#484f58]○[/]"
                name_color = "#484f58"

            label_text = (
                f"{indicator} [{name_color}]{pinfo['name']}[/] "
                f"[#484f58]{pinfo['ip']}[/]"
                f"{badge}{active}"
            )
            item = ListItem(Label(label_text), name=target_key)
            list_view.append(item)

        # Restore selection
        if current_index is not None and current_index < len(list_view):
            list_view.index = current_index

    # --- LIST SELECTION EVENT ---
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not event.item:
            return

        target_key = getattr(event.item, "name", None)
        if not target_key:
            return

        # Avoid redundant re-selection and infinite log-clearing loop
        if self.current_chat_target == target_key:
            return

        self.current_chat_target = target_key

        # Clear unread count
        self.unread_counts[target_key] = 0

        # Update headers
        title = self.query_one("#chat-title", Static)
        subtitle = self.query_one("#chat-subtitle", Static)
        badge = self.query_one("#encryption-badge", Static)

        if target_key.startswith("peer:"):
            peer_id = target_key.split(":", 1)[1]
            pinfo = self.network_manager.peers.get(peer_id)
            if pinfo:
                status_icon = "●" if pinfo["status"] == "online" else "○"
                status_color = "#3fb950" if pinfo["status"] == "online" else "#484f58"
                title.update(f"💬 {pinfo['name']}")
                subtitle.update(
                    f"[{status_color}]{status_icon} {pinfo['status'].upper()}[/] │ "
                    f"[#8b949e]{pinfo['ip']}:{pinfo['port']}[/]"
                )
                badge.update("[#3fb950]🔒 ECDH + Fernet[/]")

        elif target_key.startswith("group:"):
            group_id = target_key.split(":", 1)[1]
            ginfo = self.groups.get(group_id)
            if ginfo:
                title.update(f"◈ {ginfo['name']}")
                subtitle.update(
                    f"[#a371f7]{len(ginfo['members'])} members[/] │ "
                    f"[#8b949e]Full-mesh topology[/]"
                )
                badge.update("[#3fb950]🔒 Mesh E2EE[/]")

        # Reload history log
        log_widget = self.query_one("#chat-log", RichLog)
        log_widget.clear()

        history = self.chat_histories.get(target_key, [])
        if not history:
            log_widget.write("")
            log_widget.write("[#484f58]  ┌──────────────────────────────────────────────────────────┐[/]")
            log_widget.write("[#484f58]  │[/]  [#8b949e]No messages yet with this peer[/]                          [#484f58]│[/]")
            log_widget.write("[#484f58]  │[/]                                                          [#484f58]│[/]")
            log_widget.write("[#484f58]  │[/]  [bold #3fb950]▸ Type in the green-bordered input bar below ▸[/]            [#484f58]│[/]")
            log_widget.write("[#484f58]  │[/]    [#c9d1d9]Write your message and press[/] [bold]ENTER[/] [#c9d1d9]to send[/]           [#484f58]│[/]")
            log_widget.write("[#484f58]  │[/]                                                          [#484f58]│[/]")
            log_widget.write("[#484f58]  │[/]  [#6e7681]Or use a command:[/]                                       [#484f58]│[/]")
            log_widget.write("[#484f58]  │[/]    [#c9d1d9]/file ~/photo.jpg[/]  [#484f58]send a file[/]                       [#484f58]│[/]")
            log_widget.write("[#484f58]  │[/]    [#c9d1d9]/help[/]              [#484f58]see all commands[/]                    [#484f58]│[/]")
            log_widget.write("[#484f58]  └──────────────────────────────────────────────────────────┘[/]")
            log_widget.write("")
        else:
            for line in history:
                log_widget.write(line)

        self.refresh_sidebar()
        self.query_one("#message-input", Input).focus()

    # --- CLI / TUI COMMAND PARSER ---
    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        input_widget = self.query_one("#message-input", Input)
        input_widget.value = ""
        input_widget.focus()

        # Handle slash commands
        if text.startswith("/"):
            self.handle_command(text)
            return

        if not self.current_chat_target:
            self.log_to_chat("")
            self.log_to_chat(
                "[bold #f85149]⚠ No peer selected![/]"
            )
            self.log_to_chat(
                "  [#c9d1d9]Click a peer name in the [bold]LEFT SIDEBAR[/][#c9d1d9] first,[/]"
            )
            self.log_to_chat(
                "  [#c9d1d9]then type your message here and press Enter.[/]"
            )
            self.log_to_chat("")
            return

        # Add to history locally
        target = self.current_chat_target
        self.log_to_chat(
            f"[bold #58a6ff]You ▸[/] [#f0f6fc]{text}[/]",
            target=target
        )
        self._msg_sent += 1

        # Send
        if target.startswith("peer:"):
            peer_id = target.split(":", 1)[1]
            try:
                self.network_manager.send_direct_message(peer_id, text)
            except Exception as e:
                self.log_to_chat(
                    f"[bold #f85149]✗ Send failed:[/] [#f85149]{e}[/]",
                    target=target
                )

        elif target.startswith("group:"):
            group_id = target.split(":", 1)[1]
            ginfo = self.groups.get(group_id)
            if ginfo:
                self.network_manager.send_group_message(
                    group_id, ginfo["name"], ginfo["members"], text
                )

    def handle_command(self, cmd_text: str):
        parts = cmd_text.split(" ", 1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command == "/help":
            self._show_help_text()

        elif command == "/group":
            self._handle_group_command(args)

        elif command == "/file":
            self._handle_file_command(args)

        elif command == "/accept":
            self._handle_accept_command()

        elif command == "/reject":
            self._handle_reject_command()

        elif command == "/peers":
            self._show_peer_list()

        elif command == "/clear":
            self.action_clear_chat()

        elif command == "/status":
            self._show_status()

        elif command == "/whoami":
            self._show_whoami()

        elif command == "/ping":
            self._handle_ping_command(args)

        else:
            self.log_to_chat(
                f"[#e3b341]ℹ Unknown command:[/] [#c9d1d9]{command}[/] "
                f"[#484f58]- type /help[/]"
            )

    def _handle_group_command(self, args: str):
        """Handle /group create <name> <peer1> <peer2>..."""
        subparts = args.split(" ")
        if len(subparts) < 3 or subparts[0] != "create":
            self.log_to_chat("")
            self.log_to_chat("[#e3b341]ℹ Group Usage:[/]")
            self.log_to_chat("  [#c9d1d9]/group create <name> <peer1> <peer2>…[/]")
            self.log_to_chat("  [#484f58]Example: /group create devteam alice bob[/]")
            self.log_to_chat("")
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
                self.log_to_chat(
                    f"[#f85149]✗ Peer '{mname}' not found or offline[/]"
                )

        if not member_ids:
            self.log_to_chat("[#f85149]✗ Group requires at least 1 online peer[/]")
            return

        # Add self as member
        member_ids.append(self.network_manager.device_id)

        group_id = f"grp_{int(time.time())}"
        self.groups[group_id] = {
            "name": group_name,
            "members": member_ids
        }

        peer_names = []
        for mid in member_ids:
            if mid == self.network_manager.device_id:
                peer_names.append("You")
            else:
                pinfo = self.network_manager.peers.get(mid)
                peer_names.append(pinfo["name"] if pinfo else mid[:8])

        self.log_to_chat("")
        self.log_to_chat(
            f"[bold #3fb950]✓ Group created:[/] [bold #c9d1d9]{group_name}[/]"
        )
        self.log_to_chat(
            f"  [#8b949e]Members:[/] [#c9d1d9]{', '.join(peer_names)}[/]"
        )
        self.log_to_chat("")
        self.refresh_sidebar()

    def _handle_file_command(self, args: str):
        """Handle /file <path>"""
        if not self.current_chat_target or not self.current_chat_target.startswith("peer:"):
            self.log_to_chat("[#f85149]✗ File sharing only works in direct peer chats[/]")
            return

        file_path = args.strip()
        if not file_path or file_path.lower() == "list":
            self.log_to_chat("[#e3b341]ℹ Usage:[/] [#c9d1d9]/file <path_to_file>[/]")
            self._list_directory_contents(".")
            return

        # Expand ~ for home directory
        expanded_path = os.path.expanduser(file_path)

        peer_id = self.current_chat_target.split(":", 1)[1]
        if not os.path.exists(expanded_path):
            self.log_to_chat(f"[#f85149]✗ File not found:[/] [#8b949e]{file_path}[/]")
            parent_dir = os.path.dirname(expanded_path)
            if parent_dir and os.path.exists(parent_dir) and os.path.isdir(parent_dir):
                self._list_directory_contents(parent_dir)
            return

        if os.path.isdir(expanded_path):
            self.log_to_chat(f"[#e3b341]ℹ '{file_path}' is a directory. Listing files inside it:[/]")
            self._list_directory_contents(file_path)
            return

        try:
            transfer_id = self.network_manager.offer_file(peer_id, expanded_path)
            file_name = os.path.basename(expanded_path)
            file_size = os.path.getsize(expanded_path)
            size_str = self._format_file_size(file_size)
            self.log_to_chat("")
            self.log_to_chat(
                f"[#58a6ff]📤 Offering file to peer…[/]"
            )
            self.log_to_chat(
                f"  [#c9d1d9]File:[/]  [bold]{file_name}[/] [#484f58]({size_str})[/]"
            )
            self.log_to_chat(
                f"  [#8b949e]Waiting for peer to accept…[/]"
            )
            self.log_to_chat("",
                target=self.current_chat_target
            )
        except Exception as e:
            self.log_to_chat(
                f"[#f85149]✗ File transfer error:[/] [#f85149]{e}[/]",
                target=self.current_chat_target
            )

    def _list_directory_contents(self, dir_path: str):
        expanded = os.path.expanduser(dir_path)
        try:
            if not os.path.exists(expanded):
                self.log_to_chat(f"[#f85149]✗ Directory not found:[/] [#8b949e]{dir_path}[/]")
                return
            if not os.path.isdir(expanded):
                self.log_to_chat(f"[#f85149]✗ Not a directory:[/] [#8b949e]{dir_path}[/]")
                return

            items = os.listdir(expanded)
            # Filter and sort
            files = []
            dirs = []
            for item in items:
                if item.startswith('.'):
                    continue
                full_path = os.path.join(expanded, item)
                if os.path.isdir(full_path):
                    dirs.append(item + "/")
                else:
                    files.append(item)
            
            dirs.sort()
            files.sort()
            
            self.log_to_chat(f"  [#8b949e]Contents of '{dir_path}':[/]")
            if not dirs and not files:
                self.log_to_chat("    [#6e7681](directory is empty)[/]")
                return
                
            for d in dirs[:15]:
                self.log_to_chat(f"    [#58a6ff]📁 {d}[/]")
            for f in files[:25]:
                size = os.path.getsize(os.path.join(expanded, f))
                size_str = self._format_file_size(size)
                self.log_to_chat(f"    [#c9d1d9]📄 {f}[/] [#484f58]({size_str})[/]")
                
            total_items = len(dirs) + len(files)
            if total_items > 40:
                self.log_to_chat(f"    [#6e7681]... and {total_items - 40} more items[/]")
        except Exception as e:
            self.log_to_chat(f"[#f85149]✗ Error listing directory:[/] [#f85149]{e}[/]")

    def _handle_accept_command(self):
        """Handle /accept"""
        if not self.active_incoming_offer:
            self.log_to_chat("[#e3b341]ℹ No pending file offer to accept[/]")
            return

        peer_id, transfer_id, file_name, file_size = self.active_incoming_offer
        self.active_incoming_offer = None

        # Save to current directory
        save_path = os.path.join(os.getcwd(), f"downloaded_{file_name}")
        self.log_to_chat(
            f"[#3fb950]✓ Accepted.[/] [#8b949e]Saving to:[/] [#c9d1d9]{save_path}[/]"
        )

        try:
            self.network_manager.accept_file(peer_id, transfer_id, save_path)
        except Exception as e:
            self.log_to_chat(f"[#f85149]✗ File accept error:[/] [#f85149]{e}[/]")

    def _handle_reject_command(self):
        """Handle /reject"""
        if not self.active_incoming_offer:
            self.log_to_chat("[#e3b341]ℹ No pending file offer to reject[/]")
            return

        peer_id, transfer_id, file_name, file_size = self.active_incoming_offer
        self.active_incoming_offer = None

        self.network_manager.reject_file(peer_id, transfer_id)
        self.log_to_chat("[#e3b341]↩ File offer rejected[/]")

    def _handle_ping_command(self, args: str):
        """Handle /ping <peer_name> - test connectivity to a peer."""
        peer_name = args.strip()
        if not peer_name:
            self.log_to_chat("[#e3b341]ℹ Usage:[/] [#c9d1d9]/ping <peer_name>[/]")
            return

        for pid, pinfo in self.network_manager.peers.items():
            if pinfo["name"].lower() == peer_name.lower():
                if pinfo["status"] == "online":
                    self.log_to_chat(
                        f"[#3fb950]● PONG[/] [#c9d1d9]{pinfo['name']}[/] "
                        f"[#8b949e]({pinfo['ip']}:{pinfo['port']})[/] "
                        f"[#3fb950]is reachable[/]"
                    )
                else:
                    self.log_to_chat(
                        f"[#f85149]○ TIMEOUT[/] [#c9d1d9]{pinfo['name']}[/] "
                        f"[#8b949e]is offline[/]"
                    )
                return
        self.log_to_chat(f"[#f85149]✗ Peer '{peer_name}' not found[/]")

    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        """Format bytes into human-readable string."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def _show_help_text(self):
        log = self.query_one("#chat-log", RichLog)
        log.write("")
        log.write("[bold #58a6ff]  ┌─ Commands ─────────────────────────────────────────┐[/]")
        log.write("[bold #58a6ff]  │[/]                                                   [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #c9d1d9]/help[/]                   [#6e7681]Show this help text[/]     [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #c9d1d9]/peers[/]                  [#6e7681]List discovered peers[/]   [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #c9d1d9]/clear[/]                  [#6e7681]Clear chat window[/]       [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #c9d1d9]/status[/]                 [#6e7681]Show session stats[/]      [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #c9d1d9]/whoami[/]                 [#6e7681]Show your identity[/]      [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #c9d1d9]/ping[/] [#8b949e]<name>[/]            [#6e7681]Check peer status[/]       [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]                                                   [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #a371f7]Group Chat[/]                                        [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #c9d1d9]/group create[/] [#8b949e]<name> <p…>[/] [#6e7681]Create group[/]    [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]                                                   [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #e3b341]File Transfer[/]                                     [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #c9d1d9]/file[/] [#8b949e]<path>[/]           [#6e7681]Send file to peer[/]      [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #c9d1d9]/accept[/]                 [#6e7681]Accept file offer[/]       [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #c9d1d9]/reject[/]                 [#6e7681]Reject file offer[/]       [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]                                                   [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  ├─ Keyboard Shortcuts ──────────────────────────────┤[/]")
        log.write("[bold #58a6ff]  │[/]                                                   [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #c9d1d9]Ctrl+Q[/]  [#6e7681]Quit ZeroNet[/]                         [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #c9d1d9]Ctrl+H[/]  [#6e7681]Show help[/]                            [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #c9d1d9]Ctrl+G[/]  [#6e7681]Group creation help[/]                  [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #c9d1d9]Ctrl+P[/]  [#6e7681]List peers[/]                           [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #c9d1d9]Ctrl+L[/]  [#6e7681]Clear chat[/]                           [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #c9d1d9]Tab[/]     [#6e7681]Toggle sidebar/input focus[/]           [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]  [bold #c9d1d9]Escape[/]  [#6e7681]Focus message input[/]                  [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  │[/]                                                   [bold #58a6ff]│[/]")
        log.write("[bold #58a6ff]  └───────────────────────────────────────────────────┘[/]")
        log.write("")

    def _show_peer_list(self):
        peers = self.network_manager.peers
        log = self.query_one("#chat-log", RichLog)

        if not peers:
            log.write("")
            log.write("[#8b949e]  No peers discovered yet. Scanning…[/]")
            log.write("")
            return

        online = [(pid, p) for pid, p in peers.items() if p["status"] == "online"]
        offline = [(pid, p) for pid, p in peers.items() if p["status"] != "online"]

        log.write("")
        log.write(f"[bold #58a6ff]  ─── Discovered Peers ({len(peers)}) ─────────────────────[/]")
        log.write("")

        if online:
            log.write("  [bold #3fb950]Online:[/]")
            for pid, pinfo in online:
                log.write(
                    f"    [bold #3fb950]●[/] [bold #c9d1d9]{pinfo['name']}[/]  "
                    f"[#8b949e]{pinfo['ip']}:{pinfo['port']}[/]  "
                    f"[#484f58]{pid[:16]}…[/]"
                )

        if offline:
            log.write("  [#484f58]Offline:[/]")
            for pid, pinfo in offline:
                log.write(
                    f"    [#484f58]○[/] [#484f58]{pinfo['name']}  "
                    f"{pinfo['ip']}:{pinfo['port']}[/]"
                )

        log.write("")

    def _show_status(self):
        """Show session statistics."""
        log = self.query_one("#chat-log", RichLog)
        try:
            local_ip = get_local_ip()
        except Exception:
            local_ip = "unknown"
        online = sum(1 for p in self.network_manager.peers.values() if p["status"] == "online")
        total = len(self.network_manager.peers)

        log.write("")
        log.write("[bold #58a6ff]  ─── Session Status ─────────────────────────────[/]")
        log.write("")
        log.write(f"  [#c9d1d9]Uptime:[/]          [#8b949e]{self._format_uptime()}[/]")
        log.write(f"  [#c9d1d9]Local IP:[/]         [#8b949e]{local_ip}[/]")
        log.write(f"  [#c9d1d9]Listening Port:[/]   [#8b949e]{self.network_manager.port}[/]")
        log.write(f"  [#c9d1d9]Device ID:[/]        [#8b949e]{self.device_id}[/]")
        log.write(f"  [#c9d1d9]Peers:[/]            [#8b949e]{online} online / {total} total[/]")
        log.write(f"  [#c9d1d9]Groups:[/]           [#8b949e]{len(self.groups)}[/]")
        log.write(f"  [#c9d1d9]Messages Sent:[/]    [#8b949e]{self._msg_sent}[/]")
        log.write(f"  [#c9d1d9]Messages Received:[/] [#8b949e]{self._msg_received}[/]")
        log.write(f"  [#c9d1d9]Encryption:[/]       [#3fb950]ECDH (secp256r1) + Fernet[/]")
        log.write(f"  [#c9d1d9]Discovery:[/]        [#3fb950]mDNS / Zeroconf[/]")
        log.write("")

    def _show_whoami(self):
        """Show current user identity info."""
        log = self.query_one("#chat-log", RichLog)
        try:
            local_ip = get_local_ip()
        except Exception:
            local_ip = "unknown"

        log.write("")
        log.write("[bold #58a6ff]  ─── Your Identity ──────────────────────────────[/]")
        log.write("")
        log.write(f"  [#c9d1d9]Username:[/]   [bold #f0f6fc]{self.username}[/]")
        log.write(f"  [#c9d1d9]Device ID:[/]  [#8b949e]{self.device_id}[/]")
        log.write(f"  [#c9d1d9]Address:[/]    [#8b949e]{local_ip}:{self.network_manager.port}[/]")
        log.write(f"  [#c9d1d9]mDNS Name:[/]  [#8b949e]{self.device_id}._zeronet._tcp.local.[/]")
        log.write("")

    def action_show_help(self) -> None:
        self._show_help_text()

    def action_show_peers(self) -> None:
        self._show_peer_list()

    def action_clear_chat(self) -> None:
        log_widget = self.query_one("#chat-log", RichLog)
        log_widget.clear()
        if self.current_chat_target and self.current_chat_target in self.chat_histories:
            self.chat_histories[self.current_chat_target] = []
        log_widget.write("[#484f58]  Chat cleared.[/]")

    def action_create_group_shortcut(self) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write("")
        log.write("[bold #a371f7]  ─── Group Chat ─────────────────────────────────[/]")
        log.write("")
        log.write("  [#c9d1d9]Create:[/]  [#8b949e]/group create <name> <peer1> <peer2>…[/]")
        log.write("  [#c9d1d9]Example:[/] [#8b949e]/group create devteam alice bob[/]")
        log.write("")
        log.write("  [#484f58]Peer names are matched case-insensitively.[/]")
        log.write("  [#484f58]All peers must be online at creation time.[/]")
        log.write("")

    def action_focus_input(self) -> None:
        self.query_one("#message-input", Input).focus()

    def action_toggle_focus(self) -> None:
        """Toggle focus between sidebar contacts list and message input."""
        input_widget = self.query_one("#message-input", Input)
        contacts_list = self.query_one("#contacts-list", ListView)

        if input_widget.has_focus:
            contacts_list.focus()
        else:
            input_widget.focus()

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
        self.log_to_chat(
            f"[bold #3fb950]● Peer online:[/] [bold #c9d1d9]{name}[/] "
            f"[#484f58]({ip}:{port})[/]"
        )
        self.refresh_sidebar()

    def handle_peer_removed(self, peer_id: str):
        pinfo = self.network_manager.peers.get(peer_id)
        name = pinfo["name"] if pinfo else peer_id[:12]
        self.log_to_chat(
            f"[#484f58]○ Peer offline:[/] [#8b949e]{name}[/]"
        )
        self.refresh_sidebar()

    def handle_message_received(self, peer_id: str, peer_name: str, text: str, timestamp: float):
        self._msg_received += 1
        self.log_to_chat(
            f"[bold #79c0ff]{peer_name} ▸[/] [#f0f6fc]{text}[/]",
            target=f"peer:{peer_id}"
        )

    def handle_group_message_received(self, peer_id: str, peer_name: str, group_id: str, group_name: str, text: str, timestamp: float):
        self._msg_received += 1
        target = f"group:{group_id}"
        if group_id not in self.groups:
            self.groups[group_id] = {
                "name": group_name,
                "members": [peer_id, self.network_manager.device_id]
            }
            self.refresh_sidebar()

        self.log_to_chat(
            f"[bold #a371f7]{peer_name} ▸[/] [#f0f6fc]{text}[/]",
            target=target
        )

    def handle_file_offer_received(self, peer_id: str, peer_name: str, file_name: str, file_size: int, transfer_id: str):
        size_str = self._format_file_size(file_size)
        self.active_incoming_offer = (peer_id, transfer_id, file_name, file_size)

        log = self.query_one("#chat-log", RichLog)
        log.write("")
        log.write("[bold #e3b341]  ┌── 📥 Incoming File ──────────────────────────────┐[/]")
        log.write(f"[#e3b341]  │[/]  [#c9d1d9]From:[/]  [bold #f0f6fc]{peer_name}[/]")
        log.write(f"[#e3b341]  │[/]  [#c9d1d9]File:[/]  [bold #f0f6fc]{file_name}[/] [#484f58]({size_str})[/]")
        log.write(f"[#e3b341]  │[/]")
        log.write(f"[#e3b341]  │[/]  [bold #3fb950]/accept[/]  to download")
        log.write(f"[#e3b341]  │[/]  [bold #f85149]/reject[/]  to decline")
        log.write("[bold #e3b341]  └──────────────────────────────────────────────────┘[/]")
        log.write("")

    def handle_file_offer_accepted(self, peer_id: str, transfer_id: str, file_port: int):
        self.log_to_chat(
            "[bold #3fb950]✓ Peer accepted - uploading...[/]",
            target=self.current_chat_target
        )
        self.network_manager.start_file_upload(peer_id, transfer_id, file_port)

    def handle_file_offer_rejected(self, peer_id: str, transfer_id: str):
        self.log_to_chat(
            "[#e3b341]↩ File offer declined by peer[/]",
            target=self.current_chat_target
        )

    def handle_file_progress(self, transfer_id: str, bytes_transferred: int, bytes_total: int):
        pct = int((bytes_transferred / bytes_total) * 100) if bytes_total > 0 else 100
        # Visual progress bar - update at 10% intervals to avoid flooding
        filled = pct // 5
        bar = "█" * filled + "░" * (20 - filled)
        size_done = self._format_file_size(bytes_transferred)
        size_total = self._format_file_size(bytes_total)
        if pct % 10 == 0:
            self.log_to_chat(
                f"[#58a6ff]  ┃{bar}┃ {pct}%  "
                f"[#484f58]{size_done} / {size_total}[/][/]"
            )

    def handle_file_completed(self, transfer_id: str, file_path: str):
        self.log_to_chat("")
        self.log_to_chat(
            f"[bold #3fb950]  ✓ Transfer complete![/]"
        )
        self.log_to_chat(
            f"  [#8b949e]Saved to:[/] [#c9d1d9]{file_path}[/]"
        )
        self.log_to_chat("")

    def handle_file_failed(self, transfer_id: str, error_msg: str):
        self.log_to_chat(
            f"[bold #f85149]  ✗ Transfer failed:[/] [#f85149]{error_msg}[/]"
        )

    def on_unmount(self) -> None:
        if self._refresh_timer:
            self._refresh_timer.stop()
        self.discovery_service.stop()
        self.network_manager.stop()


def parse_args():
    parser = argparse.ArgumentParser(
        description="ZeroNet - Secure P2P LAN Messenger (TUI)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                         Start with hostname as username
  %(prog)s --name Alice            Start as "Alice"
  %(prog)s --name Bob --port 54322 Start as "Bob" on port 54322
        """
    )
    parser.add_argument(
        "--name", type=str, default=None,
        help="Display username (defaults to system hostname)"
    )
    parser.add_argument(
        "--port", type=int, default=54321,
        help="TCP listening port (default: 54321)"
    )
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
