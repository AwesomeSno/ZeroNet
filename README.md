# 🌐 ZeroNet Messenger

> A serverless, peer-to-peer, end-to-end encrypted LAN messaging & file-sharing application.

---

ZeroNet Messenger enables direct, secure communication between devices on a local area network (LAN) without relying on external servers, third-party databases, or cloud brokers.

## ✨ Features

- **📡 Zero-Configuration Discovery**: Automatically finds nearby ZeroNet devices using mDNS — no IP addresses to configure
- **🔒 End-to-End Encryption**: ECDH key exchange + Fernet symmetric encryption — no one can read your messages
- **💬 Real-Time Chat**: Direct P2P messaging over persistent TCP connections
- **👥 Group Chats**: Full-mesh group conversations where each message is individually encrypted per member
- **📁 File Sharing**: Stream files of any size with live progress bars, encrypted in transit
- **🖥️ Terminal UI**: Beautiful GitHub Dark-themed TUI built with Textual

---

## 🚀 Installation

### Prerequisites
- [Python 3.10+](https://www.python.org/)
- [uv](https://github.com/astral-sh/uv) (Python package manager)

### Setup
```bash
git clone git@github.com:AwesomeSno/ZeroNet.git
cd ZeroNet
uv sync
```

---

## 🖥️ How to Launch

### Start the TUI (Terminal Interface)
```bash
PYTHONPATH=. uv run python -m zeronet.tui
```

### Start with a Custom Name
```bash
PYTHONPATH=. uv run python -m zeronet.tui --name "Alice"
```

### Start on a Custom Port (for running multiple instances)
```bash
PYTHONPATH=. uv run python -m zeronet.tui --name "Bob" --port 54322
```

### Start the GUI (PyQt6 — alternative)
```bash
PYTHONPATH=. uv run python -m zeronet.main
```

---

## 📖 How to Use ZeroNet (Step-by-Step Guide)

When you launch ZeroNet, you'll see a terminal interface with three areas:

```
┌──────────────────────────────────────────────────────────────────┐
│ ◆ ZeroNet                                    ● Online │ 192.168… │  ← Title Bar
├──────────────┬───────────────────────────────────────────────────┤
│              │                                                   │
│  LEFT        │  CHAT LOG                                         │
│  SIDEBAR     │  (messages appear here)                           │
│              │                                                   │
│  (peers &    │                                                   │
│   groups     │                                                   │
│   appear     │                                                   │
│   here)      │                                                   │
│              ├═══════════════════════════════════════════════════╡
│              │ ▸ TYPE HERE: [ type your message here...       ]  │  ← INPUT BAR
├──────────────┴───────────────────────────────────────────────────┤
│ 192.168.1.5:54321 │ 🔒 E2EE │ 1↑ 0↓ │ 💡 Tip…                  │  ← Status Bar
└──────────────────────────────────────────────────────────────────┘
```

### Step 1: Wait for Peers

When you start ZeroNet, it automatically scans your local network using mDNS. Any other device running ZeroNet on the same Wi-Fi/Ethernet will appear in the **left sidebar** within a few seconds.

**To test locally**, open a second terminal and start another instance:
```bash
PYTHONPATH=. uv run python -m zeronet.tui --name "Bob" --port 54322
```

### Step 2: Select a Peer

**Click** on a peer name in the left sidebar (or use arrow keys + Enter). This opens their chat and automatically performs a secure key exchange.

The chat header will update to show:
- Peer name and online status
- Their IP address
- Encryption badge (🔒 ECDH + Fernet)

### Step 3: Type and Send a Message

1. Look for the **green-bordered input bar** at the very bottom of the screen. It says `▸ TYPE HERE:`.
2. **Click** in it (or press `Escape` to focus it)
3. **Type** your message
4. Press **Enter** to send

Your messages appear as `You ▸ hello` and incoming messages appear as `PeerName ▸ hey there`.

### Step 4: Send a File

While chatting with a peer, type a `/file` command in the input bar:

```
/file ~/Documents/photo.jpg
```

The peer will see a file offer card and can accept or reject it.

### Step 5: Create a Group Chat

```
/group create devteam alice bob
```

This creates a group called "devteam" with peers named "alice" and "bob". Peer names are matched case-insensitively. The group appears in your sidebar.

---

## 📟 All Commands

Type these in the **input bar** at the bottom of the screen:

### General
| Command | What it does | Example |
|---------|-------------|---------|
| `/help` | Show all commands and shortcuts | `/help` |
| `/peers` | List all discovered devices | `/peers` |
| `/status` | Show session stats (uptime, messages, encryption) | `/status` |
| `/whoami` | Show your identity and network address | `/whoami` |
| `/ping` | Check if a specific peer is reachable | `/ping alice` |
| `/clear` | Clear the current chat window | `/clear` |

### Messaging & Groups
| Command | What it does | Example |
|---------|-------------|---------|
| *(just type)* | Send a message to selected peer | `hello there!` |
| `/group create` | Create a group chat | `/group create team alice bob` |

### File Transfer
| Command | What it does | Example |
|---------|-------------|---------|
| `/file` | Send a file to the current peer | `/file ~/photo.jpg` |
| `/accept` | Accept an incoming file offer | `/accept` |
| `/reject` | Decline an incoming file offer | `/reject` |

> **Note:** `~/` is expanded to your home directory. You can only send files, not directories.

---

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **Ctrl+Q** | Quit ZeroNet |
| **Ctrl+H** | Show help |
| **Ctrl+G** | Show group creation help |
| **Ctrl+P** | List discovered peers |
| **Ctrl+L** | Clear chat |
| **Tab** | Toggle focus between sidebar and input bar |
| **Escape** | Focus the input bar |
| **Enter** | Send message / run command |

---

## 🔒 How Encryption Works

1. When you connect to a peer, both devices generate **ephemeral ECDH key pairs** (secp256r1)
2. Public keys are exchanged over the network
3. Both sides independently derive a **shared secret** using ECDH
4. The shared secret is passed through **HKDF (HMAC-SHA256)** to derive a symmetric Fernet key
5. All messages and files are encrypted/decrypted using **Fernet symmetric encryption**
6. Raw ECDH keys are discarded after the session key is derived

**No encryption keys are ever transmitted in plaintext.** An attacker sniffing your network only sees ciphertext.

---

## ⚙️ Architecture

```
         ┌────────────────────────────────────────────┐
         │          Textual TUI / PyQt6 GUI           │
         └────────────────┬───────────────────────────┘
                          │  (Callbacks / Qt Signals)
                          ▼
         ┌────────────────┴───────────────────────────┐
         │            Network Manager                 │
         ├──────┬──────────────────┬──────────────────┤
         │      │                  │                  │
         ▼      ▼                  ▼                  ▼
    ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
    │Discovery│ │TCP Listen│ │Heartbeat │ │Key Exchange  │
    │(mDNS)   │ │(port)    │ │(30s)     │ │(ECDH + HKDF) │
    └─────────┘ └──────────┘ └──────────┘ └──────────────┘
```

- **mDNS Discovery**: Broadcasts `_zeronet._tcp.local.` on the network
- **Heartbeat**: Every 30 seconds, dead connections are detected and cleaned up
- **Connection Retry**: Failed connections are retried 3 times with exponential backoff
- **Payload Framing**: `[4B metadata length][4B payload length][JSON metadata][encrypted payload]`

---

## 🧑‍💻 Testing on One Machine

To simulate two users chatting, open **two terminal windows**:

**Terminal 1:**
```bash
cd ZeroNet
PYTHONPATH=. uv run python -m zeronet.tui --name "Alice" --port 54321
```

**Terminal 2:**
```bash
cd ZeroNet
PYTHONPATH=. uv run python -m zeronet.tui --name "Bob" --port 54322
```

Within seconds, "Alice" will appear in Bob's sidebar and vice versa. Click the peer name and start chatting!

---

## 🧪 Running Tests

```bash
PYTHONPATH=. uv run pytest -v
```

---

## 🛠️ Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| TUI Framework | Textual |
| GUI Framework | PyQt6 |
| Discovery | Zeroconf (mDNS) |
| Network | TCP Sockets (custom framing) |
| Encryption | ECDH (secp256r1) + HKDF + Fernet |
| Package Manager | uv |

