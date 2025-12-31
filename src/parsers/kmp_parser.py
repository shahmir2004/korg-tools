"""
Korg Multisample Parameter (.KMP) Parser

KMP files define how samples are mapped across the keyboard,
including velocity layers, key ranges, and tuning information.
"""

import struct
from typing import Optional, List
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.korg_types import Multisample, KeyZone, SampleInfo


class KMPParser:
    """Parser for Korg Multisample Parameter (.KMP) format."""
    
    SIGNATURES = [b'KMP1', b'MSP1', b'kmp1']
    
    def __init__(self):
        self.debug = False
    
    def parse(self, data: bytes, name: str = "Unknown") -> Optional[Multisample]:
        """
        Parse a KMP file and return Multisample information.
        
        Args:
            data: Raw bytes of the KMP file
            name: Name to assign to the multisample
            
        Returns:
            Multisample object or None if parsing fails
        """
        if len(data) < 32:
            return None
        
        header = data[:4]
        
        if header in self.SIGNATURES:
            return self._parse_kmp1_format(data, name)
        else:
            return self._parse_generic_format(data, name)
    
    def _parse_kmp1_format(self, data: bytes, name: str) -> Optional[Multisample]:
        """
        Parse KMP1 format.
        
        Typical KMP1 structure:
        - Header (4 bytes): "KMP1"
        - Version/Size (4 bytes)
        - Name (variable, often 24 bytes null-padded)
        - Number of zones (2 or 4 bytes)
        - Zone definitions (variable per zone)
        - Sample references (filenames or indices)
        """
        try:
            # Read basic header
            version = struct.unpack('<I', data[4:8])[0]
            
            # Try to read name from header
            ms_name = name
            name_end = data.find(b'\x00', 8, 40)
            if name_end > 8:
                try:
                    ms_name = data[8:name_end].decode('ascii', errors='ignore').strip()
                    if not ms_name:
                        ms_name = name
                except:
                    pass
            
            # Find zone count (position varies by version)
            zones = []
            
            # Common layout: zone count at offset 32 or 40
            for zone_offset in [32, 40, 48]:
                if zone_offset + 2 <= len(data):
                    num_zones = struct.unpack('<H', data[zone_offset:zone_offset+2])[0]
                    if 1 <= num_zones <= 128:  # Reasonable zone count
                        zones = self._parse_zones(data, zone_offset + 2, num_zones)
                        if zones:
                            break
            
            if not zones:
                # Create a default single-zone mapping
                zones = [KeyZone(
                    low_key=0,
                    high_key=127,
                    low_velocity=0,
                    high_velocity=127,
                    sample_index=0,
                    root_key=60
                )]
            
            return Multisample(
                name=ms_name,
                zones=zones,
                samples=[]  # Samples loaded separately
            )
            
        except Exception as e:
            if self.debug:
                print(f"KMP1 parse error: {e}")
            return None
    
    def _parse_zones(self, data: bytes, offset: int, num_zones: int) -> List[KeyZone]:
        """Parse zone definitions from KMP data."""
        zones = []
        
        # Zone structure (typical, 16-32 bytes per zone):
        # - Low key (1 byte)
        # - High key (1 byte)
        # - Root key (1 byte)  
        # - Fine tune (1-2 bytes, signed)
        # - Low velocity (1 byte)
        # - High velocity (1 byte)
        # - Sample index (2-4 bytes)
        # - Level (1-2 bytes)
        # - Pan (1 byte)
        # - Padding/reserved
        
        zone_sizes = [16, 20, 24, 32]
        
        for zone_size in zone_sizes:
            if offset + num_zones * zone_size > len(data):
                continue
            
            zones = []
            valid = True
            
            for i in range(num_zones):
                pos = offset + i * zone_size
                
                try:
                    low_key = data[pos]
                    high_key = data[pos + 1]
                    root_key = data[pos + 2]
                    fine_tune = struct.unpack('<b', data[pos+3:pos+4])[0]
                    low_vel = data[pos + 4] if zone_size > 4 else 0
                    high_vel = data[pos + 5] if zone_size > 5 else 127
                    sample_idx = struct.unpack('<H', data[pos+6:pos+8])[0] if zone_size > 7 else i
                    level = data[pos + 8] if zone_size > 8 else 127
                    pan = data[pos + 9] if zone_size > 9 else 64
                    
                    # Validate
                    if low_key > 127 or high_key > 127 or low_key > high_key:
                        valid = False
                        break
                    if root_key > 127:
                        root_key = (low_key + high_key) // 2
                    
                    zones.append(KeyZone(
                        low_key=low_key,
                        high_key=high_key,
                        low_velocity=low_vel,
                        high_velocity=high_vel,
                        sample_index=sample_idx,
                        root_key=root_key,
                        fine_tune=fine_tune,
                        level=level,
                        pan=pan
                    ))
                    
                except Exception:
                    valid = False
                    break
            
            if valid and zones:
                return zones
        
        return []
    
    def _parse_generic_format(self, data: bytes, name: str) -> Optional[Multisample]:
        """Parse unknown format by making educated guesses."""
        # Return a simple single-zone multisample as fallback
        return Multisample(
            name=name,
            zones=[KeyZone(
                low_key=0,
                high_key=127,
                low_velocity=0,
                high_velocity=127,
                sample_index=0,
                root_key=60
            )],
            samples=[]
        )
    
    def get_sample_references(self, data: bytes) -> List[str]:
        """
        Extract sample file references from KMP data.
        Some KMP files contain filenames of associated KSF files.
        """
        references = []
        
        # Look for .KSF or .ksf strings in the data
        search_terms = [b'.KSF', b'.ksf', b'.KSF\x00', b'.ksf\x00']
        
        for term in search_terms:
            pos = 0
            while True:
                idx = data.find(term, pos)
                if idx < 0:
                    break
                
                # Find the start of the filename (scan backwards)
                start = idx
                while start > 0 and data[start-1:start] not in [b'\x00', b' ', b'/']:
                    start -= 1
                    if idx - start > 100:  # Filename too long
                        break
                
                if start < idx:
                    try:
                        filename = data[start:idx+4].decode('ascii', errors='ignore')
                        if filename and len(filename) > 4:
                            references.append(filename)
                    except:
                        pass
                
                pos = idx + 1
        
        return list(set(references))


def parse_kmp(data: bytes, name: str = "Unknown") -> Optional[Multisample]:
    """Parse a KMP file and return Multisample."""
    parser = KMPParser()
    return parser.parse(data, name)
