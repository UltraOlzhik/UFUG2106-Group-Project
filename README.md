# LogicScript Optimizing Compiler

LogicScript is a four-phase optimizing compiler for a small propositional-logic language. It reads a source program, validates the syntax, builds prefix-form abstract syntax trees, applies static logical simplifications, verifies each optimization with a full truth table, and writes a JSON execution trace.

The implementation is contained in one file, `logic_compiler.py`, as required by the project specification. It does not use external parsing or AST libraries.

## Files

```text
logic_compiler.py   # compiler implementation and command-line entry point
tests.py            # dependency-free regression test suite
README.md           # execution, language, and testing instructions
report.pdf          # technical brief
```

## Requirements

Python 3.10 or later is recommended. The compiler uses only the Python standard library.

No installation step is required.

## Run the compiler

```bash
python logic_compiler.py <input_file> <output_file>
```

Example:

```bash
python logic_compiler.py program.txt compiler_trace.json
```

The compiler writes the full JSON trace to the output file. It does not print program output directly to the terminal; LogicScript `print` statements are captured inside the `phase_4_execution.printed_output` list.

## Example program

Create `program.txt`:

```txt
let p = T
let q = F
let r = (NOT ((NOT p) AND q))
if r then print p
```

Run:

```bash
python logic_compiler.py program.txt compiler_trace.json
```

The output JSON contains four successful phases:

```json
{
  "phase_1_lexer": [
    {"line": 1, "tokens": ["LET", "VAR_P", "EQ", "TRUE"]}
  ],
  "phase_2_parser": [
    {"line": 1, "ast": ["LET", "VAR_P", "TRUE"]}
  ],
  "phase_3_optimizer": [
    {"line": 1, "ast": ["LET", "VAR_P", "TRUE"]}
  ],
  "phase_4_execution": {
    "verifications": [],
    "final_state_dictionary": {"VAR_P": "TRUE"},
    "printed_output": []
  }
}
```

For the full example program above, the final state includes `VAR_P`, `VAR_Q`, and `VAR_R`, and the printed output is `TRUE` on line 4.

## Language summary

A LogicScript program is one or more statements. Blank lines are ignored, but line numbers are preserved for error reporting.

Supported terminal symbols:

```text
Keywords:   let, if, then, print
Booleans:   T, F
Operators:  AND, OR, NOT, IMPLIES
Symbols:    =, (, )
Variables:  one lowercase letter, such as p, q, x
```

Valid statements:

```text
let <variable> = <expression>
if <expression> then <statement>
print <variable>
```

Valid expressions:

```text
T
F
p
(NOT p)
(p AND q)
(p OR q)
(p IMPLIES q)
```

All recursive expressions must be fully parenthesized. For example, `let x = (p AND T)` is valid, but `let x = p AND T` is not.

## Compiler phases

### Phase 1: Lexer

The lexer converts source text into standardized tokens. Examples:

```text
let   -> LET
T     -> TRUE
(     -> L_PAREN
p     -> VAR_P
```

Invalid symbols, uppercase variable names, and multi-letter identifiers are rejected in this phase.

### Phase 2: Parser

The parser validates the recursive grammar and builds nested-list ASTs in prefix notation.

Example:

```text
(p AND q)
```

becomes:

```json
["AND", "VAR_P", "VAR_Q"]
```

A statement such as:

```text
let x = (p OR T)
```

becomes:

```json
["LET", "VAR_X", ["OR", "VAR_P", "TRUE"]]
```

### Phase 3: Optimizer

The optimizer recursively simplifies expression subtrees using propositional equivalence laws. It is static: it does not read the runtime state dictionary and does not evaluate variables.

Implemented simplifications include:

```text
p OR TRUE        -> TRUE
p AND TRUE       -> p
p OR FALSE       -> p
p AND FALSE      -> FALSE
NOT (NOT p)      -> p
NOT (p AND q)    -> (NOT p) OR (NOT q)
NOT (p OR q)     -> (NOT p) AND (NOT q)
p OR (NOT p)     -> TRUE
p AND (NOT p)    -> FALSE
p OR (p AND q)   -> p
p AND (p OR q)   -> p
p IMPLIES q      -> (NOT p) OR q
```

The optimizer does not use the distributive law, because the project specification warns against expanding the syntax tree.

### Phase 4: Verification and execution

Before execution, every changed expression is verified with a complete truth table over all variables appearing in the original or optimized expression. If any optimized expression is not equivalent to the original, the compiler halts with a `phase_4_execution` error.

After verification, the compiler executes the optimized statements using a state dictionary such as:

```json
{
  "VAR_P": "TRUE",
  "VAR_Q": "FALSE"
}
```

All truth values in the JSON trace are uppercase strings, not Python booleans.

## Error output

The compiler catches source-program errors and writes a JSON error object instead of crashing with a Python traceback.

Example invalid program:

```txt
let p = T
if (p AND ) then print p
```

Expected structure:

```json
{
  "phase_1_lexer": [
    {"line": 1, "tokens": ["LET", "VAR_P", "EQ", "TRUE"]},
    {"line": 2, "tokens": ["IF", "L_PAREN", "VAR_P", "AND", "R_PAREN", "THEN", "PRINT", "VAR_P"]}
  ],
  "error": {
    "phase": "phase_2_parser",
    "line": 2
  }
}
```

## Run the tests

The test suite uses only standard Python assertions:

```bash
python tests.py
```

It also works with pytest if pytest is available:

```bash
pytest tests.py
```

The tests cover:

```text
successful full compilation
command-line JSON output
empty and blank programs
lexical errors
syntax errors
runtime undefined-variable errors
blank-line line-number preservation
nested conditionals
static optimization behavior
truth-table verification records
complement, absorption, double negation, implication, and De Morgan rewrites
```

## Common invalid programs

Uppercase variable:

```txt
let X = T
```

Binary expression without parentheses:

```txt
let p = x AND F
```

Missing operand:

```txt
if (p AND ) then print p
```

Multi-line statement:

```txt
if (x OR p)
then print p
```

LogicScript expects one complete statement per non-empty source line.
