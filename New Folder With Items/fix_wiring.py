import os
import re
import shutil
import time

TARGET = "explorer.py"
BACKUP = f"explorer_backup_WIRING_{int(time.time())}.py"

def fix_wiring():
    if not os.path.exists(TARGET):
        print(f"❌ Error: {TARGET} not found.")
        return

    print(f"💾 Creating backup: {BACKUP}")
    shutil.copyfile(TARGET, BACKUP)

    with open(TARGET, 'r') as f:
        content = f.read()

    # The Pattern to Find: command=self.list_audit_db
    # The Replacement:     command=self.open_audit_blueprint_manager
    
    old_command = "command=self.list_audit_db"
    new_command = "command=self.open_audit_blueprint_manager"
    
    if old_command in content:
        print(f"🔌 Found broken wiring: '{old_command}'")
        new_content = content.replace(old_command, new_command)
        
        with open(TARGET, 'w') as f:
            f.write(new_content)
            
        print(f"✅ RE-WIRED SUCCESSFUL.")
        print(f"   Old: {old_command}")
        print(f"   New: {new_command}")
        print("🚀 Run ./run.sh -> The Edit buttons will now appear.")
    else:
        print("⚠️ Could not find the specific string 'command=self.list_audit_db'.")
        print("   It might be written differently (spaces, newlines).")
        # Fallback regex approach if simple replace fails
        pattern = r"command\s*=\s*self\.list_audit_db"
        if re.search(pattern, content):
            print("   -> Detected via Regex. Patching...")
            new_content = re.sub(pattern, "command=self.open_audit_blueprint_manager", content)
            with open(TARGET, 'w') as f:
                f.write(new_content)
            print("✅ RE-WIRED VIA REGEX.")
        else:
            print("❌ FAILED: Please check line 1802 manually.")

if __name__ == "__main__":
    fix_wiring()
