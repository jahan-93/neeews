import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.security import create_access_token, hash_password, verify_password
from features.auth.model import EmailVerificationToken, User
from features.auth.schema import LoginRequest, RegisterRequest

_mail_config = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
)


async def register_user(request: RegisterRequest, db: AsyncSession) -> dict:
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 이메일입니다.",
        )

    user = User(
        email=request.email,
        hashed_password=hash_password(request.password),
    )
    db.add(user)
    await db.flush()

    token = _create_verification_token(user.id)
    db.add(token)
    await db.commit()

    await _send_verification_email(request.email, token.token)

    return {"message": "회원가입이 완료되었습니다. 이메일을 확인하여 인증을 완료해주세요."}


async def verify_email(token: str, db: AsyncSession) -> dict:
    result = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.token == token)
    )
    record = result.scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="유효하지 않은 인증 토큰입니다.",
        )

    if record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        await db.delete(record)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="만료된 인증 토큰입니다. 인증 메일을 다시 요청해주세요.",
        )

    user_result = await db.execute(select(User).where(User.id == record.user_id))
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다.",
        )

    if user.is_verified:
        await db.delete(record)
        await db.commit()
        return {"message": "이미 인증된 이메일입니다."}

    user.is_verified = True
    await db.delete(record)
    await db.commit()

    return {"message": "이메일 인증이 완료되었습니다. 로그인해주세요."}


async def resend_verification_email(email: str, db: AsyncSession) -> dict:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # 존재 여부를 노출하지 않기 위해 동일 메시지 반환
        return {"message": "인증 메일이 발송되었습니다."}

    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 인증된 이메일입니다.",
        )

    # 기존 토큰 삭제
    existing = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    for record in existing.scalars().all():
        await db.delete(record)

    token = _create_verification_token(user.id)
    db.add(token)
    await db.commit()

    await _send_verification_email(email, token.token)

    return {"message": "인증 메일이 발송되었습니다."}


async def login_user(request: LoginRequest, db: AsyncSession) -> dict:
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="이메일 인증이 필요합니다. 이메일을 확인해주세요.",
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    return {"access_token": access_token, "token_type": "bearer"}


def _create_verification_token(user_id: int) -> EmailVerificationToken:
    return EmailVerificationToken(
        user_id=user_id,
        token=str(uuid.uuid4()),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )


async def _send_verification_email(email: str, token: str) -> None:
    verification_url = f"{settings.APP_URL}/auth/verify-email?token={token}"

    message = MessageSchema(
        subject="[Neeews] 이메일 인증을 완료해주세요",
        recipients=[email],
        body=f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #333;">이메일 인증</h2>
            <p>Neeews에 가입해주셔서 감사합니다.</p>
            <p>아래 버튼을 클릭하여 이메일 인증을 완료해주세요.</p>
            <a href="{verification_url}"
               style="display: inline-block; padding: 12px 24px; background-color: #4F46E5;
                      color: white; text-decoration: none; border-radius: 6px; margin: 16px 0;">
                이메일 인증하기
            </a>
            <p style="color: #888; font-size: 14px;">이 링크는 24시간 후에 만료됩니다.</p>
            <p style="color: #888; font-size: 14px;">본인이 요청하지 않은 경우 이 메일을 무시해주세요.</p>
        </div>
        """,
        subtype=MessageType.html,
    )

    fm = FastMail(_mail_config)
    await fm.send_message(message)
