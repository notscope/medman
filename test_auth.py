
from fastapi.testclient import TestClient
from web_app import app, state
import os

client = TestClient(app)

def test_redirect_to_login():
    # Attempt to access protected route without session
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

def test_login_success():
    # Login with default credentials
    response = client.post("/login", data={"username": "admin", "password": "medman"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    
    # Check if session cookie is set (TestClient handles this internally usually, but we can verify subsequent requests)
    # Re-use cookies for next request
    response = client.get("/", cookies=response.cookies)
    assert response.status_code == 200
    assert "admin" in response.text  # User name should be in header

def test_login_failure():
    response = client.post("/login", data={"username": "admin", "password": "wrongpassword"})
    assert response.status_code == 200
    assert "Invalid credentials" in response.text

def test_logout():
    # Login first
    login_response = client.post("/login", data={"username": "admin", "password": "medman"}, follow_redirects=False)
    cookies = login_response.cookies
    
    # Logout
    logout_response = client.get("/logout", cookies=cookies, follow_redirects=False)
    assert logout_response.status_code == 303
    assert logout_response.headers["location"] == "/login"
    
    # Verify access denied after logout
    # Note: TestClient cookies might persist unless manually cleared or handled, 
    # but the server-side session should be cleared.
    # However, Starlette SessionMiddleware stores data IN the cookie. 
    # Logout clears the session dict, which means the response cookie will be empty/different.
    # We should use the cookies from the logout response.
    
    response = client.get("/", cookies=logout_response.cookies, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
