"""
models/calculator.py — Calculatrice sécurisée via AST.
"""

import ast
import operator

_SAFE_OPS: dict = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def eval_safe(expression: str) -> str:
    """Évalue une expression arithmétique de manière sécurisée."""
    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp):
            fn = _SAFE_OPS.get(type(node.op))
            if fn:
                return fn(_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp):
            fn = _SAFE_OPS.get(type(node.op))
            if fn:
                return fn(_eval(node.operand))
        raise ValueError

    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval(tree.body)
        if isinstance(result, float) and result.is_integer():
            return str(int(result))
        return str(result)
    except ZeroDivisionError:
        return "Erreur : division par zéro"
    except Exception:
        return "Erreur de calcul"
