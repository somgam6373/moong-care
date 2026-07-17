from fastapi import FastAPI

app = FastAPI(title="MoongCare Server")


@app.get("/health")
def health():
    return {"status": "ok"}
