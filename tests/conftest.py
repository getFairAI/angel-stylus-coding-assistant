import os
import sys
import tempfile

import pytest


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


# Point the vector store at a throwaway directory for the whole test session so
# tests never read from — or write feedback/conversation docs into — the real
# ./chroma_db. All Chroma code paths honor CHROMA_PATH via embeddings.get_chroma_path().
@pytest.fixture(autouse=True, scope="session")
def _isolate_chroma_path():
    tmp_dir = tempfile.mkdtemp(prefix="stylus_chroma_test_")
    os.environ["CHROMA_PATH"] = tmp_dir
    yield
