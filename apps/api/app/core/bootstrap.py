import asyncio
from app.db.session import async_session_maker
from sqlalchemy.future import select
from app.modules.identity.models import Role, Permission, RolePermission
import app.modules.organization.models # Ensure all models are loaded in SQLAlchemy registry

# Definition of system roles and their permissions
SYSTEM_ROLES = {
    "OWNER": [
        "organization.read",
        "organization.update",
        "organization.members.read",
        "organization.members.invite",
        "organization.members.remove",
        "organization.roles.manage",
        "resource.upload",
        "resource.read",
        "resource.download",
        "resource.delete"
    ],
    "ADMIN": [
        "organization.read",
        "organization.update",
        "organization.members.read",
        "organization.members.invite",
        "resource.upload",
        "resource.read",
        "resource.download",
        "resource.delete"
    ],
    "INSTRUCTOR": [
        "organization.read",
        "organization.members.read",
        "resource.upload",
        "resource.read",
        "resource.download"
    ],
    "MEMBER": [
        "organization.read",
        "resource.read",
        "resource.download"
    ]
}

async def seed_rbac():
    async with async_session_maker() as session:
        try:
            # Upsert Permissions
            all_permissions = set()
            for perms in SYSTEM_ROLES.values():
                all_permissions.update(perms)
                
            db_permissions = {}
            for perm_name in all_permissions:
                result = await session.execute(select(Permission).where(Permission.name == perm_name))
                perm = result.scalars().first()
                if not perm:
                    perm = Permission(name=perm_name, description=f"Permission for {perm_name}")
                    session.add(perm)
                db_permissions[perm_name] = perm
                
            await session.commit()
            
            # Re-fetch permissions to get IDs
            for perm_name, perm in db_permissions.items():
                if not perm.id:
                    result = await session.execute(select(Permission).where(Permission.name == perm_name))
                    db_permissions[perm_name] = result.scalars().first()
            
            # Upsert Roles and RolePermissions
            for role_name, permissions in SYSTEM_ROLES.items():
                result = await session.execute(select(Role).where(Role.name == role_name))
                role = result.scalars().first()
                if not role:
                    role = Role(name=role_name, description=f"System role: {role_name}")
                    session.add(role)
                    await session.flush()
                
                # Update role permissions deterministically
                result = await session.execute(select(RolePermission).where(RolePermission.role_id == role.id))
                existing_role_perms = result.scalars().all()
                existing_perm_ids = {rp.permission_id for rp in existing_role_perms}
                
                target_perm_ids = {db_permissions[p].id for p in permissions}
                
                # Delete removed
                for rp in existing_role_perms:
                    if rp.permission_id not in target_perm_ids:
                        await session.delete(rp)
                        
                # Add missing
                for p_id in target_perm_ids:
                    if p_id not in existing_perm_ids:
                        session.add(RolePermission(role_id=role.id, permission_id=p_id))
                        
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise e

if __name__ == "__main__":
    asyncio.run(seed_rbac())

