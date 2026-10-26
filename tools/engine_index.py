#!/usr/bin/env python3
"""Build, sign and verify the signed Calimocho engine release index (ADR-0082, REQ-124).

The index is a DSSE v1 envelope around a calimocho-engine-index/1 JSON payload, signed with
Ed25519. Ed25519 comes from OpenSSL 3 (Homebrew openssl@3); everything else is the Python
standard library.

  keygen       create a passphrase-encrypted signing key (mode 0600) and print its public key
  encrypt-key  encrypt an existing unencrypted key in place with a passphrase (interactive)
  pubkey       print the public key and keyid of a key file
  entry        describe one engine release from its zip and source tar
  payload      combine entries into an index payload
  sign         wrap a payload in a signed envelope
  verify       check an envelope exactly as X Ode must, optionally updating client state
  check-asset  check a downloaded engine zip against a verified index (installer rules)

Passphrases come from the terminal, or from CALIMOCHO_ENGINE_INDEX_PASSPHRASE when set.
"""

import argparse
import base64
import datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
import urllib.parse
import zipfile

REPO = Path(__file__).resolve().parents[1]
CONTRACTS = REPO / "docs/contracts"
SCHEMAS = {
    "payload": CONTRACTS / "calimocho-engine-index-v1.schema.json",
    "envelope": CONTRACTS / "calimocho-engine-index-envelope-v1.schema.json",
    "trust": CONTRACTS / "calimocho-engine-index-trust-v1.schema.json",
    "state": CONTRACTS / "calimocho-engine-index-state-v1.schema.json",
}
DEFAULT_TRUST = CONTRACTS / "calimocho-engine-index-trust.json"
PAYLOAD_TYPE = "application/vnd.calimocho.engine-index+json; version=1"
STATE_SCHEMA = "calimocho-engine-index-state/1"
TEAM_ID = "M62Z4M5EUY"  # embedded constant: never taken from the index
MAX_ENVELOPE_BYTES = 1536 * 1024
MAX_PAYLOAD_BYTES = 1024 * 1024
MAX_VALIDITY = datetime.timedelta(days=90)
MAX_STATE_REVOCATIONS = 1024
CLOCK_SKEW = datetime.timedelta(minutes=5)
RELEASE_HOST = "github.com"
RELEASE_PATH = "/WorkingPrinciple/calimocho/releases"
PASSPHRASE_ENV = "CALIMOCHO_ENGINE_INDEX_PASSPHRASE"
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


def engine_version(text):
    """Calimocho versions compare as four non-negative integers: 0.1120.4.6 < 0.1120.4.10."""
    if not re.fullmatch(r"0\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", text):
        raise IndexError_(f"not a Calimocho engine version: {text!r}")
    return tuple(int(part) for part in text.split("."))


def canonical(document):
    """Deterministic payload bytes. Verifiers never re-serialise; they check these exact bytes."""
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def strict_json(raw):
    """Parse JSON, refusing duplicate object keys and non-finite numbers."""
    def pairs(items):
        result = {}
        for name, value in items:
            if name in result:
                raise IndexError_(f"duplicate JSON key {name!r}")
            result[name] = value
        return result

    def constant(name):
        raise IndexError_(f"invalid JSON constant {name}")

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def strict_b64(text, what):
    try:
        data = base64.b64decode(text, validate=True)
    except ValueError as error:
        raise IndexError_(f"{what}: invalid base64") from error
    if base64.b64encode(data).decode() != text:
        raise IndexError_(f"{what}: non-canonical base64")
    return data


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


def run_openssl(arguments, interactive=False):
    """Run openssl. Interactive runs inherit the terminal so passphrase prompts reach the user."""
    if interactive:
        result = subprocess.run([openssl(), *arguments], stdout=subprocess.PIPE)
        if result.returncode:
            raise IndexError_(f"openssl {arguments[0]} failed")
        return result.stdout
    result = subprocess.run([openssl(), *arguments], capture_output=True, stdin=subprocess.DEVNULL)
    if result.returncode:
        raise IndexError_(f"openssl {arguments[0]} failed: {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def check_key_file(path):
    info = os.lstat(path)
    if not stat.S_ISREG(info.st_mode):
        raise IndexError_(f"{path} must be a regular file")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise IndexError_(f"{path} must not be accessible by group or others (chmod 600)")
    if info.st_uid != os.getuid():
        raise IndexError_(f"{path} is not owned by you")


def key_is_encrypted(path):
    first = Path(path).read_text().lstrip().splitlines()[0]
    if first == "-----BEGIN ENCRYPTED PRIVATE KEY-----":
        return True
    if first == "-----BEGIN PRIVATE KEY-----":
        return False
    raise IndexError_(f"{path} is not a PKCS#8 PEM private key")


def passin(path):
    if not key_is_encrypted(path):
        return [], False
    if os.environ.get(PASSPHRASE_ENV):
        return ["-passin", f"env:{PASSPHRASE_ENV}"], False
    return [], True


def public_key_of(key_path):
    check_key_file(key_path)
    password, interactive = passin(key_path)
    der = run_openssl(["pkey", "-in", str(key_path), *password, "-pubout", "-outform", "DER"],
                      interactive)
    if len(der) != 44 or not der.startswith(SPKI_PREFIX):
        raise IndexError_(f"{key_path} is not an Ed25519 private key")
    return der[-32:]


def sign_bytes(key_path, message):
    check_key_file(key_path)
    if not message:
        raise IndexError_("refusing to sign an empty message")
    password, interactive = passin(key_path)
    with tempfile.TemporaryDirectory() as scratch:
        source = Path(scratch) / "message"
        source.write_bytes(message)
        signature = run_openssl(["pkeyutl", "-sign", "-rawin", "-inkey", str(key_path), *password,
                                 "-in", str(source)], interactive)
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
                                capture_output=True, stdin=subprocess.DEVNULL)
    return result.returncode == 0


def private_key_pem_from_seed(seed):
    """Unencrypted PEM for a raw 32-byte Ed25519 seed (the published RFC 8032 test keys only)."""
    if len(seed) != 32:
        raise IndexError_("Ed25519 seed must be 32 bytes")
    body = base64.b64encode(PKCS8_PREFIX + seed).decode()
    return f"-----BEGIN PRIVATE KEY-----\n{body}\n-----END PRIVATE KEY-----\n"


# ------------------------------------------------------------------ schema validation

KNOWN_KEYWORDS = {"$schema", "$id", "$defs", "$ref", "title", "description", "type", "const", "enum",
                  "pattern", "minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems",
                  "required", "additionalProperties", "properties", "items"}


def validate(instance, schema, root, where="$"):
    """Strict validator for the JSON Schema keywords our contracts use; unknown keywords are errors.
    Patterns must match the whole string (re.fullmatch), as ADR-0082 requires of every client."""
    unknown = set(schema) - KNOWN_KEYWORDS
    if unknown:
        raise IndexError_(f"schema uses unsupported keywords {sorted(unknown)}")
    if "$ref" in schema:
        validate(instance, root["$defs"][schema["$ref"].removeprefix("#/$defs/")], root, where)
    kind = schema.get("type")
    if kind == "integer" and (isinstance(instance, bool) or not isinstance(instance, int)):
        raise IndexError_(f"{where}: expected an integer")
    checks = {"object": dict, "array": list, "string": str}
    if kind in checks and not isinstance(instance, checks[kind]):
        raise IndexError_(f"{where}: expected {kind}")
    if "const" in schema and (instance != schema["const"] or type(instance) is not type(schema["const"])):
        raise IndexError_(f"{where}: must be {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        raise IndexError_(f"{where}: must be one of {schema['enum']}")
    if isinstance(instance, str):
        if "pattern" in schema and not re.fullmatch(schema["pattern"], instance):
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


def check_schema(document, kind):
    schema = json.loads(SCHEMAS[kind].read_text())
    validate(document, schema, schema)


def release_url(url, kind, tag, name=None):
    """Parse, don't compare strings: https, github.com, no userinfo, port, query or fragment."""
    parts = urllib.parse.urlsplit(url)
    expected = f"{RELEASE_PATH}/{kind}/{tag}" + (f"/{name}" if name else "")
    if (parts.scheme != "https" or parts.hostname != RELEASE_HOST or parts.netloc != RELEASE_HOST
            or parts.username or parts.password or parts.port or parts.query or parts.fragment
            or parts.path != expected):
        raise IndexError_(f"URL is not the release URL for {tag}: {url!r}")


def check_payload(document):
    """Schema plus the rules JSON Schema cannot express."""
    check_schema(document, "payload")
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
        release_url(entry["release_notes_url"], "tag", tag)
        for part in ("asset", "source"):
            release_url(entry[part]["url"], "download", tag, entry[part]["name"])
    revoked = {item["engine_id"] for item in document["revoked"]}
    if revoked & seen:
        raise IndexError_(f"revoked engines are still listed: {sorted(revoked & seen)}")


# ------------------------------------------------------------------ client verification

def load_trust(path):
    trust = strict_json(Path(path).read_bytes())
    check_schema(trust, "trust")
    keys = {}
    for item in trust["keys"]:
        public = strict_b64(item["public_key"], "public_key")
        if len(public) != 32 or keyid(public) != item["keyid"]:
            raise IndexError_(f"trusted key {item['keyid']} does not match its public key")
        if item["status"] == "active" and item["keyid"] not in trust["revoked_keyids"]:
            keys[item["keyid"]] = (public, item["epoch"])
    trust["active"] = keys
    return trust


def load_state(path):
    if not path or not Path(path).exists():
        return None
    state = strict_json(Path(path).read_bytes())
    check_schema(state, "state")
    return state


def verify_envelope(raw, trust, state=None, now=None, xode_version=None, installed_version=None):
    """The client algorithm of ADR-0082. Returns (payload, eligible engines, new state)."""
    if len(raw) > MAX_ENVELOPE_BYTES:
        raise IndexError_("envelope too large")
    envelope = strict_json(raw)
    check_schema(envelope, "envelope")
    payload = strict_b64(envelope["payload"], "payload")
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise IndexError_("payload too large")
    message = pae(envelope["payloadType"], payload)
    verified = {}
    for signature in envelope["signatures"]:
        trusted = trust["active"].get(signature["keyid"])
        if trusted and verify_bytes(trusted[0], message, strict_b64(signature["sig"], "sig")):
            verified[signature["keyid"]] = trusted[1]
    if not verified:
        raise IndexError_("no signature from a trusted key verifies")
    document = strict_json(payload)
    check_payload(document)
    signers = sorted(k for k, epoch in verified.items() if epoch == document["epoch"])
    if not signers:
        raise IndexError_(f"no verifying key is bound to epoch {document['epoch']}")
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if now > utc(document["expires_at"]) + CLOCK_SKEW:
        raise IndexError_("index expired")
    if now + CLOCK_SKEW < utc(document["generated_at"]):
        raise IndexError_("index is from the future; check the clock")
    epoch, version, digest = document["epoch"], document["index_version"], sha256_bytes(payload)
    floor = trust["floor"]
    if (epoch, version) < (floor["epoch"], floor["index_version"]):
        raise IndexError_(f"index ({epoch}, {version}) is below the embedded floor")
    # The high-water mark is bound to the keys that set it. If one of them is revoked here, the
    # mark is discarded (a stolen key must not freeze clients) and the embedded floor applies.
    # Revocations are kept separately and only grow.
    high = state["high_water"] if state else None
    if high and any(k in trust["revoked_keyids"] for k in high["keyids"]):
        high = None
    if high:
        if epoch < high["epoch"]:
            raise IndexError_(f"epoch {epoch} is older than {high['epoch']} (rollback)")
        if epoch == high["epoch"]:
            if version < high["index_version"]:
                raise IndexError_(f"index_version {version} is older than {high['index_version']} (rollback)")
            if version == high["index_version"] and digest != high["payload_sha256"]:
                raise IndexError_("a different payload claims the same index_version (equivocation)")
    revoked = {}
    for source in (trust["revoked_engines"], state["revoked_engines"] if state else [], document["revoked"]):
        for item in source:
            revoked.setdefault(item["engine_id"], item)
    if len(revoked) > MAX_STATE_REVOCATIONS:
        raise IndexError_("revocation list overflow; treating as no update")
    eligible = []
    for entry in document["engines"]:
        if entry["engine_id"] in revoked:
            continue
        if xode_version and semver(entry["min_xode_version"]) > semver(xode_version):
            continue
        if installed_version and engine_version(entry["version"]) <= engine_version(installed_version):
            continue
        eligible.append(entry)
    keep_old = high and (high["epoch"], high["index_version"]) == (epoch, version)
    new_state = {"schema": STATE_SCHEMA,
                 "high_water": {"epoch": epoch, "index_version": version, "payload_sha256": digest,
                                "keyids": high["keyids"] if keep_old else signers},
                 "revoked_engines": sorted(revoked.values(), key=lambda item: item["engine_id"])}
    check_schema(new_state, "state")
    return document, eligible, new_state


# ------------------------------------------------------------------ installer checks

def zip_member_type(member):
    """Type comes only from a Unix (create_system 3) mode; anything else is refused. A name ending
    in / must be a directory and a directory's name must end in /."""
    if member.create_system != 3:
        raise IndexError_(f"member without a Unix mode: {member.filename!r}")
    kind = {stat.S_IFREG: "file", stat.S_IFDIR: "dir", stat.S_IFLNK: "symlink"}.get(
        stat.S_IFMT(member.external_attr >> 16))
    if kind is None:
        raise IndexError_(f"unsupported member type (device, FIFO, hard link): {member.filename!r}")
    if (kind == "dir") != member.filename.endswith("/"):
        raise IndexError_(f"member type and trailing slash disagree: {member.filename!r}")
    return kind


def safe_relative(name, what):
    if not name or "\\" in name or name.startswith("/") or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise IndexError_(f"unsafe {what}: {name!r}")
    parts = name.rstrip("/").split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise IndexError_(f"unsafe {what}: {name!r}")
    return parts


def check_zip(zip_path, entry):
    """ADR-0082 installer rules applied to the archive itself: paths, types, links, bounds on the
    bytes actually decompressed, the signed hashes and the full MANIFEST."""
    zip_path = Path(zip_path)
    if zip_path.stat().st_size != entry["asset"]["size"] or sha256_file(zip_path) != entry["asset"]["sha256"]:
        raise IndexError_("zip size or SHA-256 differs from the signed entry")
    top = entry["install"]["directory"]
    bound = entry["unpacked"]
    with zipfile.ZipFile(zip_path) as archive:
        members = archive.infolist()
        if len(members) > bound["entries"] or sum(m.file_size for m in members) > bound["size"]:
            raise IndexError_("central directory exceeds the signed expansion bound")
        kinds, folded, links = {}, {}, {}
        for member in members:
            name = member.filename
            parts = safe_relative(name, "path")
            if parts[0] != top:
                raise IndexError_(f"path outside {top}/: {name!r}")
            path = "/".join(parts)
            kind = zip_member_type(member)
            if path in kinds:
                raise IndexError_(f"duplicate path: {name!r}")
            key = unicodedata.normalize("NFC", path).casefold()
            if key in folded:
                raise IndexError_(f"paths collide on a case-insensitive or normalising file system: {name!r}")
            kinds[path], folded[key] = kind, path
        written, hashes = 0, {}
        for member in members:
            path = "/".join(safe_relative(member.filename, "path"))
            if kinds[path] == "dir":
                continue
            digest, size = hashlib.sha256(), 0
            with archive.open(member) as stream:
                for block in iter(lambda: stream.read(1 << 20), b""):
                    size += len(block)
                    written += len(block)
                    if written > bound["size"] or size > member.file_size:
                        raise IndexError_("decompressed bytes exceed the signed expansion bound")
                    digest.update(block)
                    if kinds[path] == "symlink":
                        links[path] = links.get(path, b"") + block
            hashes[path] = digest.hexdigest()
        for path, target in links.items():
            target = target.decode("utf-8")
            if (not target or target.startswith("/") or "\\" in target
                    or any(ord(c) < 32 or ord(c) == 127 for c in target)):
                raise IndexError_(f"unsafe symlink target {path} -> {target!r}")
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
            if not resolved.startswith(top + "/"):
                raise IndexError_(f"symlink {path} -> {target} leaves {top}/")
            links[path] = target
        fold = lambda value: unicodedata.normalize("NFC", value).casefold()  # noqa: E731
        folded_links = {fold(path) for path, kind in kinds.items() if kind == "symlink"}
        for path in kinds:
            # Nothing may be written through a symlink: no proper prefix of a path, compared the
            # way APFS compares names, is a symlink.
            parts = fold(path).split("/")
            for depth in range(1, len(parts)):
                if "/".join(parts[:depth]) in folded_links:
                    raise IndexError_(f"{path} lies under a symlink")
        for path in links:
            resolved = resolve_link(path, links, kinds, top)
            if resolved is None:
                raise IndexError_(f"symlink {path} -> {links[path]} leaves {top}/ or dangles")
        manifest = archive.read(f"{top}/MANIFEST.sha256").decode("utf-8")
    listed = {}
    for line in manifest.splitlines():
        digest, relative = line.split("  ", 1)
        listed[f"{top}/{relative}"] = digest
    for path, kind in kinds.items():
        if kind == "dir" or path == f"{top}/MANIFEST.sha256":
            continue
        expected = listed.pop(path, None)
        actual = f"link {links[path]}" if kind == "symlink" else hashes[path]
        if expected != actual:
            raise IndexError_(f"{path} is missing from or differs from MANIFEST.sha256")
    if listed:
        raise IndexError_(f"MANIFEST.sha256 lists files the zip lacks: {sorted(listed)[:5]}")
    named = {"bin/wine": "wine_sha256", "bin/wineserver": "wineserver_sha256",
             "lib/wine/x86_64-unix/wine": "loader_sha256", "MANIFEST.sha256": "manifest_sha256",
             "calimocho-engine.json": "engine_json_sha256"}
    for relative, field in named.items():
        if hashes.get(f"{top}/{relative}") != entry["hashes"][field]:
            raise IndexError_(f"{relative} differs from the signed entry")
    if entry["signing"]["team_id"] != TEAM_ID:
        raise IndexError_("entry names a different Team ID; clients use their embedded constant")
    return {"entries": len(kinds), "bytes": written, "symlinks": len(links)}


def resolve_link(path, links, kinds, top, depth=0):
    """Lexically resolve a symlink chain inside top/. Returns the final path or None."""
    if depth > 40:
        return None
    target = posixpath.normpath(posixpath.join(posixpath.dirname(path), links[path]))
    if not (target == top or target.startswith(top + "/")):
        return None
    # Resolve any symlinked parent components, then the target itself.
    parts = target.split("/")
    for index in range(1, len(parts) + 1):
        prefix = "/".join(parts[:index])
        if kinds.get(prefix) == "symlink":
            inner = resolve_link(prefix, links, kinds, top, depth + 1)
            if inner is None:
                return None
            rest = "/".join(parts[index:])
            return resolve_existing(f"{inner}/{rest}" if rest else inner, kinds, links, top, depth + 1)
    return target if target in kinds or any(k.startswith(target + "/") for k in kinds) else None


def resolve_existing(path, kinds, links, top, depth):
    if depth > 40 or not (path == top or path.startswith(top + "/")):
        return None
    parts = path.split("/")
    for index in range(1, len(parts) + 1):
        prefix = "/".join(parts[:index])
        if kinds.get(prefix) == "symlink":
            inner = resolve_link(prefix, links, kinds, top, depth + 1)
            if inner is None:
                return None
            rest = "/".join(parts[index:])
            return resolve_existing(f"{inner}/{rest}" if rest else inner, kinds, links, top, depth + 1)
    return path if path in kinds or any(k.startswith(path + "/") for k in kinds) else None


# ------------------------------------------------------------------ commands

def write_private(path, data):
    path = Path(path)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)


def cmd_keygen(args):
    key = Path(args.key).expanduser()
    if key.exists():
        raise IndexError_(f"{key} exists; never overwrite a signing key")
    key.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(key.parent, 0o700)
    password = ["-pass", f"env:{PASSPHRASE_ENV}"] if os.environ.get(PASSPHRASE_ENV) else []
    previous = os.umask(0o077)
    try:
        run_openssl(["genpkey", "-algorithm", "ed25519", "-aes256", *password, "-out", str(key)],
                    interactive=not password)
    finally:
        os.umask(previous)
    os.chmod(key, 0o600)
    cmd_pubkey(args)


def cmd_encrypt_key(args):
    key = Path(args.key).expanduser()
    check_key_file(key)
    if key_is_encrypted(key):
        raise IndexError_(f"{key} is already encrypted")
    before = public_key_of(key)
    password = ["-passout", f"env:{PASSPHRASE_ENV}"] if os.environ.get(PASSPHRASE_ENV) else []
    staged = key.with_name(key.name + ".encrypting")
    if staged.exists():
        raise IndexError_(f"{staged} exists; remove it after checking it")
    previous = os.umask(0o077)
    try:
        run_openssl(["pkey", "-in", str(key), "-aes256", *password, "-out", str(staged)],
                    interactive=not password)
    finally:
        os.umask(previous)
    os.chmod(staged, 0o600)
    if not key_is_encrypted(staged) or public_key_of(staged) != before:
        staged.unlink()
        raise IndexError_("encrypted key does not match the original; original kept")
    os.replace(staged, key)
    print(json.dumps({"encrypted": str(key), "keyid": keyid(before)}, indent=2))


def cmd_pubkey(args):
    public = public_key_of(Path(args.key).expanduser())
    print(json.dumps({"keyid": keyid(public), "public_key": base64.b64encode(public).decode(),
                      "public_key_hex": public.hex()}, indent=2))


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
        engine = strict_json(read_member(archive, f"{top}/calimocho-engine.json"))
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
    if engine["signing"]["team_id"] != TEAM_ID:
        raise IndexError_("engine is not signed by the Calimocho Team ID")
    tag, components = args.tag, engine["components"]
    download = f"https://{RELEASE_HOST}{RELEASE_PATH}/download/{tag}"
    entry = {
        "engine_id": engine["engine_id"],
        "version": engine["version"],
        "provider": engine["provider"],
        "channel": args.channel,
        "min_xode_version": args.min_xode_version,
        "release_tag": tag,
        "release_notes_url": f"https://{RELEASE_HOST}{RELEASE_PATH}/tag/{tag}",
        "asset": {"name": zip_path.name, "url": f"{download}/{zip_path.name}",
                  "size": zip_path.stat().st_size, "sha256": sha256_file(zip_path)},
        "unpacked": unpacked,
        "source": {"name": source_path.name, "url": f"{download}/{source_path.name}",
                   "size": source_path.stat().st_size, "sha256": sha256_file(source_path)},
        "source_commit": engine["source_commit"],
        "install": {"directory": engine["engine_id"]},
        "hashes": hashes,
        "signing": {"team_id": TEAM_ID, "notarization_id": args.notarization_id},
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
        "epoch": args.epoch,
        "index_version": args.index_version,
        "generated_at": utc_text(generated),
        "expires_at": utc_text(generated + datetime.timedelta(days=args.expires_days)),
        "publisher": "WorkingPrinciple/calimocho",
        "engines": [strict_json(Path(path).read_bytes()) for path in args.entry],
        "revoked": strict_json(Path(args.revoked).read_bytes()) if args.revoked else [],
    }
    check_payload(document)
    Path(args.out).write_bytes(canonical(document))
    print(args.out)


def cmd_sign(args):
    payload = Path(args.payload).read_bytes()
    document = strict_json(payload)
    check_payload(document)
    if canonical(document) != payload:
        raise IndexError_("payload is not in canonical form; build it with the payload command")
    message = pae(PAYLOAD_TYPE, payload)
    signatures = []
    for key in args.key:
        key = Path(key).expanduser()
        check_key_file(key)
        if not key_is_encrypted(key) and not args.allow_unencrypted_test_key:
            raise IndexError_(f"{key} is not passphrase-encrypted (run encrypt-key)")
        public = public_key_of(key)
        signature = sign_bytes(key, message)
        if not verify_bytes(public, message, signature):
            raise IndexError_("fresh signature does not verify")
        signatures.append({"keyid": keyid(public), "sig": base64.b64encode(signature).decode()})
    envelope = {"payloadType": PAYLOAD_TYPE, "payload": base64.b64encode(payload).decode(),
                "signatures": signatures}
    Path(args.out).write_text(json.dumps(envelope, indent=2) + "\n")
    print(args.out)


def verify_from_args(args):
    trust = load_trust(args.trust)
    state = load_state(args.state)
    now = utc(args.now) if args.now else None
    return verify_envelope(Path(args.envelope).read_bytes(), trust, state, now,
                           args.xode_version, args.installed_version)


def cmd_verify(args):
    document, eligible, new_state = verify_from_args(args)
    if args.state and args.write_state:
        # Persist only after every check passed; write-then-rename.
        target = Path(args.state)
        staged = target.with_name(target.name + ".new")
        staged.write_text(json.dumps(new_state, indent=2) + "\n")
        os.replace(staged, target)
    print(json.dumps({"verified": True, "epoch": document["epoch"], "index_version": document["index_version"],
                      "keyids": new_state["high_water"]["keyids"], "expires_at": document["expires_at"],
                      "engines": [e["engine_id"] for e in document["engines"]],
                      "eligible": [e["engine_id"] for e in eligible],
                      "revoked": [r["engine_id"] for r in new_state["revoked_engines"]]}, indent=2))


def cmd_check_asset(args):
    _, eligible, _ = verify_from_args(args)
    entry = next((e for e in eligible if e["engine_id"] == args.engine_id), None)
    if entry is None:
        raise IndexError_(f"{args.engine_id} is not offered by this index here")
    result = check_zip(args.zip, entry)
    print(json.dumps({"asset": "ok", "engine_id": args.engine_id, **result,
                      "unpacked_bound": entry["unpacked"]}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("keygen", help="create a passphrase-encrypted signing key")
    p.add_argument("--key", required=True)
    p.set_defaults(func=cmd_keygen)
    p = commands.add_parser("encrypt-key", help="encrypt an existing key in place (interactive)")
    p.add_argument("--key", required=True)
    p.set_defaults(func=cmd_encrypt_key)
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
    p.add_argument("--epoch", type=int, required=True)
    p.add_argument("--index-version", type=int, required=True)
    p.add_argument("--generated-at", help="UTC, e.g. 2026-10-26T12:00:00Z (default: now)")
    p.add_argument("--expires-days", type=int, default=30)
    p.add_argument("--revoked", help="JSON list of {engine_id, reason}")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_payload)
    p = commands.add_parser("sign", help="wrap a payload in a signed DSSE envelope")
    p.add_argument("--payload", required=True)
    p.add_argument("--key", action="append", required=True, help="repeat to sign with several keys")
    p.add_argument("--allow-unencrypted-test-key", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_sign)
    for name, func, text in (("verify", cmd_verify, "verify an envelope like X Ode does"),
                             ("check-asset", cmd_check_asset, "check a downloaded engine zip")):
        p = commands.add_parser(name, help=text)
        p.add_argument("--envelope", required=True)
        p.add_argument("--trust", default=str(DEFAULT_TRUST))
        p.add_argument("--state", help="client state file (calimocho-engine-index-state/1)")
        p.add_argument("--now", help="UTC time to check expiry against (default: now)")
        p.add_argument("--xode-version", help="running X Ode version, for min_xode_version")
        p.add_argument("--installed-version", help="installed Calimocho version; only newer is offered")
        if name == "verify":
            p.add_argument("--write-state", action="store_true", help="persist the state after success")
        else:
            p.add_argument("--engine-id", required=True)
            p.add_argument("--zip", required=True)
        p.set_defaults(func=func)
    args = parser.parse_args()
    try:
        args.func(args)
    except (IndexError_, OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print(f"calimocho: ERROR {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
