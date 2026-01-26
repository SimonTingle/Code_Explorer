import os
import sys
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import mimetypes
from datetime import datetime
import re
import subprocess
import time
import threading
import json 

# 

try:
    import psutil
except ImportError:
    psutil = None

# --- Helper for Hover Labels (ToolTips) ---
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + cy + self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                      background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                      font=("tahoma", "10", "normal"))
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()

class FileSystemHandler:
    CHUNK_SIZE = 2048

    def search_files(self, start_path, query, cancel_event=None):
        items = []
        query = query.lower()
        try:
            for root, dirs, files in os.walk(start_path):
                if cancel_event and cancel_event.is_set():
                    return None
                for d in dirs:
                    if query in d.lower():
                        items.append(self._create_item_dict_from_path(os.path.join(root, d)))
                for f in files:
                    if query in f.lower():
                        items.append(self._create_item_dict_from_path(os.path.join(root, f)))
                if len(items) > 2000: break 
        except Exception: pass
        return items

    def list_directory(self, path):
        items = []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    items.append(self._create_item_dict(entry))
        except PermissionError: return None
        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        return items

    def _create_item_dict(self, entry):
        stats = entry.stat()
        return self._format_item_data(entry.name, entry.path, entry.is_dir(), stats)

    def _create_item_dict_from_path(self, path):
        try:
            stats = os.stat(path)
            return self._format_item_data(os.path.basename(path), path, os.path.isdir(path), stats)
        except (FileNotFoundError, PermissionError): return None

    def _format_item_data(self, name, path, is_dir, stats):
        return {
            "name": name, "path": path, "is_dir": is_dir,
            "raw_size": stats.st_size if not is_dir else -1,
            "size": self._format_size(stats.st_size) if not is_dir else "--",
            "modified": datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M'),
            "raw_modified": stats.st_mtime
        }

    def _format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024: return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def get_preview_content(self, path, offset=0):
        """Determines content for the preview pane with offset support and expanded extension support."""
        if not path or not os.path.exists(path): return "Info", "Item not found.", False
        if os.path.isdir(path):
            try: count = len(os.listdir(path))
            except: count = "?"
            return "Folder Info", f"Path: {path}\nContains: {count} items", False
        
        mime_type, _ = mimetypes.guess_type(path)
        stats = os.stat(path)
        header = f"File: {os.path.basename(path)}\nType: {mime_type or 'Unknown'}\nSize: {self._format_size(stats.st_size)}"
        
        text_extensions = {
            '.py', '.txt', '.md', '.json', '.xml', '.html', '.css', '.js', '.csv', '.log', '.yml', 
            '.sh', '.bash', '.zsh', '.env', '.gitignore', '.gitconfig', '.toml', '.lock', '.cfg'
        }
        
        _, ext = os.path.splitext(path)
        is_dotfile = os.path.basename(path).startswith('.')
        
        if (mime_type and mime_type.startswith('text')) or (ext.lower() in text_extensions) or is_dotfile:
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    f.seek(offset)
                    content = f.read(self.CHUNK_SIZE)
                    has_more = (offset + self.CHUNK_SIZE) < stats.st_size
                    return header, content, has_more
            except Exception as e: return header, f"Error reading text: {str(e)}", False
        return header, "[Binary File]\nNo preview available.", False

class SystemMonitor(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.active_tasks = 0 
        if psutil is None:
            ttk.Label(self, text="⚠️ No psutil", font=("Menlo", 9), foreground="red").pack(side=tk.LEFT, padx=10)
            return
        self.last_net_io = psutil.net_io_counters(); self.last_time = time.time()
        f_cfg = ("Menlo", 9)
        
        self.lbl_task = ttk.Label(self, text="T: 0", font=f_cfg, width=6, foreground="#007AFF")
        self.lbl_task.pack(side=tk.LEFT, padx=2)
        
        self.lbl_disk = ttk.Label(self, text="D: --%", font=f_cfg, width=8)
        self.lbl_disk.pack(side=tk.LEFT, padx=2)
        
        self.lbl_mem = ttk.Label(self, text="M: --%", font=f_cfg, width=8)
        self.lbl_mem.pack(side=tk.LEFT, padx=2)
        
        self.lbl_net = ttk.Label(self, text="↓0K ↑0K", font=f_cfg, width=18)
        self.lbl_net.pack(side=tk.LEFT, padx=2)
        self.update_stats()

    def set_tasks(self, count):
        self.lbl_task.config(text=f"T: {count}")

    def update_stats(self):
        if psutil is None: return
        try:
            d = psutil.disk_usage('/'); self.lbl_disk.config(text=f"D: {d.percent}%")
            m = psutil.virtual_memory(); self.lbl_mem.config(text=f"M: {m.percent}%")
            curr_net = psutil.net_io_counters(); curr_t = time.time(); dt = curr_t - self.last_time
            if dt > 0:
                ds = (curr_net.bytes_recv - self.last_net_io.bytes_recv) / dt
                us = (curr_net.bytes_sent - self.last_net_io.bytes_sent) / dt
                self.lbl_net.config(text=f"↓{self._fmt(ds)} ↑{self._fmt(us)}")
                self.last_net_io = curr_net; self.last_time = curr_t
        except: pass
        self.after(1000, self.update_stats)

    def _fmt(self, b):
        if b < 1024: return f"{int(b)}B"
        elif b < 1024**2: return f"{b/1024:.0f}K"
        else: return f"{b/1024**2:.1f}M"

class ExplorerUI(ttk.Frame):
    def __init__(self, parent, logic_handler):
        super().__init__(parent)
        self.logic = logic_handler
        self.current_path = os.path.expanduser("~")
        self.is_searching = False
        self.sort_reverse = False
        self.running_threads = 0 
        self.cancel_event = threading.Event()
        self.fav_file = "favorites.json"
        self.preview_offset = 0
        self.current_preview_file = None
        
        self._setup_layout()
        self._setup_context_menu() 
        self._bind_events()
        self._load_favorites() 
        self.load_path(self.current_path)

    def _setup_layout(self):
        self.pack(fill=tk.BOTH, expand=True)
        
        top_container = ttk.Frame(self, padding=(5, 2))
        top_container.pack(fill=tk.X)
        nav_frame = ttk.Frame(top_container)
        nav_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(nav_frame, text="Up", command=self.go_up, width=4).pack(side=tk.LEFT, padx=(0, 5))
        self.path_var = tk.StringVar()
        ttk.Entry(nav_frame, textvariable=self.path_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        ttk.Label(nav_frame, text="S:", font=("Helvetica", 10)).pack(side=tk.LEFT)
        self.search_var = tk.StringVar(); self.search_entry = ttk.Entry(nav_frame, textvariable=self.search_var, width=12)
        self.search_entry.pack(side=tk.LEFT, padx=(2, 5))
        ttk.Button(nav_frame, text="Go", command=self.perform_search, width=4).pack(side=tk.LEFT)
        self.clear_btn = ttk.Button(nav_frame, text="X", width=2, command=self.clear_search, state=tk.DISABLED)
        self.clear_btn.pack(side=tk.LEFT, padx=(2, 0))
        
        monitor_frame = ttk.Frame(top_container); monitor_frame.pack(side=tk.RIGHT, padx=(5, 0))
        self.monitor = SystemMonitor(monitor_frame); self.monitor.pack(side=tk.LEFT)

        mem_frame = ttk.Frame(self, padding=(5, 0, 5, 5))
        mem_frame.pack(fill=tk.X)
        ttk.Label(mem_frame, text="Memory slots:", font=("Helvetica", 9, "italic")).pack(side=tk.LEFT, padx=(5, 5))
        
        self.mem_buttons = []
        self.mem_tips = []
        for i in range(4):
            btn = ttk.Button(mem_frame, text=f"[{i+1}] Empty", width=12)
            btn.pack(side=tk.LEFT, padx=2)
            btn.configure(command=lambda idx=i: self._jump_to_favorite(idx))
            btn.bind("<Button-2>", lambda e, idx=i: self._save_to_favorite(idx)) 
            btn.bind("<Button-3>", lambda e, idx=i: self._save_to_favorite(idx)) 
            tip = ToolTip(btn, "")
            self.mem_buttons.append(btn)
            self.mem_tips.append(tip)

        self.paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.tree_frame = ttk.Frame(self.paned_window); self.paned_window.add(self.tree_frame, weight=1)
        self.cols = ("size", "modified")
        self.tree = ttk.Treeview(self.tree_frame, columns=self.cols, selectmode="browse")
        self.tree.heading("#0", text="Name ↑↓", command=lambda: self._sort_column("#0"))
        self.tree.heading("size", text="Size ↑↓", command=lambda: self._sort_column("size"))
        self.tree.heading("modified", text="Date Modified ↑↓", command=lambda: self._sort_column("modified"))
        self.tree.column("#0", stretch=True, width=250)
        self.tree.column("size", width=100, anchor=tk.E)
        self.tree.column("modified", width=150)
        self.tree.tag_configure('folder', foreground='#007AFF') 
        scrollbar = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set); self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.preview_frame = ttk.Frame(self.paned_window, relief="sunken", padding=5)
        self.paned_window.add(self.preview_frame, weight=0)
        
        # --- REASON FOR UPDATE: New header frame for preview metadata and Copy button ---
        preview_header = ttk.Frame(self.preview_frame)
        preview_header.pack(fill=tk.X, pady=(0, 5))
        
        self.lbl_meta = ttk.Label(preview_header, text="Select a file", font=("Helvetica", 10, "bold"))
        self.lbl_meta.pack(side=tk.LEFT, anchor="nw")
        
        self.copy_btn = ttk.Button(preview_header, text="Copy", width=6, command=self.copy_preview_to_clipboard)
        # REASON: Hide copy button until valid text is loaded
        
        self.text_container = ttk.Frame(self.preview_frame)
        self.text_container.pack(fill=tk.BOTH, expand=True)

        self.txt_preview = tk.Text(self.text_container, wrap="none", height=10, width=35, font=("Menlo", 10), state=tk.DISABLED)
        self.txt_preview.pack(fill=tk.BOTH, expand=True)
        
        self.load_more_btn = ttk.Button(self.preview_frame, text="Load More...", command=self.load_next_chunk)

    def _load_favorites(self):
        if os.path.exists(self.fav_file):
            try:
                with open(self.fav_file, 'r') as f:
                    self.favorites = json.load(f)
            except: self.favorites = {}
        else: self.favorites = {}
        self._update_mem_ui()

    def _save_to_favorite(self, idx):
        path = self.tree.focus() or self.current_path
        if not os.path.isdir(path):
            path = os.path.dirname(path)
        self.favorites[str(idx)] = path
        try:
            with open(self.fav_file, 'w') as f:
                json.dump(self.favorites, f)
            self._update_mem_ui()
            self.mem_buttons[idx].state(['pressed'])
            self.after(100, lambda: self.mem_buttons[idx].state(['!pressed']))
        except Exception as e:
            messagebox.showerror("Error", f"Could not save favorite: {e}")

    def _jump_to_favorite(self, idx):
        path = self.favorites.get(str(idx))
        if path and os.path.exists(path):
            self.load_path(path)
        else:
            messagebox.showinfo("Memory", "Slot is empty. Right-click to save a folder here.")

    def _update_mem_ui(self):
        for i in range(4):
            path = self.favorites.get(str(i))
            if path:
                folder_name = os.path.basename(path) or path
                self.mem_buttons[i].config(text=f"[{i+1}] {folder_name[:10]}")
                self.mem_tips[i].text = path
            else:
                self.mem_buttons[i].config(text=f"[{i+1}] Empty")
                self.mem_tips[i].text = "Empty slot - Right-click to save folder"

    def _update_task_status(self, delta):
        self.running_threads += delta
        self.monitor.set_tasks(max(0, self.running_threads))

    def load_path(self, path):
        self.cancel_event.set(); self.cancel_event = threading.Event()
        self._update_task_status(1)
        threading.Thread(target=lambda: self._bg_load(path), daemon=True).start()

    def _bg_load(self, path):
        items = self.logic.list_directory(path)
        self.after(0, lambda: self._finish_load(items, path))

    def _finish_load(self, items, path):
        if items is not None:
            self.current_path = path; self.path_var.set(path); self._populate_tree(items)
        self._update_task_status(-1)

    def perform_search(self):
        q = self.search_var.get().strip()
        if not q: return
        self.is_searching = True; self.clear_btn.config(state=tk.NORMAL)
        self.cancel_event.set(); self.cancel_event = threading.Event()
        self._update_task_status(1)
        threading.Thread(target=lambda: self._bg_search(q), daemon=True).start()

    def _bg_search(self, q):
        res = self.logic.search_files(self.current_path, q, cancel_event=self.cancel_event)
        self.after(0, lambda: self._finish_search(res))

    def _finish_search(self, res):
        if res is not None: self._populate_tree(res)
        self._update_task_status(-1)

    def clear_search(self):
        self.cancel_event.set(); self.is_searching = False; self.search_var.set("")
        self.clear_btn.config(state=tk.DISABLED); self.load_path(self.current_path)

    def _setup_context_menu(self):
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Reveal in Finder", command=lambda: subprocess.run(["open", "-R", self.tree.focus()]))
        self.context_menu.add_command(label="Copy Path", command=lambda: (self.clipboard_clear(), self.clipboard_append(self.tree.focus())))

    def _bind_events(self):
        self.tree.bind("<Double-1>", lambda e: self._on_dbclick())
        self.tree.bind("<Return>", lambda e: self._on_dbclick())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_preview(self.tree.focus()))
        self.search_entry.bind("<Return>", lambda e: self.perform_search())
        self.tree.bind("<Button-2>", self._show_ctx); self.tree.bind("<Button-3>", self._show_ctx)

    def _show_ctx(self, e):
        row = self.tree.identify_row(e.y)
        if row: self.tree.selection_set(row); self.context_menu.post(e.x_root, e.y_root)

    def _on_dbclick(self):
        sid = self.tree.focus()
        if sid and os.path.isdir(sid):
            if self.is_searching: self.clear_search()
            self.load_path(sid)

    # REASON FOR COMMENTING: Previous update_preview did not handle Copy button visibility.
    # def update_preview(self, path):
    #     ... original code ...

    def update_preview(self, path):
        """Initial load of a file preview with truncation check and button visibility."""
        self.preview_offset = 0
        self.current_preview_file = path
        self.load_more_btn.pack_forget()
        self.copy_btn.pack_forget()
        
        self.txt_preview.config(state=tk.NORMAL)
        self.txt_preview.delete(1.0, tk.END)
        
        if not path: 
            self.lbl_meta.config(text="No Selection")
            self.txt_preview.config(state=tk.DISABLED)
            return

        h, c, has_more = self.logic.get_preview_content(path, self.preview_offset)
        self.lbl_meta.config(text=h)
        self.txt_preview.insert(tk.END, c)
        self.txt_preview.config(state=tk.DISABLED)
        
        # REASON: Show Copy button only if text was actually loaded
        if c and not c.startswith("["):
            self.copy_btn.pack(side=tk.RIGHT, anchor="ne", padx=5)
        
        if has_more:
            self.load_more_btn.pack(side=tk.BOTTOM, fill=tk.X, pady=2)
            self.preview_offset += self.logic.CHUNK_SIZE

    def load_next_chunk(self):
        """Appends next chunk to preview window."""
        if not self.current_preview_file: return
        h, c, has_more = self.logic.get_preview_content(self.current_preview_file, self.preview_offset)
        self.txt_preview.config(state=tk.NORMAL); self.txt_preview.insert(tk.END, "\n" + "-"*10 + " [Next Chunk] " + "-"*10 + "\n"); self.txt_preview.insert(tk.END, c); self.txt_preview.config(state=tk.DISABLED); self.txt_preview.see(tk.END)
        if not has_more: self.load_more_btn.pack_forget()
        else: self.preview_offset += self.logic.CHUNK_SIZE

    # REASON FOR ADDITION: Function to copy current preview text to macOS clipboard
    def copy_preview_to_clipboard(self):
        """Copies all text currently in the preview window."""
        content = self.txt_preview.get(1.0, tk.END)
        if content.strip():
            self.clipboard_clear()
            self.clipboard_append(content)
            # Optional: Visual feedback
            self.copy_btn.config(text="Copied!")
            self.after(1500, lambda: self.copy_btn.config(text="Copy"))

    def _sort_column(self, col):
        children = self.tree.get_children(''); self.sort_reverse = not self.sort_reverse
        def nk(t): return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', str(t))]
        if col == "#0":
            s_items = sorted(children, key=lambda i: nk(self.tree.item(i, 'text')), reverse=self.sort_reverse)
        else:
            s_items = sorted(children, key=lambda i: nk(self.tree.set(i, col)), reverse=self.sort_reverse)
        for idx, iid in enumerate(s_items): self.tree.move(iid, '', idx)

    def _populate_tree(self, items):
        for i in self.tree.get_children(): self.tree.delete(i)
        self.update_preview(None)
        if items:
            for itm in items:
                d_name = f"📁 {itm['name']}" if itm['is_dir'] else f"📄 {itm['name']}"
                tag = 'folder' if itm['is_dir'] else ''
                self.tree.insert("", tk.END, iid=itm['path'], text=d_name, values=(itm['size'], itm['modified']), tags=(tag,))

    def go_up(self):
        if self.is_searching: self.clear_search()
        else:
            p = os.path.dirname(self.current_path)
            if p and os.path.exists(p): self.load_path(p)

if __name__ == "__main__":
    root = tk.Tk(); root.title("MacExplorer Pro"); root.geometry("1100x650")
    app = ExplorerUI(root, FileSystemHandler()); root.mainloop()