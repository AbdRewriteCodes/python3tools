import socket
import struct
import sys

def check_rmi(target, port=1099):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect((target, port))
        # send RMI header
        sock.send(b"JRMI\x00\x02K")
        ack = sock.recv(2)
        if ack != b"\x4e\x00":  # protocol ack
            print("[!] Not an RMI service")
            return
        # build DGC clean call (simplified)
        # object number 2, uid 0, operation 0, hash for DGC
        dgc_hash = 0xf6b6898d8bf28643
        call_data = struct.pack(">IIQIII", 0x50, 2, 0, 0, 0, 0)  # header
        call_data += struct.pack(">Q", dgc_hash)
        call_data += b"\x00"  # operation 0
        # arguments: empty array, long 0, object with URL, boolean false
        # simplified: send minimal valid call
        sock.send(call_data)
        resp = sock.recv(4096)
        if b"class loader disabled" in resp:
            print("[+] VULNERABLE - RMI class loader is enabled!")
        elif b"ClassNotFoundException" in resp:
            print("[+] VULNERABLE - remote class loading allowed (payload failed)")
        else:
            print("[-] Not vulnerable or unknown response")
    except Exception as e:
        print(f"[!] Error: {e}")
    finally:
        sock.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python rmi_check.py <target> [port]")
        sys.exit(1)
    target = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 1099
    check_rmi(target, port)
