"""Navigation API and browser explorer smoke checks."""
from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)

def test_moon_is_default_view():
    response=client.get("/explorer")
    assert response.status_code==200
    assert "Explore the Moon" in response.text

def test_moon_sites():
    response=client.get("/exploration/sites?body=moon")
    assert response.status_code==200
    sites=response.json()["sites"]
    assert len(sites)>=6
    assert any(s["name"]=="Tranquility Base" for s in sites)
    assert all(s["similarity_percent"] is None for s in sites)

def test_mars_sites():
    response=client.get("/exploration/sites?body=mars")
    assert response.status_code==200
    assert any(s["name"]=="Jezero Crater" for s in response.json()["sites"])

def test_assets():
    for name in ("explorer.js","explorer.css"):
        assert client.get("/explorer-assets/"+name).status_code==200

def test_no_invented_analogs():
    assert client.get("/analogs?target=moon").json()==[]
