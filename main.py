"""
EPUB to PDF — Clean, Claude-style desktop UI
Auto-selects best available system font (Inter > Segoe UI Variable > Segoe UI).
"""

import os
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageTk

# Windows taskbar grouping: distinct AppUserModelID so taskbar uses our icon,
# not the host pythonw.exe icon. Must run BEFORE first Tk window is created.
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "epub2pdf.app.1"
        )
    except Exception:
        pass

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

# ── Palette ──────────────────────────────────────────────────────────────────
BG     = "#FAF9F7"
ACCENT = "#D4774A"
ACCH   = "#BE6038"
TEXT   = "#18181B"
SUB    = "#6B7280"
BORDER = "#E4E4E7"
INPBG  = "#FFFFFF"
DSBLD  = "#EAC4AD"
TRACK  = "#E4E4E7"

# ── Font detection ────────────────────────────────────────────────────────────
_FONT_PREF = ["Inter", "Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", "Arial"]

def _pick_font() -> str:
    avail = set(tkfont.families())
    for f in _FONT_PREF:
        if f in avail:
            return f
    return "TkDefaultFont"


class FontPicker(ctk.CTkFrame):
    """Entry + dropdown button. Dropdown is tk.Listbox = native mouse-wheel scroll."""

    def __init__(self, master, variable: tk.StringVar, values: list[str],
                 ui_font: str, item_size: int = 18, height: int = 38):
        # Outer is the unified rounded rectangle container
        super().__init__(
            master, fg_color=INPBG, border_color=BORDER, border_width=1,
            corner_radius=8, height=height,
        )
        self.pack_propagate(False)

        self._values_all = values
        self._var = variable
        self._ui_font = ui_font
        self._item_size = item_size
        self._height = height
        self._popup: tk.Toplevel | None = None
        self._listbox: tk.Listbox | None = None
        self._root_click_bind_id: str | None = None
        self._chev_color = TEXT

        # ── Chevron canvas (right side, inside the rounded container) ────
        chev_w = 36
        self._canvas = tk.Canvas(
            self, bg=INPBG, highlightthickness=0, bd=0,
            width=chev_w, height=height - 4, cursor="hand2",
        )
        self._canvas.pack(side="right", padx=(0, 6), pady=2)
        self._canvas.bind("<Configure>", lambda _e: self._draw_chevron())
        self._canvas.bind("<Button-1>", lambda _e: self._toggle())
        self._canvas.bind("<Enter>", lambda _e: self._set_chev_hover(True))
        self._canvas.bind("<Leave>", lambda _e: self._set_chev_hover(False))

        # ── Entry (no own border, blends into rounded container) ─────────
        self.entry = ctk.CTkEntry(
            self, textvariable=variable,
            font=ctk.CTkFont(ui_font, 15),
            fg_color=INPBG, border_width=0,
            text_color=TEXT, corner_radius=0, height=height - 6,
        )
        self.entry.pack(side="left", fill="both", expand=True,
                        padx=(10, 2), pady=3)

        self.entry.bind("<KeyRelease>", self._on_key)
        self.entry.bind("<FocusIn>", lambda _e: self._open())
        self.entry.bind("<Down>", lambda _e: (self._open(), self._focus_list()))

    # ── Backward-compat: code reads self.btn.winfo_width() for popup sizing
    @property
    def btn(self):
        return self._canvas

    def _set_chev_hover(self, on: bool) -> None:
        self._chev_color = ACCENT if on else TEXT
        self._draw_chevron()

    def _draw_chevron(self) -> None:
        self._canvas.delete("all")
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        if w < 4 or h < 4:
            return
        cx, cy = w // 2, h // 2
        r = 8   # chevron half-width
        d = 4   # chevron half-height
        # Two strokes forming a "v"
        self._canvas.create_line(
            cx - r, cy - d, cx, cy + d,
            fill=self._chev_color, width=3, capstyle="round",
        )
        self._canvas.create_line(
            cx, cy + d, cx + r, cy - d,
            fill=self._chev_color, width=3, capstyle="round",
        )

    def _toggle(self) -> None:
        if self._popup and self._popup.winfo_exists():
            self._close()
        else:
            self._open()

    def _open(self) -> None:
        if self._popup and self._popup.winfo_exists():
            return
        self.update_idletasks()
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height() + 2
        w = self.entry.winfo_width() + self.btn.winfo_width() + 6
        h = 380

        self._popup = tk.Toplevel(self)
        self._popup.overrideredirect(True)
        self._popup.geometry(f"{w}x{h}+{x}+{y}")
        self._popup.configure(bg=BORDER)

        inner = tk.Frame(self._popup, bg=INPBG)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        self._listbox = tk.Listbox(
            inner, font=(self._ui_font, self._item_size),
            bg=INPBG, fg=TEXT, selectbackground=ACCENT,
            selectforeground="white", bd=0, highlightthickness=0,
            activestyle="none", relief="flat",
        )
        sb = tk.Scrollbar(inner, command=self._listbox.yview, width=12)
        self._listbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._listbox.pack(side="left", fill="both", expand=True)

        self._refresh()

        self._listbox.bind("<ButtonRelease-1>", self._on_pick)
        self._listbox.bind("<Return>", self._on_pick)
        self._listbox.bind("<Escape>", lambda _e: self._close())

        # ── Global click detection: close on click outside popup/button ──
        root = self.winfo_toplevel()
        self._root_click_bind_id = root.bind(
            "<Button-1>", self._on_global_click, add="+"
        )

    def _focus_list(self) -> None:
        if self._listbox and self._listbox.size() > 0:
            self._listbox.focus_set()
            self._listbox.selection_set(0)
            self._listbox.activate(0)

    def _refresh(self) -> None:
        """Populate listbox with full font list. Scroll/select to match current value."""
        if not self._listbox:
            return
        self._listbox.delete(0, "end")
        for v in self._values_all:
            self._listbox.insert("end", v)
        self._jump_to(self._var.get())

    def _jump_to(self, query: str) -> None:
        """Find first font matching query, select + scroll to it. Full list stays."""
        if not self._listbox or not query:
            return
        q = query.strip().lower()
        if not q:
            return
        # Prefer prefix match, fallback to substring match
        idx = None
        for i, v in enumerate(self._values_all):
            if v.lower().startswith(q):
                idx = i
                break
        if idx is None:
            for i, v in enumerate(self._values_all):
                if q in v.lower():
                    idx = i
                    break
        if idx is None:
            return
        self._listbox.selection_clear(0, "end")
        self._listbox.selection_set(idx)
        self._listbox.activate(idx)
        # Center the match in visible viewport
        self._listbox.see(idx)
        try:
            total = len(self._values_all)
            # Push so match sits near middle of viewport (~5 rows above)
            top = max(0, idx - 5)
            self._listbox.yview_moveto(top / total)
        except Exception:
            pass

    def _on_key(self, _e) -> None:
        self._open()
        self._jump_to(self._var.get())

    def _on_pick(self, _e) -> None:
        if not self._listbox:
            return
        sel = self._listbox.curselection()
        if sel:
            self._var.set(self._listbox.get(sel[0]))
        self._close()
        self.entry.focus_set()

    def _on_global_click(self, event) -> None:
        """Close popup if click lands outside popup, entry, or dropdown button."""
        if not self._popup or not self._popup.winfo_exists():
            return
        x, y = event.x_root, event.y_root

        def inside(widget) -> bool:
            try:
                wx = widget.winfo_rootx()
                wy = widget.winfo_rooty()
                ww = widget.winfo_width()
                wh = widget.winfo_height()
                return wx <= x <= wx + ww and wy <= y <= wy + wh
            except Exception:
                return False

        if inside(self._popup) or inside(self.entry) or inside(self._canvas) or inside(self):
            return
        self._close()

    def _close(self) -> None:
        if self._root_click_bind_id is not None:
            try:
                self.winfo_toplevel().unbind("<Button-1>", self._root_click_bind_id)
            except Exception:
                pass
            self._root_click_bind_id = None
        if self._popup and self._popup.winfo_exists():
            self._popup.destroy()
        self._popup = None
        self._listbox = None


# 0 = transparent (rounded corner), 1 = orange bg, 2 = white arrow
_ICON_GRID = [
    [0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0],
    [0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1,1,1,1,2,1,1,1,1],
    [1,1,1,1,1,1,1,1,1,1,1,2,2,1,1,1],
    [1,1,1,1,1,1,1,2,2,2,2,2,2,2,1,1],
    [1,1,1,1,1,1,1,2,2,2,2,2,2,2,2,1],
    [1,1,1,1,1,1,1,2,2,2,2,2,2,2,1,1],
    [1,1,1,1,1,1,1,1,1,1,1,2,2,1,1,1],
    [1,1,1,1,1,1,1,1,1,1,1,2,1,1,1,1],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    [0,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0],
    [0,0,1,1,1,1,1,1,1,1,1,1,1,1,0,0],
]


def _render_app_icon(size: int) -> Image.Image:
    """Pixel art icon — NEAREST scaling, rounded corners, same as desktop icon."""
    _ACCENT = (212, 119, 74, 255)
    _WHITE  = (255, 255, 255, 255)
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    pix = img.load()
    for r, row in enumerate(_ICON_GRID):
        for c, val in enumerate(row):
            if val == 1:
                pix[c, r] = _ACCENT
            elif val == 2:
                pix[c, r] = _WHITE
    return img.resize((size, size), Image.NEAREST)


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("EPUB → PDF")
        w, h = 660, 620
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, (sw - w) // 2)
        y = max(0, (sh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(560, 500)
        self.configure(fg_color=BG)
        self.resizable(True, True)

        # Window + taskbar icon. icon.ico for window decoration / system tray.
        # wm_iconphoto sets the icon Windows uses in the taskbar (256x256 PNG
        # path gives crisp rendering at any DPI).
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "icon.ico")
        if os.path.isfile(icon_path):
            try:
                # default=True → all future Toplevel windows inherit this icon
                self.iconbitmap(default=icon_path)
            except Exception:
                try:
                    self.iconbitmap(icon_path)
                except Exception:
                    pass
        try:
            # High-res PNG for taskbar (iconbitmap alone sometimes leaves
            # the small taskbar icon stale; iconphoto forces refresh).
            self._taskbar_icon = ImageTk.PhotoImage(_render_app_icon(256))
            self.wm_iconphoto(True, self._taskbar_icon)
        except Exception:
            pass

        self._UF = _pick_font()          # UI font family
        self._all_fonts: list[str] = sorted(set(tkfont.families()), key=str.lower)
        self._var_map:   dict[str, tk.StringVar] = {}

        self.epub_var   = tk.StringVar()
        self.output_var = tk.StringVar()
        self.font_var   = tk.StringVar(value="Times New Roman")
        self.cjk_var    = tk.StringVar(value="PMingLiU")
        self.code_var   = tk.StringVar(value="Consolas")
        self.size_var   = tk.IntVar(value=12)
        self.lh_var     = tk.DoubleVar(value=1.6)
        self.margin_var = tk.StringVar(value="2cm")
        self.status_var = tk.StringVar(value="选择 EPUB 文件开始转换")

        self._build()
        self.after(100, self._force_show)

    def _force_show(self) -> None:
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(500, lambda: self.attributes("-topmost", False))

    # ── Shorthand font constructors ───────────────────────────────────────────

    def _f(self, size: int, weight: str = "normal") -> ctk.CTkFont:
        return ctk.CTkFont(self._UF, size, weight)

    def _tf(self, size: int, weight: str = "normal") -> tuple:
        """Plain tk font tuple (for tk.Label / tk.Frame children)."""
        return (self._UF, size, weight)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        main = ctk.CTkFrame(self, fg_color=BG)
        main.pack(fill="both", expand=True, padx=28, pady=22)

        self._header(main)
        self._sep(main, top=16, bot=16)
        self._file_section(main)
        self._sep(main, top=14, bot=14)
        self._font_section(main)
        self._sep(main, top=14, bot=14)
        self._page_section(main)
        self._action_section(main)

    # ── Header ────────────────────────────────────────────────────────────────

    def _header(self, p) -> None:
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x")

        # Canvas icon: pixel art at 48px (3× of 16px base = perfect NEAREST scale)
        size = 48
        pil_img = _render_app_icon(size)
        self._header_icon = ImageTk.PhotoImage(pil_img)
        c = tk.Canvas(row, width=size, height=size,
                       bg=BG, highlightthickness=0)
        c.pack(side="left", padx=(0, 4))
        c.create_image(0, 0, anchor="nw", image=self._header_icon)

        title_col = tk.Frame(row, bg=BG)
        title_col.pack(side="left", padx=14)

        tk.Label(title_col, text="EPUB  →  PDF",
                  bg=BG, fg=TEXT,
                  font=self._tf(26, "bold")).pack(anchor="w")
        tk.Label(title_col, text="电子书转 PDF 转换器",
                  bg=BG, fg=SUB,
                  font=self._tf(15)).pack(anchor="w")

    def _sep(self, p, top: int = 16, bot: int = 16) -> None:
        ctk.CTkFrame(p, fg_color=BORDER, height=1).pack(
            fill="x", pady=(top, bot))

    def _section_lbl(self, p, text: str) -> None:
        tk.Label(p, text=text, bg=BG, fg=SUB,
                  font=self._tf(14, "bold"), anchor="w").pack(anchor="w", pady=(0, 8))

    # ── File section ──────────────────────────────────────────────────────────

    def _file_section(self, p) -> None:
        self._section_lbl(p, "文件")

        for var, placeholder, cmd in [
            (self.epub_var,   "选择 EPUB 文件…",            self._browse_epub),
            (self.output_var, "输出目录（留空 = 与文件相同目录）", self._browse_output),
        ]:
            row = ctk.CTkFrame(p, fg_color="transparent")
            row.pack(fill="x", pady=(0, 10))
            ctk.CTkEntry(
                row, textvariable=var,
                placeholder_text=placeholder,
                font=self._f(15),
                fg_color=INPBG, border_color=BORDER, border_width=1,
                text_color=TEXT, placeholder_text_color="#A1A1AA",
                corner_radius=8, height=38,
            ).pack(side="left", fill="x", expand=True, padx=(0, 10))
            ctk.CTkButton(
                row, text="选择", command=cmd,
                font=self._f(15),
                fg_color=INPBG, hover_color="#F0EDEA",
                text_color=TEXT, border_width=1, border_color=BORDER,
                corner_radius=8, height=38, width=68,
            ).pack(side="right")

    # ── Font section ──────────────────────────────────────────────────────────

    def _font_section(self, p) -> None:
        self._section_lbl(p, "字体")

        grid = tk.Frame(p, bg=BG)
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=6, uniform="fc")
        grid.columnconfigure(1, weight=6, uniform="fc")
        grid.columnconfigure(2, weight=5, uniform="fc")

        for col, (lbl, var, tag) in enumerate([
            ("西文字体", self.font_var, "en"),
            ("中文字体", self.cjk_var,  "cjk"),
            ("代码字体", self.code_var,  "code"),
        ]):
            cell = tk.Frame(grid, bg=BG)
            cell.grid(row=0, column=col, sticky="ew",
                       padx=(0, 18) if col < 2 else 0)

            tk.Label(cell, text=lbl, bg=BG, fg=SUB,
                      font=self._tf(13), anchor="w").pack(anchor="w", pady=(0, 5))

            picker = FontPicker(
                cell, variable=var, values=self._all_fonts,
                ui_font=self._UF, item_size=18, height=38,
            )
            picker.pack(fill="x")

            self._var_map[tag] = var
            setattr(self, f"_combo_{tag}", picker)

    # ── Page section ──────────────────────────────────────────────────────────

    def _page_section(self, p) -> None:
        self._section_lbl(p, "页面")

        grid = tk.Frame(p, bg=BG)
        grid.pack(fill="x")
        grid.columnconfigure(0, weight=1, uniform="pg")
        grid.columnconfigure(1, weight=1, uniform="pg")
        grid.columnconfigure(2, weight=1, uniform="pg")

        sz = tk.Frame(grid, bg=BG)
        sz.grid(row=0, column=0, sticky="ew", padx=(0, 28))
        self._slider_cell(sz, "字号", self.size_var, 8, 28,
                           lambda v: f"{int(float(v))} pt")

        lh = tk.Frame(grid, bg=BG)
        lh.grid(row=0, column=1, sticky="ew", padx=(0, 28))
        self._slider_cell(lh, "行距", self.lh_var, 1.0, 3.0,
                           lambda v: f"{float(v):.1f}")

        mg = tk.Frame(grid, bg=BG)
        mg.grid(row=0, column=2, sticky="ew")
        tk.Label(mg, text="页边距", bg=BG, fg=SUB,
                  font=self._tf(13), anchor="w").pack(anchor="w", pady=(0, 5))
        self._margin_buttons(mg)

    def _slider_cell(self, parent, lbl: str, var, lo, hi, fmt_fn) -> None:
        tk.Label(parent, text=lbl, bg=BG, fg=SUB,
                  font=self._tf(13), anchor="w").pack(anchor="w", pady=(0, 5))

        val_lbl = tk.Label(parent, text=fmt_fn(var.get()),
                            bg=BG, fg=TEXT,
                            font=self._tf(22, "bold"), anchor="w")
        val_lbl.pack(anchor="w")

        ctk.CTkSlider(
            parent, variable=var, from_=lo, to=hi,
            command=lambda v, l=val_lbl, f=fmt_fn: l.configure(text=f(v)),
            button_color=ACCENT, button_hover_color=ACCH,
            progress_color=ACCENT, fg_color=TRACK,
            height=14,
        ).pack(fill="x", pady=(8, 0))

    def _margin_buttons(self, parent) -> None:
        choices = ["1cm", "1.5cm", "2cm", "2.5cm", "3cm"]
        row = tk.Frame(parent, bg=BG)
        row.pack(anchor="w")
        self._mbtn: dict[str, tk.Label] = {}

        def select(val: str) -> None:
            self.margin_var.set(val)
            for v, btn in self._mbtn.items():
                active = v == val
                btn.configure(
                    bg=ACCENT if active else INPBG,
                    fg="white" if active else TEXT,
                )

        for i, ch in enumerate(choices):
            # Thin border wrapper
            wrap = tk.Frame(row, bg=BORDER, padx=1, pady=1)
            wrap.pack(side="left")
            btn = tk.Label(
                wrap, text=ch, cursor="hand2",
                bg=ACCENT if ch == self.margin_var.get() else INPBG,
                fg="white" if ch == self.margin_var.get() else TEXT,
                font=self._tf(13, "bold"),
                padx=9, pady=6,
            )
            btn.pack()
            btn.bind("<Button-1>", lambda _e, v=ch: select(v))
            self._mbtn[ch] = btn

    # ── Action section ────────────────────────────────────────────────────────

    def _action_section(self, p) -> None:
        self.convert_btn = ctk.CTkButton(
            p, text="开始转换",
            font=self._f(17, "bold"),
            fg_color=ACCENT, hover_color=ACCH,
            text_color="white", corner_radius=8,
            height=46, command=self._on_convert,
        )
        self.convert_btn.pack(fill="x", pady=(20, 12))

        self._pb = ctk.CTkProgressBar(
            p, fg_color=TRACK, progress_color=ACCENT,
            corner_radius=3, height=4,
        )
        self._pb.pack(fill="x", pady=(0, 8))
        self._pb.set(0)

        ctk.CTkLabel(p, textvariable=self.status_var,
                      font=self._f(14),
                      text_color=SUB, anchor="w").pack(fill="x")

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _browse_epub(self) -> None:
        path = filedialog.askopenfilename(
            title="选择 EPUB 文件",
            filetypes=[("EPUB 文件", "*.epub"), ("所有文件", "*.*")],
        )
        if path:
            self.epub_var.set(path)
            if not self.output_var.get():
                self.output_var.set(os.path.dirname(path))

    def _browse_output(self) -> None:
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.output_var.set(path)

    def _on_convert(self) -> None:
        epub = self.epub_var.get().strip()
        outd = self.output_var.get().strip() or (
            os.path.dirname(epub) if epub else ""
        )
        if not epub:
            messagebox.showerror("错误", "请先选择 EPUB 文件")
            return
        if not os.path.isfile(epub):
            messagebox.showerror("错误", f"文件不存在:\n{epub}")
            return

        out = os.path.join(outd, Path(epub).stem + ".pdf")
        self._pb.set(0)
        self.convert_btn.configure(state="disabled", fg_color=DSBLD)
        self.status_var.set("转换中，请稍候…")

        def _run() -> None:
            try:
                from converter import convert_epub_to_pdf
                convert_epub_to_pdf(
                    epub_path=epub, output_path=out,
                    font_family=self.font_var.get().strip(),
                    cjk_font_family=self.cjk_var.get().strip(),
                    code_font_family=self.code_var.get().strip(),
                    font_size=self.size_var.get(),
                    line_height=round(self.lh_var.get(), 1),
                    margin=self.margin_var.get(),
                    progress_callback=self._on_progress,
                )
                self.after(0, self._done, out, None)
            except Exception as exc:
                self.after(0, self._done, None, str(exc))

        threading.Thread(target=_run, daemon=True).start()

    def _on_progress(self, msg: str, pct) -> None:
        def _u():
            self.status_var.set(msg)
            if pct is not None:
                self._pb.set(pct / 100)
        self.after(0, _u)

    def _done(self, out, err) -> None:
        self.convert_btn.configure(state="normal", fg_color=ACCENT)
        if err:
            self.status_var.set(f"失败: {err}")
            messagebox.showerror("转换失败", err)
        else:
            self._pb.set(1.0)
            self.status_var.set(f"完成！已保存到: {out}")
            if messagebox.askyesno("转换成功",
                                    f"PDF 已保存至:\n{out}\n\n是否立即打开?"):
                os.startfile(out)



if __name__ == "__main__":
    try:
        App().mainloop()
    except Exception:
        import traceback
        log_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "crash.log"
        )
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
        except Exception:
            pass
        try:
            from tkinter import messagebox
            messagebox.showerror("启动失败", traceback.format_exc())
        except Exception:
            pass
