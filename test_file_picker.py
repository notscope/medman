
from fastapi.testclient import TestClient
from web_app import app
import os

client = TestClient(app)

def test_browse_api_access_denied_without_login():
    response = client.get("/api/browse")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

def test_browse_api_root():
    # Helper to login
    client.post("/login", data={"username": "admin", "password": "medman"})
    
    # Test browsing user home or root (default)
    response = client.get("/api/browse")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "file-browser-nav" in response.text
    assert "breadcrumbs" in response.text
    # Should contain at least some directories from the system
    assert "Select Current" in response.text

def test_browse_api_specific_path():
    client.post("/login", data={"username": "admin", "password": "medman"})
    
    # Test browsing the current directory
    current_path = os.path.dirname(os.path.abspath(__file__))
    response = client.get(f"/api/browse?path={current_path}")
    assert response.status_code == 200
    assert "file-grid" in response.text
    # "templates" directory should be listed
    assert "templates" in response.text

def test_browse_parent_navigation():
    client.post("/login", data={"username": "admin", "password": "medman"})
    
    current_path = os.path.dirname(os.path.abspath(__file__))
    parent_path = os.path.dirname(current_path)
    
    response = client.get(f"/api/browse?path={current_path}")
    # The "Up" button/card should point to parent_path
    assert f'hx-get="/api/browse?path={parent_path}"' in response.text
