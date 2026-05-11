"""
EPUB to PDF — Clean, Claude-style desktop UI
Auto-selects best available system font (Inter > Segoe UI Variable > Segoe UI).
"""

import os
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox
from pathlib import Path

import customtkinter as ctk

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


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("EPUB → PDF")
        self.geometry("780x660")
        self.minsize(660, 580)
        self.configure(fg_color=BG)
        self.resizable(True, True)

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
        self._center()

    # ── Shorthand font constructors ───────────────────────────────────────────

    def _f(self, size: int, weight: str = "normal") -> ctk.CTkFont:
        return ctk.CTkFont(self._UF, size, weight)

    def _tf(self, size: int, weight: str = "normal") -> tuple:
        """Plain tk font tuple (for tk.Label / tk.Frame children)."""
        return (self._UF, size, weight)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        main = ctk.CTkFrame(self, fg_color=BG)
        main.pack(fill="both", expand=True, padx=48, pady=40)

        self._header(main)
        self._sep(main, top=24, bot=24)
        self._file_section(main)
        self._sep(main, top=22, bot=22)
        self._font_section(main)
        self._sep(main, top=22, bot=22)
        self._page_section(main)
        self._action_section(main)

    # ── Header ────────────────────────────────────────────────────────────────

    def _header(self, p) -> None:
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x")

        # Canvas icon: orange circle + white arrow
        size = 44
        c = tk.Canvas(row, width=size, height=size,
                       bg=BG, highlightthickness=0)
        c.pack(side="left")
        c.create_oval(2, 2, size - 2, size - 2, fill=ACCENT, outline="")
        c.create_text(size // 2, size // 2 + 1, text="→",
                       fill="white",
                       font=(self._UF, 18, "bold"))

        title_col = tk.Frame(row, bg=BG)
        title_col.pack(side="left", padx=14)

        tk.Label(title_col, text="EPUB  →  PDF",
                  bg=BG, fg=TEXT,
                  font=self._tf(22, "bold")).pack(anchor="w")
        tk.Label(title_col, text="电子书转 PDF 转换器",
                  bg=BG, fg=SUB,
                  font=self._tf(12)).pack(anchor="w")

    def _sep(self, p, top: int = 16, bot: int = 16) -> None:
        ctk.CTkFrame(p, fg_color=BORDER, height=1).pack(
            fill="x", pady=(top, bot))

    def _section_lbl(self, p, text: str) -> None:
        tk.Label(p, text=text, bg=BG, fg=SUB,
                  font=self._tf(10), anchor="w").pack(anchor="w", pady=(0, 10))

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
                font=self._f(12),
                fg_color=INPBG, border_color=BORDER, border_width=1,
                text_color=TEXT, placeholder_text_color="#A1A1AA",
                corner_radius=8, height=44,
            ).pack(side="left", fill="x", expand=True, padx=(0, 10))
            ctk.CTkButton(
                row, text="选择", command=cmd,
                font=self._f(12),
                fg_color=INPBG, hover_color="#F0EDEA",
                text_color=TEXT, border_width=1, border_color=BORDER,
                corner_radius=8, height=44, width=68,
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
                      font=self._tf(10), anchor="w").pack(anchor="w", pady=(0, 5))

            combo = ctk.CTkComboBox(
                cell, variable=var, values=self._all_fonts,
                font=self._f(12),
                fg_color=INPBG, border_color=BORDER, border_width=1,
                button_color=BORDER, button_hover_color="#D4D4D8",
                dropdown_fg_color=INPBG, dropdown_hover_color="#F4F4F5",
                dropdown_text_color=TEXT,
                dropdown_font=self._f(12),
                text_color=TEXT, corner_radius=8, height=44,
                command=lambda _v, t=tag: None,
            )
            combo.pack(fill="x")

            self._var_map[tag] = var
            setattr(self, f"_combo_{tag}", combo)

            try:
                combo._entry.bind("<KeyRelease>",
                                   lambda _e, t=tag: self._filter_fonts(t))
            except AttributeError:
                pass

    def _filter_fonts(self, tag: str) -> None:
        var   = self._var_map[tag]
        combo = getattr(self, f"_combo_{tag}")
        q     = var.get().lower().strip()
        hits  = [f for f in self._all_fonts if q in f.lower()] if q else self._all_fonts
        combo.configure(values=hits or self._all_fonts)

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
                  font=self._tf(10), anchor="w").pack(anchor="w", pady=(0, 5))
        self._margin_buttons(mg)

    def _slider_cell(self, parent, lbl: str, var, lo, hi, fmt_fn) -> None:
        tk.Label(parent, text=lbl, bg=BG, fg=SUB,
                  font=self._tf(10), anchor="w").pack(anchor="w", pady=(0, 5))

        val_lbl = tk.Label(parent, text=fmt_fn(var.get()),
                            bg=BG, fg=TEXT,
                            font=self._tf(18, "bold"), anchor="w")
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
                font=self._tf(10),
                padx=9, pady=6,
            )
            btn.pack()
            btn.bind("<Button-1>", lambda _e, v=ch: select(v))
            self._mbtn[ch] = btn

    # ── Action section ────────────────────────────────────────────────────────

    def _action_section(self, p) -> None:
        self.convert_btn = ctk.CTkButton(
            p, text="开始转换",
            font=self._f(14, "bold"),
            fg_color=ACCENT, hover_color=ACCH,
            text_color="white", corner_radius=8,
            height=50, command=self._on_convert,
        )
        self.convert_btn.pack(fill="x", pady=(28, 16))

        self._pb = ctk.CTkProgressBar(
            p, fg_color=TRACK, progress_color=ACCENT,
            corner_radius=3, height=4,
        )
        self._pb.pack(fill="x", pady=(0, 10))
        self._pb.set(0)

        ctk.CTkLabel(p, textvariable=self.status_var,
                      font=self._f(11),
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

    def _center(self) -> None:
        self.update_idletasks()
        w, h   = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")


if __name__ == "__main__":
    App().mainloop()
