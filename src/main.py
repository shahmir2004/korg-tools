#!/usr/bin/env python3
"""
Korg Package Export Tool - Main Entry Point

A Python application with GUI for reading, analyzing, and playing
instruments/samples from Korg synthesizer packages.

Usage:
    python main.py                  # Start GUI
    python main.py package.set      # Open package and start GUI
"""

import sys
import os

# Ensure src directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    """Main entry point for the application."""
    # Check for file argument
    package_file = None
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ['-h', '--help']:
            print(__doc__)
            print("Options:")
            print("  -h, --help     Show this help message")
            print("  --cli          Run in CLI mode (no GUI)")
            print("  <file.set>     Open the specified package file")
            return 0
        elif arg == '--cli':
            # Run CLI version
            from cli import main as cli_main
            return cli_main()
        elif os.path.exists(arg):
            package_file = arg
    
    # Start GUI
    try:
        from gui.main_window import create_gui
        
        root = create_gui()
        
        # If a file was specified, load it after GUI starts
        if package_file:
            root.after(100, lambda: _load_initial_file(root, package_file))
        
        root.mainloop()
        return 0
        
    except ImportError as e:
        print(f"Error: Missing dependency - {e}")
        print("Please install requirements: pip install -r requirements.txt")
        return 1
    except Exception as e:
        print(f"Error starting application: {e}")
        return 1


def _load_initial_file(root, filepath):
    """Load a file after GUI initialization."""
    # Find the MainWindow instance
    for child in root.children.values():
        if hasattr(child, 'master'):
            continue
    
    # Access the main window through the root's internal state
    # The create_gui function creates MainWindow which stores itself
    if hasattr(root, 'children'):
        # Get the main app from the root
        import gui.main_window as main_module
        for obj in dir(main_module):
            item = getattr(main_module, obj)
            if isinstance(item, main_module.MainWindow):
                item._load_package(filepath)
                return
    
    # Alternative: Just trigger the load through the window
    print(f"Note: Please use File > Open to load {filepath}")


if __name__ == "__main__":
    sys.exit(main())
