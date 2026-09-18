export const CUSTOMER = "customer";
export const SUPPORT_AGENT = "support_agent";
export const MANAGER = "manager";
export const ADMINISTRATOR = "administrator";

export const STAFF_ROLES = [SUPPORT_AGENT, MANAGER, ADMINISTRATOR];

let permissionsCache = {};

export function setPermissionsCache(cache) {
  permissionsCache = cache || {};
}

export function hasPermission(role, permission) {
  if (!role || !permission) return false;
  const rolePerms = permissionsCache[role] || [];
  return rolePerms.includes(permission);
}

// `permission` may be a single permission string or an array (OR
// semantics — matches the backend's own require_any_permission()).
// The one place both the sidebar nav and ProtectedRoute should resolve
// "can this role reach this page" from, so they can never drift apart.
export function isPermitted(role, permission) {
  if (Array.isArray(permission)) {
    return permission.some((p) => hasPermission(role, p));
  }
  return hasPermission(role, permission);
}
