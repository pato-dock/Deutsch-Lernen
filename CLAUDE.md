# Instrucciones para Claude Code

Lee `README.md` primero: describe la arquitectura, el formato del contenido y las decisiones de diseño.

## Sobre la usuaria

- Patricia no es programadora. Explícale los cambios en español, en lenguaje no técnico, y dale instrucciones paso a paso para probarlos.
- Es diseñadora gráfica: cuida la tipografía, la jerarquía y el color. Respeta el sistema visual de `app/static/app.css`.
- Tiene TDAH: la interfaz debe seguir siendo de una tarea por pantalla, con feedback inmediato y sin ruido visual.
- Requisito fijo: **coste cero**. No añadas servicios de pago. Para IA o voz, usa opciones gratuitas o locales, o planes gratuitos.

## Reglas técnicas

- El servidor usa **solo la biblioteca estándar de Python**. No añadas dependencias sin un buen motivo y, si lo haces, actualiza `Instalar.command` para instalarlas con `uv`.
- La interfaz es JavaScript sin frameworks ni build. Todo vive en `app/static/app.js`.
- Desarrollo: `cd app && DEUTSCH_DATA=./.datos-dev python3 server.py --port 8799`. Nunca uses la carpeta de datos real de la usuaria.
- Después de cada cambio, ejecuta `python3 tests/test_content.py` y `python3 tests/test_api.py`.
- Contenido en alemán: tiene que ser gramaticalmente correcto y natural. Cada ejercicio necesita su frase completa con traducción al español.
- `grammar_tr.json` va en paralelo a `grammar.json["exercises"]`: si añades un ejercicio, añade su traducción en la misma posición.
- No reordenes elementos del contenido: los ids derivan de él y se perdería el progreso guardado.
- Para publicar una versión: sube `VERSION` en `app/server.py`; la usuaria actualiza ejecutando de nuevo `Instalar.command`.
