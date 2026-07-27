import os
import sys
import unittest.mock

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Provide dummy credentials so config/database import without a real cluster
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017/test")

# Pre-populate tools.clients so plugins.bots module-level assignment doesn't KeyError
# ponytail: bots.py line 53 does `session = clients["session"]` at import time — patch before import
import tools
_mock_client = unittest.mock.MagicMock()
tools.clients["session"] = _mock_client
tools.clients["call_py"] = _mock_client
tools.clients["bot"] = _mock_client
