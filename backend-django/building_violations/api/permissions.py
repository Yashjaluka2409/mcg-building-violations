from rest_framework.permissions import BasePermission

from ..models import Role
from ..services import access

MANAGEMENT_ROLES = access.MANAGEMENT_ROLES


def role_of(user):
    prof = getattr(user, "bvms_profile", None)
    return prof.role if prof and prof.active else None


class HasOfficerProfile(BasePermission):
    message = "No active officer profile for this module."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and role_of(request.user))


class IsModuleAdmin(BasePermission):
    def has_permission(self, request, view):
        return role_of(request.user) in MANAGEMENT_ROLES


class HasPerm(BasePermission):
    """Use as HasPerm.of("PLANS_MANAGE") - checks the admin-configurable permission matrix
    (role defaults + per-officer overrides; management roles always pass)."""
    codes: tuple = ()
    message = "You do not have the required permission."

    @classmethod
    def of(cls, *codes):
        return type("HasPerm_" + "_".join(codes), (cls,), {"codes": codes, "message": f"Requires permission: {', '.join(codes)}"})

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and role_of(request.user)):
            return False
        perms = access.permissions_for(request.user)
        return any(c in perms for c in self.codes)


class RoleIn(BasePermission):
    """Legacy helper; prefer HasPerm."""
    roles: tuple = ()

    @classmethod
    def of(cls, *roles):
        return type("RoleIn_" + "_".join(roles), (cls,), {"roles": roles})

    def has_permission(self, request, view):
        r = role_of(request.user)
        return r in self.roles or r in MANAGEMENT_ROLES
