# Korg Tools - Feature Roadmap

## Priority 1 - Core Improvements

- [ ] 🎹 **Better Keyboard Playback** - Play melodic samples across the keyboard with proper pitch shifting (currently plays at original pitch only)

- [x] 🔗 **Program-to-Sample Linking** - Parse PCG files to show which programs actually use which samples ✅ Implemented in `program_linker.py`

- [ ] 📊 **Better Classification** - Improve unknown sample detection (currently 2799 out of 4229 are unknown)

## Priority 2 - Export & Filtering

- [ ] 📁 **Batch WAV Export** - Export all samples to organized folders (by PCM file, by type, or by instrument)

- [ ] 🔍 **Filter/Search by Type** - Quick filters to show only drumkits, melodics, or unknowns in the tree

- [ ] 💾 **Export to SFZ format** - Popular open format for samplers

## Priority 3 - UI/UX Enhancements

- [ ] 🎵 **Loop Point Display** - Show loop markers in waveform view

- [ ] 🌙 **Dark Mode Theme** - Easier on the eyes

- [ ] 📜 **Recent Files List** - Quick access to previously opened packages

## Priority 4 - Advanced Parsing

- [ ] 🎼 **Style (STY) Parsing** - Extract rhythm/accompaniment patterns

- [ ] 🔄 **KMP Multisample Mapping** - Parse key zones and velocity layers

## Priority 5 - Advanced Features

- [ ] 🎹 **MIDI Input** - Trigger samples from external MIDI keyboard

- [ ] ✂️ **Sample Editing** - Trim, normalize, fade in/out

- [ ] 📋 **Compare Packages** - Diff two SET files to see differences

- [ ] 🔄 **Drag & Drop Import** - Drop SET folders onto window to load

---

## Completed ✅

- [x] Parse Korg Pa-series SET packages (folder-based format)
- [x] Extract audio samples from PCM containers
- [x] Support both Pa3X/Pa800 and Pa1000/Pa4X formats
- [x] Fast sample classification (keyword-based)
- [x] Program-to-Sample linking via name/pattern matching (35% coverage)
- [x] Play samples with correct sample rate
- [x] Export to SF2 (SoundFont) format
- [x] GUI with hierarchical tree view
- [x] Optimized loading for large packages (4000+ samples in ~1.3s)
