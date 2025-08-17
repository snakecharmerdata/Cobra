# Cobra Architecture Mapper

A Python GUI application for visually mapping application architecture using draggable function pills.

Key highlights:
- Visual canvas with a responsive grid (minor lines every 25px, major every 100px)
- Double-click pills to edit details: name, description, inputs, outputs, relationships
- Save/Load projects to JSON files or PostgreSQL (per-project schemas)
- Quick actions from a top toolbar (with Cobra logo)


## Table of Contents
- Requirements
- Quick Start (App only)
- PostgreSQL Setup (Terminal)
  - macOS (Homebrew)
  - Linux (Debian/Ubuntu)
  - Windows
  - Create role and database (psql)
- App Database Defaults and Behavior
- DBeaver Setup to Verify Data
- Using the App (Saving/Loading)
- Project Structure
- JSON File Format


## Requirements
- Python 3.8+
- Pip

Install Python dependencies:

```
pip install -r requirements.txt
```

Note: For showing a JPEG logo, Pillow is required (already in requirements.txt). If you installed before this change:

```
python -m pip install Pillow
```


## Quick Start (App only)
If you only want to run the app without DB persistence:

```
python architecture_mapper.py
```

- Click “Add Function”, enter a name, drag to position.
- Double-click a pill to edit details (inputs/outputs/description/relationships).
- Use “Save to JSON File” and “Load from JSON File” for file-based persistence.


## PostgreSQL Setup (Terminal)
The app can automatically create the Cobra database if it doesn’t exist when connecting with a superuser.

### macOS (Homebrew)
```
brew install postgresql@15
brew services start postgresql@15
# or for on-demand use:
# /opt/homebrew/opt/postgresql@15/bin/pg_ctl -D /opt/homebrew/var/postgresql@15 start
```
Optionally, add the client tools to PATH (if needed):
```
echo 'export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### Linux (Debian/Ubuntu)
```
sudo apt update
sudo apt install postgresql postgresql-contrib -y
sudo systemctl enable postgresql
sudo systemctl start postgresql
```

### Windows
- Download and run the latest PostgreSQL installer from: https://www.postgresql.org/download/
- Ensure “Command Line Tools” are selected in the installer.
- After install, open “SQL Shell (psql)” or use psql from PowerShell/CMD (add bin folder to PATH if needed).

### Create role and database (psql)
If you’ll use the app’s defaults (user: postgres, db: Cobra):

1) Open psql as a superuser (macOS/Linux examples):
```
psql -U postgres -h localhost
```

2) (Optional) Set a password for the postgres user if you plan to use one:
```
ALTER USER postgres WITH PASSWORD 'your_strong_password';
```

3) (Optional) Pre-create the database (the app can create it automatically):
```
CREATE DATABASE "Cobra";
```

If you created a password, remember it for the in-app DB connection dialog.


## App Database Defaults and Behavior
- Default auto-connect attempt on startup:
  - Host: localhost
  - Port: 5432
  - Database: Cobra
  - User: postgres
  - Password: (empty by default)

- If auto-connect fails, go to File → Connect to Database and provide credentials. If the database is missing and the user has privileges, the app will create it automatically.
- The app stores each project’s data in a dedicated schema derived from the project name: `proj_<slug>`. For example, project “My App” becomes schema `proj_my_app`.
- Inside each project schema, three tables are used:
  - `functions` (name, description, visual_output, relationships, x_position, y_position, timestamps)
  - `function_inputs` (function_id, name, position)
  - `function_outputs` (function_id, name, position)


## DBeaver Setup to Verify Data
DBeaver is a popular SQL client to validate changes written by the app.

1) Download and install DBeaver Community:
   - https://dbeaver.io/download/

2) Create a new connection:
   - Database type: PostgreSQL
   - Host: localhost
   - Port: 5432
   - Database: Cobra
   - User: postgres
   - Password: (your password, or leave empty if you use none)
   - Test Connection → Finish

3) Expand the connection in the Database Navigator:
   - Expand Schemas
   - You will see per-project schemas like `proj_<your_project_slug>`
   - Expand a schema, expand Tables → `functions`, `function_inputs`, `function_outputs`

4) Verify data:
   - Right-click `functions` → View Data → All rows
   - You should see rows after saving from the app.
   - Or run a query:
```
SELECT id, name, x_position, y_position
FROM proj_your_project_slug.functions
ORDER BY id DESC;
```


## Using the App (Saving/Loading)
1) Launch the app:
```
python architecture_mapper.py
```

2) Connect to DB (if not auto-connected):
   - File → Connect to Database
   - Enter your Postgres host/port/db/user/password

3) Create a new project:
   - File → Create New Project
   - Enter a project name (e.g., My Project)

4) Add at least one function pill and optionally define inputs/outputs/description/relationships (double-click a pill).

5) Save project to DB:
   - File → Save Project
   - This writes to schema `proj_<your_project_slug>` and its tables.

6) Validate in DBeaver that data exists (see DBeaver section above).

7) Load a project from DB:
   - File → Open Project → pick a row

8) Save/Load as JSON:
   - File → Save to JSON File / Load from JSON File


## Project Structure
The app persists the following for each function:
- name
- position (x, y)
- description
- inputs (ordered)
- outputs (ordered)
- visual_output (optional text)
- relationships (optional text)


## JSON File Format
Example of a saved project JSON:
```
{
  "project": "Project Name",
  "functions": [
    {
      "name": "Function Name",
      "x": 100,
      "y": 100,
      "inputs": ["input1", "input2"],
      "outputs": ["output1"],
      "description": "Function description",
      "visual_output": "",
      "relationships": "",
      "function_id": null
    }
  ]
}
```
