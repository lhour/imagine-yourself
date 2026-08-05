"""临时跑 api 测试。"""
import sys, os
sys.path.insert(0, os.path.abspath('.'))
import pytest
sys.exit(pytest.main([
    "src/backend/tests/test_api.py",
    "-q", "--no-header", "--tb=short", "-rA", "-x"
]))
