import os
import re
import shutil
import time

TARGET = "explorer.py"
BACKUP = f"explorer_backup_FINAL_{int(time.time())}.py"

# THE WORKING CODE (Indented 4 spaces to match class level)
NEW_CODE = """
    def open_audit_blueprint_manager(self):
        \"\"\"
        REASON: FINAL LAYOUT FIX.
        Injected BEFORE __init__ to ensure structural validity.
        \"\"\"
        import tkinter as tk
        from tkinter import ttk, messagebox

        # 1. WINDOW
        win = tk.Toplevel(self)
        win.title("Audit Blueprint Manager")
        win.geometry("700x500")

        # 2. LAYOUT: Buttons (Row 1) First, List (Row 0) Second
        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1) 
        win.rowconfigure(1, weight=0)

        # Buttons (Row 1)
        btn_frame = ttk.Frame(win, padding=10)
        btn_frame.grid(row=1, column=0, sticky="ew")

        # Listbox (Row 0)
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

        def get_target():
            sel = lb.curselection()
            if not sel: 
                messagebox.showwarning("Select Record", "Please select a record.")
                return None
            return lb.get(sel[0])

        # Edit Button
        ttk.Button(btn_frame, text="Close", command=win.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Edit / View", 
                   command=lambda: self.edit_database_record(get_target(), win)).pack(side=tk.RIGHT)

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
"""

def final_fix():
    if not os.path.exists(TARGET):
        print(f"❌ Error: {TARGET} not found.")
        return

    print(f"💾 Creating backup: {BACKUP}")
    shutil.copyfile(TARGET, BACKUP)

    with open(TARGET, 'r') as f:
        lines = f.readlines()

    new_lines = []
    
    inside_explorer_ui = False
    injected = False
    
    # 1. Identify ExplorerUI Class
    class_pattern = re.compile(r"^\s*class ExplorerUI")
    # 2. Identify __init__ method (to inject BEFORE it)
    init_pattern = re.compile(r"^\s*def __init__")
    # 3. Identify old versions of the manager to disable
    manager_def = re.compile(r"^\s*def open_audit_blueprint_manager")

    for line in lines:
        if class_pattern.match(line):
            inside_explorer_ui = True
        
        # Rename any old copies of the function to prevent conflicts
        if manager_def.match(line):
            print(f"👻 Renaming old definition at line {len(new_lines)+1}")
            new_lines.append(line.replace("def open_audit_blueprint_manager", "def _ghost_manager"))
            continue

        # Inject BEFORE __init__ matches
        if inside_explorer_ui and not injected and init_pattern.match(line):
            print("💉 Injecting NEW Manager Code BEFORE __init__...")
            new_lines.append(NEW_CODE + "\n")  # Inject first
            new_lines.append(line)             # Then append the original __init__
            injected = True
            continue

        new_lines.append(line)

    with open(TARGET, 'w') as f:
        f.writelines(new_lines)

    if injected:
        print("✅ Final Fix Applied.")
        print("   -> Code injected cleanly as a sibling method.")
        print("🚀 Run ./run.sh")
    else:
        print("❌ Error: Could not find injection point.")

if __name__ == "__main__":
    final_fix()
