import socket
import platform
import datetime

PORT = 8766
MAGIC = b"BAZOR_DISCOVER_V1"
hostname = platform.node() or "BAZOR-PC"

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("0.0.0.0", PORT))

print("=" * 58)
print(" BAZOR PC RELAY - DETECTION MOBILE")
print("=" * 58)
print(f"PC       : {hostname}")
print(f"UDP      : {PORT}")
print("Etat     : EN LIGNE")
print("Ollama   : NON EXPOSE")
print("Fermer cette fenetre pour arreter le relais.")
print("=" * 58)

while True:
    data, addr = sock.recvfrom(512)
    if data.strip() == MAGIC:
        reply = f"BAZOR_PC_OK|{hostname}".encode("utf-8")
        sock.sendto(reply, addr)
        now = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] BAZOR Mobile detecte depuis {addr[0]}")
