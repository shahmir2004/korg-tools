"""Test script for sample classification."""

import sys
sys.path.insert(0, 'src')

from parsers.pcm_parser import PCMParser
from parsers.sample_classifier import classify_all_samples, get_sample_type_summary

# Parse samples from a few PCM files
parser = PCMParser()
parser.debug = False

all_samples = []
for i in [1, 2, 3, 24, 42, 55]:
    filepath = f'samples/Stefanv22021.SET/PCM/RAM{i:02d}.PCM'
    samples = parser.parse_file(filepath)
    for s in samples:
        s.pcm_file = f'RAM{i:02d}.PCM'
    all_samples.extend(samples)

print(f'Loaded {len(all_samples)} samples from 6 PCM files')

# Classify them
classify_all_samples(all_samples)

# Summary
summary = get_sample_type_summary(all_samples)
print(f'\nType Summary:')
print(f'  Total: {summary["total"]}')
print(f'  Drumkit: {summary["drumkit"]}')
print(f'  Melodic: {summary["melodic"]}')
print(f'  Unknown: {summary["unknown"]}')

# Show samples with their types
print(f'\nSamples:')
for s in all_samples:
    note_info = f'({s.detected_note}{s.detected_octave})' if s.detected_note else ''
    print(f'  {s.pcm_file}:{s.sample_index} {s.name:<25} -> {s.sample_type.value:<10} {note_info}')
