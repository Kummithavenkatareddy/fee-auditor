from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://fee-auditor-frontend.vercel.app", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "online", "message": "FastAPI is running cleanly on Vercel!"}

@app.get("/")
def root():
    return {"message": "Fee Auditor Backend running on Vercel"}
