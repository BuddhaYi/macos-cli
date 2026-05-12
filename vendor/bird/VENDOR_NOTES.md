# bird (vendored - upstream deleted)

**Source**: copied from `~/.npm-global/lib/node_modules/@steipete/bird/` v0.8.0

The original GitHub repo `steipete/bird` was **removed from GitHub**.
The published npm tarball at `@steipete/bird` is the only remaining canonical source.
We bundle the entire installed npm package (incl. compiled `dist/` and `node_modules/`)
so the project keeps working offline regardless of npm registry state.

There is **no TypeScript source** — only compiled `dist/index.js`.

To "upgrade":
1. `npm i -g @steipete/bird@<new-version>` (if a new one is published)
2. `cp -R ~/.npm-global/lib/node_modules/@steipete/bird/* vendor/bird/`
