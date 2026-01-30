import os
import sys
import tkinter as tk
from tkinter import ttk, simpledialog
from tkinter import messagebox
import mimetypes
from datetime import datetime
import re
import subprocess
import time
import threading
import json 
import difflib 
import random 
import webbrowser 
from concurrent.futures import ThreadPoolExecutor
# --- MISSING IMPORTS ADDED BELOW ---
import http.server
import socketserver 
# -----------------------------------

try:
    import psutil
except ImportError:
    psutil = None

class ToolTip:
    def __init__(self, widget, text=""):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.label = None

    def show_tip(self, x=None, y=None, text=None):
        """Manually show or update tip at specific coordinates."""
        if text: self.text = text
        
        if not self.text:
            self.hide_tip()
            return
        
        if x is None or y is None:
            x, y, cx, cy = self.widget.bbox("insert")
            x = x + self.widget.winfo_rootx() + 25
            y = y + cy + self.widget.winfo_rooty() + 25
        
        if self.tip_window:
            self.tip_window.wm_geometry(f"+{x}+{y}")
            if self.label:
                self.label.config(text=self.text)
            return

        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(1)
        self.tip_window.wm_geometry(f"+{x}+{y}")
        
        self.label = tk.Label(self.tip_window, text=self.text, justify=tk.LEFT,
                              background="#ffffe0", foreground="#000000",
                              relief=tk.SOLID, borderwidth=1,
                              font=("tahoma", "10", "normal"))
        self.label.pack(ipadx=1)

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None
            self.label = None

class DirectoryVisualizer(tk.Toplevel):
    def __init__(self, parent, path):
        super().__init__(parent)
        self.title(f"Visualizing: {os.path.basename(path)}")
        self.geometry("600x450")
        self.path = path
        self.canvas = tk.Canvas(self, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # REASON FOR UPDATE: Ensure loading text is visible (black)
        self.lbl_loading = tk.Label(self, text="Scanning...", font=("Helvetica", 14), bg="white", fg="black")
        self.lbl_loading.place(relx=0.5, rely=0.5, anchor="center")
        
        threading.Thread(target=self._scan_and_draw, daemon=True).start()

    def _scan_and_draw(self):
        stats = {}
        total_size = 0
        try:
            with os.scandir(self.path) as it:
                for entry in it:
                    if entry.is_file():
                        try:
                            size = entry.stat().st_size
                            _, ext = os.path.splitext(entry.name)
                            ext = ext.lower() if ext else "No Ext"
                            stats[ext] = stats.get(ext, 0) + size
                            total_size += size
                        except (OSError, PermissionError): pass
        except Exception: pass

        self.after(0, lambda: self._draw_pie_chart(stats, total_size))

    def _draw_pie_chart(self, stats, total_size):
        self.lbl_loading.destroy()
        if total_size == 0:
            # REASON FOR UPDATE: Added fill="black"
            self.canvas.create_text(300, 225, text="Folder is empty or inaccessible.", font=("Helvetica", 12), fill="black")
            return

        sorted_stats = sorted(stats.items(), key=lambda item: item[1], reverse=True)
        
        cx, cy = 200, 225
        radius = 150
        start_angle = 0
        lx, ly = 400, 50
        
        # REASON FOR UPDATE: Added fill="black" to title
        self.canvas.create_text(cx, 30, text="File Type Distribution (Size)", font=("Helvetica", 12, "bold"), fill="black")

        for ext, size in sorted_stats:
            percent = (size / total_size) * 360
            if percent < 1: continue 
            
            color = "#%02x%02x%02x" % (random.randint(100,255), random.randint(100,255), random.randint(100,255))
            
            self.canvas.create_arc(cx-radius, cy-radius, cx+radius, cy+radius, 
                                   start=start_angle, extent=percent, fill=color, outline="white")
            
            readable_pct = (size / total_size) * 100
            legend_text = f"{ext}: {readable_pct:.1f}%"
            
            self.canvas.create_rectangle(lx, ly, lx+15, ly+15, fill=color, outline="black")
            
            # REASON FOR UPDATE: Added fill="black" to legend text to ensure visibility
            self.canvas.create_text(lx+25, ly+7, text=legend_text, anchor="w", font=("Menlo", 9), fill="black")
            
            start_angle += percent
            ly += 20
            if ly > 400: break


class VisualizerLauncher(tk.Toplevel):
    def __init__(self, parent, root_path, generator_callback):
        super().__init__(parent)
        self.title("3D Network Configuration")
        self.geometry("600x600")
        self.root_path = root_path
        self.generator_callback = generator_callback
        
        # Data containers
        self.all_exts = set()
        self.all_folders = set()
        self.ext_vars = {}
        self.folder_vars = {}
        
        self._setup_ui()
        self._scan_metadata()

    def _setup_ui(self):
        # Header
        ttk.Label(self, text="Configure 3D Visualization", font=("Helvetica", 14, "bold")).pack(pady=10)
        
        # Split pane for Folders and Extensions
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Left: File Types
        left_frame = ttk.Labelframe(paned, text="File Types")
        paned.add(left_frame, weight=1)
        self.ext_canvas = self._create_scrollable_frame(left_frame)
        
        # Right: Folders
        right_frame = ttk.Labelframe(paned, text="Folders (Top Level)")
        paned.add(right_frame, weight=1)
        self.folder_canvas = self._create_scrollable_frame(right_frame)

        # Bottom: Actions
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        ttk.Button(btn_frame, text="Generate 3D Graph", command=self._on_generate).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Select All", command=self._select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Select None", command=self._select_none).pack(side=tk.LEFT, padx=5)

    def _create_scrollable_frame(self, parent):
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return scrollable_frame

    def _scan_metadata(self):
        """Quickly scans just the top level folders and all extensions."""
        try:
            for root, dirs, files in os.walk(self.root_path):
                # Folders
                if root == self.root_path:
                    for d in dirs: self.all_folders.add(d)
                
                # Extensions
                for f in files:
                    _, ext = os.path.splitext(f)
                    if ext: self.all_exts.add(ext.lower())
        except: pass
        
        self._populate_ui()

    def _populate_ui(self):
        # Populate Extensions
        for ext in sorted(self.all_exts):
            var = tk.BooleanVar(value=True)
            self.ext_vars[ext] = var
            chk = ttk.Checkbutton(self.ext_canvas.master.winfo_children()[0], text=ext, variable=var)
            chk.pack(anchor="w", padx=5)
            
        # Populate Folders
        for folder in sorted(self.all_folders):
            var = tk.BooleanVar(value=True)
            self.folder_vars[folder] = var
            chk = ttk.Checkbutton(self.folder_canvas.master.winfo_children()[0], text=f"/{folder}", variable=var)
            chk.pack(anchor="w", padx=5)

    def _select_all(self):
        for v in self.ext_vars.values(): v.set(True)
        for v in self.folder_vars.values(): v.set(True)

    def _select_none(self):
        for v in self.ext_vars.values(): v.set(False)
        for v in self.folder_vars.values(): v.set(False)

    def _on_generate(self):
        # Gather allowed items
        allowed_exts = {ext for ext, var in self.ext_vars.items() if var.get()}
        allowed_folders = {folder for folder, var in self.folder_vars.items() if var.get()}
        
        self.destroy()
        self.generator_callback(allowed_exts, allowed_folders)

class ConfigurableGraphGenerator:
    """Enhanced Graph Generator with Filtering, Snippet Extraction, and Threading."""
    def _analyze_relationships(self, nodes, file_nodes):
        """
        Scans code in file_nodes to find mentions of other file names 
        within the same project structure.
        """
        new_links = []
        # Map of base filename (without ext) to its node ID
        # e.g., 'auth' -> 105
        name_to_id = {os.path.splitext(n["name"])[0]: n["id"] for n in file_nodes}
        
        def scan_single_file(source_node):
            local_links = []
            try:
                # Limit scanning to text-based code files only
                if not source_node["name"].endswith(('.py', '.js', '.ts', '.java', '.cs', '.tf')):
                    return []
                
                with open(source_node["path"], "r", errors="ignore") as f:
                    content = f.read()
                    
                # Look for mentions of other "Planets" (files)
                for target_name, target_id in name_to_id.items():
                    if target_id == source_node["id"]:
                        continue
                    
                    # Regex check for word boundary to ensure it's a real reference
                    # e.g., 'import auth' or 'auth.login()'
                    if re.search(r'\b' + re.escape(target_name) + r'\b', content):
                        local_links.append({
                            "source": source_node["id"],
                            "target": target_id,
                            "width": 2,
                            "color": "#00FF00", # Bright green for logic links
                            "type": "logic_link",
                            "label": f"Logic: {source_node['name']} -> {target_name}"
                        })
            except:
                pass
            return local_links

        # REASON: Using ThreadPoolExecutor to prevent blocking the HTTP server or UI
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(scan_single_file, file_nodes))
            for res in results:
                new_links.extend(res)
                
        return new_links
    
    def generate_3d_view(self, root_path, allowed_exts, allowed_folders):
        graph_data = self._generate_data(root_path, allowed_exts, allowed_folders)
        
        with open("graph_data.json", "w") as f:
            json.dump(graph_data, f)
        with open("network_graph.html", "w") as f:
            f.write(self._get_html_template())
        return "network_graph.html"

    # REASON FOR UPDATE: Merged Planetary/Solar System Logic here.
    # Replaced the generic data generation with Star/Planet logic.
    def _generate_data(self, root_path, allowed_exts, allowed_folders):
        nodes = []
        links = []
        id_counter = 0
        path_map = {} 
        
        # SOLAR SYSTEM LOGIC: Ignore system folders for cleaner galaxy
        ignored_directories = {
            'node_modules', 'lib', 'libs', 'bin', 'obj', 'include', 'vendor', 
            'venv', 'env', '.git', '.idea', '.vscode', '__pycache__', 'dist', 'build'
        }

        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in ignored_directories]
            
            rel_path = os.path.relpath(root, root_path)
            top_level = rel_path.split(os.sep)[0]
            if top_level != "." and top_level not in allowed_folders:
                dirs[:] = [] 
                continue

            folder_id = path_map.get(root)
            if folder_id is None:
                folder_id = id_counter
                path_map[root] = folder_id
                id_counter += 1
                
                is_root = (root == root_path)
                star_size = 40 if is_root else 15
                star_color = "#FFFFE0" if is_root else "#FFFFFF"
                
                # FOLDER = STAR
                nodes.append({
                    "id": folder_id, 
                    "name": os.path.basename(root) if not is_root else "SUN (Root)", 
                    "val": star_size, 
                    "color": star_color, 
                    "type": "folder"
                })

            parent_dir = os.path.dirname(root)
            if parent_dir in path_map:
                links.append({
                    "source": path_map[parent_dir], 
                    "target": folder_id, 
                    "width": 1.5, 
                    "color": "#666666", 
                    "type": "gravity"
                })

            for f in files:
                _, ext = os.path.splitext(f)
                if ext.lower() not in allowed_exts: continue
                
                file_path = os.path.join(root, f)
                file_id = id_counter
                path_map[file_path] = file_id
                id_counter += 1
                
                color = self._get_color(ext)
                try: size = os.path.getsize(file_path) / 1024 
                except: size = 1
                visual_size = max(2, min(10, size**0.2))

                # FILE = PLANET
                nodes.append({
                    "id": file_id, 
                    "name": f, 
                    "val": visual_size, 
                    "color": color, 
                    "type": "file", 
                    "path": file_path
                })
                
                links.append({
                    "source": folder_id, 
                    "target": file_id, 
                    "width": 0.5, 
                    "color": "#333333", 
                    "type": "orbit"
                })
        # --- NEW LOGIC LINKS START HERE ---
        file_nodes = [n for n in nodes if n["type"] == "file"]
        # REASON: Run the code assessment to find inter-planetary logic threads
        logic_links = self._analyze_relationships(nodes, file_nodes)
        links.extend(logic_links)
        # ----------------------------------
        return {"nodes": nodes, "links": links}

    # REASON FOR UPDATE: Old _generate_data (Generic) logic commented out to preserve history
    # def _generate_data_OLD_GENERIC(self, root_path, allowed_exts, allowed_folders):
    #    # ... (Old generic logic that treated everything as nodes) ...
    #    pass

    def _get_color(self, ext):
        ext = ext.lower()
        if ext in ['.py', '.pyw']: return "#3776ab"
        if ext in ['.js', '.json', '.ts']: return "#f7df1e"
        if ext in ['.html', '.css', '.scss']: return "#e34c26"
        if ext in ['.md', '.txt', '.rst']: return "#dddddd"
        if ext in ['Dockerfile', 'dockerfile', '.yml', '.yaml']: return "#0db7ed"
        if ext in ['.tf', '.hcl']: return "#5f43e9"
        if ext in ['.c', '.cpp', '.h', '.hpp']: return "#00599C"
        if ext in ['.java', '.jar']: return "#b07219"
        return "#ff00ff"

    def _get_html_template(self):
        # REASON: Added linkDirectionalParticles and conditional coloring for Logic Links
        return r"""
        <!DOCTYPE html>
        <html>
        <head>
          <style> body { margin: 0; background: #000005; overflow: hidden; } </style>
          <script src="https://unpkg.com/three@0.160.0/build/three.js"></script>
          <script src="https://unpkg.com/3d-force-graph@1.73.2/dist/3d-force-graph.min.js"></script>
          <script src="https://unpkg.com/three-spritetext@1.8.1/dist/three-spritetext.min.js"></script>
        </head>
        <body>
          <div id="3d-graph"></div>
          <script>
            async function load() {
                const r = await fetch('graph_data.json?t=' + Date.now());
                const data = await r.json();
                
                const Graph = ForceGraph3D()(document.getElementById('3d-graph'))
                    .graphData(data)
                    .nodeLabel('name')
                    .nodeColor('color')
                    .nodeVal('val')
                    .nodeResolution(24)
                    /* REASON: Logic links are thicker and neon green; gravity/orbits remain subtle */
                    .linkWidth(l => l.type === 'logic_link' ? 2 : (l.type === 'gravity' ? 1 : 0.2))
                    .linkColor(l => l.type === 'logic_link' ? '#00FF00' : (l.type === 'gravity' ? '#555' : '#333'))
                    /* REASON: Added glowing particles to logic links to visualize code flow */
                    .linkDirectionalParticles(l => l.type === 'logic_link' ? 4 : 0)
                    .linkDirectionalParticleSpeed(0.01)
                    .linkDirectionalParticleWidth(2)
                    .backgroundColor('#000005')
                    .onNodeClick(node => {
                        const dist = 50;
                        const distRatio = 1 + dist/Math.hypot(node.x, node.y, node.z);
                        Graph.cameraPosition(
                            { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio }, 
                            node, 
                            3000
                        );
                    });

                Graph.d3Force('charge').strength(node => node.type === 'folder' ? -200 : -30);
                Graph.d3Force('link').distance(link => link.type === 'gravity' ? 100 : 30);
            }
            load();
          </script>
        </body>
        </html>
        """

class AuditManager:
    DB_FILE = "audit_conformity_db.json"

    def __init__(self):
        self.blueprints = self._load_db()

    def _load_db(self):
        if os.path.exists(self.DB_FILE):
            try:
                with open(self.DB_FILE, 'r') as f:
                    return json.load(f)
            except: return {}
        return {}

    def add_blueprint(self, name, code_block):
        self.blueprints[name] = code_block
        with open(self.DB_FILE, 'w') as f:
            json.dump(self.blueprints, f, indent=4)

    def get_all_titles(self):
        return list(self.blueprints.keys())

    def get_blueprint_code(self, title):
        return self.blueprints.get(title, "")

    def find_conformity(self, content):
        matches = []
        def get_tokens(text):
            return [(m.group(), m.start(), m.end()) for m in re.finditer(r'\S+', text)]

        content_tokens = get_tokens(content)
        if len(content_tokens) < 3: return []

        blueprint_ngrams = {}
        for title, code in self.blueprints.items():
            bp_tokens = get_tokens(code)
            if len(bp_tokens) < 3: continue
            for i in range(len(bp_tokens) - 2):
                t1, t2, t3 = bp_tokens[i][0], bp_tokens[i+1][0], bp_tokens[i+2][0]
                gram = f"{t1} {t2} {t3}"
                if gram not in blueprint_ngrams: blueprint_ngrams[gram] = set()
                blueprint_ngrams[gram].add(title)

        for i in range(len(content_tokens) - 2):
            t1, s1, _ = content_tokens[i]
            t2, _, _ = content_tokens[i+1]
            t3, _, e3 = content_tokens[i+2]
            gram = f"{t1} {t2} {t3}"
            if gram in blueprint_ngrams:
                for title in blueprint_ngrams[gram]:
                    matches.append({'start': s1, 'end': e3, 'title': title})
        return matches

class SyntaxHighlighter:
    COLORS = {
        "normal": "#d4d4d4",
        "background": "#1e1e1e",
        "keyword": "#569cd6", 
        "string": "#ce9178", 
        "comment": "#6a9955", 
        "number": "#b5cea8", 
        "class": "#4ec9b0", 
        "function": "#dcdcaa", 
        "decorator": "#dcdcaa",
        "audit_match": "#C586C0" 
    }

    def __init__(self, text_widget):
        self.text_widget = text_widget
        self._configure_tags()

    def _configure_tags(self):
        for name, color in self.COLORS.items():
            if name != "background":
                self.text_widget.tag_configure(name, foreground=color)
        
        self.text_widget.tag_configure("audit_match", background="#6a0dad", foreground="#ffffff", underline=True)

        self.text_widget.config(
            background=self.COLORS["background"],
            foreground=self.COLORS["normal"],
            insertbackground="white",
            selectbackground="#264f78",
            font=("Menlo", 10)
        )

    def highlight(self, content, file_extension):
        self.text_widget.config(state=tk.NORMAL)
        for tag in self.COLORS.keys():
            self.text_widget.tag_remove(tag, "1.0", tk.END)

        if file_extension in {'.py', '.pyw'}:
            self._highlight_python(content)
        elif file_extension in {'Dockerfile', '.sh', '.bash', '.zsh'}:
            self._highlight_shell(content)
        elif file_extension in {'.json', '.js'}:
            self._highlight_json_js(content)
        else:
            self._highlight_generic(content)
            
        self.text_widget.config(state=tk.DISABLED)

    def _apply_pattern(self, pattern, tag_name, content_str):
        for match in re.finditer(pattern, content_str, re.MULTILINE):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            self.text_widget.tag_add(tag_name, start, end)

    def _highlight_python(self, content):
        kw_pattern = r"\b(def|class|if|else|elif|return|import|from|try|except|finally|for|while|in|is|not|and|or|as|with|pass|lambda|global|raise|continue|break)\b"
        self._apply_pattern(kw_pattern, "keyword", content)
        self._apply_pattern(r"(?<=class\s)\w+", "class", content)
        self._apply_pattern(r"(?<=def\s)\w+", "function", content)
        self._apply_pattern(r"@\w+", "decorator", content)
        self._apply_pattern(r"\b\d+\b", "number", content)
        self._apply_pattern(r"(\".*?\"|'.*?')", "string", content)
        self._apply_pattern(r"#.*$", "comment", content)

    def _highlight_shell(self, content):
        kw_pattern = r"\b(if|fi|then|else|elif|for|do|done|while|case|esac|function|return|exit|echo|source|local|export)\b"
        self._apply_pattern(kw_pattern, "keyword", content)
        self._apply_pattern(r"(\".*?\"|'.*?')", "string", content)
        self._apply_pattern(r"#.*$", "comment", content)
        self._apply_pattern(r"\b\d+\b", "number", content)
        docker_kw = r"^(FROM|RUN|CMD|LABEL|MAINTAINER|EXPOSE|ENV|ADD|COPY|ENTRYPOINT|VOLUME|USER|WORKDIR|ARG|ONBUILD|STOPSIGNAL|HEALTHCHECK|SHELL)\b"
        self._apply_pattern(docker_kw, "keyword", content)

    def _highlight_json_js(self, content):
        kw_pattern = r"\b(true|false|null|var|let|const|function|return|if|else)\b"
        self._apply_pattern(kw_pattern, "keyword", content)
        self._apply_pattern(r"(\".*?\"|'.*?')", "string", content)
        self._apply_pattern(r"\b\d+\b", "number", content)
        self._apply_pattern(r"//.*$", "comment", content)

    def _highlight_generic(self, content):
        self._apply_pattern(r"(\".*?\"|'.*?')", "string", content)
        self._apply_pattern(r"\b\d+\b", "number", content)

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
                        item = self._create_item_dict_from_path(os.path.join(root, d))
                        if item: items.append(item)
                for f in files:
                    if query in f.lower():
                        item = self._create_item_dict_from_path(os.path.join(root, f))
                        if item: items.append(item)
                if len(items) > 2000: break 
        except Exception: pass
        return items

    def list_directory(self, path):
        items = []
        try:
            with os.scandir(path) as it:
                for entry in it:
                    item = self._create_item_dict(entry)
                    if item:
                        items.append(item)
        except PermissionError: return None
        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        return items

    def _create_item_dict(self, entry):
        try:
            stats = entry.stat()
            return self._format_item_data(entry.name, entry.path, entry.is_dir(), stats)
        except (FileNotFoundError, OSError):
            return None

    def _create_item_dict_from_path(self, path):
        try:
            stats = os.stat(path)
            return self._format_item_data(os.path.basename(path), path, os.path.isdir(path), stats)
        except (FileNotFoundError, PermissionError, OSError): 
            return None

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
        if not path or not os.path.exists(path): return "Info", "Item not found.", False
        if os.path.isdir(path):
            try: count = len(os.listdir(path))
            except: count = "?"
            return "Folder Info", f"Path: {path}\nContains: {count} items", False
        
        mime_type, _ = mimetypes.guess_type(path)
        try:
            stats = os.stat(path)
        except OSError:
            return "Error", "File inaccessible.", False

        header = f"File: {os.path.basename(path)}\nType: {mime_type or 'Unknown'}\nSize: {self._format_size(stats.st_size)}"
        
        text_extensions = {
            '.py', '.pyi', '.js', '.ts', '.html', '.css', '.scss', '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
            '.go', '.rs', '.java', '.cs', '.kt', '.c', '.cpp', '.h', '.hpp', '.clj', '.gradle',
            '.json', '.xml', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.properties', '.env', 
            '.hcl', '.tf', '.tfvars', '.tfstate',
            '.txt', '.md', '.rst', '.adoc', '.csv', '.log', '.patch', '.diff',
            '.gitignore', '.gitconfig', '.dockerignore', '.editorconfig', '.lock', '.mod', '.sum', '.work', 
            '.csproj', '.sln', '.pylintrc', '.npmrc', '.typed', '.pth',
            '.pem', '.pub', '.key', '.crt'
        }

        known_text_filenames = {
            'Dockerfile', 'Makefile', 'Jenkinsfile', 'Vagrantfile', 'Rakefile', 'Gemfile', 'Procfile',
            'LICENSE', 'README', 'NOTICE', 'AUTHORS', 'OWNERS', 'CONTRIBUTORS', 'PATENTS',
            'APACHE', 'BSD', 'COPYING', 'INSTALL',
            'METADATA', 'RECORD', 'WHEEL', 'INSTALLER', 'REQUESTED',
            'HEAD', 'config', 'description', 'exclude', 'packed-refs',
            'TAG', 'python-version'
        }
        
        filename = os.path.basename(path)
        _, ext = os.path.splitext(path)
        is_dotfile = filename.startswith('.')
        is_known_filename = filename in known_text_filenames
        is_extensionless_text = (not ext and stats.st_size < 1_000_000)

        should_try_read = (
            (mime_type and mime_type.startswith('text')) or 
            (ext.lower() in text_extensions) or 
            is_dotfile or 
            is_known_filename or 
            is_extensionless_text
        )

        binary_extensions = {'.gz', '.zip', '.tar', '.tgz', '.pyc', '.so', '.dylib', '.dll', '.class', '.exe', '.pack', '.idx', '.whl'}
        if ext.lower() in binary_extensions or filename == '.DS_Store' or filename == 'index':
            should_try_read = False

        if should_try_read:
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

class LiveServer(threading.Thread):
    def __init__(self, port):
        super().__init__(daemon=True)
        self.port = port
        self.httpd = None
    def run(self):
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, format, *args): pass 
            def end_headers(self):
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
                super().end_headers()
        try:
            socketserver.TCPServer.allow_reuse_address = True
            self.httpd = socketserver.ThreadingTCPServer(("127.0.0.1", self.port), Handler)
            self.httpd.serve_forever()
        except Exception as e: print(f"Server failed to start: {e}")

class ExplorerUI(ttk.Frame):
    def __init__(self, parent, logic_handler):
        super().__init__(parent)
        self.logic = logic_handler
        self.current_path = os.path.expanduser("~")
        self.is_searching = False; self.sort_reverse = False; self.running_threads = 0 
        self.cancel_event = threading.Event(); self.fav_file = "favorites.json"
        self.preview_offset = 0; self.current_preview_file = None
        self.audit_manager = AuditManager(); self.current_matches = []
        
        self.server_port = 8099
        self.server_thread = LiveServer(self.server_port)
        self.server_thread.start()
        
        self.graph_generator = ConfigurableGraphGenerator()
        
        self._setup_layout(); self._setup_menus(); self._setup_context_menu(); self._bind_events(); self._load_favorites() 
        self.highlighter = SyntaxHighlighter(self.txt_preview); self.audit_tip = ToolTip(self.txt_preview)
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
        self.mem_buttons = []
        self.mem_tips = []
        for i in range(4):
            btn = ttk.Button(mem_frame, text=f"[{i+1}] Empty", width=12)
            btn.pack(side=tk.LEFT, padx=2)
            btn.configure(command=lambda idx=i: self._jump_to_favorite(idx))
            btn.bind("<Button-2>", lambda e, idx=i: self._save_to_favorite(idx))
            btn.bind("<Button-3>", lambda e, idx=i: self._save_to_favorite(idx))
            self.mem_buttons.append(btn)
            self.mem_tips.append(ToolTip(btn, ""))

        self.paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        self.tree_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(self.tree_frame, weight=1)
        self.tree = ttk.Treeview(self.tree_frame, columns=("size", "modified"), selectmode="browse")
        self.tree.heading("#0", text="Name ↑↓", command=lambda: self._sort_column("#0"))
        self.tree.heading("size", text="Size ↑↓", command=lambda: self._sort_column("size"))
        self.tree.heading("modified", text="Date Modified ↑↓", command=lambda: self._sort_column("modified"))
        self.tree.column("#0", minwidth=200, width=300, stretch=True)
        self.tree.column("size", minwidth=60, width=80, anchor=tk.E)
        self.tree.column("modified", minwidth=100, width=120)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.preview_frame = ttk.Frame(self.paned_window, relief="sunken", padding=5)
        self.paned_window.add(self.preview_frame, weight=0)
        self.lbl_meta = ttk.Label(self.preview_frame, text="Select a file")
        self.lbl_meta.pack(fill=tk.X)
        self.copy_btn = ttk.Button(self.preview_frame, text="Copy", command=self.copy_preview_to_clipboard)
        self.text_container = ttk.Frame(self.preview_frame)
        self.text_container.pack(fill=tk.BOTH, expand=True)
        self.txt_preview = tk.Text(self.text_container, wrap="none", height=10, width=35, state=tk.DISABLED)
        self.txt_preview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.load_more_btn = ttk.Button(self.preview_frame, text="Load More...", command=self.load_next_chunk)

    def _setup_menus(self):
        menubar = tk.Menu(self.master)
        file_menu = tk.Menu(menubar, tearoff=0); file_menu.add_command(label="Exit", command=self.master.quit); menubar.add_cascade(label="File", menu=file_menu)
        
        db_menu = tk.Menu(file_menu, tearoff=0)
        db_menu.add_command(label="Add Database", command=self.wizard_add_to_db)
        db_menu.add_command(label="List Database", command=self.list_audit_db)
        file_menu.add_cascade(label="Database", menu=db_menu)
        
        vis_menu = tk.Menu(menubar, tearoff=0)
        vis_menu.add_command(label="Folder Composition", command=self.visualize_folder)
        vis_menu.add_command(label="3D Network", command=self.visualize_3d_network)
        menubar.add_cascade(label="Visualize", menu=vis_menu)
        self.master.config(menu=menubar)

    def visualize_folder(self):
        if self.current_path and os.path.exists(self.current_path): DirectoryVisualizer(self, self.current_path)
    
    def visualize_3d_network(self):
        if not self.current_path or not os.path.exists(self.current_path): messagebox.showerror("Error", "Invalid path."); return
        VisualizerLauncher(self, self.current_path, self._start_live_generation)
    
    def _start_live_generation(self, allowed_exts, allowed_folders):
        try:
            self.graph_generator.generate_3d_view(self.current_path, allowed_exts, allowed_folders)
            url = f"http://127.0.0.1:{self.server_port}/network_graph.html"
            self.after(1000, lambda: webbrowser.open(url))
            def update_loop():
                while True:
                    time.sleep(60); self.graph_generator.generate_3d_view(self.current_path, allowed_exts, allowed_folders)
            threading.Thread(target=update_loop, daemon=True).start()
        except Exception as e: messagebox.showerror("Error", f"Visualizer failed: {e}")

    def wizard_add_to_db(self):
        title = simpledialog.askstring("Add Database - Step 1/2", "Enter Title (Index Card):")
        if not title: return
        try: initial_code = self.txt_preview.get("sel.first", "sel.last")
        except tk.TclError: initial_code = ""
        win = tk.Toplevel(self)
        win.title("Add Code Blueprint")
        win.geometry("500x400")
        tk.Label(win, text="Paste/Edit Code Block to Match:", font=("Helvetica", 10, "bold")).pack(pady=5)
        txt = tk.Text(win, height=15, width=60, font=("Menlo", 10))
        txt.pack(padx=10, pady=5, expand=True, fill=tk.BOTH)
        txt.insert("1.0", initial_code)
        def on_save():
            code = txt.get("1.0", tk.END).strip()
            if code:
                self.audit_manager.add_blueprint(title, code)
                messagebox.showinfo("Success", f"Saved '{title}' to database.")
                self.run_audit_scan(self.txt_preview.get("1.0", tk.END))
            win.destroy()
        ttk.Button(win, text="Save", command=on_save).pack(pady=10)

    def list_audit_db(self):
        win = tk.Toplevel(self)
        win.title("Database Manager")
        win.geometry("400x500")
        list_frame = ttk.Frame(win, padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True)
        lb = tk.Listbox(list_frame, font=("Menlo", 10))
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        titles = sorted(self.audit_manager.get_all_titles())
        for t in titles: lb.insert(tk.END, t)
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=5)

    def run_audit_scan(self, content):
        target_file = self.current_preview_file 
        threading.Thread(target=self._threaded_audit_scan, args=(content, target_file), daemon=True).start()

    def _threaded_audit_scan(self, content, target_file):
        matches = self.audit_manager.find_conformity(content)
        self.after(0, lambda: self._apply_audit_results(matches, target_file))

    def _apply_audit_results(self, matches, target_file):
        if self.current_preview_file != target_file: return 
        self.current_matches = matches
        self.txt_preview.config(state=tk.NORMAL)
        self.txt_preview.tag_remove("audit_match", "1.0", tk.END)
        for m in matches:
            tk_start = f"1.0 + {m['start']} chars"
            tk_end = f"1.0 + {m['end']} chars"
            self.txt_preview.tag_add("audit_match", tk_start, tk_end)
        self.txt_preview.config(state=tk.DISABLED)

    def _on_text_motion(self, event):
        try:
            index = self.txt_preview.index(f"@{event.x},{event.y}")
            tags = self.txt_preview.tag_names(index)
            if "audit_match" in tags:
                count_res = self.txt_preview.count("1.0", index, "chars")
                current_char_idx = count_res[0] if count_res else 0
                matches_here = []
                for m in self.current_matches:
                    if m['start'] <= current_char_idx < m['end']: matches_here.append(m['title'])
                matches_here = list(set(matches_here))
                if matches_here:
                    titles = "\n".join(matches_here)
                    x = event.x_root + 15
                    y = event.y_root + 15
                    self.audit_tip.show_tip(x, y, titles)
                    return
            self.audit_tip.hide_tip()
        except Exception: self.audit_tip.hide_tip()

    def _load_favorites(self):
        if os.path.exists(self.fav_file):
            try:
                with open(self.fav_file, 'r') as f: self.favorites = json.load(f)
            except: self.favorites = {}
        else: self.favorites = {}
        self._update_mem_ui()
    def _save_to_favorite(self, idx):
        path = self.tree.focus() or self.current_path
        if not os.path.isdir(path): path = os.path.dirname(path)
        self.favorites[str(idx)] = path
        with open(self.fav_file, 'w') as f: json.dump(self.favorites, f)
        self._update_mem_ui()
    def _jump_to_favorite(self, idx):
        path = self.favorites.get(str(idx))
        if path and os.path.exists(path): self.load_path(path)
    def _update_mem_ui(self):
        for i in range(4):
            path = self.favorites.get(str(i))
            if path: self.mem_buttons[i].config(text=f"[{i+1}] {os.path.basename(path)[:10]}")
            else: self.mem_buttons[i].config(text=f"[{i+1}] Empty")

    def load_path(self, path):
        self.monitor.set_tasks(1)
        threading.Thread(target=lambda: self._finish_load(self.logic.list_directory(path), path), daemon=True).start()
    def _finish_load(self, items, path):
        if items is not None:
            self.current_path = path; self.path_var.set(path); self._populate_tree(items)
        self.monitor.set_tasks(0)

    def perform_search(self):
        q = self.search_var.get().strip()
        if not q: return
        self.clear_btn.config(state=tk.NORMAL)
        threading.Thread(target=lambda: self._finish_search(self.logic.search_files(self.current_path, q)), daemon=True).start()
    def _finish_search(self, res):
        if res is not None: self._populate_tree(res)
    def clear_search(self):
        self.search_var.set(""); self.clear_btn.config(state=tk.DISABLED); self.load_path(self.current_path)

    def _setup_context_menu(self):
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="Reveal in Finder/Explorer", command=self.reveal_in_finder)
        self.context_menu.add_command(label="Copy Path", command=self.copy_path_to_clipboard)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Open Terminal Here", command=self.open_terminal_at_selection)
        self.context_menu.add_command(label="Refresh Folder", command=lambda: self.load_path(self.current_path))
    
    def reveal_in_finder(self):
        path = self.tree.focus()
        if path: subprocess.run(["open", "-R", path])
    def copy_path_to_clipboard(self):
        path = self.tree.focus()
        if path: self.clipboard_clear(); self.clipboard_append(path)
    def open_terminal_at_selection(self):
        path = self.tree.focus()
        if path:
            target = path if os.path.isdir(path) else os.path.dirname(path)
            subprocess.run(["open", "-a", "Terminal", target])

    def _bind_events(self):
        self.tree.bind("<Double-1>", lambda e: self._on_dbclick())
        self.tree.bind("<Return>", lambda e: self._on_dbclick())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_preview(self.tree.focus()))
        self.search_entry.bind("<Return>", lambda e: self.perform_search())
        self.tree.bind("<Button-2>", self._show_ctx)
        self.tree.bind("<Button-3>", self._show_ctx)
        self.txt_preview.bind("<Motion>", self._on_text_motion)

    def _show_ctx(self, e):
        row = self.tree.identify_row(e.y)
        if row: self.tree.selection_set(row); self.context_menu.post(e.x_root, e.y_root)
    def _on_dbclick(self):
        sid = self.tree.focus()
        if sid and os.path.isdir(sid):
            if self.is_searching: self.clear_search()
            self.load_path(sid)
    
    def update_preview(self, path):
        self.preview_offset = 0; self.current_preview_file = path; self.load_more_btn.pack_forget(); self.copy_btn.pack_forget(); self.txt_preview.config(state=tk.NORMAL); self.txt_preview.delete(1.0, tk.END)
        if not path: self.lbl_meta.config(text="No Selection"); self.txt_preview.config(state=tk.DISABLED); return
        h, c, has_more = self.logic.get_preview_content(path, self.preview_offset)
        self.lbl_meta.config(text=h); self.txt_preview.insert(tk.END, c)
        
        _, ext = os.path.splitext(path)
        if os.path.basename(path) in {'Dockerfile', 'Makefile', 'Jenkinsfile'}: ext = 'Dockerfile'
        self.highlighter.highlight(c, ext)
        self.run_audit_scan(c)
        
        self.txt_preview.config(state=tk.DISABLED)
        if c and not c.startswith("["): self.copy_btn.pack(side=tk.RIGHT)
        if has_more: self.load_more_btn.pack(side=tk.BOTTOM, fill=tk.X, pady=2); self.preview_offset += self.logic.CHUNK_SIZE

    def load_next_chunk(self):
        if not self.current_preview_file: return
        h, c, has_more = self.logic.get_preview_content(self.current_preview_file, self.preview_offset)
        self.txt_preview.config(state=tk.NORMAL)
        self.txt_preview.insert(tk.END, "\n" + "-"*10 + " [Next Chunk] " + "-"*10 + "\n")
        self.txt_preview.insert(tk.END, c)
        full_content = self.txt_preview.get("1.0", tk.END)
        _, ext = os.path.splitext(self.current_preview_file)
        self.highlighter.highlight(full_content, ext)
        self.run_audit_scan(full_content)
        self.txt_preview.config(state=tk.DISABLED); self.txt_preview.see(tk.END)
        if not has_more: self.load_more_btn.pack_forget()
        else: self.preview_offset += self.logic.CHUNK_SIZE

    def copy_preview_to_clipboard(self):
        content = self.txt_preview.get(1.0, tk.END)
        if content.strip(): self.clipboard_clear(); self.clipboard_append(content)

    def _sort_column(self, col):
        children = self.tree.get_children(''); self.sort_reverse = not self.sort_reverse
        def nk(t): return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', str(t))]
        if col == "#0": s_items = sorted(children, key=lambda i: nk(self.tree.item(i, 'text')), reverse=self.sort_reverse)
        else: s_items = sorted(children, key=lambda i: nk(self.tree.set(i, col)), reverse=self.sort_reverse)
        for idx, iid in enumerate(s_items): self.tree.move(iid, '', idx)

    def _populate_tree(self, items):
        for i in self.tree.get_children(): self.tree.delete(i)
        self.update_preview(None)
        if items:
            for itm in items:
                d_name = f"📁 {itm['name']}" if itm['is_dir'] else f"📄 {itm['name']}"
                self.tree.insert("", tk.END, iid=itm['path'], text=d_name, values=(itm['size'], itm['modified']))

    def go_up(self):
        if self.is_searching: self.clear_search()
        else:
            p = os.path.dirname(self.current_path)
            if p and os.path.exists(p): self.load_path(p)

if __name__ == "__main__":
    root = tk.Tk(); root.title("MacExplorer Pro"); root.geometry("1100x650")
    app = ExplorerUI(root, FileSystemHandler()); root.mainloop()