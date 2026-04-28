import re

FILE = "explorer.py"

print(f"--- ANALYZING MENU WIRING IN {FILE} ---")

try:
    with open(FILE, "r") as f:
        lines = f.readlines()
        
    found = False
    for i, line in enumerate(lines):
        # Search for the menu label
        if "List Database" in line or "label=\"Database\"" in line:
            print(f"Line {i+1}: {line.strip()}")
            found = True
            
            # Check for the command binding on this line or the next few
            # (Sometimes command=... is on the next line)
            context = "".join(lines[i:i+3])
            match = re.search(r'command\s*=\s*(?:lambda\s*:\s*)?self\.([a-zA-Z0-9_]+)', context)
            if match:
                func_name = match.group(1)
                print(f"   -> WIRED TO FUNCTION: '{func_name}'")
                
                # Check if this matches our target
                if func_name == "open_audit_blueprint_manager":
                    print("   -> ✅ CORRECT: Pointing to the Blueprint Manager.")
                else:
                    print(f"   -> ❌ MISMATCH: It is NOT pointing to Blueprint Manager!")
            else:
                print("   -> ⚠️ WARNING: Could not detect 'command=' binding nearby.")

    if not found:
        print("❌ Error: Could not find 'List Database' in the file. Check spelling.")

except Exception as e:
    print(f"Error reading file: {e}")
