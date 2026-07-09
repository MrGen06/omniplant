from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_me_endpoint_returns_current_user():
    login_resp = client.post(
        "/api/auth/token",
        data={"username": "EMP-1042", "password": "password123"},
    )

    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    me_resp = client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me_resp.status_code == 200
    payload = me_resp.json()
    assert payload["employee_id"] == "EMP-1042"
    assert payload["name"] == "Ramesh"
