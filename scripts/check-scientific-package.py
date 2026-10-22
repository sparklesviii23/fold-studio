"""Check the actual bundled service before signing or replacing the current app."""
import ast
import pathlib
import subprocess
import sys


def check(app):
    resources = pathlib.Path(app).resolve() / 'Contents/Resources'
    scientific = resources / 'scientific'
    source = pathlib.Path(__file__).resolve().parents[1] / 'scientific'
    pending, visited = ['worker'], set()
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        module = scientific / (name + '.py')
        if not module.is_file():
            raise RuntimeError('Missing packaged scientific module: ' + name)
        tree = ast.parse(module.read_text())
        for node in ast.walk(tree):
            names = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            for imported in names:
                local = imported.split('.')[0]
                if (source / (local + '.py')).is_file():
                    pending.append(local)
    python = resources / 'runtime/bin/python3'
    subprocess.run([str(python), '-B', '-c', 'import sys;sys.path.insert(0,sys.argv[1]);import worker;assert worker.research.ACTIONS and worker.cinema.ACTIONS', str(scientific)], check=True, timeout=60)
    print('Packaged scientific service imports successfully; checked', len(visited), 'local modules.')


if __name__ == '__main__':
    check(sys.argv[1])
