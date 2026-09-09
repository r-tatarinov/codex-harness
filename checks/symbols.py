import ast


class SymbolIndex(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.symbols: dict[int, str] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        self.stack.append(node.name)
        self.symbols[id(node)] = ".".join(self.stack)
        self.generic_visit(node)
        self.stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef


def build_symbol_index(tree: ast.AST) -> dict[int, str]:
    index = SymbolIndex()
    index.visit(tree)

    return index.symbols
