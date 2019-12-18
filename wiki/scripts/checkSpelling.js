const fs = require('fs');
const { spell } = require('markdown-spellcheck').default;

const OPTS = {
  dictionary: {
    language: 'en-us',
  },
  ignoreAcronyms: true,
  ignoreNumbers: true,
  suggestions: true,
}

// Read a file, return a string.
const readFile = (file) => {
  // Check that the file exists and open it. Otherwise just skip.
  if (fs.existsSync(file)) {
    const buf = fs.readFileSync(file, { encoding: 'utf-8' });
    return buf.toString();
  }
}

// Given a top level directory, collects all `.md` files.
const collectMarkdownRecursive = (dir) => {
  const contents = fs.readdirSync(dir);

  let files = contents.map(fileOrDir => {
    // console.log(fileOrDir)
    if (fileOrDir.endsWith('.md')) {
      return `${dir}/${fileOrDir}`;
    } else if (fileOrDir.indexOf('.') === -1) {
      return collectMarkdownRecursive(`${dir}/${fileOrDir}`);
    } else { console.error("Does not match pattern:", fileOrDir); }
  });

  return files;
}

let files = collectMarkdownRecursive('docs/polkadot');
// Do this transformation to put all contents into one array.
files = [].concat(...[].concat(...files));

let collection = new Set();

files.forEach(file => {
  const res = spell(readFile(file), OPTS);
  console.log(res.slice(0, 8))
  res.forEach(({ word }) => {
    if (!collection.has(word)) { collection.add(word); }
  });
})

// console.log(collection)
