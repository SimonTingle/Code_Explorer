import os
import sys
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import mimetypes
from datetime import datetime

class FileSystemHandler:
    """
    Handles file system interactions, data retrieval, and search.
    """
    def list_directory(self, path):
        """Returns a list of items in the directory with metadata."""
        items = []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    items.append(self._create_item_dict(entry))
        except PermissionError:
            return None
        
        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        return items

    def search_files(self, start_path, query):
        """Recursively searches for files/folders matching the query."""
        items = []
        query = query.lower()
        
        # Walk through the directory tree
        try:
            for root, dirs, files in os.walk(start_path):
                # Check directories
                for d in dirs:
                    if query in d.lower():
                        path = os.path.join(root, d)
                        items.append(self._create_item_dict_from_path(path))
                
                # Check files
                for f in files:
                    if query in f.lower():
                        path = os.path.join(root, f)
                        items.append(self._create_item_dict_from_path(path))
                        
                # Safety limit to prevent freezing on huge searches
                if len(items) > 1000:
                    break
        except Exception:
            pass # Ignore permission errors during search
            
        return items

    def _create_item_dict(self, entry):
        """Helper to create item dict from os.scandir entry."""
        stats = entry.stat()
        return self._format_item_data(entry.name, entry.path, entry.is_dir(), stats)

    def _create_item_dict_from_path(self, path):
        """Helper to create item dict from a raw path string."""
        try:
            stats = os.stat(path)
            is_dir = os.path.isdir(path)
            name = os.path.basename(path)
            return self._format_item_data(name, path, is_dir, stats)
        except (FileNotFoundError, PermissionError):
            return None

    def _format_item_data(self, name, path, is_dir, stats):
        size = self._format_size(stats.st_size) if not is_dir else "--"
        mod_time = datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M')
        return {
            "name": name,
            "path": path,
            "is_dir": is_dir,
            "size": size,
            "modified": mod_time
        }

    def get_preview_content(self, path):
        """Determines content for the preview pane."""
        if not path or not os.path.exists(path):
             return "Info", "Item not found."

        if os.path.isdir(path):
            return "Folder Info", f"Path: {path}\nContains: {len(os.listdir(path))} items"

        mime_type, _ = mimetypes.guess_type(path)
        stats = os.stat(path)
        size_str = self._format_size(stats.st_size)
        header = f"File: {os.path.basename(path)}\nType: {mime_type or 'Unknown'}\nSize: {size_str}"

        # Text / Code Preview
        text_extensions = {'.py', '.txt', '.md', '.json', '.xml', '.html', '.css', '.js', '.csv', '.log', '.yml'}
        _, ext = os.path.splitext(path)
        
        if (mime_type and mime_type.startswith('text')) or (ext.lower() in text_extensions):
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read(2048) # Read 2KB
                    if stats.st_size > 2048:
                        content += "\n\n... [Preview Truncated] ..."
                    return header, content
            except Exception as e:
                return header, f"Error reading text: {str(e)}"

        return header, "[Binary/Image File]\nPreview not supported in this version."

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
        self.is_searching = False
        
        self._setup_layout()
        self._bind_events()
        
        # FIX: Directly call load_path instead of the missing refresh_view
        self.load_path(self.current_path)

    def _setup_layout(self):
        self.pack(fill=tk.BOTH, expand=True)
        
        # 1. Navigation & Search Bar
        nav_frame = ttk.Frame(self, padding=(10, 10))
        nav_frame.pack(fill=tk.X)
        
        # Path Bar
        self.path_var = tk.StringVar()
        entry = ttk.Entry(nav_frame, textvariable=self.path_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # Up Button
        up_btn = ttk.Button(nav_frame, text="Up", command=self.go_up)
        up_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Search Bar
        ttk.Label(nav_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(nav_frame, textvariable=self.search_var, width=15)
        self.search_entry.bind("<Return>", lambda e: self.perform_search())
        self.search_entry.pack(side=tk.LEFT, padx=(5, 5))
        
        self.search_btn = ttk.Button(nav_frame, text="Go", command=self.perform_search)
        self.search_btn.pack(side=tk.LEFT)
        
        self.clear_btn = ttk.Button(nav_frame, text="X", width=3, command=self.clear_search, state=tk.DISABLED)
        self.clear_btn.pack(side=tk.LEFT, padx=(2, 0))

        # 2. Split View (PanedWindow)
        self.paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # --- Left Pane: Treeview ---
        self.tree_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(self.tree_frame, weight=1)

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
        self.paned_window.add(self.preview_frame, weight=0)

        self.lbl_meta = ttk.Label(self.preview_frame, text="Select a file", justify=tk.LEFT, font=("Helvetica", 11, "bold"))
        self.lbl_meta.pack(anchor="nw", fill=tk.X, pady=(0, 5))

        self.txt_preview = tk.Text(self.preview_frame, wrap="none", height=10, width=40, font=("Menlo", 11))
        self.txt_preview.pack(fill=tk.BOTH, expand=True)
        self.txt_preview.config(state=tk.DISABLED)

    def _bind_events(self):
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Return>", self.on_double_click)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    def go_up(self):
        if self.is_searching:
            self.clear_search() # Return to normal view first
            return
            
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
        self._populate_tree(items)

    def perform_search(self):
        query = self.search_var.get().strip()
        if not query:
            return

        self.is_searching = True
        self.clear_btn.config(state=tk.NORMAL)
        self.path_var.set(f"Searching: '{query}' in {os.path.basename(self.current_path)}...")
        
        # Perform search
        results = self.logic.search_files(self.current_path, query)
        self._populate_tree(results)
        
        if not results:
            self.path_var.set(f"No results for '{query}'")

    def clear_search(self):
        self.is_searching = False
        self.search_var.set("")
        self.clear_btn.config(state=tk.DISABLED)
        self.load_path(self.current_path)

    def _populate_tree(self, items):
        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Clear preview
        self.update_preview(None)

        if items:
            for item in items:
                if item is None: continue 
                
                # If searching, we might want to show partial path in name or just name
                # Here we stick to name, but the tooltip/preview shows full path
                display_name = f"📁 {item['name']}" if item['is_dir'] else f"📄 {item['name']}"
                
                self.tree.insert(
                    "", tk.END, iid=item['path'], text=display_name, 
                    values=(item['size'], item['modified']),
                    tags=('dir' if item['is_dir'] else 'file',)
                )

    def on_double_click(self, event):
        selected_id = self.tree.focus()
        if selected_id and os.path.isdir(selected_id):
            # If we are searching and click a folder, we enter that folder and exit search mode
            if self.is_searching:
                self.clear_search() 
                self.load_path(selected_id)
            else:
                self.load_path(selected_id)

    def on_select(self, event):
        selected_id = self.tree.focus()
        if selected_id:
            self.update_preview(selected_id)

    def update_preview(self, path):
        self.txt_preview.config(state=tk.NORMAL)
        self.txt_preview.delete(1.0, tk.END)
        
        if not path:
            self.lbl_meta.config(text="No Selection")
            self.txt_preview.config(state=tk.DISABLED)
            return

        header, content = self.logic.get_preview_content(path)
        self.lbl_meta.config(text=header)
        self.txt_preview.insert(tk.END, content)
        self.txt_preview.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("MacExplorer Pro")
    root.geometry("900x600")
    
    fs_handler = FileSystemHandler()
    app = ExplorerUI(root, fs_handler)
    
    root.mainloop()