# Taller 2 - Un asistente de EcoMarket que consulta sus documentos

**Universidad Icesi · IA Generativa · Taller práctico 2**

## Grupo de trabajo

- Cristian Camilo Quebrada
- Rubén Darío Sabogal
- Edwin Pérez L.

## Qué resuelve este proyecto

En el [Taller 1](https://github.com/poppetmaster/iagen-taller1) construimos un prototipo que
consultaba pedidos y orientaba devoluciones. Ahora añadimos un sistema RAG: antes de responder
una pregunta documental, el asistente busca fragmentos pertinentes en una base de conocimiento
y los entrega al modelo como evidencia. La respuesta muestra las fuentes que el modelo cita.

Conservamos Qwen2.5 7B mediante Ollama, los doce pedidos de prueba y las reglas de devolución.
Los pedidos se consultan por su identificador exacto. Las decisiones sobre una devolución
siguen dependiendo de las reglas, no de lo que el modelo considere conveniente.

Todos los datos son ficticios. Los documentos se derivan del Taller 1: no se agregaron precios,
existencias, atributos de productos ni políticas comerciales. RAG puede ayudar a responder
con respaldo, pero no garantiza que el modelo interprete bien la evidencia.

## Dónde está la respuesta a cada fase

| Fase y criterio de la rúbrica | Documento y evidencia |
|---|---|
| Componentes| [FASE_1.md](FASE_1.md): embeddings, base vectorial, español, costos y alternativas |
| Base de conocimiento| [FASE_2.md](FASE_2.md): PDF, CSV, JSON, procedencia, fragmentación e indexación |
| Integración| [FASE_3.md](FASE_3.md): recorrido del código, ejecución, comparación y limitaciones |

Cómo ejecutarlo

Las versiones de
dependencias están fijadas en `requirements.txt`; otras plataformas necesitan su propia verificación.

Desde esta carpeta, crea un entorno e instala las dependencias:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

En Windows, activa el entorno con `.venv\Scripts\Activate.ps1` en PowerShell.
Instala [Ollama](https://ollama.com/download), abre la aplicación y descarga el generador:

```bash
ollama pull qwen2.5:7b
python app.py index
python app.py retrieve "¿Cuál es el plazo de devolución?"
python app.py ask "¿Cuál es el plazo de devolución y desde cuándo se cuenta?"
```

La primera indexación descarga el embedding multilingüe desde Hugging Face. Después, con los
modelos disponibles en caché y Ollama funcionando, las consultas se ejecutan localmente.
No se necesitan claves de OpenAI, Tavily, Pinecone ni LangSmith. No actives trazas externas
si no deseas enviar datos a esos servicios.

Más ejemplos:

```bash
python app.py ask "¿En qué categoría está el cuaderno reciclado?"
python app.py ask "¿Cuánto cuesta la botella reutilizable?"
python app.py ask "¿Dónde está mi pedido EM-1003?"
python app.py ask "¿Puedo devolver EM-1010?" --as-of 2026-09-24 --used no --good-condition si --packaging-ok si
python app.py ask "Cancela mi pedido EM-1003"
```

La fecha del ejemplo se mantiene fija para reproducir el caso original; no representa la fecha
actual. Las condiciones de devolución se suministran mediante opciones, no se extraen de texto libre.
Si falta la fecha o una condición necesaria, el sistema pide información.

Para inspeccionar la evidencia completa y comparar una pregunta sin recuperación:

```bash
python app.py ask "¿Cuál es el plazo de devolución?" --json
python app.py ask "¿Cuál es el plazo de devolución?" --without-rag --json
```

Se conservan los comandos del Taller 1:

```bash
python app.py order EM-1003
python app.py --mode rules return EM-1010 --as-of 2026-09-24 --used no --good-condition si --packaging-ok si
```

Estos comandos llaman al flujo histórico, que mantiene sus limitaciones. El nuevo flujo híbrido
se usa con `ask`. El modo `rules` no genera texto con IA y siempre se identifica como tal.

## Cómo verificar la entrega

```bash
python -m unittest discover -s tests -v
python evaluate.py --calibrate
python evaluate.py --retrieval-only
python evaluate.py
```

La última orden compara doce preguntas con y sin RAG: 24 inferencias reales. Puede tardar varios
minutos. Guarda consultas, prompts, respuestas, fuentes, tiempos, identidad del modelo y controles
automáticos en una carpeta nueva de `evaluacion/runs/`.

Consulta [la verificación local](evaluacion/VERIFICACION_LOCAL.md) y
[los resultados y sus límites](evaluacion/RESULTADOS.md). Los resultados históricos del Taller 1
no se presentan como ejecuciones de este taller.

## Estructura para el nuevo repositorio

```text
FASE_1.md / FASE_2.md / FASE_3.md    Respuestas a las tres fases
app.py                             Entrada al sistema RAG
app_legacy.py                      Aplicación original conservada
evaluate.py                        Comparación con y sin recuperación
evaluate_legacy.py                 Evaluador de prompts del Taller 1
ecomarket/domain.py                Pedidos y reglas del Taller 1
ecomarket/embeddings.py             Embeddings E5
ecomarket/retrieval.py              Documentos, fragmentos e índice
ecomarket/rag.py                    Flujo híbrido y controles de respuesta
data/                              Fuentes canónicas y casos de evaluación
knowledge/                         PDF, CSV, JSON y registro de procedencia
scripts/prepare_knowledge.py        Regeneración de los documentos derivados
tests/                             Pruebas de regresión e integración
evaluacion/                        Evidencia y conclusiones
config.json                        Configuración del experimento
```

La base `.index/`, el entorno `.venv/` y los pesos de modelos no se publican. Cada persona
construye su índice con `python app.py index`. Si cambias las fuentes, regenera los documentos
con `python scripts/prepare_knowledge.py` y vuelve a indexar. El programa detecta varias
inconsistencias y evita consultar un índice desactualizado.

Los pasos para subir la carpeta a un repositorio nuevo están en [PUBLICACION.md](PUBLICACION.md).

## Límites que deben acompañar la demostración

El asistente reconoce algunas intenciones mediante reglas acotadas; no entiende universalmente
cualquier solicitud. No autentica clientes, no consulta existencias actuales y no ejecuta
cancelaciones, pagos, reembolsos, tickets ni transferencias a personas. Los enlaces de seguimiento
son simulados. Una cita válida demuestra que el fragmento existe, no que sustente cada frase.

Antes de un uso real se necesitarían fuentes autorizadas y actualizadas, control de acceso,
integración transaccional y una evaluación representativa. Esta entrega demuestra el recorrido
RAG solicitado y documenta sus resultados; no acredita capacidad empresarial.

Las referencias oficiales y su relación con las decisiones se encuentran en [FUENTES.md](FUENTES.md).
