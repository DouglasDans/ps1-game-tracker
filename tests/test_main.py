from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from daemon.main import add_no_store_header


def build_test_app(static_dir) -> FastAPI:
    app = FastAPI()
    app.middleware("http")(add_no_store_header)

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    return app


def test_api_response_has_no_store_header(tmp_path):
    (tmp_path / "index.html").write_text("<html></html>")
    client = TestClient(build_test_app(tmp_path))

    response = client.get("/api/ping")

    assert response.headers["cache-control"] == "no-store"


def test_static_file_response_has_no_store_header(tmp_path):
    (tmp_path / "index.html").write_text("<html></html>")
    (tmp_path / "app.js").write_text("console.log('hi')")
    client = TestClient(build_test_app(tmp_path))

    response = client.get("/app.js")

    assert response.headers["cache-control"] == "no-store"
