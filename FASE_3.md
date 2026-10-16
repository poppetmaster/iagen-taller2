# Fase 3 - Cómo funciona el código y qué comprobamos

## Qué conservamos y qué cambia

El [Taller 1](https://github.com/poppetmaster/iagen-taller1) ya conectaba datos, reglas,
prompts y Qwen local. Conservamos `domain.py`, el cliente original, los prompts y el validador
históricos para mantener una referencia. Su aplicación y evaluador se llaman ahora
`app_legacy.py` y `evaluate_legacy.py`. Las pruebas heredadas ajustan esos nombres de importación.

El flujo nuevo está en `app.py`, `embeddings.py`, `retrieval.py` y `rag.py`. Usa LangChain para
combinar prompt y modelo, e incorpora la recuperación vectorial que antes no existía.
Los comandos antiguos siguen disponibles, pero la entrada a la ampliación es `ask`.

## Recorrido de una pregunta documental

Con `python app.py ask "¿Cuál es el plazo de devolución?"` ocurre lo siguiente:

1. `app.py` lee la configuración y `route_question()` reconoce una consulta documental.
2. `E5Embeddings` carga la revisión fija del modelo. Su método `embed_query()` añade `query: `.
3. `Retriever` comprueba que documentos, configuración e índice coincidan.
4. Chroma devuelve cuatro fragmentos por similitud, junto con sus ubicaciones.
5. `PROMPT` separa instrucciones, hechos, documentos y consulta. Pide una respuesta JSON.
6. La cadena `PROMPT | ChatOllama` envía ese contexto a Qwen2.5 7B.
7. `validate_generated()` comprueba estructura, hechos, IDs de citas, enlaces y algunos límites.
8. La consola presenta la respuesta y las fuentes citadas, o retiene una salida que falle.

No usamos ajuste fino. El conocimiento se aporta al responder y puede actualizarse reconstruyendo
los documentos y el índice. Un error de Ollama se muestra como error: no se reemplaza por una
plantilla que aparente ser generación real.

## Pedidos, devoluciones y consultas que no se pueden ejecutar

Un identificador como EM-1003 activa la consulta exacta de pedido. El nuevo prompt recibe sus
hechos, sin incluir los otros once pedidos. Esto reduce el contexto innecesario, aunque no
sustituye controles de acceso.

La primera comprobación real del nuevo recorrido de pedidos produjo hechos vacíos y citas
inventadas. El validador retuvo esa salida. Después añadimos a esa ruta un ejemplo de contrato
con los hechos exactos y citas vacías. Este refuerzo se aplica solo a pedidos: no altera el
prompt de la comparación documental. La evidencia inicial se conserva junto a la verificación
posterior, sin presentar ese cambio de prompt como una mejora debida a RAG.

Si la pregunta solicita devolver un pedido concreto, se requieren fecha y condiciones mediante
opciones. `evaluate_return()` calcula la decisión. La recuperación añade explicación documental;
el modelo no puede cambiar los hechos calculados. Por ejemplo:

```bash
python app.py ask "¿Puedo devolver EM-1010?" --as-of 2026-09-24 --used no --good-condition si --packaging-ok si
```

Los datos desconocidos se conservan como desconocidos. La fecha explícita permite repetir los
casos sin que el resultado cambie por usar la fecha del equipo.

El enrutador es una lista acotada de patrones en español. Pide un identificador cuando detecta
una consulta de pedido sin él, limita la demostración a un pedido por vez y reconoce algunas
acciones no disponibles. Es conservador: ciertas frases informativas con verbos como «abrir»
pueden recibir una explicación del límite. Tampoco descompone solicitudes compuestas. Estos
son límites conocidos; no presentamos la clasificación como comprensión general del lenguaje.

## Contrato y controles

La salida nueva contiene `status`, `message`, `citations` y `facts`. Los hechos deben coincidir
con los calculados por el programa. Una respuesta documental marcada como contestada necesita
al menos una cita de los fragmentos enviados. Si no hay hechos ni documentos, debe reconocer
información insuficiente. El esquema difiere del contrato histórico de dos campos.

El validador nuevo maneja enlaces Markdown sin el falso positivo observado en el Taller 1 y
rechaza algunas afirmaciones explícitas de acciones no disponibles. Esto es una mejora del
control, separada de RAG. Sus patrones no cubren todas las formas de expresar una acción.
Cuando el mensaje incluye un enlace de seguimiento de prueba, exige una aclaración de que es
simulado o ficticio. Esto no garantiza que toda la frase sea semánticamente coherente.
Los controles tampoco prueban que una cita respalde el mensaje o que no existan contradicciones.
Hay una prueba que documenta esa limitación: una respuesta falsa puede tener formato válido.

## Comparación para observar el efecto de RAG

El experimento principal ejecuta las doce consultas de `data/rag_cases.json` en dos variantes:

- **Con RAG:** el modelo recibe los fragmentos recuperados.
- **Sin RAG:** recibe el mismo prompt y los mismos parámetros, con documentos vacíos.

Los hechos documentales están vacíos en ambas variantes. La instrucción limita la respuesta
a evidencia proporcionada, por lo que la abstención sin documentos es un resultado esperado.
Esta comparación demuestra el efecto de aportar contexto en ese marco; no compara todos los
usos posibles de un modelo sin RAG ni prueba que la búsqueda supere a enviar todo el corpus.

Se alterna el orden de variantes. Se conserva temperatura 0,2, semilla 42, contexto 8192 y máximo
1000 tokens generados. La semilla no garantiza identidad entre equipos. El cambio de endpoint
de generación del cliente histórico a la integración de chat de LangChain también impide
atribuir diferencias con las cifras antiguas exclusivamente a RAG.

El evaluador guarda identidad y digest de Qwen, versión de Ollama, bibliotecas, revisión de E5,
consultas, prompts, fragmentos, respuesta cruda, tiempos y controles. Los errores se registran
por separado. Un resultado esperado por palabras clave es solo una comprobación parcial:
no reemplaza la lectura semántica de la respuesta.

## Evidencias y revisión

Las pruebas automatizadas incluyen las 40 del proyecto anterior y nuevos casos de carga,
persistencia, índice desactualizado, enrutamiento, citas y contratos. Los dobles de prueba se
identifican como tales; no prueban precisión del embedding ni calidad de Qwen.

Los quince casos anteriores se comprueban además mediante reglas. Las ejecuciones reales del
nuevo generador se conservan en `evaluacion/runs/`. El archivo `revision.csv` queda disponible
para una persona; cualquier revisión realizada por Codex se identifica aparte como cualitativa
asistida por IA, sin presentarla como evaluación humana independiente.

El informe [evaluacion/RESULTADOS.md](evaluacion/RESULTADOS.md) explica los aciertos y fallos
observados. No convertimos una ejecución pequeña en una promesa de disponibilidad, equidad,
ausencia de alucinaciones ni reducción del tiempo empresarial de atención.

## Limitaciones y supuestos

Usamos fuentes sintéticas pequeñas, dos de ellas expresadas en varios formatos. La descarga
inicial requiere internet. Después se necesita memoria suficiente para Qwen y el embedding;
tener el archivo del modelo no garantiza latencia adecuada. No se hizo una prueba de carga.

No se implementan autenticación, búsqueda transaccional real, inventario actualizado,
transferencias, creación de tickets ni reembolsos. El programa recomienda pasos sin ejecutarlos.
Si la recuperación omite una excepción, el generador puede responder mal. Si recupera una fuente
pertinente, todavía puede interpretarla de forma incorrecta. Esos riesgos forman parte del
resultado que se evalúa, no desaparecen por usar una base vectorial.
