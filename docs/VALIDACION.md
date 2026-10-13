# Plan de pruebas y validación Moímetro

## Estado general

- **Pruebas de API automatizadas**: presentes en `tests/test_api.py` y workflow `.github/workflows/test.yml`.
- **Compilación automatizada ESP32**: workflow con PlatformIO; compilación no prueba cableado ni precisión.
- **Validación física de sensores**: **pendiente**.
- **Clasificación automática de triaje**: **deshabilitada y pendiente de protocolo/revisión**.
- **Seguridad para expedientes reales**: **no demostrada**.

## Matriz de pruebas por componente

| ID | Prueba | Evidencia esperada | Estado |
|---|---|---|---|
| QA-001 | Login válido/inválido | Pruebas automatizadas y resultado Actions | En seguimiento CI |
| QA-002 | Búsqueda y duplicado de cédula | Caso automatizado sin datos reales | En seguimiento CI |
| QA-003 | Consulta con identidad de paciente | Sesión ligada a `encounter_id` correcto | En seguimiento CI |
| QA-004 | SpO₂ falso enviado por ESP32 | API responde 422 | En seguimiento CI |
| QA-005 | Lectura sin dedo/valor inválido | Se rechaza y no acepta automáticamente | En seguimiento CI |
| QA-006 | Lectura pendiente y aceptación humana | Registro de `accepted_by` y estado | En seguimiento CI |
| QA-007 | Rol recepción intenta editar diagnóstico | API responde 403 | En seguimiento CI |
| QA-008 | Persistencia/copias SQLite | Backup coherente + prueba de restauración | Parcial: backup y verificación; restauración pendiente |
| QA-009 | API y frontend sin Internet | PC y ESP32 en router sin WAN | Pendiente prueba física |
| QA-010 | Recalibración DS18B20 | Comparación repetida con termómetro de referencia | Pendiente |
| QA-011 | BPM MAX30102 | Comparación repetida con referencia y movimiento | Pendiente |
| QA-012 | SpO₂ MAX30102 | Algoritmo real y evaluación contra referencia aceptada | Pendiente |
| QA-013 | Calidad de triaje | Protocolos clínicos aprobados, casos normales/urgentes y revisión profesional | Pendiente |
| QA-014 | Pérdida WiFi/reinicio/corte de energía | Sin pacientes mezclados ni lecturas antiguas aceptadas | Pendiente |
| QA-015 | Auditoría, permisos y privacidad clínica | Prueba de roles y revisión de amenazas | Parcial, no aprobada |
| QA-016 | Recuperación tras corrupción / reinstalación | Ensayo con respaldo externo, restauración y reporte | Pendiente |

## Registro de validación instrumental pendiente

Para cada sensor documentar: modelo/lote, conexión, ubicación/tiempo de estabilización, instrumento de referencia (marca y control), muestra de participantes autorizada o simulador, rango observado, número de muestras, desviaciones, repetibilidad, condiciones de exclusión y evidencia sin identificadores personales.

**Específicamente:**
- DHT11: condición ambiental, calibración básica y frecuencia mínima de lectura.
- DS18B20: no asumir temperatura clínica central por lectura superficial; demostrar método útil antes de anunciar «temperatura corporal».
- MAX30102 BPM: evaluar variabilidad por dedo, movimiento, perfusión y frecuencia de muestreo durante HTTP.
- MAX30102 SpO₂: no afirmar 98 % u otra saturación hasta algoritmo fiable y validación de extremo a extremo.

Los «rangos físicos» del backend son filtros de valores imposibles o corruptos, **no valores normales por edad**.

## Evidencia de finalización

Registrar la URL del commit, URL del workflow, fecha, versión del firmware, identificación del equipo, resultado esperado, resultado real y responsable. Un build exitoso **no** justifica cerrar QA-010 a QA-016.

### Formato de acta

```text
ID:
Fecha / versión:
Tipo de prueba:
Ambiente y equipo:
Datos sintéticos o mediciones:
Procedimiento:
Resultado esperado:
Resultado observado:
Error o incertidumbre:
Conclusión:
Responsable / revisión clínica (si aplica):
Enlace de evidencia:
```
