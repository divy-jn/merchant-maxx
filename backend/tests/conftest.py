import importlib.util
import sys
import os
from unittest.mock import MagicMock

# Mock Pinecone to prevent API key errors during import
sys.modules['pinecone'] = MagicMock()
sys.modules['pinecone'].Pinecone = MagicMock()

# Make payment_state importable without going through agents/__init__.py
_state_path = os.path.join(os.path.dirname(__file__), "..", "agents", "payment_state.py")
_spec = importlib.util.spec_from_file_location("agents.payment_state", _state_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["agents.payment_state"] = _mod
_spec.loader.exec_module(_mod)
