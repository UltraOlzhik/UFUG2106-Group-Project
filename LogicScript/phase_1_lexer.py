import re


class CompilerError(Exception):
    def __init__(self, phase, line, message=""):
        self.phase = phase
        self.line = line
        self.message = message
        super().__init__(f"{phase} at line {line}: {message}")

KEYWORDS = {"let": "LET", "if": "IF", "then": "THEN", "print": "PRINT"}
BOOLEANS = {"T": "TRUE", "F": "FALSE"}
OPERATORS = {"AND": "AND", "OR": "OR", "NOT": "NOT", "IMPLIES": "IMPLIES"}
SYMBOLS = {"=": "EQ", "(": "L_PAREN", ")": "R_PAREN"}
TOKEN_MAPS = (SYMBOLS, KEYWORDS, BOOLEANS, OPERATORS)

TOKEN_PATTERN = re.compile(r"\s+|[()]|=|[A-Za-z]+|.")


# Convert one raw source fragment into its canonical token string.
def classify_token(piece):
    for token_map in TOKEN_MAPS:
        token = token_map.get(piece)
        if token is not None:
            return token

    if len(piece) == 1 and piece.islower():
        return f"VAR_{piece.upper()}"

    return None


# Tokenize a single source line and report lexical errors with the line number.
def tokenize_line(line_text, line_number):
    tokens = []

    for match in TOKEN_PATTERN.finditer(line_text):
        piece = match.group(0)

        if piece.isspace():
            continue

        token = classify_token(piece)
        if token is None:
            raise CompilerError("phase_1_lexer", line_number, f"Invalid token: {piece}")
        tokens.append(token)

    return tokens


# Tokenize every non-empty line and package the phase 1 output format.
def run_lexer(source_lines):
    phase_1_output = []

    for line_number, raw_line in enumerate(source_lines, start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue

        tokens = tokenize_line(stripped, line_number)
        phase_1_output.append({
            "line": line_number,
            "tokens": tokens,
        })

    return phase_1_output
