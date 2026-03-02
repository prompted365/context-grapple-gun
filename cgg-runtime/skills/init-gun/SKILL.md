---
name: init-gun
description: "[DEPRECATED — use the bootstrap prompt in INSTALL.md] This setup step is now handled by the bootstrap install flow."
user-invocable: true
disable-model-invocation: true
---

# /init-gun (deprecated)

**This command has been absorbed into the CGG bootstrap install flow.**

When the user invokes `/init-gun`, inform them:

> `/init-gun` is no longer needed as a separate step. CGG now uses a single bootstrap prompt that handles the entire installation — including everything `/init-gun` and `/init-cogpr` used to do.
>
> If you've already installed CGG via the bootstrap prompt, you're all set.
>
> If you haven't installed yet, see `INSTALL.md` in the CGG repo for the one-step bootstrap prompt, or paste this into a Claude Code session in your project:
>
> "Install Context Grapple Gun from vendor/context-grapple-gun into this project."
>
> Would you like me to run the full installation now?

If the user confirms, execute the installation steps from the bootstrap flow.
