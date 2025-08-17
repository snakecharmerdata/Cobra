# Cobra Architecture Mapper — How It Works (v0.1)

This document explains how the Cobra Architecture Mapper application works at a high level (version 0.1). It covers the runtime flow, UI structure, persistence model, and key behaviors, so you can understand how the parts fit together and how to extend or debug the app.


## Overview

Cobra Architecture Mapper is a Python desktop GUI built with Tkinter for visually modeling application architecture. You add “function pills” to a canvas, drag them into place, and define their metadata (description, inputs, outputs, relationships). Projects can be saved to JSON or persisted in PostgreSQL using a per-project schema design.


## Key Concepts

- Function Pill: A draggable rectangular widget representing a function (name, position, details).
- Project: A logical grouping of pills (functions). Each DB-backed project has its own schema.
- Per-Project Schema: For each project, the app creates a dedicated schema with tables for functions, inputs, and outputs.
- Detail Window: The dialog for editing a pill’s metadata, including a relationships selector.
- Database Manager: A helper that connects to PostgreSQL, creates tables/schemas, and reads/writes data.


## Runtime Flow

1) App Launch
- The main Tkinter window is created (title, size) with these major sections:
  - Toolbar (top): buttons for Add Function, Clear All, Flow Output, Compile, Logical Mapping, Instructions. A small Cobra logo appears at the far left if available.
  - Canvas (center): drawing surface for function pills and the background grid.
  - Status Bar (bottom): shows state messages and drag coordinates when moving pills.
- The app attempts an automatic PostgreSQL connection using defaults (host=localhost, port=5432, db=Cobra, user=postgres, no password). If it fails, it sets the status accordingly; you can connect manually from the File menu.

2) Canvas + Grid
- The canvas draws a responsive grid:
  - Minor lines every 25 pixels
  - Major lines every 100 pixels (slightly darker)
- The grid clears and redraws automatically on window/canvas resize events.

3) Adding and Editing Pills
- Add Function: creates a pill centered in the visible canvas area.
- Dragging: click and drag a pill; the status bar shows position updates.
- Editing: double-click a pill to open the Detail Window, where you can:
  - Update name and description
  - Manage ordered lists of inputs and outputs
  - Add a visual output note
  - Define relationships via text or by opening the relationships selector

4) Relationships Selector
- From the Detail Window, click “Relationships” label (or double-click the text box) to open a dialog.
- The app fetches functions from the current project (DB-backed) and presents them as checkboxes.
- You can select related functions and provide an explanation block; results are written back into the relationships text area.


## Data Model and Persistence

### In-Memory
- The app holds an array of pill objects each with:
  - name, x/y position, inputs (list), outputs (list)
  - description, visual_output (optional), relationships (optional)
  - function_id (if saved and known in DB)

### JSON (File) Persistence
- You can export the current canvas to a .json file or import from one.
- JSON includes project name and a list of function objects with metadata and coordinates.

Example JSON structure:
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

### PostgreSQL Persistence

1) Auto-Connect on Startup (Best Effort)
- Attempts: host=localhost, port=5432, database=Cobra, user=postgres, password="".
- If DB is missing and permissions allow, the app can create it by connecting to the default 'postgres' database and issuing CREATE DATABASE.

2) Global Catalog Table
- A public `projects` table tracks project names and timestamps.
- A unique index on name ensures idempotent project creation and updates.

3) Per-Project Schema
- When saving a project, the app derives a safe schema name: `proj_<slug>`.
- Tables created per project schema:
  - `functions(id, name, description, visual_output, relationships, x_position, y_position, created_at, updated_at)`
  - `function_inputs(id, function_id, name, position)`
  - `function_outputs(id, function_id, name, position)`
- Saving a project writes all pills and their inputs/outputs to the project’s schema.
- Loading a project reads back the functions and IO lists, recreating pills on the canvas (with positions).

4) Project Lifecycle Operations
- Create New Project: Inserts/ensures a row in `projects`, prepares the per-project schema.
- Save Project: Replaces the project’s function records with the current canvas (and updates in-memory function_ids).
- Open Project: Lists projects, shows function counts, and loads the selected project’s pills.
- Delete/Cancel Project: Provides options to remove a project and its schema (irreversible) or clear session memory-only references.

5) Error Handling
- DB operations include rollback on exceptions to recover from aborted transactions.
- Connection errors and other failures are shown with message dialogs and status updates.


## UI Structure and Behavior

- Toolbar
  - Cobra Logo: loaded from `cobraimage.jpeg` using Pillow (Image, ImageTk). If Pillow is unavailable or the file is missing, a text fallback label (“Cobra”) is shown.
  - Buttons:
    - Add Function: create a new pill
    - Clear All: remove all pills from canvas
    - Flow Output: show aggregated/synthesized output view (UI wiring present)
    - Compile: generate compiled prompt(s) from current canvas (UI wiring present)
    - Logical Mapping: show a conceptual mapping (UI wiring present)
    - Instructions: opens a help window with an updated user guide

- Canvas
  - White background, sunken relief
  - Responsive grid with minor/major lines
  - Function pills drawn as blue rectangles with white bold text

- Status Bar
  - Reflects connectivity and user actions; shows coordinates while dragging.


## Defaults and Configuration

- Auto-connect defaults: host=localhost, port=5432, db=Cobra, user=postgres, no password
- If auto-connect fails, use File → Connect to Database to provide credentials
- The app can create the database and per-project schemas automatically for you when permissions allow


## Dependencies

- Python 3.8+
- Tkinter (stdlib GUI)
- psycopg2-binary (PostgreSQL client)
- Pillow (for loading JPEG logo)

Install all requirements:
```
pip install -r requirements.txt
```


## Typical Workflows

1) File-Only Workflow
- Run the app → Add pills → Edit details → Save to JSON → Load later from JSON.

2) DB Workflow
- Run the app → If not connected, File → Connect to Database → Create New Project → Add pills → Save Project → Verify in client (e.g., DBeaver) → Reopen via File → Open Project.

3) Relationships
- Double-click a pill → open Detail Window → click label/double-click box in Relationships → select related functions → add explanation → Save.


## Notable Behaviors in v0.1

- Denser, responsive grid with minor/major lines and automatic redraw on resize.
- Toolbar Cobra logo (24–144px scaled thumbnail) loaded via Pillow from `cobraimage.jpeg` with a text fallback.
- Updated Instructions window describing the current UX and persistence behavior.
- Per-project schemas and functions/inputs/outputs tables are created automatically.
- Defensive database error handling, including transaction rollback.


## Extending the App

- Add new attributes to pills: update the FunctionPill class, its get_data(), and Detail Window bindings; ensure save/load paths write/read those fields.
- Add new output views: wire a new Tkinter Toplevel window or frame and add a button to the toolbar.
- Change persistence model: modify DatabaseManager (schema creation, save/load queries) while maintaining the projects catalog and schema prefixing.


## Limitations & Notes

- Buttons like Flow Output, Compile, and Logical Mapping are wired in the UI and assumed to invoke their respective views/windows. Ensure their implementations exist before distribution.
- JPEG logo display requires Pillow; if it’s not installed, the app falls back to a text label.
- Auto-creating databases/schemas requires sufficient DB permissions. Provide valid credentials if auto-connect fails.


## Launching the App

```
python architecture_mapper.py
```
- Create or open a project (for DB workflows), then add/edit pills.
- Save to JSON or to DB from the File menu.


---

Version: 0.1
- First public explanation of the architecture and data model
- Introduces responsive grid, logo, and updated instructions
