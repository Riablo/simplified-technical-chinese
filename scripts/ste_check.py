#!/usr/bin/env python3
"""旧命令路径的兼容入口。此分支执行简明技术中文检查，不再检查英文 STE。"""

from stc_check import main


if __name__ == "__main__":
    raise SystemExit(main())
