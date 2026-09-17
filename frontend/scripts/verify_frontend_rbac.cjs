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

// Based on backend/app/auth/permissions.py
const ROLE_PERMISSIONS = {
  customer: ["view_own_tickets", "submit_tickets"],
  support_agent: [
    "view_own_tickets",
    "submit_tickets",
    "view_investigation_board",
    "handle_escalations",
    "manage_knowledge_base",
    "view_customer_conversations"
  ],
  admin: [
    "view_own_tickets",
    "submit_tickets",
    "view_investigation_board",
    "handle_escalations",
    "manage_knowledge_base",
    "manage_users",
    "manage_system_settings",
    "manage_integrations",
    "assign_roles",
    "view_analytics",
    "view_customer_conversations"
  ]
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

console.log("Customer tabs:", customerTabs);
console.log("Agent tabs:", agentTabs);

if (!customerTabs.includes('chat')) {
  console.error("Customer should see chat");
  process.exit(1);
}
if (customerTabs.includes('dashboard_omni')) {
  console.error("Customer should NOT see dashboard_omni");
  process.exit(1);
}
if (!agentTabs.includes('dashboard_omni')) {
  console.error("Support agent should see dashboard_omni");
  process.exit(1);
}

console.log("Navigation RBAC logic test passed!");
