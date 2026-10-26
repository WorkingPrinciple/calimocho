#!/usr/bin/env python3
"""Test vector and tests for the signed engine release index (ADR-0082, REQ-124).

  python3 tests/engine-index/test_engine_index.py              run the tests
  python3 tests/engine-index/test_engine_index.py --regenerate rewrite the vector files

The vector is signed with the RFC 8032 section 7.1 TEST 1 key. That key is public; it must
never be trusted by X Ode or the backend. Ed25519 is deterministic, so every implementation
must reproduce signature_hex exactly.
"""

import base64
import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
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


def key_file(directory, seed, name):
    path = Path(directory) / name
    path.write_text(ei.private_key_pem_from_seed(seed))
    path.chmod(0o600)
    return path


def build(directory):
    """Write the full vector into directory (deterministic)."""
    directory = Path(directory)
    with tempfile.TemporaryDirectory() as scratch:
        test_key = key_file(scratch, TEST_SEED, "test.pem")
        other_key = key_file(scratch, OTHER_SEED, "other.pem")
        entry = json.loads((HERE / "entry-06.json").read_text())
        payload = {"schema": "calimocho-engine-index/1", "index_version": 1,
                   "generated_at": "2026-10-26T12:00:00Z", "expires_at": "2026-11-25T12:00:00Z",
                   "publisher": "WorkingPrinciple/calimocho", "engines": [entry], "revoked": []}
        ei.check_payload(payload)
        payload_bytes = ei.canonical(payload)
        (directory / "payload.json").write_bytes(payload_bytes)
        message = ei.pae(ei.PAYLOAD_TYPE, payload_bytes)
        public = ei.public_key_of(test_key)
        signature = ei.sign_bytes(test_key, message)

        def envelope(payload_type, body, key, sig=None):
            pub = ei.public_key_of(key)
            sig = sig if sig is not None else ei.sign_bytes(key, ei.pae(payload_type, body))
            return {"payloadType": payload_type, "payload": base64.b64encode(body).decode(),
                    "signatures": [{"keyid": ei.keyid(pub), "sig": base64.b64encode(sig).decode()}]}

        def write(name, document):
            (directory / name).write_text(json.dumps(document, indent=2) + "\n")

        write("envelope.json", envelope(ei.PAYLOAD_TYPE, payload_bytes, test_key, signature))
        tampered = payload_bytes.replace(b'"size":200075043', b'"size":200075044')
        assert tampered != payload_bytes
        write("envelope-tampered-payload.json", envelope(ei.PAYLOAD_TYPE, tampered, test_key, signature))
        write("envelope-wrong-type.json", envelope("application/json", payload_bytes, test_key))
        write("envelope-untrusted-key.json", envelope(ei.PAYLOAD_TYPE, payload_bytes, other_key))
        write("trusted-keys.test.json", {
            "schema": "calimocho-engine-index-keys/1",
            "keys": [{"keyid": ei.keyid(public), "public_key": base64.b64encode(public).decode(),
                      "status": "active", "created": "2026-10-26",
                      "note": "RFC 8032 TEST 1 key. TEST ONLY: never ship this key in X Ode or the backend."}]})
        write("vector.json", {
            "description": "Known-answer vector for calimocho-engine-index/1 in a DSSE v1 envelope (ADR-0082).",
            "test_key": {"source": "RFC 8032 section 7.1, TEST 1", "warning": "Public test key. Never trust it.",
                         "seed_hex": TEST_SEED.hex(), "public_key_hex": public.hex(), "keyid": ei.keyid(public)},
            "payload_type": ei.PAYLOAD_TYPE,
            "payload_sha256": ei.sha256_bytes(payload_bytes),
            "pae_prefix": message[:message.index(b"{")].decode(),
            "pae_sha256": ei.sha256_bytes(message),
            "signature_hex": signature.hex(),
            "cases": [
                {"envelope": "envelope.json", "now": NOW, "xode_version": "0.2.0", "min_index_version": 0,
                 "expect": "valid", "eligible": ["calimocho-11.20-4.0b3-06"]},
                {"envelope": "envelope.json", "now": NOW, "xode_version": "0.1.9", "min_index_version": 0,
                 "expect": "valid", "eligible": []},
                {"envelope": "envelope.json", "now": "2026-11-25T12:06:00Z", "expect": "invalid", "why": "expired"},
                {"envelope": "envelope.json", "now": "2026-10-26T11:54:00Z", "expect": "invalid", "why": "from the future"},
                {"envelope": "envelope.json", "now": NOW, "min_index_version": 2, "expect": "invalid", "why": "rollback"},
                {"envelope": "envelope-tampered-payload.json", "now": NOW, "expect": "invalid", "why": "bad signature"},
                {"envelope": "envelope-wrong-type.json", "now": NOW, "expect": "invalid", "why": "payloadType"},
                {"envelope": "envelope-untrusted-key.json", "now": NOW, "expect": "invalid", "why": "untrusted key"},
            ],
        })


class EngineIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vector = json.loads((HERE / "vector.json").read_text())
        cls.trusted = ei.load_trusted_keys(HERE / "trusted-keys.test.json")

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
            for path in sorted(Path(scratch).iterdir()):
                self.assertEqual(path.read_bytes(), (HERE / path.name).read_bytes(), path.name)

    def test_pae_and_signature(self):
        payload = (HERE / "payload.json").read_bytes()
        message = ei.pae(self.vector["payload_type"], payload)
        self.assertEqual(ei.sha256_bytes(payload), self.vector["payload_sha256"])
        self.assertEqual(ei.sha256_bytes(message), self.vector["pae_sha256"])
        self.assertTrue(message.startswith(self.vector["pae_prefix"].encode()))
        public = bytes.fromhex(self.vector["test_key"]["public_key_hex"])
        self.assertTrue(ei.verify_bytes(public, message, bytes.fromhex(self.vector["signature_hex"])))

    def test_cases(self):
        for case in self.vector["cases"]:
            raw = (HERE / case["envelope"]).read_bytes()
            run = lambda: ei.verify_envelope(raw, self.trusted, ei.utc(case["now"]),  # noqa: E731
                                             case.get("min_index_version", 0), case.get("xode_version"))
            with self.subTest(case=case):
                if case["expect"] == "valid":
                    _, eligible, _ = run()
                    self.assertEqual([e["engine_id"] for e in eligible], case["eligible"])
                else:
                    with self.assertRaises(ei.IndexError_):
                        run()

    def test_payload_rules(self):
        base = json.loads((HERE / "payload.json").read_text())
        mutations = {
            "unknown field": lambda d: d.update(extra=1),
            "install dir": lambda d: d["engines"][0]["install"].update(directory="calimocho-11.20-4.0b3-05"),
            "foreign url": lambda d: d["engines"][0]["asset"].update(url="https://example.com/x.zip"),
            "tag mismatch": lambda d: d["engines"][0].update(release_tag="engine-0.1120.4.4"),
            "bad sha": lambda d: d["engines"][0]["hashes"].update(wine_sha256="00"),
            "team": lambda d: d["engines"][0]["signing"].update(team_id="ABCDEFGHIJ"),
            "too long": lambda d: d.update(expires_at="2027-03-01T12:00:00Z"),
            "revoked listed": lambda d: d["revoked"].append({"engine_id": "calimocho-11.20-4.0b3-06", "reason": "x"}),
            "duplicate": lambda d: d["engines"].append(json.loads(json.dumps(d["engines"][0]))),
            "bool version": lambda d: d.update(index_version=True),
        }
        ei.check_payload(base)
        for name, mutate in mutations.items():
            document = json.loads(json.dumps(base))
            mutate(document)
            with self.subTest(name=name), self.assertRaises(ei.IndexError_):
                ei.check_payload(document)

    def test_key_file_permissions(self):
        with tempfile.TemporaryDirectory() as scratch:
            key = key_file(scratch, TEST_SEED, "loose.pem")
            key.chmod(0o644)
            with self.assertRaises(ei.IndexError_):
                ei.public_key_of(key)

    def test_independent_implementation(self):
        """Cross-check with pyca/cryptography when an interpreter has it (Apple's /usr/bin/python3 does)."""
        program = (
            "import base64,json,sys\n"
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
        """X Ode verifies with CryptoKit; check the vector with it when Swift is available."""
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
