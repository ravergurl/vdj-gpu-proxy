import asyncio
import socket

TARGET = "192.168.1.104"
COMMON_PORTS = [
    21,
    22,
    23,
    25,
    53,
    80,
    110,
    135,
    139,
    143,
    443,
    445,
    993,
    995,
    1433,
    1521,
    3306,
    3389,
    5432,
    5900,
    5985,
    5986,
    8080,
    8443,
    8888,
    21115,
    21116,
    21117,
    21118,
    21119,
    50051,
    50052,
]


async def check_port(ip, port):
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port), timeout=2
        )
        writer.close()
        await writer.wait_closed()
        return port
    except:
        return None


async def main():
    print(f"Scanning {TARGET} for common ports...")
    tasks = [check_port(TARGET, p) for p in COMMON_PORTS]
    results = await asyncio.gather(*tasks)

    open_ports = [p for p in results if p]

    if open_ports:
        print(f"\n[+] OPEN PORTS FOUND: {open_ports}")
        for p in open_ports:
            print(f"    Port {p} OPEN")
    else:
        print("[-] No open ports found in common list")

    return open_ports


if __name__ == "__main__":
    asyncio.run(main())
