# Fase 2 - Qué documentos consulta el asistente

## La información disponible y su procedencia

El [Taller 1](https://github.com/poppetmaster/iagen-taller1) ya incluía dos fuentes de prueba:
doce pedidos en `data/orders.json` y una política en `data/return_policy.json`. Conservamos
esos archivos sin cambiar su contenido. La política es ficticia y no representa asesoría legal
ni condiciones comerciales reales de una empresa.

Para demostrar la carga de distintos documentos preparamos tres tipos, con tres formatos:

| Documento | Contenido y utilidad | Procedencia |
|---|---|---|
| `knowledge/politica_devoluciones.pdf` | Plazo, exclusiones, condiciones por categoría, reclamaciones y procedimiento | Representación del JSON canónico de política |
| `knowledge/catalogo.csv` | Nombre y categoría de los doce productos identificados en los pedidos | Proyección de campos existentes en `orders.json` |
| `knowledge/faq.json` | Preguntas frecuentes y respuestas sobre la política | Reformulación de las mismas secciones de la política |

No son tres fuentes independientes. El PDF y las preguntas frecuentes representan la misma
política. El catálogo mínimo no es inventario: no contiene cantidades disponibles, precios,
fichas de materiales ni certificaciones. El asistente debe reconocer esas ausencias.

La redundancia entre política y FAQ facilita la demostración, pero puede hacer que varios
resultados de búsqueda repitan una regla. Cuatro fragmentos recuperados no equivalen a cuatro
evidencias independientes. Esta base pequeña tampoco demuestra la calidad de recuperación
en una empresa con miles de documentos.

## Cómo conservamos la coherencia

El script `scripts/prepare_knowledge.py` genera los tres documentos a partir de las fuentes.
Conserva el plazo de 30 días calendario desde la entrega efectiva, con el día 30 incluido;
la exclusión ordinaria de perecederos; las condiciones de cada categoría; y la prioridad de
revisión humana para defectos, daños o producto equivocado.

El archivo `knowledge/provenance.json` registra el repositorio de origen y huellas SHA-256 de
fuentes, generador y documentos. Además, la comprobación `verify()` compara FAQ y catálogo
con los datos canónicos y extrae el PDF para comprobar sus secciones. Las huellas detectan
cambios, pero no certifican que una fuente empresarial sea verdadera.

El motor de devoluciones sigue leyendo el JSON canónico. El modelo recupera su representación
documental y explica el resultado. Si cambia la política, deben actualizarse documentos e índice
y repetirse los casos; editar solo un PDF no actualiza las reglas.

## Por qué no dividimos todo de la misma forma

| Estrategia | Ventaja | Problema en este caso |
|---|---|---|
| Tamaño fijo | Es simple y controla el tamaño | Puede separar una excepción de la regla a la que pertenece |
| Párrafos o secciones | Mantiene juntas ideas completas | Un párrafo muy largo puede exceder el límite del embedding |
| Recursiva | Intenta conservar párrafos y frases antes de usar cortes menores | Requiere elegir tamaño y solapamiento; no comprende la política |

Usamos las secciones del PDF como unidades iniciales y segmentación recursiva cuando hace
falta. El objetivo es de 360 tokens con solapamiento de 50, medidos por el tokenizador de E5.
La representación elegida tiene una sección por página para conservar su ubicación y hacer
fácil revisar la fuente. En esta versión las secciones son breves y no requieren subdivisión:
no afirmamos haber demostrado la ventaja del solapamiento con estos datos.

Cada producto del CSV se convierte en un documento completo. Cada pareja pregunta-respuesta
del JSON también permanece junta. Si una unidad estructurada supera 512 tokens, la carga falla
con un mensaje explícito; no se corta una fila ni se trunca silenciosamente.

El resultado comprobado de esta base es de 36 fragmentos: 12 páginas de política, 12 productos
y 12 preguntas frecuentes. El tamaño no se infla con documentos comerciales inventados.

## Del documento al índice

1. Verificamos la coherencia con las fuentes del Taller 1.
2. Extraemos las páginas del PDF con `pypdf` y leemos registros CSV y JSON.
3. Conservamos origen, página, fila o identificador de FAQ y tipo documental.
4. Aplicamos la estrategia de segmentación y asignamos un identificador estable al fragmento.
5. Añadimos el prefijo de E5 y generamos vectores normalizados de 384 dimensiones.
6. Guardamos texto, vector y metadatos en Chroma, con distancia coseno.
7. Escribimos un manifiesto con configuración, revisión del embedding y huella del contenido.

`python app.py index` repite la indexación sin duplicar los mismos IDs en la misma colección.
Cuando cambia el contenido o la configuración relevante se usa otra colección. Las colecciones
anteriores permanecen en la carpeta local; esta entrega no implementa limpieza automática.
Un cambio en las fuentes invalida la consulta del índice anterior hasta volver a indexar.

## Recuperación y suficiencia de la evidencia

La búsqueda devuelve los cuatro fragmentos más cercanos. Preservamos los puntajes para
inspeccionarlos, pero un documento sobre devoluciones puede parecer cercano a una pregunta
sobre una garantía que la base no describe.

Separamos seis consultas de calibración de las doce de evaluación. Sus resultados sirven
para estudiar los puntajes, no para asegurar un umbral universal. La configuración inicial
mantiene `minimum_similarity` en `null`: no descarta por un valor arbitrario. El modelo debe
reconocer cuándo la evidencia no contesta la pregunta, y la revisión comprueba ese comportamiento.
Los resultados observados y la razón para mantener este criterio aparecen en el informe.

En una ampliación real agregaríamos fuentes autorizadas, fechas de vigencia y una evaluación
mayor. Los pedidos privados continuarían fuera del índice documental compartido y requerirían
autenticación y autorización, que no están implementadas en esta demostración.
