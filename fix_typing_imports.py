#!/usr/bin/env python3
"""
Fix Python 3.13 typing compatibility issues.
Remove 'dict', 'list', 'set', 'tuple' from typing imports as they're now built-in.
"""

import os
import re
import subprocess
import sys


def fix_typing_imports(file_path):
    """Fix typing imports in a single file."""
    try:
        with open(file_path, encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Pattern to match "from typing import ..." lines
        typing_import_pattern = r'from typing import ([^;\n]+)'

        def fix_import_line(match):
            imports = match.group(1)
            # Split by comma and clean each import
            import_items = [item.strip() for item in imports.split(',')]

            # Remove problematic lowercase built-in types
            filtered_items = []
            for item in import_items:
                if item.strip() not in ['dict', 'list', 'set', 'tuple']:
                    filtered_items.append(item)

            if filtered_items:
                return f"from typing import {', '.join(filtered_items)}"
            else:
                return ""  # Remove the entire import line if nothing left

        # Apply the fix
        content = re.sub(typing_import_pattern, fix_import_line, content)

        # Remove any empty lines that resulted from removed imports
        content = re.sub(r'\nfrom typing import\s*\n', '\n', content)
        content = re.sub(r'from typing import\s*\n', '', content)

        # Only write if there were changes
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fixed: {file_path}")
            return True
        else:
            print(f"No changes needed: {file_path}")
            return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    """Main function to fix typing imports in all problematic files."""
    # Get list of files to fix
    try:
        result = subprocess.run([
            'find', 'src', '-name', '*.py', '-exec',
            'grep', '-l', 'from typing import.*dict\\|from typing import.*list\\|from typing import.*set\\|from typing import.*tuple',
            '{}', ';'
        ], capture_output=True, text=True, cwd='/Users/adamburdett/Github/work/Marty/marty-microservices-framework')

        files = result.stdout.strip().split('\n')
        files = [f for f in files if f]  # Remove empty strings

    except Exception as e:
        print(f"Error finding files: {e}")
        return 1

    if not files:
        print("No files found with problematic typing imports")
        return 0

    print(f"Found {len(files)} files to fix")

    fixed_count = 0
    for file_path in files:
        full_path = f"/Users/adamburdett/Github/work/Marty/marty-microservices-framework/{file_path}"
        if fix_typing_imports(full_path):
            fixed_count += 1

    print(f"\nFixed {fixed_count} out of {len(files)} files")
    return 0

if __name__ == "__main__":
    sys.exit(main())
