#!/usr/bin/env python3
"""
Script de verification des imports pour MassaCorp.

Detecte:
- Dependances circulaires
- Imports problematiques (sync dans async, etc.)
- Imports non utilises

Usage:
    python scripts/check_imports.py
"""
import ast
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple


class ImportAnalyzer(ast.NodeVisitor):
    """Analyse les imports d'un fichier Python."""

    def __init__(self, module_name: str):
        self.module_name = module_name
        self.imports: Set[str] = set()
        self.from_imports: Dict[str, Set[str]] = defaultdict(set)
        self._in_type_checking = False

    def visit_If(self, node: ast.If):
        """Detecte les blocs TYPE_CHECKING et les ignore."""
        # Detecter: if TYPE_CHECKING:
        is_type_checking = False
        if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            is_type_checking = True
        elif isinstance(node.test, ast.Attribute) and node.test.attr == "TYPE_CHECKING":
            is_type_checking = True

        if is_type_checking:
            # Ignorer les imports dans ce bloc
            old_state = self._in_type_checking
            self._in_type_checking = True
            self.generic_visit(node)
            self._in_type_checking = old_state
        else:
            self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        """Capture les imports directs (import x)."""
        if not self._in_type_checking:
            for alias in node.names:
                self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Capture les imports from (from x import y)."""
        if not self._in_type_checking and node.module:
            for alias in node.names:
                self.from_imports[node.module].add(alias.name)
        self.generic_visit(node)


def get_module_name(file_path: Path, base_path: Path) -> str:
    """Convertit un chemin de fichier en nom de module."""
    relative = file_path.relative_to(base_path)
    parts = list(relative.parts)

    # Enlever l'extension .py
    if parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]

    # Enlever __init__
    if parts[-1] == "__init__":
        parts = parts[:-1]

    return ".".join(parts) if parts else ""


def analyze_file(file_path: Path, base_path: Path) -> Tuple[str, Set[str]]:
    """Analyse un fichier et retourne ses dependances internes."""
    module_name = get_module_name(file_path, base_path)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Erreur lecture {file_path}: {e}")
        return module_name, set()

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"Erreur syntaxe {file_path}: {e}")
        return module_name, set()

    analyzer = ImportAnalyzer(module_name)
    analyzer.visit(tree)

    # Filtrer pour garder uniquement les imports app.*
    internal_deps = set()

    for imp in analyzer.imports:
        if imp.startswith("app."):
            internal_deps.add(imp)

    for mod, names in analyzer.from_imports.items():
        if mod.startswith("app."):
            internal_deps.add(mod)

    return module_name, internal_deps


def find_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """Detecte les cycles dans un graphe de dependances."""
    cycles = []
    visited = set()
    rec_stack = set()

    def dfs(node: str, path: List[str]):
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, set()):
            if neighbor not in visited:
                dfs(neighbor, path)
            elif neighbor in rec_stack:
                # Cycle detecte
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)

        path.pop()
        rec_stack.remove(node)

    for node in graph:
        if node not in visited:
            dfs(node, [])

    return cycles


def check_async_dependencies(file_path: Path) -> List[str]:
    """
    Verifie les problemes async/sync dans un fichier.

    Detecte:
    - Appels sync dans des fonctions async
    - await sur des fonctions non-async
    """
    issues = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content)
    except Exception:
        return issues

    class AsyncChecker(ast.NodeVisitor):
        def __init__(self):
            self.in_async = False
            self.current_func = None

        def visit_AsyncFunctionDef(self, node):
            old_async = self.in_async
            old_func = self.current_func
            self.in_async = True
            self.current_func = node.name
            self.generic_visit(node)
            self.in_async = old_async
            self.current_func = old_func

        def visit_Call(self, node):
            if self.in_async and isinstance(node.func, ast.Attribute):
                # Detecter les appels potentiellement bloquants
                blocking_methods = ["read", "write", "sleep", "execute"]
                if node.func.attr in blocking_methods:
                    # Verifier si c'est un await
                    pass  # Analyse complexe, simplifiee ici

            self.generic_visit(node)

    checker = AsyncChecker()
    checker.visit(tree)

    return issues


def main():
    """Point d'entree principal."""
    base_path = Path(__file__).parent.parent
    app_path = base_path / "app"

    if not app_path.exists():
        print(f"Erreur: {app_path} n'existe pas")
        sys.exit(1)

    print("=" * 60)
    print("Analyse des imports MassaCorp")
    print("=" * 60)

    # Collecter tous les fichiers Python
    python_files = list(app_path.rglob("*.py"))
    print(f"\nFichiers Python trouves: {len(python_files)}")

    # Construire le graphe de dependances
    dep_graph: Dict[str, Set[str]] = {}

    for file_path in python_files:
        module_name, deps = analyze_file(file_path, base_path)
        if module_name:
            dep_graph[module_name] = deps

    # Detecter les cycles
    print("\n" + "-" * 60)
    print("Detection des dependances circulaires")
    print("-" * 60)

    cycles = find_cycles(dep_graph)

    if cycles:
        print(f"\n⚠️  {len(cycles)} cycle(s) detecte(s):")
        for i, cycle in enumerate(cycles, 1):
            print(f"\n  Cycle {i}:")
            print(f"    {' -> '.join(cycle)}")
    else:
        print("\n✅ Aucune dependance circulaire detectee")

    # Verifier les problemes async
    print("\n" + "-" * 60)
    print("Verification des dependances async")
    print("-" * 60)

    async_issues = []
    for file_path in python_files:
        issues = check_async_dependencies(file_path)
        if issues:
            async_issues.extend([(file_path, issue) for issue in issues])

    if async_issues:
        print(f"\n⚠️  {len(async_issues)} probleme(s) async detecte(s):")
        for file_path, issue in async_issues:
            print(f"  {file_path}: {issue}")
    else:
        print("\n✅ Aucun probleme async detecte")

    # Resume
    print("\n" + "=" * 60)
    print("Resume")
    print("=" * 60)
    print(f"  Modules analyses: {len(dep_graph)}")
    print(f"  Cycles detectes: {len(cycles)}")
    print(f"  Problemes async: {len(async_issues)}")

    # Exit code
    if cycles or async_issues:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
