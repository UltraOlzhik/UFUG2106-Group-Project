from phase_1_lexer import CompilerError

# Expression token categories.
BOOLEAN_LITERALS = {"TRUE", "FALSE"}
BINARY_OPERATORS = {"AND", "OR", "IMPLIES"}


# Phase 1 variable format.
def is_variable(token):
    return isinstance(token, str) and token.startswith("VAR_")


class TokenStream:
    # Token list plus current read position.
    def __init__(self, tokens, line_number):
        self.tokens = tokens
        self.line_number = line_number
        self.position = 0

    # Look ahead without consuming.
    def current(self):
        if self.position < len(self.tokens):
            return self.tokens[self.position]
        return None

    # Consume one token, optionally asserting its value.
    def consume(self, expected=None):
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

    # Consume a variable token.
    def consume_variable(self):
        token = self.current()
        if not is_variable(token):
            raise CompilerError("phase_2_parser", self.line_number, "Expected variable")
        self.position += 1
        return token


# Parse one expression subtree.
def parse_expression(stream):
    token = stream.current()

    if token in BOOLEAN_LITERALS:
        return stream.consume()

    if is_variable(token):
        return stream.consume()

    if token == "L_PAREN":
        stream.consume("L_PAREN")

        if stream.current() == "NOT":
            stream.consume("NOT")
            inner_expr = parse_expression(stream)
            stream.consume("R_PAREN")
            return ["NOT", inner_expr]

        left_expr = parse_expression(stream)
        operator = stream.current()

        if operator not in BINARY_OPERATORS:
            raise CompilerError("phase_2_parser", stream.line_number, "Expected binary operator")

        stream.consume()
        right_expr = parse_expression(stream)
        stream.consume("R_PAREN")
        return [operator, left_expr, right_expr]

    raise CompilerError("phase_2_parser", stream.line_number, "Invalid expression")


# Parse one statement node.
def parse_statement(stream):
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


# Parse `let <var> = <expr>`.
def parse_let_statement(stream):
    stream.consume("LET")
    variable = stream.consume_variable()
    stream.consume("EQ")
    expression = parse_expression(stream)
    return ["LET", variable, expression]


# Parse `if <expr> then <statement>`.
def parse_if_statement(stream):
    stream.consume("IF")
    condition = parse_expression(stream)
    stream.consume("THEN")
    statement = parse_statement(stream)
    return ["IF", condition, statement]


# Parse `print <var>`.
def parse_print_statement(stream):
    stream.consume("PRINT")
    variable = stream.consume_variable()
    return ["PRINT", variable]


# Parse one full line.
def parse_line(tokens, line_number):
    stream = TokenStream(tokens, line_number)
    ast = parse_statement(stream)

    if stream.current() is not None:
        raise CompilerError("phase_2_parser", line_number, "Extra tokens after statement")

    return ast


# Parse all tokenized lines.
def run_parser(phase_1_output):
    phase_2_output = []

    for item in phase_1_output:
        line_number = item["line"]
        tokens = item["tokens"]
        ast = parse_line(tokens, line_number)
        phase_2_output.append({
            "line": line_number,
            "ast": ast,
        })

    return phase_2_output
