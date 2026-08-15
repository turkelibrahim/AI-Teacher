from datetime import timezone
import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from app.core.config import settings
from app.modules.identity.models import User, RefreshToken, AuditLog, Role
from app.modules.identity.repository import IdentityRepository
from app.modules.organization.repository import OrganizationRepository
from app.modules.organization.models import Organization, OrganizationMember, MemberRole
from app.core.exceptions import BadRequestException, UnauthorizedException, NotFoundException
import uuid
import hashlib
import re

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

class IdentityService:
    def __init__(self, identity_repo: IdentityRepository, org_repo: OrganizationRepository):
        self.identity_repo = identity_repo
        self.org_repo = org_repo
        self.session = identity_repo.session

    def get_password_hash(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    def create_access_token(self, subject: str) -> str:
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "exp": expire,
            "iat": now,
            "sub": str(subject),
            "type": "access",
            "jti": str(uuid.uuid4())
        }
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt

    def create_refresh_token_payload(self) -> str:
        return str(uuid.uuid4())

    def hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    async def register_user(self, email: str, password: str, first_name: str = None, last_name: str = None) -> tuple[User, str, str]:
        # Enforce password minimum length manually in service just in case
        if len(password) < settings.PASSWORD_MIN_LENGTH:
            raise BadRequestException(detail=f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters")
            
        # Check existing user
        if await self.identity_repo.get_user_by_email(email):
            raise BadRequestException(detail="Email already registered")
        
        try:
            # Create user
            user = User(
                email=email.strip(),
                email_normalized=email.strip().lower(),
                password_hash=self.get_password_hash(password),
                first_name=first_name,
                last_name=last_name
            )
            user = await self.identity_repo.create_user(user)

            # Create personal organization
            slug_base = re.sub(r'[^a-z0-9]+', '-', user.email_normalized.split('@')[0])
            slug = f"{slug_base}-{str(uuid.uuid4())[:8]}"
            org_name = f"{first_name or 'Personal'} Organization"
            
            org = Organization(
                name=org_name,
                slug=slug,
                organization_type="PERSONAL"
            )
            org = await self.org_repo.create_organization(org)

            # Create membership
            member = OrganizationMember(
                organization_id=org.id,
                user_id=user.id,
                status="ACTIVE"
            )
            member = await self.org_repo.create_membership(member)

            # Assign OWNER role
            role = await self.org_repo.get_role_by_name("OWNER")
            if not role:
                raise Exception("System roles not seeded. Run bootstrap.")

            member_role = MemberRole(member_id=member.id, role_id=role.id)
            await self.org_repo.assign_role_to_member(member_role)

            # Audit Log
            await self.identity_repo.create_audit_log(AuditLog(
                user_id=user.id,
                organization_id=org.id,
                event_type="USER_REGISTERED"
            ))
            
            # Generate initial tokens
            access_token = self.create_access_token(user.id)
            raw_refresh_token = self.create_refresh_token_payload()
            token_hash = self.hash_token(raw_refresh_token)

            rt = RefreshToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
            )
            await self.identity_repo.save_refresh_token(rt)
            
            # Flush everything so if commit fails it catches here, but auto-commit will do it
            await self.session.flush()

            return user, access_token, raw_refresh_token
            
        except Exception as e:
            # If any failure occurs, we bubble it up. session will automatically rollback in FastAPI deps
            raise e

    async def login(self, email: str, password: str, ip_address: str = None, user_agent: str = None) -> tuple[str, str]:
        user = await self.identity_repo.get_user_by_email(email)
        if not user or not self.verify_password(password, user.password_hash):
            if user:
                await self.identity_repo.create_audit_log(AuditLog(user_id=user.id, event_type="USER_LOGIN_FAILED"))
                await self.session.commit()
            raise UnauthorizedException(detail="Incorrect email or password")
        
        if not user.is_active:
            raise UnauthorizedException(detail="Inactive user")

        access_token = self.create_access_token(user.id)
        raw_refresh_token = self.create_refresh_token_payload()
        token_hash = self.hash_token(raw_refresh_token)

        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        rt = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent
        )
        await self.identity_repo.save_refresh_token(rt)
        
        user.last_login_at = datetime.now(timezone.utc)

        await self.identity_repo.create_audit_log(AuditLog(user_id=user.id, event_type="USER_LOGIN_SUCCESS"))
        await self.session.flush()
        
        return access_token, raw_refresh_token

    async def refresh_token(self, raw_refresh_token: str, ip_address: str = None, user_agent: str = None) -> tuple[str, str]:
        token_hash = self.hash_token(raw_refresh_token)
        token_record = await self.identity_repo.get_refresh_token(token_hash)
        
        if not token_record:
            raise UnauthorizedException(detail="Invalid refresh token")
        
        if token_record.revoked_at:
            await self.identity_repo.create_audit_log(AuditLog(user_id=token_record.user_id, event_type="REFRESH_TOKEN_REUSED"))
            await self.session.commit()
            raise UnauthorizedException(detail="Token revoked")
        
        if token_record.expires_at < datetime.now(timezone.utc):
            raise UnauthorizedException(detail="Token expired")
            
        user = await self.identity_repo.get_user_by_id(token_record.user_id)
        if not user or not user.is_active:
            raise UnauthorizedException(detail="Inactive user")

        # Revoke old token
        token_record.revoked_at = datetime.now(timezone.utc)

        # Issue new token
        new_access_token = self.create_access_token(user.id)
        new_raw_refresh = self.create_refresh_token_payload()
        new_token_hash = self.hash_token(new_raw_refresh)

        rt = RefreshToken(
            user_id=user.id,
            token_hash=new_token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            ip_address=ip_address,
            user_agent=user_agent
        )
        await self.identity_repo.save_refresh_token(rt)
        await self.session.flush()
        
        # Point OLD token to NEW token
        token_record.replaced_by_token_id = rt.id
        
        await self.identity_repo.create_audit_log(AuditLog(user_id=user.id, event_type="REFRESH_TOKEN_ROTATED"))
        await self.session.flush()

        return new_access_token, new_raw_refresh

    async def logout(self, raw_refresh_token: str) -> None:
        token_hash = self.hash_token(raw_refresh_token)
        token_record = await self.identity_repo.get_refresh_token(token_hash)
        if token_record and not token_record.revoked_at:
            token_record.revoked_at = datetime.now(timezone.utc)
            await self.identity_repo.create_audit_log(AuditLog(user_id=token_record.user_id, event_type="USER_LOGOUT"))
            await self.session.flush()



