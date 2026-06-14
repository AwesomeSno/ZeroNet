import sys
import argparse
import socket
import uuid
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from zeronet.network.connection import NetworkManager
from zeronet.network.discovery import DiscoveryService
from zeronet.ui.main_window import MainWindow

def parse_args():
    parser = argparse.ArgumentParser(description="ZeroNet Secure LAN Messenger")
    parser.add_argument("--name", type=str, default=None, help="Display username (defaults to hostname)")
    parser.add_argument("--port", type=int, default=54321, help="TCP Listening Port (defaults to 54321)")
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    
    # Establish username
    username = args.name
    if not username:
        username = socket.gethostname()
        
    # Generate unique device ID
    # In production, we'd persist this, but generating an ephemeral ID
    # on startup is perfectly fine for a serverless LAN chat.
    device_id = f"dev_{uuid.uuid4().hex[:12]}_{username.replace(' ', '_')}"
    
    print(f"[Main] Starting ZeroNet for user: {username} ({device_id})")
    
    # Initialize connection manager & discovery
    network_manager = NetworkManager(username, device_id, default_port=args.port)
    discovery_service = DiscoveryService(network_manager)
    
    # Start background networking threads
    network_manager.start()
    discovery_service.start()
    
    # Build & show GUI
    window = MainWindow(network_manager, discovery_service)
    window.show()
    
    # Execute application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
