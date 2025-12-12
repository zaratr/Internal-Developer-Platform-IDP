from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings


bearer_scheme = HTTPBearer()


class Role:
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    TEAM_ADMIN = "TEAM_ADMIN"
    DEVELOPER = "DEVELOPER"


class UserContext:
    def __init__(self, username: str, role: str, team_id: Optional[int]):
        self.username = username
        self.role = role
        self.team_id = team_id


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> UserContext:
    token = credentials.credentials
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        team_id: Optional[int] = payload.get("team_id")
        if username is None or role is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return UserContext(username=username, role=role, team_id=team_id)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def create_access_token(subject: str, role: str, team_id: Optional[int]) -> str:
    settings = get_settings()
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode = {"exp": expire, "sub": subject, "role": role, "team_id": team_id}
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def require_roles(*roles: str):
    async def checker(user: UserContext = Depends(get_current_user)) -> UserContext:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return checker
