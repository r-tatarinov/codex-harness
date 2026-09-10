import ast

from .symbol_index import SymbolIndex


def build_symbol_index(tree: ast.AST) -> dict[int, str]:
    index = SymbolIndex()
    index.visit(tree)

    return index.symbols
