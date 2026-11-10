from fastapi import FastAPI

app = FastAPI()

@app.get("/api/test")
def test_endpoint():
    return {"status": "ok", "message": "FastAPI serverless function works on Vercel!"}
