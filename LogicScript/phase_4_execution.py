from itertools import product
from phase_1_lexer import CompilerError
from phase_2_parser import is_variable

EXPRESSION_EVALUATORS = {
    "AND": lambda left, right: "TRUE" if left == "TRUE" and right == "TRUE" else "FALSE",
    "OR": lambda left, right: "TRUE" if left == "TRUE" or right == "TRUE" else "FALSE",
    "IMPLIES": lambda left, right: "FALSE" if left == "TRUE" and right == "FALSE" else "TRUE",
}


# Collect all variable names that appear inside an expression tree.
def collect_variables(expr):
    if isinstance(expr, str):
        return {expr} if is_variable(expr) else set()

    if len(expr) == 2:
        return collect_variables(expr[1])

    return collect_variables(expr[1]) | collect_variables(expr[2])


# Evaluate one expression against the current state dictionary.
def eval_expression(expr, state, line_number):
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


# Build a full truth-table comparison for an original and optimized expression.
def build_verification(line_number, original_expr, optimized_expr):
    variables = sorted(collect_variables(original_expr) | collect_variables(optimized_expr))
    original_column = []
    optimized_column = []

    for values in product(["TRUE", "FALSE"], repeat=len(variables)):
        state = dict(zip(variables, values))
        original_column.append(eval_expression(original_expr, state, line_number))
        optimized_column.append(eval_expression(optimized_expr, state, line_number))

    return {
        "line": line_number,
        "variables_tested": variables,
        "ast_original_column": original_column,
        "ast_optimized_column": optimized_column,
        "is_equivalent": "TRUE" if original_column == optimized_column else "FALSE",
    }


# Execute one statement by dispatching to the matching statement handler.
def execute_statement(statement, state, printed_output, line_number):
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


# Evaluate an assignment and store the result in the state dictionary.
def execute_let_statement(statement, state, _printed_output, line_number):
    state[statement[1]] = eval_expression(statement[2], state, line_number)


# Record the value of a variable in the printed output trace.
def execute_print_statement(statement, state, printed_output, line_number):
    variable = statement[1]
    if variable not in state:
        raise CompilerError("phase_4_execution", line_number, f"Undefined variable: {variable}")
    printed_output.append({
        "line": line_number,
        "output": state[variable],
    })


# Execute the nested statement only when the IF condition is TRUE.
def execute_if_statement(statement, state, printed_output, line_number):
    condition_value = eval_expression(statement[1], state, line_number)
    if condition_value == "TRUE":
        execute_statement(statement[2], state, printed_output, line_number)


# Verify all optimizations and then execute the optimized program.
def run_execution(phase_3_output, verification_pairs):
    verifications = []

    for line_number, original_expr, optimized_expr in verification_pairs:
        verification = build_verification(line_number, original_expr, optimized_expr)
        if verification["is_equivalent"] != "TRUE":
            raise CompilerError(
                "phase_4_execution",
                line_number,
                "Optimization produced a non-equivalent expression",
            )
        verifications.append(verification)

    state = {}
    printed_output = []

    for item in phase_3_output:
        line_number = item["line"]
        statement = item["ast"]
        execute_statement(statement, state, printed_output, line_number)

    return {
        "verifications": verifications,
        "final_state_dictionary": state,
        "printed_output": printed_output,
    }
