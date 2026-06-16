import sys
import os
import argparse
import socket
import uuid
import logging

# Configure logging early
logging.basicConfig(
    level=logging.INFO,
    format="[%(name)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Fix Qt platform plugin path on macOS (venv installs)
# Must be done before any Qt imports
try:
    import PyQt6
    _qt_base = os.path.dirname(PyQt6.__file__)
    _qt_plugins = os.path.join(_qt_base, "Qt6", "plugins")
    if not os.path.isdir(_qt_plugins):
        _qt_plugins = os.path.join(_qt_base, "Qt", "plugins")
    if os.path.isdir(_qt_plugins):
        os.environ["QT_PLUGIN_PATH"] = _qt_plugins
except ImportError:
    logger.error("PyQt6 is not installed. Install it with: uv add PyQt6")
    sys.exit(1)

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
    device_id = f"dev_{uuid.uuid4().hex[:12]}_{username.replace(' ', '_')}"

    logger.info("Starting ZeroNet for user: %s (%s)", username, device_id)

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
