#!/usr/bin/env python3
"""
GEO Content Agent for OneTrack
Generates SEO/GEO-optimized blog articles and submits them to Google Search Console.
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

import anthropic
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ── Config ────────────────────────────────────────────────────────────────────

REPO_ROOT   = Path(__file__).parent.parent
TOPICS_FILE = REPO_ROOT / "agent" / "topics.json"
SITEMAP     = REPO_ROOT / "sitemap.xml"
BLOG_DIR    = REPO_ROOT / "blog"
SITE_URL    = "https://www.onetrack.lat"
TZ_MEXICO   = timezone(timedelta(hours=-6))

# ── Helpers ───────────────────────────────────────────────────────────────────

def today() -> str:
    return datetime.now(TZ_MEXICO).strftime("%Y-%m-%d")


def load_topic() -> dict:
    """Pop the first topic from topics.json. Returns None if list is empty."""
    topics = json.loads(TOPICS_FILE.read_text(encoding="utf-8"))
    if not topics:
        return None
    topic = topics.pop(0)
    TOPICS_FILE.write_text(
        json.dumps(topics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[topics] {len(topics)} temas restantes después de consumir '{topic['slug']}'")
    return topic


def refill_topics(client: anthropic.Anthropic) -> dict:
    """Ask Claude to generate 20 new topics, save them to topics.json, and return the first one."""
    print("[topics] topics.json vacío — generando 20 temas nuevos con Claude...")

    # Collect slugs already published to avoid duplicates
    published = [f.stem for f in (REPO_ROOT / "blog").glob("*.html") if f.stem != "index"]

    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": (
                "Eres el equipo de contenido de OneTrack, una plataforma iOS para coaches y nutriólogos en México y LATAM.\n\n"
                "Features: rutinas, planes de dieta con macros, análisis de macros con IA, InBody AI, "
                "check-ins semanales, plantillas reutilizables, dashboard de adherencia, widget de rutina.\n"
                "Planes: Free (3 clientes), Starter $9.99, Growth $19.99, Unlimited $49.99.\n\n"
                "Genera exactamente 20 temas para artículos de blog basados en búsquedas conversacionales "
                "reales que haría un coach o nutriólogo profesional en Google, ChatGPT o Perplexity.\n\n"
                "Criterios:\n"
                "- Específicos y accionables (no genéricos)\n"
                "- Variados: casos de éxito, guías prácticas, comparativas, errores comunes, herramientas\n"
                "- Relevantes para México y LATAM\n"
                "- En español (es-MX)\n"
                f"- NO repetir estos slugs ya publicados: {published}\n\n"
                "Responde ÚNICAMENTE con un array JSON válido de 20 objetos, sin texto adicional:\n"
                '[{"slug": "slug-con-guiones", "titulo": "Título del artículo"}, ...]'
            )
        }]
    )

    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
    topics = json.loads(raw.strip())
    first = topics.pop(0)

    # Save remaining 19 to topics.json for future runs
    TOPICS_FILE.write_text(
        json.dumps(topics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[topics] {len(topics)} temas guardados en topics.json para próximas ejecuciones")
    return first


def generate_article_html(client: anthropic.Anthropic, topic: dict) -> str:
    """Call Claude to produce a full standalone HTML article."""
    date = today()
    slug = topic["slug"]
    title = topic["titulo"]
    url = f"{SITE_URL}/blog/{slug}.html"

    prompt = f"""Eres el equipo de contenido de OneTrack.

OneTrack es una plataforma iOS para coaches y nutriólogos en México y LATAM.
Versión actual: 1.2

Features principales:
- Rutinas personalizadas por día con ejercicios, series y repeticiones
- Planes de dieta con macros (kcal, proteína, carbos, grasa) editables manual o con IA
- Análisis de macros con IA: un tap rellena la nutrición automáticamente (plan Unlimited, 2 análisis/día)
- InBody AI: sube el PDF del InBody y la IA extrae peso, músculo, grasa y BMI + recomendación personalizada para el coach (plan Unlimited)
- Check-ins semanales con fotos y gráfica de progreso de peso
- Plantillas de rutina y dieta reutilizables entre clientes
- Dashboard de adherencia — el coach ve qué clientes siguen su plan
- Widget de rutina — el cliente ve sus ejercicios del día desde la pantalla de inicio
- Código de invitación único para vincular coach y cliente

Planes:
- Free: hasta 3 clientes, sin IA
- Starter: $9.99/mes, hasta 8 clientes
- Growth: $19.99/mes, hasta 13 clientes
- Unlimited: $49.99/mes, clientes ilimitados + todas las features de IA

URL: https://www.onetrack.lat
App Store: https://apps.apple.com/mx/app/onetrack/id6761740866

Escribe un artículo de blog completo en HTML sobre:
  Título: {title}
  Slug: {slug}
  URL canónica: {url}
  Fecha: {date}

────────────────────────────────────────────
REQUISITOS DE CONTENIDO
────────────────────────────────────────────
• Mínimo 800 palabras de contenido real, práctico y útil
• Idioma: español (es-MX)
• Menciona OneTrack de forma natural donde aporte valor (no repetitivo)
• Si algo no funciona, dilo. No todo es positivo.
• Sección FAQ al final con 4 preguntas relevantes al tema

────────────────────────────────────────────
TONO DE ESCRITURA — OBLIGATORIO
────────────────────────────────────────────
• Escribe como alguien mandando mensajes de WhatsApp, no como revista de negocios
• Frases cortas. Párrafos cortos. Sin adornos.
• PROHIBIDO usar: "es fundamental", "cabe destacar", "en conclusión", "sin lugar a dudas",
  "es importante", "hay que tener en cuenta", "en el mundo del fitness", "como coach profesional"
• PROHIBIDO: citas dramatizadas tipo "recuerda Javier" o "confiesa María"
• PROHIBIDO: frases motivacionales de cierre ("el éxito está en tus manos", etc.)
• USA en cambio: "la neta", "te lo digo de frente", "esto sí funciona", "aquí el punto",
  "en la práctica", "lo que nadie dice", "funciona así"
• El lector ya sabe de fitness — no le expliques qué es una rutina, un macro o un check-in
• Máximo 2 ideas por párrafo
• Cada sección termina con una conclusión accionable, no teórica
• NÚMEROS CREÍBLES: un coach que pasó de 8 a 22 clientes, que ahorra 2-3 horas/semana,
  que cobra $1,500-3,000 MXN por cliente. NUNCA escribas $180,000 MXN/mes ni 100 clientes

────────────────────────────────────────────
ESTRUCTURA HTML REQUERIDA (documento completo y standalone)
────────────────────────────────────────────

<!DOCTYPE html>
<html lang="es-MX">
<head>
  <!-- charset, viewport -->
  <!-- title: "{title} | Blog OneTrack" -->
  <!-- meta description: 150-160 caracteres -->
  <!-- canonical: {url} -->
  <!-- Open Graph: og:title, og:description, og:url, og:type=article, og:site_name=OneTrack -->
  <!-- Twitter Card: summary_large_image -->

  <!-- JSON-LD Article schema -->
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "{title}",
    "author": {{"@type": "Organization", "name": "OneTrack", "url": "{SITE_URL}"}},
    "publisher": {{
      "@type": "Organization",
      "name": "OneTrack",
      "url": "{SITE_URL}",
      "logo": {{"@type": "ImageObject", "url": "{SITE_URL}/logo.png"}}
    }},
    "datePublished": "{date}",
    "dateModified": "{date}",
    "url": "{url}",
    "inLanguage": "es-MX",
    "mainEntityOfPage": {{"@type": "WebPage", "@id": "{url}"}}
  }}
  </script>

  <!-- JSON-LD FAQPage schema (mismas 4 preguntas que la sección FAQ del body) -->
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [/* array de Question+Answer */]
  }}
  </script>

  <!-- Google Fonts: Inter -->
  <!-- CSS con dark mode -->
</head>
<body>
  <!-- nav: logo OneTrack (link /) + "Descargar app" (link /) -->
  <main>
    <article>
      <!-- h1 con el título -->
      <!-- fecha publicación -->
      <!-- contenido completo mínimo 800 palabras con h2/h3/p/ul -->
      <!-- sección FAQ con las mismas 4 preguntas -->
    </article>
  </main>
  <!-- footer con link a {SITE_URL} y año -->
</body>
</html>

────────────────────────────────────────────
CSS (incluir en <style> dentro del <head>)
────────────────────────────────────────────
* {{ margin:0; padding:0; box-sizing:border-box }}
body {{ background:#070B16; color:#E8EAF0; font-family:'Inter',sans-serif; line-height:1.7 }}
nav {{ background:rgba(7,11,22,0.92); backdrop-filter:blur(12px); position:sticky; top:0;
       z-index:100; padding:16px 24px; display:flex; justify-content:space-between;
       align-items:center; border-bottom:1px solid #1a2340 }}
nav a.logo {{ color:#fff; font-weight:700; font-size:1.2rem; text-decoration:none }}
nav a.cta {{ background:#5B91F5; color:#fff; padding:8px 18px; border-radius:8px;
             text-decoration:none; font-size:.9rem; font-weight:600 }}
main {{ max-width:800px; margin:0 auto; padding:48px 24px 80px }}
h1 {{ font-size:2rem; font-weight:800; color:#fff; line-height:1.2; margin-bottom:12px }}
h2 {{ font-size:1.4rem; font-weight:700; color:#fff; margin:40px 0 14px }}
h3 {{ font-size:1.1rem; font-weight:600; color:#c8d0e0; margin:28px 0 10px }}
p  {{ margin-bottom:18px; color:#c8d0e0 }}
ul,ol {{ margin:0 0 18px 24px; color:#c8d0e0 }}
li {{ margin-bottom:8px }}
a  {{ color:#5B91F5; text-decoration:none }}
a:hover {{ text-decoration:underline }}
.meta {{ color:#6b7a99; font-size:.9rem; margin-bottom:40px }}
.faq {{ margin-top:56px }}
.faq-item {{ background:#0d1424; border:1px solid #1a2340; border-radius:12px;
             padding:24px; margin-bottom:16px }}
.faq-item h3 {{ color:#fff; margin:0 0 10px; font-size:1rem }}
.faq-item p {{ margin:0; font-size:.95rem }}
footer {{ border-top:1px solid #1a2340; padding:32px 24px; text-align:center;
          color:#6b7a99; font-size:.875rem }}
footer a {{ color:#5B91F5 }}

────────────────────────────────────────────
Genera SOLO el HTML completo. Sin explicaciones, sin markdown, sin bloques de código.
El output debe empezar con <!DOCTYPE html> directamente.
"""

    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}]
    )
    html = msg.content[0].text.strip()
    # Strip accidental markdown fences if Claude adds them
    if html.startswith("```"):
        html = html.split("\n", 1)[1]
        if html.endswith("```"):
            html = html.rsplit("```", 1)[0]
    return html.strip()


def save_article(slug: str, html: str) -> Path:
    BLOG_DIR.mkdir(exist_ok=True)
    path = BLOG_DIR / f"{slug}.html"
    path.write_text(html, encoding="utf-8")
    print(f"[article] guardado en {path.relative_to(REPO_ROOT)}")
    return path


def update_sitemap(slug: str):
    url = f"{SITE_URL}/blog/{slug}.html"
    entry = (
        f"  <url>\n"
        f"    <loc>{url}</loc>\n"
        f"    <lastmod>{today()}</lastmod>\n"
        f"    <changefreq>monthly</changefreq>\n"
        f"    <priority>0.8</priority>\n"
        f"  </url>\n"
    )
    content = SITEMAP.read_text(encoding="utf-8")
    if url in content:
        print(f"[sitemap] {url} ya existe, no se duplica")
        return
    updated = content.replace("</urlset>", entry + "</urlset>")
    SITEMAP.write_text(updated, encoding="utf-8")
    print(f"[sitemap] agregado {url}")


def request_indexing(slug: str):
    """Notify Google Indexing API of the new article URL using desktop OAuth credentials."""
    creds_json = os.environ.get("GOOGLE_OAUTH_CREDENTIALS")
    if not creds_json:
        print("[indexing] GOOGLE_OAUTH_CREDENTIALS no definido — omitiendo")
        return

    data = json.loads(creds_json)

    # Support both the raw credential dict and the file format produced by
    # google-auth-oauthlib (which nests everything under an "installed" key).
    if "installed" in data:
        data = data["installed"]

    credentials = Credentials(
        token=None,
        refresh_token=data["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        scopes=["https://www.googleapis.com/auth/indexing"],
    )
    service = build("indexing", "v3", credentials=credentials)
    url = f"{SITE_URL}/blog/{slug}.html"
    resp = service.urlNotifications().publish(
        body={"url": url, "type": "URL_UPDATED"}
    ).execute()
    print(f"[indexing] respuesta Google: {resp}")


def sync_app_store_rating():
    """Fetch live ratingCount from iTunes API and update index.html schema."""
    app_id = "6761740866"
    url = f"https://itunes.apple.com/mx/lookup?id={app_id}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        if not data.get("resultCount"):
            print("[rating] App no encontrada en iTunes API")
            return
        result = data["results"][0]
        count = str(result.get("userRatingCount", 0))
        rating = str(result.get("averageUserRating", 5))
    except Exception as e:
        print(f"[rating] error al consultar iTunes API (no crítico): {e}")
        return

    index_path = REPO_ROOT / "index.html"
    content = index_path.read_text(encoding="utf-8")

    updated = re.sub(
        r'(\\"ratingCount\\":\s*\\")[0-9]+(\\")',
        rf'\g<1>{count}\g<2>',
        content
    )
    updated = re.sub(
        r'(\\"ratingValue\\":\s*\\")[0-9.]+(\\")',
        rf'\g<1>{rating}\g<2>',
        updated
    )

    if updated == content:
        print(f"[rating] sin cambios (ratingCount ya es {count})")
        return

    index_path.write_text(updated, encoding="utf-8")
    print(f"[rating] actualizado → ratingCount={count}, ratingValue={rating}")


def rebuild_blog_index():
    """Regenerate blog/index.html listing all articles sorted newest first."""
    articles = []
    for f in sorted(BLOG_DIR.glob("*.html")):
        if f.stem == "index":
            continue
        text = f.read_text(encoding="utf-8")
        title_m = re.search(r'<title>([^<]+)</title>', text)
        desc_m  = re.search(r'<meta name="description" content="([^"]+)"', text)
        date_m  = re.search(r'"datePublished":\s*"([^"]+)"', text)
        h1_m    = re.search(r'<h1[^>]*>([^<]+)</h1>', text)

        title = (title_m.group(1).split("|")[0].strip() if title_m else
                 h1_m.group(1).strip() if h1_m else f.stem)
        desc  = desc_m.group(1) if desc_m else ""
        date  = date_m.group(1) if date_m else "2026-05-19"
        articles.append({"slug": f.name, "title": title, "desc": desc, "date": date})

    articles.sort(key=lambda a: a["date"], reverse=True)

    cards = ""
    for a in articles:
        cards += f"""
    <a href="/blog/{a['slug']}" class="card">
      <div class="card-date">{a['date']}</div>
      <h2>{a['title']}</h2>
      <p>{a['desc']}</p>
      <span class="read-more">Leer artículo →</span>
    </a>"""

    year = datetime.now(TZ_MEXICO).year
    html = f"""<!DOCTYPE html>
<html lang="es-MX">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Blog para coaches de fitness | OneTrack</title>
  <meta name="description" content="Guías, casos de estudio y recursos prácticos para coaches y nutriólogos en México y LATAM. Publicado por el equipo de OneTrack.">
  <link rel="canonical" href="{SITE_URL}/blog/index.html">
  <meta property="og:title" content="Blog para coaches de fitness | OneTrack">
  <meta property="og:description" content="Guías, casos de estudio y recursos prácticos para coaches y nutriólogos en México y LATAM.">
  <meta property="og:url" content="{SITE_URL}/blog/index.html">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="OneTrack">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{background:#070B16;color:#E8EAF0;font-family:'Inter',sans-serif;line-height:1.6;min-height:100vh}}
    nav{{background:rgba(7,11,22,0.92);backdrop-filter:blur(12px);position:sticky;top:0;z-index:100;
         padding:16px 24px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1a2340}}
    nav a.logo{{color:#fff;font-weight:800;font-size:1.2rem;text-decoration:none}}
    nav a.cta{{background:#5B91F5;color:#fff;padding:8px 18px;border-radius:8px;text-decoration:none;font-size:.875rem;font-weight:600}}
    header{{max-width:860px;margin:0 auto;padding:64px 24px 40px;border-bottom:1px solid #1a2340}}
    header h1{{font-size:2.2rem;font-weight:800;color:#fff;margin-bottom:12px}}
    header p{{color:#8a94a8;font-size:1rem}}
    main{{max-width:860px;margin:0 auto;padding:48px 24px 80px}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:20px}}
    .card{{background:#0d1424;border:1px solid #1a2340;border-radius:14px;padding:28px;
           text-decoration:none;color:inherit;transition:border-color .2s,transform .2s;
           display:flex;flex-direction:column;gap:10px}}
    .card:hover{{border-color:#5B91F5;transform:translateY(-2px)}}
    .card-date{{color:#5B91F5;font-size:.8rem;font-weight:600;letter-spacing:.04em}}
    .card h2{{font-size:1.05rem;font-weight:700;color:#fff;line-height:1.3}}
    .card p{{color:#8a94a8;font-size:.9rem;flex:1}}
    .read-more{{color:#5B91F5;font-size:.875rem;font-weight:600;margin-top:4px}}
    footer{{border-top:1px solid #1a2340;padding:32px 24px;text-align:center;color:#6b7a99;font-size:.875rem}}
    footer a{{color:#5B91F5;text-decoration:none}}
  </style>
</head>
<body>
  <nav>
    <a href="/" class="logo">OneTrack</a>
    <a href="/" class="cta">Descargar app</a>
  </nav>
  <header>
    <h1>Blog para coaches de fitness</h1>
    <p>{len(articles)} artículos — guías, casos de estudio y recursos para coaches en México y LATAM.</p>
  </header>
  <main>
    <div class="grid">{cards}
    </div>
  </main>
  <footer>
    <a href="{SITE_URL}">← Volver a OneTrack</a>
    <p style="margin-top:8px">© {year} OneTrack. Todos los derechos reservados.</p>
  </footer>
</body>
</html>"""

    (BLOG_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"[blog-index] reconstruido con {len(articles)} artículos")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY no definida")

    client = anthropic.Anthropic(api_key=api_key)

    # 1. Get topic
    topic = load_topic()
    if topic is None:
        topic = refill_topics(client)

    print(f"[agent] Generando artículo: {topic['titulo']}")

    # 2. Generate HTML
    html = generate_article_html(client, topic)

    # 3. Save article
    save_article(topic["slug"], html)

    # 4. Update sitemap
    update_sitemap(topic["slug"])

    # 5. Rebuild blog/index.html with all articles
    rebuild_blog_index()

    # 6. Sync App Store rating count in index.html
    sync_app_store_rating()

    # 7. Request Google indexing (non-fatal if it fails)
    try:
        request_indexing(topic["slug"])
    except Exception as e:
        print(f"[indexing] error (no crítico): {e}")

    # Write slug to file so the GitHub Action can use it in the commit message
    (REPO_ROOT / ".geo_last_slug").write_text(topic["slug"], encoding="utf-8")

    print("[agent] ✓ Completado exitosamente")


if __name__ == "__main__":
    main()
