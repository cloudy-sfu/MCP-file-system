import os
import server

base_dir = os.path.dirname(__file__)
server.base_dir = base_dir
server.edit_permission = True
print("Base directory:", server.base_dir)

lines = [str(i) for i in range(1, 21)]
lines_str = "\n".join(lines)
path = os.path.join(base_dir, "test_delete_lines")
with open(path, "w") as f:
    f.write(lines_str)

server.delete_lines(path, "3-5,8,17-")
