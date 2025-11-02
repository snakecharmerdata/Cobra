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

# Guide helper (module-level): comprehensive, up-to-date instructions and usage
# Called from toolbar via: open_guide(self)

def open_guide(app):
    try:
        win = tk.Toplevel(app.root)
        win.title("Guide")
        try:
            win.geometry("840x680")
        except Exception:
            pass

        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        def add_tab(title, body):
            frame = ttk.Frame(nb)
            nb.add(frame, text=title)
            text_frame = ttk.Frame(frame)
            text_frame.pack(fill=tk.BOTH, expand=True)
            yscroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
            yscroll.pack(side=tk.RIGHT, fill=tk.Y)
            txt = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=yscroll.set,
                          font=("Arial", 10), padx=10, pady=10)
            txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            yscroll.config(command=txt.yview)
            try:
                txt.insert("1.0", body.strip())
                txt.config(state=tk.DISABLED)
            except Exception:
                pass
            return frame

        quick = """
How to use this guide
- Tabs group topics. Start with Quick Start, then explore the features you use most.
- Concepts define terms you’ll see across the UI (List, Order, Relationships).

Quick Start
1) Create/open project and connect the database.
2) Manage Lists (modules/phases) as needed.
3) Add functions (name, List, optional Order). Double-click a pill to edit details.
4) Save to DB to persist per-function data (including position) in the project’s schema.
5) Arrange pills visually on the canvas. Use File → Save Project to capture the whole map snapshot.
6) Explore views:
   - Logical Mapping: see Lists, functions and relationships.
   - Mind Map: left→right tree of project → lists → functions.
   - Analysis: quality gauges, suggestions, and graph insights (including Edges by Type).
7) Define the Objective (project goal), then use Compile to generate segmented text with token estimates for export.
        """

        logical = """
Logical Mapping
- Shows functions grouped by their List with optional Order (sequence) inside each List.
- Lines reflect Relationships defined per function (via the "Related to:" field in Details).
- Drag pills to adjust visual positions; double-click to edit a function.
- Assigning Lists and Orders improves the plan’s clarity and Analysis scoring.
        """

        mindmap = """
Mind Map
- Left→right layered layout: Project (root) → Lists → Functions.
- Orthogonal connectors minimize overlap and improve readability.
- Zoom: Ctrl/Cmd + and Ctrl/Cmd −; Reset via the dedicated control in the viewer.
- Scrollbars allow panning when zoomed.
- Use this to communicate structure at a glance while retaining the List/function tree.
        """

        analysis = """
Analysis and Graph Insights
- Gauges: "Success Rate" and "With Improvement" summarize coverage and potential.
- Suggestions: concrete next-steps to increase clarity and reduce risk.
- Description Improvement Suggestions: drafts short, outcome-focused descriptions for underspecified functions.
- Graph Insights:
  • Components: weakly connected subgraphs; many small components can indicate fragmentation.
  • Cycles (SCC>1): function cycles; consider breaking or buffering to reduce risk.
  • Top Degree: most connected functions (possible hubs/integration points).
  • Edges by Type: Cross vs Intra (see Mind Map and Lists). Cross = across different Lists, Intra = within the same List.
    – High Cross ratio suggests coupling across modules; refactor responsibilities or introduce integration functions.
    – Higher Intra indicates cohesive modules.
        """

        objective_compile = """
Objective and Compile
- Objective: set the project’s goal and scope. Longer, concrete objectives (≥ 60 chars) increase plan quality.
- Compile: creates a segmented text pack for sharing/review:
  • Splits content into manageable segments with rough token estimates.
  • Includes Objective & overview, per-List details, and cross-relations.
  • Copy a single segment, Copy All, or Save .txt.
        """

        saving_shortcuts = """
Saving and Shortcuts
- Save to DB / Update in DB: persists an individual function (fields + position) into the project’s schema.
- File → Save Project: captures a full canvas snapshot/layout and related artifacts for quick restore/sharing.
- When to use which:
  • Editing a function (or adding new)? Use Save/Update in DB.
  • Only rearranged pills and want all positions captured at once? Use Save Project.
  • Want a snapshot/export bundle? Use Save Project (and/or Compile’s Save .txt).

Shortcuts and Tips
- Drag to reposition pills; double-click a pill to open details.
- Mind Map: Ctrl/Cmd + and Ctrl/Cmd − to zoom; use scrollbars to pan.
- Prefer Intra (within-List) relationships; keep Cross (between Lists) relationships intentional.
        """

        add_tab("Quick Start", quick)
        add_tab("Logical Mapping", logical)
        add_tab("Mind Map", mindmap)
        add_tab("Analysis", analysis)
        add_tab("Objective & Compile", objective_compile)
        add_tab("Saving & Shortcuts", saving_shortcuts)

        bottom = ttk.Frame(win)
        bottom.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(bottom, text="Close", command=win.destroy).pack(side=tk.RIGHT)
    except Exception as e:
        try:
            messagebox.showerror("Guide", str(e))
        except Exception:
            pass

# Analysis helper (module-level): generates a likelihood score and suggestions, no DB writes
# Called from toolbar via: open_analysis(self)

def open_analysis(app):
    try:
        project_name = getattr(app, 'current_project', None) or '(unnamed)'
        # Heuristic token estimator
        def _est_tokens(s):
            try:
                return max(1, int(len(s) / 4))
            except Exception:
                return len(s)
        # Parse relationships field
        def _parse_related_names(rel_text):
            if not rel_text:
                return []
            try:
                for line in (rel_text or '').splitlines():
                    if line.strip().lower().startswith('related to:'):
                        rest = line.split(':', 1)[1]
                        return [n.strip() for n in rest.split(',') if n.strip()]
            except Exception:
                return []
            return []
        # Load objective
        objective = None
        try:
            if getattr(app, 'db_manager', None) and app.db_manager.connected and getattr(app, 'current_project', None):
                if hasattr(app.db_manager, 'get_project_objective'):
                    try:
                        objective = app.db_manager.get_project_objective(app.current_project)
                    except Exception:
                        try:
                            app.db_manager.connection.rollback()
                        except Exception:
                            pass
                if not objective:
                    try:
                        schema = app.db_manager.schema_name_for_project(app.current_project)
                        cur = app.db_manager.connection.cursor()
                        cur.execute(sql.SQL("SELECT objective FROM {}.project_info WHERE id = 1").format(sql.Identifier(schema)))
                        row = cur.fetchone()
                        if row and row[0]:
                            objective = row[0]
                    except Exception:
                        try:
                            app.db_manager.connection.rollback()
                        except Exception:
                            pass
        except Exception:
            pass
        if not objective:
            objective = ''
        # Collect pills
        pills = list(getattr(app, 'pills', []) or [])
        n = len(pills)
        name_to_pill = {getattr(p, 'name', '').strip(): p for p in pills if getattr(p, 'name', None)}
        # Coverage metrics
        desc_cov = (sum(1 for p in pills if (getattr(p, 'description', '') or '').strip().__len__() >= 20) / n) if n else 0.0
        inputs_cov = (sum(1 for p in pills if (getattr(p, 'inputs', []) or [])) / n) if n else 0.0
        outputs_cov = (sum(1 for p in pills if (getattr(p, 'outputs', []) or [])) / n) if n else 0.0
        list_cov = (sum(1 for p in pills if (getattr(p, 'list_name', '') or getattr(p, 'list_id', None))) / n) if n else 0.0
        order_cov = (sum(1 for p in pills if getattr(p, 'list_order', None) is not None) / n) if n else 0.0
        # Edges
        edges = []
        for p in pills:
            for rn in _parse_related_names(getattr(p, 'relationships', '') or ''):
                if rn:
                    edges.append((getattr(p, 'name', ''), rn))
        total_edges = len(edges)
        # Graph and degrees
        nodes = set(name_to_pill.keys())
        adj = {u: [] for u in nodes}
        indeg = {u: 0 for u in nodes}
        for a, b in edges:
            if a in nodes and b in nodes:
                adj[a].append(b)
                indeg[b] += 1
        deg = {u: (len(adj[u]) + indeg[u]) for u in nodes}
        orphan_ratio = (sum(1 for u in nodes if deg[u] == 0) / n) if n else 0.0
        # Cross-list ratio
        def _list_of(name):
            p = name_to_pill.get(name)
            return (getattr(p, 'list_name', '') or '').strip() if p else ''
        cross_edges = 0
        for a, b in edges:
            if a in nodes and b in nodes:
                if (_list_of(a) or '') != (_list_of(b) or ''):
                    cross_edges += 1
        cross_ratio = (cross_edges / total_edges) if total_edges else 0.0
        # Relation density (edges per node, capped at 1)
        rel_density = min(1.0, (total_edges / n) if n else 0.0)
        # Cycle detection via Kahn
        try:
            indeg2 = indeg.copy()
            q = [u for u in nodes if indeg2[u] == 0]
            visited = 0
            from collections import deque
            dq = deque(q)
            while dq:
                u = dq.popleft()
                visited += 1
                for v in adj[u]:
                    indeg2[v] -= 1
                    if indeg2[v] == 0:
                        dq.append(v)
            has_cycle = (visited < len(nodes))
        except Exception:
            has_cycle = False
        # Scoring
        w_obj = 15
        w_fn = 10
        w_desc = 15
        w_in = 10
        w_out = 10
        w_list = 10
        w_order = 5
        w_rel = 15
        # Objective quality factor by length only (simple heuristic)
        obj_len = len((objective or '').strip())
        obj_factor = 1.0 if obj_len >= 60 else (obj_len / 60.0)
        fn_factor = 1.0 if n >= 8 else (n / 8.0)
        score = 0.0
        score += w_obj * obj_factor
        score += w_fn * fn_factor
        score += w_desc * desc_cov
        score += w_in * inputs_cov
        score += w_out * outputs_cov
        score += w_list * list_cov
        score += w_order * order_cov
        score += w_rel * rel_density
        # Penalties
        pen_cross = 5.0 * cross_ratio  # up to -5
        pen_orph = 10.0 * orphan_ratio  # up to -10
        pen_cycle = 10.0 if has_cycle else 0.0
        score -= (pen_cross + pen_orph + pen_cycle)
        score = max(0.0, min(100.0, score))
        # Potential improvement assuming suggestions are applied toward ~95% coverage and no cycles/orphans
        tgt = 0.95
        imp = 0.0
        imp += w_obj * max(0.0, (1.0 - obj_factor))
        imp += w_fn * max(0.0, (1.0 - fn_factor)) * 0.25  # partial; adding more functions only helps modestly
        imp += w_desc * max(0.0, (tgt - desc_cov))
        imp += w_in * max(0.0, (tgt - inputs_cov))
        imp += w_out * max(0.0, (tgt - outputs_cov))
        imp += w_list * max(0.0, (tgt - list_cov))
        imp += w_order * max(0.0, (tgt - order_cov))
        imp += w_rel * max(0.0, (tgt - rel_density))
        imp += pen_cross + pen_orph + pen_cycle
        improved = max(score, min(100.0, score + imp))
        # Build suggestions
        suggestions = []
        if obj_factor < 1.0:
            suggestions.append("Expand the Objective with concrete scope, success criteria, constraints, and milestones (aim ≥ 60 chars).")
        if desc_cov < 0.95:
            suggestions.append("Provide clear, outcome-focused descriptions for all functions (≥ 20 chars each).")
        if inputs_cov < 0.95:
            suggestions.append("Define inputs for all functions. Ensure alignment between upstream outputs and downstream inputs.")
        if outputs_cov < 0.95:
            suggestions.append("Define outputs for all functions with measurable artifacts/results.")
        if list_cov < 0.95:
            suggestions.append("Assign every function to a List (module/phase).")
        if order_cov < 0.95:
            suggestions.append("Set List order for functions to clarify execution sequence and dependencies.")
        if rel_density < 0.6:
            suggestions.append("Increase relationships between related functions to reduce ambiguity; connect isolated nodes.")
        if orphan_ratio > 0.0:
            suggestions.append("Eliminate orphan functions by linking them or removing them if unnecessary.")
        if cross_ratio > 0.35:
            suggestions.append("Reduce cross-list dependencies by refactoring responsibilities or introducing integration functions.")
        if has_cycle:
            suggestions.append("Break dependency cycles by introducing buffers/queues, redefining boundaries, or reordering steps.")
        if not suggestions:
            suggestions.append("The plan appears consistent. Consider adding validation/monitoring steps to further improve confidence.")
        # Build KPIs text
        kpi_lines = [
            f"Project: {project_name}",
            f"Objective length: {obj_len} chars",
            f"Functions: {n}",
            f"Descriptions coverage: {int(desc_cov*100)}%",
            f"Inputs coverage: {int(inputs_cov*100)}%",
            f"Outputs coverage: {int(outputs_cov*100)}%",
            f"List assignment coverage: {int(list_cov*100)}%",
            f"Order coverage: {int(order_cov*100)}%",
            f"Relations: {total_edges} (density≈{int(rel_density*100)}%)",
            f"Cross-list edges: {int(cross_ratio*100)}%",
            f"Orphan functions: {int(orphan_ratio*100)}%",
            f"Cycles detected: {'Yes' if has_cycle else 'No'}",
        ]
        # UI
        win = tk.Toplevel(app.root)
        win.title("Analysis")
        try:
            win.geometry("1000x640")
        except Exception:
            pass
        top = ttk.Frame(win)
        top.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        # Gauges
        gauge = tk.Canvas(top, height=160, highlightthickness=0)
        gauge.pack(fill=tk.X)
        W = 920
        X0 = 40
        BAR_H = 28
        def draw_bar(y, pct, color, label):
            # Bar background
            gauge.create_rectangle(X0, y, X0+W, y+BAR_H, fill="#eee", outline="#ddd")
            # Centered label above the bar to avoid clipping
            gauge.create_text(X0 + W/2, y - 6, text=label, anchor='s', font=("Arial", 11, 'bold'))
            w = int(W * max(0.0, min(1.0, pct/100.0)))
            gauge.create_rectangle(X0, y, X0+w, y+BAR_H, fill=color, outline=color)
            gauge.create_text(X0+w+8, y+BAR_H/2, text=f"{pct:.1f}%", anchor='w', font=("Arial", 10))
        draw_bar(20, score, "#10b981", "Success Rate")
        draw_bar(70, improved, "#3b82f6", "With Improvement")
        # KPI + Suggestions panes
        panes = ttk.Frame(top)
        panes.pack(fill=tk.BOTH, expand=True, pady=(10,0))
        left = ttk.Frame(panes)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = ttk.Frame(panes)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10,0))
        ttk.Label(left, text="Key Metrics").pack(anchor='w')
        kpi_text = tk.Text(left, height=12, wrap=tk.WORD)
        kpi_text.pack(fill=tk.BOTH, expand=True)
        kpi_text.insert('1.0', "\n".join(kpi_lines))
        ttk.Label(right, text="Suggested Improvements").pack(anchor='w')
        sug_text = tk.Text(right, height=12, wrap=tk.WORD)
        sug_text.pack(fill=tk.BOTH, expand=True)
        sug_text.insert('1.0', "\n- ".join(["Suggestions:"] + suggestions))
        # Description improvement advice box
        desc_suggestions = []
        for p in pills:
            try:
                desc_val = (getattr(p, 'description', '') or '').strip()
                if len(desc_val) < 60:
                    ins = ", ".join((getattr(p, 'inputs', []) or [])) or "relevant inputs"
                    outs = ", ".join((getattr(p, 'outputs', []) or [])) or "expected outputs"
                    lname = (getattr(p, 'list_name', '') or 'its module')
                    sample = f"{p.name} takes {ins} and produces {outs} within the {lname} list. It is responsible for {p.name.lower()} core logic, and completes successfully when outputs meet defined acceptance criteria."
                    desc_suggestions.append(f"- Function: {p.name}\n  Field: Description\n  Suggested: {sample}")
            except Exception:
                pass
        ttk.Label(top, text="Description Improvement Suggestions").pack(anchor='w', pady=(6,0))
        desc_box = tk.Text(top, height=8, wrap=tk.WORD)
        desc_box.pack(fill=tk.BOTH, expand=True)
        desc_box.insert('1.0', "\n\n".join(desc_suggestions) if desc_suggestions else "All functions have sufficiently detailed descriptions (≥ 60 chars).")

        # Graph insights (pure Python algorithms)
        try:
            # Build undirected adjacency for articulation points and components
            uadj = {u: set() for u in nodes}
            for a, b in edges:
                if a in uadj and b in uadj:
                    uadj[a].add(b)
                    uadj[b].add(a)

            # Weakly connected component sizes
            comp_sizes = []
            _vis = set()
            for u in nodes:
                if u not in _vis:
                    stack = [u]
                    _vis.add(u)
                    sz = 0
                    while stack:
                        w = stack.pop()
                        sz += 1
                        for v in uadj[w]:
                            if v not in _vis:
                                _vis.add(v)
                                stack.append(v)
                    comp_sizes.append(sz)
            comp_sizes.sort(reverse=True)

            # Articulation points (cut vertices) via DFS
            disc, low, parent = {}, {}, {}
            _time = [0]
            articulation = set()
            def _dfs_ap(u):
                _time[0] += 1
                disc[u] = low[u] = _time[0]
                children = 0
                for v in uadj[u]:
                    if v not in disc:
                        parent[v] = u
                        children += 1
                        _dfs_ap(v)
                        low[u] = min(low[u], low[v])
                        if parent.get(u) is None and children > 1:
                            articulation.add(u)
                        if parent.get(u) is not None and low[v] >= disc[u]:
                            articulation.add(u)
                    elif v != parent.get(u):
                        low[u] = min(low[u], disc[v])
            for u in nodes:
                if u not in disc:
                    parent[u] = None
                    _dfs_ap(u)

            # Strongly connected components (Kosaraju)
            radj = {u: [] for u in nodes}
            for a, b in edges:
                if a in nodes and b in nodes:
                    radj[b].append(a)
            _seen = set()
            order = []
            def _dfs1(u):
                _seen.add(u)
                for v in adj[u]:
                    if v in nodes and v not in _seen:
                        _dfs1(v)
                order.append(u)
            for u in nodes:
                if u not in _seen:
                    _dfs1(u)
            _seen2 = set()
            sccs = []
            def _dfs2(u, comp):
                _seen2.add(u)
                comp.append(u)
                for v in radj[u]:
                    if v not in _seen2:
                        _dfs2(v, comp)
            for u in reversed(order):
                if u not in _seen2:
                    comp = []
                    _dfs2(u, comp)
                    if len(comp) > 1:
                        sccs.append(comp)
            sccs.sort(key=len, reverse=True)

            # Top-degree nodes (already have 'deg')
            top_deg = sorted(deg.items(), key=lambda kv: kv[1], reverse=True)[:5]
            intra_edges = max(0, total_edges - cross_edges)

            # Draw insights
            insights = ttk.LabelFrame(top, text="Graph Insights")
            insights.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

            row = ttk.Frame(insights)
            row.pack(anchor='center', pady=4)

            # Pie: Cross-list vs Intra-list edges
            pie = tk.Canvas(row, width=260, height=170, highlightthickness=0)
            pie.pack(side=tk.LEFT, padx=6)
            M = 12
            bbox = (M, M, M + 140, M + 140)
            tot = max(1, total_edges)
            cross_extent = int(360 * (cross_edges / tot))
            try:
                pie.create_arc(bbox, start=0, extent=cross_extent, fill="#ef4444", outline="")  # cross-list
                pie.create_arc(bbox, start=cross_extent, extent=360 - cross_extent, fill="#10b981", outline="")  # intra
            except Exception:
                pass
            # Title at top-right of the pane (use real canvas width after layout)
            try:
                pie.update_idletasks()
            except Exception:
                pass
            try:
                Wc = pie.winfo_width()
                Hc = pie.winfo_height()
            except Exception:
                Wc = 0
                Hc = 0
            if not Wc:
                try:
                    Wc = int(pie['width'])
                except Exception:
                    Wc = 260
            if not Hc:
                try:
                    Hc = int(pie['height'])
                except Exception:
                    Hc = 230
            title_id = pie.create_text(M, M, text="Edges by Type", anchor='nw', font=("Arial", 10,'bold'))

            # Legend left-aligned near top (under title row)
            try:
                pie.update_idletasks()
                try:
                    Wc = pie.winfo_width()
                except Exception:
                    Wc = int(pie['width'])
                # Measure text widths by creating temporary text items
                def _measure(txt):
                    item = pie.create_text(0, 0, text=txt, anchor='nw', font=("Arial", 10))
                    b = pie.bbox(item)
                    pie.delete(item)
                    return (b[2] - b[0]) if b else 80
                sq = 12
                gap = 8
                tb = pie.bbox(title_id) if 'title_id' in locals() else None
                y_title_bottom = tb[3] if tb else (M + 12)
                y1 = y_title_bottom + 4
                y2 = y1 + 16
                # Cross (left-aligned block)
                text1 = f"Cross ({cross_edges})"
                w1 = _measure(text1)
                xl = M  # left margin
                # Draw colored square then text to the right
                sx1 = xl
                pie.create_rectangle(sx1, y1 - 6, sx1 + sq, y1 + 6, fill="#ef4444", outline="")
                pie.create_text(sx1 + sq + gap, y1, text=text1, anchor='w', font=("Arial", 10))

                # Intra (left-aligned block)
                text2 = f"Intra ({intra_edges})"
                w2 = _measure(text2)
                sx2 = xl
                pie.create_rectangle(sx2, y2 - 6, sx2 + sq, y2 + 6, fill="#10b981", outline="")
                pie.create_text(sx2 + sq + gap, y2, text=text2, anchor='w', font=("Arial", 10))
            except Exception:
                pass

            # Bar: Top-degree nodes
            cen = tk.Canvas(row, width=380, height=170, highlightthickness=0)
            cen.pack(side=tk.LEFT, padx=6)
            maxv = max([v for _, v in top_deg] + [1])
            y0 = 20
            bar_h = 20
            for i, (nm, val) in enumerate(top_deg):
                y = y0 + i * (bar_h + 10)
                w = int(260 * (val / maxv))
                cen.create_rectangle(10, y, 10 + w, y + bar_h, fill="#60a5fa", outline="")
                cen.create_text(15, y + bar_h / 2, anchor='w', text=f"{nm}", font=("Arial", 9))
                cen.create_text(280, y + bar_h / 2, anchor='w', text=str(val), font=("Arial", 9,'bold'))
            cen.create_text(190, 160, text="Top Degree Nodes", font=("Arial", 10,'bold'))

            # Summary box: components, SCCs, articulation points
            summary = tk.Text(row, width=42, height=10, wrap=tk.WORD)
            summary.pack(side=tk.LEFT, padx=6)
            comp_txt = ", ".join(map(str, comp_sizes[:6])) + ("..." if len(comp_sizes) > 6 else "")
            ap_list = list(articulation)
            ap_txt = ", ".join(ap_list[:6]) + ("..." if len(ap_list) > 6 else "") if ap_list else "None"
            cyc_preview = [", ".join(c[:6]) + ("..." if len(c) > 6 else "") for c in sccs[:3]]
            summary_lines = [
                f"Components: {len(comp_sizes)} (sizes: {comp_txt or 'n/a'})",
                f"Cycles (SCC>1): {len(sccs)}",
            ]
            if cyc_preview:
                for idx, line in enumerate(cyc_preview, 1):
                    summary_lines.append(f"  Cycle {idx}: {line}")
            summary_lines.append(f"Articulation points: {len(articulation)} ({ap_txt})")
            summary.insert('1.0', "\n".join(summary_lines))

            # Legend moved into pie canvas (centered under title)
        except Exception:
            pass

        # Bottom controls
        bottom = ttk.Frame(win)
        bottom.pack(fill=tk.X, pady=6)
        status = tk.StringVar(value=f"Objective tokens≈{_est_tokens(objective)} • Segments not saved")
        ttk.Label(bottom, textvariable=status).pack(side=tk.LEFT, padx=8)
        def copy_report():
            try:
                report_lines = []
                report_lines.append("Analysis Report")
                report_lines.append("")
            except Exception:
                pass
        
    except Exception as e:
        try:
            messagebox.showerror("Analysis Error", str(e))
        except Exception:
            pass
    
        class FunctionPill:
            pass
    """Represents a draggable function pill on the canvas"""
    def __init__(self, canvas, x, y, name, function_id=None, list_id=None, list_order=None, list_name=""):
        self.canvas = canvas
        self.name = name
        self.function_id = function_id
        self.list_id = list_id
        self.list_order = list_order
        self.list_name = list_name or ""
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
            fill="#4A90E2", outline="#2E5C8A", width=2
        )

        # Create the text label
        self.text = self.canvas.create_text(
            x + self.width/2, y + self.height/2,
            text=name, fill="white", font=("Arial", 10, "bold")
        )

        # Ensure both items share a common tag for event binding
        tag = f"pill_{id(self)}"
        self.canvas.itemconfig(self.rect, tags=("pill", tag))
        self.canvas.itemconfig(self.text, tags=("pill_text", tag))

        # Bind events on the common tag
        self.canvas.tag_bind(tag, "<Button-1>", self.on_click)
        self.canvas.tag_bind(tag, "<B1-Motion>", self.on_drag)
        self.canvas.tag_bind(tag, "<ButtonRelease-1>", self.on_release)
        self.canvas.tag_bind(tag, "<Double-Button-1>", self.on_double_click)

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
            try:
                app.status_var.set(f"Moving '{self.name}' to position ({self.x}, {self.y})")
            except Exception:
                pass

    def on_release(self, event):
        """Handle mouse release"""
        pass

    def on_double_click(self, event):
        """Open detail window on double click"""
        root = self.canvas.winfo_toplevel()
        DetailWindow(root, self)

    def update_name(self, new_name):
        """Update the pill's name and label"""
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
            "function_id": self.function_id,
            "list_id": self.list_id,
            "list_order": self.list_order,
            "list_name": self.list_name,
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

class FunctionPill:
    """Represents a draggable function pill on the canvas"""
    def __init__(self, canvas, x, y, name, function_id=None, list_id=None, list_order=None, list_name=""):
        self.canvas = canvas
        self.name = name
        self.function_id = function_id
        self.list_id = list_id
        self.list_order = list_order
        self.list_name = list_name or ""
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
            fill="#4A90E2", outline="#2E5C8A", width=2
        )

        # Create the text label
        self.text = self.canvas.create_text(
            x + self.width/2, y + self.height/2,
            text=name, fill="white", font=("Arial", 10, "bold")
        )

        # Ensure both items share a common tag for event binding
        tag = f"pill_{id(self)}"
        self.canvas.itemconfig(self.rect, tags=("pill", tag))
        self.canvas.itemconfig(self.text, tags=("pill_text", tag))

        # Bind events on the common tag
        self.canvas.tag_bind(tag, "<Button-1>", self.on_click)
        self.canvas.tag_bind(tag, "<B1-Motion>", self.on_drag)
        self.canvas.tag_bind(tag, "<ButtonRelease-1>", self.on_release)
        self.canvas.tag_bind(tag, "<Double-Button-1>", self.on_double_click)

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
            try:
                app.status_var.set(f"Moving '{self.name}' to position ({self.x}, {self.y})")
            except Exception:
                pass

    def on_release(self, event):
        """Handle mouse release"""
        pass

    def on_double_click(self, event):
        """Open detail window on double click"""
        root = self.canvas.winfo_toplevel()
        DetailWindow(root, self)

    def update_name(self, new_name):
        """Update the pill's name and label"""
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
            "function_id": self.function_id,
            "list_id": self.list_id,
            "list_order": self.list_order,
            "list_name": self.list_name,
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

# Auto-size FunctionPill pills based on text length
try:
    _FunctionPill_type = FunctionPill
    if not hasattr(_FunctionPill_type, "_auto_size_patched"):
        _orig_init_fp = _FunctionPill_type.__init__
        def _fp_resize_to_text(self, pad_x=24, pad_y=12, min_w=80, min_h=40):
            try:
                self.canvas.update_idletasks()
            except Exception:
                pass
            try:
                bbox = self.canvas.bbox(self.text)
            except Exception:
                bbox = None
            if not bbox:
                return
            try:
                text_w = max(0, bbox[2] - bbox[0])
                text_h = max(0, bbox[3] - bbox[1])
                new_w = max(min_w, text_w + pad_x)
                new_h = max(min_h, text_h + pad_y)
                self.width = new_w
                self.height = new_h
                self.canvas.coords(self.rect, self.x, self.y, self.x + new_w, self.y + new_h)
                self.canvas.coords(self.text, self.x + new_w/2, self.y + new_h/2)
            except Exception:
                pass
        def _fp_new_init(self, *args, **kwargs):
            _orig_init_fp(self, *args, **kwargs)
            try:
                _fp_resize_to_text(self)
            except Exception:
                pass
        _orig_update_name_fp = _FunctionPill_type.update_name
        def _fp_new_update_name(self, new_name):
            _orig_update_name_fp(self, new_name)
            try:
                _fp_resize_to_text(self)
            except Exception:
                pass
        _FunctionPill_type.__init__ = _fp_new_init
        _FunctionPill_type.update_name = _fp_new_update_name
        _FunctionPill_type._resize_to_text = _fp_resize_to_text
        _FunctionPill_type._auto_size_patched = True
except Exception:
    pass

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
        # Set size and center on screen (wider by default to show all fields horizontally)
        w, h = 1400, 650
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

        # List selection and order (hierarchy)
        tk.Label(main_frame, text="List:", bg="#f2f2f2", fg="#000000").grid(row=0, column=3, sticky=tk.E, padx=(10, 2))
        self.list_var = tk.StringVar(value="")
        self._list_options = []  # list of (id, name)
        self.list_combo = ttk.Combobox(main_frame, textvariable=self.list_var, state="readonly", width=18)
        self.list_combo.grid(row=0, column=4, sticky=(tk.W), pady=5)

        tk.Label(main_frame, text="Order:", bg="#f2f2f2", fg="#000000").grid(row=0, column=5, sticky=tk.E, padx=(10, 2))
        self.order_var = tk.IntVar(value=1)
        try:
            self.order_spin = tk.Spinbox(main_frame, from_=1, to=9999, width=6, textvariable=self.order_var)
        except Exception:
            self.order_spin = tk.Entry(main_frame, width=6, textvariable=self.order_var)
        self.order_spin.grid(row=0, column=6, sticky=tk.W, pady=5)
        
        # Description
        tk.Label(main_frame, text="Description:", bg="#f2f2f2", fg="#000000").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.desc_text = tk.Text(main_frame, height=3, width=40, bg="#f2f2f2", fg="#000000", insertbackground="#000000")
        self.desc_text.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        self.desc_text.insert("1.0", pill.description)
        
        # Inputs column
        tk.Label(main_frame, text="Inputs:", font=("Arial", 10, "bold"), bg="#f2f2f2", fg="#000000").grid(row=2, column=0, pady=10)
        
        # Inputs textbox (multiline; one per line or comma-separated)
        self.inputs_text = tk.Text(main_frame, height=8, width=40, bg="#f2f2f2", fg="#000000", insertbackground="#000000")
        self.inputs_text.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Outputs column
        tk.Label(main_frame, text="Outputs:", font=("Arial", 10, "bold"), bg="#f2f2f2", fg="#000000").grid(row=2, column=2, pady=10)
        
        # Outputs textbox (multiline; one per line or comma-separated)
        self.outputs_text = tk.Text(main_frame, height=8, width=40, bg="#f2f2f2", fg="#000000", insertbackground="#000000")
        self.outputs_text.grid(row=3, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
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
        
                
        # Database operations frame
        db_frame = tk.LabelFrame(main_frame, text="Database Operations", bg="#f2f2f2", fg="#000000")
        db_frame.grid(row=8, column=0, columnspan=3, pady=10, sticky=(tk.W, tk.E), ipadx=5, ipady=5)
        
        # Database buttons
        ttk.Button(db_frame, text="Save to DB", command=self.save_to_db).pack(side=tk.LEFT, padx=5)
        ttk.Button(db_frame, text="Update in DB", command=self.update_in_db).pack(side=tk.LEFT, padx=5)
        ttk.Button(db_frame, text="Delete from DB", command=self.delete_from_db).pack(side=tk.LEFT, padx=5)
        ttk.Button(db_frame, text="Load from DB", command=self.load_from_db).pack(side=tk.LEFT, padx=5)
        ttk.Button(db_frame, text="Cancel", command=self.clear_fields).pack(side=tk.LEFT, padx=5)

        # Spinner/Status area (right side)
        self._spinner_running = False
        self._spinner_angle = 0
        self._gear_assets = None  # (base_images, sizes, colors)
        self._gear_items = []     # canvas image item ids
        self._gear_images_cache = []  # PhotoImage refs to prevent GC
        gear_container = tk.Frame(db_frame, bg="#f2f2f2")
        gear_container.pack(side=tk.RIGHT, padx=5)
        self.gear_canvas = tk.Canvas(gear_container, width=120, height=60, bg="#f2f2f2", highlightthickness=0)
        self.gear_canvas.pack()
        self.gear_label = ttk.Label(gear_container, text="", foreground="#555")
        self.gear_label.pack()
        
        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(2, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Load list options and existing data
        app_ctx = self.get_app_instance()
        self._schema = None
        if app_ctx and getattr(app_ctx, 'db_manager', None) and app_ctx.db_manager.connected and app_ctx.current_project:
            try:
                app_ctx.db_manager.ensure_project_schema(app_ctx.current_project)
                self._schema = app_ctx.db_manager.schema_name_for_project(app_ctx.current_project)
                cur = app_ctx.db_manager.connection.cursor()
                cur.execute(sql.SQL("SELECT id, name FROM {}.function_lists ORDER BY name").format(sql.Identifier(self._schema)))
                rows = cur.fetchall()
                self._list_options = rows
                self.list_combo["values"] = [r[1] for r in rows]
            except Exception:
                try:
                    app_ctx.db_manager.connection.rollback()
                except Exception:
                    pass
        # Auto set order when list changes
        def _auto_set_order_evt():
            sel_name = (self.list_var.get() or "").strip()
            lid = None
            for rid, rname in self._list_options:
                if rname == sel_name:
                    lid = rid
                    break
            if lid and app_ctx and getattr(app_ctx, 'db_manager', None) and app_ctx.db_manager.connected and self._schema:
                try:
                    cur = app_ctx.db_manager.connection.cursor()
                    cur.execute(sql.SQL("SELECT COALESCE(MAX(list_order), 0) + 1 FROM {}.functions WHERE list_id = %s").format(sql.Identifier(self._schema)), (lid,))
                    next_ord = cur.fetchone()[0] or 1
                    self.order_var.set(int(next_ord))
                    # Update pill model immediately so Logical Mapping reflects selection without DB update
                    try:
                        self.pill.list_id = lid
                    except Exception:
                        pass
                    self.pill.list_name = sel_name
                    try:
                        self.pill.list_order = int(next_ord)
                    except Exception:
                        self.pill.list_order = None
                except Exception:
                    try:
                        app_ctx.db_manager.connection.rollback()
                    except Exception:
                        pass
                    self.order_var.set(1)
                    # Still update pill model with selection; order fallback to 1
                    try:
                        self.pill.list_id = lid
                    except Exception:
                        pass
                    self.pill.list_name = sel_name
                    try:
                        self.pill.list_order = 1
                    except Exception:
                        self.pill.list_order = None
            else:
                self.order_var.set(1)
                # Apply selected list to pill even if not connected or no lid resolved
                try:
                    self.pill.list_id = lid
                except Exception:
                    pass
                self.pill.list_name = sel_name
                try:
                    self.pill.list_order = 1 if sel_name else None
                except Exception:
                    self.pill.list_order = None
        self.list_combo.bind("<<ComboboxSelected>>", lambda e: _auto_set_order_evt())
        # Ensure in-memory changes are reflected even if user closes without DB update
        try:
            self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        except Exception:
            pass

        self.load_data()
        # Reflect pill's existing list/order in UI if available
        if getattr(self.pill, 'list_id', None):
            for rid, rname in self._list_options:
                if rid == self.pill.list_id:
                    self.list_var.set(rname)
                    break
            try:
                self.order_var.set(int(self.pill.list_order) if self.pill.list_order else 1)
            except Exception:
                self.order_var.set(1)
        else:
            self.order_var.set(1)

        # Auto-load current function details from DB (without popup), so List and Order appear immediately
        try:
            self._auto_load_current_function_from_db()
        except Exception:
            pass
        
    def load_data(self):
        """Load existing inputs and outputs"""
        self.inputs_text.delete("1.0", tk.END)
        self.inputs_text.insert("1.0", "\n".join(self.pill.inputs))
        self.outputs_text.delete("1.0", tk.END)
        self.outputs_text.insert("1.0", "\n".join(self.pill.outputs))
            
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

        # Update list selection and order
        selected_list_name = (self.list_var.get() or "").strip()
        selected_list_id = None
        for lid, lname in getattr(self, "_list_options", []):
            if lname == selected_list_name:
                selected_list_id = lid
                break
        self.pill.list_id = selected_list_id
        self.pill.list_name = selected_list_name
        try:
            self.pill.list_order = int(self.order_var.get()) if selected_list_id else None
        except Exception:
            self.pill.list_order = None
        
        # Update inputs and outputs from text (split by commas/newlines)
        def _parse_io(txt):
            parts = re.split(r'[\,\n]+', (txt or "").strip())
            return [p.strip() for p in parts if p and p.strip()]
        self.pill.inputs = _parse_io(self.inputs_text.get("1.0", tk.END))
        self.pill.outputs = _parse_io(self.outputs_text.get("1.0", tk.END))
        
        self.window.destroy()
    
    def update_pill_from_ui(self):
        """Copy current UI fields into the pill without closing the window"""
        self.pill.name = self.name_var.get()
        self.pill.update_name(self.pill.name)
        self.pill.description = self.desc_text.get("1.0", tk.END).strip()
        self.pill.visual_output = self.visual_output_text.get("1.0", tk.END).strip()
        self.pill.relationships = self.relationships_text.get("1.0", tk.END).strip()

        # Update list selection and order
        selected_list_name = (self.list_var.get() or "").strip()
        selected_list_id = None
        for lid, lname in getattr(self, "_list_options", []):
            if lname == selected_list_name:
                selected_list_id = lid
                break
        self.pill.list_id = selected_list_id
        self.pill.list_name = selected_list_name
        try:
            self.pill.list_order = int(self.order_var.get()) if selected_list_id else None
        except Exception:
            self.pill.list_order = None

        # Update inputs and outputs from text (split by commas/newlines)
        def _parse_io(txt):
            parts = re.split(r'[\,\n]+', (txt or "").strip())
            return [p.strip() for p in parts if p and p.strip()]
        self.pill.inputs = _parse_io(self.inputs_text.get("1.0", tk.END))
        self.pill.outputs = _parse_io(self.outputs_text.get("1.0", tk.END))

    def clear_fields(self):
        """Clear descriptive fields (Inputs, Outputs, Description, Visual Output, Relationships) but keep Function Name, List, and Order unchanged."""
        for txt in [self.desc_text, self.visual_output_text, self.relationships_text, self.inputs_text, self.outputs_text]:
            try:
                txt.delete("1.0", tk.END)
            except Exception:
                pass

    def _on_close(self):
        """Apply pending UI edits to the pill model so views reflect changes without requiring DB update."""
        try:
            self.update_pill_from_ui()
        except Exception:
            pass
        try:
            self.window.destroy()
        except Exception:
            pass

    # Spinner helpers
    def _create_gear_image(self, size, color):
        try:
            if not ("PIL_AVAILABLE" in globals() and PIL_AVAILABLE):
                return None
            from PIL import Image, ImageDraw
            # Supersample for smoother edges, then downscale
            scale = 3
            big = int(size * scale)
            img_large = Image.new("RGBA", (big, big), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img_large)
            cx = cy = big / 2.0

            # Gear geometry
            teeth = 10
            R = big * 0.48          # outer radius
            r_root = big * 0.40     # valley/root radius (closer to R to look more solid)
            dtheta = 2.0 * math.pi / teeth
            tip_flat_frac = 0.55    # fraction of the tooth pitch used for a flat tip
            half_tip = (tip_flat_frac * dtheta) / 2.0
            inner_offset = dtheta / 2.0

            # Build trapezoidal teeth with flat tips
            pts = []
            for t in range(teeth):
                theta = t * dtheta
                # Inner-left valley
                ang1 = theta - inner_offset
                x1 = cx + r_root * math.cos(ang1)
                y1 = cy + r_root * math.sin(ang1)
                pts.append((x1, y1))
                # Outer-left corner of flat tip
                ang2 = theta - half_tip
                x2 = cx + R * math.cos(ang2)
                y2 = cy + R * math.sin(ang2)
                pts.append((x2, y2))
                # Outer-right corner of flat tip
                ang3 = theta + half_tip
                x3 = cx + R * math.cos(ang3)
                y3 = cy + R * math.sin(ang3)
                pts.append((x3, y3))
                # Inner-right valley
                ang4 = theta + inner_offset
                x4 = cx + r_root * math.cos(ang4)
                y4 = cy + r_root * math.sin(ang4)
                pts.append((x4, y4))

            # Gear body with a subtle outline to enhance solidity
            try:
                outline = (0, 0, 0, 90)
                draw.polygon(pts, fill=color, outline=outline)
            except Exception:
                draw.polygon(pts, fill=color)

            # Center hole
            hole_r = big * 0.12
            draw.ellipse((cx - hole_r, cy - hole_r, cx + hole_r, cy + hole_r), fill=(0, 0, 0, 0))

            # Downscale to requested size for anti-aliased edges
            img = img_large.resize((size, size), resample=Image.LANCZOS)
            return img
        except Exception:
            return None

    def _ensure_spinner_assets(self):
        if self._gear_assets is not None:
            return
        sizes = [26, 34, 22]
        colors = [(255, 215, 0, 255), (70, 130, 180, 255), (60, 179, 113, 255)]  # yellow, steelblue, mediumseagreen
        base_images = []
        if "PIL_AVAILABLE" in globals() and PIL_AVAILABLE:
            for sz, col in zip(sizes, colors):
                img = self._create_gear_image(sz, col)
                base_images.append(img)
        else:
            base_images = [None, None, None]
        self._gear_assets = (base_images, sizes, colors)

        # Place initial images/items
        self.gear_canvas.delete("all")
        self._gear_items = []
        self._gear_images_cache = []
        positions = [(25, 30), (60, 30), (95, 30)]
        for idx, (pos, sz) in enumerate(zip(positions, sizes)):
            if base_images[idx] is not None and 'ImageTk' in globals():
                try:
                    from PIL import ImageTk
                    ph = ImageTk.PhotoImage(base_images[idx])
                    self._gear_images_cache.append(ph)
                    item = self.gear_canvas.create_image(pos[0], pos[1], image=ph)
                except Exception:
                    item = self.gear_canvas.create_oval(pos[0]-sz/2, pos[1]-sz/2, pos[0]+sz/2, pos[1]+sz/2, outline="#888")
            else:
                item = self.gear_canvas.create_oval(pos[0]-sz/2, pos[1]-sz/2, pos[0]+sz/2, pos[1]+sz/2, outline="#888")
            self._gear_items.append(item)

    def _animate_spinner(self):
        if not self._spinner_running:
            return
        self._ensure_spinner_assets()
        base_images, sizes, colors = self._gear_assets
        positions = [(25, 30), (60, 30), (95, 30)]
        self._gear_images_cache = []
        self.gear_canvas.delete("all")
        for idx, (pos, sz) in enumerate(zip(positions, sizes)):
            if base_images[idx] is not None and 'ImageTk' in globals():
                try:
                    from PIL import ImageTk
                    # Different gears rotate in opposite directions / speeds
                    ang = (self._spinner_angle * (1 if idx % 2 == 0 else -1)) % 360
                    img = base_images[idx].rotate(ang, resample=Image.BICUBIC, expand=False)
                    ph = ImageTk.PhotoImage(img)
                    self._gear_images_cache.append(ph)
                    self.gear_canvas.create_image(pos[0], pos[1], image=ph)
                except Exception:
                    self.gear_canvas.create_oval(pos[0]-sz/2, pos[1]-sz/2, pos[0]+sz/2, pos[1]+sz/2, outline="#888")
            else:
                self.gear_canvas.create_oval(pos[0]-sz/2, pos[1]-sz/2, pos[0]+sz/2, pos[1]+sz/2, outline="#888")
        self._spinner_angle = (self._spinner_angle + 12) % 360
        self.window.after(80, self._animate_spinner)

    def start_spinner(self, msg="Updating database..."):
        try:
            self._spinner_running = True
            self._spinner_angle = 0
            if hasattr(self, 'gear_label'):
                self.gear_label.configure(text=msg)
            self._ensure_spinner_assets()
            self._animate_spinner()
        except Exception:
            pass

    def stop_spinner(self, msg="Database updated!"):
        self._spinner_running = False
        try:
            if hasattr(self, 'gear_label'):
                self.gear_label.configure(text=msg)
        except Exception:
            pass
    
    def save_to_db(self):
        """Save function as new entry to database (per-project schema)"""
        if not self.ensure_connected():
            return
        app = self.get_app_instance()
        if not app.current_project:
            messagebox.showwarning("No Project", "Please create or open a project first before saving functions to database.")
            return

        # Pull latest UI values into the pill (without closing this window)
        self.update_pill_from_ui()

        # Start spinner
        self.start_spinner("Updating database...")

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
            inputs_json = json.dumps(data['inputs'])
            outputs_json = json.dumps(data['outputs'])
            cursor.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.functions (name, description, visual_output, relationships, x_position, y_position, list_id, list_order, list_name, inputs, outputs)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (name)
                    DO UPDATE SET
                        description = EXCLUDED.description,
                        visual_output = EXCLUDED.visual_output,
                        relationships = EXCLUDED.relationships,
                        x_position = EXCLUDED.x_position,
                        y_position = EXCLUDED.y_position,
                        list_id = EXCLUDED.list_id,
                        list_order = EXCLUDED.list_order,
                        list_name = COALESCE(EXCLUDED.list_name, {}.functions.list_name),
                        inputs = EXCLUDED.inputs,
                        outputs = EXCLUDED.outputs,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                    """
                ).format(sql.Identifier(schema), sql.Identifier(schema)),
                (data['name'], data['description'], data['visual_output'], data['relationships'], data['x'], data['y'], data.get('list_id'), data.get('list_order'), data.get('list_name'), inputs_json, outputs_json),
            )
            function_id = cursor.fetchone()[0]
            self.pill.function_id = function_id

            app.db_manager.connection.commit()
            self.stop_spinner("Database updated!")
            messagebox.showinfo("Success", "Function saved to database!")
        except Exception as e:
            app.db_manager.connection.rollback()
            self.stop_spinner("Update failed")
            messagebox.showerror("Database Error", f"Failed to save: {str(e)}")
    
    def update_in_db(self):
        """Update existing function in database (per-project schema)"""
        if not self.pill.function_id:
            messagebox.showwarning("Database", "This function is not in the database. Use 'Save to DB' first.")
            return
        if not self.ensure_connected():
            return
        app = self.get_app_instance()

        # Pull latest UI values into the pill (without closing this window)
        self.update_pill_from_ui()

        # Start spinner
        self.start_spinner("Updating database...")

        cursor = app.db_manager.connection.cursor()
        try:
            schema = app.db_manager.schema_name_for_project(app.current_project)
            # Update function
            data = self.pill.get_data()
            inputs_json = json.dumps(data['inputs'])
            outputs_json = json.dumps(data['outputs'])
            cursor.execute(
                sql.SQL(
                    """
                    UPDATE {}.functions
                    SET name = %s, description = %s, visual_output = %s, relationships = %s,
                        x_position = %s, y_position = %s, list_id = %s, list_order = %s, list_name = COALESCE(%s, list_name),
                        inputs = %s, outputs = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """
                ).format(sql.Identifier(schema)),
                (data['name'], data['description'], data['visual_output'], data['relationships'], data['x'], data['y'], data.get('list_id'), data.get('list_order'), data.get('list_name'), inputs_json, outputs_json, self.pill.function_id),
            )

            app.db_manager.connection.commit()
            self.stop_spinner("Database updated!")
            messagebox.showinfo("Success", "Function updated in database!")
        except Exception as e:
            app.db_manager.connection.rollback()
            self.stop_spinner("Update failed")
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
                        SELECT name, description, visual_output, relationships, x_position, y_position, list_id, list_order, list_name, inputs, outputs
                        FROM {}.functions WHERE id = %s
                        """
                    ).format(sql.Identifier(schema)),
                    (func_id,),
                )
                func_data = cursor.fetchone()
                if func_data:
                    name, desc, visual_output, relationships, x, y, lid, lorder, list_name_db, inputs_json, outputs_json = func_data

                    # Update UI
                    self.name_var.set(name)
                    self.desc_text.delete("1.0", tk.END)
                    self.desc_text.insert("1.0", desc or "")
                    self.visual_output_text.delete("1.0", tk.END)
                    self.visual_output_text.insert("1.0", visual_output or "")
                    self.relationships_text.delete("1.0", tk.END)
                    self.relationships_text.insert("1.0", relationships or "")

                    # Set inputs/outputs text
                    try:
                        inputs_list = json.loads(inputs_json) if inputs_json else []
                    except Exception:
                        inputs_list = [s.strip() for s in (inputs_json or "").splitlines() if s.strip()]
                    try:
                        outputs_list = json.loads(outputs_json) if outputs_json else []
                    except Exception:
                        outputs_list = [s.strip() for s in (outputs_json or "").splitlines() if s.strip()]
                    self.inputs_text.delete("1.0", tk.END)
                    self.inputs_text.insert("1.0", "\n".join(inputs_list))
                    self.outputs_text.delete("1.0", tk.END)
                    self.outputs_text.insert("1.0", "\n".join(outputs_list))

                    # Set list selection and order in UI (prefer DB list_name if present)
                    try:
                        self.pill.list_id = lid
                        self.pill.list_order = lorder

                        resolved_list_name = (list_name_db or "").strip() or None
                        if not resolved_list_name and lid and hasattr(self, "_list_options"):
                            for rid, rname in self._list_options:
                                if rid == lid:
                                    resolved_list_name = rname
                                    break
                        if resolved_list_name:
                            self.list_var.set(resolved_list_name)
                            try:
                                self.pill.list_name = resolved_list_name
                            except Exception:
                                pass

                        try:
                            self.order_var.set(int(lorder) if lorder else 1)
                        except Exception:
                            self.order_var.set(1)
                    except Exception:
                        pass

                    self.pill.function_id = func_id
                    messagebox.showinfo("Success", "Function loaded from database!")

                dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Load", command=load_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _auto_load_current_function_from_db(self):
        app = self.get_app_instance()
        if not app or not app.current_project or not getattr(app, 'db_manager', None) or not app.db_manager.connected:
            return
        try:
            schema = app.db_manager.schema_name_for_project(app.current_project)
            cur = app.db_manager.connection.cursor()
            if getattr(self.pill, 'function_id', None):
                cur.execute(
                    sql.SQL("SELECT id, name, description, visual_output, relationships, x_position, y_position, list_id, list_order, list_name, inputs, outputs FROM {}.functions WHERE id = %s").format(sql.Identifier(schema)),
                    (self.pill.function_id,)
                )
            else:
                cur.execute(
                    sql.SQL("SELECT id, name, description, visual_output, relationships, x_position, y_position, list_id, list_order, list_name, inputs, outputs FROM {}.functions WHERE name = %s").format(sql.Identifier(schema)),
                    (self.pill.name,)
                )
            row = cur.fetchone()
            if not row:
                return
            fid, name, desc, visual_output, relationships, x, y, lid, lorder, list_name_db, inputs_json, outputs_json = row

            # Update pill model
            self.pill.function_id = fid
            self.pill.name = name
            self.pill.description = desc or ""
            self.pill.visual_output = visual_output or ""
            self.pill.relationships = relationships or ""
            self.pill.list_id = lid
            self.pill.list_order = lorder
            try:
                self.pill.list_name = (list_name_db or self.pill.list_name) or ""
            except Exception:
                pass

            # Update UI text fields
            self.name_var.set(name)
            self.desc_text.delete("1.0", tk.END)
            self.desc_text.insert("1.0", desc or "")
            self.visual_output_text.delete("1.0", tk.END)
            self.visual_output_text.insert("1.0", visual_output or "")
            self.relationships_text.delete("1.0", tk.END)
            self.relationships_text.insert("1.0", relationships or "")

            try:
                inputs_list = json.loads(inputs_json) if inputs_json else []
            except Exception:
                inputs_list = [s.strip() for s in (inputs_json or "").splitlines() if s.strip()]
            try:
                outputs_list = json.loads(outputs_json) if outputs_json else []
            except Exception:
                outputs_list = [s.strip() for s in (outputs_json or "").splitlines() if s.strip()]

            self.inputs_text.delete("1.0", tk.END)
            self.inputs_text.insert("1.0", "\n".join(inputs_list))
            self.outputs_text.delete("1.0", tk.END)
            self.outputs_text.insert("1.0", "\n".join(outputs_list))

            # Resolve list name and set order
            list_name = None
            if lid and hasattr(self, "_list_options"):
                for rid, rname in self._list_options:
                    if rid == lid:
                        list_name = rname
                        break
            if not list_name and lid and app.db_manager.connected:
                try:
                    cur.execute(sql.SQL("SELECT name FROM {}.function_lists WHERE id = %s").format(sql.Identifier(schema)), (lid,))
                    r = cur.fetchone()
                    if r:
                        list_name = r[0]
                except Exception:
                    try:
                        app.db_manager.connection.rollback()
                    except Exception:
                        pass

            if list_name:
                self.list_var.set(list_name)
                self.pill.list_name = list_name
            elif (list_name_db or "").strip():
                self.list_var.set(list_name_db)
                self.pill.list_name = list_name_db

            try:
                self.order_var.set(int(lorder) if lorder else 1)
            except Exception:
                self.order_var.set(1)
        except Exception:
            try:
                app.db_manager.connection.rollback()
            except Exception:
                pass
            # Fail silently to keep UI responsive
    
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
            # Immediately sync current UI state back to the pill model
            try:
                self.update_pill_from_ui()
            except Exception:
                pass
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

class NewFunctionDialog:
    """Dialog to create a new function with list assignment and ordering."""
    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.db = app.db_manager
        self.project = app.current_project
        self.result = None

        self.window = tk.Toplevel(self.root)
        self.window.title("New Function")
        try:
            self.window.configure(bg="#f2f2f2")
            self.window.minsize(520, 200)
            self.window.update_idletasks()
            sw = self.window.winfo_screenwidth()
            sh = self.window.winfo_screenheight()
            w, h = 560, 240
            x = max((sw - w) // 2, 0)
            y = max((sh - h) // 2, 0)
            self.window.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            self.window.geometry("520x200")
        self.window.transient(self.root)
        self.window.grab_set()

        frm = tk.Frame(self.window, bg="#f2f2f2", highlightthickness=0)
        frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        ttk.Label(frm, text="Function Name:").grid(row=0, column=0, sticky=tk.E, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.name_var, width=40).grid(row=0, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        ttk.Label(frm, text="List:").grid(row=1, column=0, sticky=tk.E, pady=5)
        self.list_var = tk.StringVar(value="")
        self.list_combo = ttk.Combobox(frm, textvariable=self.list_var, state="readonly", width=28)
        self.list_combo.grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Label(frm, text="Order:").grid(row=1, column=2, sticky=tk.E, padx=(10, 2))
        self.order_var = tk.IntVar(value=1)
        try:
            self.order_spin = tk.Spinbox(frm, from_=1, to=9999, width=6, textvariable=self.order_var)
        except Exception:
            self.order_spin = ttk.Entry(frm, textvariable=self.order_var, width=6)
        self.order_spin.grid(row=1, column=3, sticky=tk.W)

        # Buttons
        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, columnspan=4, pady=10)
        ttk.Button(btns, text="Manage Lists", command=self._open_manage_lists).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Create", command=self._create).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Cancel", command=self.window.destroy).pack(side=tk.LEFT, padx=4)

        frm.columnconfigure(1, weight=1)

        # Load list options
        self._schema = self.db.schema_name_for_project(self.project) if (self.db.connected and self.project) else None
        self._list_options = []
        self._load_list_options()
        self.list_combo.bind("<<ComboboxSelected>>", lambda e: self._auto_set_order())

    def _load_list_options(self):
        names = []
        self._list_options = []
        if self.db.connected and self.project:
            try:
                self.db.ensure_project_schema(self.project)
                cur = self.db.connection.cursor()
                cur.execute(sql.SQL("SELECT id, name FROM {}.function_lists ORDER BY name").format(sql.Identifier(self._schema)))
                rows = cur.fetchall()
                self._list_options = rows
                names = [r[1] for r in rows]
            except Exception:
                try:
                    self.db.connection.rollback()
                except Exception:
                    pass
        self.list_combo["values"] = names

    def _auto_set_order(self):
        sel_name = self.list_var.get()
        lid = None
        for i, (rid, rname) in enumerate(self._list_options):
            if rname == sel_name:
                lid = rid
                break
        if lid and self.db.connected and self.project:
            try:
                cur = self.db.connection.cursor()
                cur.execute(sql.SQL("SELECT COALESCE(MAX(list_order), 0) + 1 FROM {}.functions WHERE list_id = %s").format(sql.Identifier(self._schema)), (lid,))
                next_ord = cur.fetchone()[0] or 1
                self.order_var.set(int(next_ord))
            except Exception:
                try:
                    self.db.connection.rollback()
                except Exception:
                    pass
                self.order_var.set(1)
        else:
            self.order_var.set(1)

    def _open_manage_lists(self):
        dlg = ListManagerDialog(self.app)
        try:
            dlg.window.wait_window()
        except Exception:
            pass
        self._load_list_options()

    def _create(self):
        name = (self.name_var.get() or "").strip()
        if not name:
            messagebox.showwarning("Input Required", "Enter a function name.")
            return
        sel_name = self.list_var.get()
        sel_id = None
        for rid, rname in self._list_options:
            if rname == sel_name:
                sel_id = rid
                break
        try:
            order = int(self.order_var.get()) if sel_id else None
        except Exception:
            order = None
        self.result = {"name": name, "list_id": sel_id, "list_order": order, "list_name": sel_name}
        self.window.destroy()

class ListManagerDialog:
    """Dialog to manage list names (add/rename/delete) stored per project in PostgreSQL."""
    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.db = app.db_manager
        self.project = app.current_project

        self.window = tk.Toplevel(self.root)
        self.window.title("Manage Lists")
        try:
            self.window.update_idletasks()
            sw = self.window.winfo_screenwidth()
            sh = self.window.winfo_screenheight()
            w, h = 460, 360
            x = max((sw - w) // 2, 0)
            y = max((sh - h) // 2, 0)
            self.window.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            self.window.geometry("460x360")
        self.window.transient(self.root)
        self.window.grab_set()

        # Layout frames
        main = ttk.Frame(self.window, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right = ttk.Frame(main)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))

        # Existing lists
        ttk.Label(left, text="Existing Lists:").pack(anchor=tk.W)
        self.listbox = tk.Listbox(left)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        # Entry for name
        ttk.Label(right, text="List Name:").pack(anchor=tk.W)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(right, textvariable=self.name_var, width=28)
        self.name_entry.pack(fill=tk.X, pady=(0, 8))

        # Buttons
        ttk.Button(right, text="Add", command=self.add_list).pack(fill=tk.X, pady=2)
        ttk.Button(right, text="Save", command=self._save_and_close).pack(fill=tk.X, pady=2)
        ttk.Button(right, text="Rename", command=self.rename_list).pack(fill=tk.X, pady=2)
        ttk.Button(right, text="Delete", command=self.delete_list).pack(fill=tk.X, pady=2)
        ttk.Button(right, text="Close", command=self.window.destroy).pack(fill=tk.X, pady=(12, 0))

        # Status label
        self.status_var = tk.StringVar(value="")
        ttk.Label(self.window, textvariable=self.status_var, foreground="#555").pack(anchor=tk.W, padx=12, pady=(0, 8))

        # Load data
        self._schema = self.db.schema_name_for_project(self.project)
        # Enter key adds the list
        try:
            self.name_entry.bind("<Return>", lambda e: self.add_list())
        except Exception:
            pass
        self._load_lists()

    def _load_lists(self):
        try:
            cur = self.db.connection.cursor()
            cur.execute(
                sql.SQL("SELECT id, name FROM {}.function_lists ORDER BY name").format(sql.Identifier(self._schema))
            )
            rows = cur.fetchall()
        except Exception as e:
            try:
                self.db.connection.rollback()
            except Exception:
                pass
            messagebox.showerror("Database", f"Failed to load lists: {e}")
            rows = []
        self.listbox.delete(0, tk.END)
        self._id_by_index = []
        for rid, name in rows:
            self.listbox.insert(tk.END, name)
            self._id_by_index.append((rid, name))
        self.status_var.set(f"{len(rows)} lists loaded")

    def on_select(self, event=None):
        sel = self.listbox.curselection()
        if sel:
            _, name = self._id_by_index[sel[0]]
            self.name_var.set(name)

    def _selected(self):
        sel = self.listbox.curselection()
        return self._id_by_index[sel[0]] if sel else (None, None)

    def add_list(self):
        name = (self.name_var.get() or "").strip()
        if not name:
            messagebox.showwarning("Input Required", "Enter a list name to add.")
            return
        try:
            cur = self.db.connection.cursor()
            # Insert if not exists
            cur.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.function_lists (name)
                    VALUES (%s)
                    ON CONFLICT (name) DO NOTHING
                    """
                ).format(sql.Identifier(self._schema)),
                (name,),
            )
            self.db.connection.commit()
            self._load_lists()
            self.status_var.set(f"Added list '{name}' (if it did not already exist)")
        except Exception as e:
            try:
                self.db.connection.rollback()
            except Exception:
                pass
            messagebox.showerror("Database", f"Failed to add list: {e}")

    def _save_and_close(self):
        # Convenience action: add the list if provided, then close dialog
        added = False
        nm = (self.name_var.get() or '').strip()
        if nm:
            try:
                self.add_list()
                added = True
            except Exception:
                pass
        try:
            self.window.destroy()
        except Exception:
            pass

    def rename_list(self):
        sel_id, sel_name = self._selected()
        if sel_id is None and not self.name_var.get().strip():
            messagebox.showwarning("Select List", "Select a list or enter its current name to rename.")
            return
        # Determine current name / id
        if sel_id is None:
            # Find id by entered name
            current_name = self.name_var.get().strip()
            try:
                cur = self.db.connection.cursor()
                cur.execute(
                    sql.SQL("SELECT id FROM {}.function_lists WHERE name = %s").format(sql.Identifier(self._schema)),
                    (current_name,),
                )
                row = cur.fetchone()
                if not row:
                    messagebox.showwarning("Not Found", f"List '{current_name}' does not exist.")
                    return
                sel_id = row[0]
                sel_name = current_name
            except Exception as e:
                try:
                    self.db.connection.rollback()
                except Exception:
                    pass
                messagebox.showerror("Database", f"Lookup failed: {e}")
                return
        # Ask for new name
        new_name = simpledialog.askstring("Rename List", "Enter new name:", initialvalue=sel_name, parent=self.window)
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name:
            messagebox.showwarning("Invalid Name", "New name cannot be empty.")
            return
        try:
            cur = self.db.connection.cursor()
            # Ensure no duplicate
            cur.execute(
                sql.SQL("SELECT 1 FROM {}.function_lists WHERE name = %s").format(sql.Identifier(self._schema)),
                (new_name,),
            )
            if cur.fetchone():
                messagebox.showwarning("Exists", f"A list named '{new_name}' already exists.")
                return
            cur.execute(
                sql.SQL(
                    "UPDATE {}.function_lists SET name = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
                ).format(sql.Identifier(self._schema)),
                (new_name, sel_id),
            )
            self.db.connection.commit()
            self._load_lists()
            self.name_var.set(new_name)
            self.status_var.set(f"Renamed list to '{new_name}'")
        except Exception as e:
            try:
                self.db.connection.rollback()
            except Exception:
                pass
            messagebox.showerror("Database", f"Failed to rename list: {e}")

    def delete_list(self):
        sel_id, sel_name = self._selected()
        target_name = sel_name or self.name_var.get().strip()
        if not sel_id:
            # resolve by name
            if not target_name:
                messagebox.showwarning("Select List", "Select a list or enter its name to delete.")
                return
            try:
                cur = self.db.connection.cursor()
                cur.execute(
                    sql.SQL("SELECT id FROM {}.function_lists WHERE name = %s").format(sql.Identifier(self._schema)),
                    (target_name,),
                )
                row = cur.fetchone()
                if not row:
                    messagebox.showwarning("Not Found", f"List '{target_name}' does not exist.")
                    return
                sel_id = row[0]
            except Exception as e:
                try:
                    self.db.connection.rollback()
                except Exception:
                    pass
                messagebox.showerror("Database", f"Lookup failed: {e}")
                return
        if not target_name:
            target_name = "the selected list"
        if not messagebox.askyesno("Delete List", f"Are you sure you want to delete '{target_name}'?", parent=self.window):
            return
        try:
            cur = self.db.connection.cursor()
            cur.execute(
                sql.SQL("DELETE FROM {}.function_lists WHERE id = %s").format(sql.Identifier(self._schema)),
                (sel_id,),
            )
            self.db.connection.commit()
            self._load_lists()
            self.name_var.set("")
            self.status_var.set(f"Deleted list '{target_name}'")
        except Exception as e:
            try:
                self.db.connection.rollback()
            except Exception:
                pass
            messagebox.showerror("Database", f"Failed to delete list: {e}")

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
            CREATE TABLE IF NOT EXISTS public.projects (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Ensure unique index on project name for ON CONFLICT to work
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_name_unique ON projects(name)")
        # Ensure columns for mapping snapshots exist on projects table
        try:
            cursor.execute("ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS mapping_image BYTEA")
            cursor.execute("ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS mapping_image_w INTEGER")
            cursor.execute("ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS mapping_image_h INTEGER")
            cursor.execute("ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS mapping_layout TEXT")
            cursor.execute("ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS mapping_updated_at TIMESTAMP")
            cursor.execute("ALTER TABLE public.projects ADD COLUMN IF NOT EXISTS objective TEXT")
        except Exception:
            # If the server doesn't support IF NOT EXISTS on ALTER, ignore; columns may already exist
            try:
                self.connection.rollback()
            except Exception:
                pass
        
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
                list_id INTEGER,
                list_order INTEGER,
                list_name TEXT,
                inputs TEXT,
                outputs TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """).format(sql.Identifier(schema)))
        # Ensure columns exist for older schemas
        cur.execute(sql.SQL("ALTER TABLE {}.functions ADD COLUMN IF NOT EXISTS list_id INTEGER").format(sql.Identifier(schema)))
        cur.execute(sql.SQL("ALTER TABLE {}.functions ADD COLUMN IF NOT EXISTS list_order INTEGER").format(sql.Identifier(schema)))
        cur.execute(sql.SQL("ALTER TABLE {}.functions ADD COLUMN IF NOT EXISTS list_name TEXT").format(sql.Identifier(schema)))
        cur.execute(sql.SQL("ALTER TABLE {}.functions ADD COLUMN IF NOT EXISTS inputs TEXT").format(sql.Identifier(schema)))
        cur.execute(sql.SQL("ALTER TABLE {}.functions ADD COLUMN IF NOT EXISTS outputs TEXT").format(sql.Identifier(schema)))
        # Ensure unique name per project to prevent duplicates and enable upsert
        cur.execute(
            sql.SQL("CREATE UNIQUE INDEX IF NOT EXISTS functions_name_unique ON {}.functions(name)")
               .format(sql.Identifier(schema))
        )
                        
        # Create function lists table (stores list names per project)
        cur.execute(sql.SQL("""
            CREATE TABLE IF NOT EXISTS {}.function_lists (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """).format(sql.Identifier(schema)))
        # Ensure unique list name per project
        cur.execute(
            sql.SQL("CREATE UNIQUE INDEX IF NOT EXISTS function_lists_name_unique ON {}.function_lists(name)")
               .format(sql.Identifier(schema))
        )

        # Project-level info table (stores objective and future metadata) within this project's schema
        cur.execute(sql.SQL("""
            CREATE TABLE IF NOT EXISTS {}.project_info (
                id SMALLINT PRIMARY KEY,
                objective TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """).format(sql.Identifier(schema)))

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
                inputs_json = json.dumps(data['inputs'])
                outputs_json = json.dumps(data['outputs'])
                cursor.execute(
                    sql.SQL(
                        """
                        INSERT INTO {}.functions (name, description, visual_output, relationships, x_position, y_position, list_id, list_order, list_name, inputs, outputs)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """
                    ).format(sql.Identifier(schema)),
                    (data['name'], data['description'], data['visual_output'], data['relationships'], data['x'], data['y'], data.get('list_id'), data.get('list_order'), data.get('list_name'), inputs_json, outputs_json),
                )
                function_id = cursor.fetchone()[0]
                # Keep in-memory pill linked to its DB row for future updates
                try:
                    pill.function_id = function_id
                except Exception:
                    pass

                
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
                    SELECT id, name, description, visual_output, relationships, x_position, y_position, list_id, list_order, list_name, inputs, outputs
                    FROM {}.functions
                    """
                ).format(sql.Identifier(schema))
            )
            for func in cursor.fetchall():
                func_id, name, desc, visual_output, relationships, x, y, list_id, list_order, list_name, inputs_json, outputs_json = func

                try:
                    inputs = json.loads(inputs_json) if inputs_json else []
                except Exception:
                    inputs = [s.strip() for s in (inputs_json or "").splitlines() if s.strip()]

                try:
                    outputs = json.loads(outputs_json) if outputs_json else []
                except Exception:
                    outputs = [s.strip() for s in (outputs_json or "").splitlines() if s.strip()]

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
                        'list_id': list_id,
                        'list_order': list_order,
                        'list_name': list_name,
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
        try:
            # Clear any aborted transaction so subsequent queries can run
            try:
                self.connection.rollback()
            except Exception:
                pass
            try:
                cursor.execute("SELECT name FROM public.projects ORDER BY name")
                return [row[0] for row in cursor.fetchall()]
            except Exception as e:
                # Attempt to bootstrap catalog table if missing, then retry
                try:
                    self.connection.rollback()
                except Exception:
                    pass
                if 'relation "public.projects" does not exist' in str(e):
                    try:
                        cursor = self.connection.cursor()
                        cursor.execute(
                            """
                            CREATE TABLE IF NOT EXISTS public.projects (
                                id SERIAL PRIMARY KEY,
                                name TEXT UNIQUE NOT NULL,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                mapping_image BYTEA,
                                mapping_image_w INTEGER,
                                mapping_image_h INTEGER,
                                mapping_layout TEXT,
                                mapping_updated_at TIMESTAMP,
                                objective TEXT
                            )
                            """
                        )
                        self.connection.commit()
                        cursor = self.connection.cursor()
                        cursor.execute("SELECT name FROM public.projects ORDER BY name")
                        return [row[0] for row in cursor.fetchall()]
                    except Exception:
                        try:
                            self.connection.rollback()
                        except Exception:
                            pass
                # Re-raise if not recoverable
                raise
        except Exception:
            try:
                self.connection.rollback()
            except Exception:
                pass
            raise
        
    def get_project_objective(self, project_name):
        """Fetch objective text from the per-project schema's project_info table."""
        if not self.connected or not project_name:
            return None
        try:
            schema = self.schema_name_for_project(project_name)
            cur = self.connection.cursor()
            cur.execute(
                sql.SQL("SELECT objective FROM {}.project_info WHERE id = 1").format(sql.Identifier(schema))
            )
            row = cur.fetchone()
            return (row[0] if row else None) or None
        except Exception:
            try:
                self.connection.rollback()
            except Exception:
                pass
            return None

    def set_project_objective(self, project_name, objective_text):
        """Upsert objective text into the per-project schema's project_info table."""
        if not self.connected or not project_name:
            return False
        try:
            schema = self.schema_name_for_project(project_name)
            cur = self.connection.cursor()
            # Ensure project schema exists
            self.ensure_project_schema(project_name)
            # Single-row upsert using id=1
            cur.execute(
                sql.SQL(
                    """
                    INSERT INTO {}.project_info (id, objective)
                    VALUES (1, %s)
                    ON CONFLICT (id) DO UPDATE
                    SET objective = EXCLUDED.objective, updated_at = CURRENT_TIMESTAMP
                    """
                ).format(sql.Identifier(schema)),
                (objective_text or None,),
            )
            self.connection.commit()
            return True
        except Exception:
            try:
                self.connection.rollback()
            except Exception:
                pass
            return False
        
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

    def save_mapping_snapshot(self, project_name, png_bytes, width, height, layout_json):
        """Persist a PNG snapshot and layout JSON on the projects table. Returns True on success, False otherwise."""
        if not self.connected:
            return False
        try:
            cur = self.connection.cursor()
            cur.execute(
                """
                UPDATE projects
                SET mapping_image = %s,
                    mapping_image_w = %s,
                    mapping_image_h = %s,
                    mapping_layout = %s,
                    mapping_updated_at = CURRENT_TIMESTAMP
                WHERE name = %s
                """,
                (psycopg2.Binary(png_bytes), int(width or 0), int(height or 0), layout_json, project_name),
            )
            self.connection.commit()
            return True
        except Exception:
            try:
                self.connection.rollback()
            except Exception:
                pass
            return False


class LogicalMappingViewer:
    """Dedicated stable viewer for Logical Mapping with zoom, scrollbars, and DB snapshot export."""
    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.db = app.db_manager
        self.win = None
        self.canvas = None
        self.hbar = None
        self.vbar = None
        self.scale = 1.0
        self.min_scale = 0.5
        self.max_scale = 2.0
        self._layout = None  # cache of computed layout model
        self._required_w = 1600
        self._required_h = 900

        # Layout constants
        self.left_margin = 40
        self.right_margin = 40
        self.top_margin = 80
        self.bottom_margin = 80
        self.lane_width = 240
        self.lane_gap = 30
        self.step_height = 120
        self.node_w = 160
        self.node_h = 44
        self.node_gap_x = 16

    def show(self):
        self.win = tk.Toplevel(self.root)
        self.win.title("Logical Mapping Viewer")
        try:
            self.win.minsize(1200, 800)
        except Exception:
            pass
        outer = ttk.Frame(self.win)
        outer.pack(fill=tk.BOTH, expand=True)

        # Toolbar
        toolbar = ttk.Frame(outer)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(toolbar, text="Refresh", command=self.render).pack(side=tk.LEFT, padx=4)
        ttk.Button(toolbar, text="-", width=3, command=lambda: self.set_scale(self.scale * 0.9)).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="100%", command=lambda: self.set_scale(1.0)).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="+", width=3, command=lambda: self.set_scale(self.scale * 1.1)).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="Save Snapshot", command=self.save_snapshot_to_db).pack(side=tk.LEFT, padx=8)

        # Scrollable canvas
        canvas_frame = ttk.Frame(outer)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(canvas_frame, bg="#ffffff")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.hbar = ttk.Scrollbar(outer, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.configure(yscrollcommand=self.vbar.set, xscrollcommand=self.hbar.set)

        # Disable redraw on canvas <Configure> to keep layout stable
        # Only the scrollregion is updated when we render
        self.render()
        try:
            self.win.focus_set()
        except Exception:
            pass

    def set_scale(self, new_scale: float):
        new_scale = max(self.min_scale, min(self.max_scale, float(new_scale)))
        if abs(new_scale - self.scale) < 1e-3:
            return
        factor = new_scale / self.scale
        self.scale = new_scale
        try:
            self.canvas.scale("all", 0, 0, factor, factor)
            # Update scrollregion proportionally
            self.canvas.configure(scrollregion=(0, 0, int(self._required_w * self.scale), int(self._required_h * self.scale)))
        except Exception:
            pass

    def _auto_upsert_pills(self):
        # Best-effort upsert so the viewer reflects latest edits without manual DB clicks
        try:
            if getattr(self.app, 'db_manager', None) and self.db.connected and self.app.current_project:
                self.db.ensure_project_schema(self.app.current_project)
                schema = self.db.schema_name_for_project(self.app.current_project)
                cur = self.db.connection.cursor()
                for pill in list(getattr(self.app, 'pills', []) or []):
                    data = pill.get_data()
                    inputs_json = json.dumps(data.get('inputs') or [])
                    outputs_json = json.dumps(data.get('outputs') or [])
                    cur.execute(
                        sql.SQL(
                            """
                            INSERT INTO {}.functions (name, description, visual_output, relationships, x_position, y_position, list_id, list_order, list_name, inputs, outputs)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (name)
                            DO UPDATE SET
                                description = EXCLUDED.description,
                                visual_output = EXCLUDED.visual_output,
                                relationships = EXCLUDED.relationships,
                                x_position = EXCLUDED.x_position,
                                y_position = EXCLUDED.y_position,
                                list_id = EXCLUDED.list_id,
                                list_order = EXCLUDED.list_order,
                                list_name = COALESCE(EXCLUDED.list_name, {}.functions.list_name),
                                inputs = EXCLUDED.inputs,
                                outputs = EXCLUDED.outputs,
                                updated_at = CURRENT_TIMESTAMP
                            """
                        ).format(sql.Identifier(schema)),
                        (
                            data.get('name'), data.get('description'), data.get('visual_output'), data.get('relationships'),
                            data.get('x'), data.get('y'), data.get('list_id'), data.get('list_order'), data.get('list_name'),
                            inputs_json, outputs_json,
                        ),
                    )
                self.db.connection.commit()
        except Exception:
            try:
                self.db.connection.rollback()
            except Exception:
                pass

    def _build_graph_from_memory(self):
        """Build graph from in-memory pills without requiring DB or extractor."""
        try:
            pills = list(getattr(self.app, 'pills', []) or [])
            if not pills:
                return {}, [], {'lane_names': [], 'step_orders': [], 'bucket_by_lane_step': {}}
            names = []
            nodes = {}
            for pill in pills:
                nm = (getattr(pill, 'name', '') or '').strip()
                if not nm:
                    continue
                names.append(nm)
                nodes[nm] = {
                    'list_id': getattr(pill, 'list_id', None),
                    'list_name': getattr(pill, 'list_name', '') or '(Unassigned)',
                    'list_order': getattr(pill, 'list_order', None),
                    'relationships_raw': getattr(pill, 'relationships', '') or '',
                }
            name_set_norm = {n.lower().strip(): n for n in names}
            edges_set = set()
            for src in names:
                rel_text = nodes[src].get('relationships_raw') or ''
                for line in rel_text.splitlines():
                    if line.strip().lower().startswith('related to:'):
                        rest = line.split(':', 1)[1]
                        for target in [t.strip() for t in rest.split(',') if t.strip()]:
                            dst_norm = name_set_norm.get(target.lower())
                            if dst_norm and dst_norm != src:
                                edges_set.add((src, dst_norm))
            edges = sorted(list(edges_set))
            # lanes
            lane_names_seq = []
            seen = set()
            for n in names:
                lname = nodes[n].get('list_name') or '(Unassigned)'
                if lname not in seen:
                    seen.add(lname)
                    lane_names_seq.append(lname)
            if '(Unassigned)' in lane_names_seq:
                lane_names_seq = [l for l in lane_names_seq if l != '(Unassigned)'] + ['(Unassigned)']
            # steps
            orders_all = [nodes[n].get('list_order') for n in names]
            orders_unique = sorted({o for o in orders_all if o is not None})
            if any(o is None for o in orders_all):
                orders_unique.append(None)
            bucket_by_lane_step = {}
            for n in names:
                lname = nodes[n].get('list_name') or '(Unassigned)'
                order = nodes[n].get('list_order')
                bucket_by_lane_step.setdefault(lname, {}).setdefault(order, []).append(n)
            return nodes, edges, {'lane_names': lane_names_seq, 'step_orders': orders_unique, 'bucket_by_lane_step': bucket_by_lane_step}
        except Exception:
            return {}, [], {'lane_names': [], 'step_orders': [], 'bucket_by_lane_step': {}}

    def _build_graph_from_db(self):
        """Fallback: build graph directly from DB when no in-memory pills are available."""
        try:
            if not self.app.current_project or not self.db.connected:
                return {}, [], {'lane_names': [], 'step_orders': [], 'bucket_by_lane_step': {}}
            rows = self.db.load_project(self.app.current_project) or []
            if not rows:
                return {}, [], {'lane_names': [], 'step_orders': [], 'bucket_by_lane_step': {}}

            # Nodes and name index
            nodes = {}
            names = []
            for r in rows:
                nm = (r.get('name') or '').strip()
                if not nm:
                    continue
                names.append(nm)
                nodes[nm] = {
                    'list_id': r.get('list_id'),
                    'list_name': r.get('list_name') or '(Unassigned)',
                    'list_order': r.get('list_order'),
                    'relationships_raw': r.get('relationships') or '',
                }
            name_set_norm = {n.lower().strip(): n for n in names}

            # Edges parsed from relationships
            edges_set = set()
            for src in names:
                rel_text = (nodes[src].get('relationships_raw') or '')
                for line in rel_text.splitlines():
                    if line.strip().lower().startswith('related to:'):
                        rest = line.split(':', 1)[1]
                        for target in [t.strip() for t in rest.split(',') if t.strip()]:
                            dst_norm = name_set_norm.get(target.lower())
                            if dst_norm and dst_norm != src:
                                edges_set.add((src, dst_norm))
            edges = sorted(list(edges_set))

            # Lanes and steps
            lane_names_set = []
            for n in names:
                lname = nodes[n].get('list_name') or '(Unassigned)'
                lane_names_set.append(lname)
            # Stable unique order preserving
            lane_names_unique = []
            seen = set()
            for l in lane_names_set:
                if l not in seen:
                    seen.add(l)
                    lane_names_unique.append(l)
            # Move Unassigned to end
            if '(Unassigned)' in lane_names_unique:
                lane_names_unique = [l for l in lane_names_unique if l != '(Unassigned)'] + ['(Unassigned)']

            # Steps by order
            orders = []
            for n in names:
                orders.append(nodes[n].get('list_order'))
            # Unique sorted with None last
            orders_unique = sorted({o for o in orders if o is not None})
            if any(o is None for o in orders):
                orders_unique.append(None)

            # Bucketization
            bucket_by_lane_step = {}
            for n in names:
                lname = nodes[n].get('list_name') or '(Unassigned)'
                order = nodes[n].get('list_order')
                bucket_by_lane_step.setdefault(lname, {}).setdefault(order, []).append(n)

            return nodes, edges, {
                'lane_names': lane_names_unique,
                'step_orders': orders_unique,
                'bucket_by_lane_step': bucket_by_lane_step,
            }
        except Exception:
            return {}, [], {'lane_names': [], 'step_orders': [], 'bucket_by_lane_step': {}}

    def _compute_layout(self):
        # Build graph model (prefer in-memory, then extractor, then DB)
        nodes, edges, lanes = self._build_graph_from_memory()
        if (not nodes) or (not lanes) or (not lanes.get('lane_names')):
            try:
                nodes, edges, lanes = self.app.extract_function_graph(include_db=True)
            except Exception:
                nodes, edges, lanes = {}, [], {'lane_names': [], 'step_orders': [], 'bucket_by_lane_step': {}}
        if (not nodes) or (not lanes) or (not lanes.get('lane_names')):
            nodes, edges, lanes = self._build_graph_from_db()
        lane_names = lanes.get('lane_names', [])
        step_orders = lanes.get('step_orders', [])
        bucket_by_lane_step = lanes.get('bucket_by_lane_step', {})

        lane_index = {name: i for i, name in enumerate(lane_names)}
        step_index = {order: i for i, order in enumerate(step_orders)}

        # Coordinates for nodes by name
        positions = {}
        for lname in lane_names:
            for order in step_orders:
                bucket = bucket_by_lane_step.get(lname, {}).get(order, [])
                if not bucket:
                    continue
                # Distribute within the lane cell horizontally
                lane_i = lane_index[lname]
                step_i = step_index[order]
                base_x = self.left_margin + lane_i * (self.lane_width + self.lane_gap)
                base_y = self.top_margin + step_i * self.step_height
                for j, fn in enumerate(bucket):
                    x = base_x + (self.lane_width - self.node_w) / 2 + (j % 2) * self.node_gap_x - (self.node_gap_x if j % 2 else 0)
                    y = base_y + 20 + (j // 2) * (self.node_h + 8)
                    positions[fn] = (x, y)

        # Required drawable area
        req_w = self.left_margin + len(lane_names) * (self.lane_width + self.lane_gap) - self.lane_gap + self.right_margin
        req_w = max(req_w, 800)
        req_h = self.top_margin + len(step_orders) * self.step_height + self.bottom_margin
        req_h = max(req_h, 600)

        return {
            'nodes': nodes,
            'edges': edges,
            'lane_names': lane_names,
            'step_orders': step_orders,
            'positions': positions,
            'req_w': req_w,
            'req_h': req_h,
        }

    def render(self):
        # Keep DB synced (best effort) and recompute layout
        self._auto_upsert_pills()
        self._layout = self._compute_layout()
        self._required_w = self._layout['req_w']
        self._required_h = self._layout['req_h']

        c = self.canvas
        c.delete("all")
        c.configure(scrollregion=(0, 0, int(self._required_w * self.scale), int(self._required_h * self.scale)))

        lane_names = self._layout['lane_names']
        step_orders = self._layout['step_orders']
        positions = self._layout['positions']
        nodes = self._layout['nodes']
        edges = self._layout['edges']

        # Draw lane titles and vertical separators
        for i, lname in enumerate(lane_names):
            x0 = self.left_margin + i * (self.lane_width + self.lane_gap)
            c.create_text(x0 + self.lane_width / 2, self.top_margin - 40, text=lname, font=("Arial", 12, "bold"), fill="#222")
            # Lane boundary (light)
            c.create_rectangle(x0, self.top_margin - 20, x0 + self.lane_width, self.top_margin + len(step_orders) * self.step_height, outline="#eee")

        # Draw horizontal step grid
        for s, order in enumerate(step_orders):
            y = self.top_margin + s * self.step_height
            c.create_line(self.left_margin - 10, y, self.left_margin + len(lane_names) * (self.lane_width + self.lane_gap) - self.lane_gap + 10, y, fill="#f0f0f0")
            c.create_text(self.left_margin - 24, y + 6, text=str(order), font=("Arial", 9), fill="#777")

        # Draw nodes
        node_drawn = False
        for name, meta in nodes.items():
            if name not in positions:
                continue
            x, y = positions[name]
            c.create_rectangle(x, y, x + self.node_w, y + self.node_h, fill="#4A90E2", outline="#2E5C8A", width=2)
            c.create_text(x + self.node_w/2, y + self.node_h/2, text=name, fill="white", font=("Arial", 10, "bold"))
            node_drawn = True

        # Draw edges (simple straight lines)
        for src, dst in edges:
            if src in positions and dst in positions:
                x1, y1 = positions[src]
                x2, y2 = positions[dst]
                x1 += self.node_w
                y1 += self.node_h/2
                y2 += self.node_h/2
                c.create_line(x1, y1, x2, y2, arrow=tk.LAST, fill="#444")

        # Apply current zoom
        if abs(self.scale - 1.0) > 1e-3:
            try:
                self.canvas.scale("all", 0, 0, self.scale, self.scale)
            except Exception:
                pass

        if not node_drawn:
            try:
                c.create_text(400, 200, text="No functions to display", fill="#777", font=("Arial", 14, "italic"))
            except Exception:
                pass

        # Update status
        try:
            self.app.status_var.set(f"Logical Mapping rendered: {len(nodes)} nodes, {len(edges)} edges")
        except Exception:
            pass

    def save_snapshot_to_db(self):
        # Build snapshot image using PIL (if available)
        if not ("PIL_AVAILABLE" in globals() and PIL_AVAILABLE):
            messagebox.showwarning("Snapshot", "Pillow is not available; cannot save PNG snapshot.")
            return
        if not self.app.current_project:
            messagebox.showwarning("Project", "Open or create a project to save a snapshot.")
            return
        try:
            from PIL import Image, ImageDraw, ImageFont
            W, H = int(self._required_w), int(self._required_h)
            img = Image.new("RGB", (max(W, 10), max(H, 10)), (255, 255, 255))
            drw = ImageDraw.Draw(img)
            try:
                font_title = ImageFont.truetype("arial.ttf", 14)
                font_node = ImageFont.truetype("arial.ttf", 12)
            except Exception:
                font_title = None
                font_node = None

            lane_names = self._layout['lane_names']
            step_orders = self._layout['step_orders']
            positions = self._layout['positions']
            nodes = self._layout['nodes']
            edges = self._layout['edges']

            # Lanes and grid
            for i, lname in enumerate(lane_names):
                x0 = self.left_margin + i * (self.lane_width + self.lane_gap)
                drw.text((x0 + self.lane_width/2 - 40, self.top_margin - 50), lname, fill=(34,34,34), font=font_title)
                drw.rectangle([x0, self.top_margin - 20, x0 + self.lane_width, self.top_margin + len(step_orders) * self.step_height], outline=(238,238,238))
            for s, order in enumerate(step_orders):
                y = self.top_margin + s * self.step_height
                drw.line([self.left_margin - 10, y, self.left_margin + len(lane_names) * (self.lane_width + self.lane_gap) - self.lane_gap + 10, y], fill=(240,240,240))
                drw.text((self.left_margin - 34, y + 0), str(order), fill=(119,119,119), font=font_node)

            # Nodes
            for name in nodes.keys():
                if name not in positions:
                    continue
                x, y = positions[name]
                drw.rectangle([x, y, x + self.node_w, y + self.node_h], fill=(74,144,226), outline=(46,92,138), width=2)
                drw.text((x + 8, y + 12), name[:24], fill=(255,255,255), font=font_node)

            # Edges
            for src, dst in edges:
                if src in positions and dst in positions:
                    x1, y1 = positions[src]
                    x2, y2 = positions[dst]
                    x1 += self.node_w
                    y1 += self.node_h/2
                    y2 += self.node_h/2
                    drw.line([x1, y1, x2, y2], fill=(68,68,68), width=1)

            import io
            bio = io.BytesIO()
            img.save(bio, format='PNG')
            png_bytes = bio.getvalue()
            layout_json = json.dumps({
                'lane_names': lane_names,
                'step_orders': step_orders,
                'positions': positions,
                'nodes': list(nodes.keys()),
                'edges': edges,
                'req_w': W,
                'req_h': H,
            })
            ok = False
            if getattr(self.app, 'db_manager', None) and self.db.connected and self.app.current_project:
                ok = self.db.save_mapping_snapshot(self.app.current_project, png_bytes, W, H, layout_json)
            if ok:
                messagebox.showinfo("Snapshot", "Mapping snapshot saved to project.")
            else:
                messagebox.showwarning("Snapshot", "Failed to save snapshot to DB. Is the database connected and project open?")
        except Exception as e:
            messagebox.showerror("Snapshot", f"Failed to build snapshot: {e}")

class MindMapViewer:
    """Mind Map style presentation of the architecture while preserving List grouping.
    Layout: Center root node (project), ring of List nodes, functions around each List node.
    Also draws best-effort relationship links between functions.
    """
    def __init__(self, app):
        self.app = app
        self.root = app.root
        self.db = app.db_manager if hasattr(app, 'db_manager') else None
        self.win = None
        self.canvas = None
        self.vscroll = None
        self.hscroll = None

        # Node sizing
        self.root_size = (160, 50)
        self.list_size = (150, 44)
        self.func_size = (130, 38)

        # Colors
        self.palette = [
            "#4A90E2", "#7B8D8E", "#27AE60", "#8E44AD",
            "#E67E22", "#2C3E50", "#16A085", "#D35400",
            "#2980B9", "#C0392B", "#9B59B6", "#3A539B",
        ]
        self.bg = "#ffffff"
        self.edge_color = "#888"
        self.rel_color = "#B22222"

    def show(self):
        # Build window
        self.win = tk.Toplevel(self.root)
        title = "Mind Map"
        try:
            if getattr(self.app, 'current_project', None):
                title = f"Mind Map - {self.app.current_project}"
        except Exception:
            pass
        self.win.title(title)
        try:
            self.win.geometry("1100x800")
        except Exception:
            pass

        outer = ttk.Frame(self.win)
        outer.pack(fill=tk.BOTH, expand=True)

        # Toolbar actions (optional export)
        tools = ttk.Frame(outer)
        tools.pack(fill=tk.X, padx=6, pady=(6, 0))
        ttk.Button(tools, text="Render", command=self.render).pack(side=tk.LEFT)

        # Canvas + scrollbars
        canvas_frame = ttk.Frame(outer)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.canvas = tk.Canvas(canvas_frame, bg=self.bg, xscrollcommand=lambda *a: None, yscrollcommand=lambda *a: None)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vscroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.vscroll.grid(row=0, column=1, sticky="ns")
        self.hscroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.hscroll.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=self.vscroll.set, xscrollcommand=self.hscroll.set)

        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

        # First render
        self.render()

    def _color_for_list(self, idx):
        if not self.palette:
            return "#4A90E2"
        return self.palette[idx % len(self.palette)]

    def _collect_functions(self):
        """Return list of {name, list_name, relationships} from memory or DB."""
        items = []
        try:
            pills = getattr(self.app, 'pills', []) or []
            for p in pills:
                items.append({
                    'name': getattr(p, 'name', ''),
                    'list_name': (getattr(p, 'list_name', '') or '').strip() or 'Unassigned',
                    'relationships': getattr(p, 'relationships', '') or ''
                })
        except Exception:
            pass
        if not items and self.db and getattr(self.app, 'current_project', None) and self.db.connected:
            try:
                rows = self.db.load_project(self.app.current_project) or []
                for r in rows:
                    items.append({
                        'name': r.get('name') or '',
                        'list_name': (r.get('list_name') or '').strip() or 'Unassigned',
                        'relationships': r.get('relationships') or ''
                    })
            except Exception:
                pass
        # Deduplicate by name (prefer first occurrence)
        seen = set()
        unique = []
        for it in items:
            nm = (it['name'] or '').strip()
            if not nm or nm.lower() in seen:
                continue
            seen.add(nm.lower())
            unique.append(it)
        return unique

    def _parse_relationships(self, rel_text):
        """Extract related names from free-form relationships field."""
        names = []
        if not rel_text:
            return names
        try:
            for line in (rel_text or '').splitlines():
                if line.strip().lower().startswith('related to:'):
                    rest = line.split(':', 1)[1]
                    for n in rest.split(','):
                        n2 = n.strip()
                        if n2:
                            names.append(n2)
        except Exception:
            pass
        return names

    def render(self):
        data = self._collect_functions()
        if not data:
            messagebox.showinfo("Mind Map", "No functions found. Add functions first.")
            return

        # Build grouping by list
        list_to_funcs = {}
        list_names = []
        for it in data:
            ln = it['list_name'] or 'Unassigned'
            if ln not in list_to_funcs:
                list_to_funcs[ln] = []
                list_names.append(ln)
            list_to_funcs[ln].append(it)

        L = max(1, len(list_names))
        # Radii
        R_lists = 420
        # Determine maximum per-list function radius to size canvas
        max_r2 = 0
        for ln in list_names:
            n = max(1, len(list_to_funcs[ln]))
            r2 = min(260, 90 + n * 14)  # grows with count, capped
            max_r2 = max(max_r2, r2)

        margin = 200
        max_radius = R_lists + max_r2 + 140
        W = H = int(2 * (max_radius + margin))
        cx = W // 2
        cy = H // 2

        c = self.canvas
        c.delete("all")

        # Root node
        prj = getattr(self.app, 'current_project', None) or "Project"
        rx, ry = self.root_size
        root_bbox = (cx - rx//2, cy - ry//2, cx + rx//2, cy + ry//2)
        c.create_rectangle(*root_bbox, fill="#1F3A93", outline="#0B2545", width=2)
        c.create_text(cx, cy, text=prj, fill="white", font=("Arial", 12, "bold"))

        # Compute list node positions on a circle
        list_pos = {}
        for i, ln in enumerate(list_names):
            ang = (2.0 * math.pi * i) / L
            x = cx + int(R_lists * math.cos(ang))
            y = cy + int(R_lists * math.sin(ang))
            list_pos[ln] = (x, y)

        # Draw lists and their functions
        func_pos = {}  # name -> (x, y)
        func_bbox = {} # lowercased name -> bbox
        legend_items = []

        for i, ln in enumerate(list_names):
            lx, ly = list_pos[ln]
            lw, lh = self.list_size
            fill = self._color_for_list(i)
            # Edge from root to list
            c.create_line(cx, cy, lx, ly, fill=self.edge_color, width=2, arrow=tk.LAST)
            # List node
            c.create_rectangle(lx - lw//2, ly - lh//2, lx + lw//2, ly + lh//2, fill=fill, outline="#2E5C8A", width=2)
            c.create_text(lx, ly, text=ln, fill="white", font=("Arial", 10, "bold"))
            legend_items.append((fill, ln))

            # Functions around list on a smaller circle
            funcs = list_to_funcs.get(ln, [])
            n = len(funcs)
            if n == 0:
                continue
            r2 = min(260, 90 + n * 14)
            for k, it in enumerate(funcs):
                fang = (2.0 * math.pi * k) / n
                fx = lx + int(r2 * math.cos(fang))
                fy = ly + int(r2 * math.sin(fang))
                fw, fh = self.func_size
                # Edge from list to function
                c.create_line(lx, ly, fx, fy, fill="#aac", width=1)
                # Function node
                c.create_rectangle(fx - fw//2, fy - fh//2, fx + fw//2, fy + fh//2, fill="#4A90E2", outline="#2E5C8A", width=2)
                label = it['name'] or "(unnamed)"
                disp = label if len(label) <= 26 else (label[:23] + "...")
                c.create_text(fx, fy, text=disp, fill="white", font=("Arial", 10, "bold"))
                func_pos[label] = (fx, fy)
                func_bbox[label.lower().strip()] = (fx - fw//2, fy - fh//2, fx + fw//2, fy + fh//2)

        # Draw relationships between functions (across lists)
        def _shorten_line(b1, b2):
            # Shorten line so it starts/ends at rect borders, not centers
            (x0, y0, x1, y1) = b1
            (u0, v0, u1, v1) = b2
            sx, sy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            tx, ty = (u0 + u1) / 2.0, (v0 + v1) / 2.0
            # Control point for smooth line
            mx, my = (sx + tx) / 2.0, (sy + ty) / 2.0
            return (sx, sy, mx, my, tx, ty)

        # Build quick map for relationships
        name_map = { (n or '').strip().lower(): n for n in func_pos.keys() }
        drawn = set()
        for it in data:
            src = (it['name'] or '').strip()
            if not src:
                continue
            src_key = src.lower()
            if src_key not in name_map:
                continue
            rels = self._parse_relationships(it.get('relationships', ''))
            for tgt in rels:
                tgt_key = (tgt or '').strip().lower()
                if tgt_key not in name_map:
                    continue
                a, b = min(src_key, tgt_key), max(src_key, tgt_key)
                if (a, b) in drawn:
                    continue
                b1 = func_bbox.get(src_key)
                b2 = func_bbox.get(tgt_key)
                if not b1 or not b2:
                    continue
                sx, sy, mx, my, tx, ty = _shorten_line(b1, b2)
                self.canvas.create_line(sx, sy, mx, my, tx, ty, arrow=tk.LAST, fill=self.rel_color, width=2, smooth=True, dash=(6, 4))
                drawn.add((a, b))

        # Legend
        try:
            lx0, ly0 = 20, 20
            c.create_rectangle(lx0, ly0, lx0 + 220, ly0 + 14 + 18 * max(1, len(legend_items)), fill="#f7f7f7", outline="#ccc")
            c.create_text(lx0 + 8, ly0 + 10, text="Lists", anchor=tk.W, font=("Arial", 10, "bold"), fill="#333")
            y = ly0 + 24
            for fill, ln in legend_items[:10]:
                c.create_rectangle(lx0 + 8, y - 8, lx0 + 28, y + 8, fill=fill, outline="#2E5C8A")
                c.create_text(lx0 + 36, y, text=ln, anchor=tk.W, font=("Arial", 9), fill="#333")
                y += 18
        except Exception:
            pass

        # Scroll region
        c.configure(scrollregion=(0, 0, W, H))
        try:
            self.app.status_var.set(f"Mind Map rendered: {len(func_pos)} functions across {L} lists")
        except Exception:
            pass


class HorizontalMindMapViewer:
    """Horizontal Mind Map view with curved links while preserving List grouping.
    Root -> Lists -> Functions arranged left-to-right with nice connectors.
    """
    def __init__(self, app):
        self.app = app
        self.root = getattr(app, 'root', None)
        self._scale = 1.0
        self._canvas = None
        self._win = None

    def _collect_functions(self):
        # Prefer in-memory pills if available
        pills = []
        try:
            pills = getattr(self.app, 'pills', []) or []
        except Exception:
            pills = []
        data = []
        if pills:
            for p in pills:
                try:
                    data.append({
                        'name': getattr(p, 'name', '') or '',
                        'list_name': getattr(p, 'list_name', '') or '',
                    })
                except Exception:
                    pass
        else:
            # Fallback to DB for current project
            try:
                if getattr(self.app, 'db_manager', None) and self.app.db_manager.connected and getattr(self.app, 'current_project', None):
                    rows = self.app.db_manager.load_project(self.app.current_project) or []
                    for r in rows:
                        data.append({
                            'name': r.get('name') or '',
                            'list_name': r.get('list_name') or '',
                        })
            except Exception:
                pass
        return data

    def _layout(self, groups):
        # Compute positions for nodes (root, lists, functions)
        # Columns
        x_root = 150
        x_list = 400
        x_func_start = 700
        func_col_dx = 180
        # Row spacing
        list_dy = 120
        func_dy = 70

        # Determine total height from number of lists
        L = max(1, len(groups))
        height = max(800, 120 + L * list_dy)
        y0 = height // 2

        # Place lists vertically centered
        list_positions = {}  # list_name -> (x,y)
        if L == 1:
            ys = [y0]
        else:
            total_h = (L - 1) * list_dy
            start_y = y0 - total_h // 2
            ys = [start_y + i * list_dy for i in range(L)]
        for (lname, _funcs), y in zip(groups.items(), ys):
            list_positions[lname] = (x_list, y)

        # Place functions to the right of their list, arranged horizontally by columns, wrapping by rows
        func_positions = {}  # func_name -> (x,y)
        func_bbox = {}       # func_name -> bbox
        node_w, node_h = 120, 40
        for lname, funcs in groups.items():
            if not funcs:
                continue
            cy_base = list_positions[lname][1]
            # Arrange in rows of 4 per row
            per_row = 4
            for idx, fname in enumerate(funcs):
                row = idx // per_row
                col = idx % per_row
                x = x_func_start + col * func_col_dx
                y = cy_base + row * func_dy
                func_positions[fname] = (x, y)
                func_bbox[fname] = (x - node_w//2, y - node_h//2, x + node_w//2, y + node_h//2)
        return {
            'canvas_w': max(1200, x_func_start + 3 * func_col_dx + 240),
            'canvas_h': height,
            'root_pos': (x_root, y0),
            'list_pos': list_positions,
            'func_pos': func_positions,
            'func_bbox': func_bbox,
            'node_w': node_w,
            'node_h': node_h,
        }

    def _draw_node(self, c, x, y, w, h, fill, outline, text, text_fill='white', tag=None):
        rect = c.create_rectangle(x - w//2, y - h//2, x + w//2, y + h//2, fill=fill, outline=outline, width=2, tags=tag)
        c.create_text(x, y, text=text, fill=text_fill, font=("Arial", 10, "bold"))
        return rect

    def _curve(self, x0, y0, x1, y1, bend=0.4):
        # Return control points for a smooth horizontal curve
        dx = x1 - x0
        cx = x0 + dx * bend
        cx2 = x1 - dx * bend
        return [x0, y0, cx, y0, cx2, y1, x1, y1]

    def _apply_zoom(self, factor):
        try:
            self._scale *= factor
            self._canvas.scale("all", 0, 0, factor, factor)
            self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        except Exception:
            pass

    def show(self):
        # Build grouped data
        data = self._collect_functions()
        if not data:
            messagebox.showinfo("Mind Map", "No functions found. Add functions first.")
            return
        # Group by list
        groups = {}
        for item in data:
            lname = (item.get('list_name') or '').strip() or 'Ungrouped'
            fname = (item.get('name') or '').strip() or 'Unnamed'
            groups.setdefault(lname, []).append(fname)
        # Sort lists and functions for stable layout
        groups = dict(sorted(((k, sorted(v)) for k, v in groups.items()), key=lambda kv: kv[0].lower()))

        # Layout
        L = self._layout(groups)

        # Create window and canvas with scrollbars and controls
        win = tk.Toplevel(self.root)
        self._win = win
        win.title("Mind Map (Horizontal)")
        win.geometry("1200x800")
        outer = ttk.Frame(win)
        outer.pack(fill=tk.BOTH, expand=True)

        # Controls (Zoom)
        controls = ttk.Frame(outer)
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(4, 2))
        ttk.Label(controls, text="Zoom:").pack(side=tk.LEFT)
        ttk.Button(controls, text="-", width=3, command=lambda: self._apply_zoom(0.9)).pack(side=tk.LEFT, padx=2)
        ttk.Button(controls, text="+", width=3, command=lambda: self._apply_zoom(1.1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(controls, text="Reset", command=lambda: self._apply_zoom(1.0 / max(self._scale, 1e-6))).pack(side=tk.LEFT, padx=6)

        xscroll = ttk.Scrollbar(outer, orient=tk.HORIZONTAL)
        yscroll = ttk.Scrollbar(outer, orient=tk.VERTICAL)
        c = tk.Canvas(outer, bg="#0b1220", scrollregion=(0, 0, L['canvas_w'], L['canvas_h']))
        self._canvas = c
        c.config(xscrollcommand=xscroll.set, yscrollcommand=yscroll.set)
        xscroll.config(command=c.xview)
        yscroll.config(command=c.yview)
        c.grid(row=1, column=0, sticky="nsew")
        yscroll.grid(row=1, column=1, sticky="ns")
        xscroll.grid(row=2, column=0, sticky="ew")
        outer.rowconfigure(1, weight=1)
        outer.columnconfigure(0, weight=1)

        # Bind keyboard zoom
        try:
            win.bind("<Control-=>", lambda e: self._apply_zoom(1.1))
            win.bind("<Control-minus>", lambda e: self._apply_zoom(0.9))
            win.bind("<Command-=>", lambda e: self._apply_zoom(1.1))  # macOS
            win.bind("<Command-minus>", lambda e: self._apply_zoom(0.9))
        except Exception:
            pass

        # Colors
        col_root = "#3b82f6"
        col_list = "#10b981"
        col_func = "#6366f1"
        outline = "#111827"
        arrow_shape = (10, 12, 4)
        gap = 8  # keep lines away from node rectangles

        # Sizes and positions
        proj = getattr(self.app, 'current_project', None) or "Project"
        rx, ry = L['root_pos']
        root_w, root_h = 150, 50
        list_w, list_h = 140, 46
        func_w, func_h = L['node_w'], L['node_h']

        # Build connector polylines first (so we can draw them beneath nodes)
        def orth(sx, sy, ex, ey):
            midx = (sx + ex) / 2.0
            return [sx, sy, midx, sy, midx, ey, ex, ey]

        root_list_lines = []
        for lname, (lx, ly) in L['list_pos'].items():
            start_x = rx + root_w//2 + gap
            end_x = lx - list_w//2 - gap
            root_list_lines.append(orth(start_x, ry, end_x, ly))

        # Map which list owns each function
        owner = {}
        for lname, funcs in groups.items():
            for fn in funcs:
                owner[fn] = lname

        list_func_lines = []
        for fname, (fx, fy) in L['func_pos'].items():
            lname = owner.get(fname)
            if lname in L['list_pos']:
                lx, ly = L['list_pos'][lname]
                start_x = lx + list_w//2 + gap
                end_x = fx - func_w//2 - gap
                list_func_lines.append(orth(start_x, ly, end_x, fy))

        # Draw connectors first (under nodes)
        for pts in root_list_lines:
            c.create_line(*pts, fill="#93c5fd", width=2, smooth=False, arrow=tk.LAST, arrowshape=arrow_shape)
        for pts in list_func_lines:
            c.create_line(*pts, fill="#c7d2fe", width=2, smooth=False, arrow=tk.LAST, arrowshape=arrow_shape)

        # Draw nodes on top of lines for readability
        self._draw_node(c, rx, ry, root_w, root_h, col_root, outline, proj)
        for lname, (lx, ly) in L['list_pos'].items():
            self._draw_node(c, lx, ly, list_w, list_h, col_list, outline, lname)
        for fname, (fx, fy) in L['func_pos'].items():
            self._draw_node(c, fx, fy, func_w, func_h, col_func, outline, fname)
        # Ensure nodes are raised above any lines
        try:
            c.tag_raise("all")
        except Exception:
            pass

        # Basic pan with mouse drag
        state = {'drag': None}
        def _start_drag(e):
            state['drag'] = (e.x, e.y)
        def _drag(e):
            if state['drag'] is None:
                return
            dx = state['drag'][0] - e.x
            dy = state['drag'][1] - e.y
            c.xview_scroll(int(dx/2), 'units')
            c.yview_scroll(int(dy/2), 'units')
            state['drag'] = (e.x, e.y)
        def _end_drag(e):
            state['drag'] = None
        c.bind('<ButtonPress-2>', _start_drag)
        c.bind('<B2-Motion>', _drag)
        c.bind('<ButtonRelease-2>', _end_drag)
        # Mac touchpad/one-button fallback (hold Shift + drag)
        def _start_drag_alt(e):
            if e.state & 0x0001:  # Shift as a simple modifier fallback
                state['drag'] = (e.x, e.y)
        c.bind('<ButtonPress-1>', _start_drag_alt, add="+")
        c.bind('<B1-Motion>', _drag, add="+")
        c.bind('<ButtonRelease-1>', _end_drag, add="+")

        try:
            if getattr(self.app, 'status_var', None):
                self.app.status_var.set(f"Mind Map rendered (horizontal): {sum(len(v) for v in groups.values())} functions across {len(groups)} lists")
        except Exception:
            pass

class ArchitectureMapper:
    """Main application class"""

    def _refresh_pill_from_db(self, pill):
        """Silently refresh a pill's model from DB without opening any UI windows."""
        try:
            if not getattr(self, 'db_manager', None) or not self.db_manager.connected or not getattr(self, 'current_project', None):
                return
            schema = self.db_manager.schema_name_for_project(self.current_project)
            cur = self.db_manager.connection.cursor()
            if getattr(pill, 'function_id', None):
                cur.execute(
                    sql.SQL(
                        """
                        SELECT name, description, visual_output, relationships,
                               x_position, y_position, list_id, list_order, list_name,
                               inputs, outputs
                        FROM {}.functions WHERE id = %s
                        """
                    ).format(sql.Identifier(schema)),
                    (pill.function_id,)
                )
            else:
                cur.execute(
                    sql.SQL(
                        """
                        SELECT name, description, visual_output, relationships,
                               x_position, y_position, list_id, list_order, list_name,
                               inputs, outputs
                        FROM {}.functions WHERE name = %s
                        """
                    ).format(sql.Identifier(schema)),
                    (pill.name,)
                )
            row = cur.fetchone()
            if not row:
                return
            name, desc, visual_output, relationships, x, y, lid, lorder, list_name_db, inputs_json, outputs_json = row

            pill.name = name or pill.name
            try:
                pill.update_name(pill.name)
            except Exception:
                pass
            pill.description = desc or ""
            pill.visual_output = visual_output or ""
            pill.relationships = relationships or ""
            pill.list_id = lid
            pill.list_order = lorder
            try:
                # Prefer stored textual name; may resolve from function_lists below if missing
                pill.list_name = (list_name_db or pill.list_name) or ""
            except Exception:
                pass
            try:
                inputs_list = json.loads(inputs_json) if inputs_json else []
            except Exception:
                inputs_list = [s.strip() for s in (inputs_json or "").splitlines() if s.strip()]
            try:
                outputs_list = json.loads(outputs_json) if outputs_json else []
            except Exception:
                outputs_list = [s.strip() for s in (outputs_json or "").splitlines() if s.strip()]
            pill.inputs = inputs_list
            pill.outputs = outputs_list

            # Resolve list name from function_lists if still missing
            if lid and not (pill.list_name or "").strip():
                try:
                    cur.execute(
                        sql.SQL("SELECT name FROM {}.function_lists WHERE id = %s").format(sql.Identifier(schema)),
                        (lid,)
                    )
                    r = cur.fetchone()
                    if r and r[0]:
                        pill.list_name = r[0]
                except Exception:
                    try:
                        self.db_manager.connection.rollback()
                    except Exception:
                        pass
        except Exception:
            try:
                self.db_manager.connection.rollback()
            except Exception:
                pass
            # Silent best-effort refresh

    def _warp_refresh_all_functions(self):
        """Run a silent, ultra-fast refresh across all pills right after a project is opened."""
        try:
            if not getattr(self, 'pills', None):
                return
            # Defer slightly to let UI settle
            def _do():
                refreshed = 0
                for pill in list(self.pills):
                    try:
                        self._refresh_pill_from_db(pill)
                        refreshed += 1
                    except Exception:
                        pass
                try:
                    self.status_var.set(f"Auto-refreshed {refreshed} functions at warp speed")
                except Exception:
                    pass
            try:
                self.root.after(10, _do)
            except Exception:
                _do()
        except Exception:
            pass
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
        ttk.Button(toolbar, text="Add List", command=self.manage_lists).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Clear All", command=self.clear_all).pack(side=tk.LEFT, padx=5)
        # Flow Output removed
        ttk.Button(toolbar, text="Compile", command=self.compile_architecture).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Logical Mapping", command=lambda: LogicalMappingViewer(self).show()).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Mind Map", command=lambda: HorizontalMindMapViewer(self).show()).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Analysis", command=lambda: open_analysis(self)).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Objective", command=self.edit_objective).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Guide", command=lambda: open_guide(self)).pack(side=tk.LEFT, padx=5)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        # Hook: when a project is opened/loaded, auto-refresh all functions silently
        try:
            def _on_status_change(*_):
                try:
                    val = self.status_var.get()
                    if isinstance(val, str) and (
                        "Loaded project" in val or "Opened project" in val or "Connected to project" in val
                    ):
                        try:
                            self._warp_refresh_all_functions()
                        except Exception:
                            pass
                except Exception:
                    pass
            # Trace status changes
            try:
                self.status_var.trace_add("write", lambda *args: _on_status_change())
            except Exception:
                # Older Tk versions
                self.status_var.trace("w", lambda *args: _on_status_change())
        except Exception:
            pass
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
            # Load objective for the now-current project if available
            try:
                self._load_project_objective()
            except Exception:
                pass

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
        """Add a new function pill with list assignment and hierarchy order."""
        # Open dialog to create function with optional list and order
        if self.db_manager.connected and self.current_project:
            try:
                self.db_manager.ensure_project_schema(self.current_project)
            except Exception:
                try:
                    self.db_manager.connection.rollback()
                except Exception:
                    pass
        dlg = NewFunctionDialog(self)
        self.root.wait_window(dlg.window)
        if getattr(dlg, 'result', None):
            name = dlg.result.get('name')
            list_id = dlg.result.get('list_id')
            list_order = dlg.result.get('list_order')
            x = self.canvas.winfo_width() // 2 - 60
            y = self.canvas.winfo_height() // 2 - 20
            pill = FunctionPill(self.canvas, x, y, name, None, list_id, list_order)
            try:
                pill.list_name = dlg.result.get('list_name')
            except Exception:
                pass
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

    def manage_lists(self):
        """Open the list manager dialog to add/rename/delete list names stored in the DB for the current project."""
        # Ensure DB connection
        if not self.db_manager.connected:
            self.connect_database()
            if not self.db_manager.connected:
                return
        # Ensure a project is selected
        if not self.current_project:
            messagebox.showwarning("No Project", "Please create or open a project first to manage lists.")
            return
        # Ensure per-project schema exists
        try:
            self.db_manager.ensure_project_schema(self.current_project)
        except Exception:
            try:
                self.db_manager.connection.rollback()
            except Exception:
                pass
            messagebox.showerror("Database", "Unable to ensure project schema for list management.")
            return
        # Open dialog
        ListManagerDialog(self)
            
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
                    func_data.get("function_id"),
                    func_data.get("list_id"),
                    func_data.get("list_order"),
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
                        func_data["function_id"],
                        func_data.get("list_id"),
                        func_data.get("list_order"),
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
            
        # Build and display token-safe prompt segments for the current project
        root = self.root
        project_name = getattr(self, 'current_project', None) or ''

        # Helper: token estimate (rough heuristic: 4 chars per token)
        def _estimate_tokens(txt):
            try:
                return max(1, int(len(txt) / 4))
            except Exception:
                return len(txt)

        # Helper: parse relationships field into list of names
        def _parse_related_names(rel_text):
            if not rel_text:
                return []
            names = []
            try:
                for line in (rel_text or '').splitlines():
                    if line.strip().lower().startswith('related to:'):
                        rest = line.split(':', 1)[1]
                        names = [n.strip() for n in rest.split(',') if n.strip()]
                        break
            except Exception:
                pass
            return names

        # Gather objective
        objective = None
        try:
            if getattr(self, 'db_manager', None) and self.db_manager.connected and project_name:
                # Prefer DB objective
                if hasattr(self.db_manager, 'get_project_objective'):
                    try:
                        objective = self.db_manager.get_project_objective(project_name)
                    except Exception:
                        try:
                            self.db_manager.connection.rollback()
                        except Exception:
                            pass
                if not objective:
                    # Fallback: read directly from per-project schema
                    try:
                        schema = self.db_manager.schema_name_for_project(project_name)
                        cur = self.db_manager.connection.cursor()
                        cur.execute(sql.SQL("SELECT objective FROM {}.project_info WHERE id = 1").format(sql.Identifier(schema)))
                        row = cur.fetchone()
                        if row and row[0]:
                            objective = row[0]
                    except Exception:
                        try:
                            self.db_manager.connection.rollback()
                        except Exception:
                            pass
        except Exception:
            pass
        if not objective:
            objective = '(Objective not set)'

        # Organize functions by list and build relationship edges
        pills = list(getattr(self, 'pills', []) or [])
        # Ensure stable ordering: by list_name, then list_order, then name
        def _pill_sort_key(p):
            try:
                return ((p.list_name or '').lower(), int(p.list_order) if p.list_order is not None else 0, (p.name or '').lower())
            except Exception:
                return ((getattr(p, 'list_name', '') or '').lower(), 0, (getattr(p, 'name', '') or '').lower())
        pills.sort(key=_pill_sort_key)

        lists_map = {}
        name_to_pill = {}
        for p in pills:
            lname = (getattr(p, 'list_name', '') or 'Unlisted').strip() or 'Unlisted'
            lists_map.setdefault(lname, []).append(p)
            if getattr(p, 'name', None):
                name_to_pill[p.name.strip()] = p

        # Build edges (A -> B) from relationships fields
        edges = []
        for p in pills:
            for rn in _parse_related_names(getattr(p, 'relationships', '') or ''):
                if rn:
                    edges.append((p.name, rn))

        # Segment builder
        MAX_CHARS = 1800  # keep each segment small enough for typical model limits
        segments = []  # list of (title, content)

        # Segment 1: Objective and overview
        overview_lines = []
        overview_lines.append(f"Project: {project_name or '(unnamed)'}")
        overview_lines.append("Objective:")
        overview_lines.append(objective.strip())
        overview_lines.append("")
        overview_lines.append("Lists and counts:")
        for lname in sorted(lists_map.keys(), key=lambda s: s.lower()):
            overview_lines.append(f"- {lname}: {len(lists_map[lname])} functions")
        overview = "\n".join(overview_lines)
        segments.append(("1) Objective & Overview", overview))

        # Per-list segments (split if necessary)
        seg_counter = 2
        for lname in sorted(lists_map.keys(), key=lambda s: s.lower()):
            fns = lists_map[lname]
            # Build text for all functions in this list
            block_lines = [f"List: {lname}", ""]
            for p in fns:
                block_lines.append(f"Function: {p.name}")
                if getattr(p, 'description', None):
                    block_lines.append(f"  Description: {p.description}")
                ins = ", ".join(getattr(p, 'inputs', []) or [])
                outs = ", ".join(getattr(p, 'outputs', []) or [])
                if ins:
                    block_lines.append(f"  Inputs: {ins}")
                if outs:
                    block_lines.append(f"  Outputs: {outs}")
                rels = _parse_related_names(getattr(p, 'relationships', '') or '')
                if rels:
                    block_lines.append(f"  Related: {', '.join(rels)}")
                try:
                    if getattr(p, 'list_order', None) is not None:
                        block_lines.append(f"  Order: {p.list_order}")
                except Exception:
                    pass
                block_lines.append("")
            full_text = "\n".join(block_lines).strip()
            # Split into chunks
            if len(full_text) <= MAX_CHARS:
                segments.append((f"{seg_counter}) List: {lname}", full_text))
                seg_counter += 1
            else:
                # Chunk by function
                chunk = []
                chunk_len = 0
                part_idx = 1
                for p in fns:
                    lines = [f"Function: {p.name}"]
                    if getattr(p, 'description', None):
                        lines.append(f"  Description: {p.description}")
                    ins = ", ".join(getattr(p, 'inputs', []) or [])
                    outs = ", ".join(getattr(p, 'outputs', []) or [])
                    if ins:
                        lines.append(f"  Inputs: {ins}")
                    if outs:
                        lines.append(f"  Outputs: {outs}")
                    rels = _parse_related_names(getattr(p, 'relationships', '') or '')
                    if rels:
                        lines.append(f"  Related: {', '.join(rels)}")
                    try:
                        if getattr(p, 'list_order', None) is not None:
                            lines.append(f"  Order: {p.list_order}")
                    except Exception:
                        pass
                    lines.append("")
                    block = "\n".join(lines)
                    if chunk_len + len(block) > MAX_CHARS and chunk:
                        segments.append((f"{seg_counter}) List: {lname} (part {part_idx})", "\n".join(chunk).strip()))
                        seg_counter += 1
                        part_idx += 1
                        chunk = []
                        chunk_len = 0
                    chunk.append(block)
                    chunk_len += len(block)
                if chunk:
                    segments.append((f"{seg_counter}) List: {lname} (part {part_idx})", "\n".join(chunk).strip()))
                    seg_counter += 1

        # Cross-relations segment(s)
        if edges:
            lines = ["Cross-Relations (A -> B):", ""]
            for a, b in edges:
                lines.append(f"- {a} -> {b}")
            rel_text = "\n".join(lines)
            if len(rel_text) <= MAX_CHARS:
                segments.append((f"{seg_counter}) Cross-Relations", rel_text))
                seg_counter += 1
            else:
                # Chunk relations
                chunk = []
                chunk_len = 0
                part_idx = 1
                for a, b in edges:
                    line = f"- {a} -> {b}\n"
                    if chunk_len + len(line) > MAX_CHARS and chunk:
                        segments.append((f"{seg_counter}) Cross-Relations (part {part_idx})", "".join(chunk).strip()))
                        seg_counter += 1
                        part_idx += 1
                        chunk = []
                        chunk_len = 0
                    chunk.append(line)
                    chunk_len += len(line)
                if chunk:
                    segments.append((f"{seg_counter}) Cross-Relations (part {part_idx})", "".join(chunk).strip()))
                    seg_counter += 1

        # Open UI to display segments
        win = tk.Toplevel(root)
        win.title("Compiled Prompts")
        try:
            win.geometry("1000x650")
        except Exception:
            pass
        container = ttk.Frame(win)
        container.pack(fill=tk.BOTH, expand=True)

        # Left: segments list
        left = ttk.Frame(container)
        left.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Label(left, text="Segments").pack(anchor=tk.W, padx=6, pady=(6, 3))
        seg_list = tk.Listbox(left, width=36)
        seg_list.pack(fill=tk.Y, padx=6, pady=6)

        # Right: viewer
        right = ttk.Frame(container)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(right, text="Content").pack(anchor=tk.W, padx=6, pady=(6, 3))
        text = tk.Text(right, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # Bottom: controls
        bottom = ttk.Frame(win)
        bottom.pack(fill=tk.X)
        token_var = tk.StringVar(value="")
        ttk.Label(bottom, textvariable=token_var).pack(side=tk.LEFT, padx=8)
        def copy_segment():
            try:
                idx = seg_list.curselection()
                if not idx:
                    return
                title, content = segments[idx[0]]
                win.clipboard_clear()
                win.clipboard_append(content)
                token_var.set(f"Copied segment • ~{_estimate_tokens(content)} tokens")
            except Exception:
                pass
        def copy_all():
            try:
                all_txt = "\n\n".join([f"{t}\n\n{c}" for t, c in segments])
                win.clipboard_clear()
                win.clipboard_append(all_txt)
                token_var.set(f"Copied all • ~{_estimate_tokens(all_txt)} tokens")
            except Exception:
                pass
        def save_txt():
            try:
                from tkinter import filedialog
                fp = filedialog.asksaveasfilename(parent=win, defaultextension=".txt", filetypes=[["Text","*.txt"]], title="Save prompts to file")
                if not fp:
                    return
                with open(fp, 'w', encoding='utf-8') as f:
                    for i, (t, c) in enumerate(segments, 1):
                        f.write(f"{t}\n\n{c}\n\n")
                token_var.set(f"Saved to {os.path.basename(fp)}")
            except Exception as e:
                messagebox.showerror("Save Error", str(e))
        ttk.Button(bottom, text="Copy Segment", command=copy_segment).pack(side=tk.RIGHT, padx=6, pady=6)
        ttk.Button(bottom, text="Copy All", command=copy_all).pack(side=tk.RIGHT, padx=6, pady=6)
        ttk.Button(bottom, text="Save .txt", command=save_txt).pack(side=tk.RIGHT, padx=6, pady=6)

        # Populate list and selection behavior
        for title, _ in segments:
            seg_list.insert(tk.END, title)
        def on_select(evt=None):
            try:
                idx = seg_list.curselection()
                if not idx:
                    return
                title, content = segments[idx[0]]
                text.delete('1.0', tk.END)
                text.insert('1.0', content)
                token_var.set(f"~{_estimate_tokens(content)} tokens")
            except Exception:
                pass
        seg_list.bind('<<ListboxSelect>>', on_select)
        if segments:
            try:
                seg_list.selection_set(0)
                on_select()
            except Exception:
                pass
    
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
        """Open a popup to visualize logical relationships between functions grouped by their List.
        Each list is rendered as a labeled rectangle containing its functions. Arrows are drawn to
        indicate relationships described in each function's 'relationships' text (best-effort parse).
        """
        if not self.pills:
            messagebox.showinfo("No Functions", "No functions to display. Please add some functions first.")
            return

        # Build groups by list name, using the text value from each function's List field.
        groups = {}
        list_name_by_id = {}
        # Resolve list names via DB if available; otherwise leave empty
        try:
            if self.db_manager.connected and self.current_project:
                schema = self.db_manager.schema_name_for_project(self.current_project)
                cur = self.db_manager.connection.cursor()
                cur.execute(sql.SQL("SELECT id, name FROM {}.function_lists").format(sql.Identifier(schema)))
                for rid, rname in cur.fetchall():
                    list_name_by_id[rid] = rname
        except Exception:
            try:
                self.db_manager.connection.rollback()
            except Exception:
                pass

        # Enrich list names from pills as fallback (when DB not connected)
        for pill in self.pills:
            if getattr(pill, 'list_id', None) and getattr(pill, 'list_name', None):
                if pill.list_id not in list_name_by_id and pill.list_name:
                    list_name_by_id[pill.list_id] = pill.list_name
        for pill in self.pills:
            # Prefer the pill's textual list name; fallback to resolving from list_id
            display_list = getattr(pill, 'list_name', None)
            if (not display_list) and getattr(pill, 'list_id', None) and (pill.list_id in list_name_by_id):
                display_list = list_name_by_id.get(pill.list_id)
            display_list = (display_list or "").strip()
            key = display_list  # group by list name text
            if key not in groups:
                groups[key] = []
            groups[key].append(pill)

        # Prepare window
        project_name = self.current_project or "Untitled"
        win = tk.Toplevel(self.root)
        win.title(f"Logical Mapping - {project_name}")
        win.geometry("1000x750")

        canvas_frame = ttk.Frame(win)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        hscroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        hscroll.pack(side=tk.BOTTOM, fill=tk.X)
        vscroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)

        canvas = tk.Canvas(canvas_frame, bg="white", xscrollcommand=hscroll.set, yscrollcommand=vscroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        hscroll.config(command=canvas.xview)
        vscroll.config(command=canvas.yview)

        # Layout parameters
        margin_x = 40
        margin_y = 40
        group_w = 420
        group_h_min = 220
        group_gap_x = 40
        group_gap_y = 40
        pill_w = 160
        pill_h = 52
        pill_gap = 12

        # Arrange groups in a grid
        group_items = []  # store (bbox, list_id)
        col = 0
        row = 0
        max_row_height = 0
        canvas_width = 0
        canvas_height = 0

        sorted_group_ids = sorted(groups.keys(), key=lambda name: (name.strip() == "", name.lower()))
        name_to_pos = {}
        group_of = {}
        for gid in sorted_group_ids:
            pills = groups[gid]
            name = gid or ""

            # Compute group height based on number of pills (2 columns layout inside group)
            cols = 2
            rows_needed = (len(pills) + cols - 1) // cols
            inner_h = rows_needed * pill_h + (rows_needed - 1) * pill_gap + 40  # extra for title
            group_h = max(group_h_min, inner_h)

            x0 = margin_x + col * (group_w + group_gap_x)
            y0 = margin_y + row * (group_h + group_gap_y)
            x1 = x0 + group_w
            y1 = y0 + group_h

            # Draw group rectangle and title
            rect = canvas.create_rectangle(x0, y0, x1, y1, outline="#888", width=2, fill="#f9f9ff")
            canvas.create_text(x0 + 10, y0 + 14, anchor=tk.W, text=f"List: {name}", font=("Arial", 11, "bold"), fill="#333")

            # Draw pills in the group
            start_y = y0 + 36
            for idx, p in enumerate(pills):
                pc = idx % cols
                pr = idx // cols
                px = x0 + 16 + pc * (pill_w + 24)
                py = start_y + pr * (pill_h + pill_gap)
                r = canvas.create_rectangle(px, py, px + pill_w, py + pill_h, fill="#4A90E2", outline="#2E5C8A", width=2)
                # Record pill center for relationship drawing
                name_to_pos[p.name] = (px + pill_w/2, py + pill_h/2)
                group_of[p.name] = name
                # Show function name and its list name (if available) inside the pill
                display_list = getattr(p, 'list_name', None)
                # Fallback: if in-memory pill lacks list_name, resolve from list_id via list_name_by_id
                if (not display_list) and getattr(p, 'list_id', None) and (getattr(p, 'list_id', None) in list_name_by_id):
                    try:
                        display_list = list_name_by_id.get(p.list_id)
                    except Exception:
                        display_list = None
                # Draw function name (first line) and list (second line) for clarity
                canvas.create_text(px + 8, py + 6, text=p.name, fill="white", font=("Arial", 10, "bold"), anchor=tk.NW)
                list_text = display_list or ""
                if list_text:
                    canvas.create_text(px + 8, py + 26, text=f"[{list_text}]", fill="white", font=("Arial", 8, "italic"), anchor=tk.NW)

            group_items.append(((x0, y0, x1, y1), gid))

            # Update layout position
            max_row_height = max(max_row_height, group_h)
            col += 1
            canvas_width = max(canvas_width, x1 + margin_x)
            canvas_height = max(canvas_height, y1 + margin_y)
            if col >= 2:
                col = 0
                row += 1
                max_row_height = 0

        # Optionally draw arrows representing relationships (best-effort parse of 'Related to:')
        # Map function names to pill center positions and list ids for arrow routing
        name_to_pos = {}
        # collect pill centers
        for bbox, gid in group_items:
            # iterate again through pills to record approx centers
            pass  # simplified; can be implemented if needed

        # Build and draw relationship arrows based on 'Related to:' entries
        try:
            pills = self.pills
        except Exception:
            pills = []
        # Canonical name map (lowercase -> original)
        canonical = { (n or "").strip().lower(): n for n in name_to_pos.keys() }
        edges = set()
        for p in pills:
            try:
                rel_text = (p.relationships or "")
            except Exception:
                rel_text = ""
            for line in rel_text.splitlines():
                if line.strip().lower().startswith("related to:"):
                    rest = line.split(":", 1)[1]
                    targets = [t.strip() for t in rest.split(",") if t.strip()]
                    for t in targets:
                        key = t.strip().lower()
                        if key in canonical:
                            dst_name = canonical[key]
                            if dst_name and dst_name != p.name:
                                edges.add((p.name, dst_name))
        def _shorten(ax, ay, bx, by, shrink=22):
            dx = bx - ax
            dy = by - ay
            d = math.hypot(dx, dy) or 1.0
            ux, uy = dx / d, dy / d
            return ax + ux * shrink, ay + uy * shrink, bx - ux * shrink, by - uy * shrink
        for src, dst in edges:
            if src in name_to_pos and dst in name_to_pos:
                x0, y0 = name_to_pos[src]
                x1, y1 = name_to_pos[dst]
                sx, sy, ex, ey = _shorten(x0, y0, x1, y1, shrink=22)
                same_group = (group_of.get(src, "") == group_of.get(dst, "") and group_of.get(src, "") != "")
                color = "#2ECC71" if same_group else "#E67E22"
                kwargs = dict(fill=color, width=2, arrow=tk.LAST, arrowshape=(12, 15, 5), tags=("connection",))
                if not same_group:
                    kwargs["dash"] = (6, 3)
                canvas.create_line(sx, sy, ex, ey, **kwargs)

        canvas.config(scrollregion=(0, 0, max(canvas_width, 1000), max(canvas_height, 750)))
        # Stop here so no duplicate/legacy drawing overwrites the grouped list view
        return
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
        # Ensure any previous Logical Mapping windows are closed to avoid duplicates
        for w in self.root.winfo_children():
            try:
                if isinstance(w, tk.Toplevel) and w.wm_title().startswith("Logical Mapping - "):
                    w.destroy()
            except Exception:
                pass
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

    def show_logical_mapping(self):
        """Open a popup to visualize logical relationships between functions grouped by their List.
        Each List is rendered as a vertical swimlane (column). Functions are placed within their
        List by their Order (top = 1, increasing downward). Arrows represent "Related to" links
        captured in each function's Relationships field.
        """
        # Gather data from in-memory pills
        pills = list(getattr(self, 'pills', []) or [])
        if not pills:
            messagebox.showinfo("Logical Mapping", "No functions found. Add functions first.")
            return

        # Resolve list names; if missing, try to resolve from DB by list_id
        def _resolve_list_name(p):
            name = (getattr(p, 'list_name', None) or '').strip()
            if name:
                return name
            lid = getattr(p, 'list_id', None)
            if lid and getattr(self, 'db_manager', None) and self.db_manager.connected and self.current_project:
                try:
                    schema = self.db_manager.schema_name_for_project(self.current_project)
                    cur = self.db_manager.connection.cursor()
                    cur.execute(sql.SQL("SELECT name FROM {}.function_lists WHERE id = %s").format(sql.Identifier(schema)), (lid,))
                    row = cur.fetchone()
                    if row and row[0]:
                        return str(row[0])
                except Exception:
                    try:
                        self.db_manager.connection.rollback()
                    except Exception:
                        pass
            return "(Unassigned)"

        # Normalize and collect
        data = []
        for p in pills:
            list_name = _resolve_list_name(p)
            try:
                order_val = int(getattr(p, 'list_order', None)) if getattr(p, 'list_order', None) is not None else None
            except Exception:
                order_val = None
            relationships_text = getattr(p, 'relationships', '') or ''
            data.append({
                'name': getattr(p, 'name', 'Unnamed') or 'Unnamed',
                'list': list_name,
                'order': order_val,
                'relationships': relationships_text,
                'pill': p,
            })

        if not data:
            messagebox.showinfo("Logical Mapping", "No functions found to map.")
            return

        # Build swimlanes by list name (sorted)
        lists = sorted({d['list'] for d in data}, key=lambda s: (s == "(Unassigned)", s.lower()))

        # Build set of distinct order values to drive vertical steps (1..N). Treat None as last.
        distinct_orders = sorted({d['order'] for d in data if d['order'] is not None})
        if not distinct_orders:
            # If no orders at all, just use a single row
            distinct_orders = [1]
        # Assign fallback order for None as last step + index bucket later
        last_order = (distinct_orders[-1] if distinct_orders else 0) + 1

        # Group functions per lane and per order for layout
        lane_buckets = {ln: {} for ln in lists}
        for d in data:
            ln = d['list']
            ov = d['order'] if d['order'] is not None else last_order
            lane_buckets.setdefault(ln, {})
            lane_buckets[ln].setdefault(ov, [])
            lane_buckets[ln][ov].append(d)
        # Determine full ordered list of steps to render
        steps = sorted({ov for ln in lane_buckets for ov in lane_buckets[ln].keys()})

        # UI: popup window with scrollable canvas
        win = tk.Toplevel(self.root)
        win.title("Logical Mapping")
        try:
            win.geometry("980x640")
        except Exception:
            pass

        outer = ttk.Frame(win)
        outer.pack(fill=tk.BOTH, expand=True)

        xscroll = ttk.Scrollbar(outer, orient=tk.HORIZONTAL)
        yscroll = ttk.Scrollbar(outer, orient=tk.VERTICAL)
        canvas = tk.Canvas(outer, bg="#fafafa", xscrollcommand=xscroll.set, yscrollcommand=yscroll.set, highlightthickness=0)
        xscroll.config(command=canvas.xview)
        yscroll.config(command=canvas.yview)

        canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        # Layout metrics
        lane_width = 240
        lane_gap = 30
        top_margin = 80
        left_margin = 40
        step_height = 120
        node_w = 160
        node_h = 44
        node_gap_x = 16  # when multiple in same lane/step

        total_width = left_margin + len(lists) * lane_width + (len(lists) - 1) * lane_gap + 80
        total_height = top_margin + len(steps) * step_height + 120
        canvas.config(scrollregion=(0, 0, total_width, total_height))

        # Draw lane headers and boundaries
        lane_x = {}
        header_font = ("Arial", 11, "bold")
        lane_fill = "#eef3fb"
        lane_outline = "#c3d3ee"
        for idx, ln in enumerate(lists):
            x0 = left_margin + idx * (lane_width + lane_gap)
            x1 = x0 + lane_width
            lane_x[ln] = (x0, x1)
            # Lane rectangle
            canvas.create_rectangle(x0, 40, x1, total_height - 40, fill=lane_fill, outline=lane_outline)
            # Lane label
            canvas.create_text((x0 + x1)//2, 20, text=ln, font=header_font, fill="#2e5c8a")

        # Helper: draw a node
        node_items = {}  # name -> (rect_id, text_id, bbox)
        def _draw_node(ln, step_idx, index_in_bucket, label, fill="#4A90E2"):
            x0, x1 = lane_x[ln]
            cx = (x0 + x1) // 2
            # offset left/right for multiple items at same step
            offset = (index_in_bucket - 0) * node_gap_x
            # Alternate left/right positioning
            dir_sign = -1 if (index_in_bucket % 2 == 1) else 1
            cx += dir_sign * offset
            y = top_margin + step_idx * step_height
            rect_id = canvas.create_rectangle(cx - node_w//2, y - node_h//2, cx + node_w//2, y + node_h//2,
                                              fill=fill, outline="#2E5C8A", width=2)
            # Wrap long labels
            disp = label if len(label) <= 22 else (label[:19] + "...")
            text_id = canvas.create_text(cx, y, text=disp, fill="white", font=("Arial", 10, "bold"))
            bbox = canvas.bbox(rect_id)
            node_items[label.lower().strip()] = (rect_id, text_id, bbox)
            return rect_id, text_id, bbox

        # Color palette per lane
        palette = ["#4A90E2", "#7B8D8E", "#8E44AD", "#27AE60", "#D35400", "#C0392B", "#16A085", "#2C3E50"]
        lane_color = {ln: palette[i % len(palette)] for i, ln in enumerate(lists)}

        # Place nodes
        for ln in lists:
            buckets = lane_buckets.get(ln, {})
            for s_idx, step in enumerate(steps):
                items = buckets.get(step, [])
                for j, d in enumerate(sorted(items, key=lambda r: (r['order'] is None, (r['name'] or '').lower()))):
                    _draw_node(ln, s_idx, j, d['name'], fill=lane_color[ln])

        # Build name -> bbox mapping for edges (case-insensitive)
        name_to_bbox = {k: v[2] for k, v in node_items.items()}

        # Helper: center of bbox
        def _center_of(b):
            x0, y0, x1, y1 = b
            return (x0 + x1) / 2.0, (y0 + y1) / 2.0

        # Parse relationships: supports lines like "Related to: A, B" (case-insensitive)
        def _parse_related_names(text):
            if not text:
                return []
            names = []
            for line in (text or "").splitlines():
                l = line.strip()
                if l.lower().startswith("related to:"):
                    rest = l.split(":", 1)[1]
                    parts = [p.strip() for p in rest.split(",") if p.strip()]
                    names.extend(parts)
            return names

        # Draw arrows for edges
        drawn = set()
        edge_color = "#555"
        for d in data:
            src_key = (d['name'] or '').strip().lower()
            src_bbox = name_to_bbox.get(src_key)
            if not src_bbox:
                continue
            sx, sy = _center_of(src_bbox)
            for tgt_name in _parse_related_names(d.get('relationships', '')):
                tgt_key = (tgt_name or '').strip().lower()
                if not tgt_key or tgt_key == src_key:
                    continue
                if (src_key, tgt_key) in drawn:
                    continue
                tgt_bbox = name_to_bbox.get(tgt_key)
                if not tgt_bbox:
                    continue
                tx, ty = _center_of(tgt_bbox)
                # Route: simple polyline with small vertical offset to reduce overlaps
                mid_x = (sx + tx) / 2.0
                canvas.create_line(sx, sy, mid_x, sy, mid_x, ty, tx, ty, arrow=tk.LAST, fill=edge_color, width=2, smooth=True)
                drawn.add((src_key, tgt_key))

        # Legend
        legend = ttk.Frame(win)
        legend.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(legend, text="Legend:").pack(side=tk.LEFT, padx=(8, 2))
        ttk.Label(legend, text="Swimlane = List, Vertical = Order, Arrows = Relationships ('Related to')").pack(side=tk.LEFT)

        # Ensure scrollregion updates if window resized
        def _on_configure(event):
            canvas.config(scrollregion=(0, 0, total_width, total_height))
        canvas.bind("<Configure>", _on_configure)


    def extract_function_graph(self, include_db=True):
        """Build a normalized graph of functions (nodes) and relationships (edges).
        include_db: if True, also attempt to resolve list names from DB using list_id.
        Returns: (nodes, edges, lanes)
          - nodes: dict[name_norm] = {
                'name': str,
                'list_id': int|None,
                'list_name': str,
                'list_order': int|None,
                'relationships_raw': str,
                'relationships': list[str],
            }
          - edges: list[(src_norm, dst_norm)]
          - lanes: {'order': [int], 'lanes': [str], 'buckets': {list_name: {order: [name_norm]}}}
        """
        pills = list(getattr(self, 'pills', []) or [])
        if not pills:
            return {}, [], {'order': [], 'lanes': [], 'buckets': {}}

        def _norm(s):
            return (s or "").strip().lower()

        # Optional resolver for list name via DB
        def _resolve_list_name(list_id, current_name=""):
            nm = (current_name or "").strip()
            if nm:
                return nm
            if include_db and list_id and getattr(self, 'db_manager', None) and self.db_manager.connected and self.current_project:
                try:
                    schema = self.db_manager.schema_name_for_project(self.current_project)
                    cur = self.db_manager.connection.cursor()
                    cur.execute(sql.SQL("SELECT name FROM {}.function_lists WHERE id = %s").format(sql.Identifier(schema)), (list_id,))
                    row = cur.fetchone()
                    if row and row[0]:
                        return str(row[0])
                except Exception:
                    try:
                        self.db_manager.connection.rollback()
                    except Exception:
                        pass
            return "(Unassigned)"

        def _parse_related(text):
            out = []
            for line in (text or "").splitlines():
                l = line.strip()
                if l.lower().startswith("related to:"):
                    rest = l.split(":", 1)[1]
                    out.extend([p.strip() for p in rest.split(",") if p.strip()])
            # Normalize/dedupe
            seen, res = set(), []
            for n in out:
                n2 = _norm(n)
                if n2 and n2 not in seen:
                    seen.add(n2)
                    res.append(n2)
            return res

        nodes = {}
        for p in pills:
            name = getattr(p, 'name', '') or ''
            name_norm = _norm(name)
            list_id = getattr(p, 'list_id', None)
            list_name = _resolve_list_name(list_id, getattr(p, 'list_name', ''))
            try:
                order_val = int(getattr(p, 'list_order', None)) if getattr(p, 'list_order', None) is not None else None
            except Exception:
                order_val = None
            relationships_raw = getattr(p, 'relationships', '') or ''
            nodes[name_norm] = {
                'name': name,
                'list_id': list_id,
                'list_name': list_name,
                'list_order': order_val,
                'relationships_raw': relationships_raw,
                'relationships': _parse_related(relationships_raw),
            }

        # Edges, filtered to known nodes, no self-loops, deduped
        edges = []
        for src_norm, nd in nodes.items():
            for dst_norm in nd['relationships']:
                if dst_norm == src_norm:
                    continue
                if dst_norm in nodes:
                    edges.append((src_norm, dst_norm))
        edges = list({e: None for e in edges}.keys())

        # Lanes and buckets
        lane_names = sorted({nd['list_name'] for nd in nodes.values()}, key=lambda s: (s == "(Unassigned)", (s or '').lower()))
        numeric_orders = sorted({nd['list_order'] for nd in nodes.values() if nd['list_order'] is not None})
        if not numeric_orders:
            numeric_orders = [1]
        none_bucket = (numeric_orders[-1] if numeric_orders else 0) + 1
        buckets = {ln: {} for ln in lane_names}
        for nm, nd in nodes.items():
            ln = nd['list_name']
            ov = nd['list_order'] if nd['list_order'] is not None else none_bucket
            buckets.setdefault(ln, {})
            buckets[ln].setdefault(ov, []).append(nm)
        steps = sorted({o for ln in buckets for o in buckets[ln].keys()})
        lanes = {'order': steps, 'lanes': lane_names, 'buckets': buckets}
        return nodes, edges, lanes

    def show_logical_mapping_v2(self):
        """Render logical mapping using the normalized graph from extract_function_graph."""
        # Auto-save current in-memory pills to DB (upsert per function) so mapping reflects latest edits
        try:
            if getattr(self, 'db_manager', None) and self.db_manager.connected and self.current_project:
                self.db_manager.ensure_project_schema(self.current_project)
                schema = self.db_manager.schema_name_for_project(self.current_project)
                cur = self.db_manager.connection.cursor()
                for pill in list(getattr(self, 'pills', []) or []):
                    data = pill.get_data()
                    inputs_json = json.dumps(data.get('inputs') or [])
                    outputs_json = json.dumps(data.get('outputs') or [])
                    cur.execute(
                        sql.SQL(
                            """
                            INSERT INTO {}.functions (name, description, visual_output, relationships, x_position, y_position, list_id, list_order, inputs, outputs)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (name)
                            DO UPDATE SET
                                description = EXCLUDED.description,
                                visual_output = EXCLUDED.visual_output,
                                relationships = EXCLUDED.relationships,
                                x_position = EXCLUDED.x_position,
                                y_position = EXCLUDED.y_position,
                                list_id = EXCLUDED.list_id,
                                list_order = EXCLUDED.list_order,
                                inputs = EXCLUDED.inputs,
                                outputs = EXCLUDED.outputs,
                                updated_at = CURRENT_TIMESTAMP
                            """
                        ).format(sql.Identifier(schema)),
                        (
                            data.get('name'),
                            data.get('description'),
                            data.get('visual_output'),
                            data.get('relationships'),
                            data.get('x'),
                            data.get('y'),
                            data.get('list_id'),
                            data.get('list_order'),
                            inputs_json,
                            outputs_json,
                        ),
                    )
                self.db_manager.connection.commit()
        except Exception:
            try:
                self.db_manager.connection.rollback()
            except Exception:
                pass
        nodes, edges, lanes = self.extract_function_graph(include_db=True)
        if not nodes:
            messagebox.showinfo("Logical Mapping", "No functions found. Add functions first.")
            return

        lane_names = lanes['lanes']
        steps = lanes['order']
        buckets = lanes['buckets']

        win = tk.Toplevel(self.root)
        win.title("Logical Mapping")
        try:
            win.geometry("980x640")
        except Exception:
            pass

        outer = ttk.Frame(win)
        outer.pack(fill=tk.BOTH, expand=True)

        xscroll = ttk.Scrollbar(outer, orient=tk.HORIZONTAL)
        yscroll = ttk.Scrollbar(outer, orient=tk.VERTICAL)
        canvas = tk.Canvas(outer, bg="#fafafa", xscrollcommand=xscroll.set, yscrollcommand=yscroll.set, highlightthickness=0)
        xscroll.config(command=canvas.xview)
        yscroll.config(command=canvas.yview)
        canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        lane_width = 240
        lane_gap = 30
        top_margin = 80
        left_margin = 40
        step_height = 120
        node_w = 160
        node_h = 44
        node_gap_x = 16

        total_width = left_margin + len(lane_names) * lane_width + (len(lane_names) - 1) * lane_gap + 80
        total_height = top_margin + len(steps) * step_height + 120
        canvas.config(scrollregion=(0, 0, total_width, total_height))

        lane_x = {}
        header_font = ("Arial", 11, "bold")
        lane_fill = "#eef3fb"
        lane_outline = "#c3d3ee"
        for idx, ln in enumerate(lane_names):
            x0 = left_margin + idx * (lane_width + lane_gap)
            x1 = x0 + lane_width
            lane_x[ln] = (x0, x1)
            canvas.create_rectangle(x0, 40, x1, total_height - 40, fill=lane_fill, outline=lane_outline)
            canvas.create_text((x0 + x1)//2, 20, text=ln, font=header_font, fill="#2e5c8a")

        node_pos = {}
        palette = ["#4A90E2", "#7B8D8E", "#8E44AD", "#27AE60", "#D35400", "#C0392B", "#16A085", "#2C3E50"]
        lane_color = {ln: palette[i % len(palette)] for i, ln in enumerate(lane_names)}

        def _draw_node(ln, step_idx, index_in_bucket, label, fill):
            x0, x1 = lane_x[ln]
            cx = (x0 + x1) // 2
            offset = index_in_bucket * node_gap_x
            dir_sign = -1 if (index_in_bucket % 2 == 1) else 1
            cx += dir_sign * offset
            y = top_margin + step_idx * step_height
            rect_id = canvas.create_rectangle(cx - node_w//2, y - node_h//2, cx + node_w//2, y + node_h//2,
                                              fill=fill, outline="#2E5C8A", width=2)
            disp = label if len(label) <= 22 else (label[:19] + "...")
            canvas.create_text(cx, y, text=disp, fill="white", font=("Arial", 10, "bold"))
            return canvas.bbox(rect_id)

        for ln in lane_names:
            for s_idx, step in enumerate(steps):
                nlist = buckets.get(ln, {}).get(step, [])
                nlist_sorted = sorted(nlist, key=lambda nm: (nodes[nm]['list_order'] is None, (nodes[nm]['name'] or '').lower()))
                for j, nm in enumerate(nlist_sorted):
                    nd = nodes[nm]
                    bbox = _draw_node(ln, s_idx, j, nd['name'], lane_color[ln])
                    node_pos[nm] = bbox

        def _center(b):
            x0, y0, x1, y1 = b
            return (x0 + x1) / 2.0, (y0 + y1) / 2.0

        drawn = set()
        for src, dst in edges:
            if src in node_pos and dst in node_pos and (src, dst) not in drawn:
                sx, sy = _center(node_pos[src])
                tx, ty = _center(node_pos[dst])
                mid_x = (sx + tx) / 2.0
                canvas.create_line(sx, sy, mid_x, sy, mid_x, ty, tx, ty, arrow=tk.LAST, fill="#555", width=2, smooth=True)
                drawn.add((src, dst))

        legend = ttk.Frame(win)
        legend.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(legend, text="Legend:").pack(side=tk.LEFT, padx=(8, 2))
        ttk.Label(legend, text="Swimlane = List, Vertical = Order, Arrows = Relationships ('Related to')").pack(side=tk.LEFT)

    # Objective management
    def edit_objective(self):
        """Open a dialog to view/edit the current project's objective and save it to the DB."""
        # Ensure preconditions
        if not getattr(self, 'db_manager', None) or not self.db_manager.connected:
            try:
                self.connect_database()
            except Exception:
                pass
        if not getattr(self, 'db_manager', None) or not self.db_manager.connected:
            messagebox.showwarning("Database", "Database connection required to edit objective")
            return
        if not getattr(self, 'current_project', None):
            messagebox.showwarning("Project", "Open or create a project to set its objective")
            return

        # Fetch current objective
        try:
            current_obj = self.db_manager.get_project_objective(self.current_project)
        except Exception:
            current_obj = None

        # Build dialog
        win = tk.Toplevel(self.root)
        win.title(f"Objective - {self.current_project}")
        win.geometry("700x360")
        win.transient(self.root)
        try:
            win.grab_set()
        except Exception:
            pass

        frm = ttk.Frame(win, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="Project Objective (short paragraph):").pack(anchor=tk.W)
        txt = tk.Text(frm, height=10, wrap=tk.WORD)
        txt.pack(fill=tk.BOTH, expand=True, pady=(6, 6))
        if current_obj:
            try:
                txt.insert("1.0", current_obj)
            except Exception:
                pass
        btns = ttk.Frame(frm)
        btns.pack(fill=tk.X)

        def _save():
            content = txt.get("1.0", tk.END).strip()
            ok = False
            try:
                ok = self.db_manager.set_project_objective(self.current_project, content)
            except Exception:
                ok = False
            if ok:
                # Keep a cached copy and reflect in status bar
                try:
                    self.current_objective = content
                except Exception:
                    pass
                try:
                    preview = (content[:80] + "…") if len(content) > 80 else content
                    self.status_var.set(f"Objective updated for '{self.current_project}': {preview}")
                except Exception:
                    pass
                messagebox.showinfo("Objective", "Objective saved")
                try:
                    win.destroy()
                except Exception:
                    pass
            else:
                messagebox.showerror("Objective", "Failed to save objective to database")

        ttk.Button(btns, text="Save", command=_save).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btns, text="Close", command=win.destroy).pack(side=tk.RIGHT)

    def _load_project_objective(self):
        """Load objective for current project and reflect in UI status bar (non-intrusive)."""
        if not getattr(self, 'db_manager', None) or not self.db_manager.connected or not getattr(self, 'current_project', None):
            return
        try:
            obj = self.db_manager.get_project_objective(self.current_project)
        except Exception:
            obj = None
        try:
            self.current_objective = obj or ""
        except Exception:
            pass
        if obj:
            try:
                preview = (obj[:80] + "…") if len(obj) > 80 else obj
                self.status_var.set(f"Opened '{self.current_project}'. Objective: {preview}")
            except Exception:
                pass

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
