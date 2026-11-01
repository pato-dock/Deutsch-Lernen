# Deutsch Lernen

Aplicación local para aprender alemán de A1 a B2, pensada para una hispanohablante que vive junto a Basilea. Funciona en macOS como una app de escritorio: un servidor Python local que sirve una interfaz web en `http://127.0.0.1:8765`.

- **Sin dependencias**: solo la biblioteca estándar de Python 3.10+ en el servidor y JavaScript sin frameworks en la interfaz.
- **Datos locales**: SQLite en `~/Library/Application Support/DeutschLernen/datos`.
- **Coste cero**: todo el contenido está escrito y revisado de antemano. La voz natural usa el plan gratuito de Azure Speech (opcional); si no hay clave, usa las voces de macOS.

## Ejecutar en desarrollo

```bash
cd app
DEUTSCH_DATA=./.datos-dev python3 server.py --port 8799
```

Se abre el navegador solo. `--no-browser` lo evita; `--auto-exit` apaga el servidor tras 20 minutos sin la app abierta (lo usa el lanzador de macOS).

`DEUTSCH_DATA` indica dónde guardar la base de datos. Úsalo siempre en desarrollo para no tocar tu progreso real.

## Pruebas

```bash
python3 tests/test_content.py   # valida el contenido y genera todos los tipos de ejercicio
python3 tests/test_api.py       # arranca el servidor y simula una sesión completa
```

## Estructura

```
app/
  server.py        Servidor HTTP (stdlib), API, lógica de sesiones, progreso, copias, Azure TTS
  content.py       Carga el contenido y genera los ejercicios
  fsrs.py          Repetición espaciada FSRS-5 (implementación propia, sin dependencias)
  store.py         SQLite: tarjetas, respuestas, sesiones, notas, ajustes
  content/         Todo el contenido didáctico en JSON (ver formato abajo)
  static/          Interfaz: index.html, app.js, app.css, icon.png, fonts/
Instalar.command   Instalador de macOS: Python con uv, copia el programa, crea la .app y la añade al Dock
Desinstalar.command
tests/
```

## Contenido (`app/content/`)

| Archivo | Qué contiene |
|---|---|
| `vocab.json` | 20 temas, 431 palabras: `[palabra, artículo, plural, español, ejemplo DE, ejemplo ES, emoji, suizo, nota]` |
| `verbs.json` | 60 verbos con presente, Präteritum, Partizip, auxiliar, imperativo y Konjunktiv II |
| `grammar.json` | 21 fichas (HTML) y 100 ejercicios `[tema, nivel, pregunta con ___, opciones, correcta, explicación]` |
| `grammar_tr.json` | Frase completa y traducción de cada ejercicio de gramática, **en el mismo orden** que `grammar.json` |
| `phrases.json` | Expresiones por grupos |
| `swiss.json` | Suizo-alemán: `[suizo, estándar, español, dialecto/helvetismo, nota]` |
| `plan.json` | Ruta A1→B2 (unidades que agrupan temas y fichas) y test de nivel |

Los ids de los elementos se derivan del contenido (`v:<tema>:<slug>`, `g:<tema>:<índice>`, …). Cambiar una palabra o reordenar ejercicios cambia su id y el progreso guardado de ese elemento se pierde, así que es mejor añadir que reordenar.

## Decisiones de diseño

- **Pensada para TDAH**: un ejercicio por pantalla, bloques cortos con pausa, feedback inmediato, temporizador visible y racha flexible.
- **Color con un solo significado**: azul = der, rojo = die, verde = das, violeta = plural, amarillo = foco/acierto, rojo editorial = acción. Los errores se marcan en azul grisáceo, nunca en rojo.
- **Paleta editorial clara**: blanco hueso, negro y rojo editorial, primarios con degradados suaves. Los tokens están al principio de `app.css`, y la capa editorial que los aplica, al final.
- **Cada ejercicio lleva una frase completa con su traducción** (`sentence`) que se muestra al corregir.

## Hoja de ruta

- [x] Fase 1: sesión diaria, vocabulario, gramática, verbos, apuntes y PDF, progreso, voz Azure
- [ ] Fase 2: pronunciación (grabación, Whisper local, pares mínimos, shadowing, diálogos de rol)
- [ ] Fase 3: escritura y comprensión lectora
- [ ] Fase 4: comprensión auditiva y más suizo-alemán
