import os
import sys
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from datetime import datetime

class FileSystemHandler:
    """
    Handles file system interactions. 
    This module is separate to allow for easier testing and future 
    search/indexing features.
    """
    def list_directory(self, path):
        """Returns a list of items in the directory with metadata."""
        items = []
        try:
            # os.scandir is faster and more efficient than os.listdir
            with os.scandir(path) as it:
                for entry in it:
                    # Basic metadata collection
                    stats = entry.stat()
                    size = self._format_size(stats.st_size) if entry.is_file() else "--"
                    mod_time = datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M')
                    
                    item = {
                        "name": entry.name,
                        "path": entry.path,
                        "is_dir": entry.is_dir(),
                        "size": size,
                        "modified": mod_time
                    }
                    items.append(item)
        except PermissionError:
            return None # Signal access denied
        
        # Sort directories first, then files
        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        return items

    def _format_size(self, size):
        # Helper to make file sizes human-readable
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

class ExplorerUI(ttk.Frame):
    """
    Handles the Visual Presentation.
    Uses ttk widgets for native macOS appearance.
    """
    def __init__(self, parent, logic_handler):
        super().__init__(parent)
        self.logic = logic_handler
        self.current_path = os.path.expanduser("~") # Start at user home on Mac
        self.parent = parent
        
        self._setup_layout()
        self._bind_events()
        self.refresh_view()

    def _setup_layout(self):
        # Configure layout weights for resizing
        self.pack(fill=tk.BOTH, expand=True)
        
        # 1. Address Bar (Navigation)
        nav_frame = ttk.Frame(self, padding=(10, 10))
        nav_frame.pack(fill=tk.X)
        
        self.path_var = tk.StringVar()
        entry = ttk.Entry(nav_frame, textvariable=self.path_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        up_btn = ttk.Button(nav_frame, text="Up", command=self.go_up)
        up_btn.pack(side=tk.RIGHT)

        # 2. File List (Treeview)
        # Treeview allows for the columns view typical in Finder
        self.tree_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        self.tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("size", "modified")
        self.tree = ttk.Treeview(self.tree_frame, columns=columns, selectmode="browse")
        
        # Define Headings
        self.tree.heading("#0", text="Name", anchor=tk.W)
        self.tree.heading("size", text="Size", anchor=tk.E)
        self.tree.heading("modified", text="Date Modified", anchor=tk.W)
        
        # Define Columns
        self.tree.column("#0", stretch=True, width=300)
        self.tree.column("size", width=100, anchor=tk.E)
        self.tree.column("modified", width=150)

        # Scrollbar (Native macOS feel)
        scrollbar = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _bind_events(self):
        # Mouse Interaction
        self.tree.bind("<Double-1>", self.on_open)
        
        # Keyboard Interaction
        # On macOS, Return is often used to rename, but Cmd+O or Cmd+Down opens.
        # For this request, we stick to generic Return/Enter for opening.
        self.tree.bind("<Return>", self.on_open)
        
        # Note: Up/Down arrow navigation is handled natively by the Treeview widget.

    def go_up(self):
        parent_dir = os.path.dirname(self.current_path)
        if parent_dir and os.path.exists(parent_dir):
            self.load_path(parent_dir)

    def load_path(self, path):
        items = self.logic.list_directory(path)
        if items is None:
            messagebox.showerror("Error", "Permission Denied")
            return

        self.current_path = path
        self.path_var.set(path)
        
        # Clear current list
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Populate list
        for item in items:
            # Use a folder icon prefix logic if we added images, strictly text for now
            display_name = f"📁 {item['name']}" if item['is_dir'] else f"📄 {item['name']}"
            
            # Insert into tree
            # iid is set to the full path to make retrieval easy
            self.tree.insert(
                "", 
                tk.END, 
                iid=item['path'], 
                text=display_name, 
                values=(item['size'], item['modified']),
                tags=('dir' if item['is_dir'] else 'file',)
            )

    def on_open(self, event):
        selected_id = self.tree.focus() # Get selected IID (which is the path)
        if not selected_id:
            return

        # Check if it's a directory or file
        if os.path.isdir(selected_id):
            self.load_path(selected_id)
        else:
            # Placeholder for file opening logic
            print(f"Selected file: {selected_id}")

    def refresh_view(self):
        self.load_path(self.current_path)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("MacExplorer")
    
    # Set default window size
    root.geometry("800x600")
    
    # Force minimal window size
    root.minsize(600, 400)

    # Initialize Logic and UI
    fs_handler = FileSystemHandler()
    app = ExplorerUI(root, fs_handler)
    
    root.mainloop()
