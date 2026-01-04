"""
Program-to-Sample Linker

Links programs from PCG files to their actual samples from PCM files.
Uses multiple strategies:
1. Direct name matching between program names and sample names
2. KMP multisample definitions
3. Pattern matching for common naming conventions
"""

import os
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.korg_types import SampleInfo, Program, SampleType


@dataclass
class ProgramSampleLink:
    """Links a program to its samples."""
    program_name: str
    program_source: str  # PCG file
    samples: List[SampleInfo] = field(default_factory=list)
    confidence: float = 0.0  # 0.0 = guess, 1.0 = confirmed
    link_method: str = ""  # How the link was established


@dataclass  
class MultisampleDef:
    """Multisample definition from KMP file."""
    name: str
    sample_names: List[str] = field(default_factory=list)
    key_zones: List[Tuple[int, int, str]] = field(default_factory=list)  # (low, high, sample_name)


class ProgramSampleLinker:
    """Links programs to samples using various strategies."""
    
    def __init__(self):
        self.programs: List[Program] = []
        self.samples: List[SampleInfo] = []
        self.multisamples: List[MultisampleDef] = []
        self.links: Dict[str, ProgramSampleLink] = {}
    
    def load_programs(self, programs: List[Program]):
        """Load programs from PCG parsing."""
        self.programs = programs
    
    def load_samples(self, samples: List[SampleInfo]):
        """Load samples from PCM parsing."""
        self.samples = samples
    
    def link_all(self) -> Dict[str, ProgramSampleLink]:
        """
        Attempt to link all programs to their samples.
        Returns dict of program_name -> ProgramSampleLink
        """
        self.links = {}
        
        # Filter valid programs first
        self._filter_valid_programs()
        
        # Strategy 1: Direct name matching
        self._link_by_name_match()
        
        # Strategy 2: Pattern-based matching (drumkit patterns)
        self._link_by_pattern()
        
        # Strategy 3: Common prefix matching
        self._link_by_prefix()
        
        return self.links
    
    def _filter_valid_programs(self):
        """Filter out invalid/garbage program names from PCG parsing artifacts."""
        valid_programs = []
        for prog in self.programs:
            name = prog.name.strip()
            
            # Skip very short names
            if len(name) < 3:
                continue
            
            # Skip names that are mostly non-alpha (need at least 50% letters)
            alpha_count = sum(1 for c in name if c.isalpha())
            if alpha_count < len(name) * 0.5:
                continue
            
            # Skip names with any non-printable or unusual chars
            special_count = sum(1 for c in name if c in '`~!@#$%^&*{}[]|\\<>?=')
            if special_count > 0:
                continue
            
            # Check first char is letter or valid start
            if name and not (name[0].isalpha() or name[0].isdigit()):
                continue
            
            # Skip if it looks like random chars (no vowels = probably garbage)
            vowels = set('aeiouAEIOU')
            has_vowel = any(c in vowels for c in name)
            if not has_vowel and len(name) > 3:
                continue
            
            valid_programs.append(prog)
        
        self.programs = valid_programs
    
    def _link_by_name_match(self):
        """Link by exact or fuzzy name matching."""
        for prog in self.programs:
            prog_name = prog.name.lower().strip()
            if not prog_name:
                continue
            
            matched_samples = []
            
            for sample in self.samples:
                sample_name = sample.name.lower().strip()
                
                # Exact match
                if prog_name in sample_name or sample_name in prog_name:
                    matched_samples.append(sample)
                    continue
                
                # Word-based match (any word in common)
                prog_words = set(re.findall(r'\w+', prog_name))
                sample_words = set(re.findall(r'\w+', sample_name))
                
                # Exclude common words and short words (1-2 chars)
                common_exclude = {'the', 'a', 'an', 'and', 'or', 'of', 'for', 'to', 'in', 'on', 'at'}
                prog_words = {w for w in prog_words if len(w) > 2} - common_exclude
                sample_words = {w for w in sample_words if len(w) > 2} - common_exclude
                
                # Only count as match if there's a significant word match (3+ chars)
                common_words = prog_words & sample_words
                if common_words and any(len(w) >= 3 for w in common_words):
                    matched_samples.append(sample)
            
            if matched_samples:
                link = ProgramSampleLink(
                    program_name=prog.name,
                    program_source=getattr(prog, 'source_file', ''),
                    samples=matched_samples,
                    confidence=0.7,
                    link_method='name_match'
                )
                self.links[prog.name] = link
    
    def _link_by_pattern(self):
        """Link using drumkit/sample naming patterns."""
        
        # Drumkit patterns - if program name contains these, look for related samples
        drumkit_keywords = {
            'toba': ['kick', 'snare', 'tom', 'crash', 'cymbal', 'hihat', 'clap', 
                     'fill', 'cinel', 'daula', 'bd', 'sd'],
            'kit': ['kick', 'snare', 'tom', 'crash', 'cymbal', 'hihat', 'clap'],
            'drum': ['kick', 'snare', 'tom', 'crash', 'ride', 'hihat'],
            'manele': ['pai', 'clap', 'daula', 'fill'],
            'etno': ['fill', 'dany', 'etno'],
        }
        
        # Melodic patterns
        melodic_keywords = {
            'banat': ['banat', 'do', 're', 'mi', 'fa', 'sol', 'la', 'si'],
            'acordeon': ['acordeon', 'acc', 'do', 're', 'mi'],
            'vioara': ['vioara', 'violin', 'vio'],
            'flute': ['fl', 'fluier', 'fleita', 'flc', 'fla', 'flg'],
            'sax': ['sax', 'saxo'],
            'clarinet': ['clr', 'clarinet'],
            'nai': ['nai', 'zamfir'],
        }
        
        for prog in self.programs:
            if prog.name in self.links:
                continue  # Already linked
            
            prog_lower = prog.name.lower()
            matched_samples = []
            
            # Check drumkit patterns
            for keyword, sample_patterns in drumkit_keywords.items():
                if keyword in prog_lower:
                    for sample in self.samples:
                        sample_lower = sample.name.lower()
                        if any(pat in sample_lower for pat in sample_patterns):
                            if sample not in matched_samples:
                                matched_samples.append(sample)
            
            # Check melodic patterns
            for keyword, sample_patterns in melodic_keywords.items():
                if keyword in prog_lower:
                    for sample in self.samples:
                        sample_lower = sample.name.lower()
                        if any(pat in sample_lower for pat in sample_patterns):
                            if sample not in matched_samples:
                                matched_samples.append(sample)
            
            if matched_samples:
                link = ProgramSampleLink(
                    program_name=prog.name,
                    program_source=getattr(prog, 'source_file', ''),
                    samples=matched_samples,
                    confidence=0.5,
                    link_method='pattern_match'
                )
                self.links[prog.name] = link
    
    def _link_by_prefix(self):
        """Link by common naming prefixes."""
        for prog in self.programs:
            if prog.name in self.links:
                continue
            
            # Try matching first N characters
            prog_prefix = prog.name[:4].lower() if len(prog.name) >= 4 else prog.name.lower()
            
            matched_samples = []
            for sample in self.samples:
                sample_prefix = sample.name[:4].lower() if len(sample.name) >= 4 else sample.name.lower()
                if prog_prefix == sample_prefix:
                    matched_samples.append(sample)
            
            if matched_samples:
                link = ProgramSampleLink(
                    program_name=prog.name,
                    program_source=getattr(prog, 'source_file', ''),
                    samples=matched_samples,
                    confidence=0.3,
                    link_method='prefix_match'
                )
                self.links[prog.name] = link
    
    def get_samples_for_program(self, program_name: str) -> List[SampleInfo]:
        """Get samples linked to a program."""
        if program_name in self.links:
            return self.links[program_name].samples
        return []
    
    def get_program_for_sample(self, sample: SampleInfo) -> Optional[str]:
        """Find which program a sample belongs to."""
        for prog_name, link in self.links.items():
            if sample in link.samples:
                return prog_name
        return None
    
    def get_unlinked_samples(self) -> List[SampleInfo]:
        """Get samples that aren't linked to any program."""
        linked_samples = set()
        for link in self.links.values():
            linked_samples.update(link.samples)
        
        return [s for s in self.samples if s not in linked_samples]
    
    def get_summary(self) -> Dict:
        """Get a summary of linking results."""
        total_samples = len(self.samples)
        linked_sample_names = set()
        for link in self.links.values():
            linked_sample_names.update(s.name for s in link.samples)
        
        return {
            'total_programs': len(self.programs),
            'linked_programs': len(self.links),
            'total_samples': total_samples,
            'linked_samples': len(linked_sample_names),
            'unlinked_samples': total_samples - len(linked_sample_names),
            'link_methods': {
                method: sum(1 for l in self.links.values() if l.link_method == method)
                for method in ['name_match', 'pattern_match', 'prefix_match']
            }
        }


def link_programs_to_samples(programs: List[Program], samples: List[SampleInfo]) -> ProgramSampleLinker:
    """Convenience function to link programs to samples."""
    linker = ProgramSampleLinker()
    linker.load_programs(programs)
    linker.load_samples(samples)
    linker.link_all()
    return linker


# Test the linker
if __name__ == '__main__':
    from parsers.pcm_parser import PCMParser
    from parsers.pcg_parser import PCGParser
    
    # Load samples
    pcm_parser = PCMParser()
    samples = []
    pcm_folder = r'..\samples\Stefanv22021.SET\PCM'
    for pcm_file in sorted(os.listdir(pcm_folder)):
        if pcm_file.endswith('.PCM'):
            path = os.path.join(pcm_folder, pcm_file)
            with open(path, 'rb') as f:
                data = f.read()
            file_samples = pcm_parser.parse(data, pcm_file)
            samples.extend(file_samples)
    
    print(f'Loaded {len(samples)} samples')
    
    # Load programs
    pcg_parser = PCGParser()
    programs = []
    sound_folder = r'..\samples\Stefanv22021.SET\SOUND'
    for pcg_file in sorted(os.listdir(sound_folder)):
        if pcg_file.endswith('.PCG'):
            path = os.path.join(sound_folder, pcg_file)
            with open(path, 'rb') as f:
                data = f.read()
            file_programs = pcg_parser.parse(data, pcg_file)
            for p in file_programs:
                p.source_file = pcg_file
            programs.extend(file_programs)
    
    print(f'Loaded {len(programs)} programs')
    
    # Link them
    linker = link_programs_to_samples(programs, samples)
    
    # Show results
    summary = linker.get_summary()
    print(f'\n{"="*60}')
    print('LINKING SUMMARY')
    print("="*60)
    print(f'Programs: {summary["linked_programs"]}/{summary["total_programs"]} linked')
    print(f'Samples: {summary["linked_samples"]}/{summary["total_samples"]} linked')
    print(f'Unlinked samples: {summary["unlinked_samples"]}')
    print(f'Link methods: {summary["link_methods"]}')
    
    print(f'\n{"="*60}')
    print('PROGRAM -> SAMPLE LINKS')
    print("="*60)
    for prog_name, link in sorted(linker.links.items()):
        print(f'\n{prog_name} ({link.link_method}, {link.confidence:.1%} confidence):')
        for s in link.samples[:10]:
            print(f'  - {s.name}')
        if len(link.samples) > 10:
            print(f'  ... and {len(link.samples) - 10} more')
