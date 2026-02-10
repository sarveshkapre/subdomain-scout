from __future__ import annotations

import json
import re
import socketserver
import struct
import subprocess
import sys
import threading
from pathlib import Path
from typing import Final, Iterator

import pytest

from subdomain_scout.dns_client import load_nameservers_file, parse_nameserver


def test_parse_nameserver_ipv4_and_port() -> None:
    assert parse_nameserver("1.1.1.1") == ("1.1.1.1", 53)
    assert parse_nameserver("1.1.1.1:5353") == ("1.1.1.1", 5353)


def test_parse_nameserver_ipv6_bracketed() -> None:
    assert parse_nameserver("[2606:4700:4700::1111]") == ("2606:4700:4700::1111", 53)
    assert parse_nameserver("[2606:4700:4700::1111]:5353") == ("2606:4700:4700::1111", 5353)


def test_parse_nameserver_ipv6_unbracketed_no_port() -> None:
    assert parse_nameserver("2606:4700:4700::1111") == ("2606:4700:4700::1111", 53)


def test_load_nameservers_file_skips_comments_and_dedupes(tmp_path: Path) -> None:
    p = tmp_path / "resolvers.txt"
    p.write_text(
        "\n# comment\n1.1.1.1\n1.1.1.1 # dup\n[2606:4700:4700::1111]:53\n",
        encoding="utf-8",
    )
    assert load_nameservers_file(p) == [("1.1.1.1", 53), ("2606:4700:4700::1111", 53)]


def test_load_nameservers_file_errors_on_empty(tmp_path: Path) -> None:
    p = tmp_path / "resolvers.txt"
    p.write_text("# only comments\n\n", encoding="utf-8")
    with pytest.raises(ValueError, match=re.escape(f"resolver file {p} contains no valid entries")):
        load_nameservers_file(p)


class _DnsHandler(socketserver.BaseRequestHandler):
    A_RDATA: Final[bytes] = b"\x01\x02\x03\x04"  # 1.2.3.4
    CNAME_TO_A: Final[bytes] = b"\x01a\x03res\x04test\x00"  # a.res.test
    CNAME_TO_MISSING: Final[bytes] = b"\x07missing\x03res\x04test\x00"  # missing.res.test

    def handle(self) -> None:
        data, sock = self.request
        if len(data) < 12:
            return
        rid = struct.unpack("!H", data[:2])[0]

        try:
            qname, qtype, qclass, qend = _parse_question(data)
        except ValueError:
            return

        question = data[12:qend]

        if qclass != 1:
            # REFUSED
            hdr = struct.pack("!HHHHHH", rid, 0x8185, 1, 0, 0, 0)
            sock.sendto(hdr + question, self.client_address)
            return

        if qname == "a.res.test" and qtype == 1:
            hdr = struct.pack("!HHHHHH", rid, 0x8180, 1, 1, 0, 0)
            # NAME pointer to offset 12
            ans = (
                b"\xc0\x0c"
                + struct.pack("!H", 1)  # TYPE A
                + struct.pack("!H", 1)  # CLASS IN
                + struct.pack("!I", 60)  # TTL
                + struct.pack("!H", len(self.A_RDATA))
                + self.A_RDATA
            )
            sock.sendto(hdr + question + ans, self.client_address)
            return

        if qname == "a.res.test" and qtype == 28:
            # NOERROR, empty AAAA
            hdr = struct.pack("!HHHHHH", rid, 0x8180, 1, 0, 0, 0)
            sock.sendto(hdr + question, self.client_address)
            return

        if qname == "b.res.test" and qtype in {1, 28}:
            # Return only a CNAME (no A/AAAA); client should follow to a.res.test.
            hdr = struct.pack("!HHHHHH", rid, 0x8180, 1, 1, 0, 0)
            ans = (
                b"\xc0\x0c"
                + struct.pack("!H", 5)  # TYPE CNAME
                + struct.pack("!H", 1)  # CLASS IN
                + struct.pack("!I", 60)  # TTL
                + struct.pack("!H", len(self.CNAME_TO_A))
                + self.CNAME_TO_A
            )
            sock.sendto(hdr + question + ans, self.client_address)
            return

        if qname == "d.res.test" and qtype in {1, 28}:
            # CNAME-only response that points to a missing name; should be surfaced as status=cname
            # when --include-cname is enabled.
            hdr = struct.pack("!HHHHHH", rid, 0x8180, 1, 1, 0, 0)
            ans = (
                b"\xc0\x0c"
                + struct.pack("!H", 5)  # TYPE CNAME
                + struct.pack("!H", 1)  # CLASS IN
                + struct.pack("!I", 60)  # TTL
                + struct.pack("!H", len(self.CNAME_TO_MISSING))
                + self.CNAME_TO_MISSING
            )
            sock.sendto(hdr + question + ans, self.client_address)
            return

        # NXDOMAIN for everything else.
        hdr = struct.pack("!HHHHHH", rid, 0x8183, 1, 0, 0, 0)
        sock.sendto(hdr + question, self.client_address)


def _parse_question(data: bytes) -> tuple[str, int, int, int]:
    off = 12
    labels: list[str] = []
    while True:
        if off >= len(data):
            raise ValueError("truncated qname")
        ln = data[off]
        off += 1
        if ln == 0:
            break
        if off + ln > len(data):
            raise ValueError("truncated label")
        labels.append(data[off : off + ln].decode("ascii", errors="ignore"))
        off += ln
    if off + 4 > len(data):
        raise ValueError("truncated qtype/qclass")
    qtype, qclass = struct.unpack("!HH", data[off : off + 4])
    off += 4
    return ".".join(labels).lower(), int(qtype), int(qclass), off


@pytest.fixture()
def dns_server() -> Iterator[tuple[str, int]]:
    server = socketserver.UDPServer(("127.0.0.1", 0), _DnsHandler)
    host, port = server.server_address
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        yield str(host), int(port)
    finally:
        server.shutdown()
        server.server_close()
        t.join(timeout=1)


def test_cli_scan_with_custom_resolver(tmp_path: Path, dns_server: tuple[str, int]) -> None:
    host, port = dns_server
    wordlist = tmp_path / "words.txt"
    wordlist.write_text("a\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "subdomain_scout",
            "scan",
            "--domain",
            "res.test",
            "--wordlist",
            str(wordlist),
            "--out",
            "-",
            "--only-resolved",
            "--resolver",
            f"{host}:{port}",
            "--timeout",
            "0.2",
            "--concurrency",
            "1",
            "--summary-json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    record = json.loads(proc.stdout.strip())
    assert record["subdomain"] == "a.res.test"
    assert record["status"] == "resolved"
    assert record["ips"] == ["1.2.3.4"]
    summary = json.loads(proc.stderr.strip())
    assert summary["attempted"] == 1
    assert summary["resolved"] == 1


def test_cli_scan_with_custom_resolver_follows_cname(
    tmp_path: Path, dns_server: tuple[str, int]
) -> None:
    host, port = dns_server
    wordlist = tmp_path / "words.txt"
    wordlist.write_text("b\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "subdomain_scout",
            "scan",
            "--domain",
            "res.test",
            "--wordlist",
            str(wordlist),
            "--out",
            "-",
            "--only-resolved",
            "--resolver",
            f"{host}:{port}",
            "--timeout",
            "0.2",
            "--concurrency",
            "1",
            "--summary-json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    record = json.loads(proc.stdout.strip())
    assert record["subdomain"] == "b.res.test"
    assert record["status"] == "resolved"
    assert record["ips"] == ["1.2.3.4"]


def test_cli_scan_include_cname_emits_chain(tmp_path: Path, dns_server: tuple[str, int]) -> None:
    host, port = dns_server
    wordlist = tmp_path / "words.txt"
    wordlist.write_text("b\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "subdomain_scout",
            "scan",
            "--domain",
            "res.test",
            "--wordlist",
            str(wordlist),
            "--out",
            "-",
            "--only-resolved",
            "--include-cname",
            "--resolver",
            f"{host}:{port}",
            "--timeout",
            "0.2",
            "--concurrency",
            "1",
            "--summary-json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    record = json.loads(proc.stdout.strip())
    assert record["subdomain"] == "b.res.test"
    assert record["status"] == "resolved"
    assert record["ips"] == ["1.2.3.4"]
    assert record["cnames"] == ["a.res.test"]
    summary = json.loads(proc.stderr.strip())
    assert summary["attempted"] == 1
    assert summary["resolved"] == 1
    assert summary["cname"] == 0


def test_cli_scan_include_cname_classifies_cname_only(
    tmp_path: Path, dns_server: tuple[str, int]
) -> None:
    host, port = dns_server
    wordlist = tmp_path / "words.txt"
    wordlist.write_text("d\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "subdomain_scout",
            "scan",
            "--domain",
            "res.test",
            "--wordlist",
            str(wordlist),
            "--out",
            "-",
            "--status",
            "cname",
            "--include-cname",
            "--resolver",
            f"{host}:{port}",
            "--timeout",
            "0.2",
            "--concurrency",
            "1",
            "--summary-json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    record = json.loads(proc.stdout.strip())
    assert record["subdomain"] == "d.res.test"
    assert record["status"] == "cname"
    assert record["ips"] == []
    assert record["cnames"] == ["missing.res.test"]
    summary = json.loads(proc.stderr.strip())
    assert summary["attempted"] == 1
    assert summary["cname"] == 1


def test_cli_scan_include_cname_requires_resolver(tmp_path: Path) -> None:
    wordlist = tmp_path / "words.txt"
    wordlist.write_text("www\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "subdomain_scout",
            "scan",
            "--domain",
            "invalid.test",
            "--wordlist",
            str(wordlist),
            "--out",
            "-",
            "--include-cname",
            "--timeout",
            "0.1",
            "--concurrency",
            "1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2
    assert "requires --resolver/--resolver-file" in proc.stderr


def test_cli_scan_with_resolver_file(tmp_path: Path, dns_server: tuple[str, int]) -> None:
    host, port = dns_server
    wordlist = tmp_path / "words.txt"
    wordlist.write_text("a\n", encoding="utf-8")

    resolvers = tmp_path / "resolvers.txt"
    resolvers.write_text(f"{host}:{port}\n", encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "subdomain_scout",
            "scan",
            "--domain",
            "res.test",
            "--wordlist",
            str(wordlist),
            "--out",
            "-",
            "--only-resolved",
            "--resolver-file",
            str(resolvers),
            "--timeout",
            "0.2",
            "--concurrency",
            "1",
            "--summary-json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    record = json.loads(proc.stdout.strip())
    assert record["subdomain"] == "a.res.test"
    assert record["status"] == "resolved"
    assert record["ips"] == ["1.2.3.4"]
