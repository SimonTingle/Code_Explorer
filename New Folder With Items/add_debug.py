import re

def add_debug_prints(filename):
    print(f"Processing {filename}...")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print("Error: Could not find explorer.py")
        return

    new_lines = []
    
    for line in lines:
        new_lines.append(line)
        
        # 1. Regex to find function definitions
        match_def = re.match(r'^(\s*)def\s+(\w+)', line)
        if match_def:
            # CHECK: Skip one-liners (e.g., "def foo(): pass")
            # If there is code (non-comment, non-whitespace) after the colon, skip it.
            if re.search(r':\s*[^#\s]', line):
                continue

            indent = match_def.group(1)
            func_name = match_def.group(2)
            new_lines.append(f'{indent}    print(f"--> [DEBUG] Running Function: {func_name}")\n')
            continue

        # 2. Regex to find class definitions
        match_class = re.match(r'^(\s*)class\s+(\w+)', line)
        if match_class:
            indent = match_class.group(1)
            class_name = match_class.group(2)
            new_lines.append(f'{indent}    print(f"==> [DEBUG] Init Class: {class_name}")\n')

    output_filename = "debug_explorer.py"
    with open(output_filename, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"Success! Created '{output_filename}'.")

if __name__ == "__main__":
    add_debug_prints("explorer.py")