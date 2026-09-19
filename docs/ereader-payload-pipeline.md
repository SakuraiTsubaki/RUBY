# e-Reader payload extraction pipeline

This project uses Japanese Ruby/Sapphire material as the primary historical reference. English material is a fallback/cross-check where the corresponding Japanese dump is not available.

## Why this exists

Ruby/Sapphire external events do not need an e-Reader emulator inside the game ROM. What matters is the final event data the e-Reader sends to the game.

For the event families we can preserve the final in-game payload and invoke the original Ruby logic directly:

- Battle-e trainer: `struct BattleTowerEReaderTrainer`, 0xBC / 188 bytes.
- Berry e-Card: `struct EnigmaBerry`, 0x530 / 1328 bytes.
- Decoration Present O001: contains normal field scripts that add decoration IDs 118, 119, and 120.
- Eon Ticket: no embedded card runtime is needed in the final ROM; the original ticket + flag flow is preserved and the ticket is delivered internally.

## Decoder

`tools/ereader_payload_extract.py` is dependency-free and implements:

1. e-Reader RAW deinterleave into BIN card data.
2. standalone/link application extraction.
3. multi-strip application merging.
4. VPK0 decompression.
5. payload discovery using the same integrity rules as `pret/pokeruby`.

Examples:

```sh
python tools/ereader_payload_extract.py scan card.raw

python tools/ereader_payload_extract.py extract berry \
  "08-K007 RS - Ginema Berry (JPN).raw" \
  -o ginema.enigma.bin

python tools/ereader_payload_extract.py extract trainer \
  "08-N001 RS - Psychic Teruko (JPN).raw" \
  -o teruko.trainer.bin

python tools/ereader_payload_extract.py extract decoration \
  "08-O001 RS - Decoration Present (JPN) (Strip 1).raw" \
  "08-O001 RS - Decoration Present (JPN) (Strip 2).raw" \
  -o decoration-present.json
```

Every command reports SHA-256 hashes of its input and output so extracted payloads can be reproduced and compared without committing the source cards.

## Verified structure checks

### Japanese Berry

A Japanese K007 Ginema Berry card was decoded through this pipeline.

- RAW length: 0xB60 / 2912
- decoded application length: 3663 bytes
- exactly one valid `struct EnigmaBerry`
- discovered at 0x4EA
- payload size: 0x530

This agrees with pokeruby's `struct EnigmaBerry` layout and its additive checksum rule.

### Japanese Battle-e trainer

A Japanese N001 Psychic Teruko card was decoded.

- RAW length: 0xB60 / 2912
- decoded application length: 6580 bytes
- exactly one valid `struct BattleTowerEReaderTrainer`
- discovered at 0xC08
- payload size: 0xBC / 188

This agrees with pokeruby's `ValidateEReaderTrainer` checksum rule.

### Japanese Decoration Present O001

The two Japanese O001 strips were merged and decoded.

The decoded program contains all three normal Ruby script sequences:

- `bufferdecorationname 0, DECOR_REGIROCK_DOLL` + `adddecoration DECOR_REGIROCK_DOLL`
- `bufferdecorationname 0, DECOR_REGICE_DOLL` + `adddecoration DECOR_REGICE_DOLL`
- `bufferdecorationname 0, DECOR_REGISTEEL_DOLL` + `adddecoration DECOR_REGISTEEL_DOLL`

Therefore the permanent internal implementation must expose all three Regi dolls, not just the Registeel debug example found in pokeruby.

## Source policy

The repository does not vendor third-party or archival card dumps. The source manifest records where the historical material was examined. Users can run the extractor against their own legally obtained card dumps.

Format behavior was cross-checked against:

- `pret/pokeruby` for the target structures, command opcodes, and checksums.
- `irdkwia/pycarde` for independently documented e-Reader RAW/VPK handling.
- `Alectardy98/PokemonRS-Ereader-Saves` for archival R/S card organization and Japanese-first source examples.
