"""LogicScript optimizing compiler.

The compiler implements the four phases required by the project brief:
1. lexical analysis,
2. recursive-descent parsing into prefix-form ASTs,
3. static propositional-logic optimization, and
4. truth-table verification followed by execution.

The public command-line interface is:
    python logic_compiler.py <input_file> <output_file>

The JSON output intentionally uses the exact phase names and uppercase string
truth values required by the automated grader. Python booleans are not written to
that trace.
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any


class CompilerError(Exception):
    """Controlled compiler failure used to halt the pipeline without traceback.

    Each compiler phase raises this exception when it detects an invalid source
    program. The top-level pipeline catches it and writes the required JSON error
    object: {"phase": <phase_name>, "line": <source_line>}.
    """

    def __init__(self, phase: str, line: int, message: str = "") -> None:
        self.phase = phase
        self.line = line
        self.message = message
        super().__init__(f"{phase} at line {line}: {message}")


# ---------------------------------------------------------------------------
# Phase 1: Lexical Analysis
# ---------------------------------------------------------------------------

# Token maps are deliberately narrow: anything outside the project lexicon is a
# lexical error, even if it would be accepted by Python or by a larger language.
KEYWORDS = {"let": "LET", "if": "IF", "then": "THEN", "print": "PRINT"}
BOOLEANS = {"T": "TRUE", "F": "FALSE"}
OPERATORS = {"AND": "AND", "OR": "OR", "NOT": "NOT", "IMPLIES": "IMPLIES"}
SYMBOLS = {"=": "EQ", "(": "L_PAREN", ")": "R_PAREN"}
TOKEN_MAPS = (SYMBOLS, KEYWORDS, BOOLEANS, OPERATORS)

# The final alternation branch, '.', guarantees that invalid single characters
# such as '@' are still consumed and can be reported as lexical errors.
TOKEN_PATTERN = re.compile(r"\s+|[()]|=|[A-Za-z]+|.")


AST = str | list[Any]
Statement = list[Any]
PhaseItem = dict[str, Any]
VerificationPair = tuple[int, AST, AST]


def classify_token(piece: str) -> str | None:
    """Convert one source lexeme into the exact standardized token string.

    Variables are the only token class generated structurally rather than by a
    fixed table. The grammar permits exactly one lowercase letter, so `p` becomes
    `VAR_P`; uppercase letters and multi-letter identifiers are rejected unless
    they are defined keywords/operators.
    """

    for token_map in TOKEN_MAPS:
        token = token_map.get(piece)
        if token is not None:
            return token

    if len(piece) == 1 and piece.islower():
        return f"VAR_{piece.upper()}"

    return None


def tokenize_line(line_text: str, line_number: int) -> list[str]:
    """Tokenize one non-empty source line or raise a lexical CompilerError."""

    tokens: list[str] = []

    for match in TOKEN_PATTERN.finditer(line_text):
        piece = match.group(0)
        if piece.isspace():
            continue

        token = classify_token(piece)
        if token is None:
            raise CompilerError("phase_1_lexer", line_number, f"Invalid token: {piece}")
        tokens.append(token)

    return tokens


def run_lexer(source_lines: list[str]) -> list[PhaseItem]:
    """Run Phase 1 over all source lines while preserving real line numbers.

    Blank lines are ignored as formatting whitespace. A program with no actual
    statements is rejected because the grammar defines a valid program as one or
    more statements.
    """

    phase_1_output: list[PhaseItem] = []

    for line_number, raw_line in enumerate(source_lines, start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue

        phase_1_output.append({
            "line": line_number,
            "tokens": tokenize_line(stripped, line_number),
        })

    if not phase_1_output:
        raise CompilerError("phase_1_lexer", 1, "Program must contain at least one statement")

    return phase_1_output


# ---------------------------------------------------------------------------
# Phase 2: Syntax Validation and AST Generation
# ---------------------------------------------------------------------------

BOOLEAN_LITERALS = {"TRUE", "FALSE"}
BINARY_OPERATORS = {"AND", "OR", "IMPLIES"}


def is_variable(token: Any) -> bool:
    """Return True only for normalized LogicScript variable tokens."""

    return isinstance(token, str) and token.startswith("VAR_")


class TokenStream:
    """Position-tracking view over one line's token list.

    Recursive-descent parsing needs one-token lookahead and a reliable way to
    report the source line where a grammar violation occurs. This small stream
    object provides both without using any external parser/AST library.
    """

    def __init__(self, tokens: list[str], line_number: int) -> None:
        self.tokens = tokens
        self.line_number = line_number
        self.position = 0

    def current(self) -> str | None:
        """Return the current token without advancing the stream."""

        if self.position < len(self.tokens):
            return self.tokens[self.position]
        return None

    def consume(self, expected: str | None = None) -> str:
        """Consume and return the current token, optionally enforcing its value."""

        token = self.current()

        if token is None:
            raise CompilerError("phase_2_parser", self.line_number, "Unexpected end of line")

        if expected is not None and token != expected:
            raise CompilerError(
                "phase_2_parser",
                self.line_number,
                f"Expected {expected}, found {token}",
            )

        self.position += 1
        return token

    def consume_variable(self) -> str:
        """Consume a required variable token."""

        token = self.current()
        if not is_variable(token):
            raise CompilerError("phase_2_parser", self.line_number, "Expected variable")
        self.position += 1
        return token


def parse_expression(stream: TokenStream) -> AST:
    """Parse one expression using the assignment's recursive syntax rules.

    Base cases are literals and variables. Recursive cases must be fully
    parenthesized. The returned AST uses prefix notation, so `(p AND q)` becomes
    `["AND", "VAR_P", "VAR_Q"]`.
    """

    token = stream.current()

    if token in BOOLEAN_LITERALS:
        return stream.consume()

    if is_variable(token):
        return stream.consume()

    if token == "L_PAREN":
        stream.consume("L_PAREN")

        # Unary recursive case: (NOT E)
        if stream.current() == "NOT":
            stream.consume("NOT")
            inner_expr = parse_expression(stream)
            stream.consume("R_PAREN")
            return ["NOT", inner_expr]

        # Binary recursive case: (E1 OP E2), where OP is AND, OR, or IMPLIES.
        left_expr = parse_expression(stream)
        operator = stream.current()

        if operator not in BINARY_OPERATORS:
            raise CompilerError("phase_2_parser", stream.line_number, "Expected binary operator")

        stream.consume()
        right_expr = parse_expression(stream)
        stream.consume("R_PAREN")
        return [operator, left_expr, right_expr]

    raise CompilerError("phase_2_parser", stream.line_number, "Invalid expression")


def parse_statement(stream: TokenStream) -> Statement:
    """Parse one LogicScript statement from the current stream position."""

    token = stream.current()
    statement_parsers = {
        "LET": parse_let_statement,
        "IF": parse_if_statement,
        "PRINT": parse_print_statement,
    }

    parser = statement_parsers.get(token)
    if parser is not None:
        return parser(stream)

    raise CompilerError("phase_2_parser", stream.line_number, "Invalid statement")


def parse_let_statement(stream: TokenStream) -> Statement:
    """Parse: let <Variable> = <Expression>."""

    stream.consume("LET")
    variable = stream.consume_variable()
    stream.consume("EQ")
    expression = parse_expression(stream)
    return ["LET", variable, expression]


def parse_if_statement(stream: TokenStream) -> Statement:
    """Parse: if <Expression> then <Statement>."""

    stream.consume("IF")
    condition = parse_expression(stream)
    stream.consume("THEN")
    statement = parse_statement(stream)
    return ["IF", condition, statement]


def parse_print_statement(stream: TokenStream) -> Statement:
    """Parse: print <Variable>."""

    stream.consume("PRINT")
    variable = stream.consume_variable()
    return ["PRINT", variable]


def parse_line(tokens: list[str], line_number: int) -> Statement:
    """Parse one full source line and reject trailing tokens."""

    stream = TokenStream(tokens, line_number)
    ast = parse_statement(stream)

    if stream.current() is not None:
        raise CompilerError("phase_2_parser", line_number, "Extra tokens after statement")

    return ast


def run_parser(phase_1_output: list[PhaseItem]) -> list[PhaseItem]:
    """Run Phase 2 over the tokenized source program."""

    phase_2_output: list[PhaseItem] = []

    for item in phase_1_output:
        phase_2_output.append({
            "line": item["line"],
            "ast": parse_line(item["tokens"], item["line"]),
        })

    return phase_2_output


# ---------------------------------------------------------------------------
# Phase 3: Static Optimization Pass
# ---------------------------------------------------------------------------


def ast_equal(left: AST, right: AST) -> bool:
    """Structural equality helper for AST rewrite rules."""

    return left == right


def is_true(expr: AST) -> bool:
    return expr == "TRUE"


def is_false(expr: AST) -> bool:
    return expr == "FALSE"


def is_not(expr: AST) -> bool:
    return isinstance(expr, list) and len(expr) == 2 and expr[0] == "NOT"


def is_binary(expr: AST, operator: str | None = None) -> bool:
    if not (isinstance(expr, list) and len(expr) == 3):
        return False
    if operator is None:
        return True
    return expr[0] == operator


def is_negation_of(left: AST, right: AST) -> bool:
    """Return True when `left` has the form NOT right."""

    return is_not(left) and ast_equal(left[1], right)


def absorption_match(expr: AST, target: AST, absorbing_operator: str) -> bool:
    """Detect one side of an absorption law pattern.

    Example: in `p OR (p AND q)`, the right branch matches target `p` with the
    absorbing operator `AND`, so the whole expression simplifies to `p`.
    """

    return is_binary(expr, absorbing_operator) and (
        ast_equal(expr[1], target) or ast_equal(expr[2], target)
    )


def collect_associative_operands(expr: AST, operator: str) -> list[AST]:
    """Flatten nested chains of the same associative operator.

    This is structural normalization only; it does not distribute expressions or
    consult runtime truth values.
    """

    if is_binary(expr, operator):
        return (
            collect_associative_operands(expr[1], operator)
            + collect_associative_operands(expr[2], operator)
        )
    return [expr]


def build_associative_expression(operator: str, operands: list[AST]) -> AST:
    """Rebuild a flattened associative operand list as a binary AST."""

    if len(operands) == 1:
        return operands[0]

    result = operands[-1]
    for operand in reversed(operands[:-1]):
        result = [operator, operand, result]
    return result


def apply_rule_list(*args: AST, rules: list[Any]) -> AST | None:
    """Return the first successful rewrite from an ordered rule list."""

    for rule in rules:
        result = rule(*args)
        if result is not None:
            return result
    return None


# NOT rules. These are standard propositional equivalences applied to syntax.
def rule_not_constant(child: AST) -> AST | None:
    if is_true(child):
        return "FALSE"
    if is_false(child):
        return "TRUE"
    return None


def rule_double_negation(child: AST) -> AST | None:
    if is_not(child):
        return optimize_expression(child[1])
    return None


def rule_de_morgan_and(child: AST) -> AST | None:
    if is_binary(child, "AND"):
        return optimize_expression(["OR", ["NOT", child[1]], ["NOT", child[2]]])
    return None


def rule_de_morgan_or(child: AST) -> AST | None:
    if is_binary(child, "OR"):
        return optimize_expression(["AND", ["NOT", child[1]], ["NOT", child[2]]])
    return None


def rule_not_implies(child: AST) -> AST | None:
    if is_binary(child, "IMPLIES"):
        return optimize_expression(["AND", child[1], ["NOT", child[2]]])
    return None


NOT_RULES = [
    rule_not_constant,
    rule_double_negation,
    rule_de_morgan_and,
    rule_de_morgan_or,
    rule_not_implies,
]


# Binary AND/OR rules. The project explicitly forbids distributive expansion, so
# these rules only reduce or normalize the AST.
def rule_and_domination(left: AST, right: AST) -> AST | None:
    if is_false(left) or is_false(right):
        return "FALSE"
    return None


def rule_and_identity(left: AST, right: AST) -> AST | None:
    if is_true(left):
        return right
    if is_true(right):
        return left
    return None


def rule_or_domination(left: AST, right: AST) -> AST | None:
    if is_true(left) or is_true(right):
        return "TRUE"
    return None


def rule_or_identity(left: AST, right: AST) -> AST | None:
    if is_false(left):
        return right
    if is_false(right):
        return left
    return None


def rule_idempotent(left: AST, right: AST) -> AST | None:
    if ast_equal(left, right):
        return left
    return None


def rule_and_complement(left: AST, right: AST) -> AST | None:
    if is_negation_of(left, right) or is_negation_of(right, left):
        return "FALSE"
    return None


def rule_or_complement(left: AST, right: AST) -> AST | None:
    if is_negation_of(left, right) or is_negation_of(right, left):
        return "TRUE"
    return None


def rule_and_absorption(left: AST, right: AST) -> AST | None:
    if absorption_match(left, right, "OR"):
        return right
    if absorption_match(right, left, "OR"):
        return left
    return None


def rule_or_absorption(left: AST, right: AST) -> AST | None:
    if absorption_match(left, right, "AND"):
        return right
    if absorption_match(right, left, "AND"):
        return left
    return None


def rule_and_associative(left: AST, right: AST) -> AST | None:
    if is_binary(left, "AND") or is_binary(right, "AND"):
        operands = collect_associative_operands(["AND", left, right], "AND")
        rebuilt = build_associative_expression("AND", operands)
        if not ast_equal(rebuilt, ["AND", left, right]):
            return optimize_expression(rebuilt)
    return None


def rule_or_associative(left: AST, right: AST) -> AST | None:
    if is_binary(left, "OR") or is_binary(right, "OR"):
        operands = collect_associative_operands(["OR", left, right], "OR")
        rebuilt = build_associative_expression("OR", operands)
        if not ast_equal(rebuilt, ["OR", left, right]):
            return optimize_expression(rebuilt)
    return None


BINARY_RULES = {
    "AND": [
        rule_and_domination,
        rule_and_identity,
        rule_idempotent,
        rule_and_complement,
        rule_and_absorption,
        rule_and_associative,
    ],
    "OR": [
        rule_or_domination,
        rule_or_identity,
        rule_idempotent,
        rule_or_complement,
        rule_or_absorption,
        rule_or_associative,
    ],
}

# Rewrite implication into an equivalent OR/NOT expression so the same optimizer
# and evaluator can treat all simplifications uniformly.
REWRITE_RULES = {
    "IMPLIES": lambda left, right: ["OR", ["NOT", left], right],
}


def optimize_not_expression(child: AST) -> AST:
    optimized = apply_rule_list(child, rules=NOT_RULES)
    if optimized is not None:
        return optimized
    return ["NOT", child]


def optimize_binary_expression(operator: str, left: AST, right: AST) -> AST:
    rewritten = REWRITE_RULES.get(operator)
    if rewritten is not None:
        return optimize_expression(rewritten(left, right))

    optimized = apply_rule_list(left, right, rules=BINARY_RULES.get(operator, []))
    if optimized is not None:
        return optimized

    return [operator, left, right]


def optimize_expression(expr: AST) -> AST:
    """Recursively optimize an expression without using execution state.

    The traversal is bottom-up: children are simplified first, then the parent
    operator is rewritten if a propositional equivalence applies.
    """

    if not isinstance(expr, list):
        return expr

    operator = expr[0]
    if operator == "NOT":
        child = optimize_expression(expr[1])
        return optimize_not_expression(child)

    left = optimize_expression(expr[1])
    right = optimize_expression(expr[2])
    return optimize_binary_expression(operator, left, right)


def optimize_statement(statement: Statement) -> Statement:
    """Optimize expression subtrees while preserving statement structure."""

    kind = statement[0]

    if kind == "LET":
        return ["LET", statement[1], optimize_expression(statement[2])]
    if kind == "IF":
        return ["IF", optimize_expression(statement[1]), optimize_statement(statement[2])]
    return statement[:]


def collect_verification_pairs(
    line_number: int,
    original_statement: Statement,
    optimized_statement: Statement,
) -> list[VerificationPair]:
    """Collect every changed expression that needs truth-table verification."""

    pairs: list[VerificationPair] = []

    if original_statement[0] == "LET":
        if not ast_equal(original_statement[2], optimized_statement[2]):
            pairs.append((line_number, original_statement[2], optimized_statement[2]))

    elif original_statement[0] == "IF":
        if not ast_equal(original_statement[1], optimized_statement[1]):
            pairs.append((line_number, original_statement[1], optimized_statement[1]))
        pairs.extend(
            collect_verification_pairs(
                line_number,
                original_statement[2],
                optimized_statement[2],
            )
        )

    return pairs


def run_optimizer(phase_2_output: list[PhaseItem]) -> tuple[list[PhaseItem], list[VerificationPair]]:
    """Run Phase 3 and remember changed expressions for Phase 4 verification."""

    phase_3_output: list[PhaseItem] = []
    verification_pairs: list[VerificationPair] = []

    for item in phase_2_output:
        line_number = item["line"]
        original_ast = item["ast"]
        optimized_ast = optimize_statement(original_ast)

        phase_3_output.append({
            "line": line_number,
            "ast": optimized_ast,
        })

        verification_pairs.extend(
            collect_verification_pairs(line_number, original_ast, optimized_ast)
        )

    return phase_3_output, verification_pairs


# ---------------------------------------------------------------------------
# Phase 4: Equivalence Verification and Execution
# ---------------------------------------------------------------------------

EXPRESSION_EVALUATORS = {
    "AND": lambda left, right: "TRUE" if left == "TRUE" and right == "TRUE" else "FALSE",
    "OR": lambda left, right: "TRUE" if left == "TRUE" or right == "TRUE" else "FALSE",
    "IMPLIES": lambda left, right: "FALSE" if left == "TRUE" and right == "FALSE" else "TRUE",
}


def collect_variables(expr: AST) -> set[str]:
    """Return all variable tokens appearing in an expression AST."""

    if isinstance(expr, str):
        return {expr} if is_variable(expr) else set()
    if len(expr) == 2:
        return collect_variables(expr[1])
    return collect_variables(expr[1]) | collect_variables(expr[2])


def generate_truth_assignments(variables: list[str]) -> list[dict[str, str]]:
    """Generate the full 2^n truth-table assignments for a variable list."""

    if not variables:
        return [{}]

    rest_assignments = generate_truth_assignments(variables[:-1])
    assignments: list[dict[str, str]] = []
    current_variable = variables[-1]

    for assignment in rest_assignments:
        true_assignment = assignment.copy()
        true_assignment[current_variable] = "TRUE"
        assignments.append(true_assignment)

        false_assignment = assignment.copy()
        false_assignment[current_variable] = "FALSE"
        assignments.append(false_assignment)

    return assignments


def eval_expression(expr: AST, state: dict[str, str], line_number: int) -> str:
    """Evaluate an expression under a state dictionary of TRUE/FALSE strings."""

    if expr == "TRUE":
        return "TRUE"
    if expr == "FALSE":
        return "FALSE"

    if is_variable(expr):
        if expr not in state:
            raise CompilerError("phase_4_execution", line_number, f"Undefined variable: {expr}")
        return state[expr]

    operator = expr[0]
    if operator == "NOT":
        value = eval_expression(expr[1], state, line_number)
        return "FALSE" if value == "TRUE" else "TRUE"

    left = eval_expression(expr[1], state, line_number)
    right = eval_expression(expr[2], state, line_number)

    evaluator = EXPRESSION_EVALUATORS.get(operator)
    if evaluator is not None:
        return evaluator(left, right)

    raise CompilerError("phase_4_execution", line_number, f"Unknown operator: {operator}")


def build_verification(line_number: int, original_expr: AST, optimized_expr: AST) -> PhaseItem:
    """Build one truth-table equivalence record for the output JSON."""

    variables = sorted(collect_variables(original_expr) | collect_variables(optimized_expr))
    original_column: list[str] = []
    optimized_column: list[str] = []

    for state in generate_truth_assignments(variables):
        original_column.append(eval_expression(original_expr, state, line_number))
        optimized_column.append(eval_expression(optimized_expr, state, line_number))

    return {
        "line": line_number,
        "variables_tested": variables,
        "ast_original_column": original_column,
        "ast_optimized_column": optimized_column,
        "is_equivalent": "TRUE" if original_column == optimized_column else "FALSE",
    }


def execute_statement(
    statement: Statement,
    state: dict[str, str],
    printed_output: list[PhaseItem],
    line_number: int,
) -> None:
    """Execute one optimized statement against the mutable state dictionary."""

    handlers = {
        "LET": execute_let_statement,
        "PRINT": execute_print_statement,
        "IF": execute_if_statement,
    }
    kind = statement[0]
    handler = handlers.get(kind)
    if handler is None:
        raise CompilerError("phase_4_execution", line_number, f"Unknown statement: {kind}")
    handler(statement, state, printed_output, line_number)


def execute_let_statement(
    statement: Statement,
    state: dict[str, str],
    _printed_output: list[PhaseItem],
    line_number: int,
) -> None:
    """Evaluate an assignment and update the state relation."""

    state[statement[1]] = eval_expression(statement[2], state, line_number)


def execute_print_statement(
    statement: Statement,
    state: dict[str, str],
    printed_output: list[PhaseItem],
    line_number: int,
) -> None:
    """Capture a print output instead of writing it directly to stdout."""

    variable = statement[1]
    if variable not in state:
        raise CompilerError("phase_4_execution", line_number, f"Undefined variable: {variable}")
    printed_output.append({
        "line": line_number,
        "output": state[variable],
    })


def execute_if_statement(
    statement: Statement,
    state: dict[str, str],
    printed_output: list[PhaseItem],
    line_number: int,
) -> None:
    """Execute the nested statement only when the condition evaluates to TRUE."""

    condition_value = eval_expression(statement[1], state, line_number)
    if condition_value == "TRUE":
        execute_statement(statement[2], state, printed_output, line_number)


def run_execution(phase_3_output: list[PhaseItem], verification_pairs: list[VerificationPair]) -> PhaseItem:
    """Verify all optimizations, then execute the optimized program."""

    verifications: list[PhaseItem] = []

    # Safety net: an optimizer bug cannot silently affect program execution.
    for line_number, original_expr, optimized_expr in verification_pairs:
        verification = build_verification(line_number, original_expr, optimized_expr)
        if verification["is_equivalent"] != "TRUE":
            raise CompilerError(
                "phase_4_execution",
                line_number,
                "Optimization produced a non-equivalent expression",
            )
        verifications.append(verification)

    state: dict[str, str] = {}
    printed_output: list[PhaseItem] = []

    for item in phase_3_output:
        execute_statement(item["ast"], state, printed_output, item["line"])

    return {
        "verifications": verifications,
        "final_state_dictionary": state,
        "printed_output": printed_output,
    }


# ---------------------------------------------------------------------------
# Pipeline and Command-Line Interface
# ---------------------------------------------------------------------------

PIPELINE_PHASES = [
    ("phase_1_lexer", run_lexer),
    ("phase_2_parser", run_parser),
]


def compile_source_lines(source_lines: list[str]) -> dict[str, Any]:
    """Compile a source program represented as a list of source lines.

    The result always has the project-specified JSON shape. If a phase fails,
    only the completed phase outputs plus the final `error` object are returned.
    """

    result: dict[str, Any] = {}

    try:
        phase_output: Any = source_lines
        for phase_name, phase_runner in PIPELINE_PHASES:
            phase_output = phase_runner(phase_output)
            result[phase_name] = phase_output

        phase_3_output, verification_pairs = run_optimizer(phase_output)
        result["phase_3_optimizer"] = phase_3_output

        phase_4_output = run_execution(phase_3_output, verification_pairs)
        result["phase_4_execution"] = phase_4_output

        return result

    except CompilerError as error:
        result["error"] = {
            "phase": error.phase,
            "line": error.line,
        }
        return result


def compile_file(input_filename: str) -> dict[str, Any]:
    """Read a source file and compile its contents."""

    with open(input_filename, "r", encoding="utf-8") as file:
        source_lines = file.readlines()
    return compile_source_lines(source_lines)


def main() -> None:
    """Command-line entry point used by the automated grader."""

    if len(sys.argv) != 3:
        print("Usage: python logic_compiler.py <input_file> <output_file>")
        sys.exit(1)

    results = compile_file(sys.argv[1])

    with open(sys.argv[2], "w", encoding="utf-8") as out_file:
        json.dump(results, out_file, indent=2)


if __name__ == "__main__":
    main()
