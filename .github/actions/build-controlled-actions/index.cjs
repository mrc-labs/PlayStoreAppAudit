'use strict';
const {spawnSync} = require('node:child_process');
const path = require('node:path');
if (process.versions.node.split('.')[0] !== '24') throw new Error('Native Node24 required');
const result = spawnSync('python', ['.github/scripts/build_controlled_actions.py', '--work', path.join(process.env.RUNNER_TEMP, 'controlled-actions-' + process.env.GITHUB_RUN_ID)], {stdio: 'inherit', env: {...process.env, PSAA_NODE: process.execPath}});
if (result.error) throw result.error;
process.exit(result.status ?? 1);
