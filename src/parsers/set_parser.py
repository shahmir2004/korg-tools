"""
Korg SET Package Parser

SET files are container packages that bundle multiple Korg files together.
They can contain PCG, KMP, KSF, STY, and other file types.

This parser handles various SET formats used by different Korg models.
"""

import struct
import zlib
import zipfile
import io
from typing import Optional, List, Tuple, Dict
from pathlib import Path
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.korg_types import (
    SetPackage, EmbeddedFile, SampleInfo, Program, 
    Multisample, identify_file_type
)
from parsers.ksf_parser import KSFParser
from parsers.kmp_parser import KMPParser
from parsers.pcg_parser import PCGParser


class SetParser:
    """Parser for Korg SET package files."""
    
    # Known SET file signatures
    SIGNATURES = {
        b'KORG': 'Korg Generic',
        b'SETi': 'Korg SET Index',
        b'SET1': 'Korg SET v1',
        b'PK\x03\x04': 'ZIP Archive',
        b'PK\x05\x06': 'ZIP Archive (empty)',
    }
    
    # File extensions to look for
    KNOWN_EXTENSIONS = {
        '.pcg': 'Program/Combination',
        '.kmp': 'Multisample',
        '.ksf': 'Sample',
        '.sty': 'Style',
        '.ksc': 'Script Collection',
        '.mid': 'MIDI',
        '.wav': 'Audio',
        '.pad': 'Pad Data',
        '.set': 'Sub-package',
    }
    
    def __init__(self):
        self.debug = False
        self.ksf_parser = KSFParser()
        self.kmp_parser = KMPParser()
        self.pcg_parser = PCGParser()
        self._folder_parser = None  # Lazy load to avoid circular imports
    
    @property
    def folder_parser(self):
        """Lazy load folder parser."""
        if self._folder_parser is None:
            from parsers.folder_set_parser import FolderSetParser
            self._folder_parser = FolderSetParser()
        return self._folder_parser
    
    def parse_file(self, filepath: str) -> Optional[SetPackage]:
        """
        Parse a SET file or folder from disk.
        
        Args:
            filepath: Path to the SET file or folder
            
        Returns:
            SetPackage object or None if parsing fails
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        # Check if it's a folder-based SET package (Pa-series)
        if path.is_dir():
            return self.folder_parser.parse_folder(str(path))
        
        with open(filepath, 'rb') as f:
            data = f.read()
        
        package = self.parse(data, path.stem)
        if package:
            package.name = path.stem
        
        return package
    
    def parse(self, data: bytes, name: str = "Unknown") -> Optional[SetPackage]:
        """
        Parse SET package data.
        
        Args:
            data: Raw bytes of the SET file
            name: Name to assign to the package
            
        Returns:
            SetPackage object or None if parsing fails
        """
        if len(data) < 16:
            return None
        
        package = SetPackage(name=name, raw_data=data)
        header = data[:4]
        
        # Detect format and parse accordingly
        if header == b'PK\x03\x04':
            # ZIP-based package
            self._parse_zip_package(data, package)
        elif header in [b'KORG', b'SETi', b'SET1']:
            # Native Korg format
            self._parse_korg_package(data, package)
        else:
            # Unknown format - try multiple strategies
            self._parse_unknown_package(data, package)
        
        # Post-process: link samples to multisamples
        self._link_samples(package)
        
        return package
    
    def _parse_zip_package(self, data: bytes, package: SetPackage):
        """Parse a ZIP-based SET package."""
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    
                    file_data = zf.read(info.filename)
                    ext = Path(info.filename).suffix.lower()
                    
                    embedded = EmbeddedFile(
                        name=info.filename,
                        file_type=self.KNOWN_EXTENSIONS.get(ext, 'Unknown'),
                        offset=0,
                        size=len(file_data),
                        compressed=True,
                        data=file_data
                    )
                    package.embedded_files.append(embedded)
                    
                    # Parse based on extension
                    self._parse_embedded_file(embedded, package)
                    
        except zipfile.BadZipFile:
            if self.debug:
                print("Invalid ZIP format, trying other methods")
            self._parse_unknown_package(data, package)
    
    def _parse_korg_package(self, data: bytes, package: SetPackage):
        """Parse native Korg SET format."""
        header = data[:4]
        
        if header == b'KORG':
            self._parse_korg_generic(data, package)
        elif header in [b'SETi', b'SET1']:
            self._parse_set_indexed(data, package)
    
    def _parse_korg_generic(self, data: bytes, package: SetPackage):
        """
        Parse KORG generic container format.
        
        Structure typically:
        - 0x00: "KORG" magic
        - 0x04: File type / version
        - 0x08: Total size or flags
        - 0x0C: File table offset or count
        - Variable: File table entries
        - Variable: File data
        """
        try:
            # Read header info
            if len(data) < 16:
                return
            
            file_type = data[4:8]
            package.model = file_type.decode('ascii', errors='ignore').strip('\x00')
            
            # Look for file table
            file_count = 0
            table_offset = 16
            
            # Try different header layouts
            for offset in [12, 16, 20]:
                if offset + 4 <= len(data):
                    count = struct.unpack('<I', data[offset:offset+4])[0]
                    if 0 < count < 1000:
                        file_count = count
                        table_offset = offset + 4
                        break
            
            if file_count > 0:
                self._parse_file_table(data, table_offset, file_count, package)
            else:
                # No file table found, scan for embedded files
                self._scan_for_embedded_files(data, package)
                
        except Exception as e:
            if self.debug:
                print(f"KORG generic parse error: {e}")
    
    def _parse_set_indexed(self, data: bytes, package: SetPackage):
        """
        Parse SETi/SET1 indexed format.
        
        This format has a clear file index structure.
        """
        try:
            # Skip signature
            pos = 4
            
            # Version
            version = struct.unpack('<I', data[pos:pos+4])[0]
            package.version = str(version)
            pos += 4
            
            # File count
            file_count = struct.unpack('<I', data[pos:pos+4])[0]
            pos += 4
            
            if file_count > 1000:
                # Probably wrong, scan instead
                self._scan_for_embedded_files(data, package)
                return
            
            # Parse file entries
            for i in range(file_count):
                if pos + 64 > len(data):
                    break
                
                # Entry structure (typical):
                # - Name (32 bytes, null-padded)
                # - Offset (4 bytes)
                # - Size (4 bytes)
                # - Flags (4 bytes)
                # - Reserved (20 bytes)
                
                name = data[pos:pos+32].split(b'\x00')[0].decode('ascii', errors='ignore')
                offset = struct.unpack('<I', data[pos+32:pos+36])[0]
                size = struct.unpack('<I', data[pos+36:pos+40])[0]
                flags = struct.unpack('<I', data[pos+40:pos+44])[0]
                
                pos += 64
                
                if offset > 0 and size > 0 and offset + size <= len(data):
                    file_data = data[offset:offset+size]
                    ext = Path(name).suffix.lower() if name else ''
                    
                    embedded = EmbeddedFile(
                        name=name or f"file_{i:03d}",
                        file_type=self.KNOWN_EXTENSIONS.get(ext, identify_file_type(file_data)),
                        offset=offset,
                        size=size,
                        compressed=(flags & 1) != 0,
                        data=file_data
                    )
                    
                    # Decompress if needed
                    if embedded.compressed:
                        try:
                            embedded.data = zlib.decompress(file_data)
                            embedded.size = len(embedded.data)
                        except:
                            pass  # Keep original data
                    
                    package.embedded_files.append(embedded)
                    self._parse_embedded_file(embedded, package)
                    
        except Exception as e:
            if self.debug:
                print(f"SET indexed parse error: {e}")
    
    def _parse_file_table(self, data: bytes, offset: int, count: int, package: SetPackage):
        """Parse a file table at the given offset."""
        pos = offset
        
        # Try different entry sizes
        for entry_size in [32, 48, 64, 128]:
            if pos + count * entry_size > len(data):
                continue
            
            valid_entries = 0
            
            for i in range(count):
                entry_pos = pos + i * entry_size
                entry = data[entry_pos:entry_pos+entry_size]
                
                # Extract file info
                try:
                    name_bytes = entry[:24].split(b'\x00')[0]
                    name = name_bytes.decode('ascii', errors='ignore')
                    
                    if entry_size >= 32:
                        file_offset = struct.unpack('<I', entry[24:28])[0]
                        file_size = struct.unpack('<I', entry[28:32])[0]
                        
                        if file_offset > 0 and file_size > 0:
                            if file_offset + file_size <= len(data):
                                valid_entries += 1
                                
                                file_data = data[file_offset:file_offset+file_size]
                                ext = Path(name).suffix.lower() if name else ''
                                
                                embedded = EmbeddedFile(
                                    name=name or f"file_{i:03d}",
                                    file_type=self.KNOWN_EXTENSIONS.get(ext, identify_file_type(file_data)),
                                    offset=file_offset,
                                    size=file_size,
                                    data=file_data
                                )
                                package.embedded_files.append(embedded)
                                self._parse_embedded_file(embedded, package)
                except:
                    continue
            
            if valid_entries > 0:
                break
    
    def _scan_for_embedded_files(self, data: bytes, package: SetPackage):
        """Scan data for embedded file signatures."""
        # Look for known file signatures
        signatures = [
            (b'KSF1', 'ksf'),
            (b'KMP1', 'kmp'),
            (b'PCG1', 'pcg'),
            (b'KORG', 'korg'),
            (b'RIFF', 'riff'),
            (b'STY1', 'sty'),
        ]
        
        found_positions = []
        
        for sig, ext in signatures:
            pos = 0
            while True:
                idx = data.find(sig, pos)
                if idx < 0:
                    break
                found_positions.append((idx, sig, ext))
                pos = idx + 1
        
        # Sort by position
        found_positions.sort(key=lambda x: x[0])
        
        # Extract files between positions
        for i, (pos, sig, ext) in enumerate(found_positions):
            if i + 1 < len(found_positions):
                next_pos = found_positions[i + 1][0]
            else:
                next_pos = len(data)
            
            file_data = data[pos:next_pos]
            
            embedded = EmbeddedFile(
                name=f"embedded_{i:03d}.{ext}",
                file_type=identify_file_type(file_data),
                offset=pos,
                size=len(file_data),
                data=file_data
            )
            package.embedded_files.append(embedded)
            self._parse_embedded_file(embedded, package)
    
    def _parse_unknown_package(self, data: bytes, package: SetPackage):
        """Parse unknown format by scanning for recognizable content."""
        # First, check if the entire file might be a single format
        file_type = identify_file_type(data)
        
        if 'Sample' in file_type or 'WAV' in file_type:
            # Treat entire file as sample
            sample = self.ksf_parser.parse(data, package.name)
            if sample:
                package.samples.append(sample)
            return
        
        if 'PCG' in file_type:
            programs = self.pcg_parser.parse(data, package.name)
            package.programs.extend(programs)
            return
        
        # Scan for embedded files
        self._scan_for_embedded_files(data, package)
        
        # If nothing found, try to treat as raw sample data
        if not package.embedded_files and not package.samples:
            sample = self.ksf_parser.parse(data, package.name)
            if sample:
                package.samples.append(sample)
    
    def _parse_embedded_file(self, embedded: EmbeddedFile, package: SetPackage):
        """Parse an embedded file and add results to package."""
        if not embedded.data:
            return
        
        ext = Path(embedded.name).suffix.lower()
        
        if ext == '.ksf' or 'Sample' in embedded.file_type:
            sample = self.ksf_parser.parse(embedded.data, embedded.name)
            if sample:
                package.samples.append(sample)
        
        elif ext == '.kmp' or 'Multisample' in embedded.file_type:
            ms = self.kmp_parser.parse(embedded.data, embedded.name)
            if ms:
                package.multisamples.append(ms)
        
        elif ext == '.pcg' or 'PCG' in embedded.file_type:
            programs = self.pcg_parser.parse(embedded.data, embedded.name)
            package.programs.extend(programs)
        
        elif ext == '.wav' or 'WAV' in embedded.file_type:
            sample = self.ksf_parser.parse(embedded.data, embedded.name)
            if sample:
                package.samples.append(sample)
    
    def _link_samples(self, package: SetPackage):
        """Link samples to multisamples based on indices."""
        for ms in package.multisamples:
            for zone in ms.zones:
                if zone.sample_index < len(package.samples):
                    if zone.sample_index < len(ms.samples):
                        continue
                    ms.samples.append(package.samples[zone.sample_index])
    
    def get_package_summary(self, package: SetPackage) -> Dict[str, any]:
        """Get a summary of package contents."""
        return {
            'name': package.name,
            'model': package.model,
            'version': package.version,
            'embedded_files': len(package.embedded_files),
            'programs': len(package.programs),
            'multisamples': len(package.multisamples),
            'samples': len(package.samples),
            'drum_kits': len(package.drum_kits),
            'styles': len(package.styles),
            'file_types': list(set(f.file_type for f in package.embedded_files)),
        }


def parse_set(filepath: str) -> Optional[SetPackage]:
    """Convenience function to parse a SET file."""
    parser = SetParser()
    return parser.parse_file(filepath)


def parse_set_data(data: bytes, name: str = "Unknown") -> Optional[SetPackage]:
    """Convenience function to parse SET data."""
    parser = SetParser()
    return parser.parse(data, name)
