#!/bin/bash

# ==============================================================================
# FIVEXL HARDENING: SAFE PRUNIFICATION SCRIPT
# Target: explorer.py
# Mission: Fix 'open_audit_blueprint_manager', prune duplicates, preserve history.
# ==============================================================================

TARGET="explorer.py"
BACKUP="explorer_backup_$(date +%Y%m%d_%H%M%S).py"
REPORT="structure_report.txt"

echo "--- [PHASE 1] PRE-FLIGHT CHECKS ---"

# 1. Guardrail: Check if file exists
if [ ! -f "$TARGET" ]; then
    echo "❌ ERROR: $TARGET not found!"
    exit 1
fi

# 2. Guardrail: Syntax Check (Don't patch a broken file)
echo "🔍 Checking syntax of original file..."
if ! python3 -m py_compile "$TARGET"; then
    echo "❌ ABORT: Original file has syntax errors. Fix them manually before pruning."
    exit 1
fi

# 3. Guardrail: Backup
echo "💾 Creating backup: $BACKUP"
cp "$TARGET" "$BACKUP"
if [ ! -f "$BACKUP" ]; then
    echo "❌ ERROR: Backup creation failed. Aborting."
    exit 1
fi
echo "✅ Backup secured."

# ==============================================================================
# [PHASE 2] STRUCTURAL MAPPING
# ==============================================================================
echo "--- [PHASE 2] MAPPING CODE STRUCTURE ---"
echo "Generating $REPORT..."
grep -nE "class |def " "$TARGET" > "$REPORT"
echo "✅ Structure map saved. You can review $REPORT to see file order."

# ==============================================================================
# [PHASE 3] THE PATCH (PYTHON INJECTION)
# ==============================================================================
echo "--- [PHASE 3] EXECUTING SURGICAL PATCH ---"

# We use a temporary python script to handle the logic safely
cat << 'EOF' > patcher.py
import re
import sys

target_file = "explorer.py"
new_method_code = """
    def open_audit_blueprint_manager(self):
        \"\"\"
        REASON: GRID LAYOUT FIX [AUTO-PATCHED].
        Replaced broken packing logic with Grid layout to ensure Edit buttons are visible.
        \"\"\"
        win = tk.Toplevel(self)
        win.title("Audit Blueprint Manager")
        win.geometry("600x450")
        
        # Grid Configuration
        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1) # List gets all space
        win.rowconfigure(1, weight=0) # Buttons get fixed space at bottom

        # --- MENU FAILSAFE ---
        menubar = tk.Menu(win)
        win.config(menu=menubar)
        actions = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Actions", menu=actions)

        # --- HELPER ---
        def get_target():
            sel = lb.curselection()
            if not sel: 
                messagebox.showwarning("Select Record", "Please select a record.")
                return None
            return lb.get(sel[0])

        actions.add_command(label="Edit Selected", command=lambda: self.edit_database_record(get_target(), win))
        actions.add_command(label="Close", command=win.destroy)

        # --- ROW 0: LISTBOX ---
        list_frame = ttk.Frame(win, padding=5)
        list_frame.grid(row=0, column=0, sticky="nsew")
        
        scrollbar = ttk.Scrollbar(list_frame)
        lb = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, 
                        bg="#1e1e1e", fg="#00ff00", font=("Courier", 11), selectmode=tk.SINGLE)
        scrollbar.config(command=lb.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        lb.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        try:
            titles = sorted(self.audit_manager.get_all_titles())
            for t in titles: lb.insert(tk.END, t)
        except AttributeError:
            lb.insert(tk.END, "Error: AuditManager offline")

        # --- ROW 1: BUTTONS ---
        btn_frame = ttk.Frame(win, padding=10)
        btn_frame.grid(row=1, column=0, sticky="ew")
        
        ttk.Button(btn_frame, text="Close", command=win.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Edit / View", command=lambda: self.edit_database_record(get_target(), win)).pack(side=tk.RIGHT)

        # --- BINDINGS ---
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
        if self.root.tk.call('tk', 'windowingsystem') == 'aqua':
            lb.bind("<Button-2>", show_ctx)
"""

try:
    with open(target_file, "r") as f:
        lines = f.readlines()

    new_lines = []
    inside_target = False
    patched = False

    # Regex to find the start of the function
    start_pattern = re.compile(r"^\s*def open_audit_blueprint_manager\(self\):")

    for line in lines:
        # 1. Detect start of the old broken function
        if start_pattern.match(line):
            inside_target = True
            new_lines.append(f"# {line.rstrip()}  # [COMMENTED OUT BY PRUNER]\n")
            # Inject the new code immediately before the commented block
            if not patched:
                new_lines.append(new_method_code + "\n")
                patched = True
            continue

        # 2. While inside the function, comment everything out
        if inside_target:
            # Detect end of function by indentation (naive but effective for top-level class methods)
            # If the next line starts with 'def ' or unindented text, we are out.
            if line.strip().startswith("def ") or (line.strip() and not line.startswith(" ")):
                inside_target = False
                new_lines.append(line) # Add the line that broke the loop
            else:
                new_lines.append(f"# {line}") # Comment out the body
        else:
            # 3. GHOST BUSTING: Comment out rogue 'edit_selected' functions
            if "def edit_selected" in line:
                new_lines.append(f"# REASON: PRUNED GHOST CODE\n# {line}")
            else:
                new_lines.append(line)

    with open(target_file, "w") as f:
        f.writelines(new_lines)
    
    print("✅ Python patch applied successfully.")

except Exception as e:
    print(f"❌ Python patch failed: {e}")
    sys.exit(1)
EOF

# Run the python patcher
python3 patcher.py
if [ $? -ne 0 ]; then
    echo "❌ PATCH FAILED. Restoring backup..."
    cp "$BACKUP" "$TARGET"
    exit 1
fi
rm patcher.py

# ==============================================================================
# [PHASE 4] POST-FLIGHT CHECKS
# ==============================================================================
echo "--- [PHASE 4] POST-FLIGHT VERIFICATION ---"

# 1. Syntax Check
if python3 -m py_compile "$TARGET"; then
    echo "✅ Syntax Validated."
    echo "🚀 PRUNIFICATION COMPLETE."
    echo "   - Old broken code is commented out."
    echo "   - New Grid-based UI is active."
    echo "   - Backup saved at: $BACKUP"
else
    echo "❌ CRITICAL: Syntax error detected after patch!"
    echo "   Restoring backup automatically..."
    cp "$BACKUP" "$TARGET"
    echo "   Restored $TARGET to original state."
    exit 1
fi
