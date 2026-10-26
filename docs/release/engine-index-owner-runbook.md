# Engine index: owner signing runbook (REQ-124)

For the maintainer only. Agents must not run these steps, read the key
or see the passphrase. This follows
[ADR-0082](../ADR/0082-signed-engine-release-index.md). Nothing here
publishes anything. Uploading the envelope to a GitHub release is a
separate owner decision.

All commands run from the repository root, on the commit that holds the
reviewed tool (`fc996c3b` or later), in the owner's own terminal.

## 1. Encrypt the production key (once)

The key is still unencrypted, and `sign` refuses it until this step is
done.

```bash
python3 tools/engine_index.py encrypt-key \
  --key ~/.config/calimocho/engine-index/engine-index-ed25519-2026-10.pem
python3 tools/engine_index.py pubkey \
  --key ~/.config/calimocho/engine-index/engine-index-ed25519-2026-10.pem
```

The keyid that `pubkey` prints must be
`b2906316227f06803851b23824ed2ff3a93fd590c0c497752387713fff70dcee`, as
in `docs/contracts/calimocho-engine-index-trust.json`. Then confirm both
backup locations in ADR-0082, "Key custody".

## 2. Describe the release

Download the published zip and source tar of the release to a scratch
folder. For 0.1120.4.6:

```bash
python3 tools/engine_index.py entry \
  --zip ~/scratch/calimocho-11.20-4.0b3-06-macos.zip \
  --source ~/scratch/calimocho-11.20-4.0b3-06-source.tar \
  --tag engine-0.1120.4.6 --channel prerelease \
  --min-xode-version 0.2.0 \
  --notarization-id 515895cd-17e1-4d4f-bf02-d175e1843a09 \
  --out ~/scratch/entry-06.json
diff <(python3 -m json.tool ~/scratch/entry-06.json) \
     <(python3 -m json.tool tests/engine-index/entry-06.json)
```

The `diff` must be empty for 0.1120.4.6. That proves the published
assets match the reviewed test vector.

## 3. Build, sign and verify the index

```bash
python3 tools/engine_index.py payload --entry ~/scratch/entry-06.json \
  --epoch 1 --index-version 1 --out ~/scratch/payload.json
python3 tools/engine_index.py sign --payload ~/scratch/payload.json \
  --key ~/.config/calimocho/engine-index/engine-index-ed25519-2026-10.pem \
  --out ~/scratch/calimocho-engine-index.json
python3 tools/engine_index.py verify \
  --envelope ~/scratch/calimocho-engine-index.json --xode-version 0.2.0
python3 tools/engine_index.py check-asset \
  --envelope ~/scratch/calimocho-engine-index.json \
  --engine-id calimocho-11.20-4.0b3-06 \
  --zip ~/scratch/calimocho-11.20-4.0b3-06-macos.zip
```

`sign` asks for the passphrase. `verify` must list
`calimocho-11.20-4.0b3-06` as eligible, and `check-asset` must pass.
Increase `--index-version` by one for every new index you sign. Every
signed index expires after 30 days unless `--expires-days` says
otherwise.

## 4. Before publishing (owner decision)

- Publish only after the independent review has passed (done for
  `fc996c3b`).
- Never upload the key, the payload with private notes or anything from
  `~/.config`.
- Agents may check a signed envelope afterwards with `verify`, which
  needs only the public trust file.

Checked by the agent on 2026-10-26, without the key:
`python3 -m unittest discover -s tests/engine-index -p 'test_*.py'`
(13 tests pass).
