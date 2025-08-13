# Project Overview

``` py
relative_path = "../db/notice.db"

current_file_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file_path)
DB_PATH = os.path.abspath(os.path.join(current_dir, relative_path))
```