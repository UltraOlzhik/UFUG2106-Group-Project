import json
import os
import sys


# Make LogicScript/ importable from the repo root.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LOGICSCRIPT_DIR = os.path.join(PROJECT_ROOT, "LogicScript")
if LOGICSCRIPT_DIR not in sys.path:
    sys.path.insert(0, LOGICSCRIPT_DIR)

from main import compile_file


# Assignment CLI wrapper.
def main():
    if len(sys.argv) != 3:
        print("Usage: python logic_compiler.py <input_file> <output_file>")
        sys.exit(1)

    input_filename = sys.argv[1]
    output_filename = sys.argv[2]

    results = compile_file(input_filename)

    with open(output_filename, "w", encoding="utf-8") as out_file:
        json.dump(results, out_file, indent=2)


if __name__ == "__main__":
    main()
