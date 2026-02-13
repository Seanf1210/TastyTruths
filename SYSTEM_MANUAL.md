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
The following table covers common issues encountered during setup or maintenance.

| Error Message | Likely Cause | Solution |
| :--- | :--- | :--- |
| `sqlalchemy.exc.OperationalError: no such table...` | Missing DB tables. | Run `flask db upgrade`. |
| `alembic.util.exc.CommandError` | Migration/DB mismatch. | Delete local `.db` and run `flask db upgrade`. |
| `ModuleNotFoundError: No module named '_cffi_backend'` | Broken C-bindings. | Reinstall: `pip install --force-reinstall argon2-cffi-bindings`. |
| `RuntimeError: The session is unavailable...` | Missing Secret Key. | Ensure `SECRET_KEY` is defined in `.env` or config. |
| `jinja2.exceptions.TemplateNotFound` | Incorrect file path. | Verify HTML files are in the `/templates` folder. |

### 🛠 Critical Fixes
* **Missing Build Tools:** On Linux, if `pip install` fails, run `sudo apt install build-essential python3-dev`.
* **Environment Check:** Always ensure the prompt shows `(.venv)` before running commands. If not, run the activation command from the Setup section.
---


## 📞 Support / Contact
For critical system failures or architecture questions:
* **Lead Developer:** Ryan Nash, rkn37@drexel.edu
* **Front End developer:** Sean Farkas, smf428@drexel.edu
* **Back End developer:** Joaquin Descotte, jud25@drexel.edu
* **Quality Control:** Ryan Gilinger, rg993@drexel.edu
