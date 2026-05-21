#!/usr/bin/env python3
"""
GEO Content Agent for OneTrack
Generates SEO/GEO-optimized blog articles and submits them to Google Search Console.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import anthropic
from google.oauth2 import service_account
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


def generate_fallback_topic(client: anthropic.Anthropic) -> dict:
    """Ask Claude to invent a topic when topics.json is exhausted."""
    print("[topics] topics.json vacío — generando tema con Claude...")
    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": (
                "Eres el equipo de contenido de OneTrack, una app para coaches de fitness en México y LATAM.\n"
                "Genera un tema para un artículo de blog basado en búsquedas conversacionales reales "
                "que haría un coach profesional en Google, ChatGPT o Perplexity.\n"
                "El tema debe ser específico, útil y en español (es-MX).\n\n"
                "Responde ÚNICAMENTE con JSON válido, sin texto adicional:\n"
                '{"slug": "slug-unico-con-guiones", "titulo": "Título del artículo"}'
            )
        }]
    )
    return json.loads(msg.content[0].text.strip())


def generate_article_html(client: anthropic.Anthropic, topic: dict) -> str:
    """Call Claude to produce a full standalone HTML article."""
    date = today()
    slug = topic["slug"]
    title = topic["titulo"]
    url = f"{SITE_URL}/blog/{slug}.html"

    prompt = f"""Eres el equipo de contenido de OneTrack.
OneTrack es una app iOS para coaches de fitness de alto rendimiento, hecha en Ciudad de México, usada en LATAM y España.
Funciones principales: creación de rutinas, planes de dieta, check-ins de clientes, seguimiento de progreso.
URL: https://www.onetrack.lat

Escribe un artículo de blog completo en HTML sobre:
  Título: {title}
  Slug: {slug}
  URL canónica: {url}
  Fecha: {date}

────────────────────────────────────────────
REQUISITOS DE CONTENIDO
────────────────────────────────────────────
• Mínimo 800 palabras de contenido real, práctico y útil
• Tono: directo, profesional, para coaches reales — sin marketing genérico
• Idioma: español (es-MX)
• Menciona OneTrack de forma natural donde aporte valor (no repetitivo)
• Incluye datos, ejemplos concretos o pasos accionables
• Sección FAQ al final con 4 preguntas relevantes al tema

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
    """Notify Google Indexing API of the new article URL."""
    creds_json = os.environ.get("GOOGLE_OAUTH_CREDENTIALS")
    if not creds_json:
        print("[indexing] GOOGLE_OAUTH_CREDENTIALS no definido — omitiendo")
        return

    credentials = service_account.Credentials.from_service_account_info(
        json.loads(creds_json),
        scopes=["https://www.googleapis.com/auth/indexing"]
    )
    service = build("indexing", "v3", credentials=credentials)
    url = f"{SITE_URL}/blog/{slug}.html"
    resp = service.urlNotifications().publish(
        body={"url": url, "type": "URL_UPDATED"}
    ).execute()
    print(f"[indexing] respuesta Google: {resp}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY no definida")

    client = anthropic.Anthropic(api_key=api_key)

    # 1. Get topic
    topic = load_topic()
    if topic is None:
        topic = generate_fallback_topic(client)

    print(f"[agent] Generando artículo: {topic['titulo']}")

    # 2. Generate HTML
    html = generate_article_html(client, topic)

    # 3. Save article
    save_article(topic["slug"], html)

    # 4. Update sitemap
    update_sitemap(topic["slug"])

    # 5. Request Google indexing (non-fatal if it fails)
    try:
        request_indexing(topic["slug"])
    except Exception as e:
        print(f"[indexing] error (no crítico): {e}")

    # Write slug to file so the GitHub Action can use it in the commit message
    (REPO_ROOT / ".geo_last_slug").write_text(topic["slug"], encoding="utf-8")

    print("[agent] ✓ Completado exitosamente")


if __name__ == "__main__":
    main()
