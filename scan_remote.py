import asyncio
import socket
import struct
import ipaddress
import time

SUBNET = "192.168.1.0/24"
PORTS = [445, 3389, 22, 135, 5357]
TIMEOUT = 1.0


class Scanner:
    def __init__(self):
        self.found_hosts = []

    async def check_port(self, ip, port):
        conn = asyncio.open_connection(str(ip), port)
        try:
            reader, writer = await asyncio.wait_for(conn, timeout=TIMEOUT)
            writer.close()
            await writer.wait_closed()
            return port
        except:
            return None

    def get_netbios_name(self, ip):
        header = struct.pack("!HHHHHH", 0x1337, 0x0000, 1, 0, 0, 0)
        query = (
            b"\x20"
            + b"\x43\x4b" * 15
            + b"\x41\x00"
            + struct.pack("!HH", 0x0021, 0x0001)
        )

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1.0)
        try:
            sock.sendto(header + query, (str(ip), 137))
            data, _ = sock.recvfrom(1024)
            return self.parse_netbios_response(data)
        except:
            return None
        finally:
            sock.close()

    def parse_netbios_response(self, data):
        try:
            num_names = data[56]
            offset = 57
            names = []
            for _ in range(num_names):
                name = (
                    data[offset : offset + 15].strip().decode("ascii", errors="ignore")
                )
                names.append(name)
                offset += 18
            return names
        except:
            return [
                s for s in data.decode("ascii", errors="ignore").split() if len(s) > 3
            ]

    async def scan_host(self, ip):
        open_ports = []
        tasks = [self.check_port(ip, p) for p in PORTS]
        results = await asyncio.gather(*tasks)
        for p in results:
            if p:
                open_ports.append(p)

        loop = asyncio.get_running_loop()
        hostname = await loop.run_in_executor(None, self.get_netbios_name, ip)

        if open_ports or hostname:
            print(f"[+] FOUND: {ip}")
            if open_ports:
                print(f"    Ports: {open_ports}")
            if hostname:
                print(f"    Hostnames: {hostname}")
                for name in hostname:
                    if "KIIRO" in name.upper() or "KURO" in name.upper():
                        print(f"    *** TARGET MATCH: {name} ***")
            self.found_hosts.append({"ip": ip, "ports": open_ports, "names": hostname})

    async def run(self):
        print(f"Scanning {SUBNET}...")
        network = ipaddress.ip_network(SUBNET)
        tasks = []
        semaphore = asyncio.Semaphore(200)

        async def sem_scan(ip):
            async with semaphore:
                await self.scan_host(ip)

        for ip in network.hosts():
            tasks.append(sem_scan(ip))

        await asyncio.gather(*tasks)
        print("Scan complete.")


if __name__ == "__main__":
    scanner = Scanner()
    asyncio.run(scanner.run())
