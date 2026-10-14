# Security policy

## Reporting a vulnerability

Please report security problems privately through a
[GitHub security advisory](https://github.com/dassjaylabs/filmwright/security/advisories/new), not in a public
issue. Include what you found, how to reproduce it, and the version (`filmwright --version`). You should hear
back within a week.

## What filmwright handles that is sensitive

- **Signed-in sessions.** Demo recordings can use a saved browser session (`auth.json`). It stays in your run
  folder, is never printed, and `.gitignore` excludes it. Never commit or share it.
- **Voice samples.** A cloned voice is made from a recording of a real person. filmwright refuses to clone
  without a consent record tied to that exact recording. Keep samples and consent records private.
- **Where it runs.** Everything (browser, voices, music, encoding) runs locally. Nothing is uploaded.
- **Target sites.** The scenario runner only visits hosts listed in `allow_hosts` and defaults to localhost.
  Point it at test environments, not production systems you don't own.
