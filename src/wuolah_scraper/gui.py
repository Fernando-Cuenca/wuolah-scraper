"""
GUI GUARRERA para Wuolah Scraper
-------------------------------
Tkinter sin florituras. Pega cookies, busca, ve enlaces, descarga.
Solo funcional con cuenta PRO (sin anuncios). Con cuenta normal
Wuolah mete publicidad y el scraper no puede saltarla.

NO USA ESTO PARA BAJAR COSAS QUE NO HAS PAGADO.
"""

from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any

from .client import WuolahClient
from .crawler import CATEGORY_VALUES

CONFIG_PATH = Path.home() / ".wuolah-scraper-config.json"
DEFAULT_CONFIG = {
    "base_url": "https://wuolah.com",
    "api_base_url": "https://api.wuolah.com",
    "auth": {
        "cookie_header": "",
        "cookie_file": "",
        "access_token": "",
        "refresh_token": "",
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    },
    "crawl": {
        "request_timeout": 30,
        "sleep_seconds": 0.15,
        "page_size": 100,
        "max_pages": 3,
        "save_raw_pages": False,
        "fetch_document_details": True,
        "persist_preview_artifacts": False,
    },
}


def load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return DEFAULT_CONFIG


def save_config(cfg: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


class WuolahGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Wuolah Scraper — Modo Guarro v0.1")
        self.root.geometry("900x650")
        self.root.configure(bg="#2b2b2b")

        self.config = load_config()
        self.client: WuolahClient | None = None
        self._results: list[dict[str, Any]] = []

        self._build_ui()
        self._try_connect()

    # ── UI ──────────────────────────────────────────────

    def _build_ui(self):
        # === TOP BAR: Cookies ===
        top = tk.LabelFrame(self.root, text="Cookies / Auth (pegar aqui la cookie entera del navegador)", bg="#2b2b2b", fg="#aaa")
        top.pack(fill=tk.X, padx=8, pady=(8, 0))

        row1 = tk.Frame(top, bg="#2b2b2b")
        row1.pack(fill=tk.X, padx=4, pady=4)
        tk.Label(row1, text="Cookie:", bg="#2b2b2b", fg="#ccc").pack(side=tk.LEFT)
        self.cookie_var = tk.StringVar(value=self.config["auth"].get("cookie_header", ""))
        tk.Entry(row1, textvariable=self.cookie_var, bg="#3c3c3c", fg="#eee", insertbackground="#eee", width=90).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))

        row2 = tk.Frame(top, bg="#2b2b2b")
        row2.pack(fill=tk.X, padx=4, pady=(0, 4))
        tk.Button(row2, text="Cargar cookies.txt", command=self._load_cookie_file, bg="#444", fg="#eee").pack(side=tk.LEFT, padx=2)
        tk.Button(row2, text="Guardar config", command=self._save_cookie_config, bg="#444", fg="#eee").pack(side=tk.LEFT, padx=2)
        tk.Button(row2, text="Probar conexion", command=self._test_auth_thread, bg="#444", fg="#eee").pack(side=tk.LEFT, padx=2)
        self.auth_label = tk.Label(row2, text="❓", bg="#2b2b2b", fg="#aaa")
        self.auth_label.pack(side=tk.LEFT, padx=8)

        # === MIDDLE: Busqueda ===
        mid = tk.LabelFrame(self.root, text="Buscar documentos", bg="#2b2b2b", fg="#aaa")
        mid.pack(fill=tk.X, padx=8, pady=(8, 0))

        r1 = tk.Frame(mid, bg="#2b2b2b")
        r1.pack(fill=tk.X, padx=4, pady=4)
        tk.Label(r1, text="Universidad:", bg="#2b2b2b", fg="#ccc").pack(side=tk.LEFT)
        self.univ_var = tk.StringVar(value="universidad-carlos-iii-de-madrid")
        tk.Entry(r1, textvariable=self.univ_var, bg="#3c3c3c", fg="#eee", insertbackground="#eee", width=35).pack(side=tk.LEFT, padx=4)
        tk.Label(r1, text="Comunidad:", bg="#2b2b2b", fg="#ccc").pack(side=tk.LEFT, padx=(8, 0))
        self.community_var = tk.StringVar()
        tk.Entry(r1, textvariable=self.community_var, bg="#3c3c3c", fg="#eee", insertbackground="#eee", width=40).pack(side=tk.LEFT, padx=4)

        r2 = tk.Frame(mid, bg="#2b2b2b")
        r2.pack(fill=tk.X, padx=4, pady=(0, 4))
        tk.Label(r2, text="Asignatura:", bg="#2b2b2b", fg="#ccc").pack(side=tk.LEFT)
        self.subject_var = tk.StringVar()
        tk.Entry(r2, textvariable=self.subject_var, bg="#3c3c3c", fg="#eee", insertbackground="#eee", width=30).pack(side=tk.LEFT, padx=4)
        tk.Label(r2, text="Keyword:", bg="#2b2b2b", fg="#ccc").pack(side=tk.LEFT, padx=(8, 0))
        self.keyword_var = tk.StringVar()
        tk.Entry(r2, textvariable=self.keyword_var, bg="#3c3c3c", fg="#eee", insertbackground="#eee", width=20).pack(side=tk.LEFT, padx=4)
        tk.Label(r2, text="Categoria:", bg="#2b2b2b", fg="#ccc").pack(side=tk.LEFT, padx=(8, 0))
        self.cat_var = tk.StringVar(value="examenes")
        cat_menu = ttk.Combobox(r2, textvariable=self.cat_var, values=[""] + CATEGORY_VALUES, width=12, state="readonly")
        cat_menu.pack(side=tk.LEFT, padx=4)

        r3 = tk.Frame(mid, bg="#2b2b2b")
        r3.pack(fill=tk.X, padx=4, pady=(0, 4))
        tk.Label(r3, text="Max paginas:", bg="#2b2b2b", fg="#ccc").pack(side=tk.LEFT)
        self.max_pages_var = tk.IntVar(value=3)
        tk.Spinbox(r3, from_=1, to=50, textvariable=self.max_pages_var, width=5, bg="#3c3c3c", fg="#eee").pack(side=tk.LEFT, padx=4)
        tk.Button(r3, text="🔍 BUSCAR", command=self._search_thread, bg="#555", fg="#eee", font=("TkDefaultFont", 11, "bold")).pack(side=tk.LEFT, padx=8)
        self.search_status = tk.Label(r3, text="", bg="#2b2b2b", fg="#aaa")
        self.search_status.pack(side=tk.LEFT, padx=4)

        # === RESULTS: Treeview ===
        self.tree = ttk.Treeview(self.root, columns=("name", "cat", "dl", "pages"), show="headings", height=14)
        self.tree.heading("name", text="Nombre")
        self.tree.heading("cat", text="Cat")
        self.tree.heading("dl", text="Descargas")
        self.tree.heading("pages", text="Pags")
        self.tree.column("name", width=480)
        self.tree.column("cat", width=80, anchor="center")
        self.tree.column("dl", width=70, anchor="center")
        self.tree.column("pages", width=50, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 0))
        self.tree.bind("<Double-1>", self._on_double_click)

        # === BOTTOM: Acciones ===
        bot = tk.Frame(self.root, bg="#2b2b2b")
        bot.pack(fill=tk.X, padx=8, pady=8)
        tk.Button(bot, text="⬇ Descargar seleccionado", command=self._download_selected, bg="#555", fg="#eee").pack(side=tk.LEFT, padx=2)
        tk.Button(bot, text="⬇ Descargar TODOS los resultados", command=self._download_all, bg="#555", fg="#eee").pack(side=tk.LEFT, padx=2)
        tk.Button(bot, text="📋 Copiar enlaces al portapapeles", command=self._copy_links, bg="#444", fg="#eee").pack(side=tk.LEFT, padx=2)
        tk.Button(bot, text="Abrir en navegador", command=self._open_browser, bg="#444", fg="#eee").pack(side=tk.LEFT, padx=2)
        self.dl_status = tk.Label(bot, text="", bg="#2b2b2b", fg="#aaa")
        self.dl_status.pack(side=tk.LEFT, padx=8)

    # ── ACTIONS ─────────────────────────────────────────

    def _load_cookie_file(self):
        path = filedialog.askopenfilename(title="Selecciona archivo de cookies", filetypes=[("Text/JSON", "*.txt *.json"), ("All", "*.*")])
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace").strip()
            self.cookie_var.set(text)
            self.config["auth"]["cookie_file"] = path
            self.config["auth"]["cookie_header"] = ""
            self._save_cookie_config()
            messagebox.showinfo("OK", f"Cookies cargadas de {path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _save_cookie_config(self):
        self.config["auth"]["cookie_header"] = self.cookie_var.get()
        save_config(self.config)

    def _try_connect(self):
        try:
            auth = self.config.get("auth") or {}
            self.client = WuolahClient(
                base_url=self.config.get("base_url", "https://wuolah.com"),
                api_base_url=self.config.get("api_base_url", "https://api.wuolah.com"),
                auth_cfg=auth,
                crawl_cfg=self.config.get("crawl") or {},
            )
            self.auth_label.config(text="OK", fg="#0f0")
        except Exception as e:
            self.client = None
            self.auth_label.config(text=f"ERR: {e}", fg="#f00")

    def _test_auth_thread(self):
        self._save_cookie_config()
        self._try_connect()
        threading.Thread(target=self._test_auth, daemon=True).start()

    def _test_auth(self):
        if not self.client:
            self.root.after(0, lambda: self.auth_label.config(text="No client", fg="#f00"))
            return
        try:
            me = self.client.get_me()
            name = me.get("name") or me.get("email") or me.get("id") or "OK"
            self.root.after(0, lambda: self.auth_label.config(text=f"✅ {name}", fg="#0f0"))
        except Exception as e:
            err = str(e)[:80]
            self.root.after(0, lambda: self.auth_label.config(text=f"❌ {err}", fg="#f00"))

    def _search_thread(self):
        self._save_cookie_config()
        self._try_connect()
        self.search_status.config(text="Buscando...")
        threading.Thread(target=self._do_search, daemon=True).start()

    def _do_search(self):
        if not self.client:
            self.root.after(0, lambda: self.search_status.config(text="❌ Sin conexion"))
            return
        self._results = []
        try:
            community = self.community_var.get().strip() or None
            subject = self.subject_var.get().strip() or None
            keyword = self.keyword_var.get().strip() or None
            category = self.cat_var.get().strip() or None
            univ = self.univ_var.get().strip() or None

            # Strategy: crawl university + community if given
            if community:
                # extract community_id from NEXT_DATA
                from .next_data import parse_next_data_from_html
                html = self.client.get_text(f"/{community}", api=False)
                nd = parse_next_data_from_html(html)
                queries = nd.get("props", {}).get("pageProps", {}).get("dehydratedState", {}).get("queries", [])
                community_id = None
                for q in queries:
                    key = q.get("queryKey") or []
                    if key and isinstance(key[0], dict) and key[0].get("id") == "communities":
                        data = q.get("state", {}).get("data")
                        if isinstance(data, dict):
                            community_id = int(data.get("id"))
                            break

                if not community_id:
                    self.root.after(0, lambda: self.search_status.config(text=f"❌ Comunidad no encontrada: {community}"))
                    return

                # Search with API subject search
                import requests
                search_url = f"{self.client.api_base_url}/v2/search/subjects"
                search_params = {"keyword": subject or keyword or "", "filter[communityId]": community_id}
                if keyword:
                    search_params["keyword"] = keyword
                resp = requests.get(search_url, params=search_params, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}, timeout=30)
                data = resp.json()
                items = data.get("items") or data.get("data") or []

                if not items and subject:
                    self.root.after(0, lambda: self.search_status.config(text=f"❌ Asignatura no encontrada: {subject}"))
                    return

                for subj in items[:1]:  # first match
                    sid = subj.get("subjectId") or (subj.get("subject") or {}).get("id") or subj.get("id")
                    params: dict[str, Any] = {
                        "sort": "-numDownloads",
                        "pagination[page]": 0,
                        "pagination[pageSize]": 100,
                        "pagination[withCount]": "false",
                        "populate[0]": "community",
                        "filter[communityId]": community_id,
                        "filter[subjectId]": sid,
                    }
                    if category:
                        params["filter[category]"] = category

                    docs = self.client.get_json("/v2/documents", params=params)
                    items = docs.get("data", []) if isinstance(docs, dict) else []
                    for d in items:
                        if keyword and keyword.lower() not in (str(d.get("name", "")) + " " + str(d.get("slug", ""))).lower():
                            continue
                        self._results.append({
                            "id": d.get("id"),
                            "name": d.get("name", "?"),
                            "category": d.get("category", ""),
                            "downloads": d.get("numDownloads", 0),
                            "pages": d.get("numPages", 0),
                            "slug": d.get("slug", ""),
                            "subject_slug": subj.get("slug") or (subj.get("subject") or {}).get("slug", ""),
                            "url": f"https://wuolah.com/apuntes/{subj.get('slug') or (subj.get('subject') or {}).get('slug', '')}/{d.get('slug', '')}" if d.get("slug") else None,
                        })
            else:
                self.root.after(0, lambda: self.search_status.config(text="Pon al menos comunidad (slug)"))
                return

        except Exception as e:
            self.root.after(0, lambda: self.search_status.config(text=f"❌ Error: {str(e)[:100]}"))
            return

        self.root.after(0, self._refresh_tree)

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for r in self._results:
            self.tree.insert("", tk.END, values=(r["name"][:90], r.get("category", ""), r.get("downloads", 0), r.get("pages", 0)))
        self.search_status.config(text=f"✅ {len(self._results)} resultados")

    def _on_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        if idx < len(self._results):
            url = self._results[idx].get("url")
            if url:
                self.root.clipboard_clear()
                self.root.clipboard_append(url)
                self.dl_status.config(text=f"📋 Copiado: {url}")

    def _copy_links(self):
        links = [r.get("url", "") for r in self._results if r.get("url")]
        if links:
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(links))
            self.dl_status.config(text=f"📋 {len(links)} enlaces copiados")
        else:
            self.dl_status.config(text="Nada que copiar")

    def _open_browser(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        if idx < len(self._results):
            url = self._results[idx].get("url")
            if url:
                import webbrowser
                webbrowser.open(url)

    def _download_selected(self):
        sel = self.tree.selection()
        if not sel:
            self.dl_status.config(text="Selecciona algo primero")
            return
        idx = self.tree.index(sel[0])
        if idx < len(self._results):
            self._download_docs([self._results[idx]])

    def _download_all(self):
        if not self._results:
            self.dl_status.config(text="Busca algo primero")
            return
        self._download_docs(self._results)

    def _download_docs(self, docs: list[dict[str, Any]]):
        outdir = filedialog.askdirectory(title="Carpeta de descarga")
        if not outdir:
            return
        self.dl_status.config(text=f"⬇ Bajando {len(docs)} archivos...")
        threading.Thread(target=self._do_download, args=(docs, outdir), daemon=True).start()

    def _do_download(self, docs: list[dict[str, Any]], outdir: str):
        if not self.client:
            self.root.after(0, lambda: self.dl_status.config(text="❌ Sin conexion"))
            return
        ok, fail = 0, 0
        import uuid
        machine_id = str(uuid.uuid4())
        for d in docs:
            try:
                resp = self.client.request_official_download(int(d["id"]), machine_id=machine_id)
                url = str((resp or {}).get("url") or "")
                if not url:
                    fail += 1
                    continue
                name = d.get("name", str(d["id"]))
                safe = "".join(c for c in name if c.isalnum() or c in " .-_()").strip()
                if not safe:
                    safe = str(d["id"])
                path = Path(outdir) / f"{safe}.pdf"
                self.client.download_url_to_file(url, path)
                ok += 1
            except Exception:
                fail += 1
        self.root.after(0, lambda: self.dl_status.config(text=f"✅ {ok} OK  ❌ {fail} fallos"))

    def run(self):
        self.root.mainloop()


def main():
    gui = WuolahGUI()
    gui.run()


if __name__ == "__main__":
    main()
