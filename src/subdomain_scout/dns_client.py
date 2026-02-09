from __future__ import annotations

import ipaddress
import socket
import secrets
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class DnsQueryError(Exception):
    message: str
    rcode: int | None = None

    def __str__(self) -> str:  # pragma: no cover - trivial
        if self.rcode is None:
            return self.message
        return f"{self.message} (rcode={self.rcode})"


def parse_nameserver(spec: str) -> tuple[str, int]:
    """
    Parse a nameserver spec into (ip, port).

    Supported:
      - "1.1.1.1"
      - "1.1.1.1:5353"
      - "2606:4700:4700::1111" (no port)
      - "[2606:4700:4700::1111]"
      - "[2606:4700:4700::1111]:5353"
    """
    raw = str(spec).strip()
    if not raw:
        raise ValueError("resolver must be non-empty")

    host = raw
    port = 53

    if raw.startswith("["):
        end = raw.find("]")
        if end == -1:
            raise ValueError("invalid resolver: missing ']'")
        host = raw[1:end].strip()
        rest = raw[end + 1 :].strip()
        if rest:
            if not rest.startswith(":"):
                raise ValueError("invalid resolver: unexpected trailing content after ']'")
            try:
                port = int(rest[1:])
            except ValueError as e:  # pragma: no cover
                raise ValueError("invalid resolver port") from e
    else:
        # IPv4 "a.b.c.d:port" or bare IP (v4/v6).
        if raw.count(":") == 1 and "." in raw:
            host_part, port_part = raw.split(":", 1)
            host = host_part.strip()
            try:
                port = int(port_part.strip())
            except ValueError as e:
                raise ValueError("invalid resolver port") from e

    try:
        ipaddress.ip_address(host)
    except ValueError as e:
        raise ValueError("invalid resolver IP address") from e
    if port < 1 or port > 65535:
        raise ValueError("invalid resolver port")

    return host, port


def load_nameservers_file(path: Path) -> list[tuple[str, int]]:
    """
    Load resolver IP[:port] entries from a file.

    - Skips blank lines and lines starting with '#'.
    - Allows inline comments after '#'.
    - Dedupes entries while preserving order.
    """
    entries: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()
    with path.open("r", encoding="utf-8") as fh:
        for lineno, raw_line in enumerate(fh, start=1):
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            spec = line.split(maxsplit=1)[0]
            try:
                ns = parse_nameserver(spec)
            except ValueError as e:
                raise ValueError(f"invalid resolver in {path}:{lineno}: {e}") from e
            if ns in seen:
                continue
            seen.add(ns)
            entries.append(ns)
    if not entries:
        raise ValueError(f"resolver file {path} contains no valid entries")
    return entries


def resolve_ips(
    name: str,
    *,
    nameservers: Sequence[tuple[str, int]],
    timeout: float,
) -> list[str]:
    if timeout <= 0:
        raise ValueError("timeout must be > 0")
    if not nameservers:
        raise ValueError("nameservers must be non-empty")

    ips: list[str] = []
    seen: set[str] = set()

    # Query both A and AAAA for parity with getaddrinfo(). We treat NXDOMAIN/NODATA
    # as "no results" and let the caller decide the final status.
    for qtype in (1, 28):  # A, AAAA
        items = _query_rrset(
            name,
            qtype=qtype,
            nameservers=nameservers,
            timeout=timeout,
        )
        for ip in items:
            if ip in seen:
                continue
            seen.add(ip)
            ips.append(ip)

    return ips


def _query_rrset(
    name: str,
    *,
    qtype: int,
    nameservers: Sequence[tuple[str, int]],
    timeout: float,
) -> list[str]:
    last_err: BaseException | None = None
    for host, port in nameservers:
        try:
            resp = _udp_query(
                host=host,
                port=port,
                qname=name,
                qtype=qtype,
                timeout=timeout,
            )
            if resp.truncated:
                # TCP fallback is intentionally minimal; it keeps resolver pinning usable
                # when UDP responses exceed limits.
                resp = _tcp_query(
                    host=host,
                    port=port,
                    qname=name,
                    qtype=qtype,
                    timeout=timeout,
                )
            if resp.rcode in {0, 3}:
                return resp.answers
            raise DnsQueryError("dns error response", rcode=resp.rcode)
        except (TimeoutError, OSError, ValueError, DnsQueryError) as e:
            last_err = e
            continue

    if last_err is None:  # pragma: no cover
        raise TimeoutError("dns query failed")
    if isinstance(last_err, TimeoutError):
        raise last_err
    if isinstance(last_err, DnsQueryError):
        raise last_err
    raise DnsQueryError(str(last_err))


@dataclass(frozen=True)
class _DnsParsed:
    rcode: int
    truncated: bool
    answers: list[str]


def _udp_query(
    *,
    host: str,
    port: int,
    qname: str,
    qtype: int,
    timeout: float,
) -> _DnsParsed:
    tid = _tid()
    msg = _build_query(tid=tid, qname=qname, qtype=qtype)
    with socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        s.sendto(msg, (host, port))
        data, _addr = s.recvfrom(4096)
    return _parse_response(data, tid=tid, qtype=qtype)


def _tcp_query(
    *,
    host: str,
    port: int,
    qname: str,
    qtype: int,
    timeout: float,
) -> _DnsParsed:
    tid = _tid()
    msg = _build_query(tid=tid, qname=qname, qtype=qtype)
    with socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect((host, port))
        s.sendall(struct.pack("!H", len(msg)) + msg)
        hdr = _recv_exact(s, 2)
        length = struct.unpack("!H", hdr)[0]
        data = _recv_exact(s, length)
    return _parse_response(data, tid=tid, qtype=qtype)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    chunks: list[bytes] = []
    remaining = n
    while remaining:
        part = sock.recv(remaining)
        if not part:
            raise OSError("unexpected EOF while reading DNS TCP response")
        chunks.append(part)
        remaining -= len(part)
    return b"".join(chunks)


def _tid() -> int:
    # Not a secret; used to correlate query/response.
    return int(secrets.randbits(16))


def _build_query(*, tid: int, qname: str, qtype: int) -> bytes:
    flags = 0x0100  # RD
    qdcount = 1
    header = struct.pack("!HHHHHH", tid, flags, qdcount, 0, 0, 0)
    qname_wire = _encode_qname(qname)
    question = qname_wire + struct.pack("!HH", qtype, 1)  # QCLASS=IN
    return header + question


def _encode_qname(name: str) -> bytes:
    parts = [p for p in str(name).strip(".").split(".") if p]
    out = bytearray()
    for part in parts:
        label = part.encode("utf-8", errors="strict")
        if len(label) > 63:
            raise ValueError("dns label too long")
        out.append(len(label))
        out.extend(label)
    out.append(0)
    return bytes(out)


def _parse_response(data: bytes, *, tid: int, qtype: int) -> _DnsParsed:
    if len(data) < 12:
        raise ValueError("short dns response")
    rid, flags, qd, an, _ns, _ar = struct.unpack("!HHHHHH", data[:12])
    if rid != tid:
        raise ValueError("dns transaction id mismatch")
    if (flags & 0x8000) == 0:
        raise ValueError("dns response missing QR flag")
    truncated = bool(flags & 0x0200)
    rcode = flags & 0x000F

    offset = 12
    for _ in range(qd):
        offset = _skip_name(data, offset)
        offset += 4
        if offset > len(data):
            raise ValueError("malformed dns question section")

    answers: list[str] = []
    for _ in range(an):
        offset = _skip_name(data, offset)
        if offset + 10 > len(data):
            raise ValueError("malformed dns answer header")
        rtype, rclass, _ttl, rdlen = struct.unpack("!HHIH", data[offset : offset + 10])
        offset += 10
        if offset + rdlen > len(data):
            raise ValueError("malformed dns rdata")
        rdata = data[offset : offset + rdlen]
        offset += rdlen

        if rclass != 1:
            continue
        if rtype != qtype:
            continue
        if rtype == 1 and rdlen == 4:
            answers.append(socket.inet_ntoa(rdata))
        elif rtype == 28 and rdlen == 16:
            answers.append(socket.inet_ntop(socket.AF_INET6, rdata))

    return _DnsParsed(rcode=rcode, truncated=truncated, answers=answers)


def _skip_name(msg: bytes, offset: int) -> int:
    # RFC 1035: labels or pointer compression.
    for _ in range(256):  # hard stop on loops
        if offset >= len(msg):
            raise ValueError("name exceeds message length")
        length = msg[offset]
        if length == 0:
            return offset + 1
        if (length & 0xC0) == 0xC0:
            if offset + 1 >= len(msg):
                raise ValueError("truncated compression pointer")
            return offset + 2
        offset += 1 + length
    raise ValueError("name compression loop detected")


__all__ = ["DnsQueryError", "parse_nameserver", "resolve_ips"]
