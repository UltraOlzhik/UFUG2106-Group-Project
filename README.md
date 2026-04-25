# LogicScript
LogicScript is a boolean-typed language. It operates only on boolean values and boolean expressions. The compiler takes a `.txt` source file written in LogicScript syntax, validates it, optimizes it, verifies that the optimization is logically safe, and then executes the optimized program.

The compiler works in 4 phases:  
phase 1. Tokenize each source line into a standardized token list. It reads the source file line by line and validates that every fragment belongs to the language,  
phase 2. Parse tokens into a nested AST that follows the recursive grammar. It builds an abstract syntax tree (AST) for each statement,  
phase 3. Optimize expressions without using runtime variable values. It simplifies logical expressions using propositional equivalences only,  
phase 4. Verify each optimization by comparing truth-table outputs, then execute the optimized program with a state dictionary. It proves that each optimization is logically safe with truth tables, then writes a structured JSON trace.

The final output is a JSON file containing the successful phases and, if compilation succeeds, the verification and execution trace. If a lexical, syntax, or execution error occurs, the pipeline stops cleanly and records the failing phase and source line.

## How to Run
`logic_compiler.py` is the command-line entry point required by the assignment. It calls the compiler pipeline implemented in `LogicScript/main.py`, which in turn uses the four phase files in the directory. This keeps the project modular while still matching the grading format.

```bash
python logic_compiler.py <input_file> <output_file>
```

For example, if you have the following source file:
```text
let p = T
let q = F
let r = (NOT ((NOT p) AND q))
if r then print p
```
you run the program with
```bash
python logic_compiler.py program123.txt program123_trace.json
```

The compiler then outputs a JSON trace file such as
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

## Implementation
The project has the following directory structure:

```text
group_project/
├── README.md
├── logic_compiler.py
├── program.txt
├── compiler_trace.json
├── LogicScript/
│   ├── main.py
│   ├── phase_1_lexer.py
│   ├── phase_2_parser.py
│   ├── phase_3_optimizer.py
│   ├── phase_4_execution.py
│   └── tests.py
├── report/
│   ├── report.tex
│   └── report.pdf
└── transcript/
    ├── overview.md
    ├── 1_lexer.md
    ├── 2_parser.md
    ├── 3_optimizer.md
    └── 4_executioner.md
```

The `LogicScript/` directory contains the modular implementation of the compiler. The `report/` directory contains the technical brief in LaTeX and PDF form. The `transcript/` directory contains the working explanations used to prepare the final report.

### LogicScript Language
The language is intentionally simple. Variables are a priori of boolean type: `T` stands for boolean true and `F` stands for boolean false.

Variable names can only be a single lowercase letter, for example `x`, `a`, `p`. LogicScript understands only the symbols `=`, `(`, `)`, the capitalized logical operators `AND`, `OR`, `NOT`, `IMPLIES`, and the keywords `let`, `if`, `then`, `print`.

LogicScript uses the following statement forms:
- `let` for assignments, for example `let x = T`
- `print` for printing the value of a variable, for example `print x`
- `if`, `then` for conditional statements, for example `if x then print y`

Expressions follow the recursive grammar of the assignment:
- base expressions: `T`, `F`, or a single variable
- unary form: `(NOT E)`
- binary forms: `(E1 AND E2)`, `(E1 OR E2)`, `(E1 IMPLIES E2)`

So the language is fully parenthesized for recursive logical expressions. This keeps the grammar unambiguous and makes the recursive parser simpler.

## Compiler Design
This is a brief explanation. For more details, please refer to `report/report.pdf`.

### Phase 1: Lexical Analysis
The lexer scans each non-empty line and converts source text into canonical tokens such as `LET`, `VAR_P`, `TRUE`, `L_PAREN`, and `R_PAREN`. It uses fixed token tables together with a regular expression scanner. If a fragment does not belong to the LogicScript alphabet, the lexer raises `phase_1_lexer` with the exact source line.

### Phase 2: Parsing and AST Generation
The parser uses a recursive-descent strategy because the grammar itself is recursively defined. It converts token lists into prefix-style nested Python lists, for example `["LET", "VAR_X", ["OR", "VAR_P", "TRUE"]]`. If the token order does not follow the grammar, the parser stops and reports `phase_2_parser` with the failing source line.

### Phase 3: Static Optimization
The optimizer traverses AST expressions recursively and applies logical equivalence laws without looking at runtime values stored in the state dictionary. It uses rules such as constant folding, double negation, De Morgan's laws, complement, absorption, and implication rewriting. This phase is purely static and does not execute the program.

### Phase 4: Verification and Execution
Phase 4 first verifies every changed expression by building a full truth-table comparison between the original AST and the optimized AST. It then executes the optimized statements using a state dictionary and records the final variable values and printed output. All boolean values in the JSON trace are stored as uppercase strings: `"TRUE"` or `"FALSE"`.

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

The tests are intentionally lightweight, but they check the main required behaviors of the pipeline:
- successful end-to-end compilation
- graceful failure on invalid syntax
- graceful failure on invalid lexical input
- correctness of at least one optimization together with truth-table verification
