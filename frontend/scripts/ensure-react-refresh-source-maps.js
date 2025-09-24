#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const baseDir = path.join(
  __dirname,
  '..',
  'node_modules',
  'next',
  'dist',
  'compiled',
  '@next',
  'react-refresh-utils',
  'dist'
);

const targets = [
  {
    filename: 'runtime.js.map',
    source: 'runtime.js',
    dir: baseDir
  },
  {
    filename: 'helpers.js.map',
    source: 'helpers.js',
    dir: path.join(baseDir, 'internal')
  }
];

let hadError = false;

for (const { filename, source, dir } of targets) {
  const targetPath = path.join(dir, filename);
  try {
    if (fs.existsSync(targetPath)) {
      continue;
    }

    const mapContent = JSON.stringify(
      {
        version: 3,
        file: path.basename(source),
        sources: [path.basename(source)],
        names: [],
        mappings: ''
      },
      null,
      2
    );

    fs.writeFileSync(targetPath, mapContent + '\n', 'utf8');
  } catch (error) {
    hadError = true;
    console.error(`Failed to create ${filename}:`, error);
  }
}

if (hadError) {
  process.exitCode = 1;
}
