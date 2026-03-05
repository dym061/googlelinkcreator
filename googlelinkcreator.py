#!/usr/bin/env python3
"""
Google Search Link Builder — Dark Neon GUI
Build, save and manage Google search URLs visually.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json, os, sys, webbrowser, urllib.parse
import copy, threading, time, shutil
from datetime import datetime, timedelta

try:
    from tkinterdnd2 import DND_FILES, DND_TEXT, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

# ── Palette ───────────────────────────────────────────────────────────────────
BG      = "#0d0d0d"
SURF    = "#141414"
SURF2   = "#1c1c1c"
SURF3   = "#252525"
ACCENT  = "#00ff41"
ACCH    = "#00cc33"
WHITE   = "#efefef"
MUTED   = "#585858"
BORDER  = "#2a2a2a"
DANGER  = "#ff3c3c"
DANGH   = "#3a0000"
ENTRY_C = "#171717"

F   = ("Segoe UI", 10)
FB  = ("Segoe UI", 10, "bold")
FS  = ("Segoe UI", 9)
FT  = ("Segoe UI", 12, "bold")
FM  = ("Consolas", 9)

BASE         = os.path.dirname(os.path.abspath(__file__))
DATA_FILE    = os.path.join(BASE, "links_data.json")
SETTINGS_FILE= os.path.join(BASE, "settings.json")
BACKUP_DIR   = os.path.join(BASE, "backups")

DATE_OPTS = [
    ("No date filter",  0),
    ("Last 24 hours",   1),
    ("Last 2 days",     2),
    ("Last 3 days",     3),
    ("Last 4 days",     4),
    ("Last 5 days",     5),
    ("Last 6 days",     6),
    ("Last 7 days",     7),
    ("Last 14 days",   14),
    ("Last 30 days",   30),
]

DEFAULTS = {
    "default_site": "",
    "default_date_range": 3,
    "auto_save": True,
    "backup_on_save": True,
    "max_backups": 10,
    "confirm_delete": True,
    "window_width": 1260,
    "window_height": 840,
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def neon_btn(parent, text, cmd, danger=False, small=False, width=None, **kw):
    fg   = DANGER if danger else ACCENT
    bgh  = DANGH  if danger else "#002b10"
    font = FS if small else F
    cfg = dict(font=font, bg=SURF3, fg=fg, activebackground=bgh,
               activeforeground=fg, relief="flat", bd=0, cursor="hand2",
               padx=8 if small else 12, pady=3 if small else 5)
    if width:
        cfg["width"] = width
    cfg.update(kw)
    btn = tk.Button(parent, text=text, command=cmd, **cfg)
    btn.bind("<Enter>", lambda e: btn.configure(bg=bgh))
    btn.bind("<Leave>", lambda e: btn.configure(bg=SURF3))
    return btn

def mk_entry(parent, width=32, **kw):
    return tk.Entry(parent, font=F, bg=ENTRY_C, fg=WHITE,
                    insertbackground=ACCENT, relief="flat", bd=0,
                    highlightthickness=1, highlightbackground=BORDER,
                    highlightcolor=ACCENT, width=width, **kw)

def mk_label(parent, text, bold=False, muted=False, fg=None, **kw):
    _fg = fg or (MUTED if muted else WHITE)
    _fn = FB if bold else F
    return tk.Label(parent, text=text, font=_fn, bg=kw.pop("bg", BG), fg=_fg, **kw)


class ScrollFrame(tk.Frame):
    """Scrollable container frame."""
    def __init__(self, parent, bg=BG, **kw):
        super().__init__(parent, bg=bg, **kw)
        self._bg = bg
        sb = tk.Scrollbar(self, orient="vertical", width=7,
                           bg=SURF2, troughcolor=BG, bd=0, relief="flat",
                           activebackground=ACCENT)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0,
                                 yscrollcommand=sb.set)
        sb.configure(command=self.canvas.yview)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.canvas.bind("<Enter>",  lambda e: self.canvas.bind_all("<MouseWheel>", self._scroll))
        self.canvas.bind("<Leave>",  lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_inner(self, e):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, e):
        self.canvas.itemconfig(self._win, width=e.width)

    def _scroll(self, e):
        self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")


# ── Main App ──────────────────────────────────────────────────────────────────

class App:
    def __init__(self):
        root_cls = TkinterDnD.Tk if HAS_DND else tk.Tk
        self.root = root_cls()
        self.root.title("Search Link Builder")
        self.root.configure(bg=BG)
        self.root.minsize(900, 580)

        self.links        = []
        self.settings     = dict(DEFAULTS)
        self.undo_stack   = []
        self.redo_stack   = []
        self._last_date   = datetime.now().date()
        self.or_rows      = []
        self.and_rows     = []
        self.excl_rows    = []
        self._drag_state  = {}

        self._load_data()
        self._load_settings()
        self.root.geometry(f"{self.settings['window_width']}x{self.settings['window_height']}")

        self._setup_styles()
        self._build_ui()
        self._start_date_watcher()
        self._rebuild_url()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    # ─── Persistence ──────────────────────────────────────────────────────────

    def _load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE) as f:
                    self.links = json.load(f).get("links", [])
            except Exception:
                self.links = []

    def _save_data(self, backup=False):
        if backup and self.settings.get("backup_on_save"):
            self._make_backup()
        try:
            with open(DATA_FILE, "w") as f:
                json.dump({"links": self.links, "ts": datetime.now().isoformat()}, f, indent=2)
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex))

    def _make_backup(self):
        if not os.path.exists(DATA_FILE):
            return
        os.makedirs(BACKUP_DIR, exist_ok=True)
        dst = os.path.join(BACKUP_DIR, f"links_{datetime.now():%Y%m%d_%H%M%S}.json")
        shutil.copy2(DATA_FILE, dst)
        files = sorted(os.listdir(BACKUP_DIR))
        mx = self.settings.get("max_backups", 10)
        while len(files) > mx:
            try:
                os.remove(os.path.join(BACKUP_DIR, files.pop(0)))
            except Exception:
                break

    def _load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE) as f:
                    self.settings.update(json.load(f))
            except Exception:
                pass

    def _save_settings(self):
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as ex:
            messagebox.showerror("Settings Error", str(ex))

    # ─── Undo / Redo ──────────────────────────────────────────────────────────

    def _push_undo(self):
        self.undo_stack.append(copy.deepcopy(self.links))
        if len(self.undo_stack) > 10:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self._sync_undo_btns()

    def _undo(self):
        if self.undo_stack:
            self.redo_stack.append(copy.deepcopy(self.links))
            self.links = self.undo_stack.pop()
            self._refresh_list()
            self._sync_undo_btns()

    def _redo(self):
        if self.redo_stack:
            self.undo_stack.append(copy.deepcopy(self.links))
            self.links = self.redo_stack.pop()
            self._refresh_list()
            self._sync_undo_btns()

    def _sync_undo_btns(self):
        if hasattr(self, "_undo_btn"):
            self._undo_btn.configure(state="normal" if self.undo_stack else "disabled")
        if hasattr(self, "_redo_btn"):
            self._redo_btn.configure(state="normal" if self.redo_stack else "disabled")

    # ─── Date watcher ─────────────────────────────────────────────────────────

    def _start_date_watcher(self):
        def run():
            while True:
                time.sleep(30)
                today = datetime.now().date()
                if today != self._last_date:
                    self._last_date = today
                    self.root.after(0, self._rebuild_url)
        threading.Thread(target=run, daemon=True).start()

    # ─── Styles ───────────────────────────────────────────────────────────────

    def _setup_styles(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=[0,0,0,0])
        s.configure("TNotebook.Tab", background=SURF2, foreground=MUTED,
                     font=FB, padding=[18, 8], borderwidth=0)
        s.map("TNotebook.Tab",
              background=[("selected", SURF3)],
              foreground=[("selected", ACCENT)])
        s.configure("TFrame", background=BG)
        s.configure("TCombobox", fieldbackground=ENTRY_C, background=SURF3,
                     foreground=WHITE, arrowcolor=ACCENT, borderwidth=0,
                     selectbackground=SURF3, selectforeground=WHITE, padding=4)
        s.map("TCombobox", fieldbackground=[("readonly", ENTRY_C)])
        self.root.option_add("*TCombobox*Listbox.background", SURF2)
        self.root.option_add("*TCombobox*Listbox.foreground", WHITE)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", BG)

    # ─── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_topbar()
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True)
        t1 = tk.Frame(nb, bg=BG)
        t2 = tk.Frame(nb, bg=BG)
        nb.add(t1, text="  SEARCH BUILDER  ")
        nb.add(t2, text="  SETTINGS  ")
        self._build_main(t1)
        self._build_settings(t2)

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=SURF, height=46)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="◆  SEARCH LINK BUILDER", font=FT,
                 bg=SURF, fg=ACCENT).pack(side="left", padx=14)
        r = tk.Frame(bar, bg=SURF)
        r.pack(side="right", padx=10, pady=6)
        self._redo_btn = neon_btn(r, "↷  Redo", self._redo, small=True)
        self._redo_btn.pack(side="right", padx=3)
        self._undo_btn = neon_btn(r, "↶  Undo", self._undo, small=True)
        self._undo_btn.pack(side="right", padx=3)
        tk.Frame(r, bg=BORDER, width=1, height=22).pack(side="right", padx=6)
        neon_btn(r, "💾  Save", lambda: self._save_data(backup=True), small=True).pack(side="right", padx=3)
        self._sync_undo_btns()

    # ─── MAIN TAB ─────────────────────────────────────────────────────────────

    def _build_main(self, parent):
        pw = tk.PanedWindow(parent, orient="horizontal",
                             sashwidth=5, sashpad=0, bg=BORDER,
                             bd=0, relief="flat")
        pw.pack(fill="both", expand=True)
        left = tk.Frame(pw, bg=BG)
        right = tk.Frame(pw, bg=BG)
        pw.add(left,  minsize=440, stretch="always")
        pw.add(right, minsize=380, stretch="always")
        self._build_builder(left)
        self._build_links_panel(right)

    # ── Query Builder (left) ──────────────────────────────────────────────────

    def _build_builder(self, parent):
        # Section header bar
        bar = tk.Frame(parent, bg=SURF, height=42)
        bar.pack(fill="x"); bar.pack_propagate(False)
        tk.Label(bar, text="Query Builder", font=FB, bg=SURF, fg=WHITE
                 ).pack(side="left", padx=14, pady=10)

        sf = ScrollFrame(parent)
        sf.pack(fill="both", expand=True)
        p = sf.inner

        # ── OR Groups ─────────────────────────────────────────────────────────
        self._sh(p, "OR GROUPS",
                 "Comma-separated terms per group → (a OR b OR c)  ·  Groups are AND-joined")
        self.or_frame = tk.Frame(p, bg=BG)
        self.or_frame.pack(fill="x", padx=10, pady=2)
        self._add_or_row()  # default empty group
        neon_btn(p, "+  Add OR Group", self._add_or_row, small=True
                 ).pack(anchor="w", padx=12, pady=(2,6))
        self._div(p)

        # ── Required terms ────────────────────────────────────────────────────
        self._sh(p, "REQUIRED TERMS",
                 "Each term/phrase must appear (AND'd)")
        self.and_frame = tk.Frame(p, bg=BG)
        self.and_frame.pack(fill="x", padx=10, pady=2)
        neon_btn(p, "+  Add Required Term", self._add_and_row, small=True
                 ).pack(anchor="w", padx=12, pady=(2,6))
        self._div(p)

        # ── Exclude ───────────────────────────────────────────────────────────
        self._sh(p, "EXCLUDE KEYWORDS", "Results containing these will be filtered out")
        self.excl_frame = tk.Frame(p, bg=BG)
        self.excl_frame.pack(fill="x", padx=10, pady=2)
        neon_btn(p, "+  Add Exclusion", self._add_excl_row, small=True
                 ).pack(anchor="w", padx=12, pady=(2,6))
        self._div(p)

        # ── Site ──────────────────────────────────────────────────────────────
        self._sh(p, "SITE FILTER", "Restrict to a specific website")
        row = tk.Frame(p, bg=BG); row.pack(fill="x", padx=12, pady=(2,6))
        tk.Label(row, text="site:", font=FB, bg=BG, fg=ACCENT).pack(side="left", padx=(0,4))
        self.site_var = tk.StringVar(value=self.settings.get("default_site",""))
        e = mk_entry(row, width=36, textvariable=self.site_var)
        e.pack(side="left", ipady=4)
        e.bind("<KeyRelease>", lambda _: self._rebuild_url())
        tk.Label(row, text="e.g. indeed.com", font=FS, bg=BG, fg=MUTED).pack(side="left", padx=6)
        self._div(p)

        # ── Date ──────────────────────────────────────────────────────────────
        self._sh(p, "DATE RANGE", "Filter by publication date (auto-updates at midnight)")
        drow = tk.Frame(p, bg=BG); drow.pack(fill="x", padx=12, pady=(2,6))
        self.date_var = tk.StringVar()
        def_days  = self.settings.get("default_date_range", 3)
        def_label = next((l for l,d in DATE_OPTS if d == def_days), "No date filter")
        self.date_var.set(def_label)
        cb = ttk.Combobox(drow, textvariable=self.date_var,
                          values=[l for l,_ in DATE_OPTS], state="readonly", width=18, font=F)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _: self._rebuild_url())
        self.date_lbl = tk.Label(drow, text="", font=FS, bg=BG, fg=MUTED)
        self.date_lbl.pack(side="left", padx=8)
        self._div(p)

        # ── URL Preview ───────────────────────────────────────────────────────
        self._sh(p, "GENERATED URL", "Live preview — updates as you type")
        pf = tk.Frame(p, bg=SURF2); pf.pack(fill="x", padx=10, pady=(2,4))
        self.url_text = tk.Text(pf, font=FM, bg=SURF2, fg=ACCENT, height=4,
                                 relief="flat", bd=6, wrap="word",
                                 state="disabled", cursor="arrow",
                                 selectbackground=SURF3, selectforeground=ACCENT,
                                 insertbackground=ACCENT)
        self.url_text.pack(fill="x")

        # Action row
        ar = tk.Frame(p, bg=BG); ar.pack(fill="x", padx=10, pady=8)
        neon_btn(ar, "⎘  Copy URL",        self._copy_url).pack(side="left", padx=(0,5))
        neon_btn(ar, "↗  Open in Browser", self._open_preview).pack(side="left", padx=(0,5))
        tk.Frame(ar, bg=BORDER, width=1, height=24).pack(side="left", padx=5)
        neon_btn(ar, "＋  Save to List",   self._save_to_list).pack(side="left", padx=(0,5))
        neon_btn(ar, "✕  Clear",           self._clear_builder, danger=True).pack(side="left")

    def _sh(self, parent, title, hint=""):
        """Section header."""
        r = tk.Frame(parent, bg=BG); r.pack(fill="x", padx=12, pady=(10,2))
        tk.Label(r, text=title, font=("Segoe UI",9,"bold"), bg=BG, fg=ACCENT).pack(side="left")
        if hint:
            tk.Label(r, text=f"  ·  {hint}", font=FS, bg=BG, fg=MUTED).pack(side="left")

    def _div(self, parent):
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=12, pady=3)

    # ── Term rows ─────────────────────────────────────────────────────────────

    def _make_row(self, container, collection, placeholder):
        rd = {}
        frame = tk.Frame(container, bg=SURF2, pady=1)
        frame.pack(fill="x", pady=2)

        inner = tk.Frame(frame, bg=SURF2); inner.pack(fill="x", padx=6, pady=3)

        ent = tk.Entry(inner, font=F, bg=ENTRY_C, fg=MUTED,
                        insertbackground=ACCENT, relief="flat", bd=0,
                        highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=ACCENT, width=34)
        ent.insert(0, placeholder)

        def fi(e, en=ent, ph=placeholder):
            if en.get() == ph: en.delete(0, "end"); en.configure(fg=WHITE)
        def fo(e, en=ent, ph=placeholder):
            if not en.get(): en.insert(0, ph); en.configure(fg=MUTED)

        ent.bind("<FocusIn>",  fi)
        ent.bind("<FocusOut>", fo)
        ent.bind("<KeyRelease>", lambda _: self._rebuild_url())
        ent.pack(side="left", fill="x", expand=True, ipady=4)

        exact_var = tk.BooleanVar()
        tk.Checkbutton(inner, text='""', variable=exact_var, font=FS,
                        bg=SURF2, fg=MUTED, activebackground=SURF2,
                        activeforeground=ACCENT, selectcolor=SURF3, cursor="hand2",
                        command=self._rebuild_url).pack(side="left", padx=4)

        def remove():
            collection.remove(rd); frame.destroy(); self._rebuild_url()

        tk.Button(inner, text="✕", font=FS, bg=SURF2, fg=MUTED,
                   activebackground=SURF2, activeforeground=DANGER,
                   relief="flat", bd=0, cursor="hand2",
                   command=remove, padx=4).pack(side="left")

        rd.update({"frame": frame, "entry": ent, "exact": exact_var, "ph": placeholder})
        collection.append(rd)
        return rd

    def _add_or_row(self):
        self._make_row(self.or_frame, self.or_rows, "term1, term2, term3 ...")

    def _add_and_row(self):
        self._make_row(self.and_frame, self.and_rows, "required phrase or word")

    def _add_excl_row(self):
        self._make_row(self.excl_frame, self.excl_rows, "word to exclude")

    def _get_val(self, rd):
        v = rd["entry"].get().strip()
        return "" if v == rd["ph"] else v

    # ── URL Assembly ──────────────────────────────────────────────────────────

    def _build_url(self):
        parts = []

        for rd in self.or_rows:
            raw = self._get_val(rd)
            if not raw: continue
            terms = [t.strip() for t in raw.split(",") if t.strip()]
            if not terms: continue
            if rd["exact"].get():
                terms = [f'"{t}"' for t in terms]
            parts.append(f"({' OR '.join(terms)})" if len(terms) > 1 else terms[0])

        for rd in self.and_rows:
            raw = self._get_val(rd)
            if not raw: continue
            parts.append(f'"{raw}"' if rd["exact"].get() else raw)

        q = " AND ".join(parts) if parts else ""

        excl = []
        for rd in self.excl_rows:
            raw = self._get_val(rd)
            if not raw: continue
            excl.append(f'-"{raw}"' if rd["exact"].get() else f"-{raw}")

        if excl:
            q = (q + " " if q else "") + " ".join(excl)

        site = self.site_var.get().strip()
        if site:
            q += f" site:{site}"

        if not q.strip():
            return ""

        params = {"q": q.strip()}

        label = self.date_var.get()
        days  = next((d for l,d in DATE_OPTS if l == label), 0)
        if days:
            today = datetime.now()
            past  = today - timedelta(days=days)
            params["tbs"] = f"cdr:1,cd_min:{past.month}/{past.day}/{past.year},cd_max:{today.month}/{today.day}/{today.year}"
            self.date_lbl.configure(text=f"{past:%b %d} → {today:%b %d, %Y}")
        else:
            self.date_lbl.configure(text="")

        return "https://www.google.com/search?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)

    def _rebuild_url(self):
        url = self._build_url()
        self.url_text.configure(state="normal")
        self.url_text.delete("1.0", "end")
        if url:
            self.url_text.insert("1.0", url)
            self.url_text.configure(fg=ACCENT)
        else:
            self.url_text.insert("1.0", "← Fill in fields above to generate a URL")
            self.url_text.configure(fg=MUTED)
        self.url_text.configure(state="disabled")

    def _copy_url(self):
        url = self._build_url()
        if not url:
            messagebox.showwarning("No URL", "Build a URL first.")
            return
        self.root.clipboard_clear(); self.root.clipboard_append(url)
        self._flash("URL copied to clipboard!")

    def _open_preview(self):
        url = self._build_url()
        if url: webbrowser.open(url)
        else: messagebox.showwarning("No URL", "Build a URL first.")

    def _save_to_list(self):
        url = self._build_url()
        if not url:
            messagebox.showwarning("No URL", "Build a URL first.")
            return
        name = simpledialog.askstring("Save Link", "Enter a name for this link:", parent=self.root)
        if not name: return
        self._push_undo()
        self.links.append({
            "id": str(int(time.time() * 1000)),
            "name": name, "url": url,
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
        })
        self._refresh_list()
        if self.settings.get("auto_save"): self._save_data()
        self._flash(f"Saved: {name}")

    def _clear_builder(self):
        if not messagebox.askyesno("Clear", "Clear all query fields?", parent=self.root):
            return
        for rd in list(self.or_rows):   rd["frame"].destroy()
        for rd in list(self.and_rows):  rd["frame"].destroy()
        for rd in list(self.excl_rows): rd["frame"].destroy()
        self.or_rows.clear(); self.and_rows.clear(); self.excl_rows.clear()
        self.site_var.set(""); self.date_var.set("No date filter")
        self._add_or_row(); self._rebuild_url()

    # ─── Links Panel (right) ──────────────────────────────────────────────────

    def _build_links_panel(self, parent):
        bar = tk.Frame(parent, bg=SURF, height=42)
        bar.pack(fill="x"); bar.pack_propagate(False)
        tk.Label(bar, text="Saved Links", font=FB, bg=SURF, fg=WHITE
                 ).pack(side="left", padx=14, pady=10)
        self._cnt_lbl = tk.Label(bar, text="", font=FS, bg=SURF, fg=MUTED)
        self._cnt_lbl.pack(side="left")

        # Drop zone
        self._build_drop_zone(parent)

        # Scrollable list
        self._list_sf = ScrollFrame(parent)
        self._list_sf.pack(fill="both", expand=True, padx=0, pady=0)
        self._list_inner = self._list_sf.inner
        self._refresh_list()

    def _build_drop_zone(self, parent):
        dz = tk.Frame(parent, bg=SURF2, height=54, cursor="hand2")
        dz.pack(fill="x", padx=8, pady=(6,2))
        dz.pack_propagate(False)

        self._dz_lbl = tk.Label(dz,
            text="⬇  Drop URL / .txt file here   ·   or click to paste",
            font=FS, bg=SURF2, fg=MUTED)
        self._dz_lbl.place(relx=0.5, rely=0.5, anchor="center")

        def hl(e):  dz.configure(bg=SURF3); self._dz_lbl.configure(bg=SURF3)
        def uhl(e): dz.configure(bg=SURF2); self._dz_lbl.configure(bg=SURF2)

        def click(e):
            try:
                text = self.root.clipboard_get().strip()
            except Exception:
                text = ""
            if text.startswith("http"):
                self._import_url(text)
            else:
                url = simpledialog.askstring("Import URL", "Paste a URL:", parent=self.root)
                if url: self._import_url(url.strip())

        for w in (dz, self._dz_lbl):
            w.bind("<Button-1>", click)
            w.bind("<Enter>", hl)
            w.bind("<Leave>", uhl)

        if HAS_DND:
            dz.drop_target_register(DND_FILES, DND_TEXT)
            dz.dnd_bind("<<Drop>>", self._on_drop)

    def _on_drop(self, event):
        data = event.data.strip().strip("{}")
        if os.path.isfile(data):
            try:
                with open(data) as f:
                    for line in f:
                        u = line.strip()
                        if u.startswith("http"): self._import_url(u)
            except Exception as ex:
                messagebox.showerror("File Error", str(ex))
        elif data.startswith("http"):
            self._import_url(data)

    def _import_url(self, url):
        if not url.startswith("http"):
            messagebox.showwarning("Invalid URL", f"Not a valid URL:\n{url[:80]}")
            return
        suggested = self._auto_name(url)
        name = simpledialog.askstring("Import Link",
            f"Name for this link?\n{url[:70]}", initialvalue=suggested, parent=self.root)
        if not name: name = suggested
        self._push_undo()
        self.links.append({
            "id": str(int(time.time() * 1000)),
            "name": name, "url": url,
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
        })
        self._refresh_list()
        if self.settings.get("auto_save"): self._save_data()
        self._flash(f"Imported: {name}")

    def _auto_name(self, url):
        try:
            p   = urllib.parse.urlparse(url)
            host = p.netloc.replace("www.", "")
            q   = urllib.parse.parse_qs(p.query).get("q", [""])[0]
            return f"{host}: {q[:40]}" if q else host
        except Exception:
            return url[:40]

    # ─── Links List ───────────────────────────────────────────────────────────

    def _refresh_list(self):
        for w in self._list_inner.winfo_children():
            w.destroy()
        if not self.links:
            tk.Label(self._list_inner,
                text="No saved links yet.\nBuild a URL and click  ＋ Save to List",
                font=FS, bg=BG, fg=MUTED, justify="center").pack(pady=40)
        else:
            for lnk in self.links:
                self._make_link_row(lnk)
        n = len(self.links)
        self._cnt_lbl.configure(text=f"  {n} link{'s' if n!=1 else ''}")

    def _make_link_row(self, lnk):
        row = tk.Frame(self._list_inner, bg=SURF2)
        row.pack(fill="x", padx=6, pady=2)

        # Drag handle
        handle = tk.Label(row, text="⠿", font=("Segoe UI",13),
                           bg=SURF2, fg=MUTED, cursor="sb_v_double_arrow", padx=5)
        handle.pack(side="left")

        # Info
        info = tk.Frame(row, bg=SURF2)
        info.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        tk.Label(info, text=lnk["name"], font=FB, bg=SURF2, fg=WHITE, anchor="w"
                 ).pack(fill="x")
        short = lnk["url"][:62] + "…" if len(lnk["url"]) > 62 else lnk["url"]
        tk.Label(info, text=short, font=FS, bg=SURF2, fg=MUTED, anchor="w"
                 ).pack(fill="x")

        # Buttons
        btns = tk.Frame(row, bg=SURF2)
        btns.pack(side="right", padx=5, pady=4)
        neon_btn(btns, "↗", lambda l=lnk: webbrowser.open(l["url"]),      small=True).pack(side="left", padx=1)
        neon_btn(btns, "✎", lambda l=lnk: self._edit_link(l),              small=True).pack(side="left", padx=1)
        neon_btn(btns, "✕", lambda l=lnk: self._delete_link(l), danger=True, small=True).pack(side="left", padx=1)

        self._attach_drag(handle, lnk, row)

        # Hover
        def hl(e):
            for w in [row, info, btns, handle]: w.configure(bg=SURF3)
            for w in info.winfo_children(): w.configure(bg=SURF3)
        def uhl(e):
            for w in [row, info, btns, handle]: w.configure(bg=SURF2)
            for w in info.winfo_children(): w.configure(bg=SURF2)
        for w in [row, info, handle]:
            w.bind("<Enter>", hl); w.bind("<Leave>", uhl)

    def _attach_drag(self, handle, lnk, row):
        st = {}

        def press(e):
            st["y0"] = e.y_root
            st["idx"] = next((i for i, l in enumerate(self.links) if l["id"] == lnk["id"]), 0)
            # Ghost label
            ghost = tk.Label(self.root, text=lnk["name"], font=FB,
                              bg=ACCENT, fg=BG, padx=10, pady=4, relief="flat")
            rx = row.winfo_rootx() - self.root.winfo_rootx()
            ry = row.winfo_rooty() - self.root.winfo_rooty()
            ghost.place(x=rx, y=ry, width=row.winfo_width())
            st["ghost"] = ghost; st["gy0"] = ry
            row.configure(bg="#0a2010")

        def drag(e):
            if "ghost" not in st: return
            delta = e.y_root - st["y0"]
            st["ghost"].place(y=st["gy0"] + delta)

        def release(e):
            if "ghost" not in st: return
            st["ghost"].destroy(); del st["ghost"]
            row.configure(bg=SURF2)
            delta  = e.y_root - st["y0"]
            steps  = round(delta / 56)
            old    = st["idx"]
            new    = max(0, min(len(self.links)-1, old + steps))
            if new != old:
                self._push_undo()
                item = self.links.pop(old)
                self.links.insert(new, item)
                self._refresh_list()
                if self.settings.get("auto_save"): self._save_data()

        handle.bind("<ButtonPress-1>", press)
        handle.bind("<B1-Motion>",     drag)
        handle.bind("<ButtonRelease-1>", release)

    def _edit_link(self, lnk):
        win = tk.Toplevel(self.root); win.title("Edit Link")
        win.configure(bg=BG); win.geometry("520x180")
        win.transient(self.root); win.grab_set()

        tk.Label(win, text="Name", font=FB, bg=BG, fg=MUTED
                 ).grid(row=0, column=0, padx=14, pady=(14,4), sticky="w")
        nv = tk.StringVar(value=lnk["name"])
        mk_entry(win, width=50, textvariable=nv).grid(row=0, column=1, padx=10, pady=(14,4), sticky="ew", ipady=4)

        tk.Label(win, text="URL", font=FB, bg=BG, fg=MUTED
                 ).grid(row=1, column=0, padx=14, pady=4, sticky="w")
        uv = tk.StringVar(value=lnk["url"])
        mk_entry(win, width=50, textvariable=uv).grid(row=1, column=1, padx=10, pady=4, sticky="ew", ipady=4)

        win.columnconfigure(1, weight=1)

        def save():
            n = nv.get().strip(); u = uv.get().strip()
            if not n or not u:
                messagebox.showwarning("Required", "Name and URL required.", parent=win); return
            self._push_undo()
            lnk.update({"name": n, "url": u, "modified": datetime.now().isoformat()})
            self._refresh_list()
            if self.settings.get("auto_save"): self._save_data()
            win.destroy()

        br = tk.Frame(win, bg=BG); br.grid(row=2, column=0, columnspan=2, pady=12)
        neon_btn(br, "Save Changes", save).pack(side="left", padx=6)
        neon_btn(br, "Cancel",       win.destroy, danger=True).pack(side="left", padx=6)

    def _delete_link(self, lnk):
        if self.settings.get("confirm_delete"):
            if not messagebox.askyesno("Delete", f"Delete  \"{lnk['name']}\"?", parent=self.root):
                return
        self._push_undo()
        self.links = [l for l in self.links if l["id"] != lnk["id"]]
        self._refresh_list()
        if self.settings.get("auto_save"): self._save_data()

    # ─── SETTINGS TAB ─────────────────────────────────────────────────────────

    def _build_settings(self, parent):
        sf = ScrollFrame(parent); sf.pack(fill="both", expand=True)
        p  = sf.inner

        tk.Label(p, text="Settings", font=FT, bg=BG, fg=WHITE
                 ).pack(anchor="w", padx=18, pady=(18,2))
        tk.Frame(p, bg=BORDER, height=1).pack(fill="x", padx=18, pady=(0,8))

        self._svars = {}

        def sec(title):
            tk.Label(p, text=title, font=("Segoe UI",9,"bold"), bg=BG, fg=ACCENT
                     ).pack(anchor="w", padx=18, pady=(14,2))
            tk.Frame(p, bg=BORDER, height=1).pack(fill="x", padx=18, pady=(0,4))

        def row_bool(key, label):
            r = tk.Frame(p, bg=BG); r.pack(fill="x", padx=18, pady=3)
            v = tk.BooleanVar(value=self.settings.get(key, True))
            self._svars[key] = v
            tk.Checkbutton(r, text=label, variable=v,
                            bg=BG, fg=WHITE, activebackground=BG,
                            activeforeground=ACCENT, selectcolor=SURF3,
                            font=F, cursor="hand2").pack(side="left")

        def row_combo(key, label, options):
            r = tk.Frame(p, bg=BG); r.pack(fill="x", padx=18, pady=3)
            tk.Label(r, text=label, font=F, bg=BG, fg=WHITE, width=24, anchor="w").pack(side="left")
            v = tk.StringVar(value=str(self.settings.get(key, options[0])))
            self._svars[key] = v
            ttk.Combobox(r, textvariable=v, values=options,
                          state="readonly", width=18, font=F).pack(side="left", padx=6)

        def row_entry(key, label, hint=""):
            r = tk.Frame(p, bg=BG); r.pack(fill="x", padx=18, pady=3)
            tk.Label(r, text=label, font=F, bg=BG, fg=WHITE, width=24, anchor="w").pack(side="left")
            v = tk.StringVar(value=str(self.settings.get(key,"")))
            self._svars[key] = v
            mk_entry(r, width=28, textvariable=v).pack(side="left", padx=6, ipady=3)
            if hint:
                tk.Label(r, text=hint, font=FS, bg=BG, fg=MUTED).pack(side="left", padx=4)

        sec("URL / SEARCH DEFAULTS")
        row_entry("default_site", "Default site filter", "e.g. indeed.com")

        # Date range default
        r = tk.Frame(p, bg=BG); r.pack(fill="x", padx=18, pady=3)
        tk.Label(r, text="Default date range", font=F, bg=BG, fg=WHITE, width=24, anchor="w").pack(side="left")
        def_lbl = next((l for l,d in DATE_OPTS if d == self.settings.get("default_date_range",3)), "Last 3 days")
        dv = tk.StringVar(value=def_lbl)
        self._svars["_date_label"] = dv
        ttk.Combobox(r, textvariable=dv, values=[l for l,_ in DATE_OPTS],
                      state="readonly", width=18, font=F).pack(side="left", padx=6)

        sec("PROGRAM SETTINGS")
        row_bool("auto_save",      "Auto-save changes to disk")
        row_bool("backup_on_save", "Create timestamped backup on save")
        row_bool("confirm_delete", "Confirm before deleting a link")
        row_combo("max_backups",   "Max backup files to keep", ["5","10","20","50"])

        tk.Frame(p, bg=BORDER, height=1).pack(fill="x", padx=18, pady=12)
        br = tk.Frame(p, bg=BG); br.pack(anchor="w", padx=18, pady=6)
        neon_btn(br, "💾  Save Settings",   self._apply_settings).pack(side="left", padx=(0,8))
        neon_btn(br, "Reset Defaults", self._reset_settings, danger=True).pack(side="left")

        sec("DATA & BACKUPS")
        dr = tk.Frame(p, bg=BG); dr.pack(fill="x", padx=18, pady=6)
        neon_btn(dr, "📂  Open Backup Folder", self._open_backups,  small=True).pack(side="left", padx=(0,6))
        neon_btn(dr, "📤  Export JSON",         self._export_links, small=True).pack(side="left", padx=(0,6))
        neon_btn(dr, "📥  Import JSON",         self._import_links, small=True).pack(side="left")

        if not HAS_DND:
            tk.Frame(p, bg=BORDER, height=1).pack(fill="x", padx=18, pady=8)
            tk.Label(p, text="ℹ  Install tkinterdnd2 (pip install tkinterdnd2) to enable drag-and-drop file support.",
                     font=FS, bg=BG, fg=MUTED, wraplength=500, justify="left"
                     ).pack(anchor="w", padx=18, pady=4)

    def _apply_settings(self):
        for key, var in self._svars.items():
            val = var.get()
            if key == "_date_label":
                self.settings["default_date_range"] = next((d for l,d in DATE_OPTS if l == val), 3)
            elif key == "max_backups":
                try: self.settings[key] = int(val)
                except ValueError: pass
            else:
                self.settings[key] = val
        self._save_settings()
        self._flash("Settings saved!")

    def _reset_settings(self):
        if messagebox.askyesno("Reset", "Reset all settings to defaults?", parent=self.root):
            self.settings = dict(DEFAULTS)
            self._save_settings()
            messagebox.showinfo("Done", "Settings reset. Restart for full effect.", parent=self.root)

    def _open_backups(self):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        if sys.platform == "win32":   os.startfile(BACKUP_DIR)
        elif sys.platform == "darwin": os.system(f'open "{BACKUP_DIR}"')
        else:                          os.system(f'xdg-open "{BACKUP_DIR}"')

    def _export_links(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON","*.json")], title="Export Links")
        if path:
            with open(path, "w") as f: json.dump({"links": self.links}, f, indent=2)
            self._flash("Links exported!")

    def _import_links(self):
        path = filedialog.askopenfilename(filetypes=[("JSON","*.json")], title="Import Links")
        if not path: return
        try:
            with open(path) as f: data = json.load(f)
            links = data.get("links", [])
            if links:
                self._push_undo()
                self.links.extend(links)
                self._refresh_list()
                if self.settings.get("auto_save"): self._save_data()
                self._flash(f"Imported {len(links)} links!")
        except Exception as ex:
            messagebox.showerror("Import Error", str(ex))

    # ─── Utilities ────────────────────────────────────────────────────────────

    def _flash(self, msg, ms=2200):
        if hasattr(self, "_flash_w"):
            try: self._flash_w.destroy()
            except Exception: pass
        lbl = tk.Label(self.root, text=f"  {msg}  ", font=FB,
                        bg=ACCENT, fg=BG, padx=12, pady=6)
        lbl.place(relx=0.5, rely=0.96, anchor="center")
        self._flash_w = lbl
        self.root.after(ms, lambda: lbl.destroy() if lbl.winfo_exists() else None)

    def _on_close(self):
        self._save_data(backup=False)
        self._save_settings()
        self.root.destroy()


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    App()