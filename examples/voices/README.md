# Example: other narration voices

Both folders reuse the stories in `../explainer` and change only the voice. Neural voices need Apple Silicon.

| Folder | Voice | Setup |
|---|---|---|
| `described/` | a voice described in words | `filmwright setup --voice described` |
| `cloned/` | your own voice, from a short recording | `filmwright setup --voice clone`, then the steps below |

## Cloning your own voice

Only clone your own voice, or the voice of someone who has agreed. filmwright records the speaker, asks them to
confirm a consent statement, and saves a consent record tied to that exact recording. Without a matching record a
cloned voice will not run, and nothing in the configuration can turn that check off.

```bash
cd examples/voices/cloned
filmwright voice clone passage                        # the text to read aloud (about 30 seconds)
filmwright voice clone record --speaker "Your Name"   # records it, then asks you to confirm consent
filmwright voice clone check                          # length, level, transcript, consent
filmwright voice clone preview --play                 # hear a sentence in the cloned voice
filmwright build .
```

`voice/` (the sample, its transcript and the consent record) is ignored by git. To remove everything:
`filmwright voice clone forget`.

This example sets `disclosure: end-card`, so each film ends with a short card saying the narration is a cloned
voice used with consent. See [docs/disclosure.md](../../docs/disclosure.md) for the other options.
