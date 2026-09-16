export const CUSTOMER = "customer";
export const SUPPORT_AGENT = "support_agent";
export const MANAGER = "manager";
export const ADMINISTRATOR = "administrator";

let permissionsCache = {};

export function setPermissionsCache(cache) {
  permissionsCache = cache || {};
}

export function hasPermission(role, permission) {
  if (!role || !permission) return false;
  const rolePerms = permissionsCache[role] || [];
  return rolePerms.includes(permission);
}
