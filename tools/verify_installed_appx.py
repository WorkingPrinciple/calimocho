"""Offline, read-only installed GamingApp integrity checks. Never grants token trust."""

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from tools.package_activation import identity


REPO = Path(__file__).resolve().parents[1]
STORE_EKU = "1.3.6.1.4.1.311.76.3.1"
TSA_EKU = "1.3.6.1.5.5.7.3.8"
TSA_ROOT_SHA256 = "df545bf919a2439c36983b54cdfc903dfa4f37d3996d8d84b4c31eec6f3c163e"
BLOCK_NS = "{http://schemas.microsoft.com/appx/2010/blockmap}"
SHA256_URI = "http://www.w3.org/2001/04/xmlenc#sha256"
MICROSOFT_SUBJECT = "CN=Microsoft Corporation,O=Microsoft Corporation,L=Redmond,ST=Washington,C=US"
MICROSOFT_PUBLISHER = "CN=Microsoft Corporation, O=Microsoft Corporation, L=Redmond, S=Washington, C=US"


def command(openssl, *args):
    result = subprocess.run([openssl, *map(str, args)], capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors="replace").strip())
    return result.stdout


def xml(data):
    if len(data) > 16 * 1024 * 1024:
        raise ValueError("Unsupported or oversized package XML")
    without_comments = re.sub(rb"<!--.*?-->", b"", data, flags=re.DOTALL)
    if b"<!" in without_comments or b"\0" in data:
        raise ValueError("Unsupported or oversized package XML")
    return ET.fromstring(data)


def der_nodes(data):
    """Read bounded, definite-length DER nodes, rejecting ambiguous encodings."""
    result = []
    offset = 0
    while offset < len(data):
        if len(data) - offset < 2 or data[offset] & 31 == 31:
            raise ValueError("Unsupported DER tag")
        tag, size = data[offset:offset + 2]
        offset += 2
        if size & 128:
            count = size & 127
            if not count or count > 4 or offset + count > len(data) or not data[offset]:
                raise ValueError("Invalid DER length")
            size = int.from_bytes(data[offset:offset + count], "big")
            offset += count
            if size < 128:
                raise ValueError("Noncanonical DER length")
        if offset + size > len(data):
            raise ValueError("Truncated DER")
        result.append((tag, data[offset:offset + size]))
        offset += size
    return result


def signed_digests(content):
    # OpenSSL PKCS7 outputs the Authenticode SEQUENCE body, not a CMS octet string.
    nodes = der_nodes(content)
    if len(nodes) != 2 or any(tag != 0x30 for tag, _ in nodes):
        raise ValueError("Unsupported AppX indirect-data structure")
    digest_info = der_nodes(nodes[1][1])
    if len(digest_info) != 2 or digest_info[0][0] != 0x30 or digest_info[1][0] != 4:
        raise ValueError("Unsupported AppX digest structure")
    if digest_info[0][1] != bytes.fromhex("06096086480165030402010500"):
        raise ValueError("Only signed SHA-256 AppX digests are supported")
    blob = digest_info[1][1]
    if len(blob) != 184 or blob[:4] != b"APPX":
        raise ValueError("Expected all five signed AppX digests")
    digests = {}
    for offset in range(4, len(blob), 36):
        name = blob[offset:offset + 4].decode("ascii")
        if name in digests:
            raise ValueError("Duplicate AppX digest")
        digests[name] = blob[offset + 4:offset + 36].hex()
    if set(digests) != {"AXPC", "AXCD", "AXCT", "AXBM", "AXCI"}:
        raise ValueError("Unknown or missing AppX digest")
    return digests


def oid(data):
    if not data:
        raise ValueError("Empty object identifier")
    parts = [min(data[0] // 40, 2), data[0] - min(data[0] // 40, 2) * 40]
    value = 0
    for byte in data[1:]:
        value = (value << 7) | (byte & 127)
        if not byte & 128:
            parts.append(value)
            value = 0
    if data[-1] & 128:
        raise ValueError("Truncated object identifier")
    return ".".join(map(str, parts))


def sequence(data):
    nodes = der_nodes(data)
    if len(nodes) != 1 or nodes[0][0] != 0x30:
        raise ValueError("Expected one DER sequence")
    return der_nodes(nodes[0][1])


def encode_der(tag, value):
    size = len(value)
    count = (size.bit_length() + 7) // 8
    length = bytes([size]) if size < 128 else bytes([128 + count]) + size.to_bytes(count, "big")
    return bytes([tag]) + length + value


def signature_timestamp(signature):
    outer = sequence(signature)
    if len(outer) != 2 or outer[0] != (6, bytes.fromhex("2a864886f70d010702")) or outer[1][0] != 0xa0:
        raise ValueError("Expected PKCS7 SignedData")
    signed_data = sequence(outer[1][1])
    if not signed_data or signed_data[-1][0] != 0x31:
        raise ValueError("Missing PKCS7 signer information")
    signers = der_nodes(signed_data[-1][1])
    if len(signers) != 1 or signers[0][0] != 0x30:
        raise ValueError("Require exactly one PKCS7 signer")
    info = der_nodes(signers[0][1])
    if len(info) != 7 or info[3][0] != 0xa0 or info[5][0] != 4 or info[6][0] != 0xa1:
        raise ValueError("Missing supported timestamp signature attributes")
    timestamps = []
    for tag, value in der_nodes(info[6][1]):
        fields = der_nodes(value)
        if tag != 0x30 or len(fields) != 2 or fields[0][0] != 6 or fields[1][0] != 0x31:
            raise ValueError("Malformed unsigned signature attribute")
        if oid(fields[0][1]) == "1.3.6.1.4.1.311.3.3.1":
            entries = der_nodes(fields[1][1])
            if len(entries) != 1 or entries[0][0] != 0x30:
                raise ValueError("Malformed RFC3161 timestamp token")
            timestamps.append(encode_der(*entries[0]))
    if len(timestamps) != 1:
        raise ValueError("Require one RFC3161 timestamp (legacy countersignatures unsupported)")
    return info[5][1], timestamps[0]


def timestamp_time(content):
    fields = sequence(content)
    if len(fields) < 5 or fields[4][0] != 0x18:
        raise ValueError("Missing RFC3161 genTime")
    text = fields[4][1].decode("ascii")
    if not re.fullmatch(r"\d{14}(?:\.\d{1,6})?Z", text):
        raise ValueError("Unsupported RFC3161 genTime")
    parsed = datetime.strptime(text, "%Y%m%d%H%M%S.%fZ" if "." in text else "%Y%m%d%H%M%SZ")
    parsed = parsed.replace(tzinfo=timezone.utc)
    if parsed > datetime.now(timezone.utc):
        raise ValueError("RFC3161 timestamp is in the future")
    return int(parsed.timestamp())


def check_certificate_extensions(certificate):
    """Handle Microsoft's critical application policies before OpenSSL verification."""
    outer = sequence(certificate)
    if len(outer) != 3 or outer[0][0] != 0x30:
        raise ValueError("Malformed certificate")
    tbs = der_nodes(outer[0][1])
    extensions = [value for tag, value in tbs if tag == 0xa3]
    if len(extensions) != 1:
        raise ValueError("Require one certificate extensions set")
    policies = eku = None
    seen = set()
    for tag, value in sequence(extensions[0]):
        if tag != 0x30:
            raise ValueError("Invalid certificate extension")
        fields = der_nodes(value)
        if len(fields) not in (2, 3) or fields[0][0] != 6 or fields[-1][0] != 4:
            raise ValueError("Invalid certificate extension fields")
        name = oid(fields[0][1])
        if name in seen:
            raise ValueError("Duplicate certificate extension")
        seen.add(name)
        critical = len(fields) == 3
        if critical and fields[1] != (1, b"\xff"):
            raise ValueError("Noncanonical critical extension marker")
        if critical and name not in ("2.5.29.15", "2.5.29.19", "2.5.29.37",
                                     "1.3.6.1.4.1.311.21.10"):
            raise ValueError(f"Unsupported critical certificate extension: {name}")
        if name == "2.5.29.37":
            entries = sequence(fields[-1][1])
            if any(tag != 6 for tag, _ in entries):
                raise ValueError("Invalid extended key usage")
            eku = {oid(value) for _, value in entries}
        if name == "1.3.6.1.4.1.311.21.10":
            policies = set()
            for tag, value in sequence(fields[-1][1]):
                entry = der_nodes(value)
                if tag != 0x30 or len(entry) != 1 or entry[0][0] != 6:
                    raise ValueError("Unsupported Microsoft application policy qualifiers")
                policies.add(oid(entry[0][1]))
    if policies is not None and policies != eku:
        raise ValueError("Microsoft application policies differ from EKU constraints")
    return eku


def embedded_certificates(openssl, signature, extra=b"", cms=False):
    if cms:
        output = signature.parent / "timestamp-certificates.pem"
        command(openssl, "cms", "-cmsout", "-inform", "DER", "-in", signature,
                "-certsout", output, "-out", "/dev/null")
        certificates = output.read_bytes()
    else:
        certificates = command(openssl, "pkcs7", "-inform", "DER",
                               "-in", signature, "-print_certs")
    blocks = re.findall(
        rb"-----BEGIN CERTIFICATE-----\s*([A-Za-z0-9+/=\s]+?)-----END CERTIFICATE-----",
        certificates + extra)
    if not blocks:
        raise ValueError("Signature contains no certificates")
    for block in blocks:
        check_certificate_extensions(base64.b64decode(re.sub(rb"\s", b"", block), validate=True))


def verify_timestamp(openssl, signature, work):
    signature_value, token = signature_timestamp(signature)
    token_outer = sequence(token)
    if len(token_outer) != 2 or token_outer[1][0] != 0xa0:
        raise ValueError("Malformed timestamp SignedData")
    token_data = sequence(token_outer[1][1])
    if len(token_data) < 3 or token_data[2][0] != 0x30:
        raise ValueError("Malformed timestamp content type")
    token_content = der_nodes(token_data[2][1])
    if (len(token_content) != 2
            or token_content[0] != (6, bytes.fromhex("2a864886f70d0109100104"))
            or token_content[1][0] != 0xa0):
        raise ValueError("Timestamp is not id-ct-TSTInfo")
    encapsulated = der_nodes(token_content[1][1])
    if len(encapsulated) != 1 or encapsulated[0][0] != 4:
        raise ValueError("Missing encapsulated timestamp content")
    # This time is untrusted until CMS signature + chain + imprint checks below
    # succeed. It selects certificate validity time, never bypasses that check.
    claimed_content = encapsulated[0][1]
    claimed_time = timestamp_time(claimed_content)
    (work / "timestamp.der").write_bytes(token)
    (work / "signature-value.bin").write_bytes(signature_value)
    embedded_certificates(openssl, work / "timestamp.der", cms=True)
    command(openssl, "cms", "-verify", "-binary", "-inform", "DER",
            "-in", work / "timestamp.der", "-CAfile", work / "tsa-roots.pem",
            "-no-CApath", "-no-CAstore", "-purpose", "timestampsign", "-ignore_critical",
            "-attime", claimed_time,
            "-signer", work / "tsa-signer.pem", "-out", work / "tstinfo.der")
    signer = (work / "tsa-signer.pem").read_bytes()
    if signer.count(b"-----BEGIN CERTIFICATE-----") != 1:
        raise ValueError("Require exactly one timestamp signer")
    certificate = command(openssl, "x509", "-in", work / "tsa-signer.pem", "-outform", "DER")
    if check_certificate_extensions(certificate) != {TSA_EKU}:
        raise ValueError("Timestamp signer must have only the timeStamping EKU")
    content = (work / "tstinfo.der").read_bytes()
    if content != claimed_content:
        raise ValueError("Verified timestamp content differs from encapsulated content")
    fields = sequence(content)
    if len(fields) < 5 or fields[2][0] != 0x30:
        raise ValueError("Malformed RFC3161 message imprint")
    imprint = der_nodes(fields[2][1])
    if (len(imprint) != 2 or imprint[0] != (0x30, bytes.fromhex("06096086480165030402010500"))
            or imprint[1] != (4, hashlib.sha256(signature_value).digest())):
        raise ValueError("RFC3161 signature message imprint mismatch")
    return timestamp_time(content)


def package_file(root, name, allow_missing=False):
    path = PureWindowsPath(name)
    if path.anchor or not path.parts or ":" in name or any(
            part in ("", ".", "..") for part in name.replace("\\", "/").split("/")):
        raise ValueError("Unsafe package-relative filename")
    candidate = root
    for part in path.parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise ValueError("Package symlinks are not accepted")
    if not candidate.is_file() and not (allow_missing and not candidate.exists()):
        raise ValueError(f"Missing package file: {name}")
    return candidate


def verify_blocks(root, raw):
    blockmap = xml(raw)
    if blockmap.tag != BLOCK_NS + "BlockMap" or blockmap.get("HashMethod") != SHA256_URI:
        raise ValueError("Unsupported block map")
    listed = set()
    for entry in blockmap:
        if entry.tag != BLOCK_NS + "File":
            raise ValueError("Unsupported block-map entry")
        name = entry.attrib["Name"]
        key = name.replace("\\", "/").casefold()
        if key in listed:
            raise ValueError("Duplicate block-map file")
        listed.add(key)
        path = package_file(root, name)
        size = int(entry.attrib["Size"])
        if size < 0 or path.stat().st_size != size:
            raise ValueError(f"File size mismatch: {name}")
        blocks = entry.findall(BLOCK_NS + "Block")
        if len(blocks) != (size + 65535) // 65536:
            raise ValueError(f"Block count mismatch: {name}")
        with path.open("rb") as stream:
            for block in blocks:
                expected = base64.b64decode(block.attrib["Hash"], validate=True)
                if len(expected) != 32 or hashlib.sha256(stream.read(65536)).digest() != expected:
                    raise ValueError(f"Block hash mismatch: {name}")
            if stream.read(1):
                raise ValueError(f"File changed while hashing: {name}")
    if "appxmanifest.xml" not in listed:
        raise ValueError("Manifest is not covered by the signed block map")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Package symlink: {path.relative_to(root)}")
        if not path.is_file() or path.relative_to(root).as_posix().casefold() in listed:
            continue
        with path.open("rb") as stream:
            executable = stream.read(2) == b"MZ"
        if executable or path.suffix.casefold() in (".exe", ".dll", ".sys", ".ocx", ".cpl", ".scr"):
            raise ValueError(f"Unlisted executable: {path.relative_to(root)}")
    return len(listed)


def verify_signature(root, roots, openssl):
    pins = {item["sha256"] for item in json.loads((REPO / "versions.json").read_text())["appx_trust_roots"]}
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        pem = []
        tsa_pem = []
        for index, path in enumerate(roots):
            data = Path(path).read_bytes()
            if hashlib.sha256(data).hexdigest() not in pins:
                raise ValueError("Unpinned Microsoft root certificate")
            converted = command(openssl, "x509", "-inform", "DER", "-in", path, "-outform", "PEM")
            pem.append(converted)
            if hashlib.sha256(data).hexdigest() == TSA_ROOT_SHA256:
                tsa_pem.append(converted)
        if not pem:
            raise ValueError("No pinned root certificates supplied")
        (work / "roots.pem").write_bytes(b"".join(pem))
        if not tsa_pem:
            raise ValueError("Pinned Microsoft 2010 timestamp root is required")
        (work / "tsa-roots.pem").write_bytes(b"".join(tsa_pem))
        signature = package_file(root, "AppxSignature.p7x").read_bytes()
        if len(signature) > 1024 * 1024 or signature[:4] != b"PKCX":
            raise ValueError("Invalid PKCX signature")
        (work / "signature.der").write_bytes(signature[4:])
        embedded_certificates(openssl, work / "signature.der", b"".join(pem))
        verified_time = verify_timestamp(openssl, signature[4:], work)
        command(openssl, "smime", "-verify", "-binary", "-inform", "DER",
                "-in", work / "signature.der", "-CAfile", work / "roots.pem",
                "-no-CApath", "-no-CAstore", "-purpose", "any", "-ignore_critical",
                "-attime", verified_time,
                "-signer", work / "signer.pem", "-out", work / "content.der")
        signer = (work / "signer.pem").read_bytes()
        if signer.count(b"-----BEGIN CERTIFICATE-----") != 1:
            raise ValueError("Require exactly one verified package signer")
        eku = command(openssl, "x509", "-in", work / "signer.pem",
                      "-noout", "-ext", "extendedKeyUsage").decode()
        if STORE_EKU not in re.findall(r"\d+(?:\.\d+)+", eku):
            raise ValueError("Verified signer lacks the Store signing EKU")
        signer_der = command(openssl, "x509", "-in", work / "signer.pem", "-outform", "DER")
        if not {"1.3.6.1.5.5.7.3.3", STORE_EKU}.issubset(check_certificate_extensions(signer_der) or set()):
            raise ValueError("Verified signer lacks code-signing and Store usages")
        subject = command(openssl, "x509", "-in", work / "signer.pem", "-noout",
                          "-subject", "-nameopt", "RFC2253").decode().strip()
        if subject != "subject=" + MICROSOFT_SUBJECT:
            raise ValueError("Signer is not the expected Microsoft publisher")
        return signed_digests((work / "content.der").read_bytes()), {
            "signer_sha256": hashlib.sha256(signer_der).hexdigest(),
            "store_eku": STORE_EKU,
            "authenticated_timestamp_epoch": verified_time,
            "revocation": "not checked (offline verifier)",
        }


def verify_payload(root, roots, openssl, progress=None):
    progress = progress if progress is not None else {}
    progress["stage"] = "signature and authenticated timestamp"
    progress["archive_digests"] = {
        label: "archive-only: not applicable to an installed package (unverified)"
        for label in ("AXPC", "AXCD", "AXCT")
    }
    root = Path(root).resolve(strict=True)
    digests, signer = verify_signature(root, roots, openssl)
    progress["signer"] = signer
    progress["signed_digests"] = digests
    for label, name in (("AXBM", "AppxBlockMap.xml"), ("AXCI", "AppxMetadata/CodeIntegrity.cat")):
        progress["stage"] = label + " installed-content binding"
        if label == "AXCI" and not (root / name).exists():
            progress["AXCI"] = "catalogue absent from installed package (unverified)"
            continue
        raw = package_file(root, name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digests[label]:
            raise ValueError(f"Signed {label} digest mismatch")
    progress["stage"] = "installed-file block map"
    count = verify_blocks(root, package_file(root, "AppxBlockMap.xml").read_bytes())
    return {"installed_content_verified": True, "signer": signer, "files_verified": count}


def verify(root, application, roots, openssl, progress=None):
    progress = progress if progress is not None else {}
    root = Path(root).resolve(strict=True)
    payload = verify_payload(root, roots, openssl, progress)
    progress["stage"] = "verified publisher, family and full-trust manifest"
    manifest = package_file(root, "AppxManifest.xml")
    metadata, _ = identity(manifest, application)
    tree = xml(manifest.read_bytes())
    package_identity = tree.find("{http://schemas.microsoft.com/appx/manifest/foundation/windows10}Identity")
    if package_identity.get("Publisher") != MICROSOFT_PUBLISHER:
        raise ValueError("Manifest publisher does not match the verified signer")
    if metadata["family_name"] != "Microsoft.GamingApp_8wekyb3d8bbwe":
        raise ValueError("Only the observed GamingApp family is eligible")
    applications = [node for node in tree.iter() if node.tag.endswith("}Application")
                    and node.get("Id") == application]
    full_trust = (len(applications) == 1 and
                  applications[0].get("EntryPoint") == "Windows.FullTrustApplication") or any(
                      node.tag.endswith("}Capability") and node.get("Name") == "runFullTrust"
                      for node in tree.iter())
    if not full_trust:
        raise ValueError("Verified manifest does not establish the full-trust condition")
    return {
        **payload, "metadata": metadata,
        "signed_context_eligible": True,
        "full_trust_manifest": True,
        "scope": "offline installed-file verification; not Windows Store installation or token trust",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--application", required=True)
    parser.add_argument("--root", type=Path, action="append", required=True)
    parser.add_argument("--openssl", default=shutil.which("openssl"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = {"installed_content_verified": False, "signed_context_eligible": False}
    try:
        receipt.update(verify(args.package, args.application, args.root, args.openssl, receipt))
    except (ValueError, OSError, ET.ParseError, KeyError, subprocess.TimeoutExpired) as error:
        receipt["error"] = str(error)
    with args.output.open("x") as stream:
        stream.write(json.dumps(receipt, indent=2) + "\n")
    return 0 if receipt["installed_content_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
