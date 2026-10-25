import base64
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools.prepare_verified_activation import prepare

from tools.verify_installed_appx import (
    BLOCK_NS, SHA256_URI, check_certificate_extensions, der_nodes,
    encode_der, signed_digests, timestamp_time, verify_blocks, verify_signature, verify_timestamp,
)


def der(tag, data):
    size = len(data)
    count = (size.bit_length() + 7) // 8
    length = bytes([size]) if size < 128 else bytes([128 + count]) + size.to_bytes(count, "big")
    return bytes([tag]) + length + data


def timestamp_token(content):
    return der(0x30, der(6, bytes.fromhex("2a864886f70d010702")) +
               der(0xa0, der(0x30, der(2, b"\x03") + der(0x31, b"") +
                             der(0x30, der(6, bytes.fromhex("2a864886f70d0109100104")) +
                                 der(0xa0, der(4, content))))))


class InstalledAppxTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "AppxManifest.xml").write_bytes(b"fixture manifest")
        (self.root / "app.exe").write_bytes(b"MZ" + b"owned fixture" * 6000)
        self.blockmap = self.make_blockmap()

    def make_blockmap(self):
        files = []
        for name in ("AppxManifest.xml", "app.exe"):
            data = (self.root / name).read_bytes()
            blocks = "".join(
                '<Block Hash="' + base64.b64encode(hashlib.sha256(
                    data[offset:offset + 65536]).digest()).decode() + '"/>'
                for offset in range(0, len(data), 65536))
            files.append(f'<File Name="{name}" Size="{len(data)}">{blocks}</File>')
        return (f'<BlockMap xmlns="{BLOCK_NS[1:-1]}" HashMethod="{SHA256_URI}">'
                + "".join(files) + "</BlockMap>").encode()

    def test_complete_multiblock_files_match(self):
        self.assertEqual(verify_blocks(self.root, self.blockmap), 2)

    def test_same_size_tampered_file_is_rejected(self):
        data = (self.root / "app.exe").read_bytes()
        (self.root / "app.exe").write_bytes(data[:-1] + b"?")
        with self.assertRaisesRegex(ValueError, "Block hash mismatch"):
            verify_blocks(self.root, self.blockmap)

    def test_unlisted_executable_rejected_even_without_exe_suffix(self):
        (self.root / "extra.dat").write_bytes(b"MZhidden executable")
        with self.assertRaisesRegex(ValueError, "Unlisted executable"):
            verify_blocks(self.root, self.blockmap)

    def test_traversal_symlink_duplicates_and_missing_blocks_rejected(self):
        for altered in (
            self.blockmap.replace(b'app.exe', b'..\\app.exe'),
            self.blockmap.replace(b'</BlockMap>', self.blockmap.split(b'>', 1)[1]),
            self.blockmap.replace(b'<Block Hash=', b'<Other Hash='),
        ):
            with self.assertRaises(ValueError):
                verify_blocks(self.root, altered)
        (self.root / "link").symlink_to(self.root / "app.exe")
        with self.assertRaisesRegex(ValueError, "symlink"):
            verify_blocks(self.root, self.blockmap)

    def test_wrong_root_rejected_before_any_openssl_execution(self):
        wrong = self.root / "wrong.der"
        wrong.write_bytes(b"not a pinned root")
        with patch("tools.verify_installed_appx.command") as command:
            with self.assertRaisesRegex(ValueError, "Unpinned"):
                verify_signature(self.root, [wrong], "unused-openssl")
        command.assert_not_called()

    def test_failed_verification_never_emits_server_registration(self):
        package = self.root / "package"
        package.mkdir()
        (package / "fixture").write_bytes(b"untrusted")
        output = self.root / "registration-output"
        with patch("tools.prepare_verified_activation.verify", side_effect=ValueError("bad signature")):
            with self.assertRaisesRegex(ValueError, "bad signature"):
                prepare(package, "App", [], "unused", output)
        self.assertFalse((output / "registration.bin").exists())

    def test_snapshot_cannot_be_created_inside_source(self):
        with self.assertRaisesRegex(ValueError, "outside the source"):
            prepare(self.root, "App", [], "unused", self.root / "output")

    def test_missing_store_eku_rejected_after_verified_signature(self):
        roots = self.root / "root.der"
        roots.write_bytes(b"test root")
        (self.root / "AppxSignature.p7x").write_bytes(b"PKCXtest signature")
        pins = {"appx_trust_roots": [{"sha256": hashlib.sha256(b"test root").hexdigest()}]}
        cert = b"-----BEGIN CERTIFICATE-----\nMAMCAQE=\n-----END CERTIFICATE-----"

        def openssl(_binary, *args):
            if args[0] == "pkcs7":
                return cert
            if args[0] == "smime":
                Path(args[args.index("-signer") + 1]).write_bytes(cert)
                Path(args[args.index("-out") + 1]).write_bytes(b"unused")
                return b""
            if "-ext" in args:
                return b"X509v3 Extended Key Usage:\n Code Signing\n"
            return cert

        with patch("tools.verify_installed_appx.json.loads", return_value=pins), \
                patch("tools.verify_installed_appx.command", side_effect=openssl), \
                patch("tools.verify_installed_appx.check_certificate_extensions"), \
                patch("tools.verify_installed_appx.TSA_ROOT_SHA256", hashlib.sha256(b"test root").hexdigest()), \
                patch("tools.verify_installed_appx.verify_timestamp", return_value=1):
            with self.assertRaisesRegex(ValueError, "Store signing EKU"):
                verify_signature(self.root, [roots], "fixture-openssl")

    def timestamp_fixture(self, imprint):
        algorithm = der(0x30, bytes.fromhex("06096086480165030402010500"))
        return der(0x30, der(2, b"\x01") + der(6, b"\x2a\x03") +
                   der(0x30, algorithm + der(4, imprint)) + der(2, b"\x01") +
                   der(0x18, b"20261014183059.504Z"))

    def test_tampered_timestamp_imprint_rejected(self):
        content = self.timestamp_fixture(b"\0" * 32)

        def openssl(_binary, *args):
            if args[0] == "cms":
                Path(args[args.index("-signer") + 1]).write_bytes(
                    b"-----BEGIN CERTIFICATE-----\nfixture\n-----END CERTIFICATE-----")
                Path(args[args.index("-out") + 1]).write_bytes(content)
            return b"fixture certificate"

        with patch("tools.verify_installed_appx.signature_timestamp",
                   return_value=(b"signature", timestamp_token(content))), \
                patch("tools.verify_installed_appx.embedded_certificates"), \
                patch("tools.verify_installed_appx.command", side_effect=openssl), \
                patch("tools.verify_installed_appx.check_certificate_extensions",
                      return_value={"1.3.6.1.5.5.7.3.8"}):
            with self.assertRaisesRegex(ValueError, "imprint mismatch"):
                verify_timestamp("fixture-openssl", b"p7x", self.root)

    def test_wrong_tsa_root_fails_closed(self):
        def openssl(_binary, *args):
            if args[0] == "cms":
                self.assertIn("-CAfile", args)
                self.assertIn(self.root / "tsa-roots.pem", args)
                self.assertNotIn("-noverify", args)
                raise ValueError("TSA certificate verify error")
            return b""

        with patch("tools.verify_installed_appx.signature_timestamp",
                   return_value=(b"signature", timestamp_token(self.timestamp_fixture(b"\0" * 32)))), \
                patch("tools.verify_installed_appx.embedded_certificates"), \
                patch("tools.verify_installed_appx.command", side_effect=openssl):
            with self.assertRaisesRegex(ValueError, "TSA certificate verify"):
                verify_timestamp("fixture-openssl", b"p7x", self.root)

    def test_tsa_validity_is_checked_at_signed_time_without_disabling_chain(self):
        content = self.timestamp_fixture(hashlib.sha256(b"signature").digest())

        def openssl(_binary, *args):
            if args[0] == "cms":
                self.assertIn("-attime", args)
                self.assertIn(1792002659, args)
                self.assertNotIn("-noverify", args)
                self.assertNotIn("-no_check_time", args)
                Path(args[args.index("-signer") + 1]).write_bytes(
                    b"-----BEGIN CERTIFICATE-----\nfixture\n-----END CERTIFICATE-----")
                Path(args[args.index("-out") + 1]).write_bytes(content)
            return b"fixture certificate"

        with patch("tools.verify_installed_appx.signature_timestamp",
                   return_value=(b"signature", timestamp_token(content))), \
                patch("tools.verify_installed_appx.embedded_certificates"), \
                patch("tools.verify_installed_appx.command", side_effect=openssl), \
                patch("tools.verify_installed_appx.check_certificate_extensions",
                      return_value={"1.3.6.1.5.5.7.3.8"}):
            self.assertEqual(verify_timestamp("fixture-openssl", b"p7x", self.root), 1792002659)

    def test_gentime_is_not_accepted_without_signer_validity_check(self):
        # OpenSSL verifies the code-signing chain at authenticated genTime.
        roots = self.root / "root.der"
        roots.write_bytes(b"test root")
        (self.root / "AppxSignature.p7x").write_bytes(b"PKCXtest signature")
        digest = hashlib.sha256(b"test root").hexdigest()

        def openssl(_binary, *args):
            if args[0] == "smime":
                self.assertIn("-attime", args)
                self.assertIn(12345, args)
                self.assertNotIn("-noverify", args)
                raise ValueError("certificate not yet valid")
            return b"fixture certificate"

        with patch("tools.verify_installed_appx.json.loads",
                   return_value={"appx_trust_roots": [{"sha256": digest}]}), \
                patch("tools.verify_installed_appx.TSA_ROOT_SHA256", digest), \
                patch("tools.verify_installed_appx.verify_timestamp", return_value=12345), \
                patch("tools.verify_installed_appx.embedded_certificates"), \
                patch("tools.verify_installed_appx.command", side_effect=openssl):
            with self.assertRaisesRegex(ValueError, "not yet valid"):
                verify_signature(self.root, [roots], "fixture-openssl")

    def test_future_or_non_utc_timestamp_rejected(self):
        for text in (b"99991014183059Z", b"20261014183059+0100"):
            content = self.timestamp_fixture(b"\0" * 32).replace(b"20261014183059.504Z", text)
            # Re-encode the changed node to keep this about time, not DER length.
            fields = der_nodes(der_nodes(self.timestamp_fixture(b"\0" * 32))[0][1])
            fields[4] = (0x18, text)
            content = der(0x30, b"".join(encode_der(*node) for node in fields))
            with self.assertRaises(ValueError):
                timestamp_time(content)

    def test_unknown_critical_extension_cannot_be_ignored(self):
        extension = der(0x30, der(6, b"\x2a\x03") + der(1, b"\xff") + der(4, b""))
        cert = der(0x30, der(0x30, der(0xa3, der(0x30, extension))) + der(0x30, b"") + der(3, b""))
        with self.assertRaisesRegex(ValueError, "Unsupported critical"):
            check_certificate_extensions(cert)

    def test_microsoft_policy_must_equal_eku(self):
        eku = der(0x30, der(6, b"\x55\x1d\x25") + der(1, b"\xff") +
                  der(4, der(0x30, der(6, b"\x2a\x03"))))
        policy = der(0x30, der(6, bytes.fromhex("2b060104018237150a")) + der(1, b"\xff") +
                     der(4, der(0x30, der(0x30, der(6, b"\x2a\x04")))))
        cert = der(0x30, der(0x30, der(0xa3, der(0x30, eku + policy))) +
                   der(0x30, b"") + der(3, b""))
        with self.assertRaisesRegex(ValueError, "differ from EKU"):
            check_certificate_extensions(cert)

    def test_signed_digest_shape_and_der_bounds(self):
        blob = b"APPX" + b"".join(label + bytes([n]) * 32 for n, label in enumerate(
            (b"AXPC", b"AXCD", b"AXCT", b"AXBM", b"AXCI")))
        algorithm = der(0x30, bytes.fromhex("06096086480165030402010500"))
        data = der(0x30, b"") + der(0x30, algorithm + der(4, blob))
        self.assertEqual(signed_digests(data)["AXBM"], "03" * 32)
        with self.assertRaises(ValueError):
            signed_digests(data[:-1])
        for value in (b"\x30\x80", b"\x30\x81\x01\0", b"\x30\x02\0"):
            with self.assertRaises(ValueError):
                der_nodes(value)


if __name__ == "__main__":
    unittest.main()
