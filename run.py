import uvicorn


def run_fastapi_server():
    print("Starting FastAPI server on 0.0.0.0:8384...")
    uvicorn.run(
        "app.api:app",
        host="0.0.0.0",
        port=8384,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    run_fastapi_server()
