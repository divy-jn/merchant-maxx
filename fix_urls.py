import os, glob

files = glob.glob('frontend/src/**/*.jsx', recursive=True)
for f in files:
    with open(f, 'r') as file:
        content = file.read()
    
    if 'http://localhost:8002' in content:
        # For single quoted strings
        content = content.replace("'http://localhost:8002/", "`\\${import.meta.env.VITE_API_URL || 'http://localhost:8002'}/")
        # Replace trailing single quote with backtick if it started with single quote
        # Actually a regex is safer
        import re
        content = re.sub(r"'http://localhost:8002([^']*)'", r"`${import.meta.env.VITE_API_URL || 'http://localhost:8002'}\1`", content)
        
        # For backticked strings
        content = re.sub(r"`http://localhost:8002([^`]*)`", r"`${import.meta.env.VITE_API_URL || 'http://localhost:8002'}\1`", content)

        with open(f, 'w') as file:
            file.write(content)
        print(f"Updated {f}")
