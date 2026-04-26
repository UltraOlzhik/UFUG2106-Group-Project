"""Local regression tests for the LogicScript compiler.

The tests are intentionally plain Python `assert` tests so they can be run with
no third-party dependencies:
    python tests.py

They also work with pytest, because every case is written as a `test_*` function.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from logic_compiler import compile_source_lines


ROOT = Path(__file__).resolve().parent
COMPILER = ROOT / "logic_compiler.py"


def compile_program(source: str):
    """Compile a readable multi-line string as a LogicScript program.

    Leading and trailing blank lines in the triple-quoted Python string are
    ignored so expected source line numbers match the visible program body.
    """

    stripped = source.strip("\n")
    if stripped == "":
        return compile_source_lines([])
    return compile_source_lines([line + "\n" for line in stripped.splitlines()])


def assert_error(result, phase, line):
    assert result["error"] == {"phase": phase, "line": line}


def assert_no_error(result):
    assert "error" not in result, result.get("error")


# ---------------------------------------------------------------------------
# Official-style successful compilation and output-shape tests
# ---------------------------------------------------------------------------


def test_successful_compilation_matches_project_example():
    program = """
let p = T
let q = F
let r = (NOT ((NOT p) AND q))
if r then print p
"""

    result = compile_program(program)

    expected = {
        "phase_1_lexer": [
            {"line": 1, "tokens": ["LET", "VAR_P", "EQ", "TRUE"]},
            {"line": 2, "tokens": ["LET", "VAR_Q", "EQ", "FALSE"]},
            {
                "line": 3,
                "tokens": [
                    "LET",
                    "VAR_R",
                    "EQ",
                    "L_PAREN",
                    "NOT",
                    "L_PAREN",
                    "L_PAREN",
                    "NOT",
                    "VAR_P",
                    "R_PAREN",
                    "AND",
                    "VAR_Q",
                    "R_PAREN",
                    "R_PAREN",
                ],
            },
            {"line": 4, "tokens": ["IF", "VAR_R", "THEN", "PRINT", "VAR_P"]},
        ],
        "phase_2_parser": [
            {"line": 1, "ast": ["LET", "VAR_P", "TRUE"]},
            {"line": 2, "ast": ["LET", "VAR_Q", "FALSE"]},
            {
                "line": 3,
                "ast": [
                    "LET",
                    "VAR_R",
                    ["NOT", ["AND", ["NOT", "VAR_P"], "VAR_Q"]],
                ],
            },
            {"line": 4, "ast": ["IF", "VAR_R", ["PRINT", "VAR_P"]]},
        ],
        "phase_3_optimizer": [
            {"line": 1, "ast": ["LET", "VAR_P", "TRUE"]},
            {"line": 2, "ast": ["LET", "VAR_Q", "FALSE"]},
            {
                "line": 3,
                "ast": ["LET", "VAR_R", ["OR", "VAR_P", ["NOT", "VAR_Q"]]],
            },
            {"line": 4, "ast": ["IF", "VAR_R", ["PRINT", "VAR_P"]]},
        ],
        "phase_4_execution": {
            "verifications": [
                {
                    "line": 3,
                    "variables_tested": ["VAR_P", "VAR_Q"],
                    "ast_original_column": ["TRUE", "TRUE", "FALSE", "TRUE"],
                    "ast_optimized_column": ["TRUE", "TRUE", "FALSE", "TRUE"],
                    "is_equivalent": "TRUE",
                }
            ],
            "final_state_dictionary": {
                "VAR_P": "TRUE",
                "VAR_Q": "FALSE",
                "VAR_R": "TRUE",
            },
            "printed_output": [{"line": 4, "output": "TRUE"}],
        },
    }

    assert result == expected


def test_command_line_interface_writes_json_trace_file():
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        source_file = tmp_path / "program.txt"
        output_file = tmp_path / "compiler_trace.json"

        source_file.write_text("let p = T\nprint p\n", encoding="utf-8")

        completed = subprocess.run(
            [sys.executable, "-S", str(COMPILER), str(source_file), str(output_file)],
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0, completed.stderr
        result = json.loads(output_file.read_text(encoding="utf-8"))
        assert result["phase_4_execution"]["final_state_dictionary"] == {"VAR_P": "TRUE"}
        assert result["phase_4_execution"]["printed_output"] == [
            {"line": 2, "output": "TRUE"}
        ]


# ---------------------------------------------------------------------------
# Lexical and parser error handling
# ---------------------------------------------------------------------------


def test_empty_program_is_rejected_because_program_needs_at_least_one_statement():
    result = compile_program("")

    assert result == {"error": {"phase": "phase_1_lexer", "line": 1}}


def test_all_blank_program_is_rejected():
    result = compile_source_lines(["\n", "   \n", "\t\n"])

    assert result == {"error": {"phase": "phase_1_lexer", "line": 1}}


def test_lexical_error_invalid_symbol():
    program = """
let p = T
let q = @
"""

    result = compile_program(program)

    assert_error(result, "phase_1_lexer", 2)


def test_lexical_error_uppercase_variable_is_not_allowed():
    result = compile_program("let P = T")

    assert_error(result, "phase_1_lexer", 1)


def test_lexical_error_multi_letter_identifier_is_not_allowed():
    result = compile_program("let ab = T")

    assert_error(result, "phase_1_lexer", 1)


def test_syntax_error_missing_operand_preserves_successful_lexer_output():
    program = """
let p = T
if (p AND ) then print p
"""

    result = compile_program(program)

    expected = {
        "phase_1_lexer": [
            {"line": 1, "tokens": ["LET", "VAR_P", "EQ", "TRUE"]},
            {
                "line": 2,
                "tokens": [
                    "IF",
                    "L_PAREN",
                    "VAR_P",
                    "AND",
                    "R_PAREN",
                    "THEN",
                    "PRINT",
                    "VAR_P",
                ],
            },
        ],
        "error": {"phase": "phase_2_parser", "line": 2},
    }

    assert result == expected


def test_syntax_error_mismatched_parentheses():
    result = compile_program("let x = (p AND T")

    assert result["phase_1_lexer"] == [
        {"line": 1, "tokens": ["LET", "VAR_X", "EQ", "L_PAREN", "VAR_P", "AND", "TRUE"]}
    ]
    assert_error(result, "phase_2_parser", 1)


def test_syntax_error_extra_tokens_after_statement():
    result = compile_program("print p q")

    assert result["phase_1_lexer"] == [
        {"line": 1, "tokens": ["PRINT", "VAR_P", "VAR_Q"]}
    ]
    assert_error(result, "phase_2_parser", 1)


def test_syntax_error_missing_then_keyword():
    result = compile_program("if p print p")

    assert result["phase_1_lexer"] == [
        {"line": 1, "tokens": ["IF", "VAR_P", "PRINT", "VAR_P"]}
    ]
    assert_error(result, "phase_2_parser", 1)


def test_binary_expression_requires_parentheses():
    result = compile_program("let p = x AND F")

    assert_error(result, "phase_2_parser", 1)


# ---------------------------------------------------------------------------
# Runtime behavior and state-dictionary checks
# ---------------------------------------------------------------------------


def test_blank_lines_are_ignored_but_line_numbers_are_preserved():
    program = """
let p = T

print p
"""

    result = compile_program(program)

    assert result["phase_1_lexer"] == [
        {"line": 1, "tokens": ["LET", "VAR_P", "EQ", "TRUE"]},
        {"line": 3, "tokens": ["PRINT", "VAR_P"]},
    ]
    assert result["phase_4_execution"]["printed_output"] == [{"line": 3, "output": "TRUE"}]


def test_runtime_error_printing_undefined_variable():
    result = compile_program("print p")

    assert result["phase_3_optimizer"] == [{"line": 1, "ast": ["PRINT", "VAR_P"]}]
    assert_error(result, "phase_4_execution", 1)


def test_runtime_error_using_undefined_variable_in_expression():
    result = compile_program("let x = (p AND T)")

    assert result["phase_3_optimizer"] == [
        {"line": 1, "ast": ["LET", "VAR_X", "VAR_P"]}
    ]
    assert_error(result, "phase_4_execution", 1)


def test_if_statement_skips_nested_statement_when_condition_is_false():
    program = """
let p = F
if p then print p
"""

    result = compile_program(program)

    assert result["phase_4_execution"] == {
        "verifications": [],
        "final_state_dictionary": {"VAR_P": "FALSE"},
        "printed_output": [],
    }


def test_if_statement_executes_nested_assignment():
    program = """
let p = T
if p then let q = F
print q
"""

    result = compile_program(program)

    assert result["phase_4_execution"]["final_state_dictionary"] == {
        "VAR_P": "TRUE",
        "VAR_Q": "FALSE",
    }
    assert result["phase_4_execution"]["printed_output"] == [
        {"line": 3, "output": "FALSE"}
    ]


def test_nested_if_statement_executes_when_both_conditions_are_true():
    program = """
let p = T
let q = F
if p then if (NOT q) then print p
"""

    result = compile_program(program)

    assert_no_error(result)
    assert result["phase_4_execution"]["printed_output"] == [
        {"line": 3, "output": "TRUE"}
    ]


# ---------------------------------------------------------------------------
# Optimizer and truth-table verification tests
# ---------------------------------------------------------------------------


def test_optimization_and_execution_program():
    program = """
let p = T
let x = (p OR T)
print x
"""

    result = compile_program(program)

    assert result["phase_3_optimizer"] == [
        {"line": 1, "ast": ["LET", "VAR_P", "TRUE"]},
        {"line": 2, "ast": ["LET", "VAR_X", "TRUE"]},
        {"line": 3, "ast": ["PRINT", "VAR_X"]},
    ]
    assert result["phase_4_execution"] == {
        "verifications": [
            {
                "line": 2,
                "variables_tested": ["VAR_P"],
                "ast_original_column": ["TRUE", "TRUE"],
                "ast_optimized_column": ["TRUE", "TRUE"],
                "is_equivalent": "TRUE",
            }
        ],
        "final_state_dictionary": {"VAR_P": "TRUE", "VAR_X": "TRUE"},
        "printed_output": [{"line": 3, "output": "TRUE"}],
    }


def test_optimizer_is_static_and_does_not_use_runtime_value_of_variable():
    program = """
let p = F
let x = (p OR T)
print x
"""

    result = compile_program(program)

    assert result["phase_3_optimizer"][1] == {"line": 2, "ast": ["LET", "VAR_X", "TRUE"]}
    assert result["phase_4_execution"]["printed_output"] == [
        {"line": 3, "output": "TRUE"}
    ]


def test_complement_rule_and_verification():
    result = compile_program("let x = (p OR (NOT p))")

    assert result["phase_3_optimizer"] == [
        {"line": 1, "ast": ["LET", "VAR_X", "TRUE"]}
    ]
    assert result["phase_4_execution"]["verifications"] == [
        {
            "line": 1,
            "variables_tested": ["VAR_P"],
            "ast_original_column": ["TRUE", "TRUE"],
            "ast_optimized_column": ["TRUE", "TRUE"],
            "is_equivalent": "TRUE",
        }
    ]


def test_absorption_rule():
    program = """
let p = T
let q = F
let x = (p OR (p AND q))
print x
"""

    result = compile_program(program)

    assert result["phase_3_optimizer"][2]["ast"] == ["LET", "VAR_X", "VAR_P"]
    assert result["phase_4_execution"]["printed_output"] == [
        {"line": 4, "output": "TRUE"}
    ]


def test_double_negation_rule():
    program = """
let p = T
let x = (NOT (NOT p))
print x
"""

    result = compile_program(program)

    assert result["phase_3_optimizer"][1]["ast"] == ["LET", "VAR_X", "VAR_P"]
    assert result["phase_4_execution"]["printed_output"] == [
        {"line": 3, "output": "TRUE"}
    ]


def test_implication_rewrite_and_execution():
    program = """
let p = T
let q = F
let x = (p IMPLIES q)
print x
"""

    result = compile_program(program)

    assert result["phase_4_execution"]["verifications"] == [
        {
            "line": 3,
            "variables_tested": ["VAR_P", "VAR_Q"],
            "ast_original_column": ["TRUE", "FALSE", "TRUE", "TRUE"],
            "ast_optimized_column": ["TRUE", "FALSE", "TRUE", "TRUE"],
            "is_equivalent": "TRUE",
        }
    ]
    assert result["phase_4_execution"]["printed_output"] == [
        {"line": 4, "output": "FALSE"}
    ]


def test_de_morgan_rewrite_and_execution():
    program = """
let p = T
let q = F
let x = (NOT (p AND q))
print x
"""

    result = compile_program(program)

    assert result["phase_3_optimizer"][2]["ast"] == [
        "LET",
        "VAR_X",
        ["OR", ["NOT", "VAR_P"], ["NOT", "VAR_Q"]],
    ]
    assert result["phase_4_execution"]["printed_output"] == [
        {"line": 4, "output": "TRUE"}
    ]


def test_if_condition_optimization_is_verified_before_execution():
    program = """
let p = F
if (p OR T) then print p
"""

    result = compile_program(program)

    assert result["phase_3_optimizer"][1] == {
        "line": 2,
        "ast": ["IF", "TRUE", ["PRINT", "VAR_P"]],
    }
    assert result["phase_4_execution"]["verifications"] == [
        {
            "line": 2,
            "variables_tested": ["VAR_P"],
            "ast_original_column": ["TRUE", "TRUE"],
            "ast_optimized_column": ["TRUE", "TRUE"],
            "is_equivalent": "TRUE",
        }
    ]
    assert result["phase_4_execution"]["printed_output"] == [
        {"line": 2, "output": "FALSE"}
    ]


def run_all_tests():
    test_successful_compilation_matches_project_example()
    test_command_line_interface_writes_json_trace_file()
    test_empty_program_is_rejected_because_program_needs_at_least_one_statement()
    test_all_blank_program_is_rejected()
    test_lexical_error_invalid_symbol()
    test_lexical_error_uppercase_variable_is_not_allowed()
    test_lexical_error_multi_letter_identifier_is_not_allowed()
    test_syntax_error_missing_operand_preserves_successful_lexer_output()
    test_syntax_error_mismatched_parentheses()
    test_syntax_error_extra_tokens_after_statement()
    test_syntax_error_missing_then_keyword()
    test_binary_expression_requires_parentheses()
    test_blank_lines_are_ignored_but_line_numbers_are_preserved()
    test_runtime_error_printing_undefined_variable()
    test_runtime_error_using_undefined_variable_in_expression()
    test_if_statement_skips_nested_statement_when_condition_is_false()
    test_if_statement_executes_nested_assignment()
    test_nested_if_statement_executes_when_both_conditions_are_true()
    test_optimization_and_execution_program()
    test_optimizer_is_static_and_does_not_use_runtime_value_of_variable()
    test_complement_rule_and_verification()
    test_absorption_rule()
    test_double_negation_rule()
    test_implication_rewrite_and_execution()
    test_de_morgan_rewrite_and_execution()
    test_if_condition_optimization_is_verified_before_execution()
    print("All tests passed.")


if __name__ == "__main__":
    run_all_tests()
