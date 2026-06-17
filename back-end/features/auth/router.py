from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from features.auth import service
from features.auth.schema import LoginRequest, MessageResponse, RegisterRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=MessageResponse, status_code=201)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    return await service.register_user(request, db)


@router.get("/verify-email", response_model=MessageResponse)
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    return await service.verify_email(token, db)


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(email: str, db: AsyncSession = Depends(get_db)):
    return await service.resend_verification_email(email, db)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await service.login_user(request, db)
