"""
Korg Sample File (.KSF) Parser

KSF files contain raw audio sample data with header information.
Based on reverse-engineering of Korg sample formats.
"""

import struct
from typing import Optional, Tuple
import numpy as np

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.korg_types import SampleInfo, SampleFormat, LoopMode


class KSFParser:
    """Parser for Korg Sample File (.KSF) format."""
    
    # Known KSF header signatures
    SIGNATURES = [b'KSF1', b'KORF', b'kSF1', b'RIFF']
    
    def __init__(self):
        self.debug = False
    
    def parse(self, data: bytes, name: str = "Unknown") -> Optional[SampleInfo]:
        """
        Parse a KSF file and return sample information.
        
        Args:
            data: Raw bytes of the KSF file
            name: Name to assign to the sample
            
        Returns:
            SampleInfo object or None if parsing fails
        """
        if len(data) < 44:  # Minimum header size
            return None
        
        # Try different parsing strategies based on file signature
        header = data[:4]
        
        if header == b'RIFF':
            return self._parse_riff_format(data, name)
        elif header in [b'KSF1', b'kSF1']:
            return self._parse_ksf1_format(data, name)
        else:
            # Try to detect format by probing
            return self._parse_generic_format(data, name)
    
    def _parse_ksf1_format(self, data: bytes, name: str) -> Optional[SampleInfo]:
        """Parse native Korg KSF1 format."""
        try:
            # KSF1 header structure (typical layout):
            # 0x00: 4 bytes - "KSF1" signature
            # 0x04: 4 bytes - File size or version
            # 0x08: 4 bytes - Sample rate
            # 0x0C: 2 bytes - Bit depth
            # 0x0E: 2 bytes - Channels
            # 0x10: 4 bytes - Number of samples
            # 0x14: 4 bytes - Loop start
            # 0x18: 4 bytes - Loop end
            # 0x1C: 1 byte  - Loop mode
            # 0x1D: 1 byte  - Root key
            # 0x1E: 2 bytes - Fine tune (cents)
            # 0x20: Variable - Sample name (null-terminated or fixed)
            # Variable: Audio data starts after header
            
            sample_rate = struct.unpack('<I', data[8:12])[0]
            bit_depth = struct.unpack('<H', data[12:14])[0]
            channels = struct.unpack('<H', data[14:16])[0]
            num_samples = struct.unpack('<I', data[16:20])[0]
            loop_start = struct.unpack('<I', data[20:24])[0]
            loop_end = struct.unpack('<I', data[24:28])[0]
            loop_mode = data[28] if len(data) > 28 else 0
            root_key = data[29] if len(data) > 29 else 60
            fine_tune = struct.unpack('<h', data[30:32])[0] if len(data) > 31 else 0
            
            # Validate parsed values
            if not self._validate_sample_params(sample_rate, bit_depth, channels):
                return self._parse_generic_format(data, name)
            
            # Find where audio data starts (after header, typically 64 or 128 bytes)
            data_offset = self._find_audio_data_offset(data, 32)
            data_size = len(data) - data_offset
            
            return SampleInfo(
                name=name,
                sample_rate=sample_rate,
                bit_depth=bit_depth,
                channels=channels,
                num_samples=num_samples if num_samples > 0 else self._calc_num_samples(data_size, bit_depth, channels),
                loop_start=loop_start,
                loop_end=loop_end if loop_end > 0 else num_samples,
                loop_mode=LoopMode(min(loop_mode, 3)),
                root_key=root_key,
                fine_tune=fine_tune,
                data_offset=data_offset,
                data_size=data_size,
                raw_data=data[data_offset:]
            )
            
        except Exception as e:
            if self.debug:
                print(f"KSF1 parse error: {e}")
            return self._parse_generic_format(data, name)
    
    def _parse_riff_format(self, data: bytes, name: str) -> Optional[SampleInfo]:
        """Parse RIFF/WAV format (some Korg files use this)."""
        try:
            if data[8:12] != b'WAVE':
                return None
            
            # Parse RIFF chunks
            pos = 12
            sample_rate = 44100
            bit_depth = 16
            channels = 1
            audio_data = None
            data_offset = 0
            
            while pos < len(data) - 8:
                chunk_id = data[pos:pos+4]
                chunk_size = struct.unpack('<I', data[pos+4:pos+8])[0]
                
                if chunk_id == b'fmt ':
                    fmt_data = data[pos+8:pos+8+chunk_size]
                    audio_format = struct.unpack('<H', fmt_data[0:2])[0]
                    channels = struct.unpack('<H', fmt_data[2:4])[0]
                    sample_rate = struct.unpack('<I', fmt_data[4:8])[0]
                    bit_depth = struct.unpack('<H', fmt_data[14:16])[0]
                    
                elif chunk_id == b'data':
                    data_offset = pos + 8
                    audio_data = data[pos+8:pos+8+chunk_size]
                    break
                
                pos += 8 + chunk_size
                if chunk_size % 2:  # Pad to word boundary
                    pos += 1
            
            if audio_data is None:
                return None
            
            num_samples = len(audio_data) // (bit_depth // 8) // channels
            
            return SampleInfo(
                name=name,
                sample_rate=sample_rate,
                bit_depth=bit_depth,
                channels=channels,
                num_samples=num_samples,
                loop_start=0,
                loop_end=num_samples,
                loop_mode=LoopMode.NO_LOOP,
                root_key=60,
                fine_tune=0,
                data_offset=data_offset,
                data_size=len(audio_data),
                raw_data=audio_data
            )
            
        except Exception as e:
            if self.debug:
                print(f"RIFF parse error: {e}")
            return None
    
    def _parse_generic_format(self, data: bytes, name: str) -> Optional[SampleInfo]:
        """
        Attempt to parse an unknown format by making educated guesses.
        Assumes 16-bit stereo 44.1kHz as defaults.
        """
        # Skip potential header (try common header sizes)
        for header_size in [0, 32, 44, 64, 128, 256]:
            if header_size >= len(data):
                continue
                
            audio_data = data[header_size:]
            
            # Check if remaining data looks like PCM audio
            if self._looks_like_audio(audio_data):
                # Assume common defaults
                sample_rate = 44100
                bit_depth = 16
                channels = 2
                
                num_samples = len(audio_data) // (bit_depth // 8) // channels
                
                return SampleInfo(
                    name=name,
                    sample_rate=sample_rate,
                    bit_depth=bit_depth,
                    channels=channels,
                    num_samples=num_samples,
                    loop_start=0,
                    loop_end=num_samples,
                    loop_mode=LoopMode.NO_LOOP,
                    root_key=60,
                    data_offset=header_size,
                    data_size=len(audio_data),
                    raw_data=audio_data
                )
        
        return None
    
    def _validate_sample_params(self, sample_rate: int, bit_depth: int, channels: int) -> bool:
        """Validate that sample parameters are within reasonable ranges."""
        if sample_rate < 8000 or sample_rate > 192000:
            return False
        if bit_depth not in [8, 16, 24, 32]:
            return False
        if channels < 1 or channels > 8:
            return False
        return True
    
    def _find_audio_data_offset(self, data: bytes, min_offset: int) -> int:
        """Try to find where audio data starts in the file."""
        # Look for common header end markers or just use min_offset
        # Some files have variable-length headers
        
        for offset in [64, 128, 256, min_offset]:
            if offset < len(data):
                return offset
        return min_offset
    
    def _calc_num_samples(self, data_size: int, bit_depth: int, channels: int) -> int:
        """Calculate number of samples from data size."""
        bytes_per_sample = (bit_depth // 8) * channels
        if bytes_per_sample > 0:
            return data_size // bytes_per_sample
        return 0
    
    def _looks_like_audio(self, data: bytes, sample_size: int = 1000) -> bool:
        """
        Heuristic check if data looks like PCM audio.
        Real audio typically has certain statistical properties.
        """
        if len(data) < sample_size * 2:
            return len(data) > 100  # Just accept small files
        
        # Check for 16-bit signed samples
        try:
            samples = np.frombuffer(data[:sample_size*2], dtype=np.int16)
            
            # Audio should have some variation but not be just noise
            std = np.std(samples)
            if std < 10 or std > 30000:  # Too quiet or too noisy
                return False
            
            # Check for reasonable zero-crossing rate
            zero_crossings = np.sum(np.diff(np.sign(samples)) != 0)
            zcr = zero_crossings / len(samples)
            
            # Typical audio has ZCR between 0.01 and 0.5
            return 0.001 < zcr < 0.8
            
        except:
            return True  # Can't analyze, assume it might be audio
    
    def extract_audio_array(self, sample: SampleInfo) -> Optional[np.ndarray]:
        """
        Extract audio data as a numpy array suitable for playback.
        
        Args:
            sample: SampleInfo with raw_data populated
            
        Returns:
            Numpy array of float32 audio samples, normalized to [-1, 1]
        """
        if sample.raw_data is None:
            return None
        
        try:
            if sample.bit_depth == 8:
                # 8-bit unsigned
                audio = np.frombuffer(sample.raw_data, dtype=np.uint8)
                audio = (audio.astype(np.float32) - 128) / 128
            elif sample.bit_depth == 16:
                # 16-bit signed
                audio = np.frombuffer(sample.raw_data, dtype=np.int16)
                audio = audio.astype(np.float32) / 32768
            elif sample.bit_depth == 24:
                # 24-bit signed (needs special handling)
                audio = self._decode_24bit(sample.raw_data)
                audio = audio.astype(np.float32) / 8388608
            elif sample.bit_depth == 32:
                # 32-bit signed or float
                try:
                    audio = np.frombuffer(sample.raw_data, dtype=np.float32)
                    if np.max(np.abs(audio)) > 2.0:  # Probably int32
                        audio = np.frombuffer(sample.raw_data, dtype=np.int32)
                        audio = audio.astype(np.float32) / 2147483648
                except:
                    return None
            else:
                return None
            
            # Reshape for stereo if needed
            if sample.channels > 1:
                audio = audio.reshape(-1, sample.channels)
            
            return audio
            
        except Exception as e:
            if self.debug:
                print(f"Audio extraction error: {e}")
            return None
    
    def _decode_24bit(self, data: bytes) -> np.ndarray:
        """Decode 24-bit audio data."""
        num_samples = len(data) // 3
        result = np.zeros(num_samples, dtype=np.int32)
        
        for i in range(num_samples):
            b = data[i*3:(i+1)*3]
            value = b[0] | (b[1] << 8) | (b[2] << 16)
            if value & 0x800000:  # Sign extend
                value |= 0xFF000000
            result[i] = value
        
        return result


# Convenience function
def parse_ksf(data: bytes, name: str = "Unknown") -> Optional[SampleInfo]:
    """Parse a KSF file and return SampleInfo."""
    parser = KSFParser()
    return parser.parse(data, name)
