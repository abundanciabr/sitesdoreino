def test_healthz_responde_200_ok(client):
    resposta = client.get("/healthz")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}
