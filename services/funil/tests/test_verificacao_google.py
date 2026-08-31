def test_verificacao_do_google_responde_200(client):
    resp = client.get("/google0e78b54775677e95.html")
    assert resp.status_code == 200
    assert (
        resp.content.decode() == "google-site-verification: google0e78b54775677e95.html"
    )
    assert resp["Content-Type"].startswith("text/plain")
