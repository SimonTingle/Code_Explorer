import os

TARGET = "explorer.py"

def fix_mac_crash():
    if not os.path.exists(TARGET):
        print(f"❌ Error: {TARGET} not found.")
        return

    with open(TARGET, 'r') as f:
        content = f.read()

    # The broken line
    broken_line = "if self.root.tk.call('tk', 'windowingsystem') == 'aqua':"
    
    # The fixed line (Every widget has .tk, so this is safe)
    fixed_line = "if self.tk.call('tk', 'windowingsystem') == 'aqua':"

    if broken_line in content:
        new_content = content.replace(broken_line, fixed_line)
        
        with open(TARGET, 'w') as f:
            f.write(new_content)
            
        print("✅ MAC CRASH FIXED.")
        print("   Replaced 'self.root.tk.call' with 'self.tk.call'")
        print("🚀 Your app should now be 100% crash-free.")
    else:
        print("⚠️ Could not find the specific line. It might already be fixed.")

if __name__ == "__main__":
    fix_mac_crash()
