"""
Korg data type models for representing synthesizer package structures.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum, IntEnum
import struct


class SampleFormat(IntEnum):
    """Audio sample format types."""
    PCM_8BIT = 8
    PCM_16BIT = 16
    PCM_24BIT = 24
    PCM_32BIT = 32
    FLOAT_32BIT = 0x20
    COMPRESSED = 0xFF


class SampleType(Enum):
    """
    Sample usage type - determines how the sample should be played.
    
    UNKNOWN: Type not yet determined
    DRUMKIT: Percussion/one-shot - each key has a unique sound, no pitch shifting
    MELODIC: Note-based samples - few samples cover keyboard with pitch interpolation
    ONESHOT: Single sound effect, no mapping
    """
    UNKNOWN = "unknown"
    DRUMKIT = "drumkit"
    MELODIC = "melodic"
    ONESHOT = "oneshot"


class LoopMode(IntEnum):
    """Sample loop modes."""
    NO_LOOP = 0
    FORWARD = 1
    BIDIRECTIONAL = 2
    REVERSE = 3


@dataclass
class SampleInfo:
    """Information about a single audio sample."""
    name: str
    sample_rate: int = 44100
    bit_depth: int = 16
    channels: int = 1
    num_samples: int = 0
    loop_start: int = 0
    loop_end: int = 0
    loop_mode: LoopMode = LoopMode.NO_LOOP
    root_key: int = 60  # Middle C
    fine_tune: int = 0  # Cents
    data_offset: int = 0
    data_size: int = 0
    raw_data: Optional[bytes] = None
    sample_type: 'SampleType' = None  # DRUMKIT, MELODIC, or ONESHOT
    detected_note: str = ""  # For melodic samples: C, D, E, etc.
    detected_octave: int = -1  # For melodic samples: octave number
    pcm_file: str = ""  # Source PCM file name
    sample_index: int = 0  # Index within PCM file
    parent_program: str = ""  # Name of the drumkit/program this sample belongs to
    key_assignment: int = -1  # MIDI key this sample is assigned to (-1 = not assigned)
    
    def __post_init__(self):
        if self.sample_type is None:
            self.sample_type = SampleType.UNKNOWN
    
    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds."""
        if self.sample_rate > 0:
            return self.num_samples / self.sample_rate
        return 0.0
    
    @property
    def is_drumkit(self) -> bool:
        """Check if this is a drum/percussion sample."""
        return self.sample_type == SampleType.DRUMKIT
    
    @property
    def is_melodic(self) -> bool:
        """Check if this is a melodic sample with pitch info."""
        return self.sample_type == SampleType.MELODIC
    
    @property
    def type_label(self) -> str:
        """Get a display label for the sample type."""
        if self.sample_type == SampleType.DRUMKIT:
            return "🥁 Drum"
        elif self.sample_type == SampleType.MELODIC:
            note_info = f" ({self.detected_note}{self.detected_octave})" if self.detected_note else ""
            return f"🎹 Melodic{note_info}"
        elif self.sample_type == SampleType.ONESHOT:
            return "🔊 One-Shot"
        else:
            return "❓ Unknown"


@dataclass
class KeyZone:
    """Defines a keyboard zone for sample mapping."""
    low_key: int = 0
    high_key: int = 127
    low_velocity: int = 0
    high_velocity: int = 127
    sample_index: int = 0
    root_key: int = 60
    fine_tune: int = 0
    level: int = 127
    pan: int = 64  # Center


@dataclass
class Multisample:
    """A multisample consists of multiple samples mapped across the keyboard."""
    name: str
    zones: List[KeyZone] = field(default_factory=list)
    samples: List[SampleInfo] = field(default_factory=list)
    
    def get_sample_for_note(self, note: int, velocity: int = 100) -> Optional[SampleInfo]:
        """Find the appropriate sample for a given note and velocity."""
        for zone in self.zones:
            if (zone.low_key <= note <= zone.high_key and
                zone.low_velocity <= velocity <= zone.high_velocity):
                if zone.sample_index < len(self.samples):
                    return self.samples[zone.sample_index]
        return None


@dataclass
class Program:
    """A program/patch/sound definition."""
    name: str
    bank: int = 0
    number: int = 0
    category: str = ""
    multisamples: List[Multisample] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class DrumKit:
    """A drum kit with samples mapped to keys."""
    name: str
    key_samples: Dict[int, SampleInfo] = field(default_factory=dict)  # Key -> Sample
    
    def get_sample_for_key(self, key: int) -> Optional[SampleInfo]:
        """Get the sample assigned to a specific key."""
        return self.key_samples.get(key)


@dataclass
class StyleElement:
    """An element within a style (intro, variation, fill, ending)."""
    name: str
    midi_data: Optional[bytes] = None
    duration_bars: int = 1
    time_signature: tuple = (4, 4)


@dataclass
class Style:
    """A rhythm style containing multiple elements."""
    name: str
    tempo: float = 120.0
    time_signature: tuple = (4, 4)
    elements: Dict[str, StyleElement] = field(default_factory=dict)
    # Common elements: Intro1, Intro2, Var1-4, Fill1-4, Ending1, Ending2


@dataclass
class EmbeddedFile:
    """Represents a file embedded within a .SET package."""
    name: str
    file_type: str
    offset: int
    size: int
    compressed: bool = False
    data: Optional[bytes] = None


@dataclass
class SetPackage:
    """Represents a complete Korg .SET package."""
    name: str
    version: str = ""
    model: str = ""  # Pa600, Pa1000, Kronos, etc.
    embedded_files: List[EmbeddedFile] = field(default_factory=list)
    programs: List[Program] = field(default_factory=list)
    multisamples: List[Multisample] = field(default_factory=list)
    samples: List[SampleInfo] = field(default_factory=list)
    drum_kits: List[DrumKit] = field(default_factory=list)
    styles: List[Style] = field(default_factory=list)
    raw_data: Optional[bytes] = None
    
    def get_all_playable_items(self) -> List[tuple]:
        """Get a list of all items that can be played (name, type, object)."""
        items = []
        for prog in self.programs:
            items.append((prog.name, "Program", prog))
        for ms in self.multisamples:
            items.append((ms.name, "Multisample", ms))
        for sample in self.samples:
            items.append((sample.name, "Sample", sample))
        for dk in self.drum_kits:
            items.append((dk.name, "DrumKit", dk))
        for style in self.styles:
            items.append((style.name, "Style", style))
        return items


# Common Korg file signatures/magic bytes
KORG_SIGNATURES = {
    b'KORG': 'Generic Korg',
    b'SETi': 'Korg SET Package',
    b'PCG1': 'Korg PCG v1',
    b'MPC1': 'Korg MPC',
    b'KMP1': 'Korg Multisample',
    b'KSF1': 'Korg Sample File',
    b'STY1': 'Korg Style',
    b'RIFF': 'RIFF Container (may contain Korg data)',
    b'PK\x03\x04': 'ZIP Archive (some Korg packages use ZIP)',
}


def identify_file_type(data: bytes) -> str:
    """Identify a file type from its header bytes."""
    if len(data) < 4:
        return "Unknown"
    
    header = data[:4]
    
    # Check for WAV audio first (special case of RIFF)
    if header == b'RIFF' and len(data) >= 12:
        if data[8:12] == b'WAVE':
            return "WAV Audio"
        return "RIFF Container (may contain Korg data)"
    
    for sig, name in KORG_SIGNATURES.items():
        if data.startswith(sig):
            return name
    
    return "Unknown"
