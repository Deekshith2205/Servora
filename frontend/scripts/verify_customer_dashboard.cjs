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

let defaultTabs = null;

traverse(ast, {
  VariableDeclarator(path) {
    if (path.node.id.name === 'DEFAULT_TABS') {
      defaultTabs = {};
      path.node.init.properties.forEach(prop => {
        defaultTabs[prop.key.name || prop.key.value] = prop.value.value;
      });
    }
  }
});

if (!defaultTabs) {
  console.error("Could not find DEFAULT_TABS in App.jsx");
  process.exit(1);
}

if (defaultTabs.customer !== 'dashboard_customer') {
  console.error("Customer default tab should be dashboard_customer");
  process.exit(1);
}

console.log("Customer default landing tab logic test passed!");
