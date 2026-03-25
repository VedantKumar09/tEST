const git = require('isomorphic-git');
const http = require('isomorphic-git/http/node/index.js');
const fs = require('fs');
const path = require('path');
const globby = require('globby');

const dir = 'c:/Users/jisha/OneDrive/Desktop/Vedant';
const repoUrl = 'https://github.com/VedantKumar09/tEST.git';
const token = 'YOUR_GITHUB_PAT_HERE';

async function push() {
  console.log('--- Initializing Git ---');
  await git.init({ fs, dir });

  console.log('--- Scanning files (respecting .gitignore) ---');
  // Simple globby to skip the heavy hitters
  const paths = await globby(['**/*', '!.git', '!node_modules', '!venv', '!backend/venv', '!frontend/node_modules', '!data'], {
    cwd: dir,
    dot: true,
    gitignore: true
  });

  console.log(`Adding ${paths.length} files...`);
  for (const filepath of paths) {
    await git.add({ fs, dir, filepath });
  }

  console.log('--- Committing ---');
  await git.commit({
    fs,
    dir,
    author: {
      name: 'Vedant',
      email: 'vedant@mindmesh.ai'
    },
    message: '🚀 Initial push: MindMesh v2 with Hybrid Agentic AI'
  });

  console.log('--- Pushing to GitHub ---');
  await git.push({
    fs,
    http,
    dir,
    remote: 'origin',
    url: repoUrl,
    onAuth: () => ({ username: token, password: '' }), // PAT as username works for GitHub
  });

  console.log('✅ PROJECT SUCCESSFULLY PUSHED TO GITHUB!');
}

push().catch(err => {
  console.error('❌ Git push failed:', err);
  process.exit(1);
});
