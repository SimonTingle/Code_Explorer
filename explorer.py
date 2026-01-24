import os
import sys
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import mimetypes
from datetime import datetime
import re
import subprocess
import psutil # NEW: Required for system stats
import time

class FileSystemHandler:
    # ... [FileSystemHandler code remains unchanged] ...
    def list_directory(self, path):
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
        items = []
        query = query.lower()
        try:
            for root, dirs, files in os.walk(start_path):
                for d in dirs:
                    if query in d.lower():
                        items.append(self._create_item_dict_from_path(os.path.join(root, d)))
                for f in files:
                    if query in f.lower():
                        items.append(self._create_item_dict_from_path(os.path.join(root, f)))
                if len(items) > 1000: break
        except Exception:
            pass
        return items

    def _create_item_dict(self, entry):
        stats = entry.stat()
        return self._format_item_data(entry.name, entry.path, entry.is_dir(), stats)

    def _create_item_dict_from_path(self, path):
        try:
            stats = os.stat(path)
            return self._format_item_data(os.path.basename(path), path, os.path.isdir(path), stats)
        except (FileNotFoundError, PermissionError):
            return None

    def _format_item_data(self, name, path, is_dir, stats):
        return {
            "name": name,
            "path": path,
            "is_dir": is_dir,
            "raw_size": stats.st_size if not is_dir else -1,
            "size": self._format_size(stats.st_size) if not is_dir else "--",
            "modified": datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M'),
            "raw_modified": stats.st_mtime
        }

    def get_preview_content(self, path):
        if not path or not os.path.exists(path):
             return "Info", "Item not found."
        if os.path.isdir(path):
            return "Folder Info", f"Path: {path}\nContains: {len(os.listdir(path))} items"

        mime_type, _ = mimetypes.guess_type(path)
        stats = os.stat(path)
        header = f"File: {os.path.basename(path)}\nType: {mime_type or 'Unknown'}\nSize: {self._format_size(stats.st_size)}"

        text_extensions = {'.py', '.txt', '.md', '.json', '.xml', '.html', '.css', '.js', '.csv', '.log', '.yml'}
        if (mime_type and mime_type.startswith('text')) or (os.path.splitext(path)[1].lower() in text_extensions):
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read(2048)
                    return header, content + ("\n\n... [Truncated] ..." if stats.st_size > 2048 else "")
            except Exception as e:
                return header, f"Error reading text: {str(e)}"
        return header, "[Binary File]\nNo preview available."

    def _format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024: return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

class SystemMonitor(ttk.Frame):
    """
    NEW: Handles fetching and displaying system stats.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.last_net_io = psutil.net_io_counters()
        self.last_time = time.time()
        
        # Labels for stats
        self.lbl_disk = ttk.Label(self, text="Disk: --%", font=("Menlo", 10))
        self.lbl_disk.pack(side=tk.LEFT, padx=8)
        
        self.lbl_mem = ttk.Label(self, text="Mem: --%", font=("Menlo", 10))
        self.lbl_mem.pack(side=tk.LEFT, padx=8)
        
        self.lbl_net = ttk.Label(self, text="↓ 0 KB/s  ↑ 0 KB/s", font=("Menlo", 10))
        self.lbl_net.pack(side=tk.LEFT, padx=8)
        
        self.update_stats()

    def update_stats(self):
        # 1. Disk Usage (Root)
        disk = psutil.disk_usage('/')
        self.lbl_disk.config(text=f"Disk: {disk.percent}%")
        
        # 2. Memory Usage
        mem = psutil.virtual_memory()
        self.lbl_mem.config(text=f"Mem: {mem.percent}%")
        
        # 3. Network Speed
        current_net = psutil.net_io_counters()
        current_time = time.time()
        
        dt = current_time - self.last_time
        if dt > 0:
            # Calculate bytes per second
            down_speed = (current_net.bytes_recv - self.last_net_io.bytes_recv) / dt
            up_speed = (current_net.bytes_sent - self.last_net_io.bytes_sent) / dt
            
            self.lbl_net.config(text=f"↓ {self._format_speed(down_speed)}  ↑ {self._format_speed(up_speed)}")
            
            self.last_net_io = current_net
            self.last_time = current_time
        
        # Update every 1000ms (1 second)
        self.after(1000, self.update_stats)

    def _format_speed(self, bytes_sec):
        if bytes_sec < 1024: return f"{int(bytes_sec)} B/s"
        elif bytes_sec < 1024**2: return f"{bytes_sec/1024:.1f} KB/s"
        else: return f"{bytes_sec/1024**2:.1f} MB/s"

class ExplorerUI(ttk.Frame):
    def __init__(self, parent, logic_handler):
        super().__init__(parent)
        self.logic = logic_handler
        self.current_path = os.path.expanduser("~")
        self.is_searching = False
        self.sort_reverse = False
        
        self._setup_layout()
        self._setup_context_menu() 
        self._bind_events()
        self.load_path(self.current_path)

    def _setup_layout(self):
        self.pack(fill=tk.BOTH, expand=True)
        
        # --- Top Bar (Nav + Monitor) ---
        top_bar = ttk.Frame(self, padding=(5, 5))
        top_bar.pack(fill=tk.X)
        
        # Left side: Navigation
        nav_frame = ttk.Frame(top_bar)
        nav_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.path_var = tk.StringVar()
        ttk.Button(nav_frame, text="Up", command=self.go_up).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(nav_frame, textvariable=self.path_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # Search controls inside nav
        ttk.Label(nav_frame, text="Search:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(nav_frame, textvariable=self.search_var, width=15)
        self.search_entry.pack(side=tk.LEFT, padx=(5, 5))
        ttk.Button(nav_frame, text="Go", command=self.perform_search).pack(side=tk.LEFT)
        self.clear_btn = ttk.Button(nav_frame, text="X", width=3, command=self.clear_search, state=tk.DISABLED)
        self.clear_btn.pack(side=tk.LEFT, padx=(2, 0))

        # Right side: System Monitor
        # Separator line
        ttk.Separator(top_bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        # NEW: Add System Monitor Widget
        self.monitor = SystemMonitor(top_bar)
        self.monitor.pack(side=tk.RIGHT)

        # REASON FOR COMMENTING: Replaced old nav_frame pack structure to accommodate split top_bar
        # nav_frame = ttk.Frame(self, padding=(10, 10))
        # nav_frame.pack(fill=tk.X)
        # ... (Old widget packing logic was moved into 'top_bar' above)

        self.paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.tree_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(self.tree_frame, weight=1)

        columns = ("size", "modified")
        self.tree = ttk.Treeview(self.tree_frame, columns=columns, selectmode="browse")
        
        self.tree.heading("#0", text="Name ↑↓", command=lambda: self._sort_column("#0"))
        self.tree.heading("size", text="Size ↑↓", command=lambda: self._sort_column("size"))
        self.tree.heading("modified", text="Date Modified ↑↓", command=lambda: self._sort_column("modified"))
        
        self.tree.column("#0", stretch=True, width=250)
        self.tree.column("size", width=100, anchor=tk.E)
        self.tree.column("modified", width=150)

        self.tree.tag_configure('folder', foreground='#007AFF') 
        self.tree.tag_configure('python', foreground='#2E7D32')
        self.tree.tag_configure('config', foreground='#EF6C00')
        
        scrollbar = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.preview_frame = ttk.Frame(self.paned_window, relief="sunken", padding=5)
        self.paned_window.add(self.preview_frame, weight=0)
        self.lbl_meta = ttk.Label(self.preview_frame, text="Select a file", font=("Helvetica", 11, "bold"))
        self.lbl_meta.pack(anchor="nw", fill=tk.X, pady=(0, 5))
        self.txt_preview = tk.Text(self.preview_frame, wrap="none", height=10, width=40, font=("Menlo", 11), state=tk.DISABLED)
        self.txt_preview.pack(fill=tk.BOTH, expand=True)

    def _setup_context_menu(self):
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Reveal in Finder", command=self.reveal_in_finder)
        self.context_menu.add_command(label="Copy Path", command=self.copy_path_to_clipboard)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Open in Terminal", command=self.open_in_terminal)

    def _bind_events(self):
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Return>", self.on_double_click)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.search_entry.bind("<Return>", lambda e: self.perform_search())
        self.tree.bind("<Button-2>", self.show_context_menu)
        self.tree.bind("<Button-3>", self.show_context_menu)

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item) 
            self.context_menu.post(event.x_root, event.y_root)

    def reveal_in_finder(self):
        path = self.tree.focus()
        if path:
            subprocess.run(["open", "-R", path])

    def copy_path_to_clipboard(self):
        path = self.tree.focus()
        if path:
            self.clipboard_clear()
            self.clipboard_append(path)
            messagebox.showinfo("Clipboard", f"Path copied:\n{path}")

    def open_in_terminal(self):
        path = self.tree.focus()
        if path:
            target = path if os.path.isdir(path) else os.path.dirname(path)
            subprocess.run(["open", "-a", "Terminal", target])

    def _sort_column(self, col):
        children = self.tree.get_children('')
        def natural_key(text):
            return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]
        def get_value(item_id):
            if col == "#0":
                return natural_key(self.tree.item(item_id, 'text'))
            return natural_key(self.tree.set(item_id, col))
        self.sort_reverse = not self.sort_reverse
        sorted_items = sorted(children, key=get_value, reverse=self.sort_reverse)
        for index, item_id in enumerate(sorted_items):
            self.tree.move(item_id, '', index)

    def load_path(self, path):
        items = self.logic.list_directory(path)
        if items is None:
            messagebox.showerror("Error", "Permission Denied")
            return
        self.current_path = path
        self.path_var.set(path)
        self._populate_tree(items)

    def _populate_tree(self, items):
        for item in self.tree.get_children(): self.tree.delete(item)
        self.update_preview(None)
        if items:
            for item in items:
                if not item: continue
                display_name = f"📁 {item['name']}" if item['is_dir'] else f"📄 {item['name']}"
                item_tags = []
                if item['is_dir']: item_tags.append('folder')
                elif item['name'].endswith('.py'): item_tags.append('python')
                elif item['name'].endswith(('.json', '.yaml', '.yml', '.md')): item_tags.append('config')

                self.tree.insert("", tk.END, iid=item['path'], text=display_name, 
                                 values=(item['size'], item['modified']), 
                                 tags=tuple(item_tags))

    def on_double_click(self, event):
        sid = self.tree.focus()
        if sid and os.path.isdir(sid):
            if self.is_searching: self.clear_search()
            self.load_path(sid)

    def on_select(self, event):
        sid = self.tree.focus()
        if sid: self.update_preview(sid)

    def update_preview(self, path):
        self.txt_preview.config(state=tk.NORMAL)
        self.txt_preview.delete(1.0, tk.END)
        if not path:
            self.lbl_meta.config(text="No Selection")
        else:
            header, content = self.logic.get_preview_content(path)
            self.lbl_meta.config(text=header)
            self.txt_preview.insert(tk.END, content)
        self.txt_preview.config(state=tk.DISABLED)

    def perform_search(self):
        q = self.search_var.get().strip()
        if not q: return
        self.is_searching = True
        self.clear_btn.config(state=tk.NORMAL)
        self._populate_tree(self.logic.search_files(self.current_path, q))

    def clear_search(self):
        self.is_searching = False
        self.search_var.set("")
        self.clear_btn.config(state=tk.DISABLED)
        self.load_path(self.current_path)

    def go_up(self):
        if self.is_searching: self.clear_search()
        else:
            p = os.path.dirname(self.current_path)
            if p and os.path.exists(p): self.load_path(p)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("MacExplorer Pro")
    root.geometry("1100x600") # REASON: Widened window to fit system monitor
    app = ExplorerUI(root, FileSystemHandler())
    root.mainloop()