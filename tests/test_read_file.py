import os
import server

base_dir = os.path.join(os.path.dirname(__file__), "test_read_file")
server.base_dir = base_dir
print("Base directory:", server.base_dir)
for fn in os.listdir(base_dir):
    fp = os.path.join(base_dir, fn)
    print("File path:", fp)
    result = server.read_file(fp)
    print(result)
