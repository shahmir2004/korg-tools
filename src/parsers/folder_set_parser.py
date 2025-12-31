"""
Korg Pa-series Folder-based SET Parser

Pa-series synthesizers use folder-based SET packages with the following structure:
- GLOBAL/     - Global settings
- MULTISMP/   - Multisample definitions (.KMP)
- PAD/        - Pad data
- PCM/        - Audio samples (.PCM)
- PERFORM/    - Performance data
- SONGBOOK/   - Songbook data
- SOUND/      - Sound programs (.PCG)
- STYLE/      - Styles/rhythms (.STY)

This parser reads the folder structure and extracts all contents.
"""

import os
import sys
from pathlib import Path
from typing import Optional, List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.korg_types import (
    SetPackage, EmbeddedFile, SampleInfo, Program,
    Multisample, Style, StyleElement
)
from parsers.pcm_parser import PCMParser
from parsers.pcg_parser import PCGParser
from parsers.kmp_parser import KMPParser


class FolderSetParser:
    """Parser for folder-based Korg Pa-series SET packages."""
    
    # Expected folder structure
    FOLDERS = {
        'GLOBAL': 'Global settings',
        'MULTISMP': 'Multisample definitions',
        'PAD': 'Pad data',
        'PCM': 'Audio samples',
        'PERFORM': 'Performance data',
        'SONGBOOK': 'Songbook data',
        'SOUND': 'Sound programs',
        'STYLE': 'Styles/rhythms'
    }
    
    def __init__(self):
        self.debug = False
        self.pcm_parser = PCMParser()
        self.pcg_parser = PCGParser()
        self.kmp_parser = KMPParser()
    
    def parse_folder(self, folder_path: str) -> Optional[SetPackage]:
        """
        Parse a folder-based SET package.
        
        Args:
            folder_path: Path to the .SET folder
            
        Returns:
            SetPackage object or None
        """
        folder = Path(folder_path)
        
        if not folder.exists() or not folder.is_dir():
            if self.debug:
                print(f"Not a valid folder: {folder_path}")
            return None
        
        package = SetPackage(
            name=folder.name.replace('.SET', ''),
            model='Pa-series'
        )
        
        # Process each subfolder
        for subfolder_name, description in self.FOLDERS.items():
            subfolder = folder / subfolder_name
            if subfolder.exists() and subfolder.is_dir():
                self._process_subfolder(subfolder, subfolder_name, package)
        
        return package
    
    def _process_subfolder(self, subfolder: Path, folder_type: str, package: SetPackage):
        """Process a subfolder based on its type."""
        
        if folder_type == 'PCM':
            self._process_pcm_folder(subfolder, package)
        elif folder_type == 'SOUND':
            self._process_sound_folder(subfolder, package)
        elif folder_type == 'MULTISMP':
            self._process_multismp_folder(subfolder, package)
        elif folder_type == 'STYLE':
            self._process_style_folder(subfolder, package)
        else:
            # Just catalog the files
            self._catalog_folder(subfolder, folder_type, package)
    
    def _process_pcm_folder(self, folder: Path, package: SetPackage):
        """Process PCM sample files."""
        for file_path in sorted(folder.glob('*.PCM')):
            if self.debug:
                print(f"Processing PCM: {file_path.name}")
            
            # Add as embedded file
            with open(file_path, 'rb') as f:
                data = f.read()
            
            embedded = EmbeddedFile(
                name=file_path.name,
                file_type='PCM Audio Container',
                offset=0,
                size=len(data),
                data=data
            )
            package.embedded_files.append(embedded)
            
            # Parse samples from PCM
            samples = self.pcm_parser.parse(data, file_path.name)
            package.samples.extend(samples)
    
    def _process_sound_folder(self, folder: Path, package: SetPackage):
        """Process sound/program files."""
        for file_path in sorted(folder.glob('*.PCG')):
            if self.debug:
                print(f"Processing PCG: {file_path.name}")
            
            with open(file_path, 'rb') as f:
                data = f.read()
            
            embedded = EmbeddedFile(
                name=file_path.name,
                file_type='Program Collection',
                offset=0,
                size=len(data),
                data=data
            )
            package.embedded_files.append(embedded)
            
            # Parse programs
            programs = self.pcg_parser.parse(data, file_path.name)
            package.programs.extend(programs)
    
    def _process_multismp_folder(self, folder: Path, package: SetPackage):
        """Process multisample definition files."""
        for file_path in sorted(folder.glob('*.KMP')):
            if self.debug:
                print(f"Processing KMP: {file_path.name}")
            
            with open(file_path, 'rb') as f:
                data = f.read()
            
            embedded = EmbeddedFile(
                name=file_path.name,
                file_type='Multisample Map',
                offset=0,
                size=len(data),
                data=data
            )
            package.embedded_files.append(embedded)
            
            # Parse multisample
            ms = self.kmp_parser.parse(data, file_path.name)
            if ms:
                package.multisamples.append(ms)
    
    def _process_style_folder(self, folder: Path, package: SetPackage):
        """Process style files."""
        for file_path in sorted(folder.glob('*.STY')):
            if self.debug:
                print(f"Processing STY: {file_path.name}")
            
            with open(file_path, 'rb') as f:
                data = f.read()
            
            embedded = EmbeddedFile(
                name=file_path.name,
                file_type='Style/Rhythm',
                offset=0,
                size=len(data),
                data=data
            )
            package.embedded_files.append(embedded)
            
            # Create basic style entry
            style = Style(
                name=file_path.stem,
                tempo=120.0
            )
            package.styles.append(style)
    
    def _catalog_folder(self, folder: Path, folder_type: str, package: SetPackage):
        """Catalog files in a folder without deep parsing."""
        for file_path in folder.iterdir():
            if file_path.is_file():
                try:
                    size = file_path.stat().st_size
                    
                    embedded = EmbeddedFile(
                        name=f"{folder_type}/{file_path.name}",
                        file_type=folder_type,
                        offset=0,
                        size=size,
                        data=None  # Don't load data for unknown files
                    )
                    package.embedded_files.append(embedded)
                except Exception as e:
                    if self.debug:
                        print(f"Error cataloging {file_path}: {e}")
    
    def get_summary(self, package: SetPackage) -> Dict:
        """Get a summary of the parsed package."""
        return {
            'name': package.name,
            'model': package.model,
            'embedded_files': len(package.embedded_files),
            'samples': len(package.samples),
            'programs': len(package.programs),
            'multisamples': len(package.multisamples),
            'styles': len(package.styles),
            'file_types': list(set(f.file_type for f in package.embedded_files))
        }


def parse_folder_set(folder_path: str) -> Optional[SetPackage]:
    """Convenience function to parse a folder-based SET."""
    parser = FolderSetParser()
    return parser.parse_folder(folder_path)
