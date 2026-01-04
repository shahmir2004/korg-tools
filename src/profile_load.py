"""Profile loading performance."""
import os
import time
from parsers.pcm_parser import PCMParser
from parsers.sample_classifier_fast import classify_all_samples_fast, group_samples_fast

parser = PCMParser()
pcm_folder = r'..\samples\SetKorgPa1000Full18.01.2019.SET\PCM'

# Parse all samples
start = time.time()
all_samples = []
for pcm_file in sorted(os.listdir(pcm_folder)):
    if pcm_file.endswith('.PCM'):
        filepath = os.path.join(pcm_folder, pcm_file)
        with open(filepath, 'rb') as f:
            data = f.read()
        samples = parser.parse(data, pcm_file)
        for s in samples:
            s.pcm_file = pcm_file  # Track source
        all_samples.extend(samples)
parse_time = time.time() - start
print(f'Parsing: {parse_time:.2f}s ({len(all_samples)} samples)')

# Classification
start = time.time()
classify_all_samples_fast(all_samples)
classify_time = time.time() - start
print(f'Classification: {classify_time:.2f}s')

# Grouping
start = time.time()
groups = group_samples_fast(all_samples)
group_time = time.time() - start
print(f'Grouping: {group_time:.2f}s ({len(groups)} groups)')

# Show type breakdown
from models.korg_types import SampleType
drumkit = sum(1 for s in all_samples if s.sample_type == SampleType.DRUMKIT)
melodic = sum(1 for s in all_samples if s.sample_type == SampleType.MELODIC)
unknown = sum(1 for s in all_samples if s.sample_type == SampleType.UNKNOWN)
print(f'Types: drumkit={drumkit}, melodic={melodic}, unknown={unknown}')
