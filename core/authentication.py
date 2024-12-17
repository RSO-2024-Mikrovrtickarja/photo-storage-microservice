from typing import Annotated, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from pydantic import BaseModel

from .configuration import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class TokenData(BaseModel):
    id: Optional[str] = None



def verify_access_token(token: str, credentials_exception: HTTPException) -> TokenData:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        if "user_id" not in payload:
            raise credentials_exception
        
        user_id = str(payload["user_id"])
    
        return TokenData(id=user_id)
    except jwt.InvalidTokenError:
        raise credentials_exception
    

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    return verify_access_token(token, credentials_exception)

CurrentUserDependency = Annotated[TokenData, Depends(get_current_user)]
