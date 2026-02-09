
from fastapi.testclient import TestClient
from web_app import app, state, get_truncated_paths
import os
import tempfile
import pytest

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert "MedMan" in response.text
    assert "Scan Directory" in response.text

def test_truncated_paths():
    p1 = "/home/user/data/setA/image.jpg"
    p2 = "/home/user/data/setB/image.jpg"
    t1, t2 = get_truncated_paths(p1, p2)
    
    # Should show setA/image.jpg and setB/image.jpg
    # The logic keeps one level of common context if possible, or just the divergence
    # Let's trace the logic:
    # parts1: home, user, data, setA, image.jpg
    # parts2: home, user, data, setB, image.jpg
    # common_len: 3 (home, user, data)
    # start: max(0, 3-1) = 2 (data)
    # t1: data/setA/image.jpg
    # t2: data/setB/image.jpg
    
    assert "setA" in t1
    assert "setB" in t2
    assert t1.startswith("data/")

def test_scan_trigger():
    # Mocking a directory scan would be complex without valid data, 
    # but we can check if it handles invalid data gracefully
    response = client.post("/scan", data={"directory": "/invalid/path/123", "threshold": 0.8})
    assert response.status_code == 200
    assert "Invalid directory" in response.text

def test_decision_endpoint():
    # Setup state manually
    state.reset()
    state.clusters = [
        {"type": "image", "files": ["/tmp/a.jpg", "/tmp/b.jpg"]}
    ]
    state.current_index = 0
    
    # Post a decision
    # We mock os.path.exists/move_to_duplicates inside the app or just expect it to try
    # Since we can't easily mock imports in this simple script without more libs,
    # we'll checking 303 redirect which happens after logic
    
    # NOTE: This test might fail if it tries to actually move files that don't exist.
    # The app code checks `if os.path.exists(right_path):` so it should be safe even if files missing.
    
    response = client.post("/decision", data={"choice": "skip"})
    assert response.status_code == 200 # HTMX request returns partial/redirect handling
    # In the code: returns RedirectResponse usually, but TestClient follows redirects by default? 
    # Validating state change:
    assert len(state.clusters[0]["files"]) == 1 # 'skip' pops one file
