# Structural AST equality.
def ast_equal(left, right):
    return left == right


# Check whether an expression is the TRUE literal.
def is_true(expr):
    return expr == "TRUE"


# Check whether an expression is the FALSE literal.
def is_false(expr):
    return expr == "FALSE"


# Check whether an AST node is a unary NOT expression.
def is_not(expr):
    return isinstance(expr, list) and len(expr) == 2 and expr[0] == "NOT"


# Match `[op, left, right]`.
def is_binary(expr, operator=None):
    if not (isinstance(expr, list) and len(expr) == 3):
        return False
    if operator is None:
        return True
    return expr[0] == operator


# Check whether one expression is the negation of another.
def is_negation_of(left, right):
    return is_not(left) and ast_equal(left[1], right)


# Match the inner absorption shape.
def absorption_match(expr, target, absorbing_operator):
    return is_binary(expr, absorbing_operator) and (
        ast_equal(expr[1], target) or ast_equal(expr[2], target)
    )


# Added by Bi Li: flatten associative chains.
def collect_associative_operands(expr, operator):
    if is_binary(expr, operator):
        return (
            collect_associative_operands(expr[1], operator)
            + collect_associative_operands(expr[2], operator)
        )
    return [expr]


# Added by Bi Li: rebuild into one canonical shape.
def build_associative_expression(operator, operands):
    if len(operands) == 1:
        return operands[0]

    result = operands[-1]
    for operand in reversed(operands[:-1]):
        result = [operator, operand, result]
    return result


# Return the first matching rule result.
def apply_rule_list(*args, rules):
    for rule in rules:
        result = rule(*args)
        if result is not None:
            return result
    return None


# Simplify NOT TRUE and NOT FALSE.
def rule_not_constant(child):
    if is_true(child):
        return "FALSE"
    if is_false(child):
        return "TRUE"
    return None


# Remove a pair of consecutive NOT operators.
def rule_double_negation(child):
    if is_not(child):
        return optimize_expression(child[1])
    return None


# Apply De Morgan's law to NOT of an AND expression.
def rule_de_morgan_and(child):
    if is_binary(child, "AND"):
        return optimize_expression(["OR", ["NOT", child[1]], ["NOT", child[2]]])
    return None


# Apply De Morgan's law to NOT of an OR expression.
def rule_de_morgan_or(child):
    if is_binary(child, "OR"):
        return optimize_expression(["AND", ["NOT", child[1]], ["NOT", child[2]]])
    return None


# Rewrite `NOT (A IMPLIES B)`.
def rule_not_implies(child):
    if is_binary(child, "IMPLIES"):
        return optimize_expression(["AND", child[1], ["NOT", child[2]]])
    return None


# Ordered NOT rules.
NOT_RULES = [
    rule_not_constant,
    rule_double_negation,
    rule_de_morgan_and,
    rule_de_morgan_or,
    rule_not_implies,
]


# Apply the domination law for AND.
def rule_and_domination(left, right):
    if is_false(left) or is_false(right):
        return "FALSE"
    return None


# Apply the identity law for AND.
def rule_and_identity(left, right):
    if is_true(left):
        return right
    if is_true(right):
        return left
    return None


# Apply the domination law for OR.
def rule_or_domination(left, right):
    if is_true(left) or is_true(right):
        return "TRUE"
    return None


# Apply the identity law for OR.
def rule_or_identity(left, right):
    if is_false(left):
        return right
    if is_false(right):
        return left
    return None


# x OP x -> x
def rule_idempotent(left, right):
    if ast_equal(left, right):
        return left
    return None


# Apply the complement law for AND.
def rule_and_complement(left, right):
    if is_negation_of(left, right) or is_negation_of(right, left):
        return "FALSE"
    return None


# Apply the complement law for OR.
def rule_or_complement(left, right):
    if is_negation_of(left, right) or is_negation_of(right, left):
        return "TRUE"
    return None


# Apply the absorption law for AND.
def rule_and_absorption(left, right):
    if absorption_match(left, right, "OR"):
        return right
    if absorption_match(right, left, "OR"):
        return left
    return None


# Apply the absorption law for OR.
def rule_or_absorption(left, right):
    if absorption_match(left, right, "AND"):
        return right
    if absorption_match(right, left, "AND"):
        return left
    return None


# Added by Bi Li: normalize nested AND chains.
def rule_and_associative(left, right):
    if is_binary(left, "AND") or is_binary(right, "AND"):
        operands = collect_associative_operands(["AND", left, right], "AND")
        rebuilt = build_associative_expression("AND", operands)
        if not ast_equal(rebuilt, ["AND", left, right]):
            return optimize_expression(rebuilt)
    return None


# Added by Bi Li: normalize nested OR chains.
def rule_or_associative(left, right):
    if is_binary(left, "OR") or is_binary(right, "OR"):
        operands = collect_associative_operands(["OR", left, right], "OR")
        rebuilt = build_associative_expression("OR", operands)
        if not ast_equal(rebuilt, ["OR", left, right]):
            return optimize_expression(rebuilt)
    return None


# Rules grouped by operator.
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


# Rewrite IMPLIES into core operators.
REWRITE_RULES = {
    "IMPLIES": lambda left, right: ["OR", ["NOT", left], right],
}


# Optimize a NOT node after its child.
def optimize_not_expression(child):
    optimized = apply_rule_list(child, rules=NOT_RULES)
    if optimized is not None:
        return optimized
    return ["NOT", child]


# Optimize one binary node.
def optimize_binary_expression(operator, left, right):
    rewritten = REWRITE_RULES.get(operator)
    if rewritten is not None:
        return optimize_expression(rewritten(left, right))

    optimized = apply_rule_list(left, right, rules=BINARY_RULES.get(operator, []))
    if optimized is not None:
        return optimized

    return [operator, left, right]


# Bottom-up expression optimization.
def optimize_expression(expr):
    if not isinstance(expr, list):
        return expr

    operator = expr[0]

    if operator == "NOT":
        child = optimize_expression(expr[1])
        return optimize_not_expression(child)

    left = optimize_expression(expr[1])
    right = optimize_expression(expr[2])
    return optimize_binary_expression(operator, left, right)


# Optimize expressions inside one statement.
def optimize_statement(statement):
    kind = statement[0]

    if kind == "LET":
        return ["LET", statement[1], optimize_expression(statement[2])]

    if kind == "IF":
        return ["IF", optimize_expression(statement[1]), optimize_statement(statement[2])]

    return statement[:]


# Collect changed expressions for Phase 4.
def collect_verification_pairs(line_number, original_statement, optimized_statement):
    pairs = []

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


# Return optimized statements plus verification pairs.
def run_optimizer(phase_2_output):
    phase_3_output = []
    verification_pairs = []

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
