const fs = require('fs');
const path = require('path');

function walkDir(dir, ext) {
  let results = [];
  const list = fs.readdirSync(dir);
  list.forEach(function(file) {
    file = path.join(dir, file);
    const stat = fs.statSync(file);
    if (stat && stat.isDirectory()) { 
      results = results.concat(walkDir(file, ext));
    } else if (file.endsWith(ext)) { 
      results.push(file);
    }
  });
  return results;
}

const frontendDir = path.join(__dirname, '../src');
const backendDir = path.join(__dirname, '../../backend/app');

const frontendFiles = walkDir(frontendDir, '.jsx').concat(walkDir(frontendDir, '.js'));
const backendFiles = walkDir(backendDir, '.py');

const frontendPerms = new Set();
const backendPerms = new Set();

frontendFiles.forEach(file => {
  const content = fs.readFileSync(file, 'utf8');
  // Specifically match ONLY <Can permission="xxx"> as per instructions for #209 actions
  const matches = content.matchAll(/<Can[^>]+permission="([a-z_]+)"/g);
  for (const match of matches) {
    frontendPerms.add(match[1]);
  }
});

backendFiles.forEach(file => {
  const content = fs.readFileSync(file, 'utf8');
  const matches = content.matchAll(/require_permission\("([a-z_]+)"\)/g);
  for (const match of matches) {
    backendPerms.add(match[1]);
  }
  const anyMatches = content.matchAll(/require_any_permission\((.*?)\)/g);
  for (const match of anyMatches) {
    const perms = match[1].match(/"([a-z_]+)"/g);
    if (perms) {
      perms.forEach(p => backendPerms.add(p.replace(/"/g, '')));
    }
  }
  // also allow has_permission/has_any_permission used in auth dependency for dynamic roles
  const hasMatches = content.matchAll(/has_permission\([^,]+,\s*"([a-z_]+)"\)/g);
  for (const match of hasMatches) {
    backendPerms.add(match[1]);
  }
});

let failed = false;

frontendPerms.forEach(fp => {
  if (!backendPerms.has(fp)) {
    console.error(`ERROR: Frontend uses permission '${fp}' but it was not found in any backend requirement.`);
    failed = true;
  } else {
    console.log(`OK: Frontend permission '${fp}' matched in backend.`);
  }
});

if (failed) {
  process.exit(1);
} else {
  console.log("Cross-check passed: All frontend permissions exist in the backend.");
}
