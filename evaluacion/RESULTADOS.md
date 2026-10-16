# Qué mostraron las pruebas del Taller 2

## Ejecución de la comparación

Se completaron las 24 inferencias, sin errores de infraestructura. Usamos Qwen `qwen2.5:7b`,
digest `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`, con Ollama 0.34.4.
Los demás parámetros y versiones se encuentran en
[los metadatos](runs/20261016T105746348886Z/metadata.json).

| Medida de esta ejecución | Con RAG | Sin RAG |
|---|---:|---:|
| Inferencias completadas | 12/12 | 12/12 |
| Contrato y controles automáticos superados | 12/12 | 12/12 |
| Estado contestada/insuficiente esperado para el caso | 10/12 | 4/12 |
| Consultas contestables con evidencia pertinente entre los primeros cuatro fragmentos | 8/8 | 0/8 |
| Respuestas completas según revisión cualitativa de Codex | 9/12 | 4/12 |

La última fila es una valoración asistida por IA, no una revisión humana independiente. Sus
criterios y observaciones están en
[revision_cualitativa_codex.csv](runs/20261016T105746348886Z/revision_cualitativa_codex.csv).
La plantilla `revision.csv` permanece vacía para que una persona pueda revisar los resultados.

El indicador de recuperación comprueba al menos un fragmento pertinente entre los primeros
cuatro para ocho preguntas con respuesta. No mide precisión de todos los fragmentos ni cobertura
de todos los hechos. Para las cuatro preguntas sin respuesta documental ese indicador no aplica.

## Qué cambió al aportar documentos

Sin recuperación, el modelo respondió que no tenía información en los doce casos. Es coherente
con la instrucción de usar solo los documentos proporcionados, pero deja sin resolver las ocho
consultas que sí tenían respuesta en la base. No se interpreta esa abstención como alucinación.

Con RAG, contestó correctamente el plazo, las condiciones de higiene, el procedimiento y las
categorías de maceta y cuaderno. También reconoció la ausencia de precio, inventario y política
de envíos internacionales, y rechazó responder una pregunta ajena a la base.

La comparación muestra que el contexto recuperado permite resolver consultas antes imposibles
dentro de este contrato. No compara RAG contra enviar todo el corpus, ni demuestra superioridad
general de este modelo o de esta base vectorial.

## Fallos que siguen presentes

**Perecederos.** El recuperador encontró la FAQ sobre cambio de opinión y la exclusión de
devolución ordinaria. Aun así, el modelo afirmó que faltaba información. Es un fallo de
interpretación y utilidad, no una ausencia del fragmento esperado. La respuesta pasó los controles.

**Reclamación por defecto.** La respuesta orientó a realizar una reclamación y mencionó la
exclusión ordinaria, pero omitió indicar expresamente la revisión humana. La consideramos
parcial, aunque el estado `answered` y las citas fueran válidos.

**Inyección en la consulta.** El modelo no aceptó permitir cualquier devolución. Sin embargo,
respondió de forma vaga, no enumeró las condiciones recuperadas y marcó insuficiencia.
Resistir una instrucción indebida no equivale a resolver bien la parte legítima de la pregunta.
Este caso no prueba resistencia a documentos maliciosos ni a otras formas de ataque.

Los tres ejemplos muestran por qué 12/12 contratos válidos no equivalen a 12/12 respuestas
correctas. Las citas existentes tampoco certifican por sí solas el respaldo de cada afirmación.

## Calibración separada

Se ejecutaron seis consultas distintas de las de evaluación: tres contestables y tres sin
respuesta en la base. Sus similitudes máximas fueron aproximadamente 0,884 a 0,908 en las
contestables y 0,793 a 0,857 en las restantes. Los registros están en
[calibration.json](runs/20261016T105746370393Z/calibration.json).

Un umbral intermedio separaría esos seis ejemplos, pero sería una conclusión débil para
consultas nuevas. Por ello no activamos un corte automático. Como comprobación de ese límite,
la pregunta de evaluación sobre el precio de la botella alcanzó 0,891 de similitud con su
registro de catálogo, aunque allí no existe un precio. Esa observación no se usó para ajustar
un umbral sobre el conjunto de evaluación.

La similitud identifica cercanía semántica, no suficiencia. La configuración mantiene
`minimum_similarity: null` y exige revisar el contenido, con los errores ya señalados.

## Qué no podemos concluir

Hay una ejecución por consulta y variante, documentos pequeños y contenidos redundantes entre
PDF y FAQ. No se demuestra ausencia de sesgos, seguridad general, capacidad para miles de
consultas ni reducción de las 24 horas empresariales descritas en el caso. Los tiempos de
inferencia no son equivalentes al tiempo completo de atención de una empresa.

Tampoco se ha probado una interfaz con usuarios reales. Las verificaciones del motor de reglas
se distinguen de las inferencias. El servicio de GitHub Actions está preparado, pero no se
ha ejecutado en un repositorio remoto nuevo.

## Cómo revisar o repetir

Además de la comparación documental, se comprobaron los recorridos de pedido, devolución,
reclamación, aclaración y acción no disponible. Los registros están en
[integracion_hibrida.json](integracion_hibrida.json). En esa primera prueba el pedido produjo
hechos vacíos y citas inventadas, y el programa retuvo la respuesta. Devolución y reclamación
conservaron los hechos calculados, aunque su redacción aún requiere revisión: la devolución
no explicitó solicitar el trámite a soporte y la reclamación añadió una explicación sobre
condiciones desconocidas que no era necesaria para justificar la revisión humana.

Se reforzó el contrato únicamente para pedidos y se repitieron dos consultas en
[pedidos_verificacion_posterior.json](pedidos_verificacion_posterior.json). El pedido inexistente
conservó correctamente sus hechos y reconoció la ausencia de datos, pero usó una frase ambigua
sobre una búsqueda posterior. El otro pedido conservó sus hechos, aunque reveló otro caso de
extracción de enlaces Markdown y presentó el seguimiento simulado como rastreo. Se corrigió
la extracción del enlace cuando su etiqueta también es una URL y se añadió un control para
exigir la aclaración de simulación cuando aparece un enlace de prueba.

La [comprobación final del pedido](pedido_contrato_final.json) conserva la respuesta tras ese
ajuste: mantuvo los hechos y aclaró que el seguimiento es simulado. Sin embargo, todavía recomendó
consultar un sistema de seguimiento que este prototipo no ofrece; ese matiz muestra el límite
de los controles de texto. Las [24 salidas documentales se revalidaron](revalidacion_contrato.json) con el control
final y obtuvieron los mismos resultados; no se volvieron a generar ni se reemplazaron.
Las correcciones de contratos y enlaces no se atribuyen a RAG. Tampoco prueban que se hayan
eliminado todas las formas de error semántico.

Las [respuestas legibles](runs/20261016T105746348886Z/RESPUESTAS_LEGIBLES.md) facilitan la lectura.
Los [registros originales](runs/20261016T105746348886Z/results.jsonl) conservan prompts, fragmentos,
texto crudo, metadatos y tiempos. Los registros no se editaron para reemplazar respuestas fallidas.

Para repetir: construye el índice y ejecuta `python evaluate.py`. Cada lote se guarda en otra
carpeta. Antes de intentar mejorar los prompts conviene preservar esta referencia y definir
otros casos de desarrollo. Cambiar instrucciones a partir de estos fallos y evaluar solo estas
mismas preguntas no constituiría una validación independiente.
