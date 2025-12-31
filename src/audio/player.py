"""
Audio playback engine for Korg samples.

Uses pygame for cross-platform audio playback with support for:
- Playing raw sample data
- Pitch shifting for different notes
- Loop support
- Volume and pan control
"""

import os
import sys
import io
import wave
import struct
import threading
import time
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum

import numpy as np

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.korg_types import SampleInfo, Multisample, LoopMode


class PlayerState(Enum):
    """Audio player states."""
    STOPPED = 0
    PLAYING = 1
    PAUSED = 2


@dataclass
class PlaybackConfig:
    """Configuration for audio playback."""
    sample_rate: int = 44100
    channels: int = 2
    buffer_size: int = 2048
    volume: float = 0.8  # 0.0 to 1.0


class AudioPlayer:
    """
    Cross-platform audio player for Korg samples.
    
    Uses pygame.mixer for playback with fallback to simpler methods.
    """
    
    def __init__(self, config: Optional[PlaybackConfig] = None):
        self.config = config or PlaybackConfig()
        self.state = PlayerState.STOPPED
        self.current_sample: Optional[SampleInfo] = None
        self._pygame_initialized = False
        self._current_channel = None
        self._on_playback_complete: Optional[Callable] = None
        self._playback_thread: Optional[threading.Thread] = None
        
        self._init_audio()
    
    def _init_audio(self):
        """Initialize the audio system."""
        try:
            import pygame
            import pygame.mixer
            
            pygame.mixer.pre_init(
                frequency=self.config.sample_rate,
                size=-16,  # 16-bit signed
                channels=self.config.channels,
                buffer=self.config.buffer_size
            )
            pygame.mixer.init()
            self._pygame_initialized = True
            
        except ImportError:
            print("Warning: pygame not available. Audio playback disabled.")
            self._pygame_initialized = False
        except Exception as e:
            print(f"Warning: Could not initialize audio: {e}")
            self._pygame_initialized = False
    
    def play_sample(self, sample: SampleInfo, 
                    note: int = None,
                    velocity: int = 100,
                    loop: bool = None) -> bool:
        """
        Play a sample.
        
        Args:
            sample: SampleInfo object with raw_data
            note: MIDI note number (for pitch shifting). None = play at original pitch
            velocity: MIDI velocity (0-127) for volume scaling
            loop: Override loop setting. None = use sample's loop mode
            
        Returns:
            True if playback started successfully
        """
        if not self._pygame_initialized:
            print("Audio not initialized")
            return False
        
        if sample.raw_data is None:
            print("No sample data available")
            return False
        
        try:
            import pygame
            
            # Stop any current playback
            self.stop()
            
            # Convert sample to pygame-compatible format
            sound = self._create_pygame_sound(sample, note, velocity)
            
            if sound is None:
                return False
            
            # Determine if we should loop
            should_loop = loop if loop is not None else (sample.loop_mode != LoopMode.NO_LOOP)
            loops = -1 if should_loop else 0
            
            # Play the sound
            self._current_channel = sound.play(loops=loops)
            self.state = PlayerState.PLAYING
            self.current_sample = sample
            
            # Start monitoring thread for playback completion
            if not should_loop:
                self._start_completion_monitor()
            
            return True
            
        except Exception as e:
            print(f"Playback error: {e}")
            return False
    
    def _create_pygame_sound(self, sample: SampleInfo, 
                              note: Optional[int],
                              velocity: int) -> Optional['pygame.mixer.Sound']:
        """Create a pygame Sound object from sample data."""
        import pygame
        
        # Extract audio data as numpy array
        audio = self._extract_audio(sample)
        
        if audio is None:
            return None
        
        # Apply pitch shifting if needed
        if note is not None and note != sample.root_key:
            audio = self._pitch_shift(audio, sample.root_key, note, sample.sample_rate)
        
        # Apply velocity (volume)
        volume = (velocity / 127.0) * self.config.volume
        audio = audio * volume
        
        # Ensure stereo output
        if audio.ndim == 1:
            audio = np.column_stack([audio, audio])
        elif audio.shape[1] == 1:
            audio = np.column_stack([audio[:, 0], audio[:, 0]])
        
        # Resample to output sample rate if needed
        if sample.sample_rate != self.config.sample_rate:
            audio = self._resample(audio, sample.sample_rate, self.config.sample_rate)
        
        # Convert to 16-bit integer
        audio = np.clip(audio, -1.0, 1.0)
        audio_int = (audio * 32767).astype(np.int16)
        
        # Create pygame Sound
        sound = pygame.mixer.Sound(buffer=audio_int.tobytes())
        
        return sound
    
    def _extract_audio(self, sample: SampleInfo) -> Optional[np.ndarray]:
        """Extract audio data from sample as float32 numpy array."""
        if sample.raw_data is None:
            return None
        
        try:
            if sample.bit_depth == 8:
                audio = np.frombuffer(sample.raw_data, dtype=np.uint8)
                audio = (audio.astype(np.float32) - 128) / 128
            elif sample.bit_depth == 16:
                audio = np.frombuffer(sample.raw_data, dtype=np.int16)
                audio = audio.astype(np.float32) / 32768
            elif sample.bit_depth == 24:
                audio = self._decode_24bit(sample.raw_data)
            elif sample.bit_depth == 32:
                audio = np.frombuffer(sample.raw_data, dtype=np.float32)
                if np.max(np.abs(audio)) > 2.0:
                    audio = np.frombuffer(sample.raw_data, dtype=np.int32)
                    audio = audio.astype(np.float32) / 2147483648
            else:
                # Default to 16-bit
                audio = np.frombuffer(sample.raw_data, dtype=np.int16)
                audio = audio.astype(np.float32) / 32768
            
            # Reshape for channels
            if sample.channels > 1 and len(audio) >= sample.channels:
                audio = audio.reshape(-1, sample.channels)
            
            return audio
            
        except Exception as e:
            print(f"Audio extraction error: {e}")
            return None
    
    def _decode_24bit(self, data: bytes) -> np.ndarray:
        """Decode 24-bit audio data."""
        num_samples = len(data) // 3
        result = np.zeros(num_samples, dtype=np.float32)
        
        for i in range(num_samples):
            b = data[i*3:(i+1)*3]
            value = b[0] | (b[1] << 8) | (b[2] << 16)
            if value & 0x800000:
                value -= 0x1000000
            result[i] = value / 8388608.0
        
        return result
    
    def _pitch_shift(self, audio: np.ndarray, 
                     root_note: int, 
                     target_note: int,
                     sample_rate: int) -> np.ndarray:
        """
        Simple pitch shifting by resampling.
        
        Note: This is a basic implementation. For better quality,
        consider using librosa or other DSP libraries.
        """
        # Calculate pitch ratio
        semitone_diff = target_note - root_note
        pitch_ratio = 2 ** (semitone_diff / 12.0)
        
        if pitch_ratio == 1.0:
            return audio
        
        # Simple resampling for pitch shift
        original_length = len(audio)
        new_length = int(original_length / pitch_ratio)
        
        if new_length <= 0:
            return audio
        
        # Linear interpolation for resampling
        if audio.ndim == 1:
            indices = np.linspace(0, original_length - 1, new_length)
            return np.interp(indices, np.arange(original_length), audio)
        else:
            result = np.zeros((new_length, audio.shape[1]), dtype=np.float32)
            indices = np.linspace(0, original_length - 1, new_length)
            for ch in range(audio.shape[1]):
                result[:, ch] = np.interp(indices, np.arange(original_length), audio[:, ch])
            return result
    
    def _resample(self, audio: np.ndarray, 
                  from_rate: int, 
                  to_rate: int) -> np.ndarray:
        """Resample audio to a different sample rate."""
        if from_rate == to_rate:
            return audio
        
        ratio = to_rate / from_rate
        original_length = len(audio)
        new_length = int(original_length * ratio)
        
        if new_length <= 0:
            return audio
        
        if audio.ndim == 1:
            indices = np.linspace(0, original_length - 1, new_length)
            return np.interp(indices, np.arange(original_length), audio)
        else:
            result = np.zeros((new_length, audio.shape[1]), dtype=np.float32)
            indices = np.linspace(0, original_length - 1, new_length)
            for ch in range(audio.shape[1]):
                result[:, ch] = np.interp(indices, np.arange(original_length), audio[:, ch])
            return result
    
    def _start_completion_monitor(self):
        """Start a thread to monitor when playback completes."""
        def monitor():
            import pygame
            while self.state == PlayerState.PLAYING:
                if self._current_channel is None or not self._current_channel.get_busy():
                    self.state = PlayerState.STOPPED
                    if self._on_playback_complete:
                        self._on_playback_complete()
                    break
                time.sleep(0.1)
        
        self._playback_thread = threading.Thread(target=monitor, daemon=True)
        self._playback_thread.start()
    
    def stop(self):
        """Stop playback."""
        if self._pygame_initialized:
            import pygame.mixer
            pygame.mixer.stop()
        
        self.state = PlayerState.STOPPED
        self.current_sample = None
    
    def pause(self):
        """Pause playback."""
        if self._pygame_initialized and self.state == PlayerState.PLAYING:
            import pygame.mixer
            pygame.mixer.pause()
            self.state = PlayerState.PAUSED
    
    def resume(self):
        """Resume paused playback."""
        if self._pygame_initialized and self.state == PlayerState.PAUSED:
            import pygame.mixer
            pygame.mixer.unpause()
            self.state = PlayerState.PLAYING
    
    def set_volume(self, volume: float):
        """Set master volume (0.0 to 1.0)."""
        self.config.volume = max(0.0, min(1.0, volume))
        
        if self._pygame_initialized and self._current_channel:
            self._current_channel.set_volume(self.config.volume)
    
    def get_volume(self) -> float:
        """Get current volume."""
        return self.config.volume
    
    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        return self.state == PlayerState.PLAYING
    
    def on_playback_complete(self, callback: Callable):
        """Set callback for when playback completes."""
        self._on_playback_complete = callback
    
    def play_note(self, multisample: Multisample, 
                  note: int, 
                  velocity: int = 100) -> bool:
        """
        Play a note from a multisample.
        
        Args:
            multisample: Multisample containing samples and key zones
            note: MIDI note number to play
            velocity: MIDI velocity
            
        Returns:
            True if playback started
        """
        sample = multisample.get_sample_for_note(note, velocity)
        
        if sample is None:
            # Fall back to first sample if available
            if multisample.samples:
                sample = multisample.samples[0]
            else:
                print(f"No sample found for note {note}")
                return False
        
        return self.play_sample(sample, note=note, velocity=velocity)
    
    def export_to_wav(self, sample: SampleInfo, filepath: str) -> bool:
        """
        Export a sample to WAV file.
        
        Args:
            sample: Sample to export
            filepath: Output file path
            
        Returns:
            True if export successful
        """
        if sample.raw_data is None:
            return False
        
        try:
            audio = self._extract_audio(sample)
            if audio is None:
                return False
            
            # Ensure stereo
            if audio.ndim == 1:
                audio = np.column_stack([audio, audio])
            
            # Convert to 16-bit
            audio_int = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
            
            # Write WAV file
            with wave.open(filepath, 'w') as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(sample.sample_rate)
                wf.writeframes(audio_int.tobytes())
            
            return True
            
        except Exception as e:
            print(f"WAV export error: {e}")
            return False
    
    def cleanup(self):
        """Clean up audio resources."""
        self.stop()
        if self._pygame_initialized:
            import pygame.mixer
            pygame.mixer.quit()
            self._pygame_initialized = False


# Singleton player instance
_player: Optional[AudioPlayer] = None


def get_player() -> AudioPlayer:
    """Get the global audio player instance."""
    global _player
    if _player is None:
        _player = AudioPlayer()
    return _player


def play_sample(sample: SampleInfo, **kwargs) -> bool:
    """Convenience function to play a sample."""
    return get_player().play_sample(sample, **kwargs)


def stop_playback():
    """Convenience function to stop playback."""
    get_player().stop()
