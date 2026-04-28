import os
import re
import shutil
import time

TARGET = "explorer.py"
BACKUP = f"explorer_backup_FINAL_{int(time.time())}.py"

# THE WORKING CODE (With 4-space indentation)
NEW_CODE = """
    def open_audit_blueprint_manager(self):
        \"\"\"
        REASON: FORCE-INJECTED FIX.
        This is the active version. All old versions have been renamed.
        \"\"\"
        import tkinter as tk
        from tkinter import ttk, messagebox

        # 1. WINDOW & LAYOUT
        win = tk.Toplevel(self)
        win.title("Audit Blueprint Manager")
        win.geometry("700x500") # Slightly larger to ensure visibility

        # USE PACKING ORDER: BOTTOM FIRST (Buttons), THEN TOP (List)
        
        # 2. BUTTONS (Pack at BOTTOM)
        btn_frame = ttk.Frame(win, padding=10)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        ttk.Button(btn_frame, text="Close", command=win.destroy).pack(side=tk.RIGHT, padx=5)

        # 3. LISTBOX (Pack at TOP, fill rest)
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

        # Connect the Edit Button
        btn_edit = ttk.Button(btn_frame, text="Edit / View", 
                              command=lambda: self.edit_database_record(get_target(), win))
        btn_edit.pack(side=tk.RIGHT)

        # Double Click & Right Click
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

def force_fix():
    if not os.path.exists(TARGET):
        print(f"❌ Error: {TARGET} not found.")
        return

    print(f"💾 Creating backup: {BACKUP}")
    shutil.copyfile(TARGET, BACKUP)

    with open(TARGET, 'r') as f:
        lines = f.readlines()

    new_lines = []
    class_found = False
    injected = False

    # Regex to find ANY definition of the manager
    def_pattern = re.compile(r"^\s*def open_audit_blueprint_manager")

    for line in lines:
        # 1. KILL ALL GHOSTS: Rename any existing definition
        if def_pattern.match(line):
            print(f"👻 Disabling old definition at line {len(new_lines)+1}")
            new_lines.append(line.replace("def open_audit_blueprint_manager", "def _broken_hidden_manager"))
            continue

        # 2. INJECT NEW CODE: Right after 'class ExplorerUI' and its __init__
        # We look for the __init__ line to know we are inside the class
        if "def __init__" in line and not injected:
            new_lines.append(line)
            print("💉 Injecting NEW Manager Code at top of class...")
            new_lines.append(NEW_CODE + "\n")
            injected = True
            continue

        new_lines.append(line)

    with open(TARGET, 'w') as f:
        f.writelines(new_lines)

    print("✅ Force Fix Applied.")
    print("   -> All old versions renamed to '_broken_hidden_manager'")
    print("   -> New version injected at top of class.")
    print("🚀 Run ./run.sh now.")

if __name__ == "__main__":
    force_fix()
