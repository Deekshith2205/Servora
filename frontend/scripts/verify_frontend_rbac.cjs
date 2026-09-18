const fs = require('fs');
const path = require('path');
const { parse } = require('@babel/parser');
const traverse = require('@babel/traverse').default;

const appJsxPath = path.join(__dirname, '../src/App.jsx');
const code = fs.readFileSync(appJsxPath, 'utf8');

const ast = parse(code, {
  sourceType: 'module',
  plugins: ['jsx']
});

let tabsConfig = null;

traverse(ast, {
  VariableDeclarator(path) {
    if (path.node.id.name === 'TABS') {
      tabsConfig = path.node.init;
    }
  }
});

if (!tabsConfig) {
  console.error("Could not find TABS in App.jsx");
  process.exit(1);
}

const tabs = {};
tabsConfig.properties.forEach(prop => {
  const key = prop.key.name || prop.key.value;
  let perm = null;
  prop.value.properties.forEach(p => {
    if (p.key.name === 'permission') {
      if (p.value.type === 'StringLiteral') {
        perm = p.value.value;
      } else if (p.value.type === 'ArrayExpression') {
        perm = p.value.elements.map(e => e.value);
      }
    }
  });
  tabs[key] = perm;
});

// Deterministically parse permissions from authoritative backend source
const permissionsPyPath = path.join(__dirname, '../../backend/app/auth/permissions.py');
const permissionsPyCode = fs.readFileSync(permissionsPyPath, 'utf8');

function extractSet(name) {
  const match = permissionsPyCode.match(new RegExp(`${name}:\\s*set\\[str\\]\\s*=\\s*{([\\s\\S]*?)\n}`));
  if (!match) return [];
  const elements = match[1].match(/"([^"]+)"/g) || [];
  return elements.map(s => s.replace(/"/g, ''));
}

const customerPerms = extractSet('_CUSTOMER_PERMISSIONS');
const agentPerms = extractSet('_SUPPORT_AGENT_PERMISSIONS');
const managerPerms = extractSet('_MANAGER_PERMISSIONS');
const adminOnlyPerms = extractSet('_ADMIN_ONLY_PERMISSIONS');

const adminPerms = [...new Set([...customerPerms, ...agentPerms, ...managerPerms, ...adminOnlyPerms])];

const ROLE_PERMISSIONS = {
  customer: customerPerms,
  support_agent: agentPerms,
  manager: managerPerms,
  administrator: adminPerms
};

function hasPermission(role, permission) {
  if (!role || !ROLE_PERMISSIONS[role]) return false;
  return ROLE_PERMISSIONS[role].includes(permission);
}

function getVisibleTabs(role) {
  return Object.keys(tabs).filter(key => {
    const perm = tabs[key];
    if (Array.isArray(perm)) {
      return perm.some(p => hasPermission(role, p));
    }
    return hasPermission(role, perm);
  });
}

const customerTabs = getVisibleTabs('customer');
const agentTabs = getVisibleTabs('support_agent');
const adminTabs = getVisibleTabs('administrator');

console.log("Customer tabs:", customerTabs);
console.log("Agent tabs:", agentTabs);
console.log("Admin tabs:", adminTabs);

// Navigation assertions
if (!customerTabs.includes('chat')) {
  console.error("Customer should see chat");
  process.exit(1);
}
if (customerTabs.includes('dashboard_omni') || customerTabs.includes('settings')) {
  console.error("Customer should NOT see staff-only tabs");
  process.exit(1);
}
if (agentTabs.includes('dashboard_omni')) {
  console.error("Support agent should NOT see dashboard_omni (requires view_analytics)");
  process.exit(1);
}
if (!adminTabs.includes('settings')) {
  console.error("Administrator should see settings");
  process.exit(1);
}

console.log("Navigation RBAC logic test passed!");
