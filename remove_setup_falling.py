#!/usr/bin/env python3

import re
import sys
import os
import argparse
import shutil

def clean_lib_file(filename):
    """
    Parses a .lib file in-place and removes any 'timing ()' block that
    contains both 'related_pin : "clk";' and 'timing_type : setup_falling;'.

    The original file is overwritten.
    """

    # Check if input file exists
    if not os.path.exists(filename):
        print(f"Error: Input file not found at '{filename}'. Skipping.")
        return

    print(f"Starting processing of '{filename}'...")

    # We'll write to a temporary file first for safety.
    temp_filename = filename + ".tmp"

    removed_blocks_count = 0

    try:
        with open(filename, 'r') as f_in, open(temp_filename, 'w') as f_out:

            in_timing_block = False
            brace_level = 0
            current_timing_block_lines = []

            # Flags to check for conditions *within* the current timing block
            found_clk = False
            found_setup_falling = False

            current_pin = "UNKNOWN" # Keep track of the pin for reporting
            line_number = 0
            block_start_line = 0

            for line in f_in:
                line_number += 1
                stripped_line = line.strip()

                # Track the current pin for better reporting
                pin_match = re.search(r'^\s*pin\s*\(\s*([\w\.-]+)\s*\)', stripped_line)
                if pin_match:
                    current_pin = pin_match.group(1)

                # Check for the start of a 'timing ()' block
                timing_start_match = re.search(r'^\s*timing\s*\(\s*\)\s*\{', stripped_line)

                if timing_start_match and not in_timing_block:
                    # --- Entered a new timing block ---
                    in_timing_block = True
                    brace_level = 1
                    block_start_line = line_number
                    current_timing_block_lines = [line]

                    # Reset flags for the new block
                    found_clk = False
                    found_setup_falling = False

                elif in_timing_block:
                    # --- We are inside a timing block ---
                    current_timing_block_lines.append(line)

                    # Check for the conditions
                    if re.search(r'related_pin\s*:\s*"clk"\s*;', stripped_line):
                        found_clk = True

                    if re.search(r'timing_type\s*:\s*setup_falling\s*;', stripped_line):
                        found_setup_falling = True

                    # Track brace level to find the end of the block
                    brace_level += line.count('{')
                    brace_level -= line.count('}')

                    # Check for the end of the block
                    if brace_level == 0:
                        in_timing_block = False

                        # Now, decide whether to write or discard the block
                        if found_clk and found_setup_falling:
                            # This is the block to remove
                            print(f"  [REMOVED] 'setup_falling' block for 'clk' in pin '{current_pin}' (Lines {block_start_line}-{line_number})")
                            removed_blocks_count += 1
                        else:
                            # This is a block to keep, write all its lines
                            for block_line in current_timing_block_lines:
                                f_out.write(block_line)

                        # Reset for the next block
                        current_timing_block_lines = []

                else:
                    # --- We are not in a timing block ---
                    # Just write the line directly to the output
                    f_out.write(line)

    except IOError as e:
        print(f"Error reading/writing file '{filename}': {e}")
        # Clean up the temp file on error
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        return
    except Exception as e:
        print(f"An unexpected error occurred processing '{filename}': {e}")
        # Clean up the temp file on error
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
        return

    # --- If we get here, processing was successful ---
    # Now, replace the original file with the temporary file
    try:
        shutil.move(temp_filename, filename)
        print(f"Processing complete for '{filename}'.")
        print(f"Total 'setup_falling' blocks for 'clk' removed: {removed_blocks_count}")
        print(f"File '{filename}' has been overwritten.")
    except Exception as e:
        print(f"Error overwriting original file '{filename}' with temp file: {e}")
        # Try to clean up
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

# --- Main execution ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Clean .lib files by removing 'setup_falling' timing blocks related to 'clk'. "
                    "The files are modified in-place.",
        epilog="Example: python clean_lib_inplace.py my_lib.lib another_lib.lib"
    )

    parser.add_argument(
        'filenames',
        metavar='FILE',
        nargs='+',
        help='One or more .lib files to process in-place.'
    )

    args = parser.parse_args()

    if not args.filenames:
        print("No files provided. Use -h for help.")
    else:
        for lib_file in args.filenames:
            clean_lib_file(lib_file)
            print("-" * 40) # Separator for multiple files
