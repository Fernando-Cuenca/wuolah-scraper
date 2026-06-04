# Wuolah Scraper

Scraper de metadata y descarga de documentos de [Wuolah](https://wuolah.com).

**ATENCIÓN — LEE ESTO ANTES DE USARLO:**

## ⚠️ Requisito de cuenta

Este scraper **solo funciona con cuenta Wuolah PRO/Premium** (sin anuncios).

**Si tienes cuenta normal (gratuita)**:
- Wuolah te mete publicidad y un flujo de "ver anuncio para descargar"
- La API de descarga (`/v2/download`) requiere token `noAdsToken` que solo se obtiene tras ver anuncios
- Este scraper **no salta la publicidad ni evade el paywall**
- Si lo intentas con cuenta normal: la API devuelve `fileUrl` vacío o error

**Si tienes cuenta PRO/Premium**:
- La descarga oficial funciona directamente sin anuncios
- Solo necesitas tus cookies/tokens de sesión

No uses esto para bajar contenido que no has pagado o para el que no tienes derecho de acceso.

## 📜 Disclaimer legal

Este proyecto es una herramienta de **automatización para tu propia cuenta**. No:

- 🚫 Evade paywalls ni salta publicidad
- 🚫 Comparte credenciales ni cookies
- 🚫 Distribuye documentos de Wuolah
- 🚫 Bypassea sistemas de autenticación
- 🚫 Hace scraping masivo no autorizado

Solo automatiza lo que YA puedes hacer manualmente desde el navegador con tu cuenta. El usuario es responsable del uso que haga de esta herramienta y debe respetar los términos de servicio de Wuolah.

## 🧠 ¿Qué hace?

1. **Indexa metadata**: universidades, centros, grados, asignaturas, documentos
2. **Busca documentos**: por universidad, comunidad, asignatura, keyword, categoría
3. **Descarga oficial**: usando `/v2/download` autenticado con tu sesión
4. **Limpia PDFs**: elimina enlaces de tracking/anuncios de PDFs ya descargados
5. **GUI guarra**: interfaz Tkinter para no tocar terminal (ver abajo)

## 📦 Instalación

```bash
git clone https://github.com/Fernando-Cuenca/wuolah-scraper.git
cd wuolah-scraper
pip install -e .

# Para la GUI (necesita tk)
pip install -e ".[gui]"

# Para limpiar PDFs (opcional)
pip install -e ".[pdf]"

# Todo junto
pip install -e ".[all]"
```

## 🔑 Configuración

Copia el ejemplo:

```bash
cp config.example.json config.json
```

Edita `config.json` y mete tus credenciales de UNA de estas formas:

### Opción A: cookie_header (recomendado)
Pega la cookie entera de sesión (la sacas de DevTools > Application > Cookies > copiar valor de `token` y `refreshToken`):

```json
"auth": {
  "cookie_header": "token=eyJhbG...; refreshToken=eyJhbG..."
}
```

### Opción B: cookie_file
Exporta las cookies desde el navegador con una extensión (cookies.txt formato Netscape):

```json
"auth": {
  "cookie_file": "/ruta/a/tus/cookies.txt"
}
```

### Opción C: tokens directos
```json
"auth": {
  "access_token": "eyJhbG...",
  "refresh_token": "eyJhbG..."
}
```

## 🖥️ CLI — comandos

```bash
# Probar auth
wuolah-scraper auth-check --config config.json

# Listar universidades
wuolah-scraper universities --config config.json

# Crawl de una universidad entera
wuolah-scraper crawl --config config.json --university-slug universidad-carlos-iii-de-madrid

# Crawl filtrado (comunidad + asignatura + categoria)
wuolah-scraper crawl --config config.json \
  --community-slug uc-3-m-escuela-politecnica-superior-campus-leganes/grado-ingenieria-tecnologias-industriales \
  --subject-slug fisica-ii \
  --category examenes \
  --max-pages 3

# Descargar documento por ID
wuolah-scraper official-download --config config.json --document-id 12345

# Limpiar anuncios de PDF
wuolah-scraper clean-pdf --aggressive archivo.pdf
```

## 🖼️ GUI guarra

```bash
wuolah-gui
```

Abre una ventana Tkinter (sin dependencias extra, viene con Python):

1. **Pega tu cookie** arriba
2. Mete universidad/comunidad/asignatura
3. Pulsa **BUSCAR**
4. Doble click en resultado → copia enlace
5. Selecciona + **Descargar** → te pide carpeta

La GUI es fea a propósito. Funciona. Si quieres bonito, usa CLI.

## 🗃️ ¿Qué es SQLite?

El scraper guarda todo lo que indexa en `outputs/wuolah.sqlite`. Es solo un índice local. No se sube al repo (está en `.gitignore`).

## 📂 Estructura

```
wuolah-scraper/
├── pyproject.toml
├── config.example.json
├── README.md
├── LICENSE
├── .gitignore
└── src/wuolah_scraper/
    ├── __init__.py
    ├── __main__.py
    ├── cli.py          # CLI argparse
    ├── gui.py          # GUI Tkinter (modo guarro)
    ├── client.py       # HTTP client con auth
    ├── auth.py         # Manejo de cookies/tokens JWT
    ├── crawler.py      # Lógica de crawl
    ├── next_data.py    # Parser __NEXT_DATA__ de Next.js
    ├── storage.py      # SQLite
    └── pdf_cleaner.py  # Limpieza de PDFs
```

## ⚡ Limitaciones

- La API de Wuolah a veces ignora `filter[category]` → el scraper filtra client-side también
- La descarga oficial requiere cuenta PRO; con cuenta free no funciona
- Sin cookies/tokens válidos no se puede autenticar
- El login email/password no está implementado (solo cookies/tokens)

## 🔒 Seguridad

- `config.json` y `*.cookies.txt` están en `.gitignore`
- No subas NUNCA tus cookies/tokens a GitHub
- Si filtraste algo por accidente, rota los tokens en Wuolah inmediatamente

## 📝 Licencia

MIT. Lo que hagas con esto es tu responsabilidad.
