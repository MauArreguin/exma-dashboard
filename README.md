# EXMA Dashboard VSL

Dashboard en tiempo real de campañas VSL de EXMA Speakers.

## Cómo funciona

1. **GitHub Actions** corre automáticamente cada hora
2. El script `generate_dashboard.py` llama a la **Meta Ads API** con el token guardado como secret
3. Genera `index.html` con datos frescos
4. Lo publica automáticamente en **GitHub Pages**

## URL del dashboard

Una vez configurado, el dashboard vive en:
```
https://mauarreguin.github.io/exma-dashboard/
```

## Setup inicial (ya hecho)

- [x] Secret `META_ACCESS_TOKEN` guardado en GitHub Secrets
- [x] GitHub Pages habilitado en rama `gh-pages`
- [x] GitHub Actions workflow configurado

## Para correr manualmente

Ve a la pestaña **Actions** en GitHub → selecciona "Actualizar Dashboard VSL" → clic en "Run workflow".

## Datos disponibles

- Campañas VSL activas: 02 MEX · 03 MEX · 04 USA
- Histórico: últimos 90 días (se actualiza automáticamente)
- Objetivo CPL: $42 USD

## Archivos

| Archivo | Descripción |
|---|---|
| `generate_dashboard.py` | Script que jala datos de Meta y genera el HTML |
| `dashboard_vsl_live.html` | Template base del dashboard |
| `index.html` | Dashboard generado (se sobreescribe cada hora) |
| `.github/workflows/update-dashboard.yml` | Configuración de GitHub Actions |
