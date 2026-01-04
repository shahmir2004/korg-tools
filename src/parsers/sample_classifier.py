"""
Korg Sample Classifier

Automatically classifies samples into types:
- DRUMKIT: Percussion/one-shot sounds (each key = different sound)
- MELODIC: Note-based samples (pitch interpolation fills keyboard)
- ONESHOT: Single sound effects

Detection is based on:
1. Sample naming patterns
2. Instrument naming conventions (Romanian solfege, letter notation)
3. Context from surrounding samples in the same PCM file
"""

import re
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.korg_types import SampleInfo, SampleType


# ============================================================================
# PATTERN DEFINITIONS
# ============================================================================

# Drum/Percussion patterns - if any match, it's a drumkit sample
DRUM_PATTERNS = [
    # Standard drum names
    r'\b(KICK|kick|Kick)\d*\b',
    r'\b(SNARE|snare|Snare)\d*\b',
    r'\bHI[\s\-]?HAT\b',
    r'\b(HH|hh)(CL|OP|PD)?\b',  # HH, HHCL (closed), HHOP (open)
    r'\b(TOM|tom|Tom)[\s_\-]?\d*\b',
    r'\b(CRASH|crash|Crash)\b',
    r'\b(RIDE|ride|Ride)\b',
    r'\b(CYMBAL|cymbal|CYM|cym)\b',
    r'\b(CLAP|clap|Clap)S?\b',  # CLAP or CLAPS
    r'\b(RIM|rim|Rim)\b',
    r'\b(FILL|fill|Fill)[\s_\-]?\d*\b',
    r'\b(PERC|perc|Percussion)\b',
    
    # Bass drum abbreviations
    r'\bBD[\s_]?\w*\b',  # BD, BD SASHKO, etc.
    r'\bBass[\s_\-]?[Dd]rum\b',
    r'\bBassdrum\b',
    
    # Ethnic percussion
    r'\b(CONGA|conga|Conga)\b',
    r'\b(BONGO|bongo|Bongo)\b',
    r'\b(TIMBAL|timbal|Timbal)\b',
    r'\b(TAMB|tamb|Tambourine)\b',
    r'\b(TABLA|tabla)\b',
    r'\b(DARBUKA|darbuka|Darbuka)\b',
    r'\b[HD]?(DAULA|daula|Daula)\b',  # DAULA, HDaula
    r'\b(DOIRA|doira)\b',
    r'\b(DJEMBE|djembe)\b',
    
    # Bells/metallic
    r'\b(CLOPOTEI|clopotei)\b',  # Romanian: bells
    r'\b(BELL|bell|Bell)s?\b',
    r'\b(TRIANGLE|triangle)\b',
    r'\b(COWBELL|cowbell)\b',
    r'\b(CHIMES|chimes)\b',
    r'\b(GONG|gong)\b',
    
    # Misc percussion
    r'\bSD\d*\b',  # Snare drum with number
    r'\b(SHAKER|shaker)\b',
    r'\b(CASTANET|castanet)\b',
    r'\b(GUIRO|guiro)\b',
    r'\b(MARACAS|maracas)\b',
    r'\b(CABASA|cabasa)\b',
    r'\b(WOODBLOCK|woodblock)\b',
    r'\b(CLAVES|claves)\b',
    r'\b(AGOGO|agogo)\b',
    r'\b(CUICA|cuica)\b',
    r'\b(VIBRASLAP|vibraslap)\b',
    r'\b(WHISTLE|whistle)\b',
    
    # Effects/Hits
    r'\b(HIT|hit|Hit)\d*\b',
    r'\b(FX|fx|Fx)\d*\b',
    r'\b(SFX|sfx)\b',
    
    # Specific patterns from your samples
    r'\bARAB\b',  # CLAPS ARAB
    r'\bGABY\d*\b',  # BD GABY222
    r'\bSASHKO\b',  # BD SASHKO
    r'\bPREMIER\b',  # Drum kit brand
]

# Melodic patterns - note names in various formats
MELODIC_PATTERNS = [
    # Romanian/Italian solfege with optional number
    (r'\b(Do|DO|do)[\s_\-]?(\d+)?(?:\s|$|[_\-])', 'C'),
    (r'\b(Re|RE|re)[\s_\-]?(\d+)?(?:\s|$|[_\-])', 'D'),
    (r'\b(Mi|MI|mi)[\s_\-]?(\d+)?(?:\s|$|[_\-])', 'E'),
    (r'\b(Fa|FA|fa)[\s_\-]?(\d+)?(?:\s|$|[_\-])', 'F'),
    (r'\b(Sol|SOL|sol)[\s_\-]?(\d+)?(?:\s|$|[_\-])', 'G'),
    (r'\b(La|LA|la)[\s_\-]?(\d+)?(?:\s|$|[_\-])', 'A'),
    (r'\b(Si|SI|si)[\s_\-]?(\d+)?(?:\s|$|[_\-])', 'B'),
    
    # Letter notation with octave (C4, F#3, etc.)
    (r'\b([A-G])#?(\d)\b', None),
    
    # Flute patterns (FLC4 = Flute C4)
    (r'\bFL([A-G])(\d)\b', None),
    
    # Romanian sharps/flats
    (r'\b(Do|Re|Mi|Fa|Sol|La|Si)[Dd]iez[\s_\-]?(\d+)?', 'sharp'),
    (r'\b(Mib|mib|MIB)[\s_\-]?(\d+)?', 'Eb'),
    (r'\b(Lab|lab|LAB)[\s_\-]?(\d+)?', 'Ab'),
    (r'\b(Sib|sib|SIB)[\s_\-]?(\d+)?', 'Bb'),
    
    # Sample names with note suffix (e.g., "Piano_C4")
    (r'[_\-]([A-G]#?)(\d)\b', None),
    
    # Standalone note at start (E51 = E, octave marker)  
    (r'^([A-G])(\d+)\b', None),
]

# Instrument name patterns that indicate melodic content
MELODIC_INSTRUMENT_PATTERNS = [
    r'\b(Piano|PIANO|piano)\b',
    r'\b(Strings?|STRING|string)\b',
    r'\b(Violin|VIOLIN|violin|Vioara|vioara)\b',
    r'\b(Viola|VIOLA|viola)\b',
    r'\b(Cello|CELLO|cello)\b',
    r'\b(Bass|BASS|bass)\b',  # Note: can also be "Bass drum"
    r'\b(Guitar|GUITAR|guitar)\b',
    r'\b(Organ|ORGAN|organ)\b',
    r'\b(Synth|SYNTH|synth)\b',
    r'\b(Pad|PAD|pad)\b',
    r'\b(Lead|LEAD|lead)\b',
    r'\b(Brass|BRASS|brass)\b',
    r'\b(Trumpet|TRUMPET|trumpet|Trompeta)\b',
    r'\b(Sax|SAX|sax|Saxo)\b',
    r'\b(Flute|FLUTE|flute|Fleita|Fluier)\b',
    r'\b(Clarinet|CLARINET|clarinet)\b',
    r'\b(Oboe|OBOE|oboe)\b',
    r'\b(Accordion|ACCORDION|accordion|Acordeon)\b',
    r'\b(Harmonica|HARMONICA|harmonica)\b',
    r'\b(Harp|HARP|harp)\b',
    r'\b(Marimba|MARIMBA|marimba)\b',
    r'\b(Vibraphone|VIBRAPHONE|vibraphone)\b',
    r'\b(Xylophone|XYLOPHONE|xylophone)\b',
    r'\b(Voice|VOICE|voice|Choir|CHOIR|choir)\b',
    r'\b(Ocarina|OCARINA|ocarina)\b',
    r'\b(Nai|NAI|nai)\b',  # Romanian pan flute
    r'\b(Bandon|bandon)\b',  # Bandoneon
    r'\b(Zeta|ZETA|zeta)\b',  # Synth type
    
    # Regional instrument names
    r'\b(banat|Banat|BANAT)\b',  # Romanian region style
    r'\b(Blerim|BLERIM)\b',  # Possibly Albanian
    r'\b(Braci|BRACI)\b',  # Regional
    r'\b(Returnela|RETURNELA)\b',  # Melodic pattern
]


# ============================================================================
# CLASSIFICATION FUNCTIONS
# ============================================================================

def classify_sample(name: str, context_samples: List[str] = None) -> Tuple[SampleType, str, int]:
    """
    Classify a sample based on its name.
    
    Args:
        name: Sample name
        context_samples: Other sample names in the same PCM file (for context)
        
    Returns:
        (sample_type, detected_note, detected_octave)
    """
    # First check for drum patterns (highest priority)
    if _is_drum_sample(name):
        return SampleType.DRUMKIT, "", -1
    
    # Check for melodic patterns
    note, octave = _detect_note(name)
    if note:
        return SampleType.MELODIC, note, octave
    
    # Check for melodic instrument names
    if _has_melodic_instrument(name):
        return SampleType.MELODIC, "", -1
    
    # Use context if available
    if context_samples:
        context_type = _infer_from_context(name, context_samples)
        if context_type != SampleType.UNKNOWN:
            return context_type, "", -1
    
    return SampleType.UNKNOWN, "", -1


def _is_drum_sample(name: str) -> bool:
    """Check if name matches any drum pattern."""
    for pattern in DRUM_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return True
    return False


def _detect_note(name: str) -> Tuple[str, int]:
    """
    Detect musical note from name.
    
    Returns:
        (note_name, octave) or ("", -1) if not found
    """
    for pattern, note_override in MELODIC_PATTERNS:
        match = re.search(pattern, name)
        if match:
            groups = match.groups()
            
            if note_override == 'sharp':
                # Handle Romanian sharp notation (e.g., "FaDiez")
                base_note = groups[0] if groups else ""
                note_map = {'Do': 'C#', 'Re': 'D#', 'Mi': 'F', 'Fa': 'F#', 
                           'Sol': 'G#', 'La': 'A#', 'Si': 'C'}
                note = note_map.get(base_note, "")
                octave = int(groups[1]) if len(groups) > 1 and groups[1] else -1
                return note, octave
            elif note_override:
                note = note_override
                octave = int(groups[1]) if len(groups) > 1 and groups[1] and groups[1].isdigit() else -1
                return note, octave
            else:
                # Direct match (letter + number)
                note = groups[0] if groups else ""
                octave = int(groups[1]) if len(groups) > 1 and groups[1] and groups[1].isdigit() else -1
                return note, octave
    
    return "", -1


def _has_melodic_instrument(name: str) -> bool:
    """Check if name contains a melodic instrument name."""
    for pattern in MELODIC_INSTRUMENT_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            # Make sure it's not "Bass drum"
            if 'bass' in name.lower() and 'drum' in name.lower():
                return False
            return True
    return False


def _infer_from_context(name: str, context_samples: List[str]) -> SampleType:
    """
    Infer sample type from surrounding samples.
    
    If most samples in the same PCM file are melodic, this one probably is too.
    """
    drum_count = 0
    melodic_count = 0
    
    for ctx_name in context_samples:
        if ctx_name == name:
            continue
        if _is_drum_sample(ctx_name):
            drum_count += 1
        elif _detect_note(ctx_name)[0] or _has_melodic_instrument(ctx_name):
            melodic_count += 1
    
    if melodic_count > drum_count:
        return SampleType.MELODIC
    elif drum_count > melodic_count:
        return SampleType.DRUMKIT
    
    return SampleType.UNKNOWN


def classify_sample_info(sample: SampleInfo, context_samples: List[str] = None) -> SampleInfo:
    """
    Classify a SampleInfo object and update its type fields.
    
    Args:
        sample: SampleInfo to classify
        context_samples: Other sample names for context
        
    Returns:
        The same SampleInfo with updated type fields
    """
    sample_type, note, octave = classify_sample(sample.name, context_samples)
    
    sample.sample_type = sample_type
    sample.detected_note = note
    sample.detected_octave = octave
    
    return sample


def classify_all_samples(samples: List[SampleInfo]) -> List[SampleInfo]:
    """
    Classify all samples in a list, using context from other samples.
    
    Args:
        samples: List of SampleInfo objects
        
    Returns:
        Same list with updated type information
    """
    # Group by PCM file for context
    by_pcm: Dict[str, List[SampleInfo]] = {}
    for sample in samples:
        pcm = sample.pcm_file or "unknown"
        if pcm not in by_pcm:
            by_pcm[pcm] = []
        by_pcm[pcm].append(sample)
    
    # Classify each sample with context from same PCM file
    for pcm, pcm_samples in by_pcm.items():
        context_names = [s.name for s in pcm_samples]
        for sample in pcm_samples:
            classify_sample_info(sample, context_names)
    
    return samples


def get_sample_type_summary(samples: List[SampleInfo]) -> Dict[str, int]:
    """
    Get a summary of sample types.
    
    Returns:
        Dict with counts for each type
    """
    summary = {
        'total': len(samples),
        'drumkit': 0,
        'melodic': 0,
        'oneshot': 0,
        'unknown': 0
    }
    
    for sample in samples:
        if sample.sample_type == SampleType.DRUMKIT:
            summary['drumkit'] += 1
        elif sample.sample_type == SampleType.MELODIC:
            summary['melodic'] += 1
        elif sample.sample_type == SampleType.ONESHOT:
            summary['oneshot'] += 1
        else:
            summary['unknown'] += 1
    
    return summary


def group_melodic_by_instrument(samples: List[SampleInfo]) -> Dict[str, List[SampleInfo]]:
    """
    Group melodic samples by their likely instrument.
    
    Returns:
        Dict mapping instrument name to list of samples
    """
    instruments: Dict[str, List[SampleInfo]] = {}
    
    for sample in samples:
        if sample.sample_type != SampleType.MELODIC:
            continue
        
        # Try to extract instrument name
        inst_name = _extract_instrument_name(sample.name)
        
        if inst_name not in instruments:
            instruments[inst_name] = []
        instruments[inst_name].append(sample)
    
    return instruments


def _extract_instrument_name(name: str) -> str:
    """Extract the instrument name from a sample name."""
    # Pattern: "Note Instrument" (e.g., "Do 1 banat")
    match = re.match(r'(?:Do|Re|Mi|Fa|Sol|La|Si|[A-G]#?)[\s_\-]?\d*\s+(.+)', name, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Pattern: instrument at start, note at end
    match = re.match(r'([A-Za-z]+)[\s_\-]?[A-G]#?\d', name)
    if match:
        prefix = match.group(1)
        if prefix.upper() not in ['FL', 'FLA', 'FLB', 'FLC', 'FLD', 'FLE', 'FLF', 'FLG']:
            return prefix
        return "Flute"
    
    # Check for known instrument patterns
    for pattern in MELODIC_INSTRUMENT_PATTERNS:
        match = re.search(pattern, name)
        if match:
            return match.group(1)
    
    return "Unknown"


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def note_to_midi(note: str, octave: int) -> int:
    """
    Convert note name and octave to MIDI note number.
    
    Args:
        note: Note name (C, C#, D, etc.)
        octave: Octave number (4 = middle C octave)
        
    Returns:
        MIDI note number (60 = middle C)
    """
    note_map = {
        'C': 0, 'C#': 1, 'Db': 1,
        'D': 2, 'D#': 3, 'Eb': 3,
        'E': 4, 'Fb': 4,
        'F': 5, 'E#': 5, 'F#': 6, 'Gb': 6,
        'G': 7, 'G#': 8, 'Ab': 8,
        'A': 9, 'A#': 10, 'Bb': 10,
        'B': 11, 'Cb': 11
    }
    
    if note not in note_map:
        return 60  # Default to middle C
    
    if octave < 0:
        octave = 4  # Default octave
    
    return 12 * (octave + 1) + note_map[note]


def midi_to_note(midi_note: int) -> Tuple[str, int]:
    """
    Convert MIDI note number to note name and octave.
    
    Args:
        midi_note: MIDI note number (0-127)
        
    Returns:
        (note_name, octave)
    """
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (midi_note // 12) - 1
    note = notes[midi_note % 12]
    return note, octave


# ============================================================================
# TEST / CLI
# ============================================================================

if __name__ == "__main__":
    # Test samples
    test_names = [
        "KICK1",
        "Bassdrum Gby",
        "CRASH 2",
        "TOM 3",
        "CLAPS ARAB",
        "FILL 1",
        "CLOPOTEI",
        "Do 1 banat",
        "Fa 2 banat",
        "La1 banat",
        "RE3",
        "MI4",
        "SOL2",
        "FLC4",
        "FLA3",
        "E51",
        "C151",
        "Sax Real",
        "Real Zeta-AD",
        "Acordeon Juzi",
        "Returnela 8 GM",
        "Blerim 15 MG",
        "Unknown Sample",
    ]
    
    print("Sample Classification Test")
    print("=" * 60)
    print(f"{'Sample Name':<25} {'Type':<12} {'Note':<5} {'Oct':<5}")
    print("-" * 60)
    
    for name in test_names:
        sample_type, note, octave = classify_sample(name)
        oct_str = str(octave) if octave >= 0 else "-"
        print(f"{name:<25} {sample_type.value:<12} {note:<5} {oct_str:<5}")
