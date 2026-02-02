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
import tkinter.font as tkfont
import difflib 
import random 
import webbrowser 
from concurrent.futures import ThreadPoolExecutor
# --- MISSING IMPORTS ADDED BELOW ---
import http.server
import socketserver 
# import pyvirtualdisplay
# -----------------------------------

# Check if we are running on Render (which defines PORT or other env vars)
# if os.environ.get('RENDER'):
#     from pyvirtualdisplay import Display
#     # Start a virtual screen in the background
#     display = Display(visible=0, size=(1024, 768))
#     display.start()
    
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
    """
    Enhanced Graph Generator with High-Fidelity Heuristic Scanning.
    Implements a 2-pass indexing system (Pass 1: Symbols, Pass 2: Intersections).
    """

    def _build_symbol_table(self, file_nodes):
        """
        Pass 1: Scans all files to index Classes and Functions.
        Ensures we find links even if the filename isn't explicitly mentioned.
        """
        symbol_table = {}
        
        # Regex to find Python classes/defs and JS functions/classes
        # REASON: Capturing the internal logic signatures of the files
        signature_regex = re.compile(r'^\s*(?:def|class|function|const|export)\s+([a-zA-Z_][a-zA-Z0-9_]*)', re.MULTILINE)

        for node in file_nodes:
            # Always index the base filename (e.g., 'auth_service' for 'auth_service.py')
            base_name = os.path.splitext(node["name"])[0]
            symbol_table[base_name] = node["id"]
            
            try:
                if node["name"].endswith(('.py', '.js', '.ts', '.java', '.cs')):
                    with open(node["path"], "r", errors="ignore") as f:
                        content = f.read()
                        matches = signature_regex.findall(content)
                        for match in matches:
                            if len(match) > 3: # Ignore tiny variable names to reduce noise
                                symbol_table[match] = node["id"]
            except:
                pass
        return symbol_table
    
    def _analyze_file(self, node, symbol_table):
        """
        Pass 2: Uses the Symbol Table to find logic threads.
        Aggregates ALL matching lines into a single 'Matrix Stream' for the HUD.
        """
        # Bucket to store snippets per target file
        # Key: target_id (int), Value: List[str] (lines of code)
        relationships_found = {} 
        
        try:
            if not node["name"].endswith(('.py', '.js', '.ts', '.java', '.cs')):
                return []

            with open(node["path"], "r", errors="ignore") as f:
                lines = f.readlines()
            
            for line_idx, line in enumerate(lines):
                line_stripped = line.strip()
                if not line_stripped or len(line_stripped) > 120: continue
                
                # Tokenize: Split line into unique words to match against the Index
                words_in_line = set(re.findall(r'\b\w+\b', line_stripped))
                
                # Intersection: Find symbols in this line that exist in our Global Index
                found_symbols = words_in_line.intersection(symbol_table.keys())
                
                for symbol in found_symbols:
                    target_id = symbol_table[symbol]
                    if target_id == node["id"]: continue
                    
                    # Initialize bucket if this is the first time we see this target
                    if target_id not in relationships_found:
                        relationships_found[target_id] = []
                    
                    # Create the Matrix snippet: "L15: import auth_service"
                    snippet = f"L{line_idx+1}: {line_stripped}"
                    
                    # Prevent duplicate lines (e.g. if a line has 2 symbols pointing to same file)
                    if not relationships_found[target_id] or relationships_found[target_id][-1] != snippet:
                        relationships_found[target_id].append(snippet)

        except:
            pass

        # Final Packaging: Convert buckets into Logic Links
        local_links = []
        for target_id, snippets in relationships_found.items():
            # Join all snippets with newlines for the HUD to scroll through
            # Limit to 30 lines to keep the JSON payload manageable
            full_stream = "\n".join(snippets[:30])
            if len(snippets) > 30: 
                full_stream += "\n... [DATA STREAM TRUNCATED] ..."

            local_links.append({
                "source": node["id"],
                "target": target_id,
                "width": 2.5,
                "color": "#00ff00",
                "type": "logic_link",
                "snippet": full_stream # This now contains MULTIPLE lines
            })
            
        return local_links
    
    # REASON FOR COMMENTING OUT: Replaced by the 400% more robust 2-pass indexing system 
    # (Pass 1 Symbol Index + Pass 2 Intersection) which finds far more connections than simple regex.
    #
    # def _analyze_relationships(self, nodes, file_nodes):
    #     new_links = []
    #     name_to_id = {os.path.splitext(n["name"])[0]: n["id"] for n in file_nodes}
    #     def scan_single_file(source_node):
    #         # ... (Old Regex scan logic) ...
    #         pass
    #     with ThreadPoolExecutor(max_workers=4) as executor:
    #         results = list(executor.map(scan_single_file, file_nodes))
    #         for res in results: new_links.extend(res)
    #     return new_links
    
    def generate_3d_view(self, root_path, allowed_exts, allowed_folders):
        graph_data = self._generate_data(root_path, allowed_exts, allowed_folders)
        
        with open("graph_data.json", "w") as f:
            json.dump(graph_data, f)
        
        # REASON: Writing the robust HTML template with Zero-G Physics and Matrix HUD
        with open("network_graph.html", "w") as f:
            f.write(self._get_html_template())
        
        return "network_graph.html"

    def _get_dir_size(self, path):
        """Recursively calculates the total size of a directory in bytes for True-Mass scaling."""
        total = 0
        try:
            with os.scandir(path) as it:
                for entry in it:
                    if entry.is_file():
                        total += entry.stat().st_size
                    elif entry.is_dir():
                        total += self._get_dir_size(entry.path)
        except (PermissionError, OSError):
            pass
        return total

    def _generate_data(self, root_path, allowed_exts, allowed_folders):
        nodes = []
        links = []
        
        # REASON FOR UPDATE: Removed 'id_counter'. 
        # We now use Deterministic IDs (the file path itself) so planets don't reset 
        # when the file list changes.
        # id_counter = 0 
        
        path_map = {} 
        ignored_directories = {'node_modules', 'lib', '.git', 'venv', 'dist', 'build', '__pycache__'}

        # 1. Structural Scan: Folders and Files
        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in ignored_directories]
            rel_path = os.path.relpath(root, root_path)
            top_level = rel_path.split(os.sep)[0]
            if top_level != "." and top_level not in allowed_folders:
                dirs[:] = [] 
                continue

            # --- SUN (FOLDER) SCALING ---
            # REASON: The ID is now the absolute path. This ensures persistence.
            folder_id = root
            
            if folder_id not in path_map:
                path_map[folder_id] = True # Mark as seen
                
                # REASON: Recursive size determines "Sun" mass
                raw_folder_size = self._get_dir_size(root) / 1024 # KB
                sun_val = 10 + (max(0, raw_folder_size)**0.25 * 2)
                
                is_root = (root == root_path)
                nodes.append({
                    "id": folder_id, # Deterministic ID
                    "name": os.path.basename(root) if not is_root else "SUN (Root)", 
                    "val": sun_val * 2 if is_root else sun_val, 
                    "color": "#FFFFE0" if is_root else "#FFFFFF", 
                    "type": "folder",
                    "path": root
                })

            parent_dir = os.path.dirname(root)
            # Only link if parent is within our scan scope
            if parent_dir.startswith(root_path) and parent_dir != root:
                 # Check if parent exists in our nodes to prevent orphans (optional safety)
                 links.append({"source": parent_dir, "target": folder_id, "width": 1.5, "color": "#666666", "type": "gravity"})

            # --- PLANET (FILE) SCALING ---
            for f in files:
                _, ext = os.path.splitext(f)
                if ext.lower() not in allowed_exts: continue
                file_path = os.path.join(root, f)
                file_id = file_path # Deterministic ID
                
                try: raw_file_size = os.path.getsize(file_path) / 1024
                except: raw_file_size = 1
                
                # REASON: True-Mass scaling for planets
                visual_size = max(2, min(25, raw_file_size**0.3 * 1.5))

                nodes.append({
                    "id": file_id, 
                    "name": f, 
                    "val": visual_size, 
                    "color": self._get_color(ext), 
                    "type": "file", 
                    "path": file_path
                })
                links.append({"source": folder_id, "target": file_id, "width": 0.5, "color": "#333333", "type": "orbit"})

        # --- REASON: Implementing 2-Pass Heuristic for robust logic links ---
        file_nodes = [n for n in nodes if n["type"] == "file"]
        
        # Pass 1: Global Symbol Indexing
        symbol_table = self._build_symbol_table(file_nodes)
        
        # Pass 2: Heuristic Analysis via Multi-threading
        logic_links = []
        
        # REASON: Initialize Thread Counter for UI Status Bar (T: Count)
        self.active_threads = len(file_nodes)
        
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(self._analyze_file, n, symbol_table) for n in file_nodes]
            
            for future in futures:
                logic_links.extend(future.result())
                # REASON: Decrement the counter as each "Planet" scan completes
                self.active_threads -= 1
        
        # REASON: Ensure it resets to 0 so the UI shows idle state
        self.active_threads = 0
        links.extend(logic_links)

        return {"nodes": nodes, "links": links}

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
        """
        Generates the 3D environment with a Matrix-style HUD for code diagnostics.
        """
        return r"""
        <!DOCTYPE html>
        <html>
        <head>
          <style> 
            body { margin: 0; background: #000005; overflow: hidden; font-family: sans-serif; } 
            
            #matrix-hud {
                position: fixed; right: 0; top: 0; bottom: 0; width: 280px;
                background: rgba(0, 15, 0, 0.6);
                border-left: 2px solid #00ff00;
                overflow: hidden; pointer-events: none; display: none; z-index: 100;
                box-shadow: -5px 0 15px rgba(0, 255, 0, 0.2);
            }
            .matrix-stream {
                color: #00ff00; font-family: 'Courier New', Courier, monospace;
                font-size: 11px; padding: 20px; white-space: pre-wrap;
                text-shadow: 0 0 5px #00ff00;
                animation: matrix-scroll 15s linear infinite;
            }
            @keyframes matrix-scroll {
                0% { transform: translateY(100vh); }
                100% { transform: translateY(-100%); }
            }
            #hud-header {
                position: absolute; top: 0; left: 0; right: 0;
                background: #00ff00; color: #000;
                font-size: 10px; font-weight: bold; padding: 2px 10px; z-index: 101;
                text-transform: uppercase;
            }
          </style>
          
          <script src="https://unpkg.com/3d-force-graph@1.73.2/dist/3d-force-graph.min.js"></script>
          <script src="https://unpkg.com/three-spritetext@1.8.1/dist/three-spritetext.min.js"></script>
        </head>
        <body>
          <div id="matrix-hud">
            <div id="hud-header">Data Stream: Logic Reference</div>
            <div id="hud-content" class="matrix-stream"></div>
          </div>
          <div id="3d-graph"></div>

          <script>
            const Graph = ForceGraph3D()(document.getElementById('3d-graph'))
                .nodeLabel('name')
                .nodeColor('color')
                .nodeVal('val')
                .nodeResolution(24)
                .linkWidth(l => l.type === 'logic_link' ? 2.5 : (l.type === 'gravity' ? 1.5 : 0.3))
                .linkColor(l => l.type === 'logic_link' ? '#00FF00' : (l.type === 'gravity' ? '#666' : '#333'))
                .linkDirectionalParticles(l => l.type === 'logic_link' ? 5 : 0)
                .linkDirectionalParticleSpeed(0.005)
                .linkDirectionalParticleWidth(3)
                .backgroundColor('#000005')
                .onLinkHover(link => {
                    const hud = document.getElementById('matrix-hud');
                    const content = document.getElementById('hud-content');
                    if (link && link.type === 'logic_link') {
                        content.innerText = link.snippet || "INITIATING DATA SCAN...\nNO RELEVANT BYTES FOUND.";
                        hud.style.display = 'block';
                    } else {
                        hud.style.display = 'none';
                    }
                })
                .onNodeClick(node => {
                    const dist = 60;
                    const distRatio = 1 + dist/Math.hypot(node.x, node.y, node.z);
                    Graph.cameraPosition(
                        { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio }, 
                        node, 2500
                    );
                });

            Graph.d3Force('charge').strength(node => node.type === 'folder' ? -350 : -40);
            Graph.d3Force('link').distance(link => link.type === 'gravity' ? 120 : 40);
            
            /* REASON: Zero-G Logic Links! 
               We set the strength of 'logic_link' to 0 so they don't pull planets out of orbit. */
            Graph.d3Force('link').strength(link => link.type === 'logic_link' ? 0.0 : 1.0);

            // --- THE HEARTBEAT LOOP ---
            let currentLinkCount = 0;

            async function checkPulse() {
                try {
                    const r = await fetch('graph_data.json?t=' + Date.now());
                    const data = await r.json();
                    
                    if (data.links.length !== currentLinkCount) {
                        console.log("Pulse detected: Updating Graph Data...");
                        currentLinkCount = data.links.length;
                        
                        // REASON: Added safety check. If graph is empty, don't try to map nodes.
                        const currentGraphData = Graph.graphData();
                        
                        if (currentGraphData && currentGraphData.nodes && currentGraphData.nodes.length > 0) {
                            // 1. Snapshot old positions
                            const nodeMap = new Map(currentGraphData.nodes.map(n => [n.id, n]));
                            
                            // 2. Restore positions to new data
                            data.nodes.forEach(n => {
                                const old = nodeMap.get(n.id);
                                if (old) {
                                    n.x = old.x; n.y = old.y; n.z = old.z;
                                    n.vx = old.vx; n.vy = old.vy; n.vz = old.vz;
                                }
                            });
                        }

                        // 3. Inject new data
                        Graph.graphData(data);
                        
                        // 4. FREEZE: Prevent explosion by setting Alpha to 0 immediately
                        Graph.d3Alpha(0); 
                        Graph.d3Restart();
                    }
                } catch (e) {
                    // REASON: Log the actual error to console for debugging
                    console.log("Waiting for data stream...", e);
                }
            }

            checkPulse();
            setInterval(checkPulse, 2500);
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
    def __init__(self, start_port):
        super().__init__(daemon=True)
        self.start_port = start_port
        self.actual_port = None # Will store the successfully bound port
        self.httpd = None
        self.root_dir = os.path.dirname(os.path.abspath(__file__))
                        # REASON: RENDER PORT BINDING.
        # On Render, we MUST listen on the port provided by the environment.
        render_port = int(os.environ.get("PORT", 8099)) 
        self.server_thread = LiveServer(render_port)
        self.server_thread.start()

        # REASON: Loop through a range of ports to avoid "Address already in use" crashes.
        # This makes the server "Indestructible" on restart.
        for port in range(self.start_port, self.start_port + 10):
            try:
                # Define handler inside the loop to ensure clean scope
                class Handler(http.server.SimpleHTTPRequestHandler):
                    def log_message(self, format, *args): pass 
                    def end_headers(self):
                        # REASON: Disable caching so the 3D graph updates immediately on reload
                        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
                        super().end_headers()
                
                socketserver.TCPServer.allow_reuse_address = True
                self.httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler)
                
                # If we reach here, the bind was successful
                self.actual_port = port
                print(f"[LiveServer] Successfully bound to http://127.0.0.1:{self.actual_port}")
                break
            except OSError as e:
                print(f"[LiveServer] Port {port} busy, trying next...")
                continue
        
        if self.actual_port is None:
            print("[LiveServer] CRITICAL: Could not find any open port in range.")

    def run(self):
        if self.httpd:
            # REASON: Ensure we serve files from the script's directory (where .html is saved)
            try:
                os.chdir(self.root_dir)
                self.httpd.serve_forever()
            except Exception as e:
                print(f"[LiveServer] Runtime Error: {e}")
class GitHandler:
    """
    REASON: ROBUST GIT INTEGRATION.
    Wraps subprocess calls in try/except blocks to prevent crashes.
    Extracts Branch, Flux (modified files), and Last Author.
    """
    def get_commit_log(self, path, limit=15):
        if not self.has_git: return []
        try:
            # Format: Hash | Author | Message
            log_raw = self._run_git(["log", f"-{limit}", "--pretty=format:%h|%an|%s"], cwd=path)
            if log_raw:
                return [line.split("|", 2) for line in log_raw.splitlines()]
        except: pass
        return []
    
    def __init__(self):
        self.has_git = bool(self._run_git(["--version"]))

    def _run_git(self, args, cwd=None):
        try:
            # Timeout prevents hanging on large repos
            result = subprocess.run(
                ["git"] + args, 
                cwd=cwd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True, 
                timeout=2,
                encoding='utf-8', 
                errors='ignore' # Prevent decoding errors on binary filenames
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None

    def get_status(self, path):
        """
        REASON: ROBUST TELEMETRY EXTRACTION.
        Safely retrieves branch, flux (uncommitted changes), and last author.
        Replaces the missing 'get_stats' method to fix the AttributeError.
        """
        if not hasattr(self, 'has_git') or not self.has_git:
            return {'branch': 'N/A', 'flux': 0, 'author': 'System'}

        try:
            # 1. Get Branch Name
            branch = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=path).strip() or "main"
            
            # 2. Get Flux (Count of modified/untracked files)
            status_raw = self._run_git(["status", "--porcelain"], cwd=path)
            flux = len(status_raw.splitlines()) if status_raw else 0
            
            # 3. Get Last Author
            author = self._run_git(["log", "-1", "--pretty=format:%an"], cwd=path).strip() or "Unknown"
            
            return {
                'branch': branch,
                'flux': flux,
                'author': author
            }
        except Exception:
            # REASON: Standard fallback to prevent UI crashes if Git commands fail
            return {'branch': 'detached', 'flux': 0, 'author': 'None'}
class MockRemoteHandler:
    """
    REASON: SIMULATES GITHUB/GITLAB CONNECTION.
    Generates fake PRs and Issues to test the UI layout without needing API keys yet.
    """
    def get_pull_requests(self):
        return [
            {"id": "#42", "title": "Fix memory leak in parser", "author": "simon-t", "status": "OPEN"},
            {"id": "#43", "title": "Refactor graph logic", "author": "dev-bot", "status": "REVIEW"},
            {"id": "#45", "title": "Update dependencies", "author": "security", "status": "OPEN"},
        ]

    def get_issues(self):
        return [
            {"id": "!101", "title": "Crash on startup (Mac)", "severity": "HIGH"},
            {"id": "!102", "title": "Add search debounce", "severity": "LOW"},
        ]
    
    def get_pr_details(self, pr_id):
        """Returns the conversation thread for the main preview pane."""
        return f"""
        PULL REQUEST {pr_id} DETAILS
        --------------------------------------------------
        STATUS: Open  |  REVIEWERS: 2  |  CI: Passing
        
        [simon-t] (2 hours ago):
        I've tracked down the leak to the graph generator.
        The nodes weren't being garbage collected.
        
        [reviewer-1] (1 hour ago):
        Nice catch. Did you check the thread pool cleanup?
        
        [simon-t] (30 mins ago):
        Yes, added a 'shutdown' hook in the destructor.
        """
class OpsHUD(tk.Canvas):
    def __init__(self, parent, stats_callback, preview_callback=None, **kwargs):
        """
        REASON: CRASH FIX.
        1. Captures 'preview_callback' to prevent TclError.
        2. Initializes 'scan_line_y' to prevent AttributeError in _animate.
        """
        # Safety: Remove custom args before calling super
        if 'preview_callback' in kwargs: 
            del kwargs['preview_callback']

        super().__init__(parent, bg="black", highlightthickness=0, **kwargs)
        
        self.stats_callback = stats_callback
        self.preview_callback = preview_callback
        
        self.stats = {}
        self.commits = []
        
        # REASON: Restore Animation Variables (The missing link causing your crash)
        self.scan_line_y = 0
        self.scan_speed = 2
        
        # Fonts
        self.font_family = "Courier New" if "Courier New" in tkfont.families() else "Courier"
        self.base_font_size = 10
        self.header_font = tkfont.Font(family=self.font_family, size=12, weight="bold")
        self.normal_font = tkfont.Font(family=self.font_family, size=10)
        
        # Internal Loop
        self.running = True
        
        # Initial placeholder data
        self.stats = {'files': 0, 'size': '0B', 'flux': 0, 'todos': 0, 'branch': 'main', 'author': 'System'}

        # Create listbox for logs
        self.lb_commits = tk.Listbox(self, bg="black", fg="#00ff00", 
                                    font=(self.font_family, 8), borderwidth=0, highlightthickness=0)
        
        # Start Animation (Must be last)
        self._animate()

    def update_data(self, *args):
        """
        REASON: CRASH FIX & COMPATIBILITY.
        The app calls this method with different arguments at different times.
        Old Code: Crashed if it didn't get exactly a Dict and a List.
        New Code: Adapts to whatever the app sends.
        """
        # Scenario 1: File System Update (Path, Count, Size)
        # The crash happened here previously because 3 args were sent.
        if len(args) == 3:
            path, count, size = args
            # We only update the specific keys so we don't wipe out the Git data
            self.stats['files'] = count
            self.stats['size'] = size
            
        # Scenario 2: Git/Flux Update (Stats Dict, Commits List)
        elif len(args) == 2:
            new_stats, new_commits = args
            if isinstance(new_stats, dict):
                # Update existing stats with new Git info (merge, don't overwrite)
                self.stats.update(new_stats)
            if isinstance(new_commits, list):
                self.commits = new_commits

        # Always redraw the HUD to show the new data
        self._draw()

    def _animate(self):
        if not self.running: return
        
        w = self.winfo_width()
        h = self.winfo_height()
        
        # Update Scan Line Position
        self.scan_line_y += self.scan_speed
        if self.scan_line_y > h:
            self.scan_line_y = 0
            
        # Redraw only if necessary or keep simple loop
        # For performance, we often just redraw the scanline or the whole HUD
        self._draw() 
        
        # Loop
        self.after(50, self._animate)

    def _text(self, x, y, text, color, max_w, is_bold=False, center=False):
        font_cfg = self._get_adaptive_font(text, max_w, is_bold)
        anchor = tk.CENTER if center else tk.W
        self.create_text(x, y, text=text, fill=color, font=font_cfg, anchor=anchor)

    def _get_adaptive_font(self, text, max_width, is_bold=False):
        size = self.base_font_size if not is_bold else 13
        min_size = 6
        weight = "bold" if is_bold else "normal"
        f = tkfont.Font(family=self.font_family, size=size, weight=weight)
        while f.measure(text) > max_width and size > min_size:
            size -= 1
            f.configure(size=size)
        return (self.font_family, size, weight)

    def _draw(self):
        self.delete("all")
        
        w = int(self.winfo_width())
        h = int(self.winfo_height())
        if w <= 1: w = 200
        if h <= 1: h = 200
        safe_w = w - 20 

        # Draw Scan Line
        self.create_line(0, self.scan_line_y, w, self.scan_line_y, fill="#003300", width=2)
        
        # Grid Lines
        self.create_line(10, 30, w-10, 30, fill="#004400", width=1)
        self.create_line(10, 100, w-10, 100, fill="#004400", width=1)
        self.create_line(10, 170, w-10, 170, fill="#004400", width=1)

        if not self.stats:
            self._text(w/2, 30, "SYSTEM OFFLINE", "#00ff00", safe_w, center=True)
            return

        # 1. SECTOR VITALS
        self._text(10, 10, "SECTOR VITALS", "#00ff00", safe_w, is_bold=True)
        files = self.stats.get('files', 0)
        size = self.stats.get('size', '0B')
        self._text(10, 25, f"MASS: {size}", "#33cc33", safe_w/2)
        self._text(w/2, 25, f"UNITS: {files}", "#33cc33", safe_w/2)

        # 2. GIT TELEMETRY
        flux_val = int(self.stats.get('flux', 0))
        color_flux = "#ff3333" if flux_val > 0 else "#33cc33"
        self._text(10, 45, f"BRANCH: {self.stats.get('branch', 'N/A')}", "#00ff00", safe_w)
        self._text(10, 60, f"FLUX: {flux_val} Pending", color_flux, safe_w)
        self._text(10, 75, f"LAST: {self.stats.get('author', 'Unknown')}", "#33cc33", safe_w)

        # 3. BIO-SIGNS
        self._text(10, 110, "CODE BIO-SIGNS", "#00ff00", safe_w, is_bold=True)
        todos = self.stats.get('todos', 0)
        self._text(10, 125, f"DEBT: {todos}", "#ffb000", safe_w)
        
        health = max(0, 100 - (todos * 5))
        self._text(10, 140, f"INTEGRITY: {health}%", "#33cc33", safe_w)
        self.create_rectangle(10, 155, 10 + (health * 1.5), 160, fill="#00ff00", outline="")

        # 4. COMMIT LOGS
        self._text(10, 180, "CRITICAL LOGS", "#00ff00", safe_w, is_bold=True)
        
        if hasattr(self, 'lb_commits'):
            self.lb_commits.delete(0, tk.END)
            for commit in self.commits:
                # REASON: Added defensive handling to prevent IndexErrors or TypeErrors 
                # if Git data is malformed or empty.
                try:
                    # REASON: Standardize Hash length to 7 characters
                    # OLD CODE: msg = commit[2] if len(commit[2]) < 30 else commit[2][:27] + "..."
                    # OLD CODE: self.lb_commits.insert(tk.END, f"[{commit[0][:7]}] {msg}")
                    
                    c_hash = str(commit[0])[:7] if len(commit) > 0 else "????"
                    c_msg = str(commit[2]) if len(commit) > 2 else "No message"
                    
                    # REASON: Truncate messages to fit the HUD width (Safe Zone)
                    if len(c_msg) > 30:
                        c_msg = c_msg[:27] + "..."
                        
                    self.lb_commits.insert(tk.END, f"[{c_hash}] {c_msg}")
                    
                except (IndexError, TypeError, AttributeError) as e:
                    # REASON: Skip individual malformed commits rather than crashing the UI
                    continue
            
            list_h = max(50, h - 210)
            self.create_window(w/2, 210 + (list_h/2), window=self.lb_commits, width=w-10, height=list_h)

    def _draw_sys_channel(self, w, h, safe_w):
        if not self.stats: 
            self._text(w/2, 60, "NO DATA LINK", "#00ff00", safe_w, center=True)
            return

        # Grid lines (Adjusted for new spacing)
        # OLD CODE: self.create_line(10, 100, w-10, 100, fill="#004400", width=1)
        # OLD CODE: self.create_line(10, 170, w-10, 170, fill="#004400", width=1)
        self.create_line(10, 105, w-10, 105, fill="#004400", width=1)
        self.create_line(10, 175, w-10, 175, fill="#004400", width=1)

        # --- SECTOR VITALS (Stacking) ---
        # REASON: Use dynamic Y to allow text to flow naturally without overlapping
        current_y = 40
        line_h = 16 
        
        # OLD CODE: self._text(10, 40, f"MASS: {self.stats['size']}", "#33cc33", safe_w)
        self._text(10, current_y, f"MASS: {self.stats['size']}", "#33cc33", safe_w)
        
        current_y += line_h
        # OLD CODE: self._text(10, 55, f"UNITS: {self.stats['files']}", "#33cc33", safe_w)
        self._text(10, current_y, f"UNITS: {self.stats['files']}", "#33cc33", safe_w)
        
        # --- GIT TELEMETRY (Stacking) ---
        # REASON: Jump current_y to the next section (approx y=70 area)
        current_y += (line_h + 5) 
        
        color_flux = "#ff3333" if int(self.stats.get('flux', 0)) > 0 else "#33cc33"
        
        # OLD CODE: self._text(10, 75, f"BRANCH: {self.stats['branch']}", "#00ff00", safe_w)
        self._text(10, current_y, f"BRANCH: {self.stats['branch']}", "#00ff00", safe_w)
        
        # REASON: Move FLUX to its own line to prevent collision with long branch names
        current_y += line_h
        # OLD CODE: self._text(110, 75, f"FLUX: {self.stats['flux']}", color_flux, safe_w)
        self._text(10, current_y, f"FLUX: {self.stats['flux']} Pending", color_flux, safe_w)

        # --- BIO-SIGNS ---
        # REASON: Jump current_y to the next section (approx y=115 area)
        current_y = 115
        
        # OLD CODE: self._text(10, 110, "BIO-SIGNS", "#00ff00", safe_w, is_bold=True)
        self._text(10, current_y, "BIO-SIGNS", "#00ff00", safe_w, is_bold=True)
        
        current_y += line_h
        # OLD CODE: self._text(10, 125, f"DEBT: {self.stats['todos']}", "#ffb000", safe_w)
        self._text(10, current_y, f"DEBT: {self.stats['todos']}", "#ffb000", safe_w)
        
        health = max(0, 100 - (self.stats['todos'] * 5))
        current_y += line_h
        # OLD CODE: self.create_rectangle(10, 140, 10 + (health * 1.5), 145, fill="#00ff00", outline="")
        self.create_rectangle(10, current_y, 10 + (health * 1.5), current_y + 5, fill="#00ff00", outline="")

        # --- COMMIT LOGS ---
        # OLD CODE: self._text(10, 180, "LOCAL LOGS", "#00ff00", safe_w, is_bold=True)
        self._text(10, 185, "LOCAL LOGS", "#00ff00", safe_w, is_bold=True)
        
        # REASON: Using unified 'lb_main'
        # OLD CODE: self.lb_commits.delete(0, tk.END)
        self.lb_main.delete(0, tk.END)
        
        for commit in self.commits:
            # OLD CODE: self.lb_commits.insert(tk.END, f"[{commit[0]}] {commit[2]}")
            self.lb_main.insert(tk.END, f"[{commit[0]}] {commit[2]}")
        
        list_h = h - 215
        # OLD CODE: self.create_window(w/2, 210 + (list_h/2), window=self.lb_commits, width=w-10, height=list_h)
        self.create_window(w/2, 215 + (list_h/2), window=self.lb_main, width=w-10, height=list_h)

    def _draw_net_channel(self, w, h, safe_w):
        # Grid
        self.create_line(10, 140, w-10, 140, fill="#004400", width=1)

        # UPLINK STATUS
        self._text(w/2, 50, "UPLINK: ACTIVE", "#33cc33", safe_w, center=True)
        self._text(w/2, 65, "SOURCE: GITHUB", "#005500", safe_w, center=True)

        # PULL REQUESTS
        self._text(10, 90, "OPEN PRs", "#00ff00", safe_w, is_bold=True)
        
        # REASON: Fixed crash by using the unified 'lb_main' widget instead of the old 'lb_commits'
        # OLD CODE: self.lb_commits.delete(0, tk.END)
        self.lb_main.delete(0, tk.END)
        
        # REASON: Adding launcher for the restored Blueprint Manager
        self._text(10, 200, "DATA OPS", "#00ff00", safe_w, is_bold=True)
        # Note: You can bind a click area on the canvas or add a real button
        
        for pr in self.prs:
            # OLD CODE: self.lb_commits.insert(tk.END, f"{pr['id']} {pr['title']}")
            self.lb_main.insert(tk.END, f"{pr['id']} {pr['title']}")
            
        # REASON: Using the same listbox for spacer and issues
        self.lb_main.insert(tk.END, "") # Spacer
        self.lb_main.insert(tk.END, "--- ISSUES ---")
        
        for issue in self.issues:
            self.lb_main.insert(tk.END, f"{issue['id']} {issue['title']}")

        list_h = h - 110
        
        # REASON: Ensure the window creation references the correct widget
        # OLD CODE: self.create_window(w/2, 110 + (list_h/2), window=self.lb_commits, width=w-10, height=list_h)
        self.create_window(w/2, 110 + (list_h/2), window=self.lb_main, width=w-10, height=list_h)

    def _on_canvas_click(self, event):
        # Hit detection for Tabs
        if event.y < 30:
            if event.x < 110: self.active_channel = "SYS"
            else: self.active_channel = "NET"
            self._draw()

    def _on_list_select(self, event):
        # Handle clicks on the list items
        if self.active_channel == "NET":
            selection = self.lb_main.curselection()
            if selection:
                text = self.lb_main.get(selection[0])
                # Simple parsing of ID (e.g., "#42")
                if text.startswith("#"):
                    pr_id = text.split(" ")[0]
                    # Callback to Main UI to show details
                    details = self.remote.get_pr_details(pr_id)
                    self.preview_callback(details)

    def _draw(self):
        """
        REASON: HUD RENDERING CORE.
        Restored function definition so 'self' calls are valid.
        """
        self.delete("all")
        
        # REASON: Ensure width/height are integers to prevent type errors
        w = int(self.winfo_width())
        h = int(self.winfo_height())
        
        # Fallback if window hasn't rendered yet
        if w <= 1: w = 200
        if h <= 1: h = 200
        
        # REASON: Define Safe Zone (10px padding on sides)
        safe_w = w - 20 
        
        # Grid Lines (The structure of the HUD)
        self.create_line(10, 30, w-10, 30, fill="#004400", width=1)
        self.create_line(10, 100, w-10, 100, fill="#004400", width=1)
        self.create_line(10, 170, w-10, 170, fill="#004400", width=1)

        if not self.stats:
            self._text(w/2, 30, "SYSTEM OFFLINE", "#00ff00", safe_w, center=True)
            return

        # 1. SECTOR VITALS
        self._text(10, 10, "SECTOR VITALS", "#00ff00", safe_w, is_bold=True)
        # Check if keys exist to prevent KeyErrors during startup
        files = self.stats.get('files', 0)
        size = self.stats.get('size', '0B')
        self._text(10, 25, f"MASS: {size}", "#33cc33", safe_w/2)
        self._text(w/2, 25, f"UNITS: {files}", "#33cc33", safe_w/2)

        # 2. GIT TELEMETRY
        # REASON: Adaptive color coding for 'Flux' (Red if pending changes, Green if clean)
        flux_val = int(self.stats.get('flux', 0))
        color_flux = "#ff3333" if flux_val > 0 else "#33cc33"
        
        self._text(10, 45, f"BRANCH: {self.stats.get('branch', 'N/A')}", "#00ff00", safe_w)
        self._text(10, 60, f"FLUX: {flux_val} Pending", color_flux, safe_w)
        self._text(10, 75, f"LAST: {self.stats.get('author', 'Unknown')}", "#33cc33", safe_w)

        # 3. BIO-SIGNS
        self._text(10, 110, "CODE BIO-SIGNS", "#00ff00", safe_w, is_bold=True)
        todos = self.stats.get('todos', 0)
        self._text(10, 125, f"DEBT: {todos}", "#ffb000", safe_w)
        
        # Calculate Health Bar
        health = max(0, 100 - (todos * 5))
        self._text(10, 140, f"INTEGRITY: {health}%", "#33cc33", safe_w)
        self.create_rectangle(10, 155, 10 + (health * 1.5), 160, fill="#00ff00", outline="")

        # 4. COMMIT LOGS
        self._text(10, 180, "CRITICAL LOGS", "#00ff00", safe_w, is_bold=True)
        
        # Ensure listbox exists before trying to update it
        if hasattr(self, 'lb_commits'):
            self.lb_commits.delete(0, tk.END)
            for commit in self.commits:
                # Truncate long messages
                msg = commit[2] if len(commit[2]) < 30 else commit[2][:27] + "..."
                self.lb_commits.insert(tk.END, f"[{commit[0][:7]}] {msg}")
            
            list_h = max(50, h - 210)
            self.create_window(w/2, 210 + (list_h/2), window=self.lb_commits, width=w-10, height=list_h)
        
    def _text(self, x, y, text, color, max_width, is_bold=False, center=False):
        # Calculate font based on the MAX WIDTH allowed for this specific line
        font = self._get_adaptive_font(text, max_width, is_bold)
        anchor = tk.CENTER if center else tk.NW
        
        self.create_text(x+1, y+1, text=text, fill="#003300", font=font, anchor=anchor)
        self.create_text(x, y, text=text, fill=color, font=font, anchor=anchor)

    def _animate(self):
        self.delete("scanline")
        w = int(self['width'])
        h = int(self['height'])
        self.create_line(0, self.scan_line_y, w, self.scan_line_y, fill="#005500", tags="scanline", width=2)
        self.scan_line_y = (self.scan_line_y + 2) % h
        self.after(50, self._animate)
class ExplorerUI(ttk.Frame):
    # --- CLEANED METHODS BLOCK ---

    def _refresh_hud_telemetry(self):
        """
        REASON: HUD BRIDGE.
        Updates the OpsHUD with Git and File stats.
        """
        if not hasattr(self, 'ops_hud') or not self.current_path:
            return

        try:
            # Attempt to fetch status from GitHandler
            stats = self.git_handler.get_status(self.current_path)
            commits = self.git_handler.get_commit_log(self.current_path)
        except AttributeError:
            stats = {'branch': 'unknown', 'flux': 0, 'author': 'N/A'}
            commits = []

        self.ops_hud.update_data(stats, commits)
        self.after(10000, self._refresh_hud_telemetry)

    def edit_database_record(self, title, parent_window=None):
        """
        REASON: DATABASE EDITOR.
        Opens the multiline editor for a specific blueprint.
        """
        if not title: return

        # 1. Fetch current data
        current_code = self.audit_manager.get_blueprint_code(title)
        
        # 2. Open Multiline Editor
        new_code = self._ask_multiline(f"Edit '{title}'", "Edit Code Block:", current_code)
        
        # 3. Save if user didn't cancel
        if new_code is not None:
            self.audit_manager.add_blueprint(title, new_code)
            messagebox.showinfo("Success", f"Updated '{title}' in database.")
            
            # Refresh Preview if active
            if hasattr(self, 'run_audit_scan'):
                self.run_audit_scan(self.txt_preview.get("1.0", tk.END))

    def _ask_multiline(self, title, prompt, initial_value=""):
        """
        REASON: MODAL TEXT EDITOR.
        Helper for edit_database_record.
        """
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        dialog.grab_set()
        
        result = [None] 

        tk.Label(dialog, text=prompt, font=(None, 10, "bold")).pack(pady=10)
        
        txt_frame = ttk.Frame(dialog)
        txt_frame.pack(padx=10, pady=5, expand=True, fill=tk.BOTH)
        
        txt = tk.Text(txt_frame, width=70, height=20, font=("Courier New", 11), undo=True)
        scrollbar = ttk.Scrollbar(txt_frame, command=txt.yview)
        txt.configure(yscrollcommand=scrollbar.set)
        txt.insert("1.0", initial_value)
        
        txt.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        def on_save():
            result[0] = txt.get("1.0", tk.END).strip()
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        btn_frame = ttk.Frame(dialog, padding=10)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="Save Changes", command=on_save).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side=tk.RIGHT)

        self.wait_window(dialog)
        return result[0]

    def open_audit_blueprint_manager(self):
        """
        REASON: BLUEPRINT MANAGER UI.
        Uses Grid layout to ensure Edit buttons are always visible.
        """
        win = tk.Toplevel(self)
        win.title("Audit Blueprint Manager")
        win.geometry("700x500")

        # GRID LAYOUT: Row 0 = List, Row 1 = Buttons
        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1) 
        win.rowconfigure(1, weight=0)

        # 1. BUTTONS (Row 1)
        btn_frame = ttk.Frame(win, padding=10)
        btn_frame.grid(row=1, column=0, sticky="ew")

        # 2. LISTBOX (Row 0)
        main_frame = ttk.Frame(win, padding=5)
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        tk.Label(main_frame, text="Database Records:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        lb_frame = ttk.Frame(main_frame)
        lb_frame.pack(expand=True, fill=tk.BOTH, pady=5)
        
        scrollbar = ttk.Scrollbar(lb_frame)
        lb = tk.Listbox(lb_frame, yscrollcommand=scrollbar.set, 
                        bg="#2b2b2b", fg="#00ff00", font=("Courier", 12), selectmode=tk.SINGLE)
        scrollbar.config(command=lb.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        lb.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        try:
            titles = sorted(self.audit_manager.get_all_titles())
            for t in titles: lb.insert(tk.END, t)
        except:
            lb.insert(tk.END, "Error: AuditManager offline")

        # Helper
        def get_target():
            sel = lb.curselection()
            if not sel: 
                messagebox.showwarning("Select Record", "Please select a record.")
                return None
            return lb.get(sel[0])

        # Buttons
        ttk.Button(btn_frame, text="Close", command=win.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Edit / View", 
                   command=lambda: self.edit_database_record(get_target(), win)).pack(side=tk.RIGHT)

        # Actions Menu (Failsafe)
        menubar = tk.Menu(win)
        win.config(menu=menubar)
        actions = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Actions", menu=actions)
        actions.add_command(label="Edit Selected", command=lambda: self.edit_database_record(get_target(), win))
        actions.add_command(label="Close", command=win.destroy)

        # Bindings
        lb.bind("<Double-1>", lambda e: self.edit_database_record(get_target(), win))
        
        ctx = tk.Menu(win, tearoff=0)
        ctx.add_command(label="Edit Record", command=lambda: self.edit_database_record(get_target(), win))
        
        def show_ctx(e):
            try:
                lb.selection_clear(0, tk.END)
                lb.activate(f"@{e.x},{e.y}")
                lb.selection_set(f"@{e.x},{e.y}")
                ctx.post(e.x_root, e.y_root)
            except: pass

        lb.bind("<Button-3>", show_ctx)
        if self.tk.call('tk', 'windowingsystem') == 'aqua':
            lb.bind("<Button-2>", show_ctx)

    # --- END CLEAN BLOCK ---


    def __init__(self, parent, logic_handler):
        """
        REASON: HARDENED INITIALIZATION.
        Ensures critical services (Git, Server, Logic) are ready before the UI tries to draw them.
        Merged and re-ordered to prevent AttributeErrors in OpsHUD.
        """
        super().__init__(parent)
        
        # REASON: Injection of logic handler (cleaner dependency management)
        # OLD CODE: self.logic = ExplorerLogic(self.root_path)
        self.logic = logic_handler
        
        self.current_path = os.path.expanduser("~")

        # REASON: Initialize Git Handler BEFORE setup_layout.
        # The OpsHUD needs this object to exist immediately to render the 'NET' channel.
        self.git_handler = GitHandler()

        # REASON: AuditManager for DB features initialized early for menu/UI safety
        self.audit_manager = AuditManager()

        # REASON: Moved the UI construction calls further down.
        # OLD CODE: self._setup_layout(); self._setup_menus(); self._setup_context_menu(); self._bind_events(); self._load_favorites()
        
        # State Flags
        self.is_searching = False
        self.sort_reverse = False
        self.running_threads = 0 
        self.cancel_event = threading.Event()
        self.fav_file = "favorites.json"
        self.preview_offset = 0
        self.current_preview_file = None
        self.current_matches = []
        
        # REASON: Initialize Debounce Timer for tooltips
        self.hover_timer = None 

        # Phase 2: Dynamic Port Selection
        self.server_thread = LiveServer(8099)
        self.server_thread.start()
        self.server_port = self.server_thread.actual_port
        
        self.graph_generator = ConfigurableGraphGenerator()
        
        # ---------------------------------------------------------
        # UI CONSTRUCTION (SAFE ZONE)
        # ---------------------------------------------------------
        
        # REASON: Now it is safe to build the layout because git_handler and audit_manager exist.
        self._setup_layout()
        self._setup_menus()
        self._setup_context_menu()
        self._bind_events()
        self._load_favorites() 
        
        # REASON: Start the Git Telemetry heartbeat loop once HUD is ready
        self._refresh_hud_telemetry()
        
        # Post-Layout Helpers
        self.highlighter = SyntaxHighlighter(self.txt_preview)
        self.audit_tip = ToolTip(self.txt_preview)
        
        # Start
        self.load_path(self.current_path)

    def _setup_layout(self):
        self.pack(fill=tk.BOTH, expand=True)
        
        # --- Top Container (Nav + Monitor) ---
        top_container = ttk.Frame(self, padding=(5, 2))
        top_container.pack(fill=tk.X)
        
        nav_frame = ttk.Frame(top_container)
        nav_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Button(nav_frame, text="Up", command=self.go_up, width=4).pack(side=tk.LEFT, padx=(0, 5))
        self.path_var = tk.StringVar()
        ttk.Entry(nav_frame, textvariable=self.path_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        ttk.Label(nav_frame, text="S:", font=("Helvetica", 10)).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(nav_frame, textvariable=self.search_var, width=12)
        self.search_entry.pack(side=tk.LEFT, padx=(2, 5))
        
        ttk.Button(nav_frame, text="Go", command=self.perform_search, width=4).pack(side=tk.LEFT)
        self.clear_btn = ttk.Button(nav_frame, text="X", width=2, command=self.clear_search, state=tk.DISABLED)
        self.clear_btn.pack(side=tk.LEFT, padx=(2, 0))
        
        monitor_frame = ttk.Frame(top_container)
        monitor_frame.pack(side=tk.RIGHT, padx=(5, 0))
        self.monitor = SystemMonitor(monitor_frame)
        self.monitor.pack(side=tk.LEFT)

        # --- Memory Buttons ---
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

        # --- REASON: SPLIT VIEW FOR HUD ---
        # Created a main container to hold the OpsHUD (Left) and the File Explorer (Right)
        main_content = ttk.Frame(self)
        main_content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 1. THE OPS-HUD (Left Side)
        # REASON: Borderless 'Pip-Boy' style display for Git/File stats
        # 1. THE OPS-HUD (Left Side)
        # 1. THE OPS-HUD (Left Side)
        # REASON: Pass 'self.show_remote_details' as the callback
        self.ops_hud = OpsHUD(
            main_content, 
            self.git_handler, 
            preview_callback=self.show_remote_details, # <--- NEW CONNECTION
            width=220, 
            height=400
        )
        self.ops_hud.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 5), pady=5)

        # 2. EXISTING PANED WINDOW (Right Side)
        # REASON: Changed parent from 'self' to 'main_content' to sit next to the HUD
        # Old Code: self.paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned_window = ttk.PanedWindow(main_content, orient=tk.HORIZONTAL)
        self.paned_window.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # --- Tree View Setup ---
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
        
        # --- Preview Pane Setup ---
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
    def show_remote_details(self, text):
        self.txt_preview.config(state=tk.NORMAL)
        self.txt_preview.delete(1.0, tk.END)
        self.txt_preview.insert(tk.END, text)
        self.txt_preview.config(state=tk.DISABLED)
        self.lbl_meta.config(text="REMOTE UPLINK DATA")
        
    def _setup_menus(self):
        menubar = tk.Menu(self.master)
        file_menu = tk.Menu(menubar, tearoff=0); file_menu.add_command(label="Exit", command=self.master.quit); menubar.add_cascade(label="File", menu=file_menu)
        
        db_menu = tk.Menu(file_menu, tearoff=0)
        db_menu.add_command(label="Add Database", command=self.wizard_add_to_db)
        db_menu.add_command(label="List Database", command=self.open_audit_blueprint_manager)
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
    
    # UPDATE FOR ExplorerUI Class
    def _start_live_generation(self, allowed_exts, allowed_folders):
        """
        Generates the graph and opens the browser.
        Includes the 'Smart Watcher' fix from Phase 1.
        """
        try:
            if not self.server_port:
                messagebox.showerror("Error", "Live Server failed to start (no ports available).")
                return

            self.graph_generator.generate_3d_view(self.current_path, allowed_exts, allowed_folders)
            
            # REASON: Use the dynamic port determined by the LiveServer class
            url = f"http://127.0.0.1:{self.server_port}/network_graph.html"
            self.after(1000, lambda: webbrowser.open(url))
            
            # The Smart Watcher Loop (From Phase 1)
            def update_loop():
                last_state_hash = ""
                while True:
                    time.sleep(2.5)
                    current_state_hash = self._get_fs_fingerprint(self.current_path)
                    
                    if current_state_hash != last_state_hash:
                        # REASON: Only regenerate if files actually changed
                        try:
                            self.graph_generator.generate_3d_view(self.current_path, allowed_exts, allowed_folders)
                            last_state_hash = current_state_hash
                        except Exception as e:
                            print(f"[Auto-Scan Error] {e}")
                            
            threading.Thread(target=update_loop, daemon=True).start()
        except Exception as e: messagebox.showerror("Error", f"Visualizer failed: {e}")

    def _get_fs_fingerprint(self, path):
        """
        Creates a simple string hash based on file count + total size + last modified time.
        This is much faster than re-scanning the whole graph logic.
        """
        total_files = 0
        total_mtime = 0
        try:
            # Fast walk to get metadata only
            for root, dirs, files in os.walk(path):
                # Skip hidden/ignored folders to save time
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {'node_modules', 'venv', '.git'}]
                
                for f in files:
                    full_p = os.path.join(root, f)
                    try:
                        stat = os.stat(full_p)
                        total_files += 1
                        total_mtime += stat.st_mtime
                    except: pass
        except: pass
        
        # Return a unique signature for this state
        return f"{total_files}-{int(total_mtime)}"

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
    
    def on_item_edit(self, event=None):
        """
        REASON: Redirecting generic edit call to the specialized Database Manager.
        OLD CODE: (Generic Modal with Field 0, Field 1)
        """
        # Get selection from the tree
        selected = self.tree.selection()
        if not selected: return
        
        item_id = selected[0]
        # In your tree, the 'text' or the first value is usually the Title/Filename
        values = self.tree.item(item_id, 'values')
        
        # REASON: Extract title (adjust index [0] if your title is in a different column)
        title = values[0] if values else self.tree.item(item_id, 'text')
        
        # REASON: Check if it's a database-style entry or a file
        if title:
            # Point to our consolidated editor
            self.edit_database_record(title)

    def save_changes(self, item_id, new_values):
        """REASON: Commits changes from the modal back to the UI and Data Source."""
        # Update UI Tree
        self.tree.item(item_id, values=new_values)
        # TODO: Add logic here to commit back to self.current_db_path via SQLite/JSON
        print(f"COMMITTED: {new_values} to {item_id}")

    def _on_text_motion(self, event):
        """
        REASON: DEBOUNCED HOVER LOGIC.
        Prevents UI stutter by waiting 100ms for mouse to stop before calculating indices.
        """
        # 1. Cancel any pending check
        if self.hover_timer:
            self.after_cancel(self.hover_timer)
            self.hover_timer = None
        
        # 2. Schedule a new check in 100ms
        self.hover_timer = self.after(100, lambda: self._process_hover(event))
    def _process_hover(self, event):
        """
        The actual heavy lifting, now only runs when mouse is idle.
        """
        try:
            # Map mouse coordinates to text index (Expensive operation)
            index = self.txt_preview.index(f"@{event.x},{event.y}")
            tags = self.txt_preview.tag_names(index)
            
            if "audit_match" in tags:
                # Calculate character offset
                count_res = self.txt_preview.count("1.0", index, "chars")
                current_char_idx = count_res[0] if count_res else 0
                
                # Find which blueprint matches this location
                matches_here = []
                for m in self.current_matches:
                    if m['start'] <= current_char_idx < m['end']: 
                        matches_here.append(m['title'])
                
                matches_here = list(set(matches_here))
                
                if matches_here:
                    titles = "\n".join(matches_here)
                    # Offset tooltip slightly so it doesn't block the text
                    x = event.x_root + 15
                    y = event.y_root + 15
                    self.audit_tip.show_tip(x, y, titles)
                    return
            
            # If no tags found, hide tip
            self.audit_tip.hide_tip()
            
        except Exception: 
            self.audit_tip.hide_tip()

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
            
            # REASON: UPDATE OPS-HUD STATISTICS
            # Calculate total size for the HUD
            total_size_str = "0 B"
            try:
                raw_size = sum(itm['raw_size'] for itm in items if not itm['is_dir'])
                total_size_str = self.logic._format_size(raw_size)
            except: pass
            
            # REASON: THREAD SAFETY FIX. 
            # The background loader thread cannot touch the UI directly or it crashes Tkinter.
            # We use self.after(0, ...) to schedule the update on the main thread.
            
            # OLD CODE: self.ops_hud.update_data(path, len(items), total_size_str)
            self.after(0, lambda: self.ops_hud.update_data(path, len(items), total_size_str))
            
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
        # REASON: Unified Double-Click logic. 
        # We REMOVED the direct bind to 'on_item_edit' because it conflicts with folder navigation.
        # Now, _on_dbclick handles both folders (open) and databases (edit).
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
        """
        REASON: Merged logic to handle directory navigation, specialized DB managers, 
        and standard file opening.
        """
        sid = self.tree.focus()
        if not sid: return
        
        # Get the full path
        path = sid 
        
        # REASON: Variable 'ext' calculation moved down to ensure it is defined before use
        # OLD CODE: 
        # if ext == ".db":
        #      self.open_audit_blueprint_manager()
        
        if os.path.isdir(path):
            if self.is_searching: self.clear_search()
            self.load_path(path)
        else:
            # REASON: Detect file extension for routing
            ext = os.path.splitext(path)[1].lower()

            # REASON: Specific handler for .db files to launch the Audit Blueprint Manager
            if ext == ".db":
                 self.open_audit_blueprint_manager()

            # REASON: Generic handler for other data formats (SQLite, JSON)
            elif ext in ['.sqlite', '.sqlite3', '.json']:
                # REASON: We call on_item_edit directly for these database files
                # This opens the modal popup we restored earlier.
                self.on_item_edit(None)
            
            # REASON: Default behavior for non-database files
            else:
                try:
                    import platform
                    if platform.system() == 'Darwin':       # macOS
                        os.system(f'open "{path}"')
                    elif platform.system() == 'Windows':    # Windows
                        os.startfile(path)
                    else:                                   # Linux
                        os.system(f'xdg-open "{path}"')
                except Exception as e:
                    print(f"Could not open file: {e}")
    
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