import os
import server

base_dir = os.path.dirname(__file__)
server.base_dir = base_dir
server.edit_permission = True
print("Base directory:", server.base_dir)
path = os.path.join(base_dir, "test_search_lines")

print("Case insensitive")
print(server.search_lines(path, "cat", False, False))
print("Case sensitive")
print(server.search_lines(path, "cat", True, False))
print("Case insensitive, whole word")
print(server.search_lines(path, "cat", False, True))
print("Case sensitive, whole word")
print(server.search_lines(path, "cat", True, True))
