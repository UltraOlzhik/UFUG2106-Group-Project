from phase_1_lexer import CompilerError
from phase_2_parser import is_variable

# Truth functions for binary operators.
EXPRESSION_EVALUATORS = {
    "AND": lambda left, right: "TRUE" if left == "TRUE" and right == "TRUE" else "FALSE",
    "OR": lambda left, right: "TRUE" if left == "TRUE" or right == "TRUE" else "FALSE",
    "IMPLIES": lambda left, right: "FALSE" if left == "TRUE" and right == "FALSE" else "TRUE",
}


# Collect unique variables from an expression.
def collect_variables(expr):
    if isinstance(expr, str):
        return {expr} if is_variable(expr) else set()

    if len(expr) == 2:
        return collect_variables(expr[1])

    return collect_variables(expr[1]) | collect_variables(expr[2])


# Generate truth-table rows in stable order.
def generate_truth_assignments(variables):
    if not variables:
        return [{}]

    rest_assignments = generate_truth_assignments(variables[:-1])
    assignments = []
    current_variable = variables[-1]

    for assignment in rest_assignments:
        true_assignment = assignment.copy()
        true_assignment[current_variable] = "TRUE"
        assignments.append(true_assignment)

        false_assignment = assignment.copy()
        false_assignment[current_variable] = "FALSE"
        assignments.append(false_assignment)

    return assignments


# Evaluate an expression under one state.
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


# Build one verification record.
def build_verification(line_number, original_expr, optimized_expr):
    variables = sorted(collect_variables(original_expr) | collect_variables(optimized_expr))
    original_column = []
    optimized_column = []

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


# Execute one statement node.
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


# Execute a LET statement.
def execute_let_statement(statement, state, _printed_output, line_number):
    state[statement[1]] = eval_expression(statement[2], state, line_number)


# Execute a PRINT statement.
def execute_print_statement(statement, state, printed_output, line_number):
    variable = statement[1]
    if variable not in state:
        raise CompilerError("phase_4_execution", line_number, f"Undefined variable: {variable}")
    printed_output.append({
        "line": line_number,
        "output": state[variable],
    })


# Execute an IF statement.
def execute_if_statement(statement, state, printed_output, line_number):
    condition_value = eval_expression(statement[1], state, line_number)
    if condition_value == "TRUE":
        execute_statement(statement[2], state, printed_output, line_number)


# Verify first, then execute.
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
