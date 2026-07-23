"""
Role-based permissions for EkSeSreshtha API
"""
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied


class RoleBasedPermission(permissions.BasePermission):
    """
    Base class for role-based permissions.
    Checks user role from JWT token or User model.
    """
    
    def get_user_role(self, request):
        """Get user role from request"""
        # First try to get from JWT token
        if hasattr(request, 'auth') and request.auth:
            # JWT token payload
            user_type = request.auth.get('user_type')
            role_id = request.auth.get('role_id')
            if user_type:
                return user_type
            if role_id:
                return role_id
        
        # Fallback to authenticated user
        if hasattr(request, 'user') and request.user and request.user.is_authenticated:
            if hasattr(request.user, 'role') and request.user.role:
                return request.user.role.role_code or request.user.role_id
            return request.user.role_id
        
        return None
    
    def get_user_id(self, request):
        """Get user ID from request"""
        if hasattr(request, 'auth') and request.auth:
            return request.auth.get('user_id')
        if hasattr(request, 'user') and request.user and request.user.is_authenticated:
            return request.user.id
        return None


class IsSuperAdmin(RoleBasedPermission):
    """Allow only SuperAdmin (RoleId=1)"""
    
    def has_permission(self, request, view):
        role = self.get_user_role(request)
        return role == 1 or role == 'SuperAdmin'


class IsRegionalAdmin(RoleBasedPermission):
    """Allow only RegionalAdmin (RoleId=2)"""
    
    def has_permission(self, request, view):
        role = self.get_user_role(request)
        return role == 2 or role == 'RegionalAdmin'


class IsTeacher(RoleBasedPermission):
    """Allow only Teacher (RoleId=3 / Type=3)"""
    
    def has_permission(self, request, view):
        role = self.get_user_role(request)
        return role == 3 or role == 'Teacher'


class IsSuperAdminOrRegionalAdmin(RoleBasedPermission):
    """Allow SuperAdmin (1) or RegionalAdmin (2)"""
    
    def has_permission(self, request, view):
        role = self.get_user_role(request)
        return role in [1, 2, 'SuperAdmin', 'RegionalAdmin']


class IsSuperAdminOrTeacher(RoleBasedPermission):
    """Allow SuperAdmin (1) or Teacher (3)"""
    
    def has_permission(self, request, view):
        role = self.get_user_role(request)
        return role in [1, 3, 'SuperAdmin', 'Teacher']


class IsRegionalAdminOrTeacher(RoleBasedPermission):
    """Allow RegionalAdmin (2) or Teacher (3)"""
    
    def has_permission(self, request, view):
        role = self.get_user_role(request)
        return role in [2, 3, 'RegionalAdmin', 'Teacher']


class IsAnyAuthenticatedUser(RoleBasedPermission):
    """Allow any authenticated user (all roles)"""
    
    def has_permission(self, request, view):
        return bool(
            self.get_user_role(request) or 
            (hasattr(request, 'user') and request.user and request.user.is_authenticated)
        )


# Convenience mapping for view decorators
ROLE_PERMISSIONS = {
    'superadmin': [IsSuperAdmin],
    'regionaladmin': [IsRegionalAdmin],
    'teacher': [IsTeacher],
    'superadmin_regionaladmin': [IsSuperAdminOrRegionalAdmin],
    'superadmin_teacher': [IsSuperAdminOrTeacher],
    'regionaladmin_teacher': [IsRegionalAdminOrTeacher],
    'any_authenticated': [IsAnyAuthenticatedUser],
}


def get_permissions_for_role(role_key):
    """Get permission classes for a role key"""
    return ROLE_PERMISSIONS.get(role_key, [IsAnyAuthenticatedUser])