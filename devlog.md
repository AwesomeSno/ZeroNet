ZeroNet: The Final Update (Retro GUI + Production Ready!)

In my last devlog, I introduced ZeroNet: a serverless, peer to peer, end to end encrypted LAN messenger that runs entirely in the terminal. Since then, I've taken the project to the next level and built out the promised GUI, but with a massive twist!

### What did you make?
I built a completely decentralized, zero configuration Local Area Network messenger. It automatically finds other users on your WiFi using mDNS, and establishes direct peer to peer TCP connections that are end to end encrypted. It features both a sleek terminal interface (TUI) and a nostalgic Windows 95 Graphical Interface.

### What was challenging?
The hardest part was solving network race conditions. Because there is no central server to mediate connections, if Alice and Bob discovered each other at the exact same millisecond, they would both initiate connections simultaneously. This caused duplicate sockets and crashed the encryption layer. I had to design a deterministic tie breaking system where peers exchange unique device IDs, and the peer with the lower ID drops their outbound connection and accepts the incoming one. 

### What are you proud of?
I am most proud of the custom PyQt6 GUI. Instead of building a generic modern chat app, I spent hours customizing the stylesheets to perfectly recreate the classic Windows 95 and ICQ aesthetic, complete with gray panels, sharp bevels, and pixel fonts.

### What should people know so they can test your project?
ZeroNet requires zero configuration! Just run the app on two computers connected to the same WiFi network. They will automatically discover each other and exchange cryptographic keys.

Here is what's new in the final release of ZeroNet:

- A stunning Retro Windows 95 / ICQ themed Graphical Interface! I bypassed modern, boring UI trends and built a fully customized PyQt6 interface that looks straight out of the 90s, complete with classic bevels, gray panels, and pixel fonts.
- Bulletproof Networking: Solved complex race conditions! If two peers discover each other and try to connect at the exact same millisecond, ZeroNet now uses deterministic device ID tie breaking to drop the duplicate connection and keep the network stable.
- Upgraded Cryptography: Every single peer connection now generates a fresh, unique ephemeral secp256r1 keypair.
- Interactive Web Demo: I built a static GitHub Pages website with a CRT scanline effect and a simulated interactive terminal that mimics the real software's key exchange and encrypted chat.
- Cross platform Polish: Hunted down and fixed a nasty PyQt6 platform plugin bug on macOS (caused by experimental Python 3.14 environments) to ensure the app boots flawlessly everywhere.

ZeroNet is now a complete, production ready tool. You can chat securely on your local network using either the beautiful dark themed TUI or the nostalgic Windows 95 GUI. No servers. No cloud brokers. Just raw, encrypted, peer to peer communication. 

Check out the interactive demo on the GitHub page!
