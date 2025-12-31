#!/usr/bin/env python3
"""
Korg Package Export Tool - Command Line Interface

A CLI for quick testing and analysis of Korg packages without the GUI.

Usage:
    python cli.py <package.set> [options]
    
Options:
    --info          Show package information
    --list          List all contents
    --play <index>  Play sample by index
    --export <dir>  Export all samples to directory
"""

import sys
import os
import argparse
import time

# Ensure src directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parsers.set_parser import SetParser, parse_set
from audio.player import AudioPlayer, get_player
from models.korg_types import SampleInfo, identify_file_type


def print_header():
    """Print CLI header."""
    print("=" * 60)
    print("Korg Package Export Tool - CLI")
    print("=" * 60)
    print()


def print_package_info(package):
    """Print detailed package information."""
    print(f"Package: {package.name}")
    print(f"Model: {package.model or 'Unknown'}")
    print(f"Version: {package.version or 'Unknown'}")
    print()
    
    print("Contents Summary:")
    print(f"  Embedded Files: {len(package.embedded_files)}")
    print(f"  Programs: {len(package.programs)}")
    print(f"  Multisamples: {len(package.multisamples)}")
    print(f"  Samples: {len(package.samples)}")
    print(f"  Drum Kits: {len(package.drum_kits)}")
    print(f"  Styles: {len(package.styles)}")
    print()


def list_contents(package):
    """List all package contents."""
    print("\n--- Embedded Files ---")
    for i, f in enumerate(package.embedded_files):
        print(f"  [{i:3d}] {f.name:<40} {f.file_type:<20} {f.size:>10} bytes")
    
    if package.samples:
        print("\n--- Samples ---")
        for i, s in enumerate(package.samples):
            duration = f"{s.duration_seconds:.2f}s"
            info = f"{s.sample_rate}Hz {s.bit_depth}bit {s.channels}ch"
            print(f"  [{i:3d}] {s.name:<40} {info:<25} {duration}")
    
    if package.programs:
        print("\n--- Programs ---")
        for i, p in enumerate(package.programs):
            print(f"  [{i:3d}] {p.name:<40} {p.category:<20} Bank {p.bank}")
    
    if package.multisamples:
        print("\n--- Multisamples ---")
        for i, ms in enumerate(package.multisamples):
            zones = f"{len(ms.zones)} zones"
            samples = f"{len(ms.samples)} samples"
            print(f"  [{i:3d}] {ms.name:<40} {zones:<15} {samples}")
    
    print()


def play_sample(package, index: int):
    """Play a sample by index."""
    if index < 0 or index >= len(package.samples):
        print(f"Error: Invalid sample index {index}. Valid range: 0-{len(package.samples)-1}")
        return False
    
    sample = package.samples[index]
    print(f"Playing: {sample.name}")
    print(f"  Duration: {sample.duration_seconds:.2f} seconds")
    print(f"  Sample Rate: {sample.sample_rate} Hz")
    print(f"  Press Ctrl+C to stop")
    
    player = get_player()
    
    if player.play_sample(sample):
        try:
            # Wait for playback to complete
            while player.is_playing():
                time.sleep(0.1)
        except KeyboardInterrupt:
            player.stop()
            print("\nPlayback stopped")
    else:
        print("Error: Failed to play sample")
        return False
    
    return True


def play_demo(package, max_samples: int = 5):
    """Play a demo of the first few samples."""
    if not package.samples:
        print("No samples to play")
        return
    
    player = get_player()
    
    print(f"\nPlaying demo of {min(max_samples, len(package.samples))} samples...")
    print("Press Ctrl+C to stop\n")
    
    try:
        for i, sample in enumerate(package.samples[:max_samples]):
            print(f"  [{i+1}/{min(max_samples, len(package.samples))}] {sample.name}")
            
            if player.play_sample(sample):
                # Wait for playback or max 3 seconds
                wait_time = min(sample.duration_seconds + 0.5, 3.0)
                time.sleep(wait_time)
                player.stop()
            
            time.sleep(0.3)  # Brief pause between samples
            
    except KeyboardInterrupt:
        player.stop()
        print("\nDemo stopped")


def export_samples(package, output_dir: str):
    """Export all samples as WAV files."""
    if not package.samples:
        print("No samples to export")
        return
    
    os.makedirs(output_dir, exist_ok=True)
    
    player = AudioPlayer()
    exported = 0
    errors = 0
    
    print(f"Exporting {len(package.samples)} samples to {output_dir}...")
    
    for i, sample in enumerate(package.samples):
        # Clean filename
        safe_name = "".join(c for c in sample.name if c.isalnum() or c in " -_").strip()
        if not safe_name:
            safe_name = f"sample_{i:03d}"
        
        filepath = os.path.join(output_dir, f"{safe_name}.wav")
        
        # Handle duplicates
        counter = 1
        while os.path.exists(filepath):
            filepath = os.path.join(output_dir, f"{safe_name}_{counter}.wav")
            counter += 1
        
        if player.export_to_wav(sample, filepath):
            print(f"  ✓ {sample.name} -> {os.path.basename(filepath)}")
            exported += 1
        else:
            print(f"  ✗ {sample.name} (export failed)")
            errors += 1
    
    print()
    print(f"Exported: {exported}")
    print(f"Errors: {errors}")


def analyze_file(filepath: str):
    """Analyze a file and print format information."""
    print(f"Analyzing: {filepath}")
    print()
    
    with open(filepath, 'rb') as f:
        data = f.read(1024)  # Read first 1KB
    
    file_type = identify_file_type(data)
    print(f"Detected Type: {file_type}")
    
    print(f"File Size: {os.path.getsize(filepath):,} bytes")
    
    # Print hex dump of header
    print("\nHeader (first 64 bytes):")
    for i in range(0, min(64, len(data)), 16):
        chunk = data[i:i+16]
        hex_part = ' '.join(f'{b:02X}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f"  {i:04X}: {hex_part:<48}  {ascii_part}")
    
    print()


def main():
    """CLI main entry point."""
    parser = argparse.ArgumentParser(
        description="Korg Package Export Tool - CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py package.set --info
  python cli.py package.set --list
  python cli.py package.set --play 0
  python cli.py package.set --demo
  python cli.py package.set --export ./output
  python cli.py file.ksf --analyze
        """
    )
    
    parser.add_argument('file', help='Korg package file to open')
    parser.add_argument('--info', action='store_true', help='Show package information')
    parser.add_argument('--list', action='store_true', help='List all contents')
    parser.add_argument('--play', type=int, metavar='INDEX', help='Play sample by index')
    parser.add_argument('--demo', action='store_true', help='Play demo of first samples')
    parser.add_argument('--export', metavar='DIR', help='Export all samples to directory')
    parser.add_argument('--analyze', action='store_true', help='Analyze file format')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    
    args = parser.parse_args()
    
    # Check file exists
    if not os.path.exists(args.file):
        print(f"Error: File not found: {args.file}")
        return 1
    
    print_header()
    
    # Analyze mode (doesn't require full parsing)
    if args.analyze:
        analyze_file(args.file)
        return 0
    
    # Parse the package
    print(f"Loading: {args.file}")
    
    try:
        parser_obj = SetParser()
        parser_obj.debug = args.debug
        
        package = parser_obj.parse_file(args.file)
        
        if package is None:
            print("Error: Failed to parse package")
            return 1
        
        print(f"Loaded successfully!\n")
        
    except Exception as e:
        print(f"Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1
    
    # Handle commands
    if args.info or (not args.list and args.play is None and not args.demo and not args.export):
        print_package_info(package)
    
    if args.list:
        list_contents(package)
    
    if args.play is not None:
        play_sample(package, args.play)
    
    if args.demo:
        play_demo(package)
    
    if args.export:
        export_samples(package, args.export)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
