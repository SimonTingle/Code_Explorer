import os
import sys
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import mimetypes
from datetime import datetime

class FileSystemHandler:
    """
    Handles file system interactions and data retrieval.
    """
    def list_directory(self, path):
        """Returns a list of items in the directory with metadata."""
        items = []
        try:
            with os.scandir(path) as it:
                for entry in it:
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
            return None
        
        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        return items

    def get_preview_content(self, path):
        """
        Determines content for the preview pane.
        Returns a tuple: (header_info, body_content)
        """
        if os.path.isdir(path):
            return "Folder Info", f"Path: {path}\nSelect a file to see a preview."

        # Guess file type
        mime_type, _ = mimetypes.guess_type(path)
        stats = os.stat(path)
        size_str = self._format_size(stats.st_size)

        # Header info (always shown)
        header = f"File: {os.path.basename(path)}\nType: {mime_type or 'Unknown'}\nSize: {size_str}"

        # 1. Text / Code Preview
        # We explicitly check common code extensions or text mime types
        text_extensions = {'.py', '.txt', '.md', '.json', '.xml', '.html', '.css', '.js', '.csv'}
        _, ext = os.path.splitext(path)
        
        if (mime_type and mime_type.startswith('text')) or (ext.lower() in text_extensions):
            try:
                # Read only the first 1024 bytes to ensure UI stays responsive
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read(1024)
                    if stats.st_size > 1024:
                        content += "\n\n... [Preview Truncated] ..."
                    return header, content
            except Exception as e:
                return header, f"Error reading text: {str(e)}"

        # 2. Image Metadata Preview
        if mime_type and mime_type.startswith('image'):
            # Without external libs (PIL), we stick to basic stats
            return header, "[Image File]\nPreview requires 'Pillow' library.\n(Metadata shown above)"

        # 3. Binary / Other
        return header, "[Binary/Unknown File]\nNo text preview available."

    def _format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

class ExplorerUI(ttk.Frame):
    def __init__(self, parent, logic_handler):
        super().__init__(parent)
        self.logic = logic_handler
        self.current_path = os.path.expanduser("~")
        
        self._setup_layout()
        self._bind_events()
        self.refresh_view()

    def _setup_layout(self):
        self.pack(fill=tk.BOTH, expand=True)
        
        # 1. Navigation Bar
        nav_frame = ttk.Frame(self, padding=(10, 10))
        nav_frame.pack(fill=tk.X)
        
        self.path_var = tk.StringVar()
        entry = ttk.Entry(nav_frame, textvariable=self.path_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        up_btn = ttk.Button(nav_frame, text="Up", command=self.go_up)
        up_btn.pack(side=tk.RIGHT)

        # 2. Split View (PanedWindow)
        # This creates the resizable divider between File List and Preview
        self.paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # --- Left Pane: Treeview ---
        self.tree_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(self.tree_frame, weight=1) # weight=1 means this side expands

        columns = ("size", "modified")
        self.tree = ttk.Treeview(self.tree_frame, columns=columns, selectmode="browse")
        self.tree.heading("#0", text="Name", anchor=tk.W)
        self.tree.heading("size", text="Size", anchor=tk.E)
        self.tree.heading("modified", text="Date Modified", anchor=tk.W)
        self.tree.column("#0", stretch=True, width=200)
        self.tree.column("size", width=80, anchor=tk.E)
        self.tree.column("modified", width=120)

        scrollbar = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # --- Right Pane: Preview ---
        self.preview_frame = ttk.Frame(self.paned_window, relief="sunken", padding=5)
        self.paned_window.add(self.preview_frame, weight=0) # weight=0 keeps it static size initially

        # Metadata Label
        self.lbl_meta = ttk.Label(self.preview_frame, text="Select a file", justify=tk.LEFT, font=("Helvetica", 11, "bold"))
        self.lbl_meta.pack(anchor="nw", fill=tk.X, pady=(0, 5))

        # Text Content Area
        self.txt_preview = tk.Text(self.preview_frame, wrap="none", height=10, width=40, font=("Menlo", 11))
        self.txt_preview.pack(fill=tk.BOTH, expand=True)
        
        # Disable editing the preview
        self.txt_preview.config(state=tk.DISABLED)

    def _bind_events(self):
        # Double click to enter folder
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Return>", self.on_double_click)
        
        # Single click (or arrow key selection) to update preview
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

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
        
        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Clear preview
        self.update_preview(None)

        for item in items:
            display_name = f"📁 {item['name']}" if item['is_dir'] else f"📄 {item['name']}"
            self.tree.insert(
                "", tk.END, iid=item['path'], text=display_name, 
                values=(item['size'], item['modified']),
                tags=('dir' if item['is_dir'] else 'file',)
            )

    def on_double_click(self, event):
        selected_id = self.tree.focus()
        if selected_id and os.path.isdir(selected_id):
            self.load_path(selected_id)

    def on_select(self, event):
        selected_id = self.tree.focus()
        if selected_id:
            self.update_preview(selected_id)

    def update_preview(self, path):
        # Enable text widget to clear/update it
        self.txt_preview.config(state=tk.NORMAL)
        self.txt_preview.delete(1.0, tk.END)
        
        if not path:
            self.lbl_meta.config(text="No Selection")
            self.txt_preview.config(state=tk.DISABLED)
            return

        header, content = self.logic.get_preview_content(path)
        
        self.lbl_meta.config(text=header)
        self.txt_preview.insert(tk.END, content)
        
        # Make read-only again
        self.txt_preview.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("MacExplorer Pro")
    root.geometry("900x600")
    
    fs_handler = FileSystemHandler()
    app = ExplorerUI(root, fs_handler)
    
    root.mainloop()