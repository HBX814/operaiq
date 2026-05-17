import os
import re

patterns = [r'[\"\'\`][a-zA-Z0-9_\-\.]{30,}[\"\'\`]']
ignore_dirs = ['node_modules', '.venv', '.git', '.next']
ignore_exts = ['.lock', '.pyc']

for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ignore_dirs]
    for file in files:
        if file.endswith(tuple(ignore_exts)): continue
        if not file.endswith(('.py', '.ts', '.tsx', '.json', '.yaml', '.yml')): continue
        filepath = os.path.join(root, file)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if 'process.env' in line or 'os.environ' in line: continue
                    for p in patterns:
                        for m in re.finditer(p, line):
                            print(f'{filepath}:{i+1}: {m.group(0)}')
        except:
            pass
