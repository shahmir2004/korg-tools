"""
SoundFont2 (SF2) Exporter

Exports Korg samples and programs to SoundFont2 format for use in
DAWs, samplers, and other software that supports SF2.

SF2 Format Structure:
- RIFF container with 'sfbk' form type
- INFO-list: Metadata (name, copyright, etc.)
- sdta-list: Sample data (24-bit or 16-bit PCM)
- pdta-list: Preset/instrument/sample headers and generators

References:
- SoundFont 2.04 Specification
- https://github.com/FluidSynth/fluidsynth/wiki/SoundFont
"""

import struct
import io
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import IntEnum
import numpy as np


class SF2Generator(IntEnum):
    """SoundFont2 Generator types (subset of most commonly used)."""
    startAddrsOffset = 0
    endAddrsOffset = 1
    startloopAddrsOffset = 2
    endloopAddrsOffset = 3
    startAddrsCoarseOffset = 4
    modLfoToPitch = 5
    vibLfoToPitch = 6
    modEnvToPitch = 7
    initialFilterFc = 8
    initialFilterQ = 9
    modLfoToFilterFc = 10
    modEnvToFilterFc = 11
    endAddrsCoarseOffset = 12
    modLfoToVolume = 13
    pan = 17
    delayModLFO = 21
    freqModLFO = 22
    delayVibLFO = 23
    freqVibLFO = 24
    delayModEnv = 25
    attackModEnv = 26
    holdModEnv = 27
    decayModEnv = 28
    sustainModEnv = 29
    releaseModEnv = 30
    delayVolEnv = 33
    attackVolEnv = 34
    holdVolEnv = 35
    decayVolEnv = 36
    sustainVolEnv = 37
    releaseVolEnv = 38
    instrument = 41
    keyRange = 43
    velRange = 44
    startloopAddrsCoarseOffset = 45
    keynum = 46
    velocity = 47
    initialAttenuation = 48
    endloopAddrsCoarseOffset = 50
    coarseTune = 51
    fineTune = 52
    sampleID = 53
    sampleModes = 54
    scaleTuning = 56
    exclusiveClass = 57
    overridingRootKey = 58


class SF2SampleType(IntEnum):
    """SoundFont2 sample types."""
    monoSample = 1
    rightSample = 2
    leftSample = 4
    linkedSample = 8
    RomMonoSample = 0x8001
    RomRightSample = 0x8002
    RomLeftSample = 0x8004
    RomLinkedSample = 0x8008


@dataclass
class SF2Sample:
    """SoundFont2 sample header."""
    name: str
    start: int = 0
    end: int = 0
    loop_start: int = 0
    loop_end: int = 0
    sample_rate: int = 44100
    original_pitch: int = 60  # MIDI note
    pitch_correction: int = 0  # cents
    sample_link: int = 0
    sample_type: int = SF2SampleType.monoSample
    data: bytes = field(default=b'', repr=False)


@dataclass
class SF2GeneratorEntry:
    """A generator (parameter) entry."""
    generator: int
    amount: int  # Can be signed or unsigned depending on generator


@dataclass
class SF2Instrument:
    """SoundFont2 instrument."""
    name: str
    zones: List[Dict] = field(default_factory=list)
    # Each zone has: key_range, vel_range, sample_id, generators


@dataclass
class SF2Preset:
    """SoundFont2 preset."""
    name: str
    preset_num: int = 0
    bank: int = 0
    instruments: List[int] = field(default_factory=list)  # Instrument indices


class SF2Writer:
    """
    Writes SoundFont2 (.sf2) files.
    
    Usage:
        writer = SF2Writer()
        writer.set_info(name="My SoundFont", creator="Korg Tools")
        
        # Add samples
        sample_id = writer.add_sample("Piano C4", audio_data, 44100, root_key=60)
        
        # Create instrument with the sample
        inst_id = writer.add_instrument("Piano", [(0, 127, 0, 127, sample_id)])
        
        # Create preset using the instrument
        writer.add_preset("Piano", 0, 0, [inst_id])
        
        # Write to file
        writer.save("output.sf2")
    """
    
    def __init__(self):
        self.samples: List[SF2Sample] = []
        self.instruments: List[SF2Instrument] = []
        self.presets: List[SF2Preset] = []
        
        # INFO metadata
        self.info = {
            'ifil': (2, 4),  # SF2 version 2.04
            'isng': 'EMU8000',  # Sound engine
            'INAM': 'Korg Export',  # Bank name
            'ICRD': '',  # Creation date
            'IENG': '',  # Engineers
            'IPRD': '',  # Product
            'ICOP': '',  # Copyright
            'ICMT': 'Exported by Korg Tools',  # Comments
            'ISFT': 'Korg Tools SF2 Exporter',  # Software
        }
    
    def set_info(self, name: str = None, creator: str = None, 
                 copyright: str = None, comment: str = None,
                 product: str = None, creation_date: str = None):
        """Set SoundFont metadata."""
        if name:
            self.info['INAM'] = name
        if creator:
            self.info['IENG'] = creator
        if copyright:
            self.info['ICOP'] = copyright
        if comment:
            self.info['ICMT'] = comment
        if product:
            self.info['IPRD'] = product
        if creation_date:
            self.info['ICRD'] = creation_date
    
    def add_sample(self, name: str, audio_data: bytes, 
                   sample_rate: int = 44100,
                   root_key: int = 60,
                   loop_start: int = 0,
                   loop_end: int = 0,
                   pitch_correction: int = 0) -> int:
        """
        Add a sample to the SoundFont.
        
        Args:
            name: Sample name (max 20 chars)
            audio_data: 16-bit signed PCM audio data (little-endian)
            sample_rate: Sample rate in Hz
            root_key: MIDI note number for original pitch
            loop_start: Loop start in samples (0 = no loop)
            loop_end: Loop end in samples (0 = no loop)
            pitch_correction: Fine tuning in cents
            
        Returns:
            Sample index
        """
        # Truncate name to 20 chars
        name = name[:20]
        
        # Calculate sample positions
        num_samples = len(audio_data) // 2
        
        # SF2 requires 46 zero samples at the end of each sample
        padding = b'\x00' * 92  # 46 samples * 2 bytes
        
        sample = SF2Sample(
            name=name,
            start=0,  # Will be set when building
            end=num_samples,
            loop_start=loop_start if loop_start > 0 else 0,
            loop_end=loop_end if loop_end > 0 else num_samples,
            sample_rate=sample_rate,
            original_pitch=root_key,
            pitch_correction=pitch_correction,
            sample_type=SF2SampleType.monoSample,
            data=audio_data + padding
        )
        
        self.samples.append(sample)
        return len(self.samples) - 1
    
    def add_sample_from_array(self, name: str, audio_array: np.ndarray,
                               sample_rate: int = 44100,
                               root_key: int = 60,
                               loop_start: int = 0,
                               loop_end: int = 0) -> int:
        """
        Add a sample from a numpy array.
        
        Args:
            name: Sample name
            audio_array: Float32 audio array (-1.0 to 1.0) or int16 array
            sample_rate: Sample rate in Hz
            root_key: Root MIDI note
            
        Returns:
            Sample index
        """
        # Convert to 16-bit signed
        if audio_array.dtype == np.float32 or audio_array.dtype == np.float64:
            audio_int = (np.clip(audio_array, -1.0, 1.0) * 32767).astype(np.int16)
        elif audio_array.dtype == np.int16:
            audio_int = audio_array
        else:
            audio_int = audio_array.astype(np.int16)
        
        # Ensure mono
        if audio_int.ndim > 1:
            audio_int = audio_int[:, 0]
        
        return self.add_sample(name, audio_int.tobytes(), sample_rate, 
                               root_key, loop_start, loop_end)
    
    def add_instrument(self, name: str, 
                       zones: List[Tuple[int, int, int, int, int, Optional[Dict]]] = None) -> int:
        """
        Add an instrument.
        
        Args:
            name: Instrument name (max 20 chars)
            zones: List of (low_key, high_key, low_vel, high_vel, sample_id, generators)
                   generators is optional dict of SF2Generator -> value
                   
        Returns:
            Instrument index
        """
        name = name[:20]
        
        inst = SF2Instrument(name=name, zones=[])
        
        if zones:
            for zone in zones:
                if len(zone) >= 5:
                    low_key, high_key, low_vel, high_vel, sample_id = zone[:5]
                    generators = zone[5] if len(zone) > 5 else {}
                else:
                    continue
                
                inst.zones.append({
                    'key_range': (low_key, high_key),
                    'vel_range': (low_vel, high_vel),
                    'sample_id': sample_id,
                    'generators': generators or {}
                })
        
        self.instruments.append(inst)
        return len(self.instruments) - 1
    
    def add_preset(self, name: str, preset_num: int, bank: int,
                   instrument_ids: List[int]) -> int:
        """
        Add a preset.
        
        Args:
            name: Preset name (max 20 chars)
            preset_num: Preset number (0-127)
            bank: Bank number (0-127)
            instrument_ids: List of instrument indices
            
        Returns:
            Preset index
        """
        name = name[:20]
        
        preset = SF2Preset(
            name=name,
            preset_num=preset_num,
            bank=bank,
            instruments=instrument_ids
        )
        
        self.presets.append(preset)
        return len(self.presets) - 1
    
    def create_simple_soundfont(self, samples_data: List[dict]) -> None:
        """
        Create a simple SoundFont with one preset per sample.
        
        Args:
            samples_data: List of dicts with keys:
                - name: str
                - audio_data: bytes (16-bit PCM) or np.ndarray
                - sample_rate: int
                - root_key: int (optional, default 60)
                - loop_start: int (optional)
                - loop_end: int (optional)
        """
        for i, sample_info in enumerate(samples_data):
            name = sample_info.get('name', f'Sample_{i}')
            audio = sample_info.get('audio_data')
            sr = sample_info.get('sample_rate', 44100)
            root = sample_info.get('root_key', 60)
            loop_start = sample_info.get('loop_start', 0)
            loop_end = sample_info.get('loop_end', 0)
            
            # Add sample
            if isinstance(audio, np.ndarray):
                sample_id = self.add_sample_from_array(name, audio, sr, root, 
                                                        loop_start, loop_end)
            else:
                sample_id = self.add_sample(name, audio, sr, root,
                                            loop_start, loop_end)
            
            # Create instrument for this sample (full key range)
            inst_id = self.add_instrument(name, [
                (0, 127, 0, 127, sample_id, {
                    SF2Generator.overridingRootKey: root,
                })
            ])
            
            # Create preset
            self.add_preset(name, i % 128, i // 128, [inst_id])
    
    def save(self, filepath: str) -> bool:
        """
        Save the SoundFont to a file.
        
        Args:
            filepath: Output file path
            
        Returns:
            True if successful
        """
        try:
            data = self._build()
            with open(filepath, 'wb') as f:
                f.write(data)
            return True
        except Exception as e:
            print(f"SF2 save error: {e}")
            return False
    
    def _build(self) -> bytes:
        """Build the complete SF2 file."""
        # Build the three main sections
        info_chunk = self._build_info()
        sdta_chunk = self._build_sdta()
        pdta_chunk = self._build_pdta()
        
        # Combine into sfbk RIFF
        sfbk_data = info_chunk + sdta_chunk + pdta_chunk
        
        # RIFF header
        riff = b'RIFF'
        riff += struct.pack('<I', len(sfbk_data) + 4)  # +4 for 'sfbk'
        riff += b'sfbk'
        riff += sfbk_data
        
        return riff
    
    def _build_info(self) -> bytes:
        """Build the INFO-list chunk."""
        chunks = []
        
        # ifil - version (required)
        major, minor = self.info['ifil']
        chunks.append(self._make_chunk(b'ifil', struct.pack('<HH', major, minor)))
        
        # isng - sound engine
        chunks.append(self._make_chunk(b'isng', self._make_string(self.info['isng'])))
        
        # INAM - name (required)
        chunks.append(self._make_chunk(b'INAM', self._make_string(self.info['INAM'])))
        
        # Optional info
        for tag in ['ICRD', 'IENG', 'IPRD', 'ICOP', 'ICMT', 'ISFT']:
            if self.info.get(tag):
                chunks.append(self._make_chunk(tag.encode(), self._make_string(self.info[tag])))
        
        info_data = b''.join(chunks)
        return self._make_list(b'INFO', info_data)
    
    def _build_sdta(self) -> bytes:
        """Build the sdta-list chunk (sample data)."""
        # Concatenate all sample data
        sample_data = b''.join(s.data for s in self.samples)
        
        # smpl chunk
        smpl_chunk = self._make_chunk(b'smpl', sample_data)
        
        return self._make_list(b'sdta', smpl_chunk)
    
    def _build_pdta(self) -> bytes:
        """Build the pdta-list chunk (preset/instrument data)."""
        chunks = []
        
        # Calculate sample start positions
        pos = 0
        for sample in self.samples:
            sample.start = pos
            sample.end = pos + (len(sample.data) // 2) - 46  # Exclude padding
            if sample.loop_end > 0:
                sample.loop_start = pos + sample.loop_start
                sample.loop_end = pos + sample.loop_end
            else:
                sample.loop_start = pos
                sample.loop_end = sample.end
            pos += len(sample.data) // 2
        
        # phdr - preset headers
        chunks.append(self._make_chunk(b'phdr', self._build_phdr()))
        
        # pbag - preset zones
        chunks.append(self._make_chunk(b'pbag', self._build_pbag()))
        
        # pmod - preset modulators (empty for now)
        chunks.append(self._make_chunk(b'pmod', self._build_pmod()))
        
        # pgen - preset generators
        chunks.append(self._make_chunk(b'pgen', self._build_pgen()))
        
        # inst - instrument headers
        chunks.append(self._make_chunk(b'inst', self._build_inst()))
        
        # ibag - instrument zones
        chunks.append(self._make_chunk(b'ibag', self._build_ibag()))
        
        # imod - instrument modulators (empty for now)
        chunks.append(self._make_chunk(b'imod', self._build_imod()))
        
        # igen - instrument generators
        chunks.append(self._make_chunk(b'igen', self._build_igen()))
        
        # shdr - sample headers
        chunks.append(self._make_chunk(b'shdr', self._build_shdr()))
        
        pdta_data = b''.join(chunks)
        return self._make_list(b'pdta', pdta_data)
    
    def _build_phdr(self) -> bytes:
        """Build preset headers."""
        data = b''
        pbag_idx = 0
        
        for preset in self.presets:
            name = preset.name.encode('ascii', errors='replace')[:20].ljust(20, b'\x00')
            data += name
            data += struct.pack('<HHH', preset.preset_num, preset.bank, pbag_idx)
            data += struct.pack('<III', 0, 0, 0)  # library, genre, morphology
            pbag_idx += len(preset.instruments) + 1  # +1 for global zone
        
        # Terminal record
        data += b'EOP'.ljust(20, b'\x00')
        data += struct.pack('<HHH', 0, 0, pbag_idx)
        data += struct.pack('<III', 0, 0, 0)
        
        return data
    
    def _build_pbag(self) -> bytes:
        """Build preset zone bags."""
        data = b''
        gen_idx = 0
        mod_idx = 0
        
        for preset in self.presets:
            for _ in preset.instruments:
                data += struct.pack('<HH', gen_idx, mod_idx)
                gen_idx += 2  # keyRange + instrument generators
        
        # Terminal
        data += struct.pack('<HH', gen_idx, mod_idx)
        
        return data
    
    def _build_pmod(self) -> bytes:
        """Build preset modulators (empty)."""
        # Terminal modulator
        return struct.pack('<HHHHH', 0, 0, 0, 0, 0)
    
    def _build_pgen(self) -> bytes:
        """Build preset generators."""
        data = b''
        
        for preset in self.presets:
            for inst_id in preset.instruments:
                # Key range (0-127)
                data += struct.pack('<HH', SF2Generator.keyRange, 0x7F00)  # lo=0, hi=127
                # Instrument reference
                data += struct.pack('<HH', SF2Generator.instrument, inst_id)
        
        # Terminal
        data += struct.pack('<HH', 0, 0)
        
        return data
    
    def _build_inst(self) -> bytes:
        """Build instrument headers."""
        data = b''
        ibag_idx = 0
        
        for inst in self.instruments:
            name = inst.name.encode('ascii', errors='replace')[:20].ljust(20, b'\x00')
            data += name
            data += struct.pack('<H', ibag_idx)
            ibag_idx += len(inst.zones) + 1  # +1 for potential global zone
        
        # Terminal record
        data += b'EOI'.ljust(20, b'\x00')
        data += struct.pack('<H', ibag_idx)
        
        return data
    
    def _build_ibag(self) -> bytes:
        """Build instrument zone bags."""
        data = b''
        gen_idx = 0
        mod_idx = 0
        
        for inst in self.instruments:
            for zone in inst.zones:
                data += struct.pack('<HH', gen_idx, mod_idx)
                # Count generators: keyRange + velRange + sampleID + custom
                gen_idx += 3 + len(zone.get('generators', {}))
        
        # Terminal
        data += struct.pack('<HH', gen_idx, mod_idx)
        
        return data
    
    def _build_imod(self) -> bytes:
        """Build instrument modulators (empty)."""
        return struct.pack('<HHHHH', 0, 0, 0, 0, 0)
    
    def _build_igen(self) -> bytes:
        """Build instrument generators."""
        data = b''
        
        for inst in self.instruments:
            for zone in inst.zones:
                # Key range
                low_key, high_key = zone['key_range']
                data += struct.pack('<HBB', SF2Generator.keyRange, low_key, high_key)
                
                # Velocity range
                low_vel, high_vel = zone['vel_range']
                data += struct.pack('<HBB', SF2Generator.velRange, low_vel, high_vel)
                
                # Custom generators
                for gen, val in zone.get('generators', {}).items():
                    if isinstance(val, tuple):
                        data += struct.pack('<HBB', gen, val[0], val[1])
                    else:
                        data += struct.pack('<Hh', gen, val)
                
                # Sample ID (must be last generator in zone)
                data += struct.pack('<HH', SF2Generator.sampleID, zone['sample_id'])
        
        # Terminal
        data += struct.pack('<HH', 0, 0)
        
        return data
    
    def _build_shdr(self) -> bytes:
        """Build sample headers."""
        data = b''
        
        for sample in self.samples:
            name = sample.name.encode('ascii', errors='replace')[:20].ljust(20, b'\x00')
            data += name
            data += struct.pack('<IIII',
                sample.start,
                sample.end,
                sample.loop_start,
                sample.loop_end
            )
            data += struct.pack('<IbBHH',
                sample.sample_rate,
                sample.original_pitch,
                sample.pitch_correction,
                sample.sample_link,
                sample.sample_type
            )
        
        # Terminal record
        data += b'EOS'.ljust(20, b'\x00')
        data += struct.pack('<IIII', 0, 0, 0, 0)
        data += struct.pack('<IbBHH', 0, 0, 0, 0, 0)
        
        return data
    
    def _make_chunk(self, tag: bytes, data: bytes) -> bytes:
        """Create a RIFF chunk."""
        # Pad to even length
        if len(data) % 2:
            data += b'\x00'
        return tag + struct.pack('<I', len(data)) + data
    
    def _make_list(self, list_type: bytes, data: bytes) -> bytes:
        """Create a LIST chunk."""
        return b'LIST' + struct.pack('<I', len(data) + 4) + list_type + data
    
    def _make_string(self, s: str) -> bytes:
        """Create a null-terminated string, padded to even length."""
        data = s.encode('ascii', errors='replace') + b'\x00'
        if len(data) % 2:
            data += b'\x00'
        return data


def export_samples_to_sf2(samples: list, output_path: str, 
                          name: str = "Korg Export") -> bool:
    """
    Convenience function to export a list of SampleInfo objects to SF2.
    
    Args:
        samples: List of SampleInfo objects (from korg_types)
        output_path: Output .sf2 file path
        name: SoundFont name
        
    Returns:
        True if successful
    """
    writer = SF2Writer()
    writer.set_info(name=name, creator="Korg Tools")
    
    samples_data = []
    for sample in samples:
        if sample.raw_data:
            samples_data.append({
                'name': sample.name,
                'audio_data': sample.raw_data,
                'sample_rate': sample.sample_rate,
                'root_key': sample.root_key,
                'loop_start': sample.loop_start,
                'loop_end': sample.loop_end,
            })
    
    if not samples_data:
        print("No samples to export")
        return False
    
    writer.create_simple_soundfont(samples_data)
    return writer.save(output_path)
