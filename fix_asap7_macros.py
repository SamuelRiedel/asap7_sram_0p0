import re
import argparse
import sys

def scale_numbers_in_line(line: str) -> str:
    """
    Finds all floating-point or integer numbers in a string and divides them by 1000.
    It preserves the overall structure of the line.
    Handles scientific notation as well.
    """
    # This regex is designed to find numbers (int, float, scientific) that are not part of other words.
    # The negative lookbehind/ahead `(?<!\w)` and `(?!\w)` prevent matching parts of names like `delay_template_7x7_x1`.
    pattern = re.compile(r'(?<!\w)(-?\d+(?:\.\d*)?(?:[eE]-?\d+)?)(?!\w)')

    def replacer(match):
        """Replacement function to scale the matched number."""
        try:
            num = float(match.group(1))
            scaled_num = num / 1000.0
            # Use general-purpose formatting to handle both small and large numbers gracefully.
            # .8g preserves up to 8 significant digits.
            return f"{scaled_num:.8g}"
        except (ValueError, TypeError):
            # If for some reason the match isn't a valid number, return it unchanged.
            return match.group(1)

    return pattern.sub(replacer, line)

def find_output_pin_line_ranges(lines: list) -> list:
    """
    First pass: Go through the file to identify the start and end line numbers
    of any pin or bus block that is an output. This avoids modifying input pins.
    """
    ranges = []
    brace_depth = 0
    in_pin_block = False
    is_output_pin = False
    block_start_info = {}  # Using a dict to track nested pin blocks

    for i, line in enumerate(lines):
        line_num = i + 1
        stripped_line = line.strip()

        # Track entering a pin or bus block
        if stripped_line.startswith(('pin (', 'bus (')) and not in_pin_block:
            in_pin_block = True
            is_output_pin = False
            block_start_info = {
                "start_line": line_num,
                "start_depth": brace_depth
            }

        # Update brace depth after checking for the start
        brace_depth += line.count('{')
        brace_depth -= line.count('}')

        if in_pin_block and 'direction' in stripped_line:
            if 'output' in stripped_line:
                is_output_pin = True

        # Track exiting the current pin/bus block
        # A block ends when the brace depth drops below where it started.
        if in_pin_block and brace_depth <= block_start_info.get("start_depth", 0):
            if is_output_pin:
                ranges.append((block_start_info["start_line"], line_num))
            in_pin_block = False
            is_output_pin = False
            block_start_info = {}

    return ranges

def process_lib_file(input_path: str, output_path: str):
    """
    Reads a .lib file, scales numbers in output pin blocks by 1/1000,
    and writes the result to a new file.
    """
    print(f"Reading from '{input_path}'...")
    try:
        with open(input_path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: Input file not found at '{input_path}'", file=sys.stderr)
        sys.exit(1)

    # --- Pass 1: Identify which line ranges belong to output pins ---
    print("Pass 1/2: Identifying output pin blocks...")
    output_ranges = find_output_pin_line_ranges(lines)
    if not output_ranges:
        print("Warning: No output pin blocks were found to modify.")
    else:
        print(f"Found {len(output_ranges)} output pin block(s) to process.")

    # --- Pass 2: Go through the file again and modify the identified ranges ---
    print("Pass 2/2: Scaling values and writing to output file...")
    modified_lines = []
    is_in_output_range = False
    is_scaling_values = False

    current_range_index = 0

    for i, line in enumerate(lines):
        line_num = i + 1

        # Check if we have entered one of the identified output pin ranges
        if current_range_index < len(output_ranges) and line_num >= output_ranges[current_range_index][0]:
            is_in_output_range = True

        if is_in_output_range:
            # Check if we are entering a multi-line values() block
            if 'values (' in line:
                is_scaling_values = True

            # If we are in a values() block or the line is an index, scale it
            if is_scaling_values or line.lstrip().startswith(('index_1', 'index_2')):
                modified_line = scale_numbers_in_line(line)
            else:
                modified_line = line

            # Check if we are exiting a values() block
            if ');' in line:
                is_scaling_values = False
        else:
            # If not in an output range, keep the line as is
            modified_line = line

        modified_lines.append(modified_line)

        # Check if we have exited the current output pin range
        if current_range_index < len(output_ranges) and line_num >= output_ranges[current_range_index][1]:
            is_in_output_range = False
            current_range_index += 1


    print(f"Writing modified Liberty file to '{output_path}'...")
    with open(output_path, 'w') as f:
        f.writelines(modified_lines)

    print("Done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="""
        Corrects inconsistent units in a Liberty (.lib) file.
        This script specifically finds pin/bus blocks with 'direction: output'
        and divides all numbers within their 'values' and 'index' tables by 1000.
        Input pin timings are not affected.
        """,
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("input_lib", help="Path to the source .lib file.")
    parser.add_argument("output_lib", nargs='?', default=None,
                        help="Path for the new, corrected .lib file. "
                             "(Optional: If not provided, overwrites the input file)")

    args = parser.parse_args()

    # If output_lib was not provided, set it to be the same as input_lib
    if args.output_lib is None:
        args.output_lib = args.input_lib
        print(f"Warning: No output file specified. The input file '{args.input_lib}' will be overwritten.", file=sys.stderr)

    process_lib_file(args.input_lib, args.output_lib)
