from rest_framework.permissions import BasePermission

from ..models import Role

MANAGEMENT_ROLES = (Role.ADMIN, Role.COMMISSIONER, Role.ADDL_COMMISSIONER)


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


class RoleIn(BasePermission):
    """Use as RoleIn.of("JE", "AE") in permission_classes."""
    roles: tuple = ()

    @classmethod
    def of(cls, *roles):
        return type("RoleIn_" + "_".join(roles), (cls,), {"roles": roles})

    def has_permission(self, request, view):
        r = role_of(request.user)
        return r in self.roles or r in MANAGEMENT_ROLES
