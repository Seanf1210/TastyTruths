# System Manual: Project Overview

This document serves as the primary technical guide for maintenance personnel, IT/troubleshooting staff, and onboarding developers.

---

## 🛠 Minimum Requirements

### Software Specifications
The application relies on **Python 3.8+**. Below are the operating system constraints required to support the modern dependency stack (specifically Flask 3.x and SQLAlchemy 2.x).

| Operating System | Minimum Version | Recommended | Notes |
| :--- | :--- | :--- | :--- |
| **Windows** | 8.1 | 10 or 11 | Required for Python 3.9+ support |
| **macOS** | 10.9 (Mavericks) | 11 (Big Sur)+ | macOS 11+ required for Apple Silicon |
| **Linux** | Ubuntu 20.04 / Debian 11 | Ubuntu 22.04 LTS | Requires glibc 2.28+ |

### Hardware Specifications
These requirements ensure stable performance during concurrent web requests and database migrations.

| Component | Minimum Requirement | Purpose |
| :--- | :--- | :--- |
| **CPU** | 2+ Cores | Handles concurrent Flask threads |
| **RAM** | 2 GB | Supports Argon2 hashing & SQLAlchemy caching |
| **Storage** | 4 GB | Accounts for app, logs, and DB growth |

> **Tech Note:** The password hashing used in this project is RAM-intensive by design. If hardware RAM is lower than 2GB, login performance may decrease. 


---

## 🚀 Installation / Setup
Follow these steps to initialize the development environment. It is highly recommended to use a virtual environment to avoid dependency conflicts.

### 1. Create and Activate Virtual Environment
Choose the command based on your Operating System:

| Platform | Command |
| :--- | :--- |
| **macOS / Linux** | `python3 -m venv .venv && source .venv/bin/activate` |
| **Windows** | `python -m venv .venv` then `.venv\Scripts\activate` |

> **Pro-Tip:** If you use this frequently, you can alias the activation command. Ask the lead dev for an example `.zshrc` or `.bashrc` config.

### 2. Install Dependencies
Once the virtual environment is active (you should see `(.venv)` in your terminal), run:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```
### Environment & OS
.venv/
.DS_Store
*.pyc
__pycache__/

### Database & Instance
instance/
*.db
*.sqlite
*.sqlite3

---

## 🔍 Troubleshooting / Error Messages

---


## 📞 Support / Contact
