# ZpaqTreeView
Allows browsing and extraction of a zpaqfranz archive in a tree/hierarchical file structure view.

It can be a pain to browse through the contents of a zpaq as they are output in an unwieldy list. As such, I've cleaned up the list output by putting it into a tree structure and allowing the browsing and extraction of folders and files.

## Quickstart
<ins>**Put zpaqfranz.exe in the same folder as the Python file or enter it when prompted**</ins>
### (Recommended) tree_tui.py
Fancy command line, Textual
1. `python tree_tui.py "C:\myzpaq.zpaq"`
2. Use arrowkeys and spacebar to select and expand nodes
3. Use 'x' to extract folder or file. Enter destination path when asked.
### zpaqtreeview.py 
Basic, command line only
1. `python zpaqtreeview.py`
2. Follow prompts for usage
### zpaq_fileexplorer.py
Integration with Windows file explorer, WinFsp.
1. `python zpaq_fileexplorer.py X: -z "C:\myzpaq.zpaq"`
2. Navigate to X: (or whatver you set it to) using File Explorer or any other file viewer.
3. Files may be viewed and extracted as normal.

## Full Descriptions
zpaqtreeview.py
- Uses treelib package
- All other files are built upon the base functionality implemented here
- Simple command line interface using user input to select folders/files and extract them
- Will only show the latest version of files (uses zpaqfranz's l/list command with -longpath)
- Works well on Windows, untested on Linux

![8hWindowsTerminal_bCl0LRJtvg](https://github.com/EpicGazel/ZpaqTreeView/assets/20029624/bd2969bd-512f-488a-8871-23e97925c802)


tree_tui.py
- Built upon zpaqtreeview.py as base (requires treelib)
- Requires Texual package
- Uses Texual's DirectoryTree for fancy command line interface
- Marginally slower than zpaqtreeview.py as tree is converted from treelib tree to Texual tree
- **Much more usable** than base zpaqtreeview.py
- Works well on Windows, untested on Linux

![8iWindowsTerminal_xScntS6ksn](https://github.com/EpicGazel/ZpaqTreeView/assets/20029624/5d6395a3-9b8f-4c7f-8311-7a28e6eb3fa6)


zpaq_filexplorer.py
- Built upon zpaqtreeview.py as base (requires treelib)
- Requires WinFsp to be installed (Windows only)
- Uses WinFsp (FUSE for Windows) to directly interface with the file system
  - Can be interacted with directly, indentical to any other folder.
  - Creates a temporary in memory file system 
- Performance is significantly worse than other options
- Works poorly on Windows, almost definitely does not work on Linux

## Demo (Audio)
https://github.com/EpicGazel/ZpaqTreeView/assets/20029624/0b1d5811-77bd-4b1c-bc9a-244ff78ac370
