import json
import logging
import os
import re
import sys
from base64 import b64encode
from datetime import datetime, timezone
from operator import itemgetter

import pathspec
import puremagic
from charset_normalizer import from_bytes
from mcp.server.fastmcp import FastMCP
from mcp.types import AudioContent, ImageContent, EmbeddedResource, BlobResourceContents
from pydantic import AnyUrl
from requests import Session
from urllib.parse import quote

# %% Logging system
error_handler = logging.Logger(name="Error", level=logging.ERROR)
error_handler.addHandler(logging.StreamHandler(sys.stderr))


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    error_handler.error(f"{exc_type.__name__}: {exc_value}")


sys.excepthook = handle_exception

# %% Define base directory
base_dir = os.path.abspath(os.environ.get('base_dir', os.path.expanduser("~")))
edit_permission = os.environ.get('mode') == "edit"

# %% Ignore list
session = Session()
response = session.get("https://www.toptal.com/developers/gitignore/api/windows,linux,macos")
response.raise_for_status()
ignore_list = response.text.split("\n")
ignore_regex = pathspec.PathSpec.from_lines(
        pathspec.patterns.GitWildMatchPattern, ignore_list)


# %% User-friendly file size
def format_size_bitwise(size_bytes):
    # Ref: Standard bitwise byte conversion
    suffixes = ('B', 'KiB', 'MiB', 'GiB', 'TiB')
    n = len(suffixes) - 1
    index = 0
    # Continue right-shifting by 10 bits (dividing by 1024)
    # as long as size >= 1024, and we haven't reached TiB.
    while size_bytes >= 1024 and index < n:
        size_bytes >>= 10  # Equivalent to size_bytes // 1024
        index += 1
    return f"{size_bytes} {suffixes[index]}"


# %% API
mcp = FastMCP("file-system")


@mcp.tool()
def list_dir(paths):
    """
    List all files and subfolders of a path relative to base directory. Base directory
    is the root of file system which you have access to.
    :param paths: list[str], the chain of subfolders inside the base directory you have
    access to. For example, input empty list to list all files of base directory, input
    ["test", "test_ls"] to list all files of "test/test_ls" relative to base directory.
    :return: JSON format of a table of files' meta information. Each item corresponds to
    one file, which is a list of 4 elements.
        1. File name.
        2. "directory" if it's a directory, "file" if it's a file.
        3. File size (IEC standard, 1024 based).
        4. Last modified time.
    """
    target_dir = os.path.join(base_dir, *paths)
    if os.path.commonpath([base_dir, target_dir]) != base_dir:
        raise PermissionError("Your attempt to access path outside of base directory "
                              "is denied.")
    files_info = []
    for filename in os.listdir(target_dir):
        if ignore_regex.match_file(filename):
            continue
        filepath = os.path.join(target_dir, filename)
        if os.path.isdir(filepath):
            is_folder = "directory"
        else:
            is_folder = "file"
        last_modified_time_stamp = os.path.getmtime(filepath)
        last_modified_time = datetime.fromtimestamp(
            last_modified_time_stamp, tz=timezone.utc)
        last_modified_time_str = last_modified_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        file_size_bytes = os.path.getsize(filepath)
        file_size = format_size_bitwise(file_size_bytes)
        files_info.append([filename, is_folder, file_size, last_modified_time_str])
    return json.dumps(files_info)


@mcp.tool()
def read_file(file_path):
    """
    Get the content of file. If it's a binary file, this function outputs base64 encoded
    bytes of it; if it's text, this function infers the most likely encoding, decodes it,
    and outputs the text.
    :param file_path: str, the file path relative to base directory. Don't need
    "./", can be just file name if it's directly in the base directory. Cannot input path
    to a folder.
    :return: The content of file.
    """
    uri = AnyUrl(f"mcp://{quote(file_path)}")
    file_path = os.path.join(base_dir, file_path)
    if os.path.commonpath([base_dir, file_path]) != base_dir:
        raise PermissionError("Your attempt to access path outside of base directory "
                              "is denied.")
    if not os.path.isfile(file_path):
        raise FileNotFoundError("File not found.")
    with open(file_path, "rb") as f:
        data = f.read()
    match = from_bytes(data).best()
    if match:  # is text
        text = str(match)
        return text
    else:  # is binary
        mime_list = puremagic.magic_string(data, filename="")
        if len(mime_list) > 0:
            mime = mime_list[0].mime_type
        else:
            mime = "application/octet-stream"
        data_b64 = b64encode(data).decode()
        if mime.startswith("image/"):
            return ImageContent(type='image', data=data_b64, mimeType=mime)
        elif mime.startswith("audio/"):
            return AudioContent(type="audio", data=data_b64, mimeType=mime)
        else:
            return EmbeddedResource(
                type="resource",
                resource=BlobResourceContents(uri=uri, mimeType=mime, blob=data_b64),
            )


_SEGMENT = r'[1-9]\d*(?:-(?:[1-9]\d*)?)?'
_LINE_RANGE_RE = re.compile(rf'^{_SEGMENT}(?:,{_SEGMENT})*$')
_PARSE_RE = re.compile(r'^([1-9]\d*)(?:-([1-9]\d*)?)?$')


@mcp.tool()
def delete_file(file_path):
    """
    Delete a text file. This function is designed for code editing, therefore audio,
    video, images, PDF, Microsoft Office documents and more binary files are not
    allowed to be deleted.
    :param file_path: File path of a text file. The file path is relative to base
    directory.
    :return: A string "OK" to notify the function succeed, or raise an error if
    it encounters errors.
    """
    assert edit_permission, "MCP server is in read-only mode."
    file_path = os.path.join(base_dir, file_path)
    if os.path.commonpath([base_dir, file_path]) != base_dir:
        raise PermissionError("Your attempt to access path outside of base directory "
                              "is denied.")
    if not os.path.isfile(file_path):
        return "OK"
    with open(file_path, "rb") as f:
        data = f.read()
    match = from_bytes(data).best()
    if not match:  # is not text
        raise Exception("This file is not a text file.")
    os.remove(file_path)
    return "OK"


@mcp.tool()
def create_file(file_path, content):
    """
    Create a new text file.
    :param file_path: File path of a text file. The file path is relative to base
    directory.
    :param content: str, string as the content of the new file. You should use "\n" LF
    line seperator regardless of operating system. MCP server will handle line seperator
    conversion based on operating system automatically.
    :return: A string "OK" to notify the function succeed, or raise an error if it
    encounters errors.
    """
    assert edit_permission, "MCP server is in read-only mode."
    file_path = os.path.join(base_dir, file_path)
    if os.path.commonpath([base_dir, file_path]) != base_dir:
        raise PermissionError("Your attempt to access path outside of base directory "
                              "is denied.")
    if not os.path.exists(file_path):
        raise FileExistsError("This file already exists. You should edit or choose a "
                              "different filename, but cannot overwrite it.")
    parent_dir = os.path.dirname(file_path)
    if os.path.commonpath([base_dir, file_path]) != base_dir:
        # File path inside base_dir, but parent_dir outside base_dir, the only situation
        # is "file_path" is the same as base_dir. LLM tries to overwrite the folder by a
        # file.
        raise PermissionError("You cannot overwrite base directory folder.")
    os.makedirs(parent_dir, exist_ok=True)
    with open(file_path, "w") as f:
        f.write(content)
    return "OK"



@mcp.tool()
def delete_lines(file_path, line_ranges):
    r"""
    Delete specific line ranges from a text file. The line index starts from 1.
    :param file_path: File path of a text file. The file path is relative to base
    directory.
    :param line_ranges: Line ranges, must fit the following regex.
    '^[1-9]\d*(?:-(?:[1-9]\d*)?)?(?:,[1-9]\d*(?:-(?:[1-9]\d*)?)?)*$'
    :return: A string "OK" to notify the function succeed, or raise an error if
    it encounters errors.
    """
    assert edit_permission, "MCP server is in read-only mode."
    file_path = os.path.join(base_dir, file_path)
    if os.path.commonpath([base_dir, file_path]) != base_dir:
        raise PermissionError("Your attempt to access path outside of base directory "
                              "is denied.")
    if not os.path.isfile(file_path):
        raise FileNotFoundError("File not found.")
    match = _LINE_RANGE_RE.match(line_ranges)
    if not match:
        raise Exception("Input argument line_ranges is not valid.")
    with open(file_path, "rb") as f:
        data = f.read()
    match = from_bytes(data).best()
    if not match:  # is not text
        raise Exception("This file is not a text file.")

    text = str(match)
    lines = text.splitlines()
    n = len(lines)
    lines_no = set(range(1, n + 1))
    lines_no_del = set()
    for seg in line_ranges.split(','):
        match = _PARSE_RE.match(seg)  # guaranteed to match since validation passed
        start = int(match.group(1))
        if "-" in seg:
            end_str = match.group(2)
            if end_str:
                end = int(end_str)
            else:
                end = n
            lines_no_del.update(range(start, end + 1))
        else:
            lines_no_del.add(start)
    lines_no = lines_no.difference(lines_no_del)
    lines_idx = sorted([i - 1 for i in lines_no])

    if not lines_idx:
        logging.warning("You have cleared all content of this file.")
        with open(file_path, "w"):
            pass  # clear the file
        return "OK"

    new_text = "\n".join(itemgetter(*lines_idx)(lines))
    with open(file_path, "w") as f:
        f.write(new_text)
    return "OK"


@mcp.tool()
def insert_lines(file_path, pos, content):
    """
    Insert string into the specific position of a text file.
    :param file_path: str, file path of a text file. The file path is relative to base
    directory.
    :param pos: int, position to insert the content, starting from 0. For example, since
    line number starts from 1, position 0 means inserting before the first line, position
    1 means inserting between line 1 and line 2 ... position "n" means inserting between
    line "n" and line "n+1". When the total number of line is "n", the maximum "pos" is
    "n" which means inserting to the end of file.
    :param content: str, string as the content of the new file. You should use "\n" LF
    line seperator regardless of operating system. MCP server will handle line seperator
    conversion based on operating system automatically.
    :return: A string "OK" to notify the function succeed, or raise an error if it
    encounters errors.
    """
    assert edit_permission, "MCP server is in read-only mode."
    file_path = os.path.join(base_dir, file_path)
    if os.path.commonpath([base_dir, file_path]) != base_dir:
        raise PermissionError("Your attempt to access path outside of base directory "
                              "is denied.")
    if not os.path.isfile(file_path):
        raise FileNotFoundError("File not found.")
    with open(file_path, "rb") as f:
        data = f.read()
    match = from_bytes(data).best()
    if not match:  # is not text
        raise Exception("This file is not a text file.")
    text = str(match)
    lines = text.splitlines()
    inserted_lines = content.splitlines()
    new_lines = lines[:pos] + inserted_lines + lines[pos:]
    new_lines = "\n".join(new_lines)
    with open(file_path, "w") as f:
        f.write(new_lines)
    return "OK"


@mcp.tool()
def search_lines(file_path, pattern, match_case, whole_word):
    """
    Search a text file and return all lines containing the specified pattern.
    :param file_path: str. Path to the text file, relative to the base directory.
    :param pattern: str. Substring to search for; any line containing this
        pattern will be included in the result.
    :param match_case: bool. If True, the search is case-sensitive and a line
        is returned only when the pattern's case matches exactly. If False,
        the search is case-insensitive.
    :param whole_word: bool. If True, a line is returned only when the pattern
        appears as a whole word (i.e., bounded by non-word characters or line
        boundaries), rather than as part of a larger word.
    :return: list. Line numbers and text from the file that match the search criteria.
        Line number starts from 1.
    """
    file_path = os.path.join(base_dir, file_path)
    if os.path.commonpath([base_dir, file_path]) != base_dir:
        raise PermissionError("Your attempt to access path outside of base directory "
                              "is denied.")
    if not os.path.isfile(file_path):
        raise FileNotFoundError("File not found.")
    with open(file_path, "rb") as f:
        data = f.read()
    match = from_bytes(data).best()
    if not match:  # is not text
        raise Exception("This file is not a text file.")
    text = str(match)
    lines = text.splitlines()
    results = []
    if not match_case:
        pattern = pattern.lower()
    for i, line in enumerate(lines):
        if match_case:
            line_to_compare = line
        else:
            line_to_compare = line.lower()
        if whole_word:
            match = re.search(rf"\b{pattern}\b", line_to_compare)
            if match:
                results.append([i+1, line])
        else:
            if pattern in line_to_compare:
                results.append([i+1, line])
    return json.dumps(results)


if __name__ == '__main__':
    mcp.run()
