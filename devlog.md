### What did you make?
I built ZeroNet, a completely decentralized, zero configuration Local Area Network messenger with a nostalgic Windows 95 Graphical Interface and a dark themed terminal interface. It automatically finds users on your WiFi and establishes direct, end to end encrypted connections.

### What was challenging?
The hardest part was solving network race conditions without a central server. I had to design a deterministic tie breaking system using unique device IDs to prevent duplicate connections when two peers discover each other simultaneously.

### What are you proud of?
I am most proud of the custom PyQt6 GUI. I spent hours customizing the stylesheets to perfectly recreate the classic Windows 95 and ICQ aesthetic with gray panels, sharp bevels, and pixel fonts.

### What should people know so they can test your project?
ZeroNet requires zero configuration to use. Just run the app on two computers connected to the same WiFi network, and they will automatically discover each other and exchange cryptographic keys.
