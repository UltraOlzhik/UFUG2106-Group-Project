# LogicScript Optimizing Compiler

This project implements the four-phase LogicScript compiler required in `UFUG2106-Project.pdf`. The compiler reads a LogicScript source file, validates it, builds an abstract syntax tree (AST), simplifies logical expressions using propositional equivalences, verifies that each optimization is logically safe with truth tables, and writes a structured JSON trace for grading.

## Project Goal

The assignment asks for a compiler pipeline for a custom micro-language called LogicScript. The pipeline must:

1. Tokenize each source line into a standardized token list.
2. Parse tokens into a nested AST that follows the recursive grammar.
3. Optimize expressions without using runtime variable values.
4. Verify each optimization by comparing truth-table outputs, then execute the optimized program with a state dictionary.

The final output is a JSON file containing the successful phases and, if compilation succeeds, the execution trace. If a lexical, syntax, or execution error occurs, the pipeline stops cleanly and records the failing phase and source line.

## Directory Structure

`LogicScript/main.py`
Main entry point and pipeline coordinator.

`LogicScript/phase_1_lexer.py`
Phase 1 tokenizer for the LogicScript lexicon.

`LogicScript/phase_2_parser.py`
Phase 2 recursive-descent parser that converts token lists into ASTs.

`LogicScript/phase_3_optimizer.py`
Phase 3 rule-based optimizer that simplifies expressions using logical laws.

`LogicScript/phase_4_execution.py`
Phase 4 verification and execution engine.

`LogicScript/common.py`
Shared token and operator helpers.

`LogicScript/errors.py`
Custom exception class used to stop the pipeline gracefully.

`LogicScript/tests.py`
Lightweight regression tests for valid programs and error handling.

## LogicScript Language Summary

### Valid keywords

`let`, `if`, `then`, `print`

### Valid boolean literals

`T`, `F`

### Valid logical operators

`AND`, `OR`, `NOT`, `IMPLIES`

### Valid symbols

`=`, `(`, `)`

### Valid variables

Any single lowercase letter such as `p`, `q`, or `x`.

## Compiler Design

### Phase 1: Lexical Analysis

The lexer scans each non-empty line and converts source text into canonical tokens such as `LET`, `VAR_P`, `TRUE`, `L_PAREN`, and `R_PAREN`.

If an invalid character or unsupported word appears, the lexer raises a `CompilerError` with:

- the failing phase: `phase_1_lexer`
- the exact line number

### Phase 2: Parsing and AST Generation

The parser uses a recursive-descent strategy because the grammar itself is recursively defined. Expressions are converted into prefix-style nested Python lists, for example:

```python
["LET", "VAR_X", ["OR", "VAR_P", "TRUE"]]
```

This phase also validates syntax rules such as:

- correct statement forms
- required parentheses
- valid operator placement
- no extra trailing tokens

### Phase 3: Static Optimization

The optimizer traverses AST expressions recursively and applies logical equivalence laws without looking at runtime values stored in the state dictionary.

Implemented simplifications include:

- constant negation
- double negation
- De Morgan's laws
- implication rewriting
- domination laws
- identity laws
- idempotent laws
- complement laws
- absorption laws

The optimizer is intentionally rule-driven so new logical laws can be added without rewriting the whole function.

### Phase 4: Verification and Execution

Before execution, every changed expression is checked by generating a complete truth table over all variables appearing in the original and optimized forms. If the result columns do not match, execution stops with a `phase_4_execution` error.

If verification succeeds, the compiler executes the optimized statements line by line:

- `LET` evaluates an expression and updates the state dictionary
- `IF` evaluates a condition and executes the nested statement when the result is `TRUE`
- `PRINT` records the current value of a variable in the output trace

All boolean values in the JSON trace are stored as uppercase strings: `"TRUE"` or `"FALSE"`.

## How to Run

Run the compiler from the `LogicScript` directory:

```bash
python main.py <input_file> <output_file>
```

Example:

```bash
cd LogicScript
python main.py ../program.txt ../compiler_trace.json
```

The compiler reads the input file, processes it through all four phases, and writes the JSON trace to the output path you provide.

## Example Input

```text
let p = T
let q = F
let r = (NOT ((NOT p) AND q))
if r then print p
```

## Example Output Shape

For successful compilation, the JSON contains:

```json
{
  "phase_1_lexer": [...],
  "phase_2_parser": [...],
  "phase_3_optimizer": [...],
  "phase_4_execution": {
    "verifications": [...],
    "final_state_dictionary": {...},
    "printed_output": [...]
  }
}
```

For a compilation error, the JSON contains the phases that completed successfully plus:

```json
{
  "error": {
    "phase": "phase_2_parser",
    "line": 2
  }
}
```

## Testing

Run the local regression tests from the `LogicScript` directory:

```bash
python tests.py
```

The current tests cover:

- the successful example from the assignment
- syntax error handling
- lexical error handling
- constant-folding verification output

## Engineering Choices

### Data structures

- Tokens are stored as flat lists of canonical token strings.
- Parsed statements are stored as nested lists to represent AST structure.
- Runtime values are stored in a Python dictionary mapping variables like `VAR_P` to `"TRUE"` or `"FALSE"`.
- Verification results are stored as JSON-friendly dictionaries for direct export.

### Error handling

The compiler uses a shared `CompilerError` class instead of letting Python crash with a traceback. This keeps the output aligned with the grading format.

### Modularity

Each phase lives in its own file so the pipeline is easy to inspect, test, and maintain. This also matches the assignment's four-phase structure directly.

## Limitations

- The language supports only the grammar specified in the assignment.
- Variables must be a single lowercase letter in the source program.
- The truth-table verifier is exponential in the number of variables, so very large expressions are not efficient.
- The optimizer deliberately avoids distributive expansion because the assignment explicitly says not to use distributive law for simplification.

## Collaboration Notes

This codebase is organized so different teammates can work on separate compiler phases while still understanding the full pipeline. The separation between lexing, parsing, optimization, and execution makes it easier to explain responsibilities during the report and live demonstration.
