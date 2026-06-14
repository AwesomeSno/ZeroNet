import socket
from zeroconf import ServiceInfo, ServiceBrowser, Zeroconf, ServiceListener
from typing import Dict, Any

def get_local_ip() -> str:
    """
    Returns the primary local IP address of this device on the active network.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connect to a public broadcast address to find local route IP
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

class ZeroNetListener(ServiceListener):
    def __init__(self, manager):
        self.manager = manager

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        # Resolving updated service details
        self.add_service(zc, type_, name)

    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        # Fetch detailed service info
        info = zc.get_service_info(type_, name)
        if not info:
            return
            
        # Extract properties
        properties = {}
        for k, v in info.properties.items():
            key = k.decode('utf-8') if isinstance(k, bytes) else k
            val = v.decode('utf-8') if isinstance(v, bytes) else v
            properties[key] = val
            
        peer_id = properties.get("device_id")
        peer_username = properties.get("username", "Unknown User")
        
        # Don't discover ourselves
        if peer_id == self.manager.device_id:
            return
            
        # Get peer IP (zeroconf returns list of binary addresses)
        ip = None
        if info.addresses:
            ip = socket.inet_ntoa(info.addresses[0])
        else:
            return
            
        port = info.port
        
        print(f"[Discovery] Discovered peer: {peer_username} ({peer_id}) at {ip}:{port}")
        
        # Update NetworkManager's peer registry
        self.manager.peers[peer_id] = {
            "name": peer_username,
            "ip": ip,
            "port": port,
            "status": "online"
        }
        
        # Emit signal to GUI
        self.manager.signals.peer_discovered_signal.emit(peer_id, peer_username, ip, port)

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        # Service name is usually "{device_id}._zeronet._tcp.local."
        # We can extract the device_id from it
        parts = name.split(".")
        if not parts:
            return
        peer_id = parts[0]
        
        # Don't remove ourselves
        if peer_id == self.manager.device_id:
            return
            
        print(f"[Discovery] Removed peer: {peer_id}")
        
        # Update status or remove
        if peer_id in self.manager.peers:
            self.manager.peers[peer_id]["status"] = "offline"
            
        # Emit signal to GUI
        self.manager.signals.peer_removed_signal.emit(peer_id)


class DiscoveryService:
    def __init__(self, manager):
        self.manager = manager
        self.zeroconf = None
        self.browser = None
        self.service_info = None
        self.service_type = "_zeronet._tcp.local."

    def start(self):
        """
        Starts the Zeroconf publisher and browser.
        """
        self.zeroconf = Zeroconf()
        local_ip = get_local_ip()
        
        # Define properties for this device
        properties = {
            "device_id": self.manager.device_id,
            "username": self.manager.username
        }
        
        # Create ServiceInfo
        # Format name as: {device_id}._zeronet._tcp.local.
        service_name = f"{self.manager.device_id}.{self.service_type}"
        
        self.service_info = ServiceInfo(
            type_=self.service_type,
            name=service_name,
            addresses=[socket.inet_aton(local_ip)],
            port=self.manager.port,
            properties=properties,
            server=f"{self.manager.device_id}.local."
        )
        
        # Register service
        self.zeroconf.register_service(self.service_info)
        print(f"[DiscoveryService] Registered mDNS service: {service_name} at {local_ip}:{self.manager.port}")
        
        # Start browser to find other peers
        listener = ZeroNetListener(self.manager)
        self.browser = ServiceBrowser(self.zeroconf, self.service_type, listener)

    def stop(self):
        """
        Stops the browser and unregisters the service.
        """
        if self.browser:
            self.browser.cancel()
            self.browser = None
            
        if self.zeroconf:
            if self.service_info:
                try:
                    self.zeroconf.unregister_service(self.service_info)
                except Exception:
                    pass
                self.service_info = None
            self.zeroconf.close()
            self.zeroconf = None
        print("[DiscoveryService] Stopped mDNS service and browser")
