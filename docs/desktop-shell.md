# OMERTAOS Desktop Shell

## Purpose

`console/desktop-shell/` is an optional native presentation client built with Tauri, React, TypeScript, and Vite. It gives OMERTAOS an OS-like application surface while keeping `console/` as the canonical presentation owner.

The Web Console owns the mature management routes and workflows. The Desktop Shell embeds that Console, opens it in the default browser, reports local service health, and provides lightweight native navigation. It deliberately does not duplicate Next.js pages.

## Running it

Start the normal OMERTAOS services first so ports 3000, 8000, and 8080 are available. Then:

```bash
cd console/desktop-shell
npm install
npm run tauri:dev
```

For a browser-only UI preview, use `npm run dev` and open `http://localhost:1420`. Validate production assets with `npm run typecheck` and `npm run build`.

## Dependencies

- Node.js 22.23.2 and npm 10.9.8
- Rust stable and Cargo
- Tauri 2 platform prerequisites
- Windows: Microsoft C++ Build Tools and WebView2
- Linux: WebKitGTK and the distribution packages required by Tauri

## Runtime environments

- **Local:** services resolve through `localhost`; this is the default.
- **WSL:** run the UI on Windows and publish the WSL services to localhost. Do not use Docker service DNS names from the desktop process.
- **Linux:** install WebKitGTK prerequisites and run the same npm/Tauri commands.
- **Bare Metal:** provide local or explicitly configured service URLs through the `VITE_OMERTA_*` variables.

Settings may be edited inside the shell and are stored locally in versioned `localStorage`. They are not persisted to Control or Gateway.

## Security limitations

- Terminal is a non-executing placeholder.
- Files is a non-reading, non-writing placeholder.
- No Tauri filesystem plugin is enabled.
- No Tauri shell/command execution plugin is enabled.
- External URL opening is scoped to the local Console, Gateway, and Control origins.
- Service health checks are read-only and gracefully report offline services.

Real command execution and file access must wait for signed Runtime capabilities, policy evaluation, sandbox enforcement, and auditable APIs.

## Roadmap

The recommended next phase is a capability-mediated desktop bridge: typed Gateway contracts for agent inventory and service health, followed by narrowly scoped Runtime grants for terminal and file workflows. Native notifications, deep links, signed updates, and bundle icons can follow after those security contracts exist.
