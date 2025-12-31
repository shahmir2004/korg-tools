"""
Korg Pa-series PCM File Parser

PCM files in Pa-series contain multiple audio samples in KORF format.
This parser extracts individual samples from these container files.

Format structure (discovered through analysis):
- Header with KORF signature
- Sample name table (24-byte entries: 16-byte name + 8-byte params)
- Audio data (16-bit signed PCM, mono, typically 48kHz)
- Footer with KBEG marker, offset table (big-endian), and KEND marker
"""

import struct
import os
import sys
from typing import Optional, List, Tuple
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.korg_types import SampleInfo, LoopMode


class PCMParser:
    """Parser for Korg Pa-series PCM files."""
    
    def __init__(self):
        self.debug = False
        self.default_sample_rate = 48000  # Pa-series typically uses 48kHz
    
    def parse(self, data: bytes, filename: str = "Unknown") -> List[SampleInfo]:
        """
        Parse a PCM file and extract all samples.
        
        Args:
            data: Raw bytes of the PCM file
            filename: Source filename for reference
            
        Returns:
            List of SampleInfo objects with audio data
        """
        samples = []
        
        if len(data) < 256:
            return samples
        
        # Find KBEG marker (contains offset table)
        kbeg_pos = data.rfind(b'KBEG')
        kend_pos = data.rfind(b'KEND')
        
        if kbeg_pos < 0:
            if self.debug:
                print(f"No KBEG marker found in {filename}")
            return self._parse_legacy_format(data, filename)
        
        # Parse sample names from header
        names_map = self._parse_sample_names(data)
        
        # Parse offset table from footer
        sample_offsets = self._parse_offset_table(data, kbeg_pos, kend_pos)
        
        if not sample_offsets:
            if self.debug:
                print(f"No sample offsets found in {filename}")
            return samples
        
        # Add end boundary
        boundaries = sample_offsets + [kbeg_pos]
        
        # Per-sample header size (contains metadata, sample rate, etc.)
        SAMPLE_HEADER_SIZE = 0x4C  # 76 bytes
        
        # Extract each sample
        for i in range(len(boundaries) - 1):
            block_start = boundaries[i]
            block_end = boundaries[i + 1]
            block_size = block_end - block_start
            
            if block_size <= SAMPLE_HEADER_SIZE or block_start >= len(data):
                continue
            
            # Parse per-sample header for sample rate
            sample_header = data[block_start:block_start + SAMPLE_HEADER_SIZE]
            
            # Sample rate is at bytes 20-21 as big-endian u16
            if len(sample_header) >= 22:
                sample_rate = struct.unpack('>H', sample_header[20:22])[0]
                if sample_rate == 0:
                    sample_rate = self.default_sample_rate
            else:
                sample_rate = self.default_sample_rate
            
            # Find name by index
            name = names_map.get(i, f'{filename}_Sample_{i}')
            
            # Audio data starts after the per-sample header
            audio_start = block_start + SAMPLE_HEADER_SIZE
            audio_data_be = data[audio_start:block_end]
            
            # Convert from big-endian to little-endian (swap bytes)
            audio_data = self._swap_endian(audio_data_be)
            
            num_samples = len(audio_data) // 2  # 16-bit = 2 bytes per sample
            
            sample = SampleInfo(
                name=name,
                sample_rate=sample_rate,
                bit_depth=16,
                channels=1,
                num_samples=num_samples,
                loop_mode=LoopMode.NO_LOOP,
                root_key=60,
                data_offset=audio_start,
                data_size=len(audio_data),
                raw_data=audio_data
            )
            samples.append(sample)
            
            if self.debug:
                duration = num_samples / sample_rate
                print(f'  Sample {i}: "{name}" offset=0x{audio_start:X} size={len(audio_data)} duration={duration:.2f}s')
        
        return samples
    
    def _swap_endian(self, data: bytes) -> bytes:
        """Swap byte order for 16-bit audio (big-endian to little-endian)."""
        if len(data) < 2:
            return data
        # Ensure even length
        if len(data) % 2 != 0:
            data = data[:-1]
        # Swap each pair of bytes
        arr = np.frombuffer(data, dtype='>i2')  # Big-endian 16-bit
        return arr.astype('<i2').tobytes()  # Convert to little-endian
    
    def _parse_sample_names(self, data: bytes) -> dict:
        """Parse sample names from header and return index->name mapping."""
        names = {}
        
        # Find KORF signature
        korf_pos = data.find(b'KORF')
        if korf_pos < 0:
            return names
        
        # Sample entries start after KORF header (typically at 0x24)
        pos = korf_pos + 13  # Skip "KORF" and some header bytes
        
        # Align to 24-byte boundary after KORF
        if pos % 24 != 0:
            pos = ((pos // 24) + 1) * 24
        
        # Try starting at 0x24 if that's a valid position
        if korf_pos < 0x24:
            pos = 0x24
        
        while pos < min(len(data), 0x1000):
            if pos + 24 > len(data):
                break
            
            entry = data[pos:pos+24]
            name_bytes = entry[:16]
            
            # Check for valid name (starts with printable ASCII)
            if 32 <= name_bytes[0] <= 126:
                # Find name end (null or non-printable)
                name_end = 16
                for j in range(16):
                    if name_bytes[j] == 0 or not (32 <= name_bytes[j] <= 126):
                        name_end = j
                        break
                
                if name_end >= 2:
                    name = name_bytes[:name_end].decode('ascii', errors='replace').strip()
                    # Sample index is at offset 20 in entry (4th byte of params)
                    idx = entry[20]
                    names[idx] = name
                    pos += 24
                    continue
            
            # No more valid entries
            break
        
        return names
    
    def _parse_offset_table(self, data: bytes, kbeg_pos: int, kend_pos: int) -> List[int]:
        """Parse the sample offset table from footer (AFTER KBEG marker)."""
        offsets = []
        
        if kend_pos <= kbeg_pos:
            kend_pos = len(data)
        
        # Format: KBEG [unknown 4 bytes] [offset1] [offset2] ... KEND
        # The offsets are big-endian 4-byte values
        
        pos = kbeg_pos + 4  # Skip 'KBEG'
        
        # First value after KBEG might be a count or header info, skip it
        # Actually check if second value looks like an offset
        if pos + 8 <= len(data):
            first_val = struct.unpack('>I', data[pos:pos+4])[0]
            second_val = struct.unpack('>I', data[pos+4:pos+8])[0]
            
            # If second value looks like a valid offset (e.g., 0xE4), skip first
            if second_val > 0x40 and second_val < kbeg_pos:
                pos += 4  # Skip the first value (likely count or header size)
        
        while pos < kend_pos - 3:
            val = struct.unpack('>I', data[pos:pos+4])[0]
            
            # Valid offset: reasonable position in file, before KBEG
            if 0x40 < val < kbeg_pos:
                offsets.append(val)
            
            pos += 4
        
        return offsets
    
    def _find_audio_start(self, data: bytes) -> int:
        """Find where audio data starts after the header."""
        # This is now handled by the offset table itself
        return 0
    
    def _parse_legacy_format(self, data: bytes, filename: str) -> List[SampleInfo]:
        """Fallback parser for older PCM formats without KBEG marker."""
        samples = []
        
        # Check for KORF signature
        korf_pos = data.find(b'KORF')
        if korf_pos < 0:
            return samples
        
        # Try to find audio data start by looking for non-header data
        audio_start = 0x1000  # Default assumption
        
        # Look for reasonable audio data start
        for offset in [0x100, 0x200, 0x400, 0x800, 0x1000]:
            if offset < len(data) - 100:
                chunk = data[offset:offset+100]
                # Check if this looks like audio
                vals = struct.unpack('<50h', chunk)
                max_val = max(abs(v) for v in vals)
                if max_val > 1000:  # Likely audio
                    audio_start = offset
                    break
        
        # Create single sample from remaining data
        audio_data = data[audio_start:]
        if len(audio_data) > 1000:
            sample = SampleInfo(
                name=filename.replace('.PCM', ''),
                sample_rate=self.default_sample_rate,
                bit_depth=16,
                channels=1,
                num_samples=len(audio_data) // 2,
                data_offset=audio_start,
                data_size=len(audio_data),
                raw_data=audio_data
            )
            samples.append(sample)
        
        return samples
    
    def parse_file(self, filepath: str) -> List[SampleInfo]:
        """Parse a PCM file from disk."""
        with open(filepath, 'rb') as f:
            data = f.read()
        return self.parse(data, os.path.basename(filepath))


def parse_pcm(filepath: str) -> List[SampleInfo]:
    """Convenience function to parse a PCM file."""
    parser = PCMParser()
    return parser.parse_file(filepath)
