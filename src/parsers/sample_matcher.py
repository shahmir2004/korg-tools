"""
Sample-to-Program Matcher

Matches individual PCM samples to their parent programs/drumkits.
Uses both pattern matching and heuristics since the exact mapping
requires parsing the full Korg keymap format.
"""

import os
import re
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from dataclasses import dataclass

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.korg_types import SampleInfo, SampleType
from parsers.program_parser import ProgramDef, get_all_programs


@dataclass
class SampleGroup:
    """A group of related samples belonging to a program/drumkit."""
    name: str  # Program/drumkit name
    samples: List[SampleInfo]
    is_drumkit: bool = False
    source_pcg: str = ""


# Known sample name patterns that indicate program membership
# These are based on common Korg naming conventions
SAMPLE_PATTERNS = {
    # Drumkit samples
    'Etno-fill 1': [
        r'FILL 1\(\d+[LR]\)',  # FILL 1(00L), FILL 1(09R), etc.
        r'ETNO Dany\(\d+[LR]\)',  # ETNO Dany(14L), etc.
    ],
    'Toba Stefan 2021': [
        r'KICK\d*',
        r'CLAP',
        r'BD GABY',
        r'TOM \d',
        r'CRASH',
        r'GABY',
        r'pai zi mai',
        r'SHUPLAKA',
        r'NOGGA',
        r'CLAPS ARAB',
        r'T_DUM',
        r'Cinel',
        r'Pik',
        r'EDGE',
        r'Daula',
        r'STAR BU',
        r'CLOPOTEI',
    ],
    'Stefan Kit': [
        r'sd \d',  # sd 3, etc.
        r'SDCRV',
        r'TOOM',
    ],
    # Melodic samples - grouped by instrument type
    'Banat (Accordion)': [
        r'(Do|Re|Mi|Fa|Sol|La|Si)[\s_]?\d*[\s_]?banat',  # Do 1 banat, Mi2 banat, etc.
        r'banat',  # Any sample with "banat" in name
    ],
    'Sax Real': [
        r'\d+\.[A-G]#?\d+\.Sax Real',  # 27.G5.Sax Real
    ],
    'Real Zeta': [
        r'\d+Real Zeta-AD',  # 8Real Zeta-AD
        r'Zeta\d*-AD',
    ],
    'Muzo': [
        r'Muzo \d+ G[M|G]',
    ],
    'Blerim': [
        r'Blerim \d+ MG',
    ],
    'Braci nou': [
        r'Braci nou \d+ MG',
    ],
    'Returnela': [
        r'Returnela \d+ GM',
    ],
    'Kaval': [
        r'Kaval \d+ GM',
    ],
    'Improv': [
        r'Improv \d+ GM',
    ],
    'Fluier/Flute': [
        r'Fluierat',
        r'FLC\d+',
        r'FLA\d+',
        r'FLG\d*',
        r'FLH\d+',
    ],
    'Musama': [
        r'Musama\w* \d+[LR]?',
    ],
    'Ts Series': [
        r'Ts[A-Z]+\d*-AD',  # TsDO15-AD, TsSOL5-AD
    ],
    'Harmonica (h)': [
        r'^h\d+[LR]?$',  # h1L, h3R, h4R, etc.
    ],
    'R Series': [
        r'^R \d+ \d+ MG$',  # R 10 40 MG
    ],
    'Sound (notes)': [
        r'^(Do|Re|Mi|Fa|Sol|La|Si)\d+$',  # Do2, Mi2, Sol3
        r'^(SOL|DO|RE|MI|FA|LA|SI)\d+$',  # SOL3, DO2 (uppercase)
    ],
    'Clr/Clarinet': [
        r'\d+Clr-AD',  # 11Clr-AD
    ],
    'SaxL': [
        r'\d+SaxL-AD',  # 19SaxL-AD
    ],
}


def match_sample_to_program(sample_name: str) -> Optional[str]:
    """
    Try to match a sample name to a known program/drumkit.
    
    Args:
        sample_name: Name of the sample
        
    Returns:
        Program name or None if no match
    """
    for program_name, patterns in SAMPLE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, sample_name, re.IGNORECASE):
                return program_name
    return None


def group_samples_by_program(samples: List[SampleInfo]) -> Dict[str, SampleGroup]:
    """
    Group samples by their parent program.
    
    Args:
        samples: List of SampleInfo objects
        
    Returns:
        Dict mapping program name to SampleGroup
    """
    groups = defaultdict(lambda: SampleGroup(name="", samples=[], is_drumkit=False))
    unmatched = []
    
    for sample in samples:
        program_name = match_sample_to_program(sample.name)
        
        if program_name:
            # Update sample's parent_program
            sample.parent_program = program_name
            
            if not groups[program_name].name:
                groups[program_name].name = program_name
                # Determine if drumkit based on sample type or program name
                groups[program_name].is_drumkit = (
                    sample.sample_type == SampleType.DRUMKIT or
                    'Toba' in program_name or
                    'Kit' in program_name or
                    'fill' in program_name.lower()
                )
            
            groups[program_name].samples.append(sample)
        else:
            unmatched.append(sample)
    
    # Add unmatched samples to "Other" group
    if unmatched:
        groups['(Unassigned)'] = SampleGroup(
            name='(Unassigned)',
            samples=unmatched,
            is_drumkit=False
        )
    
    return dict(groups)


def group_samples_by_pattern(samples: List[SampleInfo]) -> Dict[str, SampleGroup]:
    """
    Group samples by common naming patterns (auto-detect groups).
    
    This uses pattern analysis to find samples that belong together
    even if we don't know the exact program name.
    """
    groups = defaultdict(lambda: SampleGroup(name="", samples=[], is_drumkit=False))
    
    # First, try to match to known programs
    for sample in samples:
        program_name = match_sample_to_program(sample.name)
        if program_name:
            sample.parent_program = program_name
            if not groups[program_name].name:
                groups[program_name].name = program_name
            groups[program_name].samples.append(sample)
            continue
        
        # Auto-detect groupings based on naming patterns
        name = sample.name
        
        # Pattern: numbered sequences like "man001", "man002"
        match = re.match(r'^([a-zA-Z]+)(\d+)$', name)
        if match:
            prefix = match.group(1)
            group_name = f'{prefix} (series)'
            sample.parent_program = group_name
            groups[group_name].name = group_name
            groups[group_name].samples.append(sample)
            continue
        
        # Pattern: instrument with note - "TsDO15-AD", "h3R"
        match = re.match(r'^(Ts|h|m\d|HA)([A-Z]+)?(\d+)?([LR])?', name)
        if match:
            prefix = match.group(1)
            group_name = f'{prefix} (instrument)'
            sample.parent_program = group_name
            groups[group_name].name = group_name
            groups[group_name].samples.append(sample)
            continue
        
        # Pattern: MS numbers - likely system/utility samples
        if name.startswith('MS') and name[2:].isdigit():
            group_name = 'MS (system)'
            sample.parent_program = group_name
            groups[group_name].name = group_name
            groups[group_name].samples.append(sample)
            continue
        
        # Unmatched
        groups['(Unassigned)'].name = '(Unassigned)'
        groups['(Unassigned)'].samples.append(sample)
    
    return dict(groups)


def print_sample_groups(groups: Dict[str, SampleGroup]):
    """Print sample groups for debugging."""
    print(f"\n{'='*60}")
    print("SAMPLE GROUPS")
    print('='*60)
    
    sorted_groups = sorted(groups.items(), key=lambda x: (-len(x[1].samples), x[0]))
    
    for name, group in sorted_groups:
        icon = "🥁" if group.is_drumkit else "🎹"
        print(f"\n{icon} {name} ({len(group.samples)} samples):")
        for sample in group.samples[:10]:
            print(f"    {sample.name}")
        if len(group.samples) > 10:
            print(f"    ... and {len(group.samples) - 10} more")


if __name__ == '__main__':
    # Test with actual samples
    from parsers.pcm_parser import PCMParser
    
    pcm_dir = 'samples/Stefanv22021.SET/PCM'
    parser = PCMParser()
    
    all_samples = []
    for filename in sorted(os.listdir(pcm_dir))[:20]:  # First 20 PCM files
        if not filename.endswith('.PCM'):
            continue
        
        path = os.path.join(pcm_dir, filename)
        with open(path, 'rb') as f:
            data = f.read()
        
        samples = parser.parse(data, filename)
        for s in samples:
            s.pcm_file = filename
        all_samples.extend(samples)
    
    print(f"Loaded {len(all_samples)} samples from PCM files")
    
    # Classify samples first
    from parsers.sample_classifier import classify_all_samples
    classify_all_samples(all_samples)
    
    # Group by program
    groups = group_samples_by_pattern(all_samples)
    print_sample_groups(groups)
