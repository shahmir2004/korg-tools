"""
Korg Sample Type Detector

Analyzes sample names and patterns to determine:
1. DRUMKIT - Percussion samples (one unique sound per key)
2. MELODIC - Note samples with pitch names (Do, Re, Mi, Fa, Sol, La, Si or C, D, E, F, G, A, B)

Detection is based on sample naming patterns in the PCM files.
"""

import os
import sys
import re
import struct
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple
from enum import Enum
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class SampleType(Enum):
    UNKNOWN = "unknown"
    DRUMKIT = "drumkit"     # Percussion - unique sounds
    MELODIC = "melodic"     # Note-based samples with pitch names
    ONESHOT = "oneshot"     # Single sound, no pitch info


@dataclass
class SampleEntry:
    """A single sample extracted from a PCM file."""
    name: str
    pcm_file: str
    index: int
    offset: int = 0
    size: int = 0
    sample_type: SampleType = SampleType.UNKNOWN
    detected_note: str = ""
    detected_octave: int = -1


# Patterns to detect note names (solfege and letter notation)
NOTE_PATTERNS = [
    # Solfege notation (Romanian/Italian style)
    (r'\b(Do|DO|do)[\s_-]?(\d+)?', 'C'),
    (r'\b(Re|RE|re)[\s_-]?(\d+)?', 'D'),
    (r'\b(Mi|MI|mi)[\s_-]?(\d+)?', 'E'),
    (r'\b(Fa|FA|fa)[\s_-]?(\d+)?', 'F'),
    (r'\b(Sol|SOL|sol)[\s_-]?(\d+)?', 'G'),
    (r'\b(La|LA|la)[\s_-]?(\d+)?', 'A'),
    (r'\b(Si|SI|si)[\s_-]?(\d+)?', 'B'),
    
    # Letter notation with number (like C4, F#3)
    (r'\b([A-G])#?(\d+)\b', None),  # Direct match
    
    # Flute/instrument + note pattern (like FLC4 = Flute C4)
    (r'\bFL([A-G])(\d+)\b', None),  # Flute pattern
    
    # Patterns with "Diez" (sharp) - Romanian
    (r'\bDiez[\s_-]?(\d+)?', 'sharp'),
]

# Patterns to detect drum/percussion sounds
DRUM_PATTERNS = [
    r'\b(KICK|kick|Kick)',
    r'\b(SNARE|snare|Snare)',
    r'\b(HI[\s-]?HAT|hihat|HH)',
    r'\b(TOM|tom|Tom)',
    r'\b(CRASH|crash|Crash)',
    r'\b(RIDE|ride|Ride)',
    r'\b(CYMBAL|cymbal|Cym)',
    r'\b(CLAP|clap|Clap)',
    r'\b(RIM|rim|Rim)',
    r'\b(FILL|fill|Fill)',
    r'\b(PERC|perc|Percussion)',
    r'\b(BD|bd)\b',  # Bass drum
    r'\b(SD|sd)\b',  # Snare drum
    r'\bBass[\s_-]?drum',
    r'\bDrum',
    r'\bCONGA|conga',
    r'\bBONGO|bongo',
    r'\bTIMBAL|timbal',
    r'\bTAMB|tamb',
    r'\bCLOPOTEI',  # Bells
    r'\bDAULA|daula|Daula',  # Ethnic drum
    r'\bTABLA|tabla',
    r'\bDARBUKA|darbuka',
    r'\bDOINA',  # Could be ethnic
]


def detect_sample_type(name: str) -> Tuple[SampleType, str, int]:
    """
    Detect the type of sample based on its name.
    
    Returns:
        (sample_type, detected_note, detected_octave)
    """
    # Check for drum patterns first
    for pattern in DRUM_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return SampleType.DRUMKIT, "", -1
    
    # Check for note patterns
    for pattern, note_map in NOTE_PATTERNS:
        match = re.search(pattern, name)
        if match:
            groups = match.groups()
            if note_map:
                note = note_map
                octave = int(groups[1]) if len(groups) > 1 and groups[1] else -1
            else:
                note = groups[0]
                octave = int(groups[1]) if len(groups) > 1 and groups[1] else -1
            
            return SampleType.MELODIC, note, octave
    
    # Check for patterns like "E51", "C151" (letter + numbers)
    match = re.match(r'^([A-G])(\d+)', name)
    if match:
        return SampleType.MELODIC, match.group(1), -1
    
    return SampleType.UNKNOWN, "", -1


def extract_samples_from_pcm(filepath: str) -> List[SampleEntry]:
    """Extract sample information from a PCM file."""
    samples = []
    
    with open(filepath, 'rb') as f:
        data = f.read()
    
    filename = os.path.basename(filepath)
    
    # Find KORF marker
    korf_pos = data.find(b'KORF')
    if korf_pos < 0:
        return samples
    
    # Find KBEG/KEND markers for offset table
    kbeg_pos = data.find(b'KBEG')
    kend_pos = data.find(b'KEND')
    
    # Parse sample offsets from footer
    offsets = []
    if kbeg_pos > 0 and kend_pos > kbeg_pos:
        pos = kbeg_pos + 4
        while pos + 4 <= kend_pos:
            val = struct.unpack('>I', data[pos:pos+4])[0]
            if 0x40 < val < kbeg_pos:
                offsets.append(val)
            pos += 4
    
    # Extract sample names from header region
    # Look for ASCII strings after KORF
    sample_names = []
    for match in re.finditer(rb'[A-Za-z][A-Za-z0-9 \-_\.]{2,14}', data[korf_pos:min(len(data), korf_pos + 0x200)]):
        name = match.group().decode('ascii', errors='ignore').strip()
        if name not in ['KORF', 'KBEG', 'KEND', 'RAM'] and len(name) >= 2:
            sample_names.append(name)
    
    # Create sample entries
    for idx, name in enumerate(sample_names):
        sample_type, note, octave = detect_sample_type(name)
        
        offset = offsets[idx] if idx < len(offsets) else 0
        next_offset = offsets[idx + 1] if idx + 1 < len(offsets) else kbeg_pos
        size = next_offset - offset if offset > 0 else 0
        
        samples.append(SampleEntry(
            name=name,
            pcm_file=filename,
            index=idx,
            offset=offset,
            size=size,
            sample_type=sample_type,
            detected_note=note,
            detected_octave=octave
        ))
    
    return samples


def analyze_all_pcm_files(pcm_dir: str) -> Dict[str, List[SampleEntry]]:
    """Analyze all PCM files and categorize samples."""
    all_samples = {}
    
    pcm_files = sorted(Path(pcm_dir).glob("RAM*.PCM"))
    
    for pcm_file in pcm_files:
        samples = extract_samples_from_pcm(str(pcm_file))
        if samples:
            all_samples[pcm_file.name] = samples
    
    return all_samples


def group_samples_by_instrument(samples: Dict[str, List[SampleEntry]]) -> Dict[str, List[SampleEntry]]:
    """
    Group samples by likely instrument based on naming patterns.
    
    For example:
    - "Do 1 banat", "Fa 2 banat", "La 3 banat" -> "banat" instrument
    - "FLC4", "FLD4", "FLE4" -> "FL" (Flute) instrument
    """
    instruments = defaultdict(list)
    
    for pcm_file, sample_list in samples.items():
        for sample in sample_list:
            # Try to extract instrument name
            name = sample.name
            
            # Pattern: "Note instrument" (e.g., "Do 1 banat")
            match = re.match(r'(?:Do|Re|Mi|Fa|Sol|La|Si|[A-G])[\s_-]?\d*\s+(.+)', name)
            if match:
                inst_name = match.group(1).strip()
                instruments[inst_name].append(sample)
                continue
            
            # Pattern: "FL[note][octave]" -> Flute
            match = re.match(r'FL([A-G])(\d+)', name)
            if match:
                instruments["Flute"].append(sample)
                continue
            
            # Pattern: instrument name in sample
            for inst in ["MG", "banat", "Blerim", "Braci", "SASHKO", "GABY", "PREMIER"]:
                if inst.lower() in name.lower():
                    instruments[inst].append(sample)
                    break
            else:
                # Use PCM file as grouping if no pattern found
                if sample.sample_type == SampleType.DRUMKIT:
                    instruments["Drums"].append(sample)
                else:
                    instruments[f"Unknown ({pcm_file})"].append(sample)
    
    return instruments


def print_analysis_report(samples: Dict[str, List[SampleEntry]]):
    """Print a detailed analysis report."""
    print("\n" + "=" * 70)
    print("KORG SAMPLE TYPE ANALYSIS REPORT")
    print("=" * 70)
    
    # Statistics
    total_samples = sum(len(s) for s in samples.values())
    drumkit_samples = sum(1 for sl in samples.values() for s in sl if s.sample_type == SampleType.DRUMKIT)
    melodic_samples = sum(1 for sl in samples.values() for s in sl if s.sample_type == SampleType.MELODIC)
    unknown_samples = sum(1 for sl in samples.values() for s in sl if s.sample_type == SampleType.UNKNOWN)
    
    print(f"\nTotal samples across {len(samples)} PCM files: {total_samples}")
    print(f"  - DRUMKIT (percussion):    {drumkit_samples:4d} ({100*drumkit_samples/total_samples:.1f}%)")
    print(f"  - MELODIC (pitch samples): {melodic_samples:4d} ({100*melodic_samples/total_samples:.1f}%)")
    print(f"  - UNKNOWN:                 {unknown_samples:4d} ({100*unknown_samples/total_samples:.1f}%)")
    
    # Group by type
    print("\n" + "-" * 70)
    print("DRUMKIT SAMPLES (one unique sound per key, no pitch shifting)")
    print("-" * 70)
    
    for pcm_file, sample_list in sorted(samples.items()):
        drum_samples = [s for s in sample_list if s.sample_type == SampleType.DRUMKIT]
        if drum_samples:
            print(f"\n{pcm_file}:")
            for s in drum_samples:
                print(f"  [{s.index:2d}] {s.name}")
    
    print("\n" + "-" * 70)
    print("MELODIC SAMPLES (notes with pitch - can be transposed)")
    print("-" * 70)
    
    # Group melodic by detected instrument
    instruments = group_samples_by_instrument(samples)
    
    for inst_name, inst_samples in sorted(instruments.items()):
        melodic = [s for s in inst_samples if s.sample_type == SampleType.MELODIC]
        if melodic:
            print(f"\n{inst_name} ({len(melodic)} samples):")
            for s in sorted(melodic, key=lambda x: (x.detected_note, x.detected_octave)):
                note_info = f"{s.detected_note}{s.detected_octave}" if s.detected_octave >= 0 else s.detected_note
                print(f"  [{s.pcm_file}:{s.index:2d}] {s.name:<20} -> Note: {note_info}")
    
    # Show per-PCM summary
    print("\n" + "-" * 70)
    print("PER-PCM FILE SUMMARY")
    print("-" * 70)
    print(f"{'PCM File':<15} {'Total':>6} {'Drum':>6} {'Melodic':>8} {'Unknown':>8} | Likely Type")
    print("-" * 70)
    
    for pcm_file, sample_list in sorted(samples.items()):
        total = len(sample_list)
        drum = sum(1 for s in sample_list if s.sample_type == SampleType.DRUMKIT)
        melodic = sum(1 for s in sample_list if s.sample_type == SampleType.MELODIC)
        unknown = sum(1 for s in sample_list if s.sample_type == SampleType.UNKNOWN)
        
        if drum > melodic:
            likely = "DRUMKIT"
        elif melodic > drum:
            likely = "MELODIC"
        else:
            likely = "MIXED"
        
        print(f"{pcm_file:<15} {total:>6} {drum:>6} {melodic:>8} {unknown:>8} | {likely}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Detect sample types in Korg PCM files")
    parser.add_argument("set_dir", nargs="?",
                       default=r"c:\work\korg\samples\Stefanv22021.SET",
                       help="Path to .SET directory")
    
    args = parser.parse_args()
    set_dir = Path(args.set_dir)
    pcm_dir = set_dir / "PCM"
    
    if not pcm_dir.exists():
        print(f"ERROR: PCM directory not found: {pcm_dir}")
        return 1
    
    print(f"Analyzing PCM files in: {pcm_dir}")
    
    # Analyze all PCM files
    samples = analyze_all_pcm_files(str(pcm_dir))
    
    # Print report
    print_analysis_report(samples)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
