"""
Korg PCG (Program/Combination/Global) File Parser

PCG files contain program and combination data for Korg synthesizers.
This includes sound definitions, effect settings, and references to samples.
"""

import struct
from typing import Optional, List, Dict, Any
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.korg_types import Program, Multisample


class PCGParser:
    """Parser for Korg PCG file format."""
    
    SIGNATURES = [b'PCG1', b'KORG', b'pcg1']
    
    # Common Korg program categories
    CATEGORIES = {
        0: "Piano",
        1: "E.Piano",
        2: "Organ",
        3: "Guitar",
        4: "Bass",
        5: "Strings",
        6: "Brass",
        7: "Woodwind",
        8: "Synth Lead",
        9: "Synth Pad",
        10: "Synth FX",
        11: "Ethnic",
        12: "Percussion",
        13: "Drums",
        14: "SFX",
        15: "User"
    }
    
    def __init__(self):
        self.debug = False
    
    def parse(self, data: bytes, name: str = "Unknown") -> List[Program]:
        """
        Parse a PCG file and return list of programs.
        
        Args:
            data: Raw bytes of the PCG file
            name: Base name for programs
            
        Returns:
            List of Program objects
        """
        if len(data) < 64:
            return []
        
        header = data[:4]
        
        if header == b'KORG':
            return self._parse_korg_format(data, name)
        elif header in [b'PCG1', b'pcg1']:
            return self._parse_pcg1_format(data, name)
        else:
            return self._parse_generic_format(data, name)
    
    def _parse_korg_format(self, data: bytes, name: str) -> List[Program]:
        """Parse PCG with KORG header (common in Pa series)."""
        programs = []
        
        try:
            # KORG header typically followed by:
            # - File type identifier
            # - Version info
            # - Chunk-based structure
            
            pos = 4
            
            # Look for program chunks
            while pos < len(data) - 8:
                # Check for chunk identifiers
                chunk_id = data[pos:pos+4]
                
                if chunk_id in [b'PRG1', b'PROG', b'prg1']:
                    chunk_size = struct.unpack('<I', data[pos+4:pos+8])[0]
                    if chunk_size > 0 and pos + 8 + chunk_size <= len(data):
                        chunk_data = data[pos+8:pos+8+chunk_size]
                        progs = self._parse_program_chunk(chunk_data, name)
                        programs.extend(progs)
                        pos += 8 + chunk_size
                        continue
                
                elif chunk_id in [b'CMB1', b'COMB', b'cmb1']:
                    # Combination chunk - skip for now
                    chunk_size = struct.unpack('<I', data[pos+4:pos+8])[0]
                    pos += 8 + chunk_size
                    continue
                
                elif chunk_id in [b'GLB1', b'GLOB', b'glb1']:
                    # Global settings chunk - skip
                    chunk_size = struct.unpack('<I', data[pos+4:pos+8])[0]
                    pos += 8 + chunk_size
                    continue
                
                pos += 1
            
            # If no chunks found, try linear scan for programs
            if not programs:
                programs = self._scan_for_programs(data, name)
            
        except Exception as e:
            if self.debug:
                print(f"KORG format parse error: {e}")
        
        return programs
    
    def _parse_pcg1_format(self, data: bytes, name: str) -> List[Program]:
        """Parse PCG1 format."""
        programs = []
        
        try:
            # PCG1 header:
            # 0x00: "PCG1"
            # 0x04: Version
            # 0x08: Number of programs
            # 0x0C: Program data offset
            
            num_programs = struct.unpack('<H', data[8:10])[0]
            
            if num_programs > 0 and num_programs < 1000:
                programs = self._scan_for_programs(data, name, max_programs=num_programs)
            else:
                programs = self._scan_for_programs(data, name)
            
        except Exception as e:
            if self.debug:
                print(f"PCG1 parse error: {e}")
            programs = self._scan_for_programs(data, name)
        
        return programs
    
    def _parse_generic_format(self, data: bytes, name: str) -> List[Program]:
        """Parse unknown PCG format."""
        return self._scan_for_programs(data, name)
    
    def _parse_program_chunk(self, data: bytes, base_name: str) -> List[Program]:
        """Parse a program data chunk."""
        programs = []
        
        try:
            # Program chunk structure varies, but typically:
            # - Number of programs (2-4 bytes)
            # - Program entries (fixed size each)
            
            if len(data) < 4:
                return programs
            
            num_programs = struct.unpack('<H', data[0:2])[0]
            
            if num_programs > 500:  # Probably wrong interpretation
                num_programs = struct.unpack('<H', data[2:4])[0]
            
            if num_programs > 500:
                return self._scan_for_programs(data, base_name)
            
            # Common program entry sizes
            entry_sizes = [128, 256, 512, 1024]
            
            for entry_size in entry_sizes:
                if 4 + num_programs * entry_size > len(data):
                    continue
                
                for i in range(min(num_programs, 128)):
                    offset = 4 + i * entry_size
                    entry = data[offset:offset+entry_size]
                    
                    prog = self._parse_program_entry(entry, f"{base_name}_{i:03d}", i)
                    if prog:
                        programs.append(prog)
                
                if programs:
                    break
            
        except Exception as e:
            if self.debug:
                print(f"Program chunk parse error: {e}")
        
        return programs
    
    def _parse_program_entry(self, data: bytes, name: str, index: int) -> Optional[Program]:
        """Parse a single program entry."""
        if len(data) < 32:
            return None
        
        try:
            # Try to extract program name (usually at the start)
            prog_name = name
            
            # Look for null-terminated string at start
            name_end = data.find(b'\x00', 0, 24)
            if name_end > 0:
                try:
                    extracted = data[0:name_end].decode('ascii', errors='ignore').strip()
                    if extracted and len(extracted) >= 2:
                        prog_name = extracted
                except:
                    pass
            
            # Category is often at a fixed offset
            category_idx = data[24] if len(data) > 24 else 0
            category = self.CATEGORIES.get(category_idx % 16, "User")
            
            # Bank and number
            bank = data[25] if len(data) > 25 else 0
            number = index
            
            return Program(
                name=prog_name,
                bank=bank,
                number=number,
                category=category,
                multisamples=[],
                parameters={}
            )
            
        except:
            return None
    
    def _scan_for_programs(self, data: bytes, base_name: str, max_programs: int = 50) -> List[Program]:
        """
        Scan data for program-like structures.
        This is a fallback when format is unknown.
        """
        programs = []
        
        # Look for readable ASCII strings that might be program names
        # Korg program names are typically 16-24 characters
        
        pos = 0
        prog_count = 0
        
        while pos < len(data) - 32 and prog_count < max_programs:
            # Look for sequences of printable ASCII
            if 32 <= data[pos] <= 126:
                end = pos
                while end < len(data) and end - pos < 32:
                    if 32 <= data[end] <= 126:
                        end += 1
                    else:
                        break
                
                if end - pos >= 4:  # Minimum name length
                    try:
                        name = data[pos:end].decode('ascii').strip()
                        
                        # Basic validation - name should be alphanumeric-ish
                        if name and len(name) >= 3 and any(c.isalpha() for c in name):
                            programs.append(Program(
                                name=name,
                                bank=prog_count // 128,
                                number=prog_count % 128,
                                category="Unknown"
                            ))
                            prog_count += 1
                    except:
                        pass
                
                pos = end
            else:
                pos += 1
        
        return programs
    
    def get_program_summary(self, programs: List[Program]) -> Dict[str, int]:
        """Get a summary of programs by category."""
        summary = {}
        for prog in programs:
            cat = prog.category or "Unknown"
            summary[cat] = summary.get(cat, 0) + 1
        return summary


def parse_pcg(data: bytes, name: str = "Unknown") -> List[Program]:
    """Parse a PCG file and return list of Programs."""
    parser = PCGParser()
    return parser.parse(data, name)
