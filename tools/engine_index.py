#!/usr/bin/env python3
"""Build, sign and verify the signed Calimocho engine release index (ADR-0082, REQ-124).

The index is a DSSE v1 envelope around a calimocho-engine-index/1 JSON payload, signed with
Ed25519. Ed25519 comes from OpenSSL 3 (Homebrew openssl@3); everything else is the Python
standard library, so the tool runs on the release Mac without extra packages.

  keygen   create a signing key file (mode 0600, never printed) and print its public key
  pubkey   print the public key and keyid of a key file
  entry    describe one engine release from its zip and source tar (hashes read from the zip)
  payload  combine entries into an index payload
  sign     wrap a payload in a signed envelope
  verify   check an envelope the way X Ode must (exit 1 on any failure)
  check-asset  check a downloaded engine zip against a verified index entry
"""

import argparse
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

REPO = Path(__file__).resolve().parents[1]
CONTRACTS = REPO / "docs/contracts"
PAYLOAD_SCHEMA = CONTRACTS / "calimocho-engine-index-v1.schema.json"
ENVELOPE_SCHEMA = CONTRACTS / "calimocho-engine-index-envelope-v1.schema.json"
PAYLOAD_TYPE = "application/vnd.calimocho.engine-index+json; version=1"
MAX_ENVELOPE_BYTES = 1536 * 1024
MAX_PAYLOAD_BYTES = 1024 * 1024
MAX_VALIDITY = datetime.timedelta(days=90)
CLOCK_SKEW = datetime.timedelta(minutes=5)
RELEASES = "https://github.com/WorkingPrinciple/calimocho/releases"
# DER prefixes for Ed25519 keys (RFC 8410): PKCS#8 private key and SubjectPublicKeyInfo.
PKCS8_PREFIX = bytes.fromhex("302e020100300506032b657004220420")
SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")


class IndexError_(ValueError):
    pass


# ------------------------------------------------------------------ helpers

def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def utc(text):
    return datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)


def utc_text(moment):
    return moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pae(payload_type, payload):
    """DSSE v1 pre-authentication encoding."""
    kind = payload_type.encode()
    return b"DSSEv1 %d %s %d %s" % (len(kind), kind, len(payload), payload)


def keyid(public_key):
    return sha256_bytes(public_key)


def semver(text):
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", text):
        raise IndexError_(f"not a SemVer core version: {text!r}")
    return tuple(int(part) for part in text.split("."))


def canonical(document):
    """Deterministic payload bytes. Verifiers never re-serialise; they check these exact bytes."""
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


# ------------------------------------------------------------------ OpenSSL Ed25519

def openssl():
    candidates = [os.environ.get("CALIMOCHO_OPENSSL"), "/opt/homebrew/opt/openssl@3/bin/openssl",
                  shutil.which("openssl")]
    for candidate in filter(None, candidates):
        try:
            version = subprocess.run([candidate, "version"], capture_output=True, text=True,
                                     check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            continue
        if version.startswith("OpenSSL 3."):
            return candidate
    raise IndexError_("OpenSSL 3 is required for Ed25519 (brew install openssl@3)")


def run_openssl(arguments, data=None):
    result = subprocess.run([openssl(), *arguments], input=data, capture_output=True)
    if result.returncode:
        raise IndexError_(f"openssl {arguments[0]} failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def check_key_file(path):
    info = os.stat(path)
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise IndexError_(f"{path} must not be readable by group or others (chmod 600)")
    if info.st_uid != os.getuid():
        raise IndexError_(f"{path} is not owned by you")


def public_key_of(key_path):
    check_key_file(key_path)
    der = run_openssl(["pkey", "-in", str(key_path), "-pubout", "-outform", "DER"])
    if len(der) != 44 or not der.startswith(SPKI_PREFIX):
        raise IndexError_(f"{key_path} is not an Ed25519 private key")
    return der[-32:]


def sign_bytes(key_path, message):
    check_key_file(key_path)
    if not message:
        raise IndexError_("refusing to sign an empty message")
    with tempfile.TemporaryDirectory() as scratch:
        source = Path(scratch) / "message"
        source.write_bytes(message)
        signature = run_openssl(["pkeyutl", "-sign", "-rawin", "-inkey", str(key_path),
                                 "-in", str(source)])
    if len(signature) != 64:
        raise IndexError_("unexpected Ed25519 signature length")
    return signature


def verify_bytes(public_key, message, signature):
    if len(public_key) != 32 or len(signature) != 64:
        return False
    with tempfile.TemporaryDirectory() as scratch:
        pem = Path(scratch) / "public.pem"
        pem.write_text("-----BEGIN PUBLIC KEY-----\n%s\n-----END PUBLIC KEY-----\n"
                       % base64.b64encode(SPKI_PREFIX + public_key).decode())
        (Path(scratch) / "message").write_bytes(message)
        (Path(scratch) / "signature").write_bytes(signature)
        result = subprocess.run([openssl(), "pkeyutl", "-verify", "-pubin", "-inkey", str(pem), "-rawin",
                                 "-in", str(Path(scratch) / "message"),
                                 "-sigfile", str(Path(scratch) / "signature")],
                                capture_output=True)
    return result.returncode == 0


def private_key_pem_from_seed(seed):
    """PEM for a raw 32-byte Ed25519 seed (used for the published RFC 8032 test key only)."""
    if len(seed) != 32:
        raise IndexError_("Ed25519 seed must be 32 bytes")
    body = base64.b64encode(PKCS8_PREFIX + seed).decode()
    return f"-----BEGIN PRIVATE KEY-----\n{body}\n-----END PRIVATE KEY-----\n"


# ------------------------------------------------------------------ schema validation

KNOWN_KEYWORDS = {"$schema", "$id", "$defs", "$ref", "title", "description", "type", "const", "enum",
                  "pattern", "minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems",
                  "required", "additionalProperties", "properties", "items"}


def validate(instance, schema, root, where="$"):
    """Strict validator for the JSON Schema keywords our contracts use; unknown keywords are errors."""
    unknown = set(schema) - KNOWN_KEYWORDS
    if unknown:
        raise IndexError_(f"schema uses unsupported keywords {sorted(unknown)}")
    if "$ref" in schema:
        name = schema["$ref"].removeprefix("#/$defs/")
        validate(instance, root["$defs"][name], root, where)
    kind = schema.get("type")
    checks = {"object": dict, "array": list, "string": str}
    if kind == "integer":
        if isinstance(instance, bool) or not isinstance(instance, int):
            raise IndexError_(f"{where}: expected an integer")
    elif kind in checks and not isinstance(instance, checks[kind]):
        raise IndexError_(f"{where}: expected {kind}")
    if "const" in schema and instance != schema["const"]:
        raise IndexError_(f"{where}: must be {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        raise IndexError_(f"{where}: must be one of {schema['enum']}")
    if isinstance(instance, str):
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            raise IndexError_(f"{where}: {instance!r} does not match {schema['pattern']}")
        if len(instance) < schema.get("minLength", 0) or len(instance) > schema.get("maxLength", 1 << 62):
            raise IndexError_(f"{where}: bad length")
    if isinstance(instance, int) and not isinstance(instance, bool):
        if instance < schema.get("minimum", -(1 << 62)) or instance > schema.get("maximum", 1 << 62):
            raise IndexError_(f"{where}: out of range")
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0) or len(instance) > schema.get("maxItems", 1 << 62):
            raise IndexError_(f"{where}: wrong number of items")
        if "items" in schema:
            for number, item in enumerate(instance):
                validate(item, schema["items"], root, f"{where}[{number}]")
    if isinstance(instance, dict):
        for name in schema.get("required", []):
            if name not in instance:
                raise IndexError_(f"{where}: missing {name}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = set(instance) - set(properties)
            if extra:
                raise IndexError_(f"{where}: unexpected {sorted(extra)}")
        for name, value in instance.items():
            if name in properties:
                validate(value, properties[name], root, f"{where}.{name}")


def check_payload(document):
    """Schema plus the rules JSON Schema cannot express."""
    schema = json.loads(PAYLOAD_SCHEMA.read_text())
    validate(document, schema, schema)
    generated, expires = utc(document["generated_at"]), utc(document["expires_at"])
    if not generated < expires <= generated + MAX_VALIDITY:
        raise IndexError_("expires_at must be after generated_at and at most 90 days later")
    seen = set()
    for entry in document["engines"]:
        name = entry["engine_id"]
        if name in seen:
            raise IndexError_(f"duplicate engine {name}")
        seen.add(name)
        if entry["install"]["directory"] != name:
            raise IndexError_(f"{name}: install.directory must equal engine_id")
        tag = entry["release_tag"]
        if entry["release_notes_url"] != f"{RELEASES}/tag/{tag}":
            raise IndexError_(f"{name}: release_notes_url does not match release_tag")
        for part in ("asset", "source"):
            item = entry[part]
            if item["url"] != f"{RELEASES}/download/{tag}/{item['name']}":
                raise IndexError_(f"{name}: {part}.url does not match release_tag and name")
    revoked = {item["engine_id"] for item in document["revoked"]}
    if revoked & seen:
        raise IndexError_(f"revoked engines are still listed: {sorted(revoked & seen)}")


def load_trusted_keys(path):
    document = json.loads(Path(path).read_text())
    if document.get("schema") != "calimocho-engine-index-keys/1":
        raise IndexError_("trusted keys file must have schema calimocho-engine-index-keys/1")
    keys = {}
    for item in document["keys"]:
        public = base64.b64decode(item["public_key"], validate=True)
        if len(public) != 32 or keyid(public) != item["keyid"]:
            raise IndexError_(f"trusted key {item.get('keyid')} does not match its public key")
        if item["status"] == "active":
            keys[item["keyid"]] = public
    return keys


def verify_envelope(raw, trusted, now=None, min_index_version=0, xode_version=None):
    """The client algorithm from ADR-0082. Returns (payload document, eligible engines)."""
    if len(raw) > MAX_ENVELOPE_BYTES:
        raise IndexError_("envelope too large")
    envelope = json.loads(raw)
    schema = json.loads(ENVELOPE_SCHEMA.read_text())
    validate(envelope, schema, schema)
    payload = base64.b64decode(envelope["payload"], validate=True)
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise IndexError_("payload too large")
    message = pae(envelope["payloadType"], payload)
    good = [s["keyid"] for s in envelope["signatures"]
            if s["keyid"] in trusted
            and verify_bytes(trusted[s["keyid"]], message, base64.b64decode(s["sig"], validate=True))]
    if not good:
        raise IndexError_("no signature from a trusted key verifies")
    document = json.loads(payload)
    check_payload(document)
    if document["index_version"] < min_index_version:
        raise IndexError_(f"index_version {document['index_version']} is older than {min_index_version} (rollback)")
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if now > utc(document["expires_at"]) + CLOCK_SKEW:
        raise IndexError_("index expired")
    if now + CLOCK_SKEW < utc(document["generated_at"]):
        raise IndexError_("index is from the future; check the clock")
    eligible = [entry for entry in document["engines"]
                if xode_version is None or semver(entry["min_xode_version"]) <= semver(xode_version)]
    return document, eligible, good


# ------------------------------------------------------------------ commands

def cmd_keygen(args):
    key = Path(args.key).expanduser()
    if key.exists():
        raise IndexError_(f"{key} exists; never overwrite a signing key")
    key.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(key.parent, 0o700)
    previous = os.umask(0o077)
    try:
        run_openssl(["genpkey", "-algorithm", "ed25519", "-out", str(key)])
    finally:
        os.umask(previous)
    os.chmod(key, 0o600)
    cmd_pubkey(args)


def cmd_pubkey(args):
    public = public_key_of(Path(args.key).expanduser())
    record = {"keyid": keyid(public), "public_key": base64.b64encode(public).decode(),
              "public_key_hex": public.hex()}
    print(json.dumps(record, indent=2))


def read_member(archive, name):
    with archive.open(name) as stream:
        return stream.read()


def cmd_entry(args):
    zip_path, source_path = Path(args.zip), Path(args.source)
    with zipfile.ZipFile(zip_path) as archive:
        tops = {name.split("/", 1)[0] for name in archive.namelist()}
        if len(tops) != 1:
            raise IndexError_("engine zip must hold exactly one top-level folder")
        top = tops.pop()
        engine = json.loads(read_member(archive, f"{top}/calimocho-engine.json"))
        manifest = read_member(archive, f"{top}/MANIFEST.sha256")
        listed = dict(reversed(line.split("  ", 1)) for line in manifest.decode().splitlines())
        hashes = {}
        for field, relative in (("wine_sha256", "bin/wine"), ("wineserver_sha256", "bin/wineserver"),
                                ("loader_sha256", "lib/wine/x86_64-unix/wine"),
                                ("engine_json_sha256", "calimocho-engine.json")):
            actual = sha256_bytes(read_member(archive, f"{top}/{relative}"))
            if relative != "calimocho-engine.json" and listed.get(relative) != actual:
                raise IndexError_(f"{relative} differs from MANIFEST.sha256")
            hashes[field] = actual
        hashes["manifest_sha256"] = sha256_bytes(manifest)
        members = archive.infolist()
        unpacked = {"size": sum(member.file_size for member in members), "entries": len(members)}
    if top != engine["engine_id"]:
        raise IndexError_("zip folder name differs from engine_id")
    tag = args.tag
    components = engine["components"]
    entry = {
        "engine_id": engine["engine_id"],
        "version": engine["version"],
        "provider": engine["provider"],
        "channel": args.channel,
        "min_xode_version": args.min_xode_version,
        "release_tag": tag,
        "release_notes_url": f"{RELEASES}/tag/{tag}",
        "asset": {"name": zip_path.name, "url": f"{RELEASES}/download/{tag}/{zip_path.name}",
                  "size": zip_path.stat().st_size, "sha256": sha256_file(zip_path)},
        "unpacked": unpacked,
        "source": {"name": source_path.name, "url": f"{RELEASES}/download/{tag}/{source_path.name}",
                   "size": source_path.stat().st_size, "sha256": sha256_file(source_path)},
        "source_commit": engine["source_commit"],
        "install": {"directory": engine["engine_id"]},
        "hashes": hashes,
        "signing": {"team_id": engine["signing"]["team_id"], "notarization_id": args.notarization_id},
        "apple_d3dmetal": {"version": components["apple_d3dmetal"]["version"],
                           "binary_sha256": components["apple_d3dmetal"]["binary_sha256"]},
        "components": {"wine": components["wine"]["version"],
                       "d3dmetal": components["apple_d3dmetal"]["version"],
                       "moltenvk": components["moltenvk"]["tag"]},
    }
    if args.source_commit and args.source_commit != entry["source_commit"]:
        raise IndexError_("--source-commit differs from the engine's recorded source_commit")
    Path(args.out).write_text(json.dumps(entry, indent=2, sort_keys=True) + "\n")
    print(args.out)


def cmd_payload(args):
    generated = utc(args.generated_at) if args.generated_at else datetime.datetime.now(
        datetime.timezone.utc).replace(microsecond=0)
    document = {
        "schema": "calimocho-engine-index/1",
        "index_version": args.index_version,
        "generated_at": utc_text(generated),
        "expires_at": utc_text(generated + datetime.timedelta(days=args.expires_days)),
        "publisher": "WorkingPrinciple/calimocho",
        "engines": [json.loads(Path(path).read_text()) for path in args.entry],
        "revoked": json.loads(Path(args.revoked).read_text()) if args.revoked else [],
    }
    check_payload(document)
    Path(args.out).write_bytes(canonical(document))
    print(args.out)


def cmd_sign(args):
    payload = Path(args.payload).read_bytes()
    document = json.loads(payload)
    check_payload(document)
    if canonical(document) != payload:
        raise IndexError_("payload is not in canonical form; build it with the payload command")
    message = pae(PAYLOAD_TYPE, payload)
    signatures = []
    for key in args.key:
        key = Path(key).expanduser()
        public = public_key_of(key)
        signature = sign_bytes(key, message)
        if not verify_bytes(public, message, signature):
            raise IndexError_("fresh signature does not verify")
        signatures.append({"keyid": keyid(public), "sig": base64.b64encode(signature).decode()})
    envelope = {"payloadType": PAYLOAD_TYPE, "payload": base64.b64encode(payload).decode(),
                "signatures": signatures}
    Path(args.out).write_text(json.dumps(envelope, indent=2) + "\n")
    print(args.out)


def cmd_verify(args):
    trusted = load_trusted_keys(args.trusted_keys)
    now = utc(args.now) if args.now else None
    document, eligible, good = verify_envelope(Path(args.envelope).read_bytes(), trusted, now,
                                               args.min_index_version, args.xode_version)
    print(json.dumps({"verified": True, "keyids": good, "index_version": document["index_version"],
                      "expires_at": document["expires_at"],
                      "engines": [e["engine_id"] for e in document["engines"]],
                      "eligible": [e["engine_id"] for e in eligible],
                      "revoked": [r["engine_id"] for r in document["revoked"]]}, indent=2))


def cmd_check_asset(args):
    """Client rule 6 on a downloaded zip, without extracting it: size, SHA-256, expansion bound
    from the central directory, and the hashes of the files the entry names."""
    trusted = load_trusted_keys(args.trusted_keys)
    now = utc(args.now) if args.now else None
    _, eligible, _ = verify_envelope(Path(args.envelope).read_bytes(), trusted, now, 0, args.xode_version)
    entry = next((e for e in eligible if e["engine_id"] == args.engine_id), None)
    if entry is None:
        raise IndexError_(f"{args.engine_id} is not offered by this index for this X Ode version")
    zip_path = Path(args.zip)
    if zip_path.stat().st_size != entry["asset"]["size"] or sha256_file(zip_path) != entry["asset"]["sha256"]:
        raise IndexError_("zip size or SHA-256 differs from the signed entry")
    with zipfile.ZipFile(zip_path) as archive:
        members = archive.infolist()
        if (sum(m.file_size for m in members) > entry["unpacked"]["size"]
                or len(members) > entry["unpacked"]["entries"]):
            raise IndexError_("zip expands beyond the signed bound")
        top = entry["install"]["directory"]
        for member in members:
            name = member.filename
            if name.startswith("/") or ".." in name.split("/") or not (name == f"{top}/" or name.startswith(f"{top}/")):
                raise IndexError_(f"unsafe path in zip: {name}")
        expected = {"bin/wine": "wine_sha256", "bin/wineserver": "wineserver_sha256",
                    "lib/wine/x86_64-unix/wine": "loader_sha256", "MANIFEST.sha256": "manifest_sha256",
                    "calimocho-engine.json": "engine_json_sha256"}
        for relative, field in expected.items():
            if sha256_bytes(read_member(archive, f"{top}/{relative}")) != entry["hashes"][field]:
                raise IndexError_(f"{relative} differs from the signed entry")
    print(json.dumps({"asset": "ok", "engine_id": args.engine_id, "unpacked": entry["unpacked"]}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("keygen", help="create a signing key (0600, never printed)")
    p.add_argument("--key", required=True)
    p.set_defaults(func=cmd_keygen)
    p = commands.add_parser("pubkey", help="print the public key and keyid of a key file")
    p.add_argument("--key", required=True)
    p.set_defaults(func=cmd_pubkey)
    p = commands.add_parser("entry", help="describe one engine release")
    p.add_argument("--zip", required=True)
    p.add_argument("--source", required=True, help="corresponding source tar")
    p.add_argument("--tag", required=True, help="release tag, e.g. engine-0.1120.4.6")
    p.add_argument("--channel", choices=("prerelease", "release"), required=True)
    p.add_argument("--min-xode-version", required=True)
    p.add_argument("--notarization-id", required=True)
    p.add_argument("--source-commit", help="optional cross-check against calimocho-engine.json")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_entry)
    p = commands.add_parser("payload", help="combine entries into an index payload")
    p.add_argument("--entry", action="append", default=[])
    p.add_argument("--index-version", type=int, required=True)
    p.add_argument("--generated-at", help="UTC, e.g. 2026-10-26T12:00:00Z (default: now)")
    p.add_argument("--expires-days", type=int, default=30)
    p.add_argument("--revoked", help="JSON list of {engine_id, reason}")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_payload)
    p = commands.add_parser("sign", help="wrap a payload in a signed DSSE envelope")
    p.add_argument("--payload", required=True)
    p.add_argument("--key", action="append", required=True, help="repeat to sign with several keys")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_sign)
    p = commands.add_parser("verify", help="verify an envelope like X Ode does")
    p.add_argument("--envelope", required=True)
    p.add_argument("--trusted-keys", default=str(CONTRACTS / "calimocho-engine-index-keys.json"))
    p.add_argument("--now", help="UTC time to check expiry against (default: now)")
    p.add_argument("--min-index-version", type=int, default=0)
    p.add_argument("--xode-version", help="running X Ode version, for min_xode_version filtering")
    p.set_defaults(func=cmd_verify)
    p = commands.add_parser("check-asset", help="check a downloaded engine zip against a verified index")
    p.add_argument("--envelope", required=True)
    p.add_argument("--engine-id", required=True)
    p.add_argument("--zip", required=True)
    p.add_argument("--trusted-keys", default=str(CONTRACTS / "calimocho-engine-index-keys.json"))
    p.add_argument("--now")
    p.add_argument("--xode-version")
    p.set_defaults(func=cmd_check_asset)
    args = parser.parse_args()
    try:
        args.func(args)
    except (IndexError_, OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print(f"calimocho: ERROR {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
