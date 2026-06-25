import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()


def run_fastapi_server():
    ssl_cert = os.getenv("SSL_CERT_PATH")
    ssl_key = os.getenv("SSL_KEY_PATH")

    ssl_kwargs = {}
    if ssl_cert and ssl_key:
        ssl_kwargs["ssl_certfile"] = ssl_cert
        ssl_kwargs["ssl_keyfile"] = ssl_key
        print(f"Starting FastAPI server on 0.0.0.0:8384 with SSL...")
    else:
        print("Starting FastAPI server on 0.0.0.0:8384...")

    uvicorn.run(
        "app.api:app",
        host="0.0.0.0",
        port=8384,
        reload=True,
        log_level="info",
        **ssl_kwargs,
    )


if __name__ == "__main__":
    run_fastapi_server()
