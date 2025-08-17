import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import psycopg2
from psycopg2 import sql
from psycopg2 import errors as pg_errors
import os
import re
from datetime import datetime
import math
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

class FunctionPill:
    """Represents a draggable function pill on the canvas"""
    def __init__(self, canvas, x, y, name, function_id=None):
        self.canvas = canvas
        self.name = name
        self.function_id = function_id
        self.x = x
        self.y = y
        self.width = 120
        self.height = 40
        self.inputs = []
        self.outputs = []
        self.description = ""
        self.visual_output = ""
        self.relationships = ""
        
        # Create the pill shape
        self.rect = self.canvas.create_rectangle(
            x, y, x + self.width, y + self.height,
            fill="#4A90E2", outline="#2E5C8A", width=2,
            tags=("pill", f"pill_{id(self)}")
        )
        
        # Create the text label
        self.text = self.canvas.create_text(
            x + self.width/2, y + self.height/2,
            text=name, fill="white", font=("Arial", 10, "bold"),
            tags=("pill_text", f"pill_{id(self)}")
        )
        
        # Bind events
        self.canvas.tag_bind(f"pill_{id(self)}", "<Button-1>", self.on_click)
        self.canvas.tag_bind(f"pill_{id(self)}", "<B1-Motion>", self.on_drag)
        self.canvas.tag_bind(f"pill_{id(self)}", "<ButtonRelease-1>", self.on_release)
        self.canvas.tag_bind(f"pill_{id(self)}", "<Double-Button-1>", self.on_double_click)
        
        self.drag_data = {"x": 0, "y": 0}
        
    def on_click(self, event):
        """Handle mouse click"""
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y
        
    def on_drag(self, event):
        """Handle dragging"""
        delta_x = event.x - self.drag_data["x"]
        delta_y = event.y - self.drag_data["y"]
        
        self.canvas.move(self.rect, delta_x, delta_y)
        self.canvas.move(self.text, delta_x, delta_y)
        
        self.x += delta_x
        self.y += delta_y
        
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y
        
        # Update status bar with position info
        app = self.get_app_instance()
        if app:
            app.status_var.set(f"Moving '{self.name}' to position ({self.x}, {self.y})")
        
    def on_release(self, event):
        """Handle mouse release"""
        pass
        
    def on_double_click(self, event):
        """Open detail window on double click"""
        # Get the root window which should be the ArchitectureMapper instance
        root = self.canvas.winfo_toplevel()
        DetailWindow(root, self)
        
    def update_name(self, new_name):
        """Update the pill's name"""
        self.name = new_name
        self.canvas.itemconfig(self.text, text=new_name)
        
    def get_data(self):
        """Get pill data for saving"""
        return {
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "description": self.description,
            "visual_output": self.visual_output,
            "relationships": self.relationships,
            "function_id": self.function_id
        }
    
    def get_app_instance(self):
        """Get the main application instance"""
        # Prefer app reference attached to the toplevel/root
        toplevel = self.canvas.winfo_toplevel()
        if hasattr(toplevel, 'app'):
            return toplevel.app
        # Fallback: walk up the widget hierarchy
        widget = self.canvas.master
        while widget:
            if hasattr(widget, 'app'):
                return widget.app
            if hasattr(widget, 'db_manager'):
                return widget
            widget = widget.master if hasattr(widget, 'master') else None
        return None

class DetailWindow:
    """Window for editing function details"""
    def __init__(self, parent, pill):
        self.pill = pill
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title(f"Function Details: {pill.name}")
        try:
            self.window.configure(bg="#f2f2f2")
        except Exception:
            pass
        # Set size and center on screen
        w, h = 700, 650
        try:
            self.window.update_idletasks()
            sw = self.window.winfo_screenwidth()
            sh = self.window.winfo_screenheight()
            x = max((sw - w) // 2, 0)
            y = max((sh - h) // 2, 0)
            self.window.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            self.window.geometry(f"{w}x{h}")
        
        # Main frame
        main_frame = tk.Frame(self.window, bg="#f2f2f2", highlightthickness=0)
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        
        # Function name
        tk.Label(main_frame, text="Function Name:", bg="#f2f2f2", fg="#000000").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar(value=pill.name)
        name_entry = tk.Entry(main_frame, textvariable=self.name_var, width=40, bg="#f2f2f2", fg="#000000", insertbackground="#000000")
        name_entry.grid(row=0, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Description
        tk.Label(main_frame, text="Description:", bg="#f2f2f2", fg="#000000").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.desc_text = tk.Text(main_frame, height=3, width=40, bg="#f2f2f2", fg="#000000", insertbackground="#000000")
        self.desc_text.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        self.desc_text.insert("1.0", pill.description)
        
        # Inputs column
        tk.Label(main_frame, text="Inputs:", font=("Arial", 10, "bold"), bg="#f2f2f2", fg="#000000").grid(row=2, column=0, pady=10)
        
        # Inputs listbox
        self.inputs_listbox = tk.Listbox(main_frame, height=8, bg="#f2f2f2", fg="#000000", selectbackground="#c0c0c0", selectforeground="#000000")
        self.inputs_listbox.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Input buttons
        input_btn_frame = tk.Frame(main_frame, bg="#f2f2f2", highlightthickness=0)
        input_btn_frame.grid(row=4, column=0, pady=5)
        ttk.Button(input_btn_frame, text="Add", command=self.add_input).pack(side=tk.LEFT, padx=2)
        ttk.Button(input_btn_frame, text="Edit", command=self.edit_input).pack(side=tk.LEFT, padx=2)
        ttk.Button(input_btn_frame, text="Delete", command=self.delete_input).pack(side=tk.LEFT, padx=2)
        
        # Outputs column
        tk.Label(main_frame, text="Outputs:", font=("Arial", 10, "bold"), bg="#f2f2f2", fg="#000000").grid(row=2, column=2, pady=10)
        
        # Outputs listbox
        self.outputs_listbox = tk.Listbox(main_frame, height=8, bg="#f2f2f2", fg="#000000", selectbackground="#c0c0c0", selectforeground="#000000")
        self.outputs_listbox.grid(row=3, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Output buttons
        output_btn_frame = tk.Frame(main_frame, bg="#f2f2f2", highlightthickness=0)
        output_btn_frame.grid(row=4, column=2, pady=5)
        ttk.Button(output_btn_frame, text="Add", command=self.add_output).pack(side=tk.LEFT, padx=2)
        ttk.Button(output_btn_frame, text="Edit", command=self.edit_output).pack(side=tk.LEFT, padx=2)
        ttk.Button(output_btn_frame, text="Delete", command=self.delete_output).pack(side=tk.LEFT, padx=2)
        
        # Visual Output
        tk.Label(main_frame, text="Visual Output:", bg="#f2f2f2", fg="#000000").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.visual_output_text = tk.Text(main_frame, height=3, width=40, bg="#f2f2f2", fg="#000000", insertbackground="#000000")
        self.visual_output_text.grid(row=5, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        self.visual_output_text.insert("1.0", pill.visual_output)
        
        # Relationships
        relationships_label = tk.Label(main_frame, text="Relationships:", bg="#f2f2f2", fg="#000000")
        relationships_label.grid(row=6, column=0, sticky=tk.W, pady=5)
        self.relationships_text = tk.Text(main_frame, height=3, width=40, bg="#f2f2f2", fg="#000000", insertbackground="#000000")
        self.relationships_text.grid(row=6, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        self.relationships_text.insert("1.0", pill.relationships)
        # Click label or double-click text to quickly select relationships
        relationships_label.bind("<Button-1>", lambda e: self.open_relationship_selector())
        self.relationships_text.bind("<Double-Button-1>", lambda e: self.open_relationship_selector())
        
        # Save/Cancel buttons
        button_frame = tk.Frame(main_frame, bg="#f2f2f2", highlightthickness=0)
        button_frame.grid(row=7, column=0, columnspan=3, pady=10)
        ttk.Button(button_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.window.destroy).pack(side=tk.LEFT, padx=5)
        
        # Database operations frame
        db_frame = tk.LabelFrame(main_frame, text="Database Operations", bg="#f2f2f2", fg="#000000")
        db_frame.grid(row=8, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E), ipadx=5, ipady=5)
        
        # Database buttons
        ttk.Button(db_frame, text="Save to DB", command=self.save_to_db).pack(side=tk.LEFT, padx=5)
        ttk.Button(db_frame, text="Update in DB", command=self.update_in_db).pack(side=tk.LEFT, padx=5)
        ttk.Button(db_frame, text="Delete from DB", command=self.delete_from_db).pack(side=tk.LEFT, padx=5)
        ttk.Button(db_frame, text="Load from DB", command=self.load_from_db).pack(side=tk.LEFT, padx=5)
        
        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(2, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Load existing data
        self.load_data()
        
    def load_data(self):
        """Load existing inputs and outputs"""
        for inp in self.pill.inputs:
            self.inputs_listbox.insert(tk.END, inp)
        for out in self.pill.outputs:
            self.outputs_listbox.insert(tk.END, out)
            
    def add_input(self):
        """Add a new input"""
        value = simpledialog.askstring("Add Input", "Enter Input Details:")
        if value:
            self.inputs_listbox.insert(tk.END, value)
            
    def edit_input(self):
        """Edit selected input"""
        selection = self.inputs_listbox.curselection()
        if selection:
            current = self.inputs_listbox.get(selection[0])
            value = simpledialog.askstring("Edit Input", "Enter new Details:", initialvalue=current)
            if value:
                self.inputs_listbox.delete(selection[0])
                self.inputs_listbox.insert(selection[0], value)
                
    def delete_input(self):
        """Delete selected input"""
        selection = self.inputs_listbox.curselection()
        if selection:
            self.inputs_listbox.delete(selection[0])
            
    def add_output(self):
        """Add a new output"""
        value = simpledialog.askstring("Add Output", "Enter Output Details:")
        if value:
            self.outputs_listbox.insert(tk.END, value)
            
    def edit_output(self):
        """Edit selected output"""
        selection = self.outputs_listbox.curselection()
        if selection:
            current = self.outputs_listbox.get(selection[0])
            value = simpledialog.askstring("Edit Output", "Enter new value:", initialvalue=current)
            if value:
                self.outputs_listbox.delete(selection[0])
                self.outputs_listbox.insert(selection[0], value)
                
    def delete_output(self):
        """Delete selected output"""
        selection = self.outputs_listbox.curselection()
        if selection:
            self.outputs_listbox.delete(selection[0])
            
    def save(self):
        """Save changes to the pill"""
        self.pill.name = self.name_var.get()
        self.pill.update_name(self.pill.name)
        self.pill.description = self.desc_text.get("1.0", tk.END).strip()
        self.pill.visual_output = self.visual_output_text.get("1.0", tk.END).strip()
        self.pill.relationships = self.relationships_text.get("1.0", tk.END).strip()
        
        # Update inputs and outputs
        self.pill.inputs = list(self.inputs_listbox.get(0, tk.END))
        self.pill.outputs = list(self.outputs_listbox.get(0, tk.END))
        
        self.window.destroy()
    
    def save_to_db(self):
        """Save function as new entry to database (per-project schema)"""
        if not self.ensure_connected():
            return
        app = self.get_app_instance()
        if not app.current_project:
            messagebox.showwarning("No Project", "Please create or open a project first before saving functions to database.")
            return

        # First save the changes to the pill (updates in-memory fields)
        self.save()

        cursor = app.db_manager.connection.cursor()
        try:
            # Ensure project exists and schema is ready
            cursor.execute(
                """
                INSERT INTO projects (name) VALUES (%s)
                ON CONFLICT (name) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                RETURNING id
                """,
                (app.current_project,),
            )
            cursor.fetchone()
            app.db_manager.ensure_project_schema(app.current_project)
            schema = app.db_manager.schema_name_for_project(app.current_project)

            # Save (upsert) function into project's schema by unique name
            data = self.pill.get_data()
            cursor.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.functions (name, description, visual_output, relationships, x_position, y_position)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (name)
                    DO UPDATE SET
                        description = EXCLUDED.description,
                        visual_output = EXCLUDED.visual_output,
                        relationships = EXCLUDED.relationships,
                        x_position = EXCLUDED.x_position,
                        y_position = EXCLUDED.y_position,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                    """
                ).format(sql.Identifier(schema)),
                (data['name'], data['description'], data['visual_output'], data['relationships'], data['x'], data['y']),
            )
            function_id = cursor.fetchone()[0]
            self.pill.function_id = function_id

            # Save inputs
            for i, inp in enumerate(data['inputs']):
                cursor.execute(
                    sql.SQL(
                        """
                        INSERT INTO {}.function_inputs (function_id, name, position)
                        VALUES (%s, %s, %s)
                        """
                    ).format(sql.Identifier(schema)),
                    (function_id, inp, i),
                )

            # Save outputs
            for i, out in enumerate(data['outputs']):
                cursor.execute(
                    sql.SQL(
                        """
                        INSERT INTO {}.function_outputs (function_id, name, position)
                        VALUES (%s, %s, %s)
                        """
                    ).format(sql.Identifier(schema)),
                    (function_id, out, i),
                )

            app.db_manager.connection.commit()
            messagebox.showinfo("Success", "Function saved to database!")
        except Exception as e:
            app.db_manager.connection.rollback()
            messagebox.showerror("Database Error", f"Failed to save: {str(e)}")
    
    def update_in_db(self):
        """Update existing function in database (per-project schema)"""
        if not self.pill.function_id:
            messagebox.showwarning("Database", "This function is not in the database. Use 'Save to DB' first.")
            return
        if not self.ensure_connected():
            return
        app = self.get_app_instance()

        # First save the changes to the pill
        self.save()

        cursor = app.db_manager.connection.cursor()
        try:
            schema = app.db_manager.schema_name_for_project(app.current_project)
            # Update function
            data = self.pill.get_data()
            cursor.execute(
                sql.SQL(
                    """
                    UPDATE {}.functions
                    SET name = %s, description = %s, visual_output = %s, relationships = %s,
                        x_position = %s, y_position = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """
                ).format(sql.Identifier(schema)),
                (data['name'], data['description'], data['visual_output'], data['relationships'], data['x'], data['y'], self.pill.function_id),
            )

            # Delete and re-insert inputs
            cursor.execute(
                sql.SQL("DELETE FROM {}.function_inputs WHERE function_id = %s").format(sql.Identifier(schema)),
                (self.pill.function_id,),
            )
            for i, inp in enumerate(data['inputs']):
                cursor.execute(
                    sql.SQL(
                        """
                        INSERT INTO {}.function_inputs (function_id, name, position)
                        VALUES (%s, %s, %s)
                        """
                    ).format(sql.Identifier(schema)),
                    (self.pill.function_id, inp, i),
                )

            # Delete and re-insert outputs
            cursor.execute(
                sql.SQL("DELETE FROM {}.function_outputs WHERE function_id = %s").format(sql.Identifier(schema)),
                (self.pill.function_id,),
            )
            for i, out in enumerate(data['outputs']):
                cursor.execute(
                    sql.SQL(
                        """
                        INSERT INTO {}.function_outputs (function_id, name, position)
                        VALUES (%s, %s, %s)
                        """
                    ).format(sql.Identifier(schema)),
                    (self.pill.function_id, out, i),
                )

            app.db_manager.connection.commit()
            messagebox.showinfo("Success", "Function updated in database!")
        except Exception as e:
            app.db_manager.connection.rollback()
            messagebox.showerror("Database Error", f"Failed to update: {str(e)}")
    
    def delete_from_db(self):
        """Delete function from database (per-project schema)"""
        if not self.pill.function_id:
            messagebox.showwarning("Database", "This function is not in the database.")
            return
        if not self.ensure_connected():
            return
        app = self.get_app_instance()

        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this function from the database?"):
            cursor = app.db_manager.connection.cursor()
            try:
                schema = app.db_manager.schema_name_for_project(app.current_project)
                cursor.execute(
                    sql.SQL("DELETE FROM {}.functions WHERE id = %s").format(sql.Identifier(schema)),
                    (self.pill.function_id,),
                )
                app.db_manager.connection.commit()

                # Remove from canvas
                self.pill.canvas.delete(self.pill.rect)
                self.pill.canvas.delete(self.pill.text)

                # Remove from pills list
                if hasattr(app, 'pills') and self.pill in app.pills:
                    app.pills.remove(self.pill)

                messagebox.showinfo("Success", "Function deleted from database!")
                self.window.destroy()
            except Exception as e:
                app.db_manager.connection.rollback()
                messagebox.showerror("Database Error", f"Failed to delete: {str(e)}")
    
    def load_from_db(self):
        """Load function details from current project's schema"""
        if not self.ensure_connected():
            return
        app = self.get_app_instance()
        if not app.current_project:
            messagebox.showwarning("No Project", "Please open or create a project first.")
            return

        # Get list of functions for current project
        cursor = app.db_manager.connection.cursor()
        schema = app.db_manager.schema_name_for_project(app.current_project)
        cursor.execute(
            sql.SQL("SELECT id, name FROM {}.functions ORDER BY name").format(sql.Identifier(schema))
        )
        functions = cursor.fetchall()
        if not functions:
            messagebox.showinfo("Database", "No functions found in the current project")
            return

        # Create selection dialog
        dialog = tk.Toplevel(self.window)
        dialog.title("Select Function")
        # Center dialog on screen
        try:
            dialog.update_idletasks()
            sw = dialog.winfo_screenwidth()
            sh = dialog.winfo_screenheight()
            w, h = 400, 300
            x = max((sw - w) // 2, 0)
            y = max((sh - h) // 2, 0)
            dialog.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            dialog.geometry("400x300")

        ttk.Label(dialog, text="Select a function to load:").pack(pady=10)

        listbox_frame = ttk.Frame(dialog)
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)

        function_map = {}
        for func_id, func_name in functions:
            display_name = func_name
            listbox.insert(tk.END, display_name)
            function_map[display_name] = func_id

        def load_selected():
            selection = listbox.curselection()
            if selection:
                selected_name = listbox.get(selection[0])
                func_id = function_map[selected_name]

                # Load function details
                cursor.execute(
                    sql.SQL(
                        """
                        SELECT name, description, visual_output, relationships, x_position, y_position
                        FROM {}.functions WHERE id = %s
                        """
                    ).format(sql.Identifier(schema)),
                    (func_id,),
                )
                func_data = cursor.fetchone()
                if func_data:
                    name, desc, visual_output, relationships, x, y = func_data

                    # Update UI
                    self.name_var.set(name)
                    self.desc_text.delete("1.0", tk.END)
                    self.desc_text.insert("1.0", desc or "")
                    self.visual_output_text.delete("1.0", tk.END)
                    self.visual_output_text.insert("1.0", visual_output or "")
                    self.relationships_text.delete("1.0", tk.END)
                    self.relationships_text.insert("1.0", relationships or "")

                    # Load inputs
                    cursor.execute(
                        sql.SQL(
                            """
                            SELECT name FROM {}.function_inputs
                            WHERE function_id = %s ORDER BY position
                            """
                        ).format(sql.Identifier(schema)),
                        (func_id,),
                    )

                    self.inputs_listbox.delete(0, tk.END)
                    for row in cursor.fetchall():
                        self.inputs_listbox.insert(tk.END, row[0])

                    # Load outputs
                    cursor.execute(
                        sql.SQL(
                            """
                            SELECT name FROM {}.function_outputs
                            WHERE function_id = %s ORDER BY position
                            """
                        ).format(sql.Identifier(schema)),
                        (func_id,),
                    )

                    self.outputs_listbox.delete(0, tk.END)
                    for row in cursor.fetchall():
                        self.outputs_listbox.insert(tk.END, row[0])

                    self.pill.function_id = func_id
                    messagebox.showinfo("Success", "Function loaded from database!")

                dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Load", command=load_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def get_app_instance(self):
        """Get the main application instance"""
        # Prefer app reference on the parent/toplevel
        if hasattr(self.parent, 'app'):
            return self.parent.app
        # Walk up the widget hierarchy to find the main app
        widget = self.parent
        while widget:
            if hasattr(widget, 'app'):
                return widget.app
            if hasattr(widget, 'db_manager'):
                return widget
            # Try to get parent in different ways
            if hasattr(widget, 'master'):
                widget = widget.master
            elif hasattr(widget, 'parent'):
                widget = widget.parent
            else:
                widget = None
        return None

    def open_relationship_selector(self):
        """Open a dialog to select related functions and explanation for this function."""
        # Validate app and DB state
        app = self.get_app_instance()
        if not app:
            messagebox.showerror("Error", "Cannot find application instance")
            return
        if not app.current_project:
            messagebox.showwarning("No Project", "Please open or create a project first.")
            return
        if not app.db_manager.connected:
            app.connect_database()
            if not app.db_manager.connected:
                messagebox.showwarning("Database", "Database connection required for this operation")
                return

        # Fetch functions for current project
        cursor = app.db_manager.connection.cursor()
        schema = app.db_manager.schema_name_for_project(app.current_project)
        try:
            cursor.execute(
                sql.SQL("SELECT id, name FROM {}.functions ORDER BY name").format(sql.Identifier(schema))
            )
            func_rows = cursor.fetchall()
        except Exception as e:
            try:
                app.db_manager.connection.rollback()
            except Exception:
                pass
            messagebox.showerror("Database", f"Failed to fetch functions: {e}")
            return

        # Build list excluding self (by id if available, otherwise by name)
        exclude_id = getattr(self.pill, 'function_id', None)
        exclude_name = (self.pill.name or "").strip().lower()
        options = []  # list of (id, name)
        for fid, fname in func_rows:
            if exclude_id and fid == exclude_id:
                continue
            if not exclude_id and fname.strip().lower() == exclude_name:
                continue
            options.append((fid, fname))

        # Parse existing relationships text to preselect
        existing = self.relationships_text.get("1.0", tk.END).strip()
        selected_names = []
        explanation_prefill = ""
        for line in existing.splitlines():
            if line.strip().lower().startswith("related to:"):
                rest = line.split(":", 1)[1].strip()
                selected_names = [n.strip() for n in rest.split(",") if n.strip()]
            elif line.strip().lower().startswith("explanation:"):
                explanation_prefill = line.split(":", 1)[1].strip()

        # Build dialog UI
        dialog = tk.Toplevel(self.window)
        dialog.title("Select Relationships")
        # Center dialog on screen
        try:
            dialog.update_idletasks()
            sw = dialog.winfo_screenwidth()
            sh = dialog.winfo_screenheight()
            w, h = 460, 520
            x = max((sw - w) // 2, 0)
            y = max((sh - h) // 2, 0)
            dialog.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            dialog.geometry("460x520")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text="Select related functions:").pack(anchor=tk.W, padx=10, pady=(10, 5))

        # Scrollable checkbox area
        outer = ttk.Frame(dialog)
        outer.pack(fill=tk.BOTH, expand=True, padx=10)

        canvas = tk.Canvas(outer, height=250)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vscroll = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.configure(yscrollcommand=vscroll.set)

        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _on_inner_configure)

        var_by_name = {}
        for _, fname in options:
            var = tk.BooleanVar(value=(fname in selected_names))
            cb = ttk.Checkbutton(inner, text=fname, variable=var)
            cb.pack(anchor=tk.W)
            var_by_name[fname] = var

        # Explanation box
        ttk.Label(dialog, text="Explanation:").pack(anchor=tk.W, padx=10, pady=(10, 5))
        exp_text = tk.Text(dialog, height=5, width=50, bg="#f2f2f2", fg="#000000", insertbackground="#000000")
        exp_text.pack(fill=tk.BOTH, expand=False, padx=10)
        if explanation_prefill:
            exp_text.insert("1.0", explanation_prefill)

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)

        def apply_selection():
            selected = [name for name, var in var_by_name.items() if var.get()]
            explanation = exp_text.get("1.0", tk.END).strip()
            new_text = f"Related to: {', '.join(selected)}\nExplanation: {explanation}"
            self.relationships_text.delete("1.0", tk.END)
            self.relationships_text.insert("1.0", new_text)
            dialog.destroy()

        ttk.Button(btn_frame, text="Save", command=apply_selection).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def ensure_connected(self):
        """Ensure database is connected, prompt if not"""
        app = self.get_app_instance()
        if not app:
            messagebox.showerror("Error", "Cannot find application instance")
            return False
        if not app.db_manager.connected:
            app.connect_database()
        if not app.db_manager.connected:
            messagebox.showwarning("Database", "Database connection required for this operation")
            return False
        return True

class DatabaseManager:
    """Manages PostgreSQL database operations"""
    def __init__(self):
        self.connection = None
        self.connected = False
        self.last_connection_info = None
        
    def connect(self, host, database, user, password, port=5432):
        """Connect to PostgreSQL database; if the DB does not exist, create it automatically."""
        def _do_connect(db_name):
            return psycopg2.connect(host=host, database=db_name, user=user, password=password, port=port)

        try:
            self.connection = _do_connect(database)
            self.connected = True
        except Exception as e:
            msg = str(e)
            if 'does not exist' in msg or 'Invalid catalog name' in msg or getattr(e, 'pgcode', None) == '3D000':
                # Try to create the database by connecting to the default 'postgres' database
                try:
                    admin_conn = _do_connect('postgres')
                    admin_conn.autocommit = True
                    cur = admin_conn.cursor()
                    cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
                    cur.close()
                    admin_conn.close()
                    # Retry original connection
                    self.connection = _do_connect(database)
                    self.connected = True
                except Exception as ce:
                    messagebox.showerror("Database Error", f"Failed to create database '{database}': {ce}")
                    return False
            else:
                messagebox.showerror("Database Error", f"Failed to connect: {msg}")
                return False

        # Save connection info (without password for security)
        self.last_connection_info = {
            "host": host,
            "port": port,
            "database": database,
            "user": user
        }
        self.create_tables()
        return True
            
    def create_tables(self):
        """Create necessary tables if they don't exist"""
        if not self.connected:
            return
            
        cursor = self.connection.cursor()
        
        # Create projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Ensure unique index on project name for ON CONFLICT to work
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_name_unique ON projects(name)")
        
        # Per-project schemas will define their own tables (functions, function_inputs, function_outputs)
        
        # Per-project schemas: function_inputs table is created per project
        
        # Per-project schemas: function_outputs table is created per project
        
        self.connection.commit()
        
    def schema_name_for_project(self, project_name):
        """Derive a safe schema name from project name"""
        slug = re.sub(r'[^a-z0-9_]+', '_', (project_name or '').lower())
        if not slug or not slug[0].isalpha():
            slug = 'p_' + slug
        schema = f'proj_{slug}'
        return schema[:63]

    def ensure_project_schema(self, project_name):
        """Create per-project schema and tables if not exist"""
        if not self.connected:
            return False
        schema = self.schema_name_for_project(project_name)
        cur = self.connection.cursor()
        # Create schema
        cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}" ).format(sql.Identifier(schema)))
        # Create functions table
        cur.execute(sql.SQL("""
            CREATE TABLE IF NOT EXISTS {}.functions (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                visual_output TEXT,
                relationships TEXT,
                x_position INTEGER,
                y_position INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """).format(sql.Identifier(schema)))
        # Ensure unique name per project to prevent duplicates and enable upsert
        cur.execute(
            sql.SQL("CREATE UNIQUE INDEX IF NOT EXISTS functions_name_unique ON {}.functions(name)")
               .format(sql.Identifier(schema))
        )
        # Create inputs table
        cur.execute(sql.SQL("""
            CREATE TABLE IF NOT EXISTS {}.function_inputs (
                id SERIAL PRIMARY KEY,
                function_id INTEGER REFERENCES {}.functions(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                position INTEGER
            )
        """).format(sql.Identifier(schema), sql.Identifier(schema)))
        # Create outputs table
        cur.execute(sql.SQL("""
            CREATE TABLE IF NOT EXISTS {}.function_outputs (
                id SERIAL PRIMARY KEY,
                function_id INTEGER REFERENCES {}.functions(id) ON DELETE CASCADE,
                name VARCHAR(255) NOT NULL,
                position INTEGER
            )
        """).format(sql.Identifier(schema), sql.Identifier(schema)))
        self.connection.commit()
        return True

    def count_functions_in_project(self, project_name):
        """Count functions inside a project's schema"""
        try:
            schema = self.schema_name_for_project(project_name)
            cur = self.connection.cursor()
            # Ensure schema exists
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = %s)",
                (schema,),
            )
            if not cur.fetchone()[0]:
                return 0
            # Ensure functions table exists in that schema
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = %s AND table_name = 'functions'
                )
                """,
                (schema,),
            )
            if not cur.fetchone()[0]:
                return 0
            # Safe to count now
            cur.execute(sql.SQL("SELECT COUNT(*) FROM {}.functions").format(sql.Identifier(schema)))
            return cur.fetchone()[0]
        except Exception:
            # If a previous statement failed, the connection enters an aborted state; clear it
            try:
                self.connection.rollback()
            except Exception:
                pass
            return 0

    def drop_project_schema(self, project_name):
        """Drop a project's schema and all contained objects"""
        schema = self.schema_name_for_project(project_name)
        cur = self.connection.cursor()
        cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
        self.connection.commit()
        return True
        
    def save_project(self, project_name, pills):
        """Save project to database (per-project schema)"""
        if not self.connected:
            messagebox.showwarning("Database", "Not connected to database")
            return False
        cursor = self.connection.cursor()
        try:
            # Ensure project row exists
            cursor.execute(
                """
                INSERT INTO projects (name) VALUES (%s)
                ON CONFLICT (name) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                RETURNING id
                """,
                (project_name,)
            )
            cursor.fetchone()

            # Ensure per-project schema/tables exist
            self.ensure_project_schema(project_name)
            schema = self.schema_name_for_project(project_name)

            # Clear existing functions in project's schema
            cursor.execute(sql.SQL("DELETE FROM {}.functions").format(sql.Identifier(schema)))

            # Insert functions and their I/O
            for pill in pills:
                data = pill.get_data()
                cursor.execute(
                    sql.SQL(
                        """
                        INSERT INTO {}.functions (name, description, visual_output, relationships, x_position, y_position)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """
                    ).format(sql.Identifier(schema)),
                    (data['name'], data['description'], data['visual_output'], data['relationships'], data['x'], data['y']),
                )
                function_id = cursor.fetchone()[0]
                # Keep in-memory pill linked to its DB row for future updates
                try:
                    pill.function_id = function_id
                except Exception:
                    pass

                # Inputs
                for i, inp in enumerate(data['inputs']):
                    cursor.execute(
                        sql.SQL(
                            """
                            INSERT INTO {}.function_inputs (function_id, name, position)
                            VALUES (%s, %s, %s)
                            """
                        ).format(sql.Identifier(schema)),
                        (function_id, inp, i),
                    )
                # Outputs
                for i, out in enumerate(data['outputs']):
                    cursor.execute(
                        sql.SQL(
                            """
                            INSERT INTO {}.function_outputs (function_id, name, position)
                            VALUES (%s, %s, %s)
                            """
                        ).format(sql.Identifier(schema)),
                        (function_id, out, i),
                    )

            self.connection.commit()
            return True
        except Exception as e:
            self.connection.rollback()
            messagebox.showerror("Database Error", f"Failed to save: {str(e)}")
            return False
            
    def load_project(self, project_name):
        """Load project from database (per-project schema)"""
        if not self.connected:
            return None
        cursor = self.connection.cursor()
        try:
            # Verify project exists
            cursor.execute("SELECT 1 FROM projects WHERE name = %s", (project_name,))
            if not cursor.fetchone():
                return None

            schema = self.schema_name_for_project(project_name)
            functions = []

            # Get functions
            cursor.execute(
                sql.SQL(
                    """
                    SELECT id, name, description, visual_output, relationships, x_position, y_position
                    FROM {}.functions
                    """
                ).format(sql.Identifier(schema))
            )
            for func in cursor.fetchall():
                func_id, name, desc, visual_output, relationships, x, y = func

                # Inputs
                cursor.execute(
                    sql.SQL(
                        """
                        SELECT name FROM {}.function_inputs
                        WHERE function_id = %s ORDER BY position
                        """
                    ).format(sql.Identifier(schema)),
                    (func_id,),
                )
                inputs = [row[0] for row in cursor.fetchall()]

                # Outputs
                cursor.execute(
                    sql.SQL(
                        """
                        SELECT name FROM {}.function_outputs
                        WHERE function_id = %s ORDER BY position
                        """
                    ).format(sql.Identifier(schema)),
                    (func_id,),
                )
                outputs = [row[0] for row in cursor.fetchall()]

                functions.append(
                    {
                        'function_id': func_id,
                        'name': name,
                        'description': desc,
                        'visual_output': visual_output,
                        'relationships': relationships,
                        'x': x,
                        'y': y,
                        'inputs': inputs,
                        'outputs': outputs,
                    }
                )

            return functions
        except Exception as e:
            # Clear aborted transaction state to allow further DB operations
            try:
                self.connection.rollback()
            except Exception:
                pass
            messagebox.showerror("Database Error", f"Failed to load: {str(e)}")
            return None
            
    def list_projects(self):
        """Get list of all projects"""
        if not self.connected:
            return []
            
        cursor = self.connection.cursor()
        cursor.execute("SELECT name FROM projects ORDER BY name")
        return [row[0] for row in cursor.fetchall()]
        
    def delete_project(self, project_name):
        """Delete a project and its dedicated schema"""
        if not self.connected:
            return False
        cursor = self.connection.cursor()
        try:
            # Drop per-project schema and all contained objects
            self.drop_project_schema(project_name)
            # Remove catalog row
            cursor.execute("DELETE FROM projects WHERE name = %s", (project_name,))
            self.connection.commit()
            return True
        except Exception as e:
            self.connection.rollback()
            messagebox.showerror("Database Error", f"Failed to delete: {str(e)}")
            return False

class ArchitectureMapper:
    """Main application class"""
    def __init__(self, root):
        self.root = root
        self.root.title("Cobra Architecture Mapper")
        self.root.geometry("1000x700")
        
        self.pills = []
        self.db_manager = DatabaseManager()
        self.current_project = None
        self.memory_projects = set()
        
        self.setup_ui()
        self.setup_menu()
        # Attach app reference to root for dialogs and child widgets to access
        self.root.app = self
        self.root.db_manager = self.db_manager
        self.auto_connect_postgres()
        
    def setup_ui(self):
        """Setup the main UI"""
        # Toolbar
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # App logo at top-left
        self._logo_label = None
        self._logo_photo = None
        try:
            logo_path = os.path.join(os.path.dirname(__file__), "cobraimage.jpeg")
        except NameError:
            logo_path = "cobraimage.jpeg"
        if os.path.exists(logo_path):
            _photo = None
            try:
                if 'PIL_AVAILABLE' in globals() and PIL_AVAILABLE:
                    _img = Image.open(logo_path)
                    _resample = getattr(Image, "LANCZOS", getattr(Image, "ANTIALIAS", 1))
                    _img.thumbnail((144, 144), resample=_resample)
                    _photo = ImageTk.PhotoImage(_img)
            except Exception:
                _photo = None

            if _photo:
                self._logo_photo = _photo
                self._logo_label = ttk.Label(toolbar, image=self._logo_photo)
                self._logo_label.pack(side=tk.LEFT, padx=(0, 8))
                try:
                    self.root.iconphoto(True, self._logo_photo)
                except Exception:
                    pass
            else:
                self._logo_label = ttk.Label(toolbar, text="Cobra", font=("Arial", 11, "bold"))
                self._logo_label.pack(side=tk.LEFT, padx=(0, 8))
        else:
            # File missing: show text fallback
            self._logo_label = ttk.Label(toolbar, text="Cobra", font=("Arial", 11, "bold"))
            self._logo_label.pack(side=tk.LEFT, padx=(0, 8))
        
        ttk.Button(toolbar, text="Add Function", command=self.add_function).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Clear All", command=self.clear_all).pack(side=tk.LEFT, padx=5)
        # Flow Output removed
        ttk.Button(toolbar, text="Compile", command=self.compile_architecture).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Logical Mapping", command=self.show_logical_mapping).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Instructions", command=self.show_instructions).pack(side=tk.LEFT, padx=5)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Canvas
        canvas_frame = ttk.Frame(self.root)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.canvas = tk.Canvas(canvas_frame, bg="white", relief=tk.SUNKEN, borderwidth=2)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Redraw grid anytime canvas is resized
        self.canvas.bind("<Configure>", lambda e: self.draw_grid())
        
        # Grid lines
        self.draw_grid()
        
    def setup_menu(self):
        """Setup menu bar"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Project operations
        file_menu.add_command(label="Create New Project", command=self.create_new_project)
        file_menu.add_command(label="Open Project", command=self.open_project)
        file_menu.add_command(label="Cancel Project", command=self.cancel_project)
        file_menu.add_separator()
        
        # Database connection
        file_menu.add_command(label="Connect to Database", command=self.connect_database)
        file_menu.add_separator()
        
        # Save/Load operations
        file_menu.add_command(label="Save Project", command=self.save_project)
        file_menu.add_command(label="Save to JSON File", command=self.save_to_file)
        file_menu.add_command(label="Load from JSON File", command=self.load_from_file)
        file_menu.add_separator()
        
        # Exit
        file_menu.add_command(label="Exit", command=self.root.quit)
        
    def auto_connect_postgres(self):
        """Auto-connect to PostgreSQL on startup with default local settings"""
        try:
            if self.db_manager.connect(host="localhost", database="Cobra", user="postgres", password="", port=5432):
                self.status_var.set("Connected to PostgreSQL: Cobra on localhost:5432")
            else:
                self.status_var.set("Database not connected. Use File -> Connect to Database.")
        except Exception:
            self.status_var.set("Database connection failed. Use File -> Connect to Database.")

    def remember_project(self, name):
        """Remember a project name in the in-memory list for this session."""
        if name:
            self.memory_projects.add(name)

    def draw_grid(self):
        """Draw responsive grid lines on canvas with higher density"""
        if not hasattr(self, 'canvas') or not self.canvas:
            return
        # Clear previous grid
        self.canvas.delete("grid")

        # Use current canvas size
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width <= 1 or height <= 1:
            # Canvas not yet fully initialized; skip now
            return

        minor = 25   # minor grid spacing (more lines)
        major = 100  # major grid spacing

        # Vertical lines
        x = 0
        while x <= width:
            color = "#DADADA" if x % major != 0 else "#C0C0C0"
            self.canvas.create_line(x, 0, x, height, fill=color, tags=("grid",))
            x += minor

        # Horizontal lines
        y = 0
        while y <= height:
            color = "#DADADA" if y % major != 0 else "#C0C0C0"
            self.canvas.create_line(0, y, width, y, fill=color, tags=("grid",))
            y += minor

        # Ensure grid lines are behind all other items
        self.canvas.tag_lower("grid")
            
    def add_function(self):
        """Add a new function pill"""
        name = simpledialog.askstring("New Function", "Enter function name:", parent=self.root)
        if name:
            # Place in center of visible canvas
            x = self.canvas.winfo_width() // 2 - 60
            y = self.canvas.winfo_height() // 2 - 20
            
            pill = FunctionPill(self.canvas, x, y, name)
            self.pills.append(pill)
            self.status_var.set(f"Added function: {name}")
            
    def clear_all(self):
        """Clear all pills from canvas"""
        if messagebox.askyesno("Clear All", "Are you sure you want to clear all functions?"):
            for pill in self.pills:
                self.canvas.delete(pill.rect)
                self.canvas.delete(pill.text)
            self.pills.clear()
            self.status_var.set("Cleared all functions")
            
    def save_to_file(self):
        """Save project to JSON file"""
        from tkinter import filedialog
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            data = {
                "project": self.current_project or "Untitled",
                "functions": [pill.get_data() for pill in self.pills]
            }
            
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
                
            self.status_var.set(f"Saved to {os.path.basename(filename)}")
            
    def load_from_file(self):
        """Load project from JSON file"""
        from tkinter import filedialog
        
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            with open(filename, 'r') as f:
                data = json.load(f)
                
            self.clear_all()
            self.current_project = data.get("project", "Untitled")
            self.remember_project(self.current_project)
            
            for func_data in data.get("functions", []):
                pill = FunctionPill(
                    self.canvas,
                    func_data["x"],
                    func_data["y"],
                    func_data["name"],
                    func_data.get("function_id")
                )
                pill.inputs = func_data.get("inputs", [])
                pill.outputs = func_data.get("outputs", [])
                pill.description = func_data.get("description", "")
                pill.visual_output = func_data.get("visual_output", "")
                pill.relationships = func_data.get("relationships", "")
                self.pills.append(pill)
                
            self.status_var.set(f"Loaded from {os.path.basename(filename)}")
            
    def connect_database(self):
        """Connect to PostgreSQL database"""
        dialog = DatabaseConnectionDialog(self.root, self.db_manager)
        self.root.wait_window(dialog.window)
        
        if dialog.result:
            if self.db_manager.connect(**dialog.result):
                self.status_var.set("Connected to database")
                messagebox.showinfo("Success", "Connected to database successfully!")
            
    def save_to_database(self):
        """Save project to database"""
        if not self.db_manager.connected:
            messagebox.showwarning("Database", "Please connect to database first")
            return

        # Use existing project name if available; otherwise prompt
        if self.current_project and str(self.current_project).strip():
            project_name = str(self.current_project).strip()
        else:
            project_name = simpledialog.askstring(
                "Save Project",
                "Enter project name:",
                initialvalue=self.current_project or ""
            )
            if not project_name:
                return

        if self.db_manager.save_project(project_name, self.pills):
            self.current_project = project_name
            if hasattr(self, 'remember_project'):
                self.remember_project(self.current_project)
            self.status_var.set(f"Saved project '{project_name}' to database")
            messagebox.showinfo("Success", "Project saved successfully!")
                
    def load_from_database(self):
        """Load project from database"""
        if not self.db_manager.connected:
            messagebox.showwarning("Database", "Please connect to database first")
            return
            
        projects = self.db_manager.list_projects()
        if not projects:
            messagebox.showinfo("Database", "No projects found in database")
            return
            
        dialog = ProjectSelectionDialog(self.root, projects)
        self.root.wait_window(dialog.window)
        
        if dialog.selected_project:
            functions = self.db_manager.load_project(dialog.selected_project)
            if functions:
                self.clear_all()
                self.current_project = dialog.selected_project
                self.remember_project(self.current_project)
                
                for func_data in functions:
                    pill = FunctionPill(
                        self.canvas,
                        func_data["x"],
                        func_data["y"],
                        func_data["name"],
                        func_data["function_id"]
                    )
                    pill.inputs = func_data["inputs"]
                    pill.outputs = func_data["outputs"]
                    pill.description = func_data["description"]
                    pill.visual_output = func_data.get("visual_output", "")
                    pill.relationships = func_data.get("relationships", "")
                    self.pills.append(pill)
                    
                self.status_var.set(f"Loaded project '{dialog.selected_project}' from database")
                
    def delete_from_database(self):
        """Delete project from database"""
        if not self.db_manager.connected:
            messagebox.showwarning("Database", "Please connect to database first")
            return
            
        projects = self.db_manager.list_projects()
        if not projects:
            messagebox.showinfo("Database", "No projects found in database")
            return
            
        dialog = ProjectSelectionDialog(self.root, projects, "Delete Project")
        self.root.wait_window(dialog.window)
        
        if dialog.selected_project:
            if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete project '{dialog.selected_project}'?"):
                if self.db_manager.delete_project(dialog.selected_project):
                    self.status_var.set(f"Deleted project '{dialog.selected_project}'")
                    messagebox.showinfo("Success", "Project deleted successfully!")
                    
    def new_project(self):
        """Create a new project"""
        if self.pills and messagebox.askyesno("New Project", "Clear current project?"):
            self.clear_all()
        self.current_project = None
        self.status_var.set("New project created")
        
    def compile_architecture(self):
        """Compile architecture into GenAI prompts"""
        if not self.pills:
            messagebox.showwarning("Compile", "No functions to compile. Please add some functions first.")
            return
            
        CompileWindow(self.root, self.pills, self.current_project)
    
    def create_new_project(self):
        """Create a new project in the database"""
        if not self.db_manager.connected:
            messagebox.showwarning("Database", "Please connect to database first")
            return
            
        project_name = simpledialog.askstring("Create New Project", "Enter new project name:")
        if not project_name:
            return
            
        # Check if project already exists
        existing_projects = self.db_manager.list_projects()
        if project_name in existing_projects:
            messagebox.showwarning("Project Exists", f"Project '{project_name}' already exists!")
            return
            
        # Clear current canvas if needed
        if self.pills:
            if messagebox.askyesno("Clear Canvas", "Clear current canvas to start new project?"):
                self.clear_all()
            else:
                return
                
        # Create the project
        cursor = self.db_manager.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO projects (name) VALUES (%s)
                RETURNING id
            """, (project_name,))
            project_id = cursor.fetchone()[0]
            self.db_manager.connection.commit()

            # Ensure per-project schema exists
            self.db_manager.ensure_project_schema(project_name)
            
            self.current_project = project_name
            self.remember_project(self.current_project)
            self.status_var.set(f"Created new project: {project_name}")
            messagebox.showinfo("Success", f"Project '{project_name}' created successfully!")
            
        except Exception as e:
            self.db_manager.connection.rollback()
            messagebox.showerror("Database Error", f"Failed to create project: {str(e)}")
    
    def open_project(self):
        """Open an existing project from the database"""
        if not self.db_manager.connected:
            messagebox.showwarning("Database", "Please connect to database first")
            return
            
        projects = self.db_manager.list_projects()
        if not projects:
            messagebox.showinfo("No Projects", "No projects found in database")
            return
            
        # Clear any aborted transaction state before running subsequent queries
        try:
            self.db_manager.connection.rollback()
        except Exception:
            pass
        
        # Show project list with details
        list_window = tk.Toplevel(self.root)
        list_window.title("Open Project")
        list_window.geometry("500x400")
        
        # Title
        title_label = ttk.Label(list_window, text="Select a Project to Open", font=("Arial", 12, "bold"))
        title_label.pack(pady=10)
        
        # Projects frame
        projects_frame = ttk.Frame(list_window)
        projects_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Treeview for projects
        columns = ("Project Name", "Functions", "Created", "Updated")
        tree = ttk.Treeview(projects_frame, columns=columns, show="headings", height=15)
        
        # Define headings
        tree.heading("Project Name", text="Project Name")
        tree.heading("Functions", text="Functions")
        tree.heading("Created", text="Created")
        tree.heading("Updated", text="Updated")
        
        # Configure column widths
        tree.column("Project Name", width=150)
        tree.column("Functions", width=80)
        tree.column("Created", width=120)
        tree.column("Updated", width=120)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(projects_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack tree and scrollbar
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Get project details
        cursor = self.db_manager.connection.cursor()
        for project in projects:
            cursor.execute(
                """
                SELECT name, created_at, updated_at
                FROM projects
                WHERE name = %s
                """,
                (project,),
            )
            result = cursor.fetchone()
            if result:
                name, created, updated = result
                try:
                    count = self.db_manager.count_functions_in_project(name)
                except Exception:
                    # Defensive: clear any aborted transaction and default to 0
                    try:
                        self.db_manager.connection.rollback()
                    except Exception:
                        pass
                    count = 0
                created_str = created.strftime("%Y-%m-%d %H:%M") if created else ""
                updated_str = updated.strftime("%Y-%m-%d %H:%M") if updated else ""
                tree.insert("", tk.END, values=(name, count, created_str, updated_str))
        
        # Buttons
        button_frame = ttk.Frame(list_window)
        button_frame.pack(pady=10)
        
        def open_selected():
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                project_name = item['values'][0]
                list_window.destroy()
                
                # Load the selected project
                functions = self.db_manager.load_project(project_name)
                if functions is not None:
                    self.clear_all()
                    self.current_project = project_name
                    self.remember_project(self.current_project)
                    
                    for func_data in functions:
                        pill = FunctionPill(
                            self.canvas,
                            func_data["x"],
                            func_data["y"],
                            func_data["name"],
                            func_data["function_id"]
                        )
                        pill.inputs = func_data["inputs"]
                        pill.outputs = func_data["outputs"]
                        pill.description = func_data["description"]
                        pill.visual_output = func_data.get("visual_output", "")
                        pill.relationships = func_data.get("relationships", "")
                        self.pills.append(pill)
                        
                    self.status_var.set(f"Opened project: {project_name}")
                    messagebox.showinfo("Success", f"Project '{project_name}' opened successfully!")
        
        # Allow double-click on a project row to open it
        def on_tree_double_click(event):
            item_id = tree.identify_row(event.y)
            if item_id:
                tree.selection_set(item_id)
                open_selected()
        tree.bind("<Double-Button-1>", on_tree_double_click)

        def remove_selected():
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                project_name = item['values'][0]
                confirm_msg = (
                    f"Are you sure you want to remove project '{project_name}' from the database?\n\n"
                    "This will permanently delete:\n"
                    "- The project\n"
                    "- All functions in the project\n"
                    "- All inputs and outputs\n\n"
                    "This action cannot be undone!"
                )
                if messagebox.askyesno("Remove Project", confirm_msg, icon='warning'):
                    try:
                        if self.db_manager.delete_project(project_name):
                            if self.current_project == project_name:
                                self.clear_all()
                                self.current_project = None
                            if hasattr(self, 'memory_projects'):
                                self.memory_projects.discard(project_name)
                            tree.delete(selection[0])
                            self.status_var.set(f"Removed project: {project_name}")
                            messagebox.showinfo("Success", f"Project '{project_name}' removed successfully!")
                    except Exception as e:
                        try:
                            self.db_manager.connection.rollback()
                        except Exception:
                            pass
                        messagebox.showerror("Database Error", f"Failed to remove: {str(e)}")

        ttk.Button(button_frame, text="Open", command=open_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Remove", command=remove_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=list_window.destroy).pack(side=tk.LEFT, padx=5)
    
    def cancel_project(self):
        """Cancel/delete a project via a selection dialog from in-memory list."""
        if not self.db_manager.connected:
            messagebox.showwarning("Database", "Please connect to database first")
            return

        # Build in-memory list of projects for this session
        mem_projects = set(self.memory_projects)
        if self.current_project:
            mem_projects.add(self.current_project)
        mem_projects = sorted(mem_projects)

        if not mem_projects:
            messagebox.showinfo("No Projects", "No projects tracked in memory for this session")
            return

        # Create selection window similar to Open Project
        list_window = tk.Toplevel(self.root)
        list_window.title("Cancel Project")
        list_window.geometry("520x420")

        ttk.Label(list_window, text="Select a Project to Cancel", font=("Arial", 12, "bold")).pack(pady=10)

        projects_frame = ttk.Frame(list_window)
        projects_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ("Project Name", "Functions", "Created", "Updated", "Status")
        tree = ttk.Treeview(projects_frame, columns=columns, show="headings", height=15)

        for col, text in zip(columns, ("Project Name", "Functions", "Created", "Updated", "Status")):
            tree.heading(col, text=text)
        tree.column("Project Name", width=160)
        tree.column("Functions", width=80)
        tree.column("Created", width=120)
        tree.column("Updated", width=120)
        tree.column("Status", width=100)

        scrollbar = ttk.Scrollbar(projects_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Helper to check existence in DB
        cursor = self.db_manager.connection.cursor()
        existing_set = set(self.db_manager.list_projects())

        def add_row(name):
            exists = name in existing_set
            created_str = updated_str = ""
            count = 0
            status = "Available" if exists else "Unavailable"
            if exists:
                try:
                    cursor.execute(
                        """
                        SELECT created_at, updated_at FROM projects WHERE name = %s
                        """,
                        (name,),
                    )
                    row = cursor.fetchone()
                    if row:
                        created, updated = row
                        created_str = created.strftime("%Y-%m-%d %H:%M") if created else ""
                        updated_str = updated.strftime("%Y-%m-%d %H:%M") if updated else ""
                    count = self.db_manager.count_functions_in_project(name)
                except Exception:
                    try:
                        self.db_manager.connection.rollback()
                    except Exception:
                        pass
            tree.insert("", tk.END, values=(name, count, created_str, updated_str, status))

        for name in mem_projects:
            add_row(name)

        button_frame = ttk.Frame(list_window)
        button_frame.pack(pady=10)

        def cancel_selected():
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a project")
                return
            item = tree.item(selection[0])
            name = item['values'][0]
            status = item['values'][4] if len(item['values']) > 4 else ""

            if status == "Unavailable":
                # Project is not found in DB
                if messagebox.askyesno(
                    "Project Not Found",
                    "Project unavailable not found, or was deleted,would you like to remove from this list",
                ):
                    # Remove from in-memory list and tree
                    if name in self.memory_projects:
                        self.memory_projects.remove(name)
                    if name == self.current_project:
                        # If current project is missing and removed, clear UI state
                        self.clear_all()
                        self.current_project = None
                    tree.delete(selection[0])
            else:
                # Confirm deletion from DB
                confirm_msg = (
                    f"Are you sure you want to cancel (delete) the project '{name}'?\n\n"
                    "This will permanently delete:\n"
                    "- The project\n"
                    "- All functions in the project\n"
                    "- All inputs and outputs\n\n"
                    "This action cannot be undone!"
                )
                if messagebox.askyesno("Cancel Project", confirm_msg, icon='warning'):
                    if self.db_manager.delete_project(name):
                        # Update UI and memory
                        if name == self.current_project:
                            self.clear_all()
                            self.current_project = None
                        if name in self.memory_projects:
                            self.memory_projects.remove(name)
                        tree.delete(selection[0])
                        self.status_var.set(f"Cancelled project: {name}")
                        messagebox.showinfo("Success", f"Project '{name}' has been cancelled (deleted)")

        ttk.Button(button_frame, text="Cancel Selected", command=cancel_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=list_window.destroy).pack(side=tk.LEFT, padx=5)

        # Double-click to cancel
        def on_tree_double_click(event):
            item_id = tree.identify_row(event.y)
            if item_id:
                tree.selection_set(item_id)
                cancel_selected()
        tree.bind("<Double-Button-1>", on_tree_double_click)
    
    def save_project(self):
        """Save the current project to database"""
        if not self.db_manager.connected:
            messagebox.showwarning("Database", "Please connect to database first")
            return
            
        if not self.current_project:
            project_name = simpledialog.askstring(
                "Save Project",
                "Enter project name:"
            )
            if not project_name:
                return
            self.current_project = project_name
            
        if self.db_manager.save_project(self.current_project, self.pills):
            self.remember_project(self.current_project)
            self.status_var.set(f"Saved project '{self.current_project}'")
            messagebox.showinfo("Success", f"Project '{self.current_project}' saved successfully!")
    
    def update_connect_project(self):
        """Update or connect to an existing project"""
        if not self.db_manager.connected:
            messagebox.showwarning("Database", "Please connect to database first")
            return
            
        projects = self.db_manager.list_projects()
        if not projects:
            messagebox.showinfo("No Projects", "No projects found in database")
            return
            
        # Create selection dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Update/Connect to Project")
        dialog.geometry("400x500")
        
        # Project selection
        ttk.Label(dialog, text="Select a project to connect to:").pack(pady=10)
        
        listbox_frame = ttk.Frame(dialog)
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        
        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        for project in projects:
            listbox.insert(tk.END, project)
            
        # Options frame
        options_frame = ttk.LabelFrame(dialog, text="Options", padding="10")
        options_frame.pack(fill=tk.X, padx=10, pady=10)
        
        load_var = tk.BooleanVar(value=True)
        ttk.Radiobutton(options_frame, text="Load project (replace current canvas)", 
                       variable=load_var, value=True).pack(anchor=tk.W)
        ttk.Radiobutton(options_frame, text="Connect only (keep current canvas)", 
                       variable=load_var, value=False).pack(anchor=tk.W)
        
        def connect_to_project():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a project")
                return
                
            selected_project = listbox.get(selection[0])
            
            if load_var.get():
                # Load the project
                functions = self.db_manager.load_project(selected_project)
                if functions:
                    self.clear_all()
                    self.current_project = selected_project
                    self.remember_project(self.current_project)
                    
                    for func_data in functions:
                        pill = FunctionPill(
                            self.canvas,
                            func_data["x"],
                            func_data["y"],
                            func_data["name"],
                            func_data["function_id"]
                        )
                        pill.inputs = func_data["inputs"]
                        pill.outputs = func_data["outputs"]
                        pill.description = func_data["description"]
                        pill.visual_output = func_data.get("visual_output", "")
                        pill.relationships = func_data.get("relationships", "")
                        self.pills.append(pill)
                        
                    self.status_var.set(f"Loaded project: {selected_project}")
                    messagebox.showinfo("Success", f"Project '{selected_project}' loaded successfully!")
            else:
                # Just connect to the project
                self.current_project = selected_project
                self.remember_project(self.current_project)
                self.status_var.set(f"Connected to project: {selected_project}")
                messagebox.showinfo("Success", f"Connected to project '{selected_project}'")
                
            dialog.destroy()
            
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Connect", command=connect_to_project).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def delete_project(self):
        """Delete a project from the database"""
        if not self.db_manager.connected:
            messagebox.showwarning("Database", "Please connect to database first")
            return
            
        projects = self.db_manager.list_projects()
        if not projects:
            messagebox.showinfo("No Projects", "No projects found in database")
            return
            
        dialog = ProjectSelectionDialog(self.root, projects, "Delete Project")
        self.root.wait_window(dialog.window)
        
        if dialog.selected_project:
            # Extra confirmation for deletion
            confirm_msg = f"Are you sure you want to delete project '{dialog.selected_project}'?\n\n"
            confirm_msg += "This will permanently delete:\n"
            confirm_msg += "- The project\n"
            confirm_msg += "- All functions in the project\n"
            confirm_msg += "- All inputs and outputs\n\n"
            confirm_msg += "This action cannot be undone!"
            
            if messagebox.askyesno("Confirm Delete", confirm_msg, icon='warning'):
                if self.db_manager.delete_project(dialog.selected_project):
                    # Clear canvas if it was the current project
                    if self.current_project == dialog.selected_project:
                        self.clear_all()
                        self.current_project = None
                        
                    self.status_var.set(f"Deleted project: {dialog.selected_project}")
                    messagebox.showinfo("Success", f"Project '{dialog.selected_project}' deleted successfully!")
    
    def list_all_projects(self):
        """List all projects in the database"""
        if not self.db_manager.connected:
            messagebox.showwarning("Database", "Please connect to database first")
            return
            
        projects = self.db_manager.list_projects()
        if not projects:
            messagebox.showinfo("No Projects", "No projects found in database")
            return
            
        # Create a window to display projects
        list_window = tk.Toplevel(self.root)
        list_window.title("All Projects")
        list_window.geometry("500x400")
        
        # Title
        title_label = ttk.Label(list_window, text="Projects in Database", font=("Arial", 12, "bold"))
        title_label.pack(pady=10)
        
        # Current project label
        if self.current_project:
            current_label = ttk.Label(list_window, text=f"Current Project: {self.current_project}", 
                                    font=("Arial", 10, "italic"))
            current_label.pack()
        
        # Projects frame
        projects_frame = ttk.Frame(list_window)
        projects_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Treeview for projects
        columns = ("Project Name", "Functions", "Created", "Updated")
        tree = ttk.Treeview(projects_frame, columns=columns, show="headings", height=15)
        
        # Define headings
        tree.heading("Project Name", text="Project Name")
        tree.heading("Functions", text="Functions")
        tree.heading("Created", text="Created")
        tree.heading("Updated", text="Updated")
        
        # Configure column widths
        tree.column("Project Name", width=150)
        tree.column("Functions", width=80)
        tree.column("Created", width=120)
        tree.column("Updated", width=120)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(projects_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack tree and scrollbar
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Get project details
        cursor = self.db_manager.connection.cursor()
        for project in projects:
            cursor.execute(
                """
                SELECT name, created_at, updated_at
                FROM projects
                WHERE name = %s
                """,
                (project,),
            )
            result = cursor.fetchone()
            if result:
                name, created, updated = result
                count = self.db_manager.count_functions_in_project(name)
                created_str = created.strftime("%Y-%m-%d %H:%M") if created else ""
                updated_str = updated.strftime("%Y-%m-%d %H:%M") if updated else ""
                
                # Highlight current project
                tags = ('current',) if name == self.current_project else ()
                tree.insert("", tk.END, values=(name, count, created_str, updated_str), tags=tags)
        
        # Configure tag for current project
        tree.tag_configure('current', background='lightblue')
        
        # Buttons
        button_frame = ttk.Frame(list_window)
        button_frame.pack(pady=10)
        
        def load_selected():
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                project_name = item['values'][0]
                list_window.destroy()
                
                # Load the selected project
                functions = self.db_manager.load_project(project_name)
                if functions:
                    self.clear_all()
                    self.current_project = project_name
                    self.remember_project(self.current_project)
                    
                    for func_data in functions:
                        pill = FunctionPill(
                            self.canvas,
                            func_data["x"],
                            func_data["y"],
                            func_data["name"],
                            func_data["function_id"]
                        )
                        pill.inputs = func_data["inputs"]
                        pill.outputs = func_data["outputs"]
                        pill.description = func_data["description"]
                        pill.visual_output = func_data.get("visual_output", "")
                        pill.relationships = func_data.get("relationships", "")
                        self.pills.append(pill)
                        
                    self.status_var.set(f"Loaded project: {project_name}")
        
        ttk.Button(button_frame, text="Load Selected", command=load_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=list_window.destroy).pack(side=tk.LEFT, padx=5)
    
    def show_flow_output(self):
        """Show visual flow output of the project"""
        # Check if project is saved
        if not self.current_project:
            messagebox.showwarning("Save Project", "Please save your project first to view the flow output.")
            return
            
        if not self.pills:
            messagebox.showinfo("No Functions", "No functions to display. Please add some functions first.")
            return
            
        # Create flow output window
        FlowOutputWindow(self.root, self.pills, self.current_project)
    
    def show_logical_mapping(self):
        """Open a popup to visualize logical relationships between functions with arrows."""
        if not self.pills:
            messagebox.showinfo("No Functions", "No functions to display. Please add some functions first.")
            return

        # Prepare data
        pills = self.pills
        project_name = self.current_project or "Untitled"

        # Build name mapping (case-insensitive)
        name_to_pill = {}
        for p in pills:
            name_to_pill[p.name.strip().lower()] = p

        # Build edges from explicit Relationships: "Related to: A, B" and from outputs->inputs matches
        edges = set()  # tuples (src_name, dst_name)
        # Parse explicit relationships
        for p in pills:
            rel = (p.relationships or "").splitlines()
            targets = []
            for line in rel:
                if line.strip().lower().startswith("related to:"):
                    rest = line.split(":", 1)[1]
                    targets.extend([t.strip() for t in rest.split(",") if t.strip()])
            for t in targets:
                key = t.strip().lower()
                if key in name_to_pill and name_to_pill[key] is not p:
                    edges.add((p.name, name_to_pill[key].name))
        # Infer relationships from outputs -> inputs
        for p in pills:
            out_set = set([o.strip() for o in (p.outputs or []) if str(o).strip()])
            if not out_set:
                continue
            for q in pills:
                if p is q:
                    continue
                in_set = set([i.strip() for i in (q.inputs or []) if str(i).strip()])
                if out_set & in_set:
                    edges.add((p.name, q.name))

        # Layout nodes on a circle
        names = [p.name for p in pills]
        n = len(names)
        width, height = 1200, 900
        cx, cy = width // 2, height // 2
        r = max(200, min(350, int(100 + 30 * n)))
        positions = {}
        for idx, name in enumerate(names):
            angle = 2 * math.pi * idx / max(1, n)
            x = cx + int(r * math.cos(angle))
            y = cy + int(r * math.sin(angle))
            positions[name] = (x, y)

        # Create window
        win = tk.Toplevel(self.root)
        win.title(f"Logical Mapping - {project_name}")
        win.geometry("1000x750")

        main = ttk.Frame(win)
        main.pack(fill=tk.BOTH, expand=True)

        # Canvas with scrollbars
        canvas_frame = ttk.Frame(main)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        hscroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        vscroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        canvas = tk.Canvas(canvas_frame, bg="white", xscrollcommand=hscroll.set, yscrollcommand=vscroll.set)
        hscroll.config(command=canvas.xview)
        vscroll.config(command=canvas.yview)
        canvas.grid(row=0, column=0, sticky="nsew")
        vscroll.grid(row=0, column=1, sticky="ns")
        hscroll.grid(row=1, column=0, sticky="ew")
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

        # Draw nodes
        node_w, node_h = 140, 48
        node_fill = "#4A90E2"
        node_outline = "#2E5C8A"
        text_fill = "white"
        for name in names:
            x, y = positions[name]
            x0, y0, x1, y1 = x - node_w // 2, y - node_h // 2, x + node_w // 2, y + node_h // 2
            canvas.create_rectangle(x0, y0, x1, y1, fill=node_fill, outline=node_outline, width=2)
            canvas.create_text(x, y, text=name, fill=text_fill, font=("Arial", 10, "bold"))

        # Draw arrows
        def _shorten(xa, ya, xb, yb, shrink=30):
            # Move endpoints inward to avoid covering node boxes
            vx, vy = xb - xa, yb - ya
            dist = (vx * vx + vy * vy) ** 0.5 or 1
            ux, uy = vx / dist, vy / dist
            return xa + int(ux * shrink), ya + int(uy * shrink), xb - int(ux * shrink), yb - int(uy * shrink)

        for src, dst in sorted(edges):
            if src not in positions or dst not in positions:
                continue
            x0, y0 = positions[src]
            x1, y1 = positions[dst]
            sx, sy, ex, ey = _shorten(x0, y0, x1, y1)
            canvas.create_line(sx, sy, ex, ey, arrow=tk.LAST, width=2, fill="#444", smooth=True)

        # Set scroll region
        canvas.configure(scrollregion=(0, 0, width, height))

        # Controls
        btns = ttk.Frame(main)
        btns.pack(fill=tk.X, pady=6)
        ttk.Button(btns, text="Close", command=win.destroy).pack(side=tk.RIGHT, padx=6)

    def show_instructions(self):
        """Show instructions window"""
        instructions_window = tk.Toplevel(self.root)
        instructions_window.title("Architecture Mapper - Instructions")
        instructions_window.geometry("700x600")
        
        # Create a scrollable text widget
        main_frame = ttk.Frame(instructions_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="How to Use Architecture Mapper", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Create text widget with scrollbar
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        instructions_text = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set,
                                   font=("Arial", 10), padx=10, pady=10)
        instructions_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=instructions_text.yview)
        
        # Instructions content
        instructions = """
ARCHITECTURE MAPPER - USER GUIDE

Welcome to Architecture Mapper! This tool helps you visually design and document application architectures.

=== GETTING STARTED ===

1. CONNECT TO DATABASE
   • Go to File → Connect to Database
   • Enter your PostgreSQL connection details
   • Default database name: Cobra
   • The app will create necessary tables automatically

2. CREATE A NEW PROJECT
   • File → Create New Project
   • Enter a unique project name
   • Your project is now ready for designing!

=== WORKING WITH FUNCTIONS ===

1. ADD FUNCTIONS
   • Click "Add Function" button
   • Enter a function name
   • A blue pill appears on the canvas

2. MOVE FUNCTIONS
   • Click and drag any function pill to reposition it
   • The status bar shows current position
   • Positions are automatically saved with the project

3. EDIT FUNCTION DETAILS
   • Double-click any function pill
   • In the detail window you can:
     - Change the function name
     - Add a description
     - Add inputs (left column)
     - Add outputs (right column)
     - Add visual output notes
     - Define relationships
   • Click "Save" to apply changes

4. DATABASE OPERATIONS (in detail window)
   • Save to DB: Save as new function
   • Update in DB: Update existing function
   • Delete from DB: Remove function
   • Load from DB: Load another function's details

=== PROJECT MANAGEMENT ===

1. SAVE YOUR WORK
   • File → Save Project
   • Saves all functions and their positions
   • Updates are automatic when project exists

2. OPEN EXISTING PROJECT
   • File → Open Project
   • Shows all projects with details
   • Double-click or select and click "Open"

3. CANCEL (DELETE) PROJECT
   • File → Cancel Project
   • Permanently deletes the current project
   • Requires confirmation

=== ADDITIONAL FEATURES ===

1. COMPILE TO AI PROMPTS
   • Click "Compile" button
   • Generates AI-ready prompts from your architecture
   • Options to include/exclude various details
   • Can copy to clipboard or save to file

2. JSON EXPORT/IMPORT
   • File → Save to JSON File: Backup your project
   • File → Load from JSON File: Restore from backup
   • Useful for sharing or version control

3. CLEAR CANVAS
   • "Clear All" button removes all functions
   • Requires confirmation
   • Does not affect saved data

=== TIPS & BEST PRACTICES ===

• VISUAL ORGANIZATION: Arrange functions logically
  - Input functions on the left
  - Processing in the middle
  - Output functions on the right

• NAMING CONVENTIONS: Use clear, descriptive names
  - getUserInput, processData, generateReport

• INPUT/OUTPUT MATCHING: When outputs match inputs
  - The Compile feature will detect data flow
  - Shows relationships in generated prompts

• REGULAR SAVES: Save your project frequently
  - Preserves positions and all details
  - Protects against accidental loss

• PROJECT STRUCTURE: One project per application
  - Keep related functions together
  - Use separate projects for different apps

=== KEYBOARD SHORTCUTS ===

• Double-click: Open function details
• Drag: Move functions around
• Enter: Confirm dialogs

=== TROUBLESHOOTING ===

• CAN'T CONNECT TO DATABASE?
  - Ensure PostgreSQL is running
  - Check connection details
  - Verify user permissions

• FUNCTIONS NOT SAVING?
  - Ensure you're connected to database
  - Check that project is created/selected
  - Look for error messages

• LOST YOUR WORK?
  - Check File → Open Project
  - Look for JSON backups
  - Functions may be in database

=== NEED HELP? ===

This tool is designed to be intuitive. If you encounter issues:
1. Check the status bar for messages
2. Ensure database connection is active
3. Save your work frequently

Happy Architecture Mapping!
"""
        
        # Insert instructions
        instructions = """
Cobra Architecture Mapper - Updated User Guide

Overview
- Visual canvas with a responsive grid (minor lines every 25px, major every 100px). Grid redraws on window resize.
- Top toolbar provides quick actions; a Cobra logo is shown at the top-left (requires Pillow to display JPEG).
- Double-click a function pill to edit details, including inputs, outputs, description, visual output and relationships.
- Data can be saved/loaded via JSON files or persisted in PostgreSQL per-project schemas.

Getting Started
1) Add Function
   - Click "Add Function". A pill is placed roughly at the canvas center.
   - Drag to reposition; the status bar shows coordinates when moving.
   - Double-click the pill to open the details dialog.

2) Edit Details (Double-click a pill)
   - Name: Title of the function.
   - Description: Free-form text of what the function does.
   - Inputs / Outputs: Use Add/Edit/Delete to manage lists.
   - Visual Output: Any intended UI/graphical output description.
   - Relationships: 
       • Click the label or double-click the text box to open a selector.
       • Pick related functions from the current project and add an explanation.
       • The dialog pre-selects any existing relationships, and prevents self-reference.

3) Canvas and Grid
   - The background grid is denser for easier alignment.
   - Grid updates automatically on resize and always covers the visible area.

4) Project Persistence
   - Database connection:
       • The app attempts auto-connect to PostgreSQL at startup (localhost:5432, database "Cobra", user "postgres").
       • If auto-connect fails, use File → Connect to Database and provide credentials. The app can create the DB if missing.
   - Create New Project: Creates a catalog row and ensures a per-project schema with tables (functions, inputs, outputs).
   - Save Project: Persists all pills to the current project schema. If no current project name exists, you will be prompted.
   - Open Project: Lists projects with created/updated timestamps and function counts, and loads selected project.
   - Delete/Cancel Project:
       • Delete Project: Removes a project and its schema from the DB (irreversible).
       • Cancel Project: Lets you delete from DB or remove unavailable entries tracked in memory this session.
   - Update/Connect to Project: Optionally load or just switch current project context without reloading the canvas.

5) File Save/Load
   - Save to JSON File: Exports the current canvas and pill definitions (including positions and details).
   - Load from JSON File: Clears current canvas and loads pills from a JSON file, rehydrating details and positions.

6) Compile and Logical Mapping
   - Compile: Generates a compiled representation/prompts based on the current canvas (ensure pills are defined).
   - Logical Mapping: Produces a higher-level mapping view of the current architecture.

7) Flow Output
   - Provides a synthesized/aggregated output view derived from the defined functions and their properties.

Tips
- Window/Icon: The toolbar logo loads from cobraimage.jpeg in the app folder. JPEG requires Pillow. If Pillow is not installed, a text fallback is shown.
- Drag and Drop: Use the status bar as a quick reference for precise placement.
- Relationships: Use the selector dialog for consistency and to avoid manual text errors.
- Database Safety: Some DB errors can put the session in an aborted state; the app automatically rolls back as needed.

Troubleshooting
- Logo not showing:
   • Install Pillow (e.g., `python -m pip install Pillow`) or convert the logo to PNG and adjust loading if needed.
- PostgreSQL not reachable:
   • Use File → Connect to Database and verify host/port/credentials; the app can create the "Cobra" DB if missing.
- No functions listed:
   • Ensure you saved the project to DB or loaded a JSON with functions; otherwise add functions first.
"""
        instructions_text.insert("1.0", instructions)
        instructions_text.config(state=tk.DISABLED)  # Make read-only
        
        # Close button
        close_button = ttk.Button(main_frame, text="Close", 
                                 command=instructions_window.destroy)
        close_button.pack(pady=10)
        
        # Make window modal
        instructions_window.transient(self.root)
        instructions_window.grab_set()

class DatabaseConnectionDialog:
    """Dialog for database connection"""
    def __init__(self, parent, db_manager=None):
        self.window = tk.Toplevel(parent)
        self.window.title("Connect to PostgreSQL")
        self.window.geometry("400x250")
        self.result = None
        self.db_manager = db_manager
        
        # Form fields with defaults
        fields = [
            ("Host:", "localhost"),
            ("Port:", "5432"),
            ("Database:", "Cobra"),
            ("Username:", "postgres"),
            ("Password:", "")
        ]
        
        # Override defaults with saved connection info if available
        if db_manager and db_manager.last_connection_info:
            saved_info = db_manager.last_connection_info
            fields = [
                ("Host:", saved_info.get("host", "localhost")),
                ("Port:", str(saved_info.get("port", "5432"))),
                ("Database:", saved_info.get("database", "Cobra")),
                ("Username:", saved_info.get("user", "postgres")),
                ("Password:", "")  # Never save password
            ]
        
        self.entries = {}
        
        for i, (label, default) in enumerate(fields):
            ttk.Label(self.window, text=label).grid(row=i, column=0, sticky=tk.W, padx=10, pady=5)
            
            if label == "Password:":
                entry = ttk.Entry(self.window, show="*")
            else:
                entry = ttk.Entry(self.window)
                
            entry.insert(0, default)
            entry.grid(row=i, column=1, sticky=(tk.W, tk.E), padx=10, pady=5)
            self.entries[label.lower().rstrip(":")] = entry
            
        # Buttons
        button_frame = ttk.Frame(self.window)
        button_frame.grid(row=len(fields), column=0, columnspan=2, pady=20)
        
        ttk.Button(button_frame, text="Connect", command=self.connect).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.window.destroy).pack(side=tk.LEFT, padx=5)
        
        self.window.columnconfigure(1, weight=1)
        
    def connect(self):
        """Handle connection"""
        self.result = {
            "host": self.entries["host"].get(),
            "port": int(self.entries["port"].get()),
            "database": self.entries["database"].get(),
            "user": self.entries["username"].get(),
            "password": self.entries["password"].get()
        }
        self.window.destroy()

class ProjectSelectionDialog:
    """Dialog for selecting a project"""
    def __init__(self, parent, projects, title="Select Project"):
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.geometry("400x300")
        self.selected_project = None
        
        # Label
        ttk.Label(self.window, text="Select a project:").pack(pady=10)
        
        # Listbox with scrollbar
        listbox_frame = ttk.Frame(self.window)
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        # Populate listbox
        for project in projects:
            self.listbox.insert(tk.END, project)
            
        # Buttons
        button_frame = ttk.Frame(self.window)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Select", command=self.select_project).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.window.destroy).pack(side=tk.LEFT, padx=5)
        
        # Bind double-click
        self.listbox.bind("<Double-Button-1>", lambda e: self.select_project())
        
    def select_project(self):
        """Handle project selection"""
        selection = self.listbox.curselection()
        if selection:
            self.selected_project = self.listbox.get(selection[0])
            self.window.destroy()

class CompileWindow:
    """Window for compiling architecture into GenAI prompts"""
    def __init__(self, parent, pills, project_name):
        self.pills = pills
        self.project_name = project_name or "Untitled Project"
        
        self.window = tk.Toplevel(parent)
        self.window.title("Compile Architecture to GenAI Prompts")
        self.window.geometry("800x600")
        
        # Main frame
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Generated GenAI Prompts", font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Options frame
        options_frame = ttk.LabelFrame(main_frame, text="Compilation Options", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Checkboxes for options
        self.include_descriptions = tk.BooleanVar(value=True)
        self.include_io_details = tk.BooleanVar(value=True)
        self.include_relationships = tk.BooleanVar(value=True)
        self.include_implementation = tk.BooleanVar(value=True)
        
        ttk.Checkbutton(options_frame, text="Include function descriptions", 
                       variable=self.include_descriptions).grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Checkbutton(options_frame, text="Include input/output details", 
                       variable=self.include_io_details).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Checkbutton(options_frame, text="Analyze relationships between functions", 
                       variable=self.include_relationships).grid(row=1, column=0, sticky=tk.W, padx=5)
        ttk.Checkbutton(options_frame, text="Generate implementation suggestions", 
                       variable=self.include_implementation).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        # Generate button
        ttk.Button(options_frame, text="Generate Prompts", command=self.generate_prompts).grid(row=2, column=0, columnspan=2, pady=10)
        
        # Text area for prompts
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Text widget
        self.prompt_text = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set, 
                                  font=("Courier", 10))
        self.prompt_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.prompt_text.yview)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="Copy to Clipboard", command=self.copy_to_clipboard).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save to File", command=self.save_prompts).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Generate initial prompts
        self.generate_prompts()
        
    def analyze_relationships(self):
        """Analyze relationships between functions based on inputs/outputs"""
        relationships = []
        
        for i, pill1 in enumerate(self.pills):
            for j, pill2 in enumerate(self.pills):
                if i != j:
                    # Check if any output of pill1 matches any input of pill2
                    for output in pill1.outputs:
                        if output in pill2.inputs:
                            relationships.append({
                                "from": pill1.name,
                                "to": pill2.name,
                                "connection": output
                            })
                            
        return relationships
        
    def generate_prompts(self):
        """Generate GenAI prompts from the architecture"""
        self.prompt_text.delete("1.0", tk.END)
        
        # Build unique pill list by name (case-insensitive) to prevent duplicate sections
        unique_pills = []
        _seen = set()
        for p in self.pills:
            k = (p.name or "").strip().lower()
            if k and k not in _seen:
                _seen.add(k)
                unique_pills.append(p)
        # Fallback: if names are empty, keep original order
        if not unique_pills:
            unique_pills = list(self.pills)

        prompts = []
        
        # Project overview
        prompts.append(f"# {self.project_name} - Application Architecture\n")
        prompts.append(f"This application consists of {len(unique_pills)} main functions/components.\n")
        
        # Function overview
        prompts.append("\n## Functions Overview:\n")
        relationships_section_added = False
        for i, pill in enumerate(unique_pills, 1):
            prompts.append(f"{i}. **{pill.name}**")
            if self.include_descriptions.get() and pill.description:
                prompts.append(f"   - Description: {pill.description}")
            if self.include_io_details.get():
                if pill.inputs:
                    prompts.append(f"   - Inputs: {', '.join(pill.inputs)}")
                if pill.outputs:
                    prompts.append(f"   - Outputs: {', '.join(pill.outputs)}")
            prompts.append("")
            
        # Relationships
        if self.include_relationships.get():
            relationships = self.analyze_relationships()
            if relationships and not relationships_section_added:
                prompts.append("\n## Function Relationships:\n")
                prompts.append("The following data flow relationships exist between functions:\n")
                for rel in relationships:
                    prompts.append(f"- {rel['from']} → {rel['to']} (via: {rel['connection']})")
                prompts.append("")
                relationships_section_added = True
                
        # GenAI Prompts section
        prompts.append("\n## GenAI Implementation Prompts:\n")
        
        # Overall architecture prompt
        prompts.append("### 1. Overall Architecture Implementation:\n")
        prompts.append("```")
        prompts.append(f"Create a {self.project_name} application with the following architecture:")
        prompts.append(f"- Total functions: {len(self.pills)}")
        
        function_list = []
        for pill in unique_pills:
            func_desc = f"{pill.name}"
            if pill.inputs:
                func_desc += f" (inputs: {', '.join(pill.inputs)})"
            if pill.outputs:
                func_desc += f" (outputs: {', '.join(pill.outputs)})"
            function_list.append(func_desc)
            
        prompts.append("- Functions: " + ", ".join(function_list))
        prompts.append("\nEnsure proper data flow between functions and implement error handling.")
        prompts.append("```\n")
        
        # Individual function prompts
        if self.include_implementation.get():
            prompts.append("### 2. Individual Function Implementation Prompts:\n")
            
            for pill in unique_pills:
                prompts.append(f"#### Function: {pill.name}\n")
                prompts.append("```")
                prompts.append(f"Implement a function called '{pill.name}' that:")
                
                if pill.description:
                    prompts.append(f"- Purpose: {pill.description}")
                    
                if pill.inputs:
                    prompts.append(f"- Accepts the following inputs: {', '.join(pill.inputs)}")
                    prompts.append("- Validates all inputs appropriately")
                    
                if pill.outputs:
                    prompts.append(f"- Produces the following outputs: {', '.join(pill.outputs)}")
                    prompts.append("- Ensures outputs are properly formatted and validated")
                    
                prompts.append("\nInclude appropriate error handling and logging.")
                prompts.append("```\n")
                
        # Integration prompt
        prompts.append("### 3. Integration Prompt:\n")
        prompts.append("```")
        prompts.append("Integrate all the above functions into a cohesive application where:")
        
        relationships = self.analyze_relationships()
        if relationships:
            prompts.append("\nData flows:")
            for rel in relationships:
                prompts.append(f"- {rel['from']} sends '{rel['connection']}' to {rel['to']}")
                
        prompts.append("\nEnsure:")
        prompts.append("- All functions can communicate as needed")
        prompts.append("- Error handling is consistent across the application")
        prompts.append("- The application follows best practices for the chosen technology stack")
        prompts.append("```\n")
        
        # Testing prompt
        prompts.append("### 4. Testing Prompt:\n")
        prompts.append("```")
        prompts.append("Create comprehensive tests for the application including:")
        prompts.append("- Unit tests for each function")
        prompts.append("- Integration tests for data flow between functions")
        prompts.append("- Edge case handling")
        prompts.append("- Input validation tests")
        prompts.append("```\n")
        
        # Insert all prompts into text widget
        text = "\n".join(prompts)
        # Deduplicate paragraphs while preserving order
        paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
        seen = set()
        deduped = []
        for p in paragraphs:
            key = re.sub(r"\s+", " ", p.strip())
            if key not in seen:
                seen.add(key)
                deduped.append(p)
        deduped_text = "\n\n".join(deduped)
        self.prompt_text.insert("1.0", deduped_text)
        
    def copy_to_clipboard(self):
        """Copy prompts to clipboard"""
        content = self.prompt_text.get("1.0", tk.END).strip()
        self.window.clipboard_clear()
        self.window.clipboard_append(content)
        messagebox.showinfo("Success", "Prompts copied to clipboard!")
        
    def save_prompts(self):
        """Save prompts to file"""
        from tkinter import filedialog
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            content = self.prompt_text.get("1.0", tk.END).strip()
            with open(filename, 'w') as f:
                f.write(content)
            messagebox.showinfo("Success", f"Prompts saved to {os.path.basename(filename)}")

class FlowOutputWindow:
    """Window for displaying visual flow output of the project"""
    def __init__(self, parent, pills, project_name):
        self.pills = pills
        self.project_name = project_name
        
        self.window = tk.Toplevel(parent)
        self.window.title(f"Flow Output - {project_name}")
        self.window.geometry("900x700")
        
        # Main frame
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text=f"Project Flow: {project_name}", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 10))
        
        # Canvas for flow diagram
        canvas_frame = ttk.Frame(main_frame, relief=tk.SUNKEN, borderwidth=2)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create canvas with scrollbars
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.canvas = tk.Canvas(canvas_frame, bg="white", 
                               xscrollcommand=h_scrollbar.set,
                               yscrollcommand=v_scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        h_scrollbar.config(command=self.canvas.xview)
        v_scrollbar.config(command=self.canvas.yview)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="Export as Image", command=self.export_image).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Copy Flow Description", command=self.copy_description).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Legend frame
        legend_frame = ttk.LabelFrame(button_frame, text="Legend", padding="5")
        legend_frame.pack(side=tk.LEFT, padx=20)
        
        ttk.Label(legend_frame, text="● Function", foreground="#4A90E2").pack(side=tk.LEFT, padx=5)
        ttk.Label(legend_frame, text="→ Data Flow", foreground="#2ECC71").pack(side=tk.LEFT, padx=5)
        ttk.Label(legend_frame, text="◆ Start/End", foreground="#E74C3C").pack(side=tk.LEFT, padx=5)
        
        # Draw the flow diagram
        self.draw_flow_diagram()
        
    def analyze_flow(self):
        """Analyze the flow between functions"""
        relationships = []
        start_functions = []
        end_functions = []
        
        # Find relationships
        for i, pill1 in enumerate(self.pills):
            has_incoming = False
            has_outgoing = False
            
            for j, pill2 in enumerate(self.pills):
                if i != j:
                    # Check if pill1 outputs to pill2
                    for output in pill1.outputs:
                        if output in pill2.inputs:
                            relationships.append({
                                "from": pill1,
                                "to": pill2,
                                "connection": output
                            })
                            has_outgoing = True
                    
                    # Check if pill1 receives from pill2
                    for output in pill2.outputs:
                        if output in pill1.inputs:
                            has_incoming = True
            
            # Identify start and end functions
            if not has_incoming and pill1.inputs:
                start_functions.append(pill1)
            if not has_outgoing and pill1.outputs:
                end_functions.append(pill1)
                
        return relationships, start_functions, end_functions
    
    def draw_flow_diagram(self):
        """Draw the flow diagram on canvas"""
        relationships, start_functions, end_functions = self.analyze_flow()
        
        # Clear canvas
        self.canvas.delete("all")
        
        # Calculate positions for better visualization
        positions = self.calculate_positions(relationships, start_functions, end_functions)
        
        # Draw connections first (so they appear behind nodes)
        for rel in relationships:
            from_pos = positions[rel["from"]]
            to_pos = positions[rel["to"]]
            
            # Calculate arrow points
            from_x = from_pos[0] + 60  # Center of pill
            from_y = from_pos[1] + 20
            to_x = to_pos[0] + 60
            to_y = to_pos[1] + 20
            
            # Draw curved arrow
            mid_x = (from_x + to_x) / 2
            mid_y = (from_y + to_y) / 2 - 30
            
            # Create smooth curve
            self.canvas.create_line(
                from_x, from_y, mid_x, mid_y, to_x, to_y,
                fill="#2ECC71", width=2, smooth=True,
                arrow=tk.LAST, arrowshape=(12, 15, 5),
                tags="connection"
            )
            
            # Add label for connection
            self.canvas.create_text(
                mid_x, mid_y - 10,
                text=rel["connection"],
                fill="#27AE60", font=("Arial", 9, "italic"),
                tags="connection_label"
            )
        
        # Draw nodes
        for pill in self.pills:
            x, y = positions[pill]
            
            # Determine node color
            if pill in start_functions:
                color = "#E74C3C"  # Red for start
                shape = "diamond"
            elif pill in end_functions:
                color = "#9B59B6"  # Purple for end
                shape = "diamond"
            else:
                color = "#4A90E2"  # Blue for regular
                shape = "rectangle"
            
            # Draw node
            if shape == "diamond":
                # Draw diamond shape
                points = [
                    x + 60, y,      # Top
                    x + 120, y + 20, # Right
                    x + 60, y + 40,  # Bottom
                    x, y + 20        # Left
                ]
                self.canvas.create_polygon(
                    points, fill=color, outline="#2C3E50", width=2,
                    tags=f"node_{id(pill)}"
                )
            else:
                # Draw rectangle
                self.canvas.create_rectangle(
                    x, y, x + 120, y + 40,
                    fill=color, outline="#2C3E50", width=2,
                    tags=f"node_{id(pill)}"
                )
            
            # Add text
            self.canvas.create_text(
                x + 60, y + 20,
                text=pill.name, fill="white", font=("Arial", 10, "bold"),
                width=110, tags=f"node_text_{id(pill)}"
            )
            
            # Add tooltip with details
            details = []
            if pill.description:
                details.append(f"Description: {pill.description}")
            if pill.inputs:
                details.append(f"Inputs: {', '.join(pill.inputs)}")
            if pill.outputs:
                details.append(f"Outputs: {', '.join(pill.outputs)}")
            
            if details:
                self.canvas.create_text(
                    x + 60, y + 50,
                    text="\n".join(details), fill="#7F8C8D", 
                    font=("Arial", 8), width=200,
                    tags=f"tooltip_{id(pill)}", state=tk.HIDDEN
                )
            
            # Bind hover events
            self.canvas.tag_bind(f"node_{id(pill)}", "<Enter>", 
                               lambda e, p=pill: self.show_tooltip(p))
            self.canvas.tag_bind(f"node_{id(pill)}", "<Leave>", 
                               lambda e, p=pill: self.hide_tooltip(p))
        
        # Update canvas scroll region
        self.canvas.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        
        # Add summary text
        self.add_flow_summary(relationships, start_functions, end_functions)
    
    def calculate_positions(self, relationships, start_functions, end_functions):
        """Calculate optimal positions for nodes in the flow diagram"""
        positions = {}
        
        # Create layers based on dependencies
        layers = []
        processed = set()
        
        # First layer: start functions or functions with no inputs
        first_layer = []
        for pill in self.pills:
            if pill in start_functions or not pill.inputs:
                first_layer.append(pill)
                processed.add(pill)
        
        if first_layer:
            layers.append(first_layer)
        
        # Build subsequent layers
        while len(processed) < len(self.pills):
            next_layer = []
            for pill in self.pills:
                if pill not in processed:
                    # Check if all dependencies are processed
                    dependencies_met = True
                    for rel in relationships:
                        if rel["to"] == pill and rel["from"] not in processed:
                            dependencies_met = False
                            break
                    
                    if dependencies_met:
                        next_layer.append(pill)
                        processed.add(pill)
            
            if next_layer:
                layers.append(next_layer)
            else:
                # Add remaining pills to avoid infinite loop
                for pill in self.pills:
                    if pill not in processed:
                        next_layer.append(pill)
                        processed.add(pill)
                if next_layer:
                    layers.append(next_layer)
        
        # Calculate positions
        x_spacing = 200
        y_spacing = 100
        x_offset = 50
        y_offset = 50
        
        for layer_idx, layer in enumerate(layers):
            x = x_offset + layer_idx * x_spacing
            for pill_idx, pill in enumerate(layer):
                y = y_offset + pill_idx * y_spacing
                positions[pill] = (x, y)
        
        return positions
    
    def show_tooltip(self, pill):
        """Show tooltip for a pill"""
        self.canvas.itemconfig(f"tooltip_{id(pill)}", state=tk.NORMAL)
    
    def hide_tooltip(self, pill):
        """Hide tooltip for a pill"""
        self.canvas.itemconfig(f"tooltip_{id(pill)}", state=tk.HIDDEN)
    
    def add_flow_summary(self, relationships, start_functions, end_functions):
        """Add a text summary of the flow"""
        summary = []
        summary.append(f"Project: {self.project_name}")
        summary.append(f"Total Functions: {len(self.pills)}")
        summary.append(f"Data Flows: {len(relationships)}")
        
        if start_functions:
            summary.append(f"Entry Points: {', '.join([f.name for f in start_functions])}")
        if end_functions:
            summary.append(f"Exit Points: {', '.join([f.name for f in end_functions])}")
        
        # Create summary text at bottom of canvas
        bbox = self.canvas.bbox("all")
        if bbox:
            y_pos = bbox[3] + 30
            self.canvas.create_text(
                50, y_pos,
                text="\n".join(summary),
                anchor=tk.NW,
                fill="#34495E",
                font=("Arial", 10),
                tags="summary"
            )
    
    def export_image(self):
        """Export the flow diagram as an image (PostScript)"""
        from tkinter import filedialog
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".ps",
            filetypes=[("PostScript files", "*.ps"), ("All files", "*.*")]
        )
        
        if filename:
            # Get the bounding box of all items
            bbox = self.canvas.bbox("all")
            if bbox:
                self.canvas.postscript(file=filename, 
                                      x=bbox[0], y=bbox[1],
                                      width=bbox[2]-bbox[0], 
                                      height=bbox[3]-bbox[1])
                messagebox.showinfo("Success", f"Flow diagram exported to {os.path.basename(filename)}")
    
    def copy_description(self):
        """Copy flow description to clipboard"""
        relationships, start_functions, end_functions = self.analyze_flow()
        
        description = []
        description.append(f"Flow Diagram for Project: {self.project_name}")
        description.append("=" * 50)
        description.append("")
        
        description.append("FUNCTIONS:")
        for i, pill in enumerate(self.pills, 1):
            description.append(f"{i}. {pill.name}")
            if pill.description:
                description.append(f"   Description: {pill.description}")
            if pill.inputs:
                description.append(f"   Inputs: {', '.join(pill.inputs)}")
            if pill.outputs:
                description.append(f"   Outputs: {', '.join(pill.outputs)}")
            description.append("")
        
        description.append("DATA FLOWS:")
        for rel in relationships:
            description.append(f"- {rel['from'].name} → {rel['to'].name} (via: {rel['connection']})")
        
        if start_functions:
            description.append("")
            description.append("ENTRY POINTS:")
            for func in start_functions:
                description.append(f"- {func.name}")
        
        if end_functions:
            description.append("")
            description.append("EXIT POINTS:")
            for func in end_functions:
                description.append(f"- {func.name}")
        
        # Copy to clipboard
        text = "\n".join(description)
        self.window.clipboard_clear()
        self.window.clipboard_append(text)
        messagebox.showinfo("Success", "Flow description copied to clipboard!")

class ProjectSelectionDialog:
    """Dialog for selecting a project"""
    def __init__(self, parent, projects, title="Select Project"):
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.geometry("300x400")
        self.selected_project = None
        
        # Label
        ttk.Label(self.window, text="Select a project:").pack(pady=10)
        
        # Listbox
        listbox_frame = ttk.Frame(self.window)
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        
        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        for project in projects:
            self.listbox.insert(tk.END, project)
            
        # Buttons
        button_frame = ttk.Frame(self.window)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Select", command=self.select).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.window.destroy).pack(side=tk.LEFT, padx=5)
        
    def select(self):
        """Handle selection"""
        selection = self.listbox.curselection()
        if selection:
            self.selected_project = self.listbox.get(selection[0])
            self.window.destroy()

def main():
    root = tk.Tk()
    app = ArchitectureMapper(root)
    root.mainloop()

if __name__ == "__main__":
    main()