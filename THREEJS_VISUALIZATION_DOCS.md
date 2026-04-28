# Three.js Code Visualization Architecture
## Complete Migration Guide for Code Explorer 3D Network Visualizer

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Data Pipeline](#data-pipeline)
4. [Client-Side Rendering](#client-side-rendering)
5. [Physics & Force Simulation](#physics--force-simulation)
6. [User Interaction](#user-interaction)
7. [Animation System](#animation-system)
8. [Server & Auto-Refresh](#server--auto-refresh)
9. [Visual Design](#visual-design)
10. [Migration Checklist](#migration-checklist)

---

## System Overview

The Code Explorer 3D Network Visualizer is a **solar system metaphor** visualization that displays code dependencies as an interactive 3D force-directed graph.

### Core Metaphor
- **Folders** = Stars ("Suns") with repulsive charge
- **Files** = Planets orbiting folders
- **Logic Links** = Zero-G communication beams (aesthetic only, no force)
- **File/Folder Size** = Mass (determines visual size via cubic root scaling)

### Key Statistics
- **Frontend Library**: 3d-force-graph v1.73.2 (WebGL wrapper around Three.js)
- **Physics Engine**: D3.js Force Simulation
- **Text Rendering**: three-spritetext v1.8.1
- **Language Support**: Python, JavaScript, TypeScript, Java, C#, C/C++
- **Refresh Interval**: 2.5 seconds (auto-detect file changes)
- **Thread Workers**: 8 (for parallel code analysis)

---

## Architecture

### File Structure
```
Code_Explorer/
├── explorer.py                    # Main application (2220 lines)
├── network_graph.html             # Generated 3D visualization HTML/JS
├── graph_data.json                # Generated node/link data (sent to browser)
├── LiveServer                     # HTTP server (ports 8099-8108)
└── ConfigurableGraphGenerator     # Data generation pipeline
```

### Core Components

#### 1. **ConfigurableGraphGenerator** (explorer.py:258-504)
Responsible for scanning code, building symbol tables, and generating graph data.

**Key Methods:**
- `generate_3d_view()` - Entry point for 3D visualization
- `_generate_data()` - Orchestrates the complete data pipeline
- `_build_symbol_table()` - Pass 1: Index all classes/functions/exports
- `_analyze_file()` - Pass 2: Find code dependencies via word intersection
- `_get_color()` - Maps file extensions to hex colors
- `_get_dir_size()` - Recursive directory size calculation

#### 2. **LiveServer** (explorer.py:948-998)
Multi-threaded HTTP server with smart port binding.

**Features:**
- Tries ports 8099-8108 automatically (port collision resistant)
- Disables browser caching (`Cache-Control: no-store`)
- Serves from script directory only
- Daemon thread (exits with main app)
- LAN-accessible (listens on 0.0.0.0, not localhost)

#### 3. **ForceGraph3D** (network_graph.html:44-79)
Client-side 3D renderer wrapper. Uses 3d-force-graph library which abstracts Three.js.

**Internal Three.js Setup** (abstracted by library):
- Perspective camera
- WebGL renderer
- Scene with near-black background (#000005)
- Automatic viewport handling

---

## Data Pipeline

### Phase 1: Filesystem Traversal
**Location**: `explorer.py:409-465`

```python
# Structural Scan: Folders and Files
for root, dirs, files in os.walk(root_path):
    # 1. Create folder nodes ("Suns")
    folder_id = root  # Deterministic ID = absolute path
    raw_folder_size = self._get_dir_size(root) / 1024  # KB
    sun_val = 10 + (max(0, raw_folder_size)**0.25 * 2)
    
    nodes.append({
        "id": folder_id,
        "name": os.path.basename(root),
        "val": sun_val,  # Size for physics
        "color": "#FFFFFF",  # White for subdirs, #FFFFE0 for root
        "type": "folder",
        "path": root
    })
    
    # 2. Create "gravity" links (folder → subfolder)
    links.append({
        "source": parent_dir,
        "target": folder_id,
        "type": "gravity",
        "width": 1.5,
        "color": "#666666"
    })
    
    # 3. Create file nodes ("Planets")
    for f in files:
        file_id = os.path.join(root, f)  # Deterministic ID
        raw_file_size = os.path.getsize(file_path) / 1024
        visual_size = max(2, min(25, raw_file_size**0.3 * 1.5))
        
        nodes.append({
            "id": file_id,
            "name": f,
            "val": visual_size,  # Clamped 2-25
            "color": self._get_color(ext),
            "type": "file",
            "path": file_path
        })
        
        # 4. Create "orbit" links (folder → files)
        links.append({
            "source": folder_id,
            "target": file_id,
            "type": "orbit",
            "width": 0.5,
            "color": "#333333"
        })
```

### Phase 2: Symbol Table Indexing (Pass 1)
**Location**: `explorer.py:264-290`

```python
def _build_symbol_table(self, file_nodes):
    """
    Index all classes, functions, and exports by name.
    Enables dependency detection beyond simple filename matching.
    """
    symbol_table = {}
    
    # Regex to capture function/class definitions
    signature_regex = re.compile(
        r'^\s*(?:def|class|function|const|export)\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        re.MULTILINE
    )
    
    for node in file_nodes:
        # Index basename: 'auth_service.py' → 'auth_service'
        base_name = os.path.splitext(node["name"])[0]
        symbol_table[base_name] = node["id"]
        
        # Index all exported symbols: 'AuthService', 'get_user()', etc.
        with open(node["path"], "r", errors="ignore") as f:
            content = f.read()
            matches = signature_regex.findall(content)
            for match in matches:
                if len(match) > 3:  # Ignore tiny variable names
                    symbol_table[match] = node["id"]
    
    return symbol_table
    # Example: symbol_table = {
    #   'auth_service': '/root/services/auth_service.py',
    #   'AuthService': '/root/services/auth_service.py',
    #   'get_user': '/root/services/auth_service.py',
    #   'verify_token': '/root/services/auth_service.py',
    # }
```

### Phase 3: Intersection Analysis (Pass 2)
**Location**: `explorer.py:292-354`

```python
def _analyze_file(self, node, symbol_table):
    """
    For each file, find which symbols it references.
    Create logic_link edges with code snippets.
    
    Algorithm:
    1. Read file line by line
    2. Tokenize each line: \b\w+\b (word boundaries)
    3. Find intersection with symbol_table keys
    4. Collect code snippets for those intersections
    5. Group snippets by target file (max 30 lines)
    6. Emit logic_link with aggregate snippet
    """
    relationships_found = {}  # target_id → [code lines]
    
    with open(node["path"], "r", errors="ignore") as f:
        lines = f.readlines()
    
    for line_idx, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped or len(line_stripped) > 120:
            continue
        
        # Tokenize: "import auth_service" → {'import', 'auth_service'}
        words_in_line = set(re.findall(r'\b\w+\b', line_stripped))
        
        # Intersection: Find which words are in our symbol table
        found_symbols = words_in_line.intersection(symbol_table.keys())
        
        for symbol in found_symbols:
            target_id = symbol_table[symbol]
            if target_id == node["id"]:
                continue  # Skip self-links
            
            if target_id not in relationships_found:
                relationships_found[target_id] = []
            
            # Create snippet: "L15: from auth_service import get_user"
            snippet = f"L{line_idx+1}: {line_stripped}"
            relationships_found[target_id].append(snippet)
    
    # Finalize: Create logic_link edges
    local_links = []
    for target_id, snippets in relationships_found.items():
        # Join all snippets with newlines (max 30)
        full_stream = "\n".join(snippets[:30])
        if len(snippets) > 30:
            full_stream += "\n... [DATA STREAM TRUNCATED] ..."
        
        local_links.append({
            "source": node["id"],
            "target": target_id,
            "type": "logic_link",
            "width": 2.5,
            "color": "#00ff00",
            "snippet": full_stream  # Multi-line code context
        })
    
    return local_links
```

### Phase 4: Multi-threaded Execution
**Location**: `explorer.py:479-486`

```python
# Parallel analysis: 8 workers process files simultaneously
with ThreadPoolExecutor(max_workers=8) as executor:
    # Submit all files to workers
    futures = [executor.submit(self._analyze_file, n, symbol_table) 
               for n in file_nodes]
    
    # Collect results as they complete
    for future in futures:
        logic_links.extend(future.result())
        self.active_threads -= 1  # UI status bar counter
```

### Phase 5: Serialization & Distribution
**Location**: `explorer.py:373-380`

```python
# Write JSON data for browser consumption
with open("graph_data.json", "w") as f:
    json.dump(graph_data, f)
    # Output: {"nodes": [...], "links": [...]}

# Generate HTML from template
with open("network_graph.html", "w") as f:
    f.write(self._get_html_template())
```

### JSON Data Format

**Nodes Structure:**
```json
{
  "id": "/absolute/path/to/file",
  "name": "filename.py",
  "val": 5.86,
  "color": "#3776ab",
  "type": "file|folder",
  "path": "/absolute/path/to/file"
}
```

**Links Structure:**
```json
{
  "source": "folder_id",
  "target": "file_id",
  "type": "orbit|gravity|logic_link",
  "width": 0.5,
  "color": "#333333",
  "snippet": "L15: import module"
}
```

---

## Client-Side Rendering

### ForceGraph3D Initialization
**Location**: `network_graph.html:44-80`

```javascript
const Graph = ForceGraph3D()(document.getElementById('3d-graph'))
    // NODE RENDERING
    .nodeLabel('name')              // Show filename on hover
    .nodeColor('color')             // Color from data
    .nodeVal('val')                 // Size from data
    .nodeResolution(24)             // Sphere geometry detail (24 segments)
    
    // LINK RENDERING
    .linkWidth(l => 
        l.type === 'logic_link' ? 2.5 : 
        (l.type === 'gravity' ? 1.5 : 0.3)
    )
    .linkColor(l => 
        l.type === 'logic_link' ? '#00FF00' : 
        (l.type === 'gravity' ? '#666' : '#333')
    )
    
    // PARTICLE ANIMATION (moving dots along logic links)
    .linkDirectionalParticles(l => l.type === 'logic_link' ? 5 : 0)
    .linkDirectionalParticleSpeed(0.005)    // Units per frame
    .linkDirectionalParticleWidth(3)        // Pixel size
    
    // SCENE
    .backgroundColor('#000005')     // Near-black (0, 0, 5)
    
    // INTERACTION
    .onLinkHover(handleLinkHover)
    .onNodeClick(handleNodeClick);

// FORCE CONFIGURATION
Graph.d3Force('charge').strength(node => 
    node.type === 'folder' ? -350 : -40
);

Graph.d3Force('link').distance(link => 
    link.type === 'gravity' ? 120 : 40
);

/* CRITICAL: Zero-G Logic Links
   Logic links have strength 0, so they don't affect layout.
   They're purely aesthetic for showing dependencies. */
Graph.d3Force('link').strength(link => 
    link.type === 'logic_link' ? 0.0 : 1.0
);
```

### Color Mapping
**Location**: `explorer.py:493-503`

```python
def _get_color(self, ext):
    ext = ext.lower()
    if ext in ['.py', '.pyw']: return "#3776ab"      # Python: Blue
    if ext in ['.js', '.json', '.ts']: return "#f7df1e"  # JS: Yellow
    if ext in ['.html', '.css', '.scss']: return "#e34c26"  # Web: Red
    if ext in ['.md', '.txt', '.rst']: return "#dddddd"    # Docs: Gray
    if ext in ['.yml', '.yaml']: return "#0db7ed"   # Config: Cyan
    if ext in ['.tf', '.hcl']: return "#5f43e9"     # IaC: Purple
    if ext in ['.c', '.cpp', '.h', '.hpp']: return "#00599C"  # C/C++: Blue
    if ext in ['.java', '.jar']: return "#b07219"   # Java: Orange
    return "#ff00ff"                                 # Unknown: Magenta
```

---

## Physics & Force Simulation

### D3 Force Configuration

The visualization uses D3.js force simulation (internal to 3d-force-graph) with three force types:

#### 1. **Charge Force** (Repulsion)
```javascript
Graph.d3Force('charge').strength(node => 
    node.type === 'folder' ? -350 : -40
);
```

- **Folders**: -350 (strong repulsion, spread out)
- **Files**: -40 (weak repulsion, allow clustering)
- **Effect**: Prevents node overlap, creates natural spacing

#### 2. **Link Force** (Attraction)
```javascript
Graph.d3Force('link').distance(link => 
    link.type === 'gravity' ? 120 : 40
);

Graph.d3Force('link').strength(link => 
    link.type === 'logic_link' ? 0.0 : 1.0
);
```

- **Gravity Links** (folder hierarchy):
  - Target Distance: 120 units
  - Strength: 1.0 (full attraction)
  
- **Orbit Links** (file containment):
  - Target Distance: 40 units
  - Strength: 1.0 (full attraction)
  
- **Logic Links** (code dependencies):
  - Target Distance: (ignored)
  - Strength: **0.0** (NO FORCE!)
  - **Reason**: Logic links are information-only. Zero strength prevents code dependencies from distorting the physical layout.

#### 3. **Center Force** (Implicit)
- Keeps overall structure centered
- Automatically applied by 3d-force-graph

### Position Persistence
**Location**: `network_graph.html:96-107`

Critical for smooth updates without node jitter:

```javascript
// When new data arrives:
const currentGraphData = Graph.graphData();
const nodeMap = new Map(
    currentGraphData.nodes.map(n => [n.id, n])
);

// Restore old positions to new data
data.nodes.forEach(n => {
    const old = nodeMap.get(n.id);
    if (old) {
        n.x = old.x;   // Copy previous position
        n.y = old.y;
        n.z = old.z;
        n.vx = old.vx; // Copy velocity for smooth continuation
        n.vy = old.vy;
        n.vz = old.vz;
    }
});

Graph.graphData(data);
Graph.d3Alpha(0);      // Freeze physics immediately
Graph.d3Restart();     // Restart simulation from frozen state
```

---

## User Interaction

### Link Hover - Matrix HUD Display
**Location**: `network_graph.html:55-64`

```javascript
.onLinkHover(link => {
    const hud = document.getElementById('matrix-hud');
    const content = document.getElementById('hud-content');
    
    if (link && link.type === 'logic_link') {
        // Display code snippet from the link's 'snippet' field
        content.innerText = link.snippet || 
            "INITIATING DATA SCAN...\nNO RELEVANT BYTES FOUND.";
        hud.style.display = 'block';
    } else {
        hud.style.display = 'none';
    }
})
```

**HUD Display**:
- Fixed position: top-right corner, 280px wide
- Background: `rgba(0, 15, 0, 0.6)` (semi-transparent dark green)
- Border: `2px solid #00ff00` (bright green)
- Text: Matrix-style green-on-black (#00ff00 on #000000)
- Animation: Scrolling text (15s loop)

### Node Click - Camera Zoom
**Location**: `network_graph.html:65-72`

```javascript
.onNodeClick(node => {
    const dist = 60;
    const distRatio = 1 + dist / Math.hypot(node.x, node.y, node.z);
    
    Graph.cameraPosition(
        { 
            x: node.x * distRatio,  // Move camera away from node
            y: node.y * distRatio,
            z: node.z * distRatio
        },
        node,    // Camera looks at this node
        2500     // 2.5 second animation
    );
})
```

**Behavior**:
- Zooms camera to 60 units away from node
- Smooth 2.5s animation
- Camera continues to point at clicked node
- Default controls: orbit via right-click drag, zoom via scroll

---

## Animation System

### Heartbeat Loop - Data Polling
**Location**: `network_graph.html:84-124`

```javascript
let currentLinkCount = 0;

async function checkPulse() {
    try {
        // Fetch new data with cache-bust parameter
        const r = await fetch('graph_data.json?t=' + Date.now());
        const data = await r.json();
        
        // Only update if something changed (link count is indicator)
        if (data.links.length !== currentLinkCount) {
            console.log("Pulse detected: Updating Graph Data...");
            currentLinkCount = data.links.length;
            
            // [Position preservation code here]
            
            Graph.graphData(data);
            Graph.d3Alpha(0);
            Graph.d3Restart();
        }
    } catch (e) {
        console.log("Waiting for data stream...", e);
    }
}

// Start polling
checkPulse();
setInterval(checkPulse, 2500);  // Every 2.5 seconds
```

**Flow**:
1. Fetch `graph_data.json` with current timestamp (breaks cache)
2. Check if link count changed (fast indicator of file changes)
3. If changed: preserve node positions, inject new data, restart physics
4. Poll interval: 2.5 seconds (allows real-time file monitoring)

### Particle Animation
**Location**: `network_graph.html:51-53`

```javascript
.linkDirectionalParticles(l => l.type === 'logic_link' ? 5 : 0)
.linkDirectionalParticleSpeed(0.005)
.linkDirectionalParticleWidth(3)
```

- **Particles per Link**: 5 (moving dots along green logic links)
- **Speed**: 0.005 units per frame (~30fps) = very slow drift
- **Width**: 3 pixels (visible but not intrusive)
- **Effect**: Visual indication of code flow without distorting layout

---

## Server & Auto-Refresh

### LiveServer Implementation
**Location**: `explorer.py:948-998`

```python
class LiveServer(threading.Thread):
    def __init__(self, start_port):
        super().__init__(daemon=True)
        self.start_port = start_port
        self.actual_port = None
        
        # Try ports 8099-8108 (10 attempts)
        for port in range(self.start_port, self.start_port + 10):
            try:
                class Handler(http.server.SimpleHTTPRequestHandler):
                    def log_message(self, format, *args): 
                        pass  # Silent logging
                    
                    def end_headers(self):
                        # Disable browser caching
                        self.send_header(
                            'Cache-Control', 
                            'no-store, no-cache, must-revalidate'
                        )
                        super().end_headers()
                
                socketserver.TCPServer.allow_reuse_address = True
                # Listen on 0.0.0.0 (LAN accessible) not 127.0.0.1
                self.httpd = socketserver.ThreadingTCPServer(
                    ("0.0.0.0", port), Handler
                )
                
                self.actual_port = port
                print(f"[LiveServer] Bound to http://127.0.0.1:{port}")
                break
            except OSError as e:
                continue
    
    def run(self):
        if self.httpd:
            try:
                os.chdir(self.root_dir)  # Serve from script directory
                self.httpd.serve_forever()
            except Exception as e:
                print(f"[LiveServer] Error: {e}")
```

**Features**:
- Daemon thread (kills on app exit)
- Port collision resilient (tries 10 ports)
- LAN accessible (0.0.0.0 binding)
- Cache disabled for instant updates
- Silent logging (no console spam)

### Auto-Refresh Watcher Loop
**Location**: `explorer.py:1854-1869`

```python
def _start_live_generation(self, allowed_exts, allowed_folders):
    self.graph_generator.generate_3d_view(
        self.current_path, allowed_exts, allowed_folders
    )
    
    url = f"http://127.0.0.1:{self.server_port}/network_graph.html"
    self.after(1000, lambda: webbrowser.open(url))
    
    # Smart Watcher Loop
    def update_loop():
        last_state_hash = ""
        while True:
            time.sleep(2.5)
            current_state_hash = self._get_fs_fingerprint(self.current_path)
            
            if current_state_hash != last_state_hash:
                try:
                    # Only regenerate if files actually changed
                    self.graph_generator.generate_3d_view(
                        self.current_path, allowed_exts, allowed_folders
                    )
                    last_state_hash = current_state_hash
                except Exception as e:
                    print(f"[Auto-Scan Error] {e}")
    
    threading.Thread(target=update_loop, daemon=True).start()
```

### Filesystem Fingerprint
**Location**: `explorer.py:1872-1889`

```python
def _get_fs_fingerprint(self, path):
    """Fast hash of file count + total mtime."""
    total_files = 0
    total_mtime = 0
    
    for root, dirs, files in os.walk(path):
        # Skip hidden/ignored folders
        dirs[:] = [d for d in dirs 
                   if not d.startswith('.') 
                   and d not in {'node_modules', 'venv', '.git'}]
        
        for f in files:
            full_p = os.path.join(root, f)
            try:
                stat = os.stat(full_p)
                total_files += 1
                total_mtime += int(stat.st_mtime)
            except:
                pass
    
    return f"{total_files}:{total_mtime}"
```

**Rationale**: Fast change detection without full graph regeneration. Only triggers graph update when fingerprint differs.

---

## Visual Design

### CSS Styling
**Location**: `network_graph.html:5-31`

```css
body { 
    margin: 0; 
    background: #000005;  /* Near-black space background */
    overflow: hidden; 
    font-family: sans-serif; 
}

#matrix-hud {
    position: fixed; 
    right: 0; top: 0; bottom: 0; 
    width: 280px;
    background: rgba(0, 15, 0, 0.6);    /* Semi-transparent dark green */
    border-left: 2px solid #00ff00;     /* Bright green border */
    overflow: hidden; 
    pointer-events: none; 
    display: none; 
    z-index: 100;
    box-shadow: -5px 0 15px rgba(0, 255, 0, 0.2);
}

.matrix-stream {
    color: #00ff00;                     /* Matrix green */
    font-family: 'Courier New', monospace;
    font-size: 11px; 
    padding: 20px; 
    white-space: pre-wrap;
    text-shadow: 0 0 5px #00ff00;       /* Glow effect */
    animation: matrix-scroll 15s linear infinite;
}

@keyframes matrix-scroll {
    0% { transform: translateY(100vh); }
    100% { transform: translateY(-100%); }
}

#hud-header {
    position: absolute; 
    top: 0; left: 0; right: 0;
    background: #00ff00;                /* Bright green header */
    color: #000;
    font-size: 10px; 
    font-weight: bold; 
    padding: 2px 10px; 
    z-index: 101;
    text-transform: uppercase;
}
```

### Color Scheme
- **Background**: #000005 (near-black with slight blue tint)
- **Folders**: #FFFFFF (white) or #FFFFE0 (pale yellow for root)
- **Logic Links**: #00FF00 (bright green)
- **Gravity Links**: #666666 (dark gray)
- **Orbit Links**: #333333 (very dark gray)
- **HUD**: Green-on-black Matrix aesthetic

### Node Size Scaling

**Folders (Suns)**:
```
size = 10 + (directory_size_kb^0.25 * 2)
if is_root:
    size *= 2
```

**Files (Planets)**:
```
size = max(2, min(25, file_size_kb^0.3 * 1.5))
```

**Rationale**: Cubic root scaling prevents extreme size variations while maintaining visual hierarchy.

---

## Migration Checklist

### For Migrating to Another 3D Framework

- [ ] **Replace 3d-force-graph**
  - [ ] Implement D3 force simulation (or equivalent physics engine)
  - [ ] Configure charge force (repulsion)
  - [ ] Configure link force (attraction with distance & strength)
  - [ ] Implement position persistence on data updates

- [ ] **Render Spheres for Nodes**
  - [ ] Create sphere geometry (24 segments for detail)
  - [ ] Apply color per node.color
  - [ ] Scale size per node.val (cubic root scaling)
  - [ ] Add text labels (SpriteText or equivalent)

- [ ] **Render Links**
  - [ ] Draw lines/tubes for gravity & orbit links
  - [ ] Draw bright green lines for logic links
  - [ ] Implement directional particles (5 per logic link, speed 0.005)
  - [ ] Color by link type

- [ ] **Camera & Controls**
  - [ ] Implement orbit controls (right-click drag)
  - [ ] Implement zoom (scroll wheel)
  - [ ] Implement pan (middle-click drag)
  - [ ] Implement zoom-to-node on click (2.5s animation)

- [ ] **User Interaction**
  - [ ] Implement link hover detection
  - [ ] Display snippet HUD on logic link hover
  - [ ] Implement node click to zoom

- [ ] **Data Pipeline**
  - [ ] Keep Python backend (ConfigurableGraphGenerator)
  - [ ] Keep JSON data format unchanged
  - [ ] Implement heartbeat polling every 2.5s
  - [ ] Implement position preservation on data reload

- [ ] **Server & Auto-Refresh**
  - [ ] Deploy HTTP server (port binding logic)
  - [ ] Implement filesystem watcher
  - [ ] Implement graph regeneration on file change
  - [ ] Disable browser cache

### Key Architectural Principles to Preserve

1. **Deterministic Node IDs**: Use absolute file paths, not incrementing integers. This preserves positions across reloads.

2. **Zero-G Logic Links**: Code dependencies should have zero force strength. They're informational only.

3. **Position Snapshot Before Update**: Always preserve (x, y, z, vx, vy, vz) from old nodes when injecting new data.

4. **Fast Change Detection**: Use filesystem fingerprint (file count + mtime sum) instead of full re-analysis.

5. **Multi-threaded Analysis**: Parallelize code analysis with ThreadPoolExecutor (8 workers).

6. **2-Pass Heuristic**: Pass 1 indexes symbols, Pass 2 finds intersections. More robust than simple regex.

7. **Immutable Server Directory**: Always serve from script directory, disable caching.

---

## Code Quality Optimizations

### Performance
- **O(n²) Prevention**: Link strength 0 for logic links prevents expensive force calculations
- **Threading**: 8 workers reduce analysis time by ~75% for medium codebases
- **Fast Polling**: Heartbeat checks link count (O(1)) before regenerating graph
- **Clamped Sizes**: Node sizes capped to 2-25 range prevents outliers from dominating layout

### Maintainability
- **No Incremental IDs**: Node IDs = file paths (deterministic, survives file changes)
- **Sparse Regens**: Only regenerate graph if filesystem fingerprint changes
- **Clean Separation**: Python backend generates data, frontend renders it
- **Single Render Loop**: Browser runs one D3 simulation, no redundant recalculations

### Robustness
- **Port Collision Resistant**: Tries 8 consecutive ports
- **Error Handling**: All file I/O wrapped in try/except
- **Graceful Degradation**: Missing files don't crash analyzer
- **Cache Busting**: `?t=Date.now()` prevents stale graph_data.json

---

## Example: Complete Data Flow

```
1. User clicks "Visualize 3D Network"
   ↓
2. VisualizerLauncher UI lets user select file types & folders
   ↓
3. _start_live_generation() called
   ↓
4. ConfigurableGraphGenerator._generate_data()
   ├─ Phase 1: os.walk() → folder/file nodes (gravity/orbit links)
   ├─ Pass 1: _build_symbol_table() → index all symbols
   ├─ Pass 2: ThreadPoolExecutor._analyze_file() × 8 workers → logic links
   └─ Return {"nodes": [...], "links": [...]}
   ↓
5. Write graph_data.json & network_graph.html
   ↓
6. Start LiveServer (port binding logic)
   ↓
7. Start filesystem watcher loop (2.5s polling)
   ↓
8. Open http://127.0.0.1:{port}/network_graph.html in browser
   ↓
9. Browser fetches graph_data.json
   ↓
10. ForceGraph3D initializes 3D scene
    ├─ Create WebGL renderer
    ├─ Load Three.js camera & perspective
    ├─ Render nodes as spheres
    ├─ Render links as lines/tubes
    └─ Start D3 force simulation
    ↓
11. Heartbeat loop: checkPulse() every 2.5s
    ├─ Fetch graph_data.json?t=Date.now()
    ├─ If link count changed:
    │  ├─ Snapshot old node positions
    │  ├─ Restore positions to new nodes
    │  ├─ Inject new data: Graph.graphData(data)
    │  └─ Freeze & restart: Graph.d3Alpha(0); Graph.d3Restart()
    └─ Poll interval: 2.5s
    ↓
12. User interaction:
    ├─ Hover logic link → show snippet HUD
    ├─ Click node → zoom camera (2.5s animation)
    └─ Scroll/drag → orbit camera, pan, zoom
    ↓
13. Filesystem watcher detects change
    ├─ Calculate new fingerprint
    ├─ If changed, regenerate graph
    └─ POST new graph_data.json
    ↓
14. Browser's checkPulse() detects link change
    ├─ Preserve positions, inject new data
    └─ Visualization updates without jitter
```

---

## References

### CDN Libraries
- **3d-force-graph**: https://unpkg.com/3d-force-graph@1.73.2
- **three-spritetext**: https://unpkg.com/three-spritetext@1.8.1
- **D3.js** (internal to 3d-force-graph)
- **Three.js** (internal to 3d-force-graph)

### Key Files
- `explorer.py:258-504` - Graph generation
- `explorer.py:948-998` - HTTP server
- `explorer.py:1833-1895` - Visualization launcher
- `network_graph.html:43-127` - Client-side rendering

### Important Methods
- `ConfigurableGraphGenerator.generate_3d_view()`
- `ConfigurableGraphGenerator._generate_data()`
- `ConfigurableGraphGenerator._build_symbol_table()`
- `ConfigurableGraphGenerator._analyze_file()`
- `LiveServer.__init__()` and `LiveServer.run()`
- `ExplorerUI._start_live_generation()`
- `ExplorerUI._get_fs_fingerprint()`

