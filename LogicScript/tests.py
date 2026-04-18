from main import compile_source_lines


def test_valid_program():
    program = [
        "let p = T\n",
        "let q = F\n",
        "let r = (NOT ((NOT p) AND q))\n",
        "if r then print p\n",
    ]

    result = compile_source_lines(program)

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


def test_syntax_error():
    program = [
        "let p = T\n",
        "if (p AND ) then print p\n",
    ]

    result = compile_source_lines(program)

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


def test_lexical_error():
    program = [
        "let p = T\n",
        "let q = @\n",
    ]

    result = compile_source_lines(program)

    expected = {"error": {"phase": "phase_1_lexer", "line": 2}}

    assert result == expected


def test_constant_folding_verification():
    program = [
        "let p = T\n",
        "let x = (p OR T)\n",
        "print x\n",
    ]

    result = compile_source_lines(program)

    assert result["phase_3_optimizer"][1]["ast"] == ["LET", "VAR_X", "TRUE"]
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
        {"line": 3, "output": "TRUE"}
    ]


def run_all_tests():
    test_valid_program()
    test_syntax_error()
    test_lexical_error()
    test_constant_folding_verification()
    print("All tests passed.")


if __name__ == "__main__":
    run_all_tests()
