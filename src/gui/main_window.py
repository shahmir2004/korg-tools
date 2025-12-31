"""
Main GUI Window for Korg Package Export Tool

Provides a user-friendly interface for:
- Opening and browsing Korg packages
- Playing sample demos
- Viewing package structure and metadata
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, List, Dict, Any
from pathlib import Path
import threading

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.korg_types import SetPackage, SampleInfo, Program, Multisample, EmbeddedFile
from parsers.set_parser import SetParser
from audio.player import AudioPlayer, PlayerState


class MainWindow:
    """Main application window."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Korg Package Export Tool - Demo Version")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        
        # State
        self.current_package: Optional[SetPackage] = None
        self.parser = SetParser()
        self.player = AudioPlayer()
        self.selected_item = None
        
        # Set up the UI
        self._create_menu()
        self._create_toolbar()
        self._create_main_layout()
        self._create_statusbar()
        
        # Bind events
        self._bind_events()
        
        # Configure styling
        self._configure_styles()
    
    def _configure_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        
        # Try to use a modern theme
        available_themes = style.theme_names()
        for theme in ['clam', 'alt', 'vista', 'xpnative']:
            if theme in available_themes:
                style.theme_use(theme)
                break
        
        # Custom styles
        style.configure('Title.TLabel', font=('Segoe UI', 12, 'bold'))
        style.configure('Info.TLabel', font=('Segoe UI', 9))
        style.configure('Playing.TButton', background='#4CAF50')
    
    def _create_menu(self):
        """Create the menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Package...", command=self._open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Open Folder...", command=self._open_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Export Sample as WAV...", command=self._export_wav, state='disabled')
        file_menu.add_command(label="Export All to SF2...", command=self._export_sf2, state='disabled')
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit, accelerator="Alt+F4")
        self.file_menu = file_menu
        
        # Playback menu
        playback_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Playback", menu=playback_menu)
        playback_menu.add_command(label="Play", command=self._play_selected, accelerator="Space")
        playback_menu.add_command(label="Stop", command=self._stop_playback, accelerator="Escape")
        playback_menu.add_separator()
        playback_menu.add_command(label="Play All (Demo)", command=self._play_all_demo)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Package Info", command=self._show_package_info)
        view_menu.add_command(label="Hex View", command=self._show_hex_view)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)
        help_menu.add_command(label="Korg Format Notes", command=self._show_format_notes)
    
    def _create_toolbar(self):
        """Create the toolbar."""
        toolbar = ttk.Frame(self.root, padding=5)
        toolbar.pack(fill=tk.X, side=tk.TOP)
        
        # Open button
        self.btn_open = ttk.Button(toolbar, text="📁 Open", command=self._open_file)
        self.btn_open.pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Playback controls
        self.btn_play = ttk.Button(toolbar, text="▶ Play", command=self._play_selected, state='disabled')
        self.btn_play.pack(side=tk.LEFT, padx=2)
        
        self.btn_stop = ttk.Button(toolbar, text="⏹ Stop", command=self._stop_playback, state='disabled')
        self.btn_stop.pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # Volume control
        ttk.Label(toolbar, text="Volume:").pack(side=tk.LEFT, padx=2)
        self.volume_var = tk.DoubleVar(value=0.8)
        self.volume_slider = ttk.Scale(
            toolbar, from_=0, to=1, 
            variable=self.volume_var,
            command=self._on_volume_change,
            length=100
        )
        self.volume_slider.pack(side=tk.LEFT, padx=2)
        
        # Search
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Label(toolbar, text="Search:").pack(side=tk.LEFT, padx=2)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self._on_search)
        self.search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=20)
        self.search_entry.pack(side=tk.LEFT, padx=2)
    
    def _create_main_layout(self):
        """Create the main content layout."""
        # Main paned window
        self.main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel - Package tree
        self._create_tree_panel()
        
        # Right panel - Details and waveform
        self._create_details_panel()
    
    def _create_tree_panel(self):
        """Create the package tree view panel."""
        left_frame = ttk.Frame(self.main_pane)
        self.main_pane.add(left_frame, weight=1)
        
        # Header
        header = ttk.Frame(left_frame)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Package Contents", style='Title.TLabel').pack(side=tk.LEFT, pady=5)
        
        # Treeview with scrollbar
        tree_frame = ttk.Frame(left_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.tree = ttk.Treeview(tree_frame, selectmode='browse', show='tree headings')
        self.tree['columns'] = ('type', 'info')
        self.tree.heading('#0', text='Name', anchor='w')
        self.tree.heading('type', text='Type', anchor='w')
        self.tree.heading('info', text='Info', anchor='w')
        self.tree.column('#0', width=200, minwidth=100)
        self.tree.column('type', width=100, minwidth=60)
        self.tree.column('info', width=150, minwidth=80)
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)
        
        # Bind selection event
        self.tree.bind('<<TreeviewSelect>>', self._on_tree_select)
        self.tree.bind('<Double-1>', self._on_tree_double_click)
    
    def _create_details_panel(self):
        """Create the details panel."""
        right_frame = ttk.Frame(self.main_pane)
        self.main_pane.add(right_frame, weight=1)
        
        # Details notebook
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Info tab
        info_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(info_frame, text="Details")
        
        self.info_text = tk.Text(info_frame, wrap=tk.WORD, font=('Consolas', 10))
        info_scroll = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=info_scroll.set)
        self.info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        info_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.info_text.insert('1.0', 'Open a Korg package to view details...')
        self.info_text.config(state='disabled')
        
        # Waveform tab
        waveform_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(waveform_frame, text="Waveform")
        
        self.waveform_canvas = tk.Canvas(waveform_frame, bg='#1a1a2e', height=200)
        self.waveform_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Keyboard tab (for testing notes)
        keyboard_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(keyboard_frame, text="Keyboard")
        
        self._create_virtual_keyboard(keyboard_frame)
        
        # Hex view tab
        hex_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(hex_frame, text="Hex View")
        
        self.hex_text = tk.Text(hex_frame, wrap=tk.NONE, font=('Consolas', 9))
        hex_scroll_y = ttk.Scrollbar(hex_frame, orient=tk.VERTICAL, command=self.hex_text.yview)
        hex_scroll_x = ttk.Scrollbar(hex_frame, orient=tk.HORIZONTAL, command=self.hex_text.xview)
        self.hex_text.configure(yscrollcommand=hex_scroll_y.set, xscrollcommand=hex_scroll_x.set)
        self.hex_text.grid(row=0, column=0, sticky='nsew')
        hex_scroll_y.grid(row=0, column=1, sticky='ns')
        hex_scroll_x.grid(row=1, column=0, sticky='ew')
        hex_frame.rowconfigure(0, weight=1)
        hex_frame.columnconfigure(0, weight=1)
    
    def _create_virtual_keyboard(self, parent: ttk.Frame):
        """Create a virtual keyboard for testing notes."""
        ttk.Label(parent, text="Click keys to play notes (requires a sample selected)", 
                  style='Info.TLabel').pack(pady=5)
        
        keyboard_canvas = tk.Canvas(parent, height=120, bg='#2d2d2d')
        keyboard_canvas.pack(fill=tk.X, pady=10)
        
        # Draw piano keys
        white_keys = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
        key_width = 40
        key_height = 100
        
        self.keyboard_keys = {}
        
        # Starting at middle C (note 60)
        base_note = 48  # C3
        
        for octave in range(2):
            for i, key in enumerate(white_keys):
                note = base_note + octave * 12 + [0, 2, 4, 5, 7, 9, 11][i]
                x = (octave * 7 + i) * key_width
                
                key_id = keyboard_canvas.create_rectangle(
                    x, 0, x + key_width - 2, key_height,
                    fill='white', outline='#333'
                )
                self.keyboard_keys[key_id] = note
                
                keyboard_canvas.tag_bind(key_id, '<Button-1>', 
                    lambda e, n=note: self._play_keyboard_note(n))
        
        # Black keys
        black_key_pattern = [1, 1, 0, 1, 1, 1, 0]  # C#, D#, skip, F#, G#, A#, skip
        black_notes = [1, 3, -1, 6, 8, 10, -1]
        
        for octave in range(2):
            for i, has_black in enumerate(black_key_pattern):
                if has_black and black_notes[i] >= 0:
                    note = base_note + octave * 12 + black_notes[i]
                    x = (octave * 7 + i) * key_width + key_width * 0.7
                    
                    key_id = keyboard_canvas.create_rectangle(
                        x, 0, x + key_width * 0.6, key_height * 0.6,
                        fill='#222', outline='#111'
                    )
                    self.keyboard_keys[key_id] = note
                    
                    keyboard_canvas.tag_bind(key_id, '<Button-1>',
                        lambda e, n=note: self._play_keyboard_note(n))
        
        self.keyboard_canvas = keyboard_canvas
    
    def _create_statusbar(self):
        """Create the status bar."""
        self.statusbar = ttk.Frame(self.root)
        self.statusbar.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_label = ttk.Label(self.statusbar, text="Ready", style='Info.TLabel')
        self.status_label.pack(side=tk.LEFT, padx=5, pady=2)
        
        self.playback_label = ttk.Label(self.statusbar, text="", style='Info.TLabel')
        self.playback_label.pack(side=tk.RIGHT, padx=5, pady=2)
    
    def _bind_events(self):
        """Bind keyboard shortcuts and events."""
        self.root.bind('<Control-o>', lambda e: self._open_file())
        self.root.bind('<space>', lambda e: self._play_selected())
        self.root.bind('<Escape>', lambda e: self._stop_playback())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _open_file(self):
        """Open a Korg package file."""
        filetypes = [
            ("Korg Packages", "*.set *.SET"),
            ("Korg PCG", "*.pcg *.PCG"),
            ("Korg Samples", "*.ksf *.KSF"),
            ("All Korg Files", "*.set *.pcg *.ksf *.kmp *.sty"),
            ("All Files", "*.*")
        ]
        
        filepath = filedialog.askopenfilename(
            title="Open Korg Package",
            filetypes=filetypes
        )
        
        if filepath:
            self._load_package(filepath)
    
    def _open_folder(self):
        """Open a folder containing Korg files."""
        folderpath = filedialog.askdirectory(title="Select Folder with Korg Files")
        
        if folderpath:
            self._scan_folder(folderpath)
    
    def _load_package(self, filepath: str):
        """Load a package file."""
        self._set_status(f"Loading: {filepath}")
        
        def load_thread():
            try:
                package = self.parser.parse_file(filepath)
                self.root.after(0, lambda: self._on_package_loaded(package))
            except Exception as e:
                self.root.after(0, lambda: self._on_load_error(str(e)))
        
        thread = threading.Thread(target=load_thread)
        thread.start()
    
    def _on_package_loaded(self, package: Optional[SetPackage]):
        """Handle successful package load."""
        if package is None:
            self._on_load_error("Failed to parse package")
            return
        
        self.current_package = package
        self._populate_tree()
        self._update_package_info()
        self._enable_controls()
        
        summary = self.parser.get_package_summary(package)
        self._set_status(f"Loaded: {package.name} - {summary['samples']} samples, "
                        f"{summary['programs']} programs")
    
    def _on_load_error(self, error: str):
        """Handle package load error."""
        self._set_status(f"Error: {error}")
        messagebox.showerror("Load Error", f"Failed to load package:\n{error}")
    
    def _populate_tree(self):
        """Populate the tree view with package contents."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if not self.current_package:
            return
        
        pkg = self.current_package
        
        # Add root node
        root = self.tree.insert('', 'end', text=pkg.name, values=('Package', pkg.model or 'Unknown'))
        
        # Embedded files
        if pkg.embedded_files:
            files_node = self.tree.insert(root, 'end', text='Files', 
                                          values=('', f'{len(pkg.embedded_files)} files'))
            for f in pkg.embedded_files:
                self.tree.insert(files_node, 'end', text=f.name,
                               values=(f.file_type, f'{f.size} bytes'),
                               tags=('embedded',))
        
        # Samples
        if pkg.samples:
            samples_node = self.tree.insert(root, 'end', text='Samples',
                                            values=('', f'{len(pkg.samples)} samples'))
            for i, sample in enumerate(pkg.samples):
                info = f"{sample.sample_rate}Hz, {sample.bit_depth}bit"
                self.tree.insert(samples_node, 'end', text=sample.name,
                               values=('Sample', info),
                               tags=('sample', f'sample_{i}'))
        
        # Programs
        if pkg.programs:
            prog_node = self.tree.insert(root, 'end', text='Programs',
                                         values=('', f'{len(pkg.programs)} programs'))
            for i, prog in enumerate(pkg.programs):
                self.tree.insert(prog_node, 'end', text=prog.name,
                               values=('Program', prog.category),
                               tags=('program', f'program_{i}'))
        
        # Multisamples
        if pkg.multisamples:
            ms_node = self.tree.insert(root, 'end', text='Multisamples',
                                       values=('', f'{len(pkg.multisamples)} multisamples'))
            for i, ms in enumerate(pkg.multisamples):
                info = f"{len(ms.zones)} zones, {len(ms.samples)} samples"
                self.tree.insert(ms_node, 'end', text=ms.name,
                               values=('Multisample', info),
                               tags=('multisample', f'multisample_{i}'))
        
        # Expand root
        self.tree.item(root, open=True)
    
    def _on_tree_select(self, event):
        """Handle tree selection change."""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = selection[0]
        tags = self.tree.item(item, 'tags')
        
        self.selected_item = None
        
        for tag in tags:
            if tag.startswith('sample_'):
                idx = int(tag.split('_')[1])
                if self.current_package and idx < len(self.current_package.samples):
                    self.selected_item = self.current_package.samples[idx]
                    self._show_sample_details(self.selected_item)
                    self._draw_waveform(self.selected_item)
                break
            elif tag.startswith('program_'):
                idx = int(tag.split('_')[1])
                if self.current_package and idx < len(self.current_package.programs):
                    self.selected_item = self.current_package.programs[idx]
                    self._show_program_details(self.selected_item)
                break
            elif tag.startswith('multisample_'):
                idx = int(tag.split('_')[1])
                if self.current_package and idx < len(self.current_package.multisamples):
                    self.selected_item = self.current_package.multisamples[idx]
                    self._show_multisample_details(self.selected_item)
                break
            elif tag == 'embedded':
                # Show embedded file details
                name = self.tree.item(item, 'text')
                for f in self.current_package.embedded_files:
                    if f.name == name:
                        self.selected_item = f
                        self._show_embedded_details(f)
                        break
        
        # Enable/disable play button
        if isinstance(self.selected_item, (SampleInfo, Multisample)):
            self.btn_play.config(state='normal')
        else:
            self.btn_play.config(state='disabled')
    
    def _on_tree_double_click(self, event):
        """Handle double-click on tree item."""
        if isinstance(self.selected_item, SampleInfo):
            self._play_selected()
    
    def _show_sample_details(self, sample: SampleInfo):
        """Show sample details in the info panel."""
        info = f"""Sample: {sample.name}
{'=' * 50}

Audio Properties:
  Sample Rate: {sample.sample_rate} Hz
  Bit Depth: {sample.bit_depth}-bit
  Channels: {sample.channels}
  Duration: {sample.duration_seconds:.3f} seconds
  Samples: {sample.num_samples}

Loop Settings:
  Mode: {sample.loop_mode.name}
  Start: {sample.loop_start}
  End: {sample.loop_end}

MIDI Mapping:
  Root Key: {sample.root_key} ({self._note_name(sample.root_key)})
  Fine Tune: {sample.fine_tune} cents

Data:
  Offset: {sample.data_offset}
  Size: {sample.data_size} bytes
  Has Data: {'Yes' if sample.raw_data else 'No'}
"""
        self._set_info_text(info)
    
    def _show_program_details(self, program: Program):
        """Show program details in the info panel."""
        info = f"""Program: {program.name}
{'=' * 50}

Bank: {program.bank}
Number: {program.number}
Category: {program.category}

Multisamples: {len(program.multisamples)}

Parameters:
"""
        for key, value in program.parameters.items():
            info += f"  {key}: {value}\n"
        
        self._set_info_text(info)
    
    def _show_multisample_details(self, ms: Multisample):
        """Show multisample details in the info panel."""
        info = f"""Multisample: {ms.name}
{'=' * 50}

Zones: {len(ms.zones)}
Samples: {len(ms.samples)}

Key Zones:
"""
        for i, zone in enumerate(ms.zones):
            info += f"""
  Zone {i+1}:
    Keys: {zone.low_key} - {zone.high_key} ({self._note_name(zone.low_key)} - {self._note_name(zone.high_key)})
    Velocity: {zone.low_velocity} - {zone.high_velocity}
    Root Key: {zone.root_key} ({self._note_name(zone.root_key)})
    Sample Index: {zone.sample_index}
"""
        self._set_info_text(info)
    
    def _show_embedded_details(self, f: EmbeddedFile):
        """Show embedded file details."""
        info = f"""Embedded File: {f.name}
{'=' * 50}

Type: {f.file_type}
Size: {f.size} bytes
Offset: {f.offset}
Compressed: {'Yes' if f.compressed else 'No'}
"""
        self._set_info_text(info)
        
        # Show hex view
        if f.data:
            self._show_hex_data(f.data[:1024])
    
    def _show_hex_data(self, data: bytes):
        """Display hex dump of data."""
        lines = []
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            hex_part = ' '.join(f'{b:02X}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            lines.append(f'{i:08X}  {hex_part:<48}  {ascii_part}')
        
        self.hex_text.config(state='normal')
        self.hex_text.delete('1.0', tk.END)
        self.hex_text.insert('1.0', '\n'.join(lines))
        self.hex_text.config(state='disabled')
    
    def _draw_waveform(self, sample: SampleInfo):
        """Draw the waveform for a sample."""
        canvas = self.waveform_canvas
        canvas.delete('all')
        
        if not sample.raw_data:
            canvas.create_text(
                canvas.winfo_width() // 2,
                canvas.winfo_height() // 2,
                text="No waveform data",
                fill='white'
            )
            return
        
        try:
            import numpy as np
            
            # Get audio data
            if sample.bit_depth == 16:
                audio = np.frombuffer(sample.raw_data, dtype=np.int16)
                audio = audio.astype(np.float32) / 32768
            elif sample.bit_depth == 8:
                audio = np.frombuffer(sample.raw_data, dtype=np.uint8)
                audio = (audio.astype(np.float32) - 128) / 128
            else:
                audio = np.frombuffer(sample.raw_data, dtype=np.int16)
                audio = audio.astype(np.float32) / 32768
            
            # Get canvas dimensions
            width = canvas.winfo_width() or 400
            height = canvas.winfo_height() or 200
            
            # Downsample for display
            if len(audio) > width * 2:
                step = len(audio) // width
                audio = audio[::step]
            
            # Draw waveform
            center = height // 2
            points = []
            
            for i, sample_val in enumerate(audio):
                x = int(i * width / len(audio))
                y = int(center - sample_val * center * 0.8)
                points.extend([x, y])
            
            if len(points) >= 4:
                canvas.create_line(points, fill='#00ff88', width=1)
            
            # Draw center line
            canvas.create_line(0, center, width, center, fill='#444444', dash=(2, 4))
            
            # Draw loop points if applicable
            if sample.loop_mode != LoopMode.NO_LOOP and sample.num_samples > 0:
                loop_start_x = int(sample.loop_start / sample.num_samples * width)
                loop_end_x = int(sample.loop_end / sample.num_samples * width)
                
                canvas.create_line(loop_start_x, 0, loop_start_x, height, fill='#ff6600', width=2)
                canvas.create_line(loop_end_x, 0, loop_end_x, height, fill='#ff6600', width=2)
                
        except Exception as e:
            canvas.create_text(
                canvas.winfo_width() // 2,
                canvas.winfo_height() // 2,
                text=f"Waveform error: {e}",
                fill='red'
            )
    
    def _play_selected(self):
        """Play the currently selected item."""
        if self.selected_item is None:
            return
        
        if isinstance(self.selected_item, SampleInfo):
            self._play_sample(self.selected_item)
        elif isinstance(self.selected_item, Multisample):
            # Play first sample or middle C
            if self.selected_item.samples:
                self._play_sample(self.selected_item.samples[0])
    
    def _play_sample(self, sample: SampleInfo):
        """Play a sample."""
        if self.player.play_sample(sample):
            self._set_status(f"Playing: {sample.name}")
            self.btn_stop.config(state='normal')
            self.playback_label.config(text=f"▶ {sample.name}")
            
            # Set completion callback
            self.player.on_playback_complete(self._on_playback_complete)
        else:
            self._set_status(f"Failed to play: {sample.name}")
    
    def _play_keyboard_note(self, note: int):
        """Play a note from the virtual keyboard."""
        if not self.selected_item:
            return
        
        if isinstance(self.selected_item, SampleInfo):
            self.player.play_sample(self.selected_item, note=note)
            self._set_status(f"Playing note: {self._note_name(note)}")
        elif isinstance(self.selected_item, Multisample):
            self.player.play_note(self.selected_item, note)
            self._set_status(f"Playing note: {self._note_name(note)}")
    
    def _stop_playback(self):
        """Stop audio playback."""
        self.player.stop()
        self.playback_label.config(text="")
        self._set_status("Playback stopped")
    
    def _on_playback_complete(self):
        """Handle playback completion."""
        self.root.after(0, lambda: self.playback_label.config(text=""))
    
    def _on_volume_change(self, value):
        """Handle volume slider change."""
        self.player.set_volume(float(value))
    
    def _play_all_demo(self):
        """Play all samples as a demo."""
        if not self.current_package or not self.current_package.samples:
            return
        
        self._set_status("Playing demo...")
        
        # Play each sample briefly
        def demo_thread():
            import time
            for sample in self.current_package.samples[:10]:  # Limit to first 10
                if not self.player.is_playing():
                    break
                self.root.after(0, lambda s=sample: self._play_sample(s))
                time.sleep(min(sample.duration_seconds + 0.5, 3))
            self.root.after(0, lambda: self._set_status("Demo complete"))
        
        thread = threading.Thread(target=demo_thread, daemon=True)
        thread.start()
    
    def _export_wav(self):
        """Export selected sample as WAV."""
        if not isinstance(self.selected_item, SampleInfo):
            messagebox.showwarning("Export", "Please select a sample to export")
            return
        
        filepath = filedialog.asksaveasfilename(
            title="Export as WAV",
            defaultextension=".wav",
            filetypes=[("WAV Audio", "*.wav")],
            initialfile=f"{self.selected_item.name}.wav"
        )
        
        if filepath:
            if self.player.export_to_wav(self.selected_item, filepath):
                self._set_status(f"Exported: {filepath}")
                messagebox.showinfo("Export", f"Sample exported successfully:\n{filepath}")
            else:
                self._set_status("Export failed")
                messagebox.showerror("Export", "Failed to export sample")
    
    def _export_sf2(self):
        """Export all samples to SoundFont2 format."""
        if not self.current_package or not self.current_package.samples:
            messagebox.showwarning("Export", "No samples loaded to export")
            return
        
        # Get output filename
        default_name = f"{self.current_package.name}.sf2"
        filepath = filedialog.asksaveasfilename(
            title="Export as SoundFont2",
            defaultextension=".sf2",
            filetypes=[("SoundFont2", "*.sf2"), ("All Files", "*.*")],
            initialfile=default_name
        )
        
        if not filepath:
            return
        
        self._set_status("Exporting to SF2...")
        
        def export_thread():
            try:
                from export.sf2_writer import export_samples_to_sf2
                
                samples = self.current_package.samples
                success = export_samples_to_sf2(
                    samples, 
                    filepath, 
                    name=self.current_package.name
                )
                
                if success:
                    self.root.after(0, lambda: self._on_sf2_export_complete(filepath, len(samples)))
                else:
                    self.root.after(0, lambda: self._on_sf2_export_error("Export failed"))
            except Exception as e:
                self.root.after(0, lambda: self._on_sf2_export_error(str(e)))
        
        thread = threading.Thread(target=export_thread, daemon=True)
        thread.start()
    
    def _on_sf2_export_complete(self, filepath: str, sample_count: int):
        """Handle successful SF2 export."""
        self._set_status(f"Exported {sample_count} samples to SF2")
        messagebox.showinfo(
            "Export Complete", 
            f"Successfully exported {sample_count} samples to:\n{filepath}"
        )
    
    def _on_sf2_export_error(self, error: str):
        """Handle SF2 export error."""
        self._set_status("SF2 export failed")
        messagebox.showerror("Export Error", f"Failed to export SF2:\n{error}")
    
    def _scan_folder(self, folderpath: str):
        """Scan a folder for Korg files or load as SET package."""
        # Check if folder itself is a SET package (Pa-series folder-based format)
        folder_name = os.path.basename(folderpath)
        if folder_name.upper().endswith('.SET'):
            # Treat as folder-based SET package
            self._load_package(folderpath)
            return
        
        # Check for Pa-series folder structure (PCM, SOUND, STYLE folders)
        expected_subfolders = {'PCM', 'SOUND', 'STYLE', 'MULTISMP'}
        actual_subfolders = set()
        for item in os.listdir(folderpath):
            item_path = os.path.join(folderpath, item)
            if os.path.isdir(item_path):
                actual_subfolders.add(item.upper())
        
        if actual_subfolders & expected_subfolders:
            # This looks like a Pa-series SET folder
            self._load_package(folderpath)
            return
        
        # Otherwise, scan for individual Korg files
        extensions = {'.set', '.pcg', '.ksf', '.kmp', '.sty'}
        files = []
        
        for root, dirs, filenames in os.walk(folderpath):
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext in extensions:
                    files.append(os.path.join(root, filename))
        
        if files:
            self._set_status(f"Found {len(files)} Korg files")
            # Load the first one as an example
            if files:
                self._load_package(files[0])
        else:
            self._set_status("No Korg files found in folder")
            messagebox.showinfo("Scan", "No Korg files found in the selected folder")
    
    def _update_package_info(self):
        """Update the general package info display."""
        if not self.current_package:
            return
        
        summary = self.parser.get_package_summary(self.current_package)
        
        info = f"""Package: {summary['name']}
{'=' * 50}

Model/Version: {summary['model'] or 'Unknown'} {summary['version']}

Contents:
  Embedded Files: {summary['embedded_files']}
  Programs: {summary['programs']}
  Multisamples: {summary['multisamples']}
  Samples: {summary['samples']}
  Drum Kits: {summary['drum_kits']}
  Styles: {summary['styles']}

File Types Found:
  {', '.join(summary['file_types']) if summary['file_types'] else 'None'}
"""
        self._set_info_text(info)
    
    def _enable_controls(self):
        """Enable controls after loading a package."""
        self.file_menu.entryconfig("Export Sample as WAV...", state='normal')
        self.file_menu.entryconfig("Export All to SF2...", state='normal')
        self.btn_stop.config(state='normal')
    
    def _set_info_text(self, text: str):
        """Set the info panel text."""
        self.info_text.config(state='normal')
        self.info_text.delete('1.0', tk.END)
        self.info_text.insert('1.0', text)
        self.info_text.config(state='disabled')
    
    def _set_status(self, message: str):
        """Set status bar message."""
        self.status_label.config(text=message)
    
    def _on_search(self, *args):
        """Handle search input."""
        query = self.search_var.get().lower()
        if not query or not self.current_package:
            return
        
        # Search through tree items
        for item in self.tree.get_children():
            self._search_tree_item(item, query)
    
    def _search_tree_item(self, item, query):
        """Recursively search tree items."""
        text = self.tree.item(item, 'text').lower()
        
        if query in text:
            self.tree.see(item)
            self.tree.selection_set(item)
            return True
        
        for child in self.tree.get_children(item):
            if self._search_tree_item(child, query):
                self.tree.item(item, open=True)
                return True
        
        return False
    
    def _show_package_info(self):
        """Show package info dialog."""
        if not self.current_package:
            messagebox.showinfo("Info", "No package loaded")
            return
        
        self.notebook.select(0)  # Switch to details tab
        self._update_package_info()
    
    def _show_hex_view(self):
        """Show hex view tab."""
        self.notebook.select(3)  # Hex view tab
    
    def _show_about(self):
        """Show about dialog."""
        about_text = """Korg Package Export Tool
Demo Version - Milestone 1

A Python application for reading and playing
Korg synthesizer package files.

Features:
• Open .SET, .PCG, .KSF, .KMP files
• Browse package contents
• Play sample demos
• View waveforms
• Export to WAV

© 2024 - MIT License"""
        
        messagebox.showinfo("About", about_text)
    
    def _show_format_notes(self):
        """Show notes about Korg file formats."""
        notes = """Korg File Format Notes
======================

.SET Files:
- Container format for Korg packages
- May use ZIP compression
- Contains multiple file types

.PCG Files:
- Program/Combination/Global data
- Sound definitions and presets

.KSF Files:
- Korg Sample File
- Contains raw audio data
- Typically 16-bit PCM

.KMP Files:
- Korg Multisample Parameter
- Defines keyboard mapping
- Contains zone definitions

.STY Files:
- Style/Rhythm data
- Contains MIDI patterns
- (Support planned for future)

Note: File formats vary between Korg models.
Some packages may not be fully supported."""
        
        # Show in a new window
        win = tk.Toplevel(self.root)
        win.title("Format Notes")
        win.geometry("400x400")
        
        text = tk.Text(win, wrap=tk.WORD, font=('Consolas', 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text.insert('1.0', notes)
        text.config(state='disabled')
    
    def _note_name(self, note: int) -> str:
        """Convert MIDI note number to note name."""
        notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        octave = (note // 12) - 1
        name = notes[note % 12]
        return f"{name}{octave}"
    
    def _on_close(self):
        """Handle window close."""
        self.player.cleanup()
        self.root.destroy()


def create_gui() -> tk.Tk:
    """Create and return the main GUI window."""
    root = tk.Tk()
    app = MainWindow(root)
    return root


if __name__ == "__main__":
    root = create_gui()
    root.mainloop()
