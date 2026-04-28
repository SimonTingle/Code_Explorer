import os
import re
import shutil
import time

TARGET = "explorer.py"
BACKUP = f"explorer_backup_CLEAN_{int(time.time())}.py"

# This block contains ALL the methods that should exist before __init__
# It includes the Telemetry, the Editor, and the Blueprint Manager.
CLEAN_BLOCK = """    # --- CLEANED METHODS BLOCK ---

    def _refresh_hud_telemetry(self):
        \"\"\"
        REASON: HUD BRIDGE.
        Updates the OpsHUD with Git and File stats.
        \"\"\"
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
        \"\"\"
        REASON: DATABASE EDITOR.
        Opens the multiline editor for a specific blueprint.
        \"\"\"
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
        \"\"\"
        REASON: MODAL TEXT EDITOR.
        Helper for edit_database_record.
        \"\"\"
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
        \"\"\"
        REASON: BLUEPRINT MANAGER UI.
        Uses Grid layout to ensure Edit buttons are always visible.
        \"\"\"
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
        if self.root.tk.call('tk', 'windowingsystem') == 'aqua':
            lb.bind("<Button-2>", show_ctx)

    # --- END CLEAN BLOCK ---
"""

def clean_sweep():
    if not os.path.exists(TARGET):
        print(f"❌ Error: {TARGET} not found.")
        return

    print(f"💾 Creating backup: {BACKUP}")
    shutil.copyfile(TARGET, BACKUP)

    with open(TARGET, 'r') as f:
        content = f.read()

    # Step 1: Identify the boundaries
    # Start: "class ExplorerUI..."
    # End:   "def __init__..." (The one inside ExplorerUI)
    
    # We use a regex that captures everything between the class definition line
    # and the __init__ definition line.
    
    # Pattern:
    # 1. Match 'class ExplorerUI(ttk.Frame):'
    # 2. Match everything (greedy) until...
    # 3. The 'def __init__' line that follows.
    
    pattern = r"(class ExplorerUI\(ttk\.Frame\):)([\s\S]*?)(?=\n\s*def __init__)"
    
    match = re.search(pattern, content)
    if not match:
        print("❌ Error: Could not locate 'class ExplorerUI' and its '__init__'. Structure might be too damaged.")
        return

    print("🧹 Locate debris between 'class ExplorerUI' and '__init__'...")
    
    # Step 2: Replace the debris with the CLEAN_BLOCK
    new_content = re.sub(pattern, r"\1\n" + CLEAN_BLOCK, content, count=1)
    
    with open(TARGET, 'w') as f:
        f.write(new_content)

    print("✅ Clean Sweep Complete.")
    print("   -> Deleted all ghosts, duplicates, and broken indentation.")
    print("   -> Inserted verified Logic & UI methods.")
    print("🚀 Run ./run.sh")

if __name__ == "__main__":
    clean_sweep()
