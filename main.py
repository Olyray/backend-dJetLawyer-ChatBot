from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, chat, chatbot, dashboard
from app.core.config import settings
from app.core.deps import setup_rate_limiter
from fastapi.responses import JSONResponse

app = FastAPI(title=settings.PROJECT_NAME, debug=True)

@app.on_event("startup")
async def startup():
    await setup_rate_limiter()

def get_allowed_origins():
    if settings.ENVIRONMENT == "production":
        return [
            "https://chat.djetlawyer.com",
            "https://www.djetlawyer.com"
        ]
    elif settings.ENVIRONMENT == "staging":
        return [
            "https://staging-chatbotfrontend-1f183cbd5331.herokuapp.com/"
        ]
    else:  # development
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000"
        ]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}/chat", tags=["chat"])
app.include_router(chatbot.router, prefix=f"{settings.API_V1_STR}/chatbot", tags=["chatbot"])
app.include_router(dashboard.router, prefix=f"{settings.API_V1_STR}/dashboard", tags=["dashboard"])


@app.get("/")
async def root():
    return JSONResponse(content={"message": "Welcome to dJetLawyer Chatbot"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)