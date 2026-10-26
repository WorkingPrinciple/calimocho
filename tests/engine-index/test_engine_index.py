#!/usr/bin/env python3
"""Test vector and tests for the signed engine release index (ADR-0082, REQ-124).

  python3 tests/engine-index/test_engine_index.py              run the tests
  python3 tests/engine-index/test_engine_index.py --regenerate rewrite the vector files

The vector is signed with the public RFC 8032 section 7.1 TEST 1 key (epoch 1) and, for the
epoch tests, the TEST 2 key (epoch 2). Both keys are public; X Ode and the backend must never
trust them. Ed25519 is deterministic, so every implementation must reproduce signature_hex.
"""

import base64
import copy
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE = Path(__file__).resolve().parent
TOOL = HERE.parents[1] / "tools/engine_index.py"
sys.path.insert(0, str(TOOL.parent))
import engine_index as ei  # noqa: E402

TEST_SEED = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
OTHER_SEED = bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb")
NOW = "2026-10-27T00:00:00Z"
# RFC 8032 section 7.1, TEST 2 (one byte 0x72) and TEST 3 (0xaf82). TEST 1 signs the empty
# message, which the OpenSSL command line cannot do; a PAE message is never empty.
RFC8032 = [
    (OTHER_SEED, b"\x72", "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    (bytes.fromhex("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7"), b"\xaf\x82",
     "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
]
ENGINE = "calimocho-11.20-4.0b3-06"


def key_file(directory, seed, name):
    path = Path(directory) / name
    path.write_text(ei.private_key_pem_from_seed(seed))
    path.chmod(0o600)
    return path


def base_payload(entry, **changes):
    payload = {"schema": "calimocho-engine-index/1", "epoch": 1, "index_version": 1,
               "generated_at": "2026-10-26T12:00:00Z", "expires_at": "2026-11-25T12:00:00Z",
               "publisher": "WorkingPrinciple/calimocho", "engines": [entry], "revoked": []}
    payload.update(changes)
    return payload


def build(directory):
    """Write the full vector into directory (deterministic)."""
    directory = Path(directory)
    with tempfile.TemporaryDirectory() as scratch:
        test_key = key_file(scratch, TEST_SEED, "test.pem")
        other_key = key_file(scratch, OTHER_SEED, "other.pem")
        test_public, other_public = ei.public_key_of(test_key), ei.public_key_of(other_key)
        test_id, other_id = ei.keyid(test_public), ei.keyid(other_public)
        entry = json.loads((HERE / "entry-06.json").read_text())
        files = {}

        def write(name, document):
            files[name] = json.dumps(document, indent=2) + "\n"
            (directory / name).write_text(files[name])

        def envelope(body, key=test_key, payload_type=ei.PAYLOAD_TYPE, encoding=None):
            sig = ei.sign_bytes(key, ei.pae(payload_type, body))
            return {"payloadType": payload_type,
                    "payload": encoding or base64.b64encode(body).decode(),
                    "signatures": [{"keyid": ei.keyid(ei.public_key_of(key)),
                                    "sig": base64.b64encode(sig).decode()}]}

        good = ei.canonical(base_payload(entry))
        (directory / "payload.json").write_bytes(good)
        message = ei.pae(ei.PAYLOAD_TYPE, good)
        signature = ei.sign_bytes(test_key, message)
        write("envelope.json", envelope(good))
        v2 = ei.canonical(base_payload(entry, index_version=2, generated_at="2026-10-26T13:00:00Z",
                                       expires_at="2026-11-25T13:00:00Z"))
        write("envelope-v2.json", envelope(v2))
        equivocation = ei.canonical(base_payload(entry, expires_at="2026-11-24T12:00:00Z"))
        write("envelope-equivocation.json", envelope(equivocation))
        epoch2 = ei.canonical(base_payload(entry, epoch=2))
        write("envelope-epoch2-other-key.json", envelope(epoch2, other_key))
        write("envelope-epoch2-test-key.json", envelope(epoch2))

        # Valid signatures over invalid payloads: each must fail on content, not cryptography.
        def bad(name, mutate):
            document = json.loads(good)
            mutate(document)
            write(name, envelope(ei.canonical(document)))
        url = "https://github.com/WorkingPrinciple/calimocho/releases/download/engine-0.1120.4.6/"
        bad("envelope-bad-dot-name.json", lambda d: d["engines"][0]["asset"].update(name="..", url=url + ".."))
        bad("envelope-bad-hidden-name.json",
            lambda d: d["engines"][0]["asset"].update(name=".zip", url=url + ".zip"))
        bad("envelope-bad-newline.json", lambda d: d["engines"][0].update(engine_id=ENGINE + "\n"))
        bad("envelope-bad-nul.json", lambda d: d["revoked"].append(
            {"engine_id": "calimocho-11.20-4.0b3-05", "reason": "bad\u0000reason"}))
        bad("envelope-bad-url-userinfo.json", lambda d: d["engines"][0]["asset"].update(
            url=url.replace("https://github.com", "https://x@github.com") + d["engines"][0]["asset"]["name"]))
        bad("envelope-bad-url-port.json", lambda d: d["engines"][0]["asset"].update(
            url=url.replace("github.com", "github.com:443") + d["engines"][0]["asset"]["name"]))
        bad("envelope-bad-url-http.json", lambda d: d["engines"][0]["asset"].update(
            url=url.replace("https:", "http:") + d["engines"][0]["asset"]["name"]))
        bad("envelope-bad-index-cap.json", lambda d: d.update(index_version=2147483648))
        duplicate = good.replace(b'{"engines"', b'{"epoch":2,"engines"', 1)
        assert duplicate != good
        write("envelope-bad-duplicate-key.json", envelope(duplicate))
        padded = good + b" " * (1 if len(good) % 3 == 0 else 0)
        canonical_b64 = base64.b64encode(padded).decode()
        data = canonical_b64.rstrip("=")
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
        last = alphabet[alphabet.index(data[-1]) | 1]
        noncanonical = data[:-1] + last + canonical_b64[len(data):]
        assert base64.b64decode(noncanonical) == padded and noncanonical != canonical_b64
        write("envelope-bad-noncanonical-base64.json", envelope(padded, encoding=noncanonical))
        tampered = good.replace(b'"size":200075043', b'"size":200075044')
        write("envelope-bad-tampered.json", {**envelope(good), "payload": base64.b64encode(tampered).decode()})
        write("envelope-bad-wrong-type.json", envelope(good, payload_type="application/json"))
        write("envelope-bad-untrusted-key.json", envelope(good, other_key))

        def trust(name, keys, revoked_keyids=(), floor=(1, 1), revoked_engines=()):
            write(name, {"schema": "calimocho-engine-index-trust/1",
                         "description": "TEST ONLY. Public RFC 8032 keys; never ship.",
                         "keys": [{"keyid": ei.keyid(p), "public_key": base64.b64encode(p).decode(),
                                   "epoch": e, "status": "active", "created": "2026-10-26"} for p, e in keys],
                         "revoked_keyids": list(revoked_keyids),
                         "floor": {"epoch": floor[0], "index_version": floor[1]},
                         "revoked_engines": list(revoked_engines)})
        trust("trust.test.json", [(test_public, 1)])
        trust("trust-floor-2.test.json", [(test_public, 1)], floor=(1, 2))
        trust("trust-revoked-key.test.json", [(test_public, 1)], revoked_keyids=[test_id])
        trust("trust-revoked-other.test.json", [(test_public, 1)], revoked_keyids=[other_id])
        trust("trust-revoked-engine.test.json", [(test_public, 1)],
              revoked_engines=[{"engine_id": ENGINE, "reason": "test revocation"}])
        trust("trust-epoch2.test.json", [(test_public, 1), (other_public, 2)])

        def state(epoch, version, body, keyids=(test_id,), revoked=()):
            return {"schema": "calimocho-engine-index-state/1", "epoch": epoch, "index_version": version,
                    "payload_sha256": ei.sha256_bytes(body), "keyids": list(keyids),
                    "revoked_engines": list(revoked)}
        fresh = state(1, 1, good)
        cases = [
            {"name": "valid", "envelope": "envelope.json", "xode_version": "0.2.0",
             "expect": "valid", "eligible": [ENGINE], "new_state": fresh},
            {"name": "X Ode too old", "envelope": "envelope.json", "xode_version": "0.1.9",
             "expect": "valid", "eligible": []},
            {"name": "same version installed", "envelope": "envelope.json", "installed_version": "0.1120.4.6",
             "expect": "valid", "eligible": []},
            {"name": "older version installed", "envelope": "envelope.json", "installed_version": "0.1120.4.4",
             "expect": "valid", "eligible": [ENGINE]},
            {"name": "numeric compare (4.10 > 4.6)", "envelope": "envelope.json",
             "installed_version": "0.1120.4.10", "expect": "valid", "eligible": []},
            {"name": "same index again", "envelope": "envelope.json", "state": fresh,
             "expect": "valid", "eligible": [ENGINE], "new_state": fresh},
            {"name": "newer index", "envelope": "envelope-v2.json", "state": fresh,
             "expect": "valid", "eligible": [ENGINE], "new_state": state(1, 2, v2)},
            {"name": "persisted revocation", "envelope": "envelope.json",
             "state": state(1, 1, good, revoked=[{"engine_id": ENGINE, "reason": "test revocation"}]),
             "expect": "valid", "eligible": []},
            {"name": "embedded revocation", "envelope": "envelope.json", "trust": "trust-revoked-engine.test.json",
             "expect": "valid", "eligible": []},
            {"name": "state from revoked key is discarded", "envelope": "envelope.json",
             "trust": "trust-revoked-other.test.json", "state": state(1, 7, b"x", keyids=[other_id]),
             "expect": "valid", "eligible": [ENGINE], "new_state": fresh},
            {"name": "new epoch resets the high-water mark", "envelope": "envelope-epoch2-other-key.json",
             "trust": "trust-epoch2.test.json", "state": state(1, 2, v2),
             "expect": "valid", "eligible": [ENGINE], "new_state": state(2, 1, epoch2, keyids=[other_id])},
            {"name": "rollback", "envelope": "envelope.json", "state": state(1, 2, v2), "expect": "invalid"},
            {"name": "state from a trusted key is honoured", "envelope": "envelope.json",
             "state": state(1, 7, b"x", keyids=[other_id]), "expect": "invalid"},
            {"name": "older epoch", "envelope": "envelope.json", "trust": "trust-epoch2.test.json",
             "state": state(2, 1, epoch2, keyids=[other_id]), "expect": "invalid"},
            {"name": "equivocation", "envelope": "envelope-equivocation.json", "state": fresh, "expect": "invalid"},
            {"name": "below embedded floor", "envelope": "envelope.json", "trust": "trust-floor-2.test.json",
             "expect": "invalid"},
            {"name": "revoked signing key", "envelope": "envelope.json", "trust": "trust-revoked-key.test.json",
             "expect": "invalid"},
            {"name": "key not bound to payload epoch", "envelope": "envelope-epoch2-test-key.json",
             "trust": "trust-epoch2.test.json", "expect": "invalid"},
            {"name": "expired", "envelope": "envelope.json", "now": "2026-11-25T12:06:00Z", "expect": "invalid"},
            {"name": "from the future", "envelope": "envelope.json", "now": "2026-10-26T11:54:00Z",
             "expect": "invalid"},
        ]
        for name in sorted(files):
            if name.startswith("envelope-bad-"):
                cases.append({"name": name, "envelope": name, "expect": "invalid"})
        for case in cases:
            case.setdefault("trust", "trust.test.json")
            case.setdefault("now", NOW)
        write("vector.json", {
            "description": "Known-answer vector for calimocho-engine-index/1 in a DSSE v1 envelope (ADR-0082). "
                           "Run every case with the named trust file, optional prior state, now, X Ode version "
                           "and installed Calimocho version; valid cases must yield exactly 'eligible' and "
                           "'new_state'.",
            "test_key": {"source": "RFC 8032 section 7.1, TEST 1", "warning": "Public test key. Never trust it.",
                         "seed_hex": TEST_SEED.hex(), "public_key_hex": test_public.hex(), "keyid": test_id,
                         "epoch": 1},
            "epoch2_test_key": {"source": "RFC 8032 section 7.1, TEST 2", "public_key_hex": other_public.hex(),
                                "keyid": other_id, "epoch": 2},
            "payload_type": ei.PAYLOAD_TYPE,
            "payload_sha256": ei.sha256_bytes(good),
            "pae_prefix": message[:message.index(b"{")].decode(),
            "pae_sha256": ei.sha256_bytes(message),
            "signature_hex": signature.hex(),
            "cases": cases,
        })


# ------------------------------------------------------------------ synthetic engine zips

def make_zip(path, members):
    """members: list of (name, kind, data) with kind file|dir|symlink|fifo."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, kind, data in members:
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 26, 0, 0, 0))
            info.create_system = 3
            mode = {"file": stat.S_IFREG | 0o644, "dir": stat.S_IFDIR | 0o755,
                    "symlink": stat.S_IFLNK | 0o777, "fifo": stat.S_IFIFO | 0o644}[kind]
            info.external_attr = mode << 16
            archive.writestr(info, data if kind != "dir" else b"")


def fake_engine(directory, extra=(), drop_manifest_line=None, bound=None, rename=None):
    top = "calimocho-11.20-4.0b3-99"
    files = {"bin/wine": b"wine", "bin/wineserver": b"server", "lib/wine/x86_64-unix/wine": b"loader",
             "calimocho-engine.json": b"{}", "lib/external/libd3dshared.dylib": b"apple"}
    links = {"lib/wine/x86_64-unix/d3d12.so": "../../external/libd3dshared.dylib"}
    lines = [f"{ei.sha256_bytes(v)}  {k}" for k, v in sorted(files.items())]
    lines += [f"link {v}  {k}" for k, v in sorted(links.items())]
    if drop_manifest_line:
        lines = [line for line in lines if not line.endswith(drop_manifest_line)]
    manifest = ("\n".join(lines) + "\n").encode()
    members = [(f"{top}/", "dir", b"")]
    members += [(f"{top}/{k}", "file", v) for k, v in files.items()]
    members += [(f"{top}/{k}", "symlink", v.encode()) for k, v in links.items()]
    members += [(f"{top}/MANIFEST.sha256", "file", manifest)]
    members += [(name.replace("TOP", top), kind, data) for name, kind, data in extra]
    if rename:
        members = [(rename(n), k, d) for n, k, d in members]
    path = Path(directory) / f"{top}.zip"
    make_zip(path, members)
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        unpacked = {"size": sum(i.file_size for i in infos), "entries": len(infos)}
    entry = {"install": {"directory": top}, "asset": {"size": path.stat().st_size, "sha256": ei.sha256_file(path)},
             "unpacked": bound or unpacked, "signing": {"team_id": ei.TEAM_ID},
             "hashes": {"wine_sha256": ei.sha256_bytes(b"wine"), "wineserver_sha256": ei.sha256_bytes(b"server"),
                        "loader_sha256": ei.sha256_bytes(b"loader"), "manifest_sha256": ei.sha256_bytes(manifest),
                        "engine_json_sha256": ei.sha256_bytes(b"{}")}}
    return path, entry


class EngineIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vector = json.loads((HERE / "vector.json").read_text())

    def test_rfc8032_known_answers(self):
        with tempfile.TemporaryDirectory() as scratch:
            for number, (seed, message, public_hex, signature_hex) in enumerate(RFC8032):
                key = key_file(scratch, seed, f"k{number}.pem")
                self.assertEqual(ei.public_key_of(key).hex(), public_hex)
                self.assertEqual(ei.sign_bytes(key, message).hex(), signature_hex)
                self.assertTrue(ei.verify_bytes(bytes.fromhex(public_hex), message, bytes.fromhex(signature_hex)))
                self.assertFalse(ei.verify_bytes(bytes.fromhex(public_hex), message + b"x",
                                                 bytes.fromhex(signature_hex)))

    def test_vector_is_reproducible(self):
        with tempfile.TemporaryDirectory() as scratch:
            build(scratch)
            produced = sorted(p.name for p in Path(scratch).iterdir())
            committed = sorted(p.name for p in HERE.iterdir()
                               if p.suffix == ".json" and p.name != "entry-06.json")
            self.assertEqual(produced, committed)
            for name in produced:
                self.assertEqual((Path(scratch) / name).read_bytes(), (HERE / name).read_bytes(), name)

    def test_pae_and_signature(self):
        payload = (HERE / "payload.json").read_bytes()
        message = ei.pae(self.vector["payload_type"], payload)
        self.assertEqual(ei.sha256_bytes(payload), self.vector["payload_sha256"])
        self.assertEqual(ei.sha256_bytes(message), self.vector["pae_sha256"])
        self.assertTrue(message.startswith(self.vector["pae_prefix"].encode()))
        public = bytes.fromhex(self.vector["test_key"]["public_key_hex"])
        self.assertTrue(ei.verify_bytes(public, message, bytes.fromhex(self.vector["signature_hex"])))

    def test_cases(self):
        names = set()
        for case in self.vector["cases"]:
            names.add(case["name"])
            trust = ei.load_trust(HERE / case["trust"])
            raw = (HERE / case["envelope"]).read_bytes()
            run = lambda: ei.verify_envelope(raw, trust, case.get("state"), ei.utc(case["now"]),  # noqa: E731
                                             case.get("xode_version"), case.get("installed_version"))
            with self.subTest(case=case["name"]):
                if case["expect"] == "valid":
                    _, eligible, new_state = run()
                    self.assertEqual([e["engine_id"] for e in eligible], case["eligible"])
                    if "new_state" in case:
                        self.assertEqual(new_state, case["new_state"])
                else:
                    with self.assertRaises(ei.IndexError_):
                        run()
        self.assertGreaterEqual(len(names), 30)

    def test_negative_envelopes_have_valid_signatures(self):
        """Content negatives must be rejected by the rules, not by a broken signature."""
        public = bytes.fromhex(self.vector["test_key"]["public_key_hex"])
        content = [p for p in HERE.glob("envelope-bad-*.json")
                   if p.name not in ("envelope-bad-tampered.json", "envelope-bad-wrong-type.json",
                                     "envelope-bad-untrusted-key.json")]
        self.assertGreaterEqual(len(content), 9)
        for path in content:
            envelope = json.loads(path.read_text())
            body = base64.b64decode(envelope["payload"])
            sig = base64.b64decode(envelope["signatures"][0]["sig"])
            with self.subTest(path=path.name):
                self.assertTrue(ei.verify_bytes(public, ei.pae(envelope["payloadType"], body), sig))

    def test_payload_rules(self):
        base = json.loads((HERE / "payload.json").read_text())
        mutations = {
            "unknown field": lambda d: d.update(extra=1),
            "install dir": lambda d: d["engines"][0]["install"].update(directory="calimocho-11.20-4.0b3-05"),
            "foreign url": lambda d: d["engines"][0]["asset"].update(url="https://example.com/x.zip"),
            "query": lambda d: d["engines"][0]["asset"].update(url=d["engines"][0]["asset"]["url"] + "?x=1"),
            "tag mismatch": lambda d: d["engines"][0].update(release_tag="engine-0.1120.4.4"),
            "bad sha": lambda d: d["engines"][0]["hashes"].update(wine_sha256="00"),
            "sha newline": lambda d: d["engines"][0]["hashes"].update(
                wine_sha256=d["engines"][0]["hashes"]["wine_sha256"] + "\n"),
            "team": lambda d: d["engines"][0]["signing"].update(team_id="ABCDEFGHIJ"),
            "too long": lambda d: d.update(expires_at="2027-03-01T12:00:00Z"),
            "revoked listed": lambda d: d["revoked"].append({"engine_id": ENGINE, "reason": "x"}),
            "duplicate": lambda d: d["engines"].append(copy.deepcopy(d["engines"][0])),
            "bool version": lambda d: d.update(index_version=True),
            "float epoch": lambda d: d.update(epoch=1.0),
            "epoch zero": lambda d: d.update(epoch=0),
            "control char": lambda d: d["engines"][0]["components"].update(wine="11.20\t"),
        }
        ei.check_payload(base)
        for name, mutate in mutations.items():
            document = copy.deepcopy(base)
            mutate(document)
            with self.subTest(name=name), self.assertRaises(ei.IndexError_):
                ei.check_payload(document)

    def test_release_url_is_parsed(self):
        """Second layer behind the schema pattern: the URL is parsed, not compared as a string."""
        good = "https://github.com/WorkingPrinciple/calimocho/releases/download/engine-0.1120.4.6/a.zip"
        ei.release_url(good, "download", "engine-0.1120.4.6", "a.zip")
        for url in (good.replace("https:", "http:"), good.replace("github.com", "x@github.com"),
                    good.replace("github.com", "github.com:443"), good + "?x=1", good + "#f",
                    good.replace("github.com", "github.com.evil"), good.replace("engine-0.1120.4.6", "engine-0.1120.4.4"),
                    good.replace("/a.zip", "/b.zip"), good.replace("WorkingPrinciple", "workingprinciple")):
            with self.subTest(url=url), self.assertRaises(ei.IndexError_):
                ei.release_url(url, "download", "engine-0.1120.4.6", "a.zip")

    def test_strict_json(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(ei.IndexError_):
                ei.strict_json(raw)

    def test_check_zip(self):
        with tempfile.TemporaryDirectory() as scratch:
            path, entry = fake_engine(scratch)
            self.assertEqual(ei.check_zip(path, entry)["symlinks"], 1)
            cases = {
                "absolute path": dict(extra=[("/etc/passwd", "file", b"x")]),
                "dot dot": dict(extra=[("TOP/../escape", "file", b"x")]),
                "backslash": dict(extra=[("TOP/a\\b", "file", b"x")]),
                "control char": dict(extra=[("TOP/a\x01b", "file", b"x")]),
                "outside top": dict(extra=[("other/file", "file", b"x")]),
                "symlink escape": dict(extra=[("TOP/escape", "symlink", b"../../outside")]),
                "absolute symlink": dict(extra=[("TOP/abs", "symlink", b"/etc/passwd")]),
                "dangling symlink": dict(extra=[("TOP/dangle", "symlink", b"missing")]),
                "write through symlink": dict(extra=[("TOP/lib/wine/x86_64-unix/d3d12.so/x", "file", b"x")]),
                "duplicate": dict(extra=[("TOP/bin/wine", "file", b"wine")]),
                "case collision": dict(extra=[("TOP/BIN/WINE", "file", b"x")]),
                "unicode collision": dict(extra=[("TOP/caf\u00e9", "file", b"x"), ("TOP/cafe\u0301", "file", b"y")]),
                "fifo or hard link": dict(extra=[("TOP/pipe", "fifo", b"")]),
                "bytes exceed bound": dict(bound={"size": 10, "entries": 100}),
                "entries exceed bound": dict(bound={"size": 1 << 30, "entries": 3}),
                "unlisted file": dict(extra=[("TOP/unlisted", "file", b"x")]),
                "manifest lists missing": dict(drop_manifest_line="bin/wineserver"),
            }
            for name, kwargs in cases.items():
                with tempfile.TemporaryDirectory() as inner, self.subTest(name=name):
                    path, entry = fake_engine(inner, **kwargs)
                    with self.assertRaises(ei.IndexError_):
                        ei.check_zip(path, entry)
            # A different zip than the signed one is refused before anything else.
            path, entry = fake_engine(scratch)
            entry["asset"]["sha256"] = "0" * 64
            with self.assertRaises(ei.IndexError_):
                ei.check_zip(path, entry)

    def test_key_files(self):
        with tempfile.TemporaryDirectory() as scratch:
            key = key_file(scratch, TEST_SEED, "loose.pem")
            key.chmod(0o644)
            with self.assertRaises(ei.IndexError_):
                ei.public_key_of(key)
            key.chmod(0o600)
            payload = Path(scratch) / "payload.json"
            payload.write_bytes((HERE / "payload.json").read_bytes())
            out = Path(scratch) / "env.json"
            refused = subprocess.run([sys.executable, str(TOOL), "sign", "--payload", str(payload),
                                      "--key", str(key), "--out", str(out)], capture_output=True, text=True)
            self.assertEqual(refused.returncode, 1)
            self.assertIn("not passphrase-encrypted", refused.stderr)
            environment = {**os.environ, ei.PASSPHRASE_ENV: "test passphrase, never used for real keys"}
            encrypted = subprocess.run([sys.executable, str(TOOL), "encrypt-key", "--key", str(key)],
                                       capture_output=True, text=True, env=environment)
            self.assertEqual(encrypted.returncode, 0, encrypted.stderr)
            self.assertTrue(ei.key_is_encrypted(key))
            self.assertEqual(stat.S_IMODE(key.stat().st_mode), 0o600)
            signed = subprocess.run([sys.executable, str(TOOL), "sign", "--payload", str(payload),
                                     "--key", str(key), "--out", str(out)], capture_output=True, text=True,
                                    env=environment)
            self.assertEqual(signed.returncode, 0, signed.stderr)
            self.assertEqual(json.loads(out.read_text()), json.loads((HERE / "envelope.json").read_text()))
            wrong = subprocess.run([sys.executable, str(TOOL), "pubkey", "--key", str(key)],
                                   capture_output=True, text=True,
                                   env={**os.environ, ei.PASSPHRASE_ENV: "wrong"})
            self.assertEqual(wrong.returncode, 1)

    def test_independent_implementation(self):
        """Cross-check with pyca/cryptography when an interpreter has it (Apple's /usr/bin/python3 does)."""
        program = (
            "import json,sys\n"
            "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey, Ed25519PrivateKey\n"
            "v=json.load(open(sys.argv[1]+'/vector.json'))\n"
            "p=open(sys.argv[1]+'/payload.json','rb').read()\n"
            "t=v['payload_type'].encode()\n"
            "m=b'DSSEv1 %d %s %d %s'%(len(t),t,len(p),p)\n"
            "k=Ed25519PrivateKey.from_private_bytes(bytes.fromhex(v['test_key']['seed_hex']))\n"
            "assert k.sign(m).hex()==v['signature_hex']\n"
            "Ed25519PublicKey.from_public_bytes(bytes.fromhex(v['test_key']['public_key_hex'])).verify(bytes.fromhex(v['signature_hex']),m)\n"
            "print('cryptography ok')\n")
        for python in ("/usr/bin/python3", sys.executable):
            if subprocess.run([python, "-c", "import cryptography"], capture_output=True).returncode == 0:
                result = subprocess.run([python, "-c", program, str(HERE)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                return
        self.skipTest("no interpreter with pyca/cryptography")

    def test_cryptokit(self):
        """X Ode verifies with CryptoKit; check the vector's signatures with it when Swift is available."""
        swift = shutil.which("swift")
        if not swift:
            self.skipTest("swift not available")
        result = subprocess.run([swift, str(HERE / "verify_vector.swift"), str(HERE)],
                                capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CryptoKit ok", result.stdout)


if __name__ == "__main__":
    if "--regenerate" in sys.argv:
        build(HERE)
        print(f"regenerated vector in {HERE}")
    else:
        unittest.main()
