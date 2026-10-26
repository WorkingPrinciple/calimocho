// Verifies the engine index test vector with CryptoKit, the way X Ode does (ADR-0082).
// Usage: swift tests/engine-index/verify_vector.swift tests/engine-index
import CryptoKit
import Foundation

func fail(_ message: String) -> Never {
    print("FAIL \(message)")
    exit(1)
}

let directory = URL(fileURLWithPath: CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : ".")

func json(_ name: String) -> [String: Any] {
    guard let data = try? Data(contentsOf: directory.appendingPathComponent(name)),
          let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { fail("read \(name)") }
    return object
}

func hex(_ text: String) -> Data {
    var data = Data()
    var index = text.startIndex
    while index < text.endIndex {
        let next = text.index(index, offsetBy: 2)
        data.append(UInt8(text[index..<next], radix: 16)!)
        index = next
    }
    return data
}

// PAE per DSSE v1: "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
func pae(_ type: String, _ body: Data) -> Data {
    let kind = Data(type.utf8)
    var message = Data("DSSEv1 \(kind.count) ".utf8)
    message.append(kind)
    message.append(Data(" \(body.count) ".utf8))
    message.append(body)
    return message
}

let vector = json("vector.json")
let testKey = vector["test_key"] as! [String: String]
let publicKey = try! Curve25519.Signing.PublicKey(rawRepresentation: hex(testKey["public_key_hex"]!))
let keyid = SHA256.hash(data: publicKey.rawRepresentation).map { String(format: "%02x", $0) }.joined()
guard keyid == testKey["keyid"] else { fail("keyid") }

func verify(_ name: String) -> Bool {
    let envelope = json(name)
    guard envelope["payloadType"] as? String == "application/vnd.calimocho.engine-index+json; version=1",
          let payload = Data(base64Encoded: envelope["payload"] as! String) else { return false }
    let message = pae(envelope["payloadType"] as! String, payload)
    for signature in envelope["signatures"] as! [[String: String]] where signature["keyid"] == keyid {
        if let sig = Data(base64Encoded: signature["sig"]!), publicKey.isValidSignature(sig, for: message) {
            return true
        }
    }
    return false
}

let payload = try! Data(contentsOf: directory.appendingPathComponent("payload.json"))
let message = pae(vector["payload_type"] as! String, payload)
let digest = SHA256.hash(data: message).map { String(format: "%02x", $0) }.joined()
guard digest == vector["pae_sha256"] as! String else { fail("pae_sha256") }
guard publicKey.isValidSignature(hex(vector["signature_hex"] as! String), for: message) else { fail("signature_hex") }
guard verify("envelope.json") else { fail("envelope.json should verify") }
for name in ["envelope-tampered-payload.json", "envelope-wrong-type.json", "envelope-untrusted-key.json"] {
    guard !verify(name) else { fail("\(name) must not verify") }
}
print("CryptoKit ok")
