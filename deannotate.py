"""
This script converts a folder of annotated scripts into scripts without annotations.

Output files (one per episode) are written as:
    <episode>.txt

Example inside a file:
    `".........Should've taken the boat...`
    `......the boat......"`
    `"Gonna faaalll!`
    `Gonna faaalll!`
    `Uu-uu-uu-uu!!"`
    `"Maria, that's enough!"`
    `"......But what a surprise.`

Notes:
 - Input files are expected to be in format: char_xxx: `text`
 - Character prefixes (char_xxx: ) are stripped from output.
 - Each line's text is extracted from backticks and written as-is.
"""

import argparse
import os
import re
from multiprocessing import Pool, cpu_count
from typing import Pattern

# Regex patterns - START.

## Annotated line matching: extracts text from format "char_xxx: `text`"
ANNOTATED_LINE_RE: Pattern[str] = re.compile(r"^\s*char_\w+:\s*`([^`]+)`\s*$")

# Regex patterns - END.

# Function definitions - START.


def deannotate_file(input_path: str, output_path: str) -> int:
    """
    This function reads an annotated .txt file and writes a deannotated version.

    It extracts dialogue text from lines in format "char_xxx: `text`" and writes
    just the backtick-enclosed content to the output file.

    Returns the number of lines written.

    Arguments
    ---------
    input_path : str
        Path to the input annotated .txt file.

    output_path : str
        Path to write the deannotated .txt file.

    Returns
    -------
    int
        Number of dialogue lines written to the output file.
    """
    lines_written: int = 0

    with open(input_path, "r", encoding="utf-8") as infile:
        with open(output_path, "w", encoding="utf-8") as outfile:
            for line in infile:
                # Skip empty lines.
                if not line:
                    continue

                # Try to match annotated line pattern.
                match = ANNOTATED_LINE_RE.match(line)
                if match:
                    # Extract text from backticks.
                    text: str = match.group(1)
                    # Write as backtick-enclosed text.
                    outfile.write(f"`{text}`\n")
                    lines_written += 1

    return lines_written


def process_single_file(args_tuple: tuple[str, str, str]) -> tuple[str, str, int]:
    """
    This function processes a single annotated file.

    It is designed to be called by multiprocessing workers.

    Arguments
    ---------
    args_tuple : tuple[str, str, str]
        A tuple containing:
        - input_path : str
            Path to the input annotated .txt file.
        - output_path : str
            Path to write the deannotated .txt file.
        - filename : str
            Original filename for logging.

    Returns
    -------
    tuple[str, str, int]
        A tuple containing (filename, output_filename, lines_written).
    """
    input_path: str = args_tuple[0]
    output_path: str = args_tuple[1]
    filename: str = args_tuple[2]

    # Process the file.
    lines_written: int = deannotate_file(input_path, output_path)

    # Extract output filename for return.
    output_filename: str = os.path.basename(output_path)

    return (filename, output_filename, lines_written)


def process_directory(input_dir: str, output_dir: str, n: int = 1) -> list[str]:
    """
    This function processes all annotated .txt files in the input directory.

    It looks for files ending with "_annotated.txt" and creates deannotated versions
    in the output directory with names ending in ".txt" (without "_annotated").

    Returns a list of processed episode names.

    Arguments
    ---------
    input_dir : str
        Directory containing annotated .txt files.

    output_dir : str
        Directory to write deannotated .txt files.

    n : int
        Number of worker processes to use for parallel processing (default: 1).

    Returns
    -------
    list[str]
        List of episode names that were processed.
    """
    # Ensure output directory exists.
    os.makedirs(output_dir, exist_ok=True)

    processed: list[str] = []

    # Collect all files to process.
    file_args: list[tuple[str, str, str]] = []
    for filename in sorted(os.listdir(input_dir)):
        # Only process files ending with "_annotated.txt".
        if filename.endswith("_annotated.txt"):
            # Extract episode name by removing "_annotated.txt" suffix.
            episode_name: str = filename[:-len("_annotated.txt")]

            # Construct input and output paths.
            input_path: str = os.path.join(input_dir, filename)
            output_filename: str = f"{episode_name}.txt"
            output_path: str = os.path.join(output_dir, output_filename)

            file_args.append((input_path, output_path, filename))
            processed.append(episode_name)

    # Process files.
    if n == 1 or len(file_args) == 1:
        # Process sequentially without multiprocessing overhead.
        for args in file_args:
            result = process_single_file(args)
            print(f"Processed {result[0]} -> {result[1]} ({result[2]} lines)")
    else:
        # Process in parallel using multiprocessing.
        num_workers = min(n, cpu_count(), len(file_args))
        print(f"Processing {len(file_args)} files in parallel with {num_workers} workers...")
        with Pool(processes=num_workers) as pool:
            results = pool.map(process_single_file, file_args)
        
        # Print results.
        for result in results:
            print(f"Processed {result[0]} -> {result[1]} ({result[2]} lines)")

    return processed


def parser_settings() -> argparse.Namespace:
    """
    This function sets up and returns the argument parser for the script.

    Returns
    -------
    argparse.Namespace
        Parsed command-line arguments.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Convert annotated episode files back to plain dialogue files."
    )
    parser.add_argument(
        "--in-dir",
        type=str,
        default="episode_annotated_txts",
        help="directory containing annotated .txt files (default: episode_annotated_txts)",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="episode_txts",
        help="directory to write deannotated .txt files (default: episode_txts)",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=1,
        help="number of worker processes for parallel processing (default: 1)",
    )

    return parser.parse_args()


# Function definitions - END.

# Main function - START.


def main():
    """
    Main entry point for the deannotation script.

    Processes all annotated files in the input directory and writes
    deannotated versions to the output directory.
    """
    # Parse command-line arguments.
    args: argparse.Namespace = parser_settings()

    input_dir: str = args.in_dir
    output_dir: str = args.out_dir
    n: int = max(1, args.n)

    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Worker processes: {n}")
    print()

    # Process all annotated files.
    processed: list[str] = process_directory(input_dir, output_dir, n)

    print()
    print(f"Successfully processed {len(processed)} episode file(s).")
    if processed:
        print("Episodes processed:")
        for episode in processed:
            print(f" - {episode}")


# The main entry point.
if __name__ == "__main__":
    main()


# Main function - END.

