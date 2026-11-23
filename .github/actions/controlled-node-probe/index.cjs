const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
assert.equal(process.arch, process.env.EXPECTED_ARCH);
assert.match(process.version, /^v24\./);
fs.writeFileSync(path.join(process.env.RUNNER_TEMP, 'controlled-node.json'),
  JSON.stringify({arch: process.arch, platform: process.platform, version: process.version, executable: process.execPath}));
