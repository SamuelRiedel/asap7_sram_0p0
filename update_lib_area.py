#!/usr/bin/env python3
"""
This script updates the 'area' field in .lib files based on the 'SIZE'
dimensions found in corresponding .lef files.

It also calculates the GE/bit density for each macro and prints a summary.

It assumes a directory structure of:
<root_dir>/
    LIB/
        macro1.lib
        macro2.lib
        ...
    LEF/
        macro1.lef
        macro2.lef
        ...

Usage:
    python update_lib_area.py /path/to/your/tech/library
"""

import os
import re
import glob
import sys
from decimal import Decimal, getcontext

# --- Configuration ---
# Set precision for area calculation to avoid floating point issues
getcontext().prec = 10

# Area of one 'Gate Equivalent' (GE)
GE_AREA = Decimal('0.08748')

# Regex to find the SIZE line in a LEF file
# Captures: 1: width, 2: height
LEF_SIZE_RE = re.compile(r"^\s*SIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)\s*;", re.MULTILINE | re.IGNORECASE)

# Regex to find the area line in a LIB file
# Captures: 1: 'area : ', 2: the number, 3: ' ;'
LIB_AREA_RE = re.compile(r"(^\s*area\s*:\s*)[0-9.]+(\s*;)", re.MULTILINE | re.IGNORECASE)

# Regex to find bit dimensions like _64x4x72_
# Captures: 1: dim1, 2: dim2, 3: dim3
BITS_RE = re.compile(r'_(\d+)x(\d+)x(\d+)')
# --- End Configuration ---

def get_bits_from_name(macro_name):
    """
    Parses a macro name (e.g., 'srambank_64x4x72_6t122')
    to find its bit dimensions and return the total bit count.

    Args:
        macro_name (str): The name of the macro.

    Returns:
        int: The total bit count (e.g., 64*4*72), or None if not found.
    """
    match = BITS_RE.search(macro_name)

    if not match:
        return None

    try:
        dim1 = int(match.group(1))
        dim2 = int(match.group(2))
        dim3 = int(match.group(3))

        total_bits = dim1 * dim2 * dim3
        if total_bits == 0:
            return None
        return total_bits
    except Exception as e:
        print(f"  [!] Error converting bit dimensions for {macro_name}: {e}")
        return None

def get_area_from_lef(lef_file_path):
    """
    Reads a LEF file and extracts the area from the 'SIZE' definition.

    Args:
        lef_file_path (str): The full path to the .lef file.

    Returns:
        Decimal: The calculated area (width * height), or None if not found.
    """
    try:
        with open(lef_file_path, 'r') as f:
            content = f.read()

        match = LEF_SIZE_RE.search(content)

        if not match:
            print(f"  [!] Error: Could not find 'SIZE ... BY ...' line in {lef_file_path}")
            return None

        width = Decimal(match.group(1))
        height = Decimal(match.group(2))
        area = width * height

        return area

    except FileNotFoundError:
        print(f"  [!] Error: Corresponding LEF file not found: {lef_file_path}")
        return None
    except Exception as e:
        print(f"  [!] Error reading {lef_file_path}: {e}")
        return None

def update_lib_file(lib_file_path, area):
    """
    Replaces the 'area : 0;' line in a .lib file with the calculated area.

    Args:
        lib_file_path (str): The full path to the .lib file.
        area (Decimal): The new area to write.

    Returns:
        bool: True on success, False on failure.
    """
    try:
        with open(lib_file_path, 'r') as f:
            lib_content = f.read()

        # Format area to string, remove trailing zeros if any
        formatted_area = f"{area:f}".rstrip('0').rstrip('.')

        # Create the replacement string using the captured groups
        # \g<1> is 'area : ', \g<2> is ' ;'
        replacement_string = rf"\g<1>{formatted_area}\g<2>"

        # Use re.subn to get a count of replacements
        new_lib_content, count = LIB_AREA_RE.subn(replacement_string, lib_content)

        if count == 0:
            print(f"  [!] Warning: Could not find 'area : ...;' line in {lib_file_path}. File not modified.")
            return False

        # Write the modified content back to the file
        with open(lib_file_path, 'w') as f:
            f.write(new_lib_content)

        print(f"  [*] Success: Updated {lib_file_path} -> area: {formatted_area}")
        return True

    except Exception as e:
        print(f"  [!] Error updating {lib_file_path}: {e}")
        return False

def main(root_dir):
    """
    Main function to find and process all .lib files.
    """
    if not os.path.isdir(root_dir):
        print(f"Error: Base directory not found: {root_dir}")
        sys.exit(1)

    # Define paths for LIB and LEF subdirectories
    lib_dir = os.path.join(root_dir, 'LIB')
    lef_dir = os.path.join(root_dir, 'LEF')

    # Check if these specific directories exist
    if not os.path.isdir(lib_dir):
        print(f"Error: 'LIB' sub-directory not found at: {lib_dir}")
        sys.exit(1)
    if not os.path.isdir(lef_dir):
        print(f"Error: 'LEF' sub-directory not found at: {lef_dir}")
        sys.exit(1)

    print(f"--- Starting SRAM Area Update Utility ---")
    print(f"Scanning for .lib files in: {lib_dir}")
    print(f"Looking for .lef files in: {lef_dir}\n")

    # Use glob to find all .lib files *only* in the LIB directory
    lib_file_pattern = os.path.join(lib_dir, '*.lib')
    lib_files = glob.glob(lib_file_pattern)

    if not lib_files:
        print(f"No .lib files found in {lib_dir}.")
        return

    updated_count = 0
    failed_count = 0
    density_data = [] # To store GE/bit for summary

    for lib_file_path in lib_files:
        # Get the base filename, e.g., "srambank_128x4x16_6t122.lib"
        base_filename = os.path.basename(lib_file_path)
        # Get the macro name without extension, e.g., "srambank_128x4x16_6t122"
        macro_name = os.path.splitext(base_filename)[0]

        print(f"Processing: {base_filename}")

        # 1. Determine the corresponding .lef file path
        # Build the path to the LEF file in the LEF directory
        lef_file_path = os.path.join(lef_dir, macro_name + '.lef')

        # 2. Get the area from the LEF file
        area = get_area_from_lef(lef_file_path)

        if area is None:
            failed_count += 1
            print("-" * 20)
            continue # Error message was already printed

        # 3. Get bits from macro name
        total_bits = get_bits_from_name(macro_name)

        # 4. Calculate and print density
        if total_bits is not None and total_bits > 0:
            total_ge = area / GE_AREA
            # Use Decimal(total_bits) for precise division
            ge_per_bit = total_ge / Decimal(total_bits)

            print(f"  [*] Total Bits: {total_bits}")
            print(f"  [*] Area: {area:f}")
            print(f"  [*] Density (GE/bit): {ge_per_bit:.6f}")
            density_data.append(ge_per_bit)
        else:
            print(f"  [!] Warning: Could not parse bit info from '{macro_name}'. Skipping density calculation.")

        # 5. Update the LIB file with the new area
        if update_lib_file(lib_file_path, area):
            updated_count += 1
        else:
            failed_count += 1

        print("-" * 20) # Separator

    print("\n--- Summary ---")
    print(f"Successfully updated: {updated_count} files")
    print(f"Failed or skipped:  {failed_count} files")

    print("\n--- Density Summary ---")
    if density_data:
        avg_density = sum(density_data) / len(density_data)
        min_density = min(density_data)
        max_density = max(density_data)

        print(f"Processed {len(density_data)} macros for density.")
        print(f"Average GE/bit: {avg_density:.6f}")
        print(f"Min GE/bit:     {min_density:.6f}")
        print(f"Max GE/bit:     {max_density:.6f}")
    else:
        print("No density data was calculated.")

    print("\nUpdate complete.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python update_lib_area.py /path/to/your/tech/library")
        sys.exit(1)

    target_directory = sys.argv[1]
    main(target_directory)
