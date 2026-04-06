import json
import re
import sys
from itertools import product


KEYWORD_MAP = {
    "let": "LET",
    "if": "IF",
    "then": "THEN",
    "print": "PRINT",
}

BOOLEAN_MAP = {
    "T": "TRUE",
    "F": "FALSE",
}

OPERATOR_MAP = {
    "AND": "AND",
    "OR": "OR",
    "NOT": "NOT",
    "IMPLIES": "IMPLIES",
}

SYMBOL_MAP = {
    "=": "EQ",
    "(": "L_PAREN",
    ")": "R_PAREN",
}


class CompilerError(Exception):
    def __init__(self, phase, line):
        self.phase = phase
        self.line = line
        super().__init__(f"{phase} at line {line}")


def is_var(token):
    return isinstance(token, str) and token.startswith("VAR_")


def ast_equal(a, b):
    return a == b


def tokenize_line(line_text, line_number):
    tokens = []
    for match in re.finditer(r"\s+|[()]|=|[A-Za-z]+|.", line_text):
        piece = match.group(0)
        if piece.isspace():
            continue
        if piece in SYMBOL_MAP:
            tokens.append(SYMBOL_MAP[piece])
            continue
        if piece in KEYWORD_MAP:
            tokens.append(KEYWORD_MAP[piece])
            continue
        if piece in BOOLEAN_MAP:
            tokens.append(BOOLEAN_MAP[piece])
            continue
        if piece in OPERATOR_MAP:
            tokens.append(OPERATOR_MAP[piece])
            continue
        if len(piece) == 1 and "a" <= piece <= "z":
            tokens.append(f"VAR_{piece.upper()}")
            continue
        raise CompilerError("phase_1_lexer", line_number)
    return tokens


class TokenStream:
    def __init__(self, tokens, line_number):
        self.tokens = tokens
        self.line_number = line_number
        self.pos = 0

    def current(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self, expected=None):
        token = self.current()
        if token is None:
            raise CompilerError("phase_2_parser", self.line_number)
        if expected is not None and token != expected:
            raise CompilerError("phase_2_parser", self.line_number)
        self.pos += 1
        return token

    def consume_var(self):
        token = self.current()
        if token is None or not is_var(token):
            raise CompilerError("phase_2_parser", self.line_number)
        self.pos += 1
        return token


def parse_expression(stream):
    token = stream.current()
    if token in {"TRUE", "FALSE"} or is_var(token):
        return stream.consume()
    if token == "L_PAREN":
        stream.consume("L_PAREN")
        if stream.current() == "NOT":
            stream.consume("NOT")
            expr = parse_expression(stream)
            stream.consume("R_PAREN")
            return ["NOT", expr]
        left = parse_expression(stream)
        op = stream.current()
        if op not in {"AND", "OR", "IMPLIES"}:
            raise CompilerError("phase_2_parser", stream.line_number)
        stream.consume()
        right = parse_expression(stream)
        stream.consume("R_PAREN")
        return [op, left, right]
    raise CompilerError("phase_2_parser", stream.line_number)


def parse_statement(stream):
    token = stream.current()
    if token == "LET":
        stream.consume("LET")
        var = stream.consume_var()
        stream.consume("EQ")
        expr = parse_expression(stream)
        return ["LET", var, expr]
    if token == "IF":
        stream.consume("IF")
        expr = parse_expression(stream)
        stream.consume("THEN")
        stmt = parse_statement(stream)
        return ["IF", expr, stmt]
    if token == "PRINT":
        stream.consume("PRINT")
        var = stream.consume_var()
        return ["PRINT", var]
    raise CompilerError("phase_2_parser", stream.line_number)


def parse_line(tokens, line_number):
    stream = TokenStream(tokens, line_number)
    ast = parse_statement(stream)
    if stream.current() is not None:
        raise CompilerError("phase_2_parser", line_number)
    return ast


def is_true(expr):
    return expr == "TRUE"


def is_false(expr):
    return expr == "FALSE"


def is_not_of(a, b):
    return isinstance(a, list) and len(a) == 2 and a[0] == "NOT" and ast_equal(a[1], b)


def optimize_expression(expr):
    if not isinstance(expr, list):
        return expr

    op = expr[0]

    if op == "NOT":
        child = optimize_expression(expr[1])

        if is_true(child):
            return "FALSE"
        if is_false(child):
            return "TRUE"
        if isinstance(child, list) and child[0] == "NOT":
            return optimize_expression(child[1])
        if isinstance(child, list) and child[0] == "AND":
            return optimize_expression(["OR", ["NOT", child[1]], ["NOT", child[2]]])
        if isinstance(child, list) and child[0] == "OR":
            return optimize_expression(["AND", ["NOT", child[1]], ["NOT", child[2]]])
        if isinstance(child, list) and child[0] == "IMPLIES":
            return optimize_expression(["AND", child[1], ["NOT", child[2]]])
        return ["NOT", child]

    left = optimize_expression(expr[1])
    right = optimize_expression(expr[2])

    if op == "IMPLIES":
        return optimize_expression(["OR", ["NOT", left], right])

    if op == "AND":
        if is_false(left) or is_false(right):
            return "FALSE"
        if is_true(left):
            return right
        if is_true(right):
            return left
        if ast_equal(left, right):
            return left
        if is_not_of(left, right) or is_not_of(right, left):
            return "FALSE"
        if isinstance(left, list) and left[0] == "OR" and (ast_equal(left[1], right) or ast_equal(left[2], right)):
            return right
        if isinstance(right, list) and right[0] == "OR" and (ast_equal(right[1], left) or ast_equal(right[2], left)):
            return left
        return ["AND", left, right]

    if op == "OR":
        if is_true(left) or is_true(right):
            return "TRUE"
        if is_false(left):
            return right
        if is_false(right):
            return left
        if ast_equal(left, right):
            return left
        if is_not_of(left, right) or is_not_of(right, left):
            return "TRUE"
        if isinstance(left, list) and left[0] == "AND" and (ast_equal(left[1], right) or ast_equal(left[2], right)):
            return right
        if isinstance(right, list) and right[0] == "AND" and (ast_equal(right[1], left) or ast_equal(right[2], left)):
            return left
        return ["OR", left, right]

    return [op, left, right]


def optimize_statement(stmt):
    kind = stmt[0]
    if kind == "LET":
        return ["LET", stmt[1], optimize_expression(stmt[2])]
    if kind == "IF":
        return ["IF", optimize_expression(stmt[1]), optimize_statement(stmt[2])]
    if kind == "PRINT":
        return stmt[:]
    return stmt[:]


def collect_verification_targets(line_number, original_stmt, optimized_stmt):
    targets = []
    if original_stmt[0] == "LET":
        if not ast_equal(original_stmt[2], optimized_stmt[2]):
            targets.append((line_number, original_stmt[2], optimized_stmt[2]))
    elif original_stmt[0] == "IF":
        if not ast_equal(original_stmt[1], optimized_stmt[1]):
            targets.append((line_number, original_stmt[1], optimized_stmt[1]))
        targets.extend(collect_verification_targets(line_number, original_stmt[2], optimized_stmt[2]))
    return targets


def collect_variables(expr):
    if isinstance(expr, str):
        return {expr} if is_var(expr) else set()
    if len(expr) == 2:
        return collect_variables(expr[1])
    return collect_variables(expr[1]) | collect_variables(expr[2])


def eval_expression(expr, state):
    if expr == "TRUE":
        return "TRUE"
    if expr == "FALSE":
        return "FALSE"
    if is_var(expr):
        if expr not in state:
            raise KeyError(expr)
        return state[expr]
    op = expr[0]
    if op == "NOT":
        return "FALSE" if eval_expression(expr[1], state) == "TRUE" else "TRUE"
    left = eval_expression(expr[1], state)
    right = eval_expression(expr[2], state)
    if op == "AND":
        return "TRUE" if left == "TRUE" and right == "TRUE" else "FALSE"
    if op == "OR":
        return "TRUE" if left == "TRUE" or right == "TRUE" else "FALSE"
    if op == "IMPLIES":
        return "FALSE" if left == "TRUE" and right == "FALSE" else "TRUE"
    raise ValueError(op)


def build_verification(line_number, original_expr, optimized_expr):
    variables = sorted(collect_variables(original_expr) | collect_variables(optimized_expr))
    original_column = []
    optimized_column = []
    for values in product(["TRUE", "FALSE"], repeat=len(variables)):
        state = dict(zip(variables, values))
        original_column.append(eval_expression(original_expr, state))
        optimized_column.append(eval_expression(optimized_expr, state))
    return {
        "line": line_number,
        "variables_tested": variables,
        "ast_original_column": original_column,
        "ast_optimized_column": optimized_column,
        "is_equivalent": "TRUE" if original_column == optimized_column else "FALSE",
    }


def execute_statement(stmt, state, printed_output, line_number):
    kind = stmt[0]
    try:
        if kind == "LET":
            state[stmt[1]] = eval_expression(stmt[2], state)
            return
        if kind == "PRINT":
            if stmt[1] not in state:
                raise CompilerError("phase_4_execution", line_number)
            printed_output.append({"line": line_number, "output": state[stmt[1]]})
            return
        if kind == "IF":
            if eval_expression(stmt[1], state) == "TRUE":
                execute_statement(stmt[2], state, printed_output, line_number)
            return
    except KeyError:
        raise CompilerError("phase_4_execution", line_number)
    raise CompilerError("phase_4_execution", line_number)


def run_pipeline(source_lines):
    result = {}

    phase_1 = []
    tokenized_lines = []
    try:
        for line_number, raw_line in enumerate(source_lines, start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue
            tokens = tokenize_line(stripped, line_number)
            phase_1.append({"line": line_number, "tokens": tokens})
            tokenized_lines.append((line_number, tokens))
    except CompilerError as exc:
        result["phase_1_lexer"] = phase_1
        result["error"] = {"phase": exc.phase, "line": exc.line}
        return result

    result["phase_1_lexer"] = phase_1

    phase_2 = []
    parsed_lines = []
    try:
        for line_number, tokens in tokenized_lines:
            ast = parse_line(tokens, line_number)
            phase_2.append({"line": line_number, "ast": ast})
            parsed_lines.append((line_number, ast))
    except CompilerError as exc:
        result["error"] = {"phase": exc.phase, "line": exc.line}
        return result

    result["phase_2_parser"] = phase_2

    phase_3 = []
    optimized_lines = []
    verification_targets = []
    for line_number, ast in parsed_lines:
        optimized_ast = optimize_statement(ast)
        phase_3.append({"line": line_number, "ast": optimized_ast})
        optimized_lines.append((line_number, optimized_ast))
        verification_targets.extend(collect_verification_targets(line_number, ast, optimized_ast))

    result["phase_3_optimizer"] = phase_3

    verifications = [build_verification(line, original_expr, optimized_expr) for line, original_expr, optimized_expr in verification_targets]

    state = {}
    printed_output = []
    try:
        for line_number, stmt in optimized_lines:
            execute_statement(stmt, state, printed_output, line_number)
    except CompilerError as exc:
        result["error"] = {"phase": exc.phase, "line": exc.line}
        return result

    result["phase_4_execution"] = {
        "verifications": verifications,
        "final_state_dictionary": state,
        "printed_output": printed_output,
    }
    return result


def main():
    if len(sys.argv) != 3:
        print("Usage: python logic_compiler.py <input_file> <output_file>")
        sys.exit(1)

    input_filename = sys.argv[1]
    output_filename = sys.argv[2]

    with open(input_filename, "r", encoding="utf-8") as file:
        source_lines = file.readlines()

    pipeline_results = run_pipeline(source_lines)

    with open(output_filename, "w", encoding="utf-8") as out_file:
        json.dump(pipeline_results, out_file, indent=2)


if __name__ == "__main__":
    main()
