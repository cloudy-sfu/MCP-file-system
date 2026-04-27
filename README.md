# MCP file system
MCP server for directory-based context injection

![](https://shields.io/badge/dependencies-Python_3.14-blue)

For Python developers who have usage-based LLM APIs rather than GitHub Copilot, this MCP server provides an alternative. It enables LLMs to read a wide range of file formats—including text, multimedia, PDFs, and Microsoft Office documents—and perform read & write operations on text files.

The server supports both read-only and read-write modes. As it does not include an "Accept or Reject" mechanism for changes, we strongly recommend using Git to manage version control and track modifications.



## Install

Create and activate a Python virtual environment.

Run the following command in terminal.

```
pip install -r requirements.txt
```



### MCP server config

Name: File system

Type: stdio

Command: 

The value is the absolute path of `start_server.ps1` in the program's root directory.

Environment variables (inside MCP server config form):

| Variable name | Description                                                  |
| ------------- | ------------------------------------------------------------ |
| `base_dir`    | The base directory, path of a folder in local machine or a network mapped drive. LLM has access to read all the files in the base directory. |

Tools:

To make LLM read only, disable "auto approve" of the following tools.

```
delete_file, create_file, delete_lines, insert_lines
```

