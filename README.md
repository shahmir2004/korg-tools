# Korg Tools# Korg Synthesizer Package Export Tool



A Python application for reading, playing, and exporting samples from Korg synthesizer packages (.SET files).A Python application with GUI for reading, analyzing, and playing back instruments/samples from Korg synthesizer packages (.SET files).



## Features## Features (Milestone 1 - Demo Version)



- **Parse Korg Pa-series SET packages** (folder-based format)- **Package Analysis**: Read and parse Korg .SET package structures

- **Extract audio samples** from proprietary PCM containers- **Sample Extraction**: Decode instruments and samples from packages

- **Play samples** with correct sample rate and format- **Demo Playback**: Play sounds directly without loading into the Korg synthesizer

- **Export samples** as standard WAV files- **GUI Interface**: Browse and preview sounds with a user-friendly interface

- **GUI interface** for browsing package contents

- **CLI interface** for batch operations## Supported Formats



## Supported Formats- `.SET` - Korg Set/Package files (Pa series, etc.)

- `.PCG` - Program/Combination/Global data

| Format | Extension | Description |- `.KSC` - Korg Script Collection

|--------|-----------|-------------|- `.KMP` - Korg Multisample Parameter

| SET Package | `.SET` folder | Pa-series folder-based package |- `.KSF` - Korg Sample File

| PCM Container | `.PCM` | Audio samples (KORF format) |

| Program Collection | `.PCG` | Programs/Sounds |## Installation

| Multisample Map | `.KMP` | Key zone mappings |

| Style | `.STY` | Rhythms/Accompaniments |```bash

# Create virtual environment (recommended)

## Requirementspython -m venv venv

venv\Scripts\activate  # Windows

- Python 3.10+# source venv/bin/activate  # Linux/Mac

- Windows/macOS/Linux

# Install dependencies

## Installationpip install -r requirements.txt

```

### 1. Clone the Repository

## Usage

```bash

git clone https://github.com/shahmir2004/korg-tools.git```bash

cd korg-tools# Run the GUI application

```python src/main.py



### 2. Create Virtual Environment# Or run CLI for quick testing

python src/cli.py path/to/package.SET

**Windows (PowerShell):**```

```powershell

python -m venv .venv## Project Structure

.venv\Scripts\Activate.ps1

``````

korg/

**Windows (Command Prompt):**├── src/

```cmd│   ├── main.py              # GUI application entry point

python -m venv .venv│   ├── cli.py               # Command-line interface

.venv\Scripts\activate.bat│   ├── parsers/

```│   │   ├── __init__.py

│   │   ├── set_parser.py    # .SET package parser

**macOS/Linux:**│   │   ├── pcg_parser.py    # .PCG file parser

```bash│   │   ├── kmp_parser.py    # .KMP multisample parser

python3 -m venv .venv│   │   └── ksf_parser.py    # .KSF sample parser

source .venv/bin/activate│   ├── audio/

```│   │   ├── __init__.py

│   │   └── player.py        # Audio playback engine

### 3. Install Dependencies│   ├── models/

│   │   ├── __init__.py

```bash│   │   └── korg_types.py    # Data models for Korg structures

pip install -r requirements.txt│   └── gui/

```│       ├── __init__.py

│       └── main_window.py   # Main GUI window

## Usage├── tests/

│   └── test_parsers.py

### GUI Application├── samples/                  # Place test .SET files here

├── requirements.txt

Launch the graphical interface:└── README.md

```

```bash

python src/main.py## Korg Package Structure Notes

```

### .SET File Structure

Then:The .SET file is typically a container format that can include:

1. Click **File → Open Folder** and select a `.SET` folder- Header with magic bytes and version info

2. Browse samples in the tree view on the left- File table/directory listing embedded files

3. Double-click a sample to play it- Embedded .PCG, .KMP, .KSF, and other files

4. Right-click to export as WAV- May use compression (often zlib or proprietary)



### Command Line Interface### .KSF (Korg Sample File)

- Contains raw audio sample data

```bash- Header includes sample rate, bit depth, loop points

# Parse and list package contents- Audio data is typically 16-bit PCM

python src/cli.py info path/to/Package.SET

### .KMP (Korg Multisample Parameter)

# Export all samples to WAV- Defines how samples are mapped across keyboard

python src/cli.py export path/to/Package.SET --output ./output- Contains velocity layers, key ranges, tuning info



# Play a specific sample## Dependencies

python src/cli.py play path/to/Package.SET --sample "Sample Name"

```- `pygame` - Audio playback

- `numpy` - Sample data processing

## Project Structure- `tkinter` - GUI (included with Python)

- `scipy` - Audio processing utilities (optional)

```

korg-tools/## Known Limitations

├── src/

│   ├── main.py              # GUI entry point- Package format varies between Korg models (Pa, Kronos, etc.)

│   ├── cli.py               # Command line interface- Some packages may use proprietary compression

│   ├── models/- Style (.STY) support planned for future milestones

│   │   └── korg_types.py    # Data models (SampleInfo, Program, etc.)

│   ├── parsers/## References

│   │   ├── set_parser.py    # Main SET package parser

│   │   ├── folder_set_parser.py  # Pa-series folder parser- Similar tools: Sofeh Music Studio, StyleWorks, KorgpaManager

│   │   ├── pcm_parser.py    # PCM audio container parser- Korg Pa series user manuals for file format hints

│   │   ├── pcg_parser.py    # Program collection parser

│   │   ├── kmp_parser.py    # Multisample map parser## License

│   │   └── ksf_parser.py    # Sample file parser

│   ├── audio/MIT License - See LICENSE file for details

│   │   └── player.py        # Audio playback engine
│   └── gui/
│       └── main_window.py   # Tkinter GUI
├── requirements.txt
├── .gitignore
└── README.md
```

## Technical Details

### PCM Format (Reverse Engineered)

The Korg Pa-series PCM format was reverse-engineered during development:

- **Signature:** `KORF` at offset 0x17
- **Sample names:** 24-byte entries (16-byte name + 8-byte params) starting at 0x24
- **Offset table:** Located in `KBEG`...`KEND` footer section (big-endian u32 values)
- **Per-sample header:** 76 bytes (0x4C) containing sample rate at bytes 20-21 (BE u16)
- **Audio format:** 16-bit signed PCM, mono, **big-endian** (swapped to LE for playback)
- **Sample rates:** 44100 Hz or 48000 Hz (read from per-sample header)

### Dependencies

| Package | Purpose |
|---------|---------|
| pygame | Audio playback |
| numpy | Audio data processing |
| scipy | Signal processing (resampling) |
| soundfile | Audio file I/O |
| construct | Binary parsing |

## Development

### Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

### Adding New Parsers

1. Create parser in `src/parsers/`
2. Add data models to `src/models/korg_types.py`
3. Register in `folder_set_parser.py` or `set_parser.py`

## Roadmap

- [ ] SF2/SoundFont2 export
- [ ] Style (STY) playback
- [ ] Waveform visualization
- [ ] Batch export with naming options
- [ ] Support for older Korg formats (Triton, M3, etc.)

## License

MIT License - See LICENSE file

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Acknowledgments

- Format reverse-engineering based on analysis of Pa-series SET packages
- Audio playback powered by pygame/SDL
