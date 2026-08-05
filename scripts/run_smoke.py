"""临时跑测试的脚本。"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import pytest
sys.exit(pytest.main([
    "src/backend/tests/test_smoke.py",
    "-q", "--no-header", "--tb=short", "-rA"
]))
