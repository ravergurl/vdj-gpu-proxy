from smb.SMBConnection import SMBConnection
import socket


def test_smb(ip):
    print(f"[*] Testing SMB on {ip}...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        if s.connect_ex((ip, 445)) == 0:
            print(f"    [+] Port 445 is OPEN on {ip}")
            conn = SMBConnection("", "", "test", "test", use_ntlm_v2=True)
            if conn.connect(ip, 445, timeout=5):
                print(f"    [+] Connected to SMB on {ip}")
                print(f"    [+] Server Name: {conn.getServerName()}")
                conn.close()
        else:
            print(f"    [-] Port 445 is CLOSED on {ip}")
        s.close()
    except Exception as e:
        print(f"    [-] Error on {ip}: {e}")


test_smb("192.168.1.104")
