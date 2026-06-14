# 🌐 ZeroNet Messenger
> A serverless, peer-to-peer, end-to-end encrypted LAN messaging & file-sharing application.

---

ZeroNet Messenger enables direct, secure communication between devices on a local area network (LAN) without relying on external servers, third-party databases, or cloud brokers. It combines modern UI aesthetics with military-grade end-to-end encryption.

## ✨ Features

- **📡 Zero-Configuration Discovery (mDNS)**: Automatically detects and connects with nearby ZeroNet nodes on your Wi-Fi or Ethernet network using Zeroconf/mDNS protocols. No IP addresses to manually configure.
- **🔒 True End-to-End Encryption (E2EE)**:
  - Direct peer connections perform automatic **ECDH (secp256r1)** key exchanges.
  - Generates secure session keys via **HKDF (HMAC-SHA256)** key derivation.
  - Encrypts all payloads (text, metadata, file streams) using symmetric **Fernet** cryptography.
- **💬 Real-Time P2P Chat**: Direct text messaging using persistent, threaded TCP sockets.
- **👥 Full-Mesh Group Chats**: Secure group conversations. Messages are securely mapped and transmitted directly to each online group member via individual E2EE peer sockets.
- **📁 Secure File Streaming**: Share documents, images, and folders. Large files are streamed in encrypted chunks on separate ephemeral ports, keeping the primary chat thread responsive and offering live transfer progress bars.
- **🎨 Glassmorphic Dark UI**: Custom-designed dark theme constructed using PyQt6 with clean, modern components, typography, and hover animations.

---

## 🛠️ Technology Stack

- **Core Engine**: Python 3.10+
- **Graphical Interface**: PyQt6 (Qt Widgets)
- **Local Service Discovery**: Zeroconf / mDNS
- **Network Protocol**: Custom-framed TCP Sockets
- **Security & Crypto**: `cryptography` (ECDH, HKDF, Fernet)

---

## 🚀 Getting Started

### Prerequisites
Make sure you have [Python 3](https://www.python.org/) and [uv](https://github.com/astral-sh/uv) (or `pip`) installed on your system.

### 1. Installation
Clone the repository and sync the dependencies inside a virtual environment using `uv`:
```bash
git clone git@github.com:AwesomeSno/ZeroNet.git
cd ZeroNet
uv sync
```

### 2. Running the GUI Application (PyQt6 Retro Theme)
Launch the GUI chat client:
```bash
PYTHONPATH=. uv run python -m zeronet.main
```

### 3. Running the TUI Application (Textual Terminal GUI)
Launch the TUI chat client in your terminal:
```bash
PYTHONPATH=. uv run python -m zeronet.tui
```

### 4. Local Multi-Device Testing
You can easily simulate multiple devices on your machine by starting another node with a different name and TCP port (using either GUI or TUI):

**Node A (Alice in TUI):**
```bash
PYTHONPATH=. uv run python -m zeronet.tui --name "Alice" --port 54321
```

**Node B (Bob in GUI):**
```bash
PYTHONPATH=. uv run python -m zeronet.main --name "Bob" --port 54322
```

---

## 🎮 How to Operate the App

Once you have multiple instances running on the network:

1. **View Contacts**:
   - The left sidebar lists all active contacts discovered on your network.
   - An active contact is prefixed with `[+]` (e.g., `[+] Alice`). If a peer disconnects, their status will update to `[-]`.
2. **Direct Secure Chat**:
   - Click a contact in the list. The chat panel will activate and perform an instant, secure E2EE key exchange.
   - Type your message in the bottom text box and click **Send** or press **Enter**.
   - Outgoing messages are prefix-wrapped in dark red (`<Me>`) and incoming messages in navy blue (e.g., `<Alice>`).
3. **Group Chats**:
   - Click **Create Group** at the bottom of the sidebar.
   - Enter a name for the group (e.g., "Dev Team").
   - Tick the checkboxes next to the online contacts you want to add and click **Ok**.
   - Your messages will be encrypted and broadcast directly to all group members via full-mesh P2P connections.
4. **File Sharing**:
   - Select a direct peer's chat window.
   - Click **📎 File** at the bottom left.
   - Select a file from your system.
   - The receiver will immediately see an **Incoming File** panel with **Accept** and **Reject** options.
   - If they click **Accept**, they will choose a save location, and the file will stream in encrypted blocks with a live progress bar.

### 📟 Operating in TUI Mode:
- **View Contacts**: Discovered peers will automatically show up on the left sidebar as `[+] Name`. Select them using your mouse or arrow keys.
- **Messaging**: Select a contact, type your message in the bottom input, and press **Enter**.
- **Group Chat**: Type `/group create <group_name> <peer_name_1> <peer_name_2> ...` to create a group. It will immediately appear on your sidebar list.
- **File Attachment**: Select a contact, type `/file <path_to_file>` to offer a file.
- **Accept/Reject File**: When you receive a file offer notification in the chat log, type `/accept` to download the file directly to your current directory (as `downloaded_<filename>`), or `/reject` to decline.
- **Quit TUI**: Press `q` to exit.

---

## ⚙️ Architecture

```
         +--------------------------------------------+
         |                PyQt6 UI                    |
         +--------------------+-----------------------+
                              | (Qt Signals)
                              v
         +--------------------+-----------------------+
         |            Network Manager                 |
         +------+--------------------+-------------+--+
                |                    |             |
                v                    v             v
       +-----------------+   +---------------+ +---------------+
       | Discovery       |   | TCP Listener  | | Key Exchange  |
       | (Zeroconf/mDNS) |   | (Port: 54321) | | (ECDH & HKDF) |
       +-----------------+   +---------------+ +---------------+
```

- **Discovery Layer**: ZeroNet broadcasts its active port and username on `_zeronet._tcp.local.`.
- **E2EE Key Exchange**: When Alice connects to Bob, both exchange their ephemeral public keys. They independently compute the shared secret, derive the Fernet key, and then discard the raw ECDH keys.
- **Payload Framing**:
  `[4-byte metadata length] [4-byte payload length] [JSON Metadata] [Encrypted Payload bytes]`

---

## 🧪 Running Unit Tests

To run the unit test suite covering key exchanges, encryption, and socket protocols:
```bash
PYTHONPATH=. uv run pytest
```
