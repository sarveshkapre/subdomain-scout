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


@dataclass(frozen=True)
class ResolvedHost:
    ips: list[str]
    cnames: list[str]
    record_types: list[str]
    ttl_min: int | None
    ttl_max: int | None
    canonical_target: str | None


_QTYPE_LABELS = {1: "A", 28: "AAAA"}
_RECORD_TYPE_ORDER = ("A", "AAAA", "CNAME")


def _ordered_record_types(values: set[str]) -> list[str]:
    return [record_type for record_type in _RECORD_TYPE_ORDER if record_type in values]


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
    return resolve_host_details(name, nameservers=nameservers, timeout=timeout).ips


def resolve_host(
    name: str,
    *,
    nameservers: Sequence[tuple[str, int]],
    timeout: float,
    max_cname_depth: int = 8,
) -> tuple[list[str], list[str]]:
    details = resolve_host_details(
        name,
        nameservers=nameservers,
        timeout=timeout,
        max_cname_depth=max_cname_depth,
    )
    return details.ips, details.cnames


def resolve_host_details(
    name: str,
    *,
    nameservers: Sequence[tuple[str, int]],
    timeout: float,
    max_cname_depth: int = 8,
) -> ResolvedHost:
    if timeout <= 0:
        raise ValueError("timeout must be > 0")
    if not nameservers:
        raise ValueError("nameservers must be non-empty")
    if max_cname_depth < 0:
        raise ValueError("max_cname_depth must be >= 0")

    ips: list[str] = []
    seen: set[str] = set()
    cnames_chain: list[str] = []
    record_types_seen: set[str] = set()
    ttl_values: list[int] = []

    # Query both A and AAAA for parity with getaddrinfo(). If we get a CNAME-only
    # response, follow the chain up to `max_cname_depth`.
    current = str(name).strip().strip(".").lower()
    seen_names: set[str] = {current}

    for _ in range(max_cname_depth + 1):
        observed_cnames: list[str] = []

        for qtype in (1, 28):  # A, AAAA
            resp = _query(
                current,
                qtype=qtype,
                nameservers=nameservers,
                timeout=timeout,
            )
            for cname in resp.cnames:
                if cname in observed_cnames:
                    continue
                observed_cnames.append(cname)
            if resp.answers:
                record_types_seen.add(_QTYPE_LABELS[qtype])
                ttl_values.extend(resp.answer_ttls)
            for ip in resp.answers:
                if ip in seen:
                    continue
                seen.add(ip)
                ips.append(ip)

        primary_cname = observed_cnames[0].strip().strip(".").lower() if observed_cnames else ""
        if primary_cname and (not cnames_chain or cnames_chain[-1] != primary_cname):
            cnames_chain.append(primary_cname)
        if observed_cnames:
            record_types_seen.add("CNAME")

        canonical_target = cnames_chain[-1] if cnames_chain else None
        ttl_min = min(ttl_values) if ttl_values else None
        ttl_max = max(ttl_values) if ttl_values else None

        if ips:
            return ResolvedHost(
                ips=ips,
                cnames=cnames_chain,
                record_types=_ordered_record_types(record_types_seen),
                ttl_min=ttl_min,
                ttl_max=ttl_max,
                canonical_target=canonical_target,
            )

        if not primary_cname:
            return ResolvedHost(
                ips=[],
                cnames=cnames_chain,
                record_types=_ordered_record_types(record_types_seen),
                ttl_min=ttl_min,
                ttl_max=ttl_max,
                canonical_target=canonical_target,
            )

        # Follow the first observed CNAME deterministically; record the chain for debugging/triage.
        nxt = primary_cname
        if nxt in seen_names:
            return ResolvedHost(
                ips=[],
                cnames=cnames_chain,
                record_types=_ordered_record_types(record_types_seen),
                ttl_min=ttl_min,
                ttl_max=ttl_max,
                canonical_target=canonical_target,
            )
        seen_names.add(nxt)
        current = nxt

    canonical_target = cnames_chain[-1] if cnames_chain else None
    ttl_min = min(ttl_values) if ttl_values else None
    ttl_max = max(ttl_values) if ttl_values else None
    return ResolvedHost(
        ips=[],
        cnames=cnames_chain,
        record_types=_ordered_record_types(record_types_seen),
        ttl_min=ttl_min,
        ttl_max=ttl_max,
        canonical_target=canonical_target,
    )


def _query_rrset(
    name: str,
    *,
    qtype: int,
    nameservers: Sequence[tuple[str, int]],
    timeout: float,
) -> list[str]:
    return _query(name, qtype=qtype, nameservers=nameservers, timeout=timeout).answers


def _query(
    name: str,
    *,
    qtype: int,
    nameservers: Sequence[tuple[str, int]],
    timeout: float,
) -> _DnsParsed:
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
                return resp
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
    cnames: list[str]
    answer_ttls: list[int]


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
    cnames: list[str] = []
    answer_ttls: list[int] = []
    for _ in range(an):
        offset = _skip_name(data, offset)
        if offset + 10 > len(data):
            raise ValueError("malformed dns answer header")
        rtype, rclass, ttl, rdlen = struct.unpack("!HHIH", data[offset : offset + 10])
        offset += 10
        if offset + rdlen > len(data):
            raise ValueError("malformed dns rdata")
        rdata_offset = offset
        rdata = data[rdata_offset : rdata_offset + rdlen]
        offset += rdlen

        if rclass != 1:
            continue
        if rtype == 5:
            # CNAME target is a compressed DNS name.
            target, _ = _decode_name(data, rdata_offset)
            target = target.strip(".").lower()
            if target:
                cnames.append(target)
            continue

        if rtype != qtype:
            continue
        if rtype == 1 and rdlen == 4:
            answers.append(socket.inet_ntoa(rdata))
            answer_ttls.append(int(ttl))
        elif rtype == 28 and rdlen == 16:
            answers.append(socket.inet_ntop(socket.AF_INET6, rdata))
            answer_ttls.append(int(ttl))

    return _DnsParsed(
        rcode=rcode,
        truncated=truncated,
        answers=answers,
        cnames=cnames,
        answer_ttls=answer_ttls,
    )


def _decode_name(msg: bytes, offset: int) -> tuple[str, int]:
    """
    Decode a possibly-compressed DNS name at `offset`.

    Returns (name, next_offset) where next_offset is where parsing should
    continue in the original message (i.e., after following any compression
    pointers).
    """
    labels: list[str] = []
    pos = offset
    end_offset: int | None = None

    for _ in range(256):  # hard stop on loops
        if pos >= len(msg):
            raise ValueError("name exceeds message length")
        length = msg[pos]
        if length == 0:
            pos += 1
            return ".".join(labels), (end_offset if end_offset is not None else pos)
        if (length & 0xC0) == 0xC0:
            if pos + 1 >= len(msg):
                raise ValueError("truncated compression pointer")
            ptr = ((length & 0x3F) << 8) | msg[pos + 1]
            if end_offset is None:
                end_offset = pos + 2
            pos = ptr
            continue
        if (length & 0xC0) != 0:
            raise ValueError("invalid label length (reserved bits set)")
        pos += 1
        if pos + length > len(msg):
            raise ValueError("truncated label")
        labels.append(msg[pos : pos + length].decode("utf-8", errors="strict"))
        pos += length

    raise ValueError("name compression loop detected")


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


__all__ = [
    "DnsQueryError",
    "ResolvedHost",
    "parse_nameserver",
    "resolve_host",
    "resolve_host_details",
    "resolve_ips",
]
