"""Conferência estática do grafo de migrações de uma candidata Git.

Lê blobs da árvore candidata; nunca importa nem executa código da candidata.
"""
import ast
import subprocess


def _git(repo, *args):
    r = subprocess.run(["git", "--git-dir", str(repo), *args], capture_output=True,
                       encoding="utf-8", errors="replace", timeout=60)
    if r.returncode:
        raise ValueError("não foi possível ler a árvore de migrações")
    return r.stdout


def _migracoes(repo, commit):
    paths = _git(repo, "ls-tree", "-r", "--name-only", commit).splitlines()
    result = {}
    for path in paths:
        bits = path.split("/")
        if len(bits) < 3 or bits[-2] != "migrations" or not bits[-1].endswith(".py") or bits[-1] == "__init__.py":
            continue
        app, name = bits[-3], bits[-1][:-3]
        source = _git(repo, "show", "%s:%s" % (commit, path))
        try:
            tree = ast.parse(source, filename=path)
        except SyntaxError as ex:
            raise ValueError("migração %s tem sintaxe inválida: %s" % (path, ex.msg))
        deps = set()
        dynamic = False
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef) or cls.name != "Migration":
                continue
            for assign in cls.body:
                if not isinstance(assign, ast.Assign) or not any(isinstance(t, ast.Name) and t.id == "dependencies" for t in assign.targets):
                    continue
                if not isinstance(assign.value, (ast.List, ast.Tuple)):
                    dynamic = True
                    continue
                for item in assign.value.elts:
                    try:
                        dep = ast.literal_eval(item)
                    except (ValueError, TypeError, SyntaxError):
                        dynamic = True
                        continue
                    if isinstance(dep, tuple) and len(dep) == 2 and all(isinstance(x, str) for x in dep):
                        deps.add(dep)
                    else:
                        dynamic = True
        result[(app, name)] = (path, deps, dynamic)
    return result


def _problemas(graph):
    problems = set()
    by_app = {}
    for node in graph:
        by_app.setdefault(node[0], set()).add(node)
    for node, (path, deps, dynamic) in graph.items():
        if dynamic:
            problems.add("dependência dinâmica em %s" % path)
        for dep in deps:
            if dep[1] in ("__first__", "__latest__"):
                continue
            if dep not in graph and dep[0] in by_app:
                problems.add("dependência ausente %s.%s em %s" % (*dep, path))
    seen, active = set(), set()
    def visit(node):
        if node in active:
            problems.add("ciclo de migrações em %s.%s" % node)
            return
        if node in seen:
            return
        active.add(node)
        for dep in graph[node][1]:
            if dep in graph:
                visit(dep)
        active.remove(node)
        seen.add(node)
    for node in graph:
        visit(node)
    for app, nodes in by_app.items():
        parents = {dep for node in nodes for dep in graph[node][1] if dep in nodes}
        leaves = nodes - parents
        if len(leaves) > 1:
            problems.add("pontas concorrentes em %s: %s" % (app, ", ".join(sorted(n for _, n in leaves))))
    return problems


def conferir(repo, main, candidata):
    """Devolve novos problemas da candidata em relação à main, sem executar blobs."""
    baseline = _problemas(_migracoes(repo, main))
    return sorted(_problemas(_migracoes(repo, candidata)) - baseline)
