import ast
from typing import Tuple

from flynt.transform.format_call_transforms import matching_call, joined_string
from flynt.transform.percent_transformer import transform_binop
from flynt import state


class FstringifyTransformer(ast.NodeTransformer):
    def __init__(self):
        super().__init__()
        self.counter = 0
        self.string_in_string = False

    def visit_Call(self, node: ast.Call):
        """
        Convert `ast.Call` to `ast.JoinedStr` f-string
        """

        match = matching_call(node)

        if match:
            state.call_candidates += 1

            # bail in these edge cases...
            if any(isinstance(arg, ast.Starred) for arg in node.args):
                return node

            result_node = joined_string(node)
            self.visit(result_node)
            self.counter += 1
            state.call_transforms += 1
            return result_node

        return node

    def visit_BinOp(self, node):
        """Convert `ast.BinOp` to `ast.JoinedStr` f-string

        Currently only if a string literal `ast.Str` is on the left side of the `%`
        and one of `ast.Tuple`, `ast.Name`, `ast.Dict` is on the right

        Args:
            node (ast.BinOp): The node to convert to a f-string

        Returns ast.JoinedStr (f-string)
        """

        percent_stringify = (
            isinstance(node.left, ast.Str)
            and isinstance(node.op, ast.Mod)
            and isinstance(
                node.right,
                (ast.Tuple, ast.Name, ast.Attribute, ast.Str, ast.Subscript, ast.Dict),
            )
        )

        if percent_stringify:
            state.percent_candidates += 1

            # bail in these edge cases...
            no_good = ["}", "{"]
            for ng in no_good:
                if ng in node.left.s:
                    return node
            for ch in ast.walk(node.right):
                # no nested binops!
                if isinstance(ch, ast.BinOp):
                    return node
                # f-string expression part cannot include a backslash
                elif isinstance(ch, ast.Str) and (
                    any(
                        map(
                            lambda x: x in ch.s,
                            ("\n", "\t", "\r", "'", '"', "%s", "%%"),
                        )
                    )
                    or "\\" in ch.s
                ):
                    return node

            result_node, str_in_str = transform_binop(node)
            self.string_in_string = str_in_str
            self.counter += 1
            state.percent_transforms += 1
            return result_node

        return node


def fstringify_node(node) -> Tuple[ast.AST, bool, bool]:
    ft = FstringifyTransformer()
    result = ft.visit(node)

    return result, ft.counter > 0, ft.string_in_string
