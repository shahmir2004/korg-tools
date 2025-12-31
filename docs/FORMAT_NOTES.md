# Korg File Format Notes

## Overview

This document contains notes on Korg synthesizer file formats discovered during the development of the Korg Package Export Tool.

## File Types

### .SET Files (Package/Set Files)

SET files are container formats used by Korg synthesizers to bundle multiple files together.

**Common Structures:**
1. **ZIP-based**: Some SET files are standard ZIP archives containing embedded files
2. **Native Korg format**: Uses "KORG", "SETi", or "SET1" header signatures
3. **Indexed format**: Contains a file table with offsets and sizes

**Header Patterns:**
```
0x00: 4 bytes - Signature ("KORG", "SETi", "SET1", or "PK\x03\x04" for ZIP)
0x04: 4 bytes - Version or file type
0x08: 4 bytes - File count or total size
0x0C: Variable - File table or data
```

### .KSF Files (Korg Sample Files)

KSF files contain raw audio sample data.

**Common KSF1 Structure:**
```
0x00: 4 bytes - "KSF1" signature
0x04: 4 bytes - File size or version
0x08: 4 bytes - Sample rate (e.g., 44100)
0x0C: 2 bytes - Bit depth (8, 16, 24)
0x0E: 2 bytes - Channels (1 = mono, 2 = stereo)
0x10: 4 bytes - Number of samples
0x14: 4 bytes - Loop start point
0x18: 4 bytes - Loop end point
0x1C: 1 byte  - Loop mode (0=none, 1=forward, 2=bidirectional)
0x1D: 1 byte  - Root key (MIDI note number)
0x1E: 2 bytes - Fine tune (cents, signed)
0x20+: Audio data (header size varies, commonly 64 or 128 bytes)
```

**Audio Data:**
- Usually 16-bit signed PCM, little-endian
- Some files use 8-bit unsigned or 24-bit formats
- May include RIFF/WAV format headers

### .KMP Files (Korg Multisample Parameters)

KMP files define how samples are mapped across the keyboard.

**Structure:**
```
0x00: 4 bytes - "KMP1" signature
0x04: 4 bytes - Version
0x08: 24 bytes - Multisample name (null-padded)
0x20: 2 bytes - Number of zones
0x22+: Zone definitions
```

**Zone Definition (typical 16-32 bytes each):**
```
+0x00: Low key (0-127)
+0x01: High key (0-127)
+0x02: Root key (0-127)
+0x03: Fine tune (signed byte, cents)
+0x04: Low velocity (0-127)
+0x05: High velocity (0-127)
+0x06: 2 bytes - Sample index
+0x08: Level (0-127)
+0x09: Pan (0-127, 64 = center)
```

### .PCG Files (Program/Combination/Global)

PCG files contain program definitions, effects, and global settings.

**Structure:**
- Uses chunk-based format similar to RIFF
- Contains PRG1 (program), CMB1 (combination), GLB1 (global) chunks
- Program data includes name (16-24 chars), category, bank, and multisample references

**Common Categories:**
| ID | Category |
|----|----------|
| 0  | Piano |
| 1  | E.Piano |
| 2  | Organ |
| 3  | Guitar |
| 4  | Bass |
| 5  | Strings |
| 6  | Brass |
| 7  | Woodwind |
| 8  | Synth Lead |
| 9  | Synth Pad |
| 10 | Synth FX |
| 11 | Ethnic |
| 12 | Percussion |
| 13 | Drums |
| 14 | SFX |
| 15 | User |

### .STY Files (Style/Rhythm)

Style files contain rhythm patterns and accompaniment data.

**Structure (planned for future investigation):**
- Contains MIDI pattern data
- Organized by elements: Intro, Variation, Fill, Ending
- Each element has multiple tracks (drums, bass, chord, etc.)

## Model Variations

File formats vary between Korg models:
- **Pa series** (Pa600, Pa1000, Pa4X, etc.): Uses SET/PCG/KMP/KSF
- **Kronos/Nautilus**: Similar but with extended capabilities
- **Older models** (Triton, M3): May use different versions

## Compression

Some packages use compression:
- ZIP compression (standard DEFLATE)
- zlib compression in native formats
- Some proprietary compression methods

## Known Limitations

1. Exact header layouts vary between model generations
2. Some files may use proprietary compression not yet decoded
3. Style (.STY) format needs more investigation
4. Some samples may have proprietary encoding

## Tools for Reference

- **Sofeh Music Studio**: Commercial tool for Korg files
- **StyleWorks**: Style editing software
- **KorgpaManager**: Pa series management tool
- **Hex editors**: For manual format investigation

## Contributing

If you discover additional format details, please document them here or create issues in the project repository.
