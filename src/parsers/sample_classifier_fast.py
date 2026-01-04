"""
Fast Sample Classifier - Optimized for large sample sets.

Uses pre-compiled patterns and simpler heuristics for speed.
"""

import re
from typing import List, Dict, Tuple, Set
from models.korg_types import SampleInfo, SampleType


# Pre-compile all patterns once at module load
_DRUM_KEYWORDS = frozenset([
    'kick', 'snare', 'hihat', 'hi-hat', 'tom', 'crash', 'ride', 'cymbal',
    'clap', 'rim', 'fill', 'perc', 'conga', 'bongo', 'timbal', 'tamb',
    'tabla', 'darbuka', 'daula', 'doira', 'djembe', 'bell', 'triangle',
    'cowbell', 'chimes', 'gong', 'shaker', 'castanet', 'guiro', 'maracas',
    'cabasa', 'woodblock', 'claves', 'agogo', 'cuica', 'vibraslap', 'whistle',
    'hit', 'sfx', 'bd', 'sd', 'hh', 'tok', 'drbk', 'drum'
])

_DRUM_PATTERN = re.compile(
    r'\b(kick|snare|tom|crash|ride|cymbal|clap|rim|fill|perc|'
    r'conga|bongo|timbal|tamb|tabla|darbuka|daula|djembe|'
    r'bell|shaker|bd|sd|hh|drbk|drum)\b',
    re.IGNORECASE
)

# Note patterns for melodic detection
_NOTE_PATTERN = re.compile(
    r'\b(Do|Re|Mi|Fa|Sol|La|Si|[A-G]#?)\s*(\d)?\b',
    re.IGNORECASE
)

_MELODIC_KEYWORDS = frozenset([
    'piano', 'string', 'violin', 'viola', 'cello', 'bass', 'guitar',
    'organ', 'synth', 'pad', 'lead', 'brass', 'trumpet', 'sax',
    'flute', 'clarinet', 'oboe', 'accordion', 'harmonica', 'harp',
    'marimba', 'vibraphone', 'xylophone', 'voice', 'choir', 'nai',
    'banat', 'blerim', 'braci', 'returnela', 'musette', 'kaval', 'fluier'
])


def classify_sample_fast(name: str) -> Tuple[SampleType, str, int]:
    """Fast sample classification using keyword matching."""
    name_lower = name.lower()
    
    # Quick drum check via keywords
    for word in name_lower.split():
        word_clean = ''.join(c for c in word if c.isalnum())
        if word_clean in _DRUM_KEYWORDS:
            return SampleType.DRUMKIT, "", -1
    
    # Pattern-based drum check
    if _DRUM_PATTERN.search(name):
        return SampleType.DRUMKIT, "", -1
    
    # Note detection for melodic
    note_match = _NOTE_PATTERN.search(name)
    if note_match:
        note = note_match.group(1)
        octave = int(note_match.group(2)) if note_match.group(2) else -1
        # Convert solfege to letter
        solfege_map = {'do': 'C', 're': 'D', 'mi': 'E', 'fa': 'F', 
                       'sol': 'G', 'la': 'A', 'si': 'B'}
        note_letter = solfege_map.get(note.lower(), note.upper())
        return SampleType.MELODIC, note_letter, octave
    
    # Melodic keyword check
    for word in name_lower.split():
        word_clean = ''.join(c for c in word if c.isalnum())
        if word_clean in _MELODIC_KEYWORDS:
            return SampleType.MELODIC, "", -1
    
    return SampleType.UNKNOWN, "", -1


def classify_all_samples_fast(samples: List[SampleInfo]) -> List[SampleInfo]:
    """Classify all samples using fast method."""
    for sample in samples:
        sample_type, note, octave = classify_sample_fast(sample.name)
        sample.sample_type = sample_type
        sample.detected_note = note
        sample.detected_octave = octave
    return samples


def group_samples_fast(samples: List[SampleInfo]) -> Dict[str, 'SampleGroup']:
    """
    Fast sample grouping by extracting common prefixes/patterns.
    Groups samples by their PCM source file as a simple heuristic.
    """
    from dataclasses import dataclass
    
    @dataclass
    class SampleGroup:
        name: str
        samples: List[SampleInfo]
        is_drumkit: bool = False
    
    groups: Dict[str, SampleGroup] = {}
    
    for sample in samples:
        # Use PCM file as initial grouping
        pcm_name = getattr(sample, 'pcm_file', None) or 'Unknown'
        group_key = pcm_name.replace('.PCM', '')
        
        if group_key not in groups:
            groups[group_key] = SampleGroup(name=group_key, samples=[], is_drumkit=False)
        
        groups[group_key].samples.append(sample)
        
        # Mark as drumkit if any sample is drumkit
        if sample.sample_type == SampleType.DRUMKIT:
            groups[group_key].is_drumkit = True
    
    return groups
