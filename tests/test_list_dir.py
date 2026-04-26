import os
import server

server.base_dir = os.path.dirname(os.path.dirname(__file__))
print("Base directory:", server.base_dir)
print("/tests", server.list_dir("tests"))
print("/tests/test_list_dir", server.list_dir("tests", "test_list_dir"))
