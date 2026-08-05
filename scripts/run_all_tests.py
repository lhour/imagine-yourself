"""跑全部 src/backend 测试。"""
import sys, os
sys.path.insert(0, os.path.abspath('.'))
import pytest
sys.exit(pytest.main([
    "src/backend/tests/",
    "-q", "--no-header", "--tb=short", "-rA"
]))
