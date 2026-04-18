import json
import sys

from phase_1_lexer import CompilerError, run_lexer
from phase_2_parser import run_parser
from phase_3_optimizer import run_optimizer
from phase_4_execution import run_execution


PIPELINE_PHASES = [
    ("phase_1_lexer", run_lexer),
    ("phase_2_parser", run_parser),
]


# Run the full compiler pipeline on already-loaded source lines.
def compile_source_lines(source_lines):
    result = {}

    try:
        phase_output = source_lines
        for phase_name, phase_runner in PIPELINE_PHASES:
            phase_output = phase_runner(phase_output)
            result[phase_name] = phase_output

        phase_3_output, verification_pairs = run_optimizer(phase_output)
        result["phase_3_optimizer"] = phase_3_output

        phase_4_output = run_execution(phase_3_output, verification_pairs)
        result["phase_4_execution"] = phase_4_output

        return result

    except CompilerError as error:
        result["error"] = {
            "phase": error.phase,
            "line": error.line,
        }
        return result


# Read a source file from disk and compile its contents.
def compile_file(input_filename):
    with open(input_filename, "r", encoding="utf-8") as file:
        source_lines = file.readlines()
    return compile_source_lines(source_lines)


# Parse command-line arguments and write the compiler trace JSON.
def main():
    if len(sys.argv) != 3:
        print("Usage: python main.py <input_file> <output_file>")
        sys.exit(1)

    input_filename = sys.argv[1]
    output_filename = sys.argv[2]

    results = compile_file(input_filename)

    with open(output_filename, "w", encoding="utf-8") as out_file:
        json.dump(results, out_file, indent=2)


if __name__ == "__main__":
    main()
