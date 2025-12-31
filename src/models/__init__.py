"""Models package for Korg data types."""

from .korg_types import (
    SampleFormat,
    LoopMode,
    SampleInfo,
    KeyZone,
    Multisample,
    Program,
    DrumKit,
    StyleElement,
    Style,
    EmbeddedFile,
    SetPackage,
    KORG_SIGNATURES,
    identify_file_type,
)

__all__ = [
    'SampleFormat',
    'LoopMode', 
    'SampleInfo',
    'KeyZone',
    'Multisample',
    'Program',
    'DrumKit',
    'StyleElement',
    'Style',
    'EmbeddedFile',
    'SetPackage',
    'KORG_SIGNATURES',
    'identify_file_type',
]
