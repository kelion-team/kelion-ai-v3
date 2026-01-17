
import sys
import os
import importlib.util
import traceback

def check_file(filepath):
    print(f"Checking {filepath}...", end=" ")
    if not os.path.exists(filepath):
        print("MISSING ❌")
        return False
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            compile(f.read(), filepath, 'exec')
        print("SYNTAX OK ✅")
        return True
    except Exception as e:
        print(f"SYNTAX ERROR ❌: {e}")
        return False

def check_import(module_name):
    print(f"Attempting to import {module_name}...", end=" ")
    try:
        spec = importlib.util.spec_from_file_location(module_name, f"{module_name}.py")
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            print("IMPORT OK ✅")
            return True
        else:
            print("LOADER ERROR ❌")
            return False
    except ImportError as e:
        print(f"IMPORT ERROR ❌: {e}")
        return False
    except Exception as e:
        print(f"EXEC ERROR ❌: {traceback.format_exc()}")
        return False

print("=== STARTING FULL SYSTEM DIAGNOSTIC ===\n")

files = [
    "app.py",
    "super_ai_routes.py",
    "claude_brain.py",
    "security_core.py",
    "vision_module.py",
    "voice_module.py",
    "extensions_module.py"
]

all_ok = True
for f in files:
    if not check_file(f):
        all_ok = False

print("\n--- CHECKING MODULE DEPENDENCIES ---")
# Order matters slightly for dependencies
modules = [
    "security_core",
    "voice_module", 
    "vision_module",
    "claude_brain",
    "extensions_module",
    "super_ai_routes"
]

for m in modules:
    if not check_import(m):
        all_ok = False

if all_ok:
    print("\n✅ SYSTEM INTEGRITY VERIFIED. CODE IS VALID.")
else:
    print("\n❌ CRITICAL ISSUES FOUND.")
