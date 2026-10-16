# Verificación local de la entrega


## Comprobaciones realizadas

- Las 68 pruebas automatizadas terminaron correctamente: 40 heredadas y 28 del nuevo recorrido.
  Registro: [pruebas_unitarias.txt](pruebas_unitarias.txt).
- Los 15 casos anteriores coincidieron con sus resultados esperados al ejecutar el motor de
  reglas. Esto no es generación: [regresion_reglas.json](regresion_reglas.json).
- Los tres tipos documentales se generaron y contrastaron con los datos originales. El PDF
  de doce páginas se renderizó y revisó visualmente; no se observaron cortes ni superposiciones.
- Se construyó un índice real con E5 y Chroma: 36 fragmentos, vectores normalizados y revisión
  fija del embedding. No se utilizaron vectores simulados para la comparación generativa.
- Se completaron seis consultas de calibración y 24 inferencias de comparación. Los resultados,
  incluidos los fallos semánticos, están en [RESULTADOS.md](RESULTADOS.md).
- Se verificaron rutas híbridas adicionales y se conservaron tanto las salidas iniciales
  retenidas como las comprobaciones posteriores. Los controles de aclaración y acciones no
  disponibles se identifican como respuestas del programa, sin inferencia.
- La comprobación de dependencias no encontró incompatibilidades declaradas. La lista completa
  instalada está en [entorno_comprobado.txt](entorno_comprobado.txt).

El entorno comprobado usa Python 3.14.6 y macOS arm64. Las pruebas de GitHub Actions no requieren descargar E5 ni
tener Ollama porque utilizan dobles identificados para los contratos; esa automatización no
constituye evaluación real del modelo y queda pendiente de ejecución remota.

## Alcance de las evidencias

Los archivos de resultados conservan identidad del modelo, parámetros y respuestas. Son
evidencia técnica consistente con el recorrido del programa, no certificación de un tercero.
Las huellas del paquete permiten detectar cambios posteriores respecto del manifiesto, pero
no certifican el origen de una ejecución ni la corrección de una respuesta.

El repositorio anterior permanece intacto. La entrega local no crea ni publica un repositorio
remoto y no incluye pesos, entorno virtual ni base vectorial. Los documentos, fuentes y código
permiten reconstruir el índice.
