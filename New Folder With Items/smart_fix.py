import os
import re
import shutil
import time

TARGET = "explorer.py"
BACKUP = f"explorer_backup_SMART_{int(time.time())}.py"

# THE WORKING GRID LAYOUT CODE
NEW_CODE = """
    def open_audit_blueprint_manager(self):
        \"\"\"
        REASON: SMART-INJECTED FIX.
        Located correctly inside ExplorerUI.
        \"\"\"
        import tkinter as tk
        from tkinter import ttk, messagebox

        # 1. WINDOW SETUP
        win = tk.Toplevel(self)
        win.title("Audit Blueprint Manager")
        win.geometry("700x500")

        # 2. BUTTONS (Packed FIRST at BOTTOM)
        btn_frame = ttk.Frame(win, padding=10)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        ttk.Button(btn_frame, text="Close", command=win.destroy).pack(side=tk.RIGHT, padx=5)

        # 3. LISTBOX (Packed SECOND to fill space)
        main_frame = ttk.Frame(win, padding=5)
        main_frame.pack(side=tk.TOP, expand=True, fill=tk.BOTH)
        
        tk.Label(main_frame, text="Database Records:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        
        lb_frame = ttk.Frame(main_frame)
        lb_frame.pack(expand=True, fill=tk.BOTH, pady=5)
        
        scrollbar = ttk.Scrollbar(lb_frame)
        lb = tk.Listbox(lb_frame, yscrollcommand=scrollbar.set, 
                        bg="#2b2b2b", fg="#00ff00", font=("Courier", 12), selectmode=tk.SINGLE)
        scrollbar.config(command=lb.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        lb.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        # Populate
        try:
            titles = sorted(self.audit_manager.get_all_titles())
            for t in titles: lb.insert(tk.END, t)
        except:
            lb.insert(tk.END, "Error: AuditManager offline")

        # 4. HELPER & ACTIONS
        def get_target():
            sel = lb.curselection()
            if not sel: 
                messagebox.showwarning("Select Record", "Please select a record.")
                return None
            return lb.get(sel[0])

        # Connect Edit Button
        ttk.Button(btn_frame, text="Edit / View", 
                   command=lambda: self.edit_database_record(get_target(), win)).pack(side=tk.RIGHT)

        # Bindings
        lb.bind("<Double-1>", lambda e: self.edit_database_record(get_target(), win))
        
        # Context Menu
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

def smart_fix():
    if not os.path.exists(TARGET):
        print(f"❌ Error: {TARGET} not found.")
        return

    print(f"💾 Creating backup: {BACKUP}")
    shutil.copyfile(TARGET, BACKUP)

    with open(TARGET, 'r') as f:
        lines = f.readlines()

    new_lines = []
    
    # STATE MACHINE FLAGS
    inside_explorer_ui = False
    injected = False
    
    # Regex to identify the start of the ExplorerUI class
    class_pattern = re.compile(r"^\s*class ExplorerUI")
    
    # Regex to identify __init__ (we only want the one INSIDE ExplorerUI)
    init_pattern = re.compile(r"^\s*def __init__")

    # Regex to neutralize old versions
    manager_def = re.compile(r"^\s*def open_audit_blueprint_manager")

    for line in lines:
        # 1. Detect Class Entry
        if class_pattern.match(line):
            print("Found class ExplorerUI... Watching for injection point.")
            inside_explorer_ui = True
        
        # 2. Rename old/broken versions ANYWHERE in the file to be safe
        if manager_def.match(line):
            print(f"👻 Neutralizing old definition at line {len(new_lines)+1}")
            new_lines.append(line.replace("def open_audit_blueprint_manager", "def _broken_hidden_manager"))
            continue

        # 3. Inject ONLY if we are inside ExplorerUI and hit __init__
        if inside_explorer_ui and not injected and init_pattern.match(line):
            print("💉 Injecting NEW Manager Code correctly into ExplorerUI...")
            new_lines.append(line) # Keep the __init__ line
            new_lines.append(NEW_CODE + "\n")
            injected = True
            continue

        new_lines.append(line)

    with open(TARGET, 'w') as f:
        f.writelines(new_lines)

    if injected:
        print("✅ Smart Fix Applied.")
        print("   -> Code injected ONLY into 'class ExplorerUI'.")
        print("   -> 'ToolTip' class was untouched.")
        print("🚀 Run ./run.sh")
    else:
        print("❌ Error: Could not find 'class ExplorerUI'. Injection failed.")

if __name__ == "__main__":
    smart_fix()
