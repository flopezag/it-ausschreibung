# README.template.md — Project README Template

<!--
  AI INSTRUCTIONS:
  This file is the base template for generating the README.md for the user’s project.
  During bootstrap:
  1. Read project.config.md to retrieve the name, description, author and licence.
  2. Generate README.md in the language chosen by the user (EN / ES / Bilingual).
  3. Replace all placeholders with the actual values.
  4. Generate the Table of Contents automatically based on the sections present.
  5. Delete this README.template.md file once the README.md has been generated.
  6. On every /ship, update README.md with the changes from the release.
-->

---

# [Project Name]

> [One-line description of the project]

<!-- TOC: Generate automatically based on the sections below, in the chosen language -->
## 📑 Table of Contents

- [About](#about)
- [Requirements](#requirements)
- [Installation](#installation)
- [Publishing](#publishing)
- [How to run](#usage)
- [How to stop](#stop)
- [Project structure](#structure)
- [Changelog](#changelog)
- [License](#license)

---

<a name="about"></a>
## 📌 About

<!-- Describe what the project does, who it's for, and what problem it solves. 2-4 sentences. -->

[Project Name] is a [type of application] that [main purpose and key benefit].

**Built with:** [Main technologies from ARCHITECTURE.md]

---

<a name="requirements"></a>
## 🧰 Requirements

<!-- List what the user needs installed before running the project. -->

- [e.g. Python 3.11+ / Node.js 20+ / Java 17+]
- [e.g. pip / npm / maven]
- [Any other dependency]

---

<a name="installation"></a>
## ⚙️ Installation

<!-- Step-by-step instructions to get the project running for the first time. -->

### 🐍 Python

#### Local Installation (Development)

**Recommended — [uv](https://docs.astral.sh/uv/):**
```bash
# 1. Create the virtual environment (.venv)
uv venv
.venv\Scripts\activate     # Windows
source .venv/bin/activate  # macOS / Linux

# 2. Install the project in editable mode
uv pip install -e .
```

**Alternative — pip:**
```bash
# 1. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate     # Windows
source venv/bin/activate  # macOS / Linux

# 2. Install the project in editable mode
pip install -e .
```

#### Remote Installation (Git)
```bash
pip install git+https://github.com/USUARIO/REPO.git
```

### 🟢 Node.js (npm)

#### Local Installation
```bash
# Install dependencies
npm install
```

#### Remote Installation (Git)
```bash
npm install git+https://github.com/USUARIO/REPO.git
```

### 🦀 Rust / Tauri v2 (Desktop App)

<!-- AI: keep this section only if the project is a native desktop app (Tauri). Delete it otherwise. -->

#### Requirements
- [Rust](https://rustup.rs) (stable) and the Tauri v2 system dependencies (WebView2 on Windows, WebKitGTK on Linux; nothing extra on macOS).
- Node.js 20+ if the frontend uses npm.

#### Development
```bash
npm install            # frontend dependencies, if any
npm run tauri dev      # or cargo tauri dev
```

---

<a name="publishing"></a>
## 🚀 Publishing

<!-- Instructions for publishing the package to official package registries. -->

### 🐍 Python (PyPI)
```bash
# 1. Build the distribution packages
python -m build

# 2. Upload to PyPI
python -m twine upload dist/*
```

### 🟢 Node.js (npm Registry)
```bash
# 1. Login to npm
npm login

# 2. Publish to npm registry
npm publish
```

### 🦀 Rust / Tauri v2 (Desktop App)

<!-- AI: keep only for native desktop apps. Store/marketplace submission: see dbv-specs-ops/docs/MARKETPLACE_PUBLISHING.md -->

```bash
# Build the installers
npm run tauri build    # or: cargo tauri build
# Output: src-tauri/target/release/bundle/
```

---

<a name="usage"></a>
## ▶️ How to run

<!-- AI: web servers, APIs and resident services use the start/stop scripts below.
     Native desktop apps (Tauri), libraries and CLIs have no daemon: replace this section with the
     native commands (e.g. `npm run tauri dev`) and delete the "How to stop" section and its TOC entry. -->

Use the startup scripts included in the project root:

**Windows:**
```cmd
start.cmd
```

**macOS / Linux:**
```bash
./start.sh
```

Then open your browser at: `http://localhost:[PORT]`

<!-- AI: fill in the correct port and any additional startup notes -->

---

<a name="stop"></a>
## ⏹ How to stop

**Windows:**
```cmd
stop.cmd
```

**macOS / Linux:**
```bash
./stop.sh
```

---

<a name="structure"></a>
## 📂 Project structure

<!-- AI: generate based on the actual project structure created during /build -->

```
/
├── src/              # Application source code
├── tests/            # Unit and integration tests
├── docs/             # User-facing documentation of the project
├── dbv-specs-ops/    # SDD files: specs, architecture, task.md, memory.md, CHANGELOG.md...
│   ├── docs/         #   SPECIFICATIONS.md, ARCHITECTURE.md, MASTER_PROMPT.md...
│   ├── project.config.md  # Project identity and file header config
│   └── CHANGELOG.md  #   Version history
├── start.cmd         # Windows startup script (servers / APIs only)
├── start.sh          # macOS/Linux startup script (servers / APIs only)
├── stop.cmd          # Windows stop script (servers / APIs only)
├── stop.sh           # macOS/Linux stop script (servers / APIs only)
└── README.md         # This file
```

---

<a name="changelog"></a>
## 📋 Changelog

See [CHANGELOG.md](./dbv-specs-ops/CHANGELOG.md) for the full version history.

---

<a name="license"></a>
## 📄 License

[License] — see [LICENSE](./LICENSE) for details.

Copyright (c) [Year] [Author / Company]

---

> 🛠️ Built with **[dbv-specs-ops](https://github.com/davidbuenov/dbv-specs-ops)** — the SDD framework for AI-assisted development.
> Created by [David Bueno Vallejo](https://github.com/davidbuenov) — free and open source.
