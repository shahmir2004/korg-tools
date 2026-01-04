"""
Korg Pa-series Program/Drumkit Parser

Parses PCG files to extract program and drumkit definitions.
These define which samples belong to which sounds.
"""

import struct
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.korg_types import Program, DrumKit, SampleInfo, SampleType


@dataclass
class ProgramDef:
    """A program/drumkit definition from PCG."""
    name: str
    pcg_file: str  # Source PCG file (USER01.PCG, USERDK.PCG, etc.)
    is_drumkit: bool = False
    bank: int = 0
    number: int = 0
    meta: bytes = b''
    offset: int = 0


class ProgramParser:
    """Parser for Korg Pa-series PCG program definitions."""
    
    def __init__(self):
        self.debug = False
    
    def parse_pcg_file(self, data: bytes, filename: str = "Unknown.PCG") -> List[ProgramDef]:
        """
        Parse a PCG file and extract program/drumkit definitions.
        
        Args:
            data: Raw bytes of PCG file
            filename: Source filename
            
        Returns:
            List of ProgramDef objects
        """
        programs = []
        
        if len(data) < 64:
            return programs
        
        # Find KORF header
        korf_pos = data.find(b'KORF')
        if korf_pos < 0:
            return programs
        
        # Determine if this is a drumkit file
        is_drumkit = 'DK' in filename.upper() or 'DRUM' in filename.upper()
        
        # Program entries start at 0x24 (after KORF header section)
        # Each entry is 24 bytes: 16-byte name + 8-byte metadata
        pos = 0x24
        
        while pos + 24 <= len(data):
            entry = data[pos:pos+24]
            
            # Check if first byte is printable ASCII (indicating a name)
            if not (32 <= entry[0] <= 126):
                # Check for end markers
                if entry[:4] == b'OC31' or entry[:4] == b'\x10\x02\x00\x38':
                    break
                pos += 24
                continue
            
            # Extract name (null-terminated, max 16 bytes)
            name_end = 16
            for j in range(16):
                if entry[j] == 0 or not (32 <= entry[j] <= 126):
                    name_end = j
                    break
            
            if name_end >= 3:
                name = entry[:name_end].decode('ascii', errors='replace').strip()
                
                # Skip if name looks like garbage
                if self._is_valid_name(name):
                    meta = entry[16:24]
                    
                    programs.append(ProgramDef(
                        name=name,
                        pcg_file=filename,
                        is_drumkit=is_drumkit,
                        bank=meta[4] if len(meta) > 4 else 0,
                        number=meta[5] if len(meta) > 5 else 0,
                        meta=meta,
                        offset=pos
                    ))
            else:
                # No more valid names
                break
            
            pos += 24
        
        return programs
    
    def _is_valid_name(self, name: str) -> bool:
        """Check if a name looks like a valid program/drumkit name."""
        if len(name) < 3:
            return False
        
        # Check for excessive special characters
        special_count = sum(1 for c in name if c in '@#$%^&*(){}[]|\\<>~`')
        if special_count > len(name) // 3:
            return False
        
        # Should have at least some letters
        if not any(c.isalpha() for c in name):
            return False
        
        return True
    
    def parse_all_pcg_files(self, sound_dir: str) -> Dict[str, List[ProgramDef]]:
        """
        Parse all PCG files in the SOUND directory.
        
        Args:
            sound_dir: Path to SOUND directory
            
        Returns:
            Dict mapping PCG filename to list of ProgramDefs
        """
        all_programs = {}
        
        if not os.path.exists(sound_dir):
            return all_programs
        
        for filename in os.listdir(sound_dir):
            if filename.upper().endswith('.PCG'):
                path = os.path.join(sound_dir, filename)
                try:
                    with open(path, 'rb') as f:
                        data = f.read()
                    programs = self.parse_pcg_file(data, filename)
                    if programs:
                        all_programs[filename] = programs
                except Exception as e:
                    if self.debug:
                        print(f"Error parsing {filename}: {e}")
        
        return all_programs


def get_all_programs(set_path: str) -> Tuple[List[ProgramDef], List[ProgramDef]]:
    """
    Get all programs and drumkits from a .SET package.
    
    Args:
        set_path: Path to .SET folder
        
    Returns:
        Tuple of (melodic_programs, drumkits)
    """
    parser = ProgramParser()
    sound_dir = os.path.join(set_path, 'SOUND')
    
    all_pcg = parser.parse_all_pcg_files(sound_dir)
    
    melodic = []
    drumkits = []
    
    for filename, programs in all_pcg.items():
        for prog in programs:
            if prog.is_drumkit:
                drumkits.append(prog)
            else:
                melodic.append(prog)
    
    return melodic, drumkits


if __name__ == '__main__':
    # Test
    set_path = 'samples/Stefanv22021.SET'
    melodic, drumkits = get_all_programs(set_path)
    
    print("Drumkits:")
    for dk in drumkits:
        print(f"  {dk.name} (from {dk.pcg_file})")
    
    print(f"\nMelodic Programs ({len(melodic)}):")
    for prog in melodic[:20]:
        print(f"  {prog.name} (from {prog.pcg_file})")
