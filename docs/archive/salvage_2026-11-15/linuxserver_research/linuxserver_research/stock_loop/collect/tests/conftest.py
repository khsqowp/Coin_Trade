import sys
from pathlib import Path
from collections import namedtuple
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))

@pytest.fixture(autouse=True)
def roomy_test_disk(monkeypatch):
    Usage=namedtuple('Usage','total used free')
    monkeypatch.setattr('collect.common.shutil.disk_usage',lambda path: Usage(100,20,80))
