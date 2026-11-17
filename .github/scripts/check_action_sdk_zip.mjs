import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';

const [sdk, output] = process.argv.slice(2);
fs.mkdirSync(output, {recursive: true});
const {createZipUploadStream} = await import(pathToFileURL(path.join(sdk, 'lib/internal/upload/zip.js')));
const rows = [['alpha.txt', Buffer.from('controlled archive8 source consumer\n')],
  ['nested/\u00e1rchive.bin', Buffer.from(Array.from({length: 256}, (_, i) => i))]];
const specification = [];
const expected = {};
for (const [name, body] of rows) {
  const source = path.join(output, 'inputs', name);
  fs.mkdirSync(path.dirname(source), {recursive: true});
  fs.writeFileSync(source, body);
  specification.push({sourcePath: source, destinationPath: name, stats: fs.statSync(source)});
  expected[name] = createHash('sha256').update(body).digest('hex');
}
specification.push({sourcePath: null, destinationPath: 'empty/'});
const stream = await createZipUploadStream(specification);
const chunks = [];
for await (const chunk of stream) chunks.push(chunk);
const archive = Buffer.concat(chunks);
assert.ok(archive.length > 0);
fs.writeFileSync(path.join(output, 'sdk.zip'), archive);
const metadata = JSON.parse(fs.readFileSync(path.join(sdk, 'package.json')));
assert.equal(metadata.version, '6.3.1+psaa.archive8');
fs.writeFileSync(path.join(output, 'expected.json'), JSON.stringify({expected, empty: 'empty/', sdk: metadata.version}));
