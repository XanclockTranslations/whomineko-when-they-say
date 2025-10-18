"""
This script converts an ONScripter compiled script into per-episode annotated .txt files.

Output files (one per episode) are written as:
    <episode>_annotated.txt

Example inside a file:
    char_but: `".........Should've taken the boat...`
    char_but: `......the boat......"`
    char_mar: `"Gonna faaalll!`
    char_mar: `Gonna faaalll!`
    char_mar: `Uu-uu-uu-uu!!"`
    char_ros: `"Maria, that's enough!"`
    char_ros: `"......But what a surprise.`

Notes:
 - Internally line numbers are used to preserve ordering across chunk boundaries, but they are NOT written to output files.
 - Dialogue fragments are detected as text inside backticks: `...`.
"""

from re import Match
from re import Pattern
import argparse
import json
import os
import re
import tempfile
from multiprocessing import Pool, cpu_count

# Regex patterns - START.

## Episode matching.
DEFAULT_EPISODE_PATTERN: str = r"^\*(umi[1-8]_(?:op|\d+))\b"
## Message-by-character matching.
MSGWND_RE: Pattern[str] = re.compile(r"^\s*msgwnd_([\w]+)\b", re.IGNORECASE)
## Dialogue line matching.
DIALOG_LINE_RE: Pattern[str] = re.compile(r"^\s*(?:\*\w+\s*)?d\d*\b", re.IGNORECASE)## Backtick fragment matching.
BACKTICK_RE: Pattern[str] = re.compile(r"`([^`]+)`")

# Regex patterns - END.

# Function definitions - START.


def parse_file(infile: str, episode_pattern: str) -> list[dict[str, str | int]]:
    """
    This function parses the entire input file directly.

    It reads the file line by line, extracts dialogue fragments, and returns them as a list of dictionaries.
    Each dictionary has keys: "lineno", "episode", "character", "text".

    Arguments
    ---------
    infile : str
        Path to the input text file to be parsed.

    episode_pattern : str
        Regex pattern to identify episode labels.

    Returns
    -------
    list[dict[str, str | int]]
        A list of dictionaries containing parsed dialogue fragments.
    """
    # Compile the episode regex pattern.
    episode_re: Pattern[str] = re.compile(episode_pattern, re.IGNORECASE)

    # Initialize storage for rows.
    rows: list[dict[str, str | int]] = []

    # Initialize episode and character state trackers.
    current_episode: str | None = None
    current_character: str | None = None

    # Open and read the input file.
    with open(infile, "r", encoding="utf-8") as f:
        # Iterate through each line in the file.
        for lineno, line in enumerate(f, start=1):
            # Right-strip newline and skip empty lines.
            line = line.rstrip("\n")
            if not line:
                continue

            # Check if line marks a new episode and update current episode context.
            episode: str | None = _try_parse_episode(line, episode_re)
            if episode is not None:
                current_episode = episode
                continue

            # Check if line marks a character change and update current character context.
            character: str | None = _try_parse_character(line)
            if character is not None:
                current_character = character
                continue

            # Dialogue detection and extract backtick fragments.
            fragments: list[dict[str, str | int]] = _extract_dialogue_fragments(
                line, lineno, current_episode, current_character
            )
            rows.extend(fragments)

    # Return the extracted rows.
    return rows


def _try_parse_episode(line: str, episode_re: Pattern[str]) -> str | None:
    """
    This function is a helper function of `parse_file`.

    It checks if a line marks a new episode and extracts the episode name.

    Returns the episode name if found, otherwise `None`.

    Arguments
    ---------
    line : str
        The line to check for episode markers.

    episode_re : Pattern[str]
        Compiled regex pattern to match episode labels.

    Returns
    -------
    str | None
        The episode name if found, otherwise None.
    """
    # Match the line against the episode regex.
    m: Match[str] | None = episode_re.match(line)
    # If a match is found, extract and return the episode name.
    if m:
        current_episode: str | None = m.group(1)
        # Validate the type of `current_episode`.
        if current_episode is not None and type(current_episode) is not str:
            raise ValueError("`current_episode` must be a string or None")
        # Return the extracted episode name.
        return current_episode
    # Return `None` if no match is found.
    return None


def _try_parse_character(line: str) -> str | None:
    """
    This function is a helper function of `parse_file`.

    It checks if a line marks a character change and extracts the character name.

    Returns the character name if found, otherwise `None`.

    Arguments
    ---------
    line : str
        The line to check for character markers.

    Returns
    -------
    str | None
        The character name if found, otherwise None.
    """
    # Match the line against the character regex.
    m: Match[str] | None = MSGWND_RE.match(line)

    # If a match is found, extract and return the character name.
    if m:
        current_character: str | None = m.group(1)
        # Validate the type of `current_character`.
        if current_character is not None and type(current_character) is not str:
            raise ValueError("`current_character` must be a string or None")
        # Return the extracted character name.
        return current_character
    # Return `None` if no match is found.
    return None


def _extract_dialogue_fragments(
    line: str, lineno: int, current_episode: str | None, current_character: str | None
) -> list[dict[str, str | int]]:
    """
    This function is a helper function of `parse_chunk_file`.

    It extracts dialogue fragments from a line and returns them as a list of dictionaries.

    Returns a list of dictionaries with keys: "lineno", "episode", "character", "text".

    Arguments
    ---------
    line : str
        The line to extract dialogue fragments from.

    lineno : int
        The line number in the original file.

    current_episode : str | None
        The current episode context.

    current_character : str | None
        The current character context.

    Returns
    -------
    list[dict[str, str | int]]
        A list of dictionaries containing the extracted dialogue fragments.
        Each dictionary has keys: "lineno", "episode", "character", "text".
    """
    # Initialize storage for dialogue fragments.
    fragments: list[dict[str, str | int]] = []

    # Check if this is a dialogue line with backticks.
    if DIALOG_LINE_RE.match(line) and "`" in line:
        # Find all backtick-enclosed fragments in the line.
        frags: list[str] = BACKTICK_RE.findall(line)
        # For each fragment...
        for frag in frags:
            # Initialize the text variable as the fragment.
            text: str = frag
            # Append the extracted data to the fragments list.
            fragments.append(
                {
                    "lineno": lineno,
                    "episode": current_episode,
                    "character": current_character,
                    "text": text,
                }
            )

    return fragments


def split_file_to_chunks(infile: str, n: int, tmpdir: str) -> list[str]:
    """
    This function splits the input file into n chunks with line numbers.

    Each chunk file contains lines prefixed with their original line number.

    Arguments
    ---------
    infile : str
        Path to the input file to split.
    n : int
        Number of chunks to create.
    tmpdir : str
        Temporary directory to store chunk files.

    Returns
    -------
    list[str]
        List of paths to the created chunk files.
    """
    # Ensure the temporary directory exists.
    os.makedirs(tmpdir, exist_ok=True)

    # Read all lines from the input file.
    with open(infile, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Calculate chunk size.
    total_lines = len(lines)
    chunk_size = (total_lines + n - 1) // n  # Ceiling division

    # Create chunk files.
    chunk_paths = []
    for i in range(n):
        start = i * chunk_size
        end = min(start + chunk_size, total_lines)
        chunk_path = os.path.join(tmpdir, f"chunk_{i:04d}.txt")
        
        with open(chunk_path, "w", encoding="utf-8") as cf:
            for lineno in range(start, end):
                # Write line with its original line number (1-indexed).
                cf.write(f"{lineno + 1}\t{lines[lineno]}")
        
        chunk_paths.append(chunk_path)

    return chunk_paths


def _parse_lineno_and_line(raw: str) -> tuple[int, str]:
    """
    This function parses a line from a chunk file.

    It extracts the line number and content from a tab-separated line.

    Arguments
    ---------
    raw : str
        The raw line from a chunk file (format: "lineno\\tline_content").

    Returns
    -------
    tuple[int, str]
        A tuple containing the line number and the line content.
    """
    # Split the line into line number and content.
    parts = raw.split("\t", 1)
    if len(parts) == 2:
        lineno = int(parts[0])
        line = parts[1].rstrip("\n")
    else:
        # Fallback for malformed lines.
        lineno = -1
        line = raw.rstrip("\n")
    
    return lineno, line


def parse_chunk_file(args_tuple: tuple[str, str]) -> str:
    """
    This function processes a chunk file.

    It takes a tuple of `(chunk_path, episode_pattern)`.
    It reads the chunk file, extracts dialogue fragments, and writes them to a JSONL file with objects of the form: `{"lineno": int, "episode": str, "character": str, "text": str}`.

    Returns the path to the generated JSONL file.

    Arguments
    ---------
    args_tuple : tuple[str, str]
        A tuple containing:
        - chunk_path : str
            Path to the chunk file to be parsed.
        - episode_pattern : str
            Regex pattern to identify episode labels.

    Returns
    -------
    str
        Path to the output JSONL file containing parsed dialogue fragments.
    """
    # Initialize state variables.
    chunk_path: str = args_tuple[0]
    episode_pattern: str = args_tuple[1]
    episode_re: Pattern[str] = re.compile(episode_pattern, re.IGNORECASE)

    # Initialize the output JSONL path and storage for rows.
    out_jsonl: str = chunk_path + ".parsed.jsonl"
    rows: list[dict[str, str]] = []

    # Initialize episode and character state trackers.
    current_episode: str | None = None
    current_character: str | None = None

    # Open and read the chunk file.
    with open(chunk_path, "r", encoding="utf-8") as f:
        # Iterate through each line in the chunk file.
        for raw in f:
            # Right-strip newline and skip empty lines.
            raw = raw.rstrip("\n")
            if not raw:
                continue

            # Extract line number and content.
            lineno, line = _parse_lineno_and_line(raw)

            # Check if line marks a new episode (e.g., umi1_op, umi2_01) and update current episode context.
            episode: str | None = _try_parse_episode(line, episode_re)
            if episode is not None:
                current_episode = episode
                continue

            # Check if line marks a character change and update current character context.
            character: str | None = _try_parse_character(line)
            if character is not None:
                current_character = character
                continue

            # Dialogue detection and extract backtick fragments.
            fragments: list[dict[str, str | int]] = _extract_dialogue_fragments(
                line, lineno, current_episode, current_character
            )
            rows.extend(fragments)

    # Write the extracted rows to the output JSONL file.
    with open(out_jsonl, "w", encoding="utf-8") as outf:
        for r in rows:
            outf.write(json.dumps(r, ensure_ascii=False) + "\n")

    # Return the path to the output JSONL file.
    return out_jsonl

def _read_jsonl_files(paths: list[str]) -> list[dict[str, str | int]]:
    """
    This function is a helper function of `merge_and_write_per_episode`.

    It reads all parsed JSONL files and returns a list of row dictionaries.
    
    Arguments
    ---------
    paths : list[str]
      Paths to the JSONL files to read.
    
    Returns
    -------
    list[dict[str, str | int]]
        A list of row dictionaries read from the JSONL files.
    """
    # Initialize storage for all rows.
    rows: list[dict[str, str | int]] = []

    # Read each JSONL file and append its rows to the list.
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                rows.append(json.loads(line))

    # Return the combined list of rows.
    return rows


def _sort_rows(rows: list[dict[str, str | int]]) -> list[dict[str, str | int]]:
    """
    This function is a helper function of `merge_and_write_per_episode`.
    
    Returns the rows sorted globally by their 'lineno' field.

    Arguments
    ---------
    rows : list[dict[str, str | int]]
        List of row dictionaries to sort.

    Returns
    -------
    list[dict[str, str | int]]
        The sorted list of row dictionaries.
    """
    return sorted(rows, key=lambda o: (o.get("lineno", -1),))


def _propagate_state(rows: list[dict[str, str | int]]) -> list[dict[str, str]]:
    """
    This function is a helper function of `merge_and_write_per_episode`.

    It propagates 'episode' and 'character' fields across rows, filling missing ones.
    It skips any rows where episode cannot be inferred.
    
    Returns a list of merged rows with guaranteed 'episode' and 'character' fields.

    Arguments
    ---------
    rows : list[dict[str, str | int]]
        List of row dictionaries to process.
    
    Returns
    -------
    list[dict[str, str]]
        A list of merged row dictionaries with propagated 'episode' and 'character' fields.
    """
    # Initialize storage for merged rows and state trackers.
    merged: list[dict[str, str]] = []
    last_episode: str | None = None
    last_character: str | None = None

    # Iterate through each row and propagate state.
    for o in rows:
        # Determine episode and character, falling back to last known values.
        ep = o.get("episode") or last_episode
        ch = o.get("character") or last_character

        # Skip rows without a known episode.
        if ep is None:
            continue

        # Update last known episode and character.
        last_episode = ep
        last_character = ch

        # Append the merged row with guaranteed fields.
        merged.append({
            "episode": ep,
            "character": ch or "unknown",
            "text": o.get("text", "")
        })

    # Return the merged rows with guaranteed fields.
    return merged


def _group_by_episode(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    """
    This function is a helper function of `merge_and_write_per_episode`.

    It groups rows by their 'episode' key.

    Returns a dictionary mapping episode names to lists of row dictionaries.

    Arguments
    ---------
    rows : list[dict[str, str]]
        List of row dictionaries to group.
    
    Returns
    -------
    dict[str, list[dict[str, str]]]
        A dictionary mapping episode names to lists of row dictionaries.
    """
    # Initialize storage for grouped rows.
    grouped = {}

    # Group rows by episode.
    for r in rows:
        grouped.setdefault(r["episode"], []).append(r)

    # Return the grouped rows.
    return grouped


def _write_episode_files(grouped: dict[str, list[dict[str, str]]], out_dir: str) -> list[str]:
    """
    This function is a helper function of `merge_and_write_per_episode`.
    It writes one annotated .txt file per episode in the output directory.

    Returns a list of episode names written.

    Arguments
    ---------
    grouped : dict[str, list[dict[str, Any]]]
        A dictionary mapping episode names to lists of row dictionaries.

    out_dir : str
        Directory to write the episode files into.
    
    Returns
    -------
    list[str]
        A list of episode names written.
    """
    # Ensure the output directory exists.
    os.makedirs(out_dir, exist_ok=True)

    # Initialize storage for written episode names.
    written: list[str] = []

    # Iterate through each episode and its rows.
    for episode, rows in grouped.items():
        # Write the episode's annotated .txt file.
        fname: str = os.path.join(out_dir, f"{episode}_annotated.txt")
        with open(fname, "w", encoding="utf-8") as outf:
            # Write each row in the specified format.
            for r in rows:
                # Ensure character name starts with "char_".
                chname = r["character"] or "unknown"
                if not chname.startswith("char_"):
                    chname = "char_" + chname
                outf.write(f"{chname}: `{r['text']}`\n")
        # Record the written episode name.
        written.append(episode)

    # Return the list of written episode names.
    return written

def merge_and_write_per_episode(parsed_jsonl_paths: list[str], out_dir: str) -> list[str]:
    """
    This function merges parsed JSONL files, propagates episode/character state,
    and writes one annotated .txt file per episode in the specified output directory.

    Returns a list of episode names written.

    Arguments
    ---------
    parsed_jsonl_paths : list[str]
        List of paths to parsed JSONL files.
    out_dir : str
        Directory to write the episode files into.

    Returns
    -------
    list[str]
        A list of episode names written.
    """
    # Read, sort, propagate state, group by episode, and write episode files.
    rows: list[dict[str, int | str]] = _read_jsonl_files(parsed_jsonl_paths)
    rows: list[dict[str, int | str]] = _sort_rows(rows)
    merged: list[dict[str, str]] = _propagate_state(rows)
    grouped: dict[str, list[dict[str, str]]] = _group_by_episode(merged)
    written: list[str] = _write_episode_files(grouped, out_dir)

    # Return the list of written episode names.
    return written


def parser_settings() -> argparse.Namespace:
    """
    This function sets up and returns the argument parser for the script.

    Returns
    -------
    argparse.Namespace
        Parsed command-line arguments.
    """
    # Initialize argument parser and define arguments.
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Parse ONScripter script into episode .txt files."
    )
    parser.add_argument(
        "infile", type=str, help="path to the compiled script .txt file"
    )
    parser.add_argument(
        "--n",
        type=int,
        default=1,
        help="number of chunks to split the file into; processed in parallel (default: 1)",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="episode_annotated_txts",
        help="directory to write per-episode annotated .txt files (default: episode_annotated_txts)",
    )
    parser.add_argument(
        "--tmp", type=str, default=None, help="temporary directory for chunk files"
    )
    parser.add_argument(
        "--cleanup",
        dest="cleanup",
        default=True,
        help="remove intermediate chunk files (default: True)",
    )

    # Return parsed arguments.
    return parser.parse_args()

# Function definitions - END.

# Main function - START.


def main():
    # Initialize and parse command-line arguments.
    args: argparse.Namespace = parser_settings()

    # Extract arguments into variables.
    infile: str = args.infile
    n: int = max(1, args.n)
    out_dir: str = args.out_dir
    tmpdir: str = args.tmp or tempfile.mkdtemp(prefix="ons_parser_")
    
    # Define episode pattern using the default value.
    episode_pattern: str = DEFAULT_EPISODE_PATTERN

    # Print initial settings.
    print(f"Input file: {infile}")
    print(f"Splitting into {n} chunk(s). Temporary dir: {tmpdir}")
    print(f"Episode regex: {episode_pattern}")

    # 1. Split input file into chunks.
    chunk_paths: list[str] = split_file_to_chunks(infile, n, tmpdir)
    print(f"Created {len(chunk_paths)} chunk files.")

    # 2. Parse each chunk file in parallel using multiprocessing.
    parsed_jsonl_paths: list[str] = []
    chunk_args: list[tuple[str, str]] = [(chunk_path, episode_pattern) for chunk_path in chunk_paths]
    
    if n == 1:
        # For single chunk, process directly without multiprocessing overhead.
        print("Processing chunk 1/1...")
        parsed_path = parse_chunk_file(chunk_args[0])
        parsed_jsonl_paths.append(parsed_path)
    else:
        # Use multiprocessing for multiple chunks.
        num_workers = min(n, cpu_count())
        print(f"Processing {n} chunks in parallel with {num_workers} workers...")
        with Pool(processes=num_workers) as pool:
            parsed_jsonl_paths = pool.map(parse_chunk_file, chunk_args)

    print("Parsing done. Merging and writing per-episode files...")

    # 3. Merge parsed parts and write per-episode annotated .txt files.
    episodes_written = merge_and_write_per_episode(parsed_jsonl_paths, out_dir)
    print(f"Wrote {len(episodes_written)} episode file(s) to: {out_dir}")
    for ep in episodes_written:
        print(" -", f"{ep}_annotated.txt")

    # Cleanup temporary files if requested.
    if args.cleanup:
        for p in chunk_paths + parsed_jsonl_paths:
            try:
                os.remove(p)
            except Exception:
                pass
        try:
            os.rmdir(tmpdir)
        except Exception:
            pass
        print("Cleaned up temporary files.")


# The main entry point.
if __name__ == "__main__":
    main()

# Main function - END.
