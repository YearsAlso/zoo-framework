def sub(fp, pairs):
    with open(fp, encoding="utf-8", newline=None) as f:
        s = f.read()
    for old, new in pairs:
        n = s.count(old)
        if n != 1:
            print(f"SKIP count={n}: {fp} :: {old[:50]}")
            continue
        s = s.replace(old, new)
    with open(fp, "w", encoding="utf-8", newline=None) as f:
        f.write(s)
    print(f"OK {fp}")


def sub_all(fp, pairs):
    with open(fp, encoding="utf-8", newline=None) as f:
        s = f.read()
    for old, new in pairs:
        s = s.replace(old, new)
    with open(fp, "w", encoding="utf-8", newline=None) as f:
        f.write(s)
    print(f"OK {fp}")


def cjk(fp):
    import ast

    with open(fp, encoding="utf-8", newline=None) as f:
        src = f.read()
    tree = ast.parse(src)
    import re

    total = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            ds = ast.get_docstring(node, clean=False)
            if ds:
                m = re.findall(r"[\u4e00-\u9fff]", ds)
                if m:
                    total += len(m)
                    print(f"  {fp}: {len(m)} CJK at {getattr(node, 'name', '<module>')}")
    if total == 0:
        print(f"CLEAR {fp}")
