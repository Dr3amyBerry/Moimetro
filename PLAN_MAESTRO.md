# MOÍMETRO — PLAN MAESTRO DEL PROYECTO

> **Documento rector:** desarrollo tecnológico y documentación técnica/académica del sistema Moímetro.  
> **Proyecto:** Consultorio Popular Tipo III Las Cayenas.  
> **Versión del plan:** 1.1 — 2026-10-12.  
> **Estado global:** prototipo de firmware y aplicación local incorporado en código; validación física, seguridad clínica y puesta en marcha aún pendientes.  
> **Fuente inicial:** definición funcional y sketch de ESP32 compartidos por el equipo del proyecto.  
> **Regla de evidencias:** una funcionalidad **no** se marca como completada sin código versionado, pruebas reproducibles y evidencia verificable.

---

## Estado de implementación — primera tanda v0.1

> **Evidencia:** archivos versionados en \`main\`, tests de integración en \`tests/test_api.py\`, y workflow [API tests](https://github.com/Dr3amyBerry/Moimetro/actions/workflows/test.yml). La aprobación de un build **no equivale** a validación clínica o de hardware. El diagnóstico de la sección 2 describe la línea base del repositorio **cuando se creó el plan**, no su estado posterior.

| Área | Evidencia implementada | Estado actual |
|---|---|---|
| Estructura y dependencias | \`requirements.txt\`, \`app/\`, \`firmware/platformio.ini\`, \`tests/\` | Código implementado; integración en evaluación |
| Pacientes por cédula | \`app/api/records.py\` y \`app/static/\` | Implementado y con pruebas API; pruebas operativas pendientes |
| Historial y consultas | \`patients\`, \`patient_histories\`, \`encounters\` | Código implementado; no validado con pacientes reales |
| Usuarios y roles | \`app/security.py\`, \`app/api/auth.py\`, \`app/manage.py\` | Roles básicos implementados; endurecimiento pendiente |
| Firmware de sensores | \`firmware/src/main.cpp\` | Compilación CI de versión inicial exitosa; pruebas físicas pendientes |
| API del ESP32 | \`app/api/sensors.py\` | Contrato implementado con validación de sesión y estado |
| Medición vinculada a consulta | \`capture_sessions\`, \`measurements\` | Implementación y pruebas automatizadas; integración física pendiente |
| Detección/SpO₂ | SpO₂ simulado eliminado; API rechaza SpO₂ del ESP32 | Mitigación del falso valor aplicada; SpO₂ real **no implementado** |
| Triaje | Ruta informa \`not_validated\` sin prioridad | **Bloqueado hasta revisión clínica** |
| Respaldo | \`python -m app.manage backup\` y \`verify-backup\` | Respaldo y verificación inicial; restauración cifrada/ensayada pendiente |
| Documentación paralela | \`docs/ARCHITECTURE.md\`, \`SEGURIDAD.md\`, \`VALIDACION.md\`, \`DOCUMENTACION_ROADMAP.md\` | Borradores y matrices preparados; informes definitivos pendientes |

### Interpretación de estados

- **Implementado en código:** existe ruta/archivo que expresa la función. No implica por sí sola corrección completa.
- **Probado automáticamente:** pruebas en CI con datos ficticios y hardware simulado o inexistente. No equivale a validación con sensores reales.
- **Pendiente de validación física:** no se ha medido exactitud, estabilidad, fiabilidad ante cortes ni seguridad del dispositivo en el consultorio.
- **Pendiente clínico:** SpO₂ y cualquier regla de urgencia/triaje **no pueden marcarse completos** sin protocolo y evaluación por profesionales.

### Próximos trabajos necesarios

1. Verificar el último commit en GitHub Actions (API, sintaxis JavaScript y firmware); corregir cualquier fallo antes de declarar la tanda probada.
2. Completar prueba **con sensores reales**: DS18B20, MAX30102, DHT11, interrupciones por HTTP y comparación contra instrumentos de referencia.
3. Integrar SpO₂ real únicamente tras validación técnica y clínica; no volver a usar saturaciones fijas.
4. Diseñar red segura con TLS y cifrado/respaldo de expedientes antes de trabajar con datos personales de salud.
5. Definir protocolo de triaje con personal sanitario y validar casos, sin automatizar decisiones médicas prematuramente.
6. Preparar restauración, migraciones, pruebas multipuesto, contingencias eléctricas y documentación académica final.

---

## 0. Cómo utilizar este documento

Este archivo es la **única fuente de verdad del alcance y del trabajo pendiente**. Se actualizará cuando haya decisiones, cambios de requisitos, resultados de pruebas o entregables completados.

**Estados admitidos**
- `PENDIENTE`: trabajo sin iniciar o sin evidencia.
- `EN CURSO`: trabajo comenzado con responsable y evidencia de avance.
- `BLOQUEADO`: falta una dependencia o decisión documentada.
- `EN REVISIÓN`: entregable preparado y pendiente de aceptación.
- `COMPLETADO`: criterios de aceptación cumplidos y enlazados a pruebas/commit/documento.
- `DESCARTADO`: fuera de alcance por decisión registrada, nunca por omisión.

**Prioridad:** `P0` crítica (seguridad/validez de datos), `P1` alta (MVP), `P2` mejora posterior.

**Reglas de coordinación**
1. Existen **dos grupos independientes y simultáneos**: **Desarrollo** y **Documentación**. Documentación **no** espera a que el desarrollo termine para investigar, estructurar ni redactar.
2. Los grupos comparten objetivo, vocabulario, requisitos, arquitectura de referencia y decisiones. Los cambios de alcance se registran aquí.
3. El Grupo de Documentación distingue siempre entre **objetivo**, **propuesta**, **implementado**, **probado** y **validado clínicamente**. Una descripción aspiracional no es una capacidad existente.
4. Las fases dividen el trabajo para su control: no exigen ejecutar todo secuencialmente. Se pueden paralelizar tareas sin dependencias.
5. No crear ramas adicionales por defecto: trabajar sobre `main` con commits identificables, salvo instrucción explícita diferente.
6. No subir claves WiFi, contraseñas, cédulas reales, datos de pacientes ni tokens. Utilizar configuraciones de ejemplo y datos ficticios para las pruebas.

## 1. Visión compartida

**Moímetro** es un sistema tecnológico local de apoyo a la atención primaria, compuesto por un dispositivo no invasivo de captura de signos vitales y un programa de gestión de historias clínicas. Está destinado a facilitar el registro de pacientes, el seguimiento de consultas, la captura estructurada de mediciones y la **priorización orientativa** del triaje, incluso sin acceso a Internet.

El personal del Consultorio Popular Tipo III Las Cayenas debe poder buscar un paciente por cédula, abrir su expediente o registrar uno nuevo; adquirir temperatura corporal, frecuencia cardíaca y saturación periférica de oxígeno cuando las mediciones sean técnicamente válidas; revisar alertas y prioridad sugerida; y guardar la consulta con fecha, profesional, evolución y tratamiento.

**Principio de seguridad clínica:** el programa **no diagnostica**, **no sustituye el criterio del personal sanitario** y **no debe presentar estimaciones inventadas como mediciones reales**. Los rangos, alertas y categorías de triaje requieren revisión y aprobación clínica antes de su uso con pacientes.

### 1.1 Objetivo general

Diseñar, implementar, documentar y validar un prototipo de Moímetro que funcione en una red local independiente de Internet, vincule mediciones de sensores con consultas clínicas e incorpore un expediente longitudinal consultable de forma segura.

### 1.2 Objetivos específicos

- Capturar signos vitales con identificación de sensor, unidad, calidad y tiempo de lectura.
- Gestionar pacientes mediante identificación única y control de duplicados.
- Crear, consultar y conservar expedientes y visitas ordenadas cronológicamente.
- Transferir lecturas del ESP32 al sistema clínico mediante una interfaz local documentada.
- Proponer niveles de prioridad/alertas a partir de protocolos aprobados por profesionales.
- Proteger información personal y clínica mediante permisos, auditoría y copias de seguridad.
- Producir documentación técnica, académica, de uso y de validación fiel a los resultados.

### 1.3 Alcance funcional previsto

| Área | Resultado esperado |
|---|---|
| Recepción | Búsqueda por cédula; registro de paciente nuevo; apertura de expediente. |
| Captura | Temperatura corporal, BPM y SpO₂ **medidos y validados**, o estado «no disponible». |
| Contexto ambiental | Temperatura/humedad DHT11 como datos auxiliares, **no signos vitales**. |
| Consulta | Registro de motivo, historia relevante, mediciones aceptadas, diagnóstico y tratamiento por personal autorizado. |
| Triaje | Alertas y categoría sugerida con motivo, límites y posibilidad de revisión humana. |
| Historial | Visitas cronológicas y acceso a antecedentes según rol. |
| Modo local | Operación en un equipo o red LAN sin servicio de Internet. |
| Continuidad | Respaldo, recuperación, trazabilidad y respuesta a cortes de energía/red. |

**Fuera del MVP:** diagnóstico autónomo, decisiones terapéuticas automáticas, integración con servicios remotos, hardware clínicamente certificado por simple declaración y precisión médica no demostrada.

---

## 2. Línea base y diagnóstico inicial

### 2.1 Evidencia disponible al crear el plan

El repositorio estaba **vacío** en el momento de crear este archivo. El único código de referencia es un sketch pegado en la conversación: `WiFi.h`, `WebServer.h`, `DHT.h`, `OneWire.h`, `DallasTemperature.h`, `MAX30105.h`, `heartRate.h`. **No se han inspeccionado pruebas de hardware, compilaciones ni archivos de firmware versionados en GitHub.**

Por tanto, lo siguiente describe **intenciones o lógica del prototipo compartido**, no funcionamiento comprobado.

| Componente | Situación del sketch compartido | Estado verificado |
|---|---|---|
| ESP32 + servidor HTTP | Página HTML y servidor local en puerto 80 | `NO VERIFICADO` |
| DHT11 / GPIO 18 | Funciones para temperatura y humedad ambiente | `NO VERIFICADO` |
| DS18B20 / GPIO 4 | Funciones para temperatura por OneWire | `NO VERIFICADO` |
| MAX30102 / I²C SDA 21, SCL 22 | Lectura IR y detección de latidos | `NO VERIFICADO` |
| BPM | Media de hasta cuatro intervalos/latidos | `NO VERIFICADO` |
| SpO₂ | **Valor fijo de 98 % dependiente de BPM: medición falsa** | `NO IMPLEMENTADO` |
| HTML de monitorización | Tarjetas que recargan cada 3 s | `NO VERIFICADO` |
| BD, expedientes, triaje, roles, auditoría | No aparecen en el código compartido | `PENDIENTE` |

### 2.2 Hallazgos técnicos que se deben corregir

1. **P0 / SpO₂ ficticio:** el sketch usa `beatAvg > 50 ? 98 : 0`, **no** calcula saturación de oxígeno. Reemplazar inmediatamente por `no disponible` y no mostrar porcentaje hasta medirlo y validarlo de verdad.
2. **P0 / detección de dedo:** umbral IR fijo sin calibración; pérdida de contacto no invalida correctamente todo el historial de BPM. Reiniciar promedios y distinguir ausencia de dedo, ruido y señal útil.
3. **P0 / datos obsoletos:** inicializar a cero y conservar valores tras errores puede hacer pasar lecturas antiguas por actuales. Usar estado `sin lectura/error/expirada`, timestamp y validez.
4. **P0 / precisión:** DS18B20 mide temperatura del sensor, no garantiza por sí solo temperatura corporal clínica; documentar colocación, equilibrio térmico, calibración y comparación con instrumento de referencia. El MAX30102 tampoco garantiza precisión clínica de BPM/SpO₂ sin validación.
5. **P1 / bloqueo de flujo:** conexión WiFi con bucle infinito; lectura de DS18B20 potencialmente bloqueante; manejo de clientes y sensores comparten el `loop`. Diseñar reconexión, temporización no bloqueante y adquisición estable.
6. **P1 / DHT11:** evitar lecturas más frecuentes que lo recomendado por su hoja técnica; el sketch intenta leer aproximadamente cada segundo. No confundir temperatura ambiente con corporal.
7. **P1 / confidencialidad:** credenciales embebidas en firmware; no versionar secretos ni exponer datos sanitarios en una web sin autenticación.
8. **P1 / robustez:** manejar ausencia de sensores, fallo I²C, valores fuera de rango, reinicios, watchdog y comunicación perdida.

### 2.3 Política de estado inicial

**Todas las tareas de las secciones siguientes comienzan en `PENDIENTE`.** El sketch compartido se considera una referencia inicial y **no** cuenta como prueba de aceptación de ninguna fase.

---

## 3. Arquitectura funcional propuesta

```text
                RED LOCAL (SIN DEPENDENCIA DE INTERNET)
  ┌─────────────────────┐
  │ Sensores            │
  │ DS18B20 / MAX30102  │  DHT11: variable ambiental auxiliar
  └──────────┬──────────┘
             │ GPIO / I²C / OneWire
  ┌──────────▼──────────┐
  │ ESP32               │
  │ lectura y validación│
  │ API / telemetría    │
  └──────────┬──────────┘
             │ WiFi LAN con protocolo definido
  ┌──────────▼──────────────────────────────────────────┐
  │ Aplicación / servidor local del consultorio         │
  │ Recepción | Pacientes | Consultas | Mediciones      │
  │ Triaje asistido | Reportes | Usuarios | Auditoría   │
  └──────────┬──────────────────────────────────────────┘
             │ acceso local autenticado
  ┌──────────▼──────────────────────────────────────────┐
  │ Base de datos local + copias de seguridad           │
  │ Pacientes | Consultas | Mediciones | Alertas        │
  └─────────────────────────────────────────────────────┘
```

### 3.1 Decisiones pendientes de arquitectura

- **ARQ-001 / Topología:** definir si será **una sola computadora** o **varios puestos**. Para varios puestos, preferir **base de datos central local** accesible mediante la aplicación/servidor interno, evitando historiales divergentes por computadora.
- **ARQ-002 / Stack:** elegir aplicación web local o escritorio, lenguaje, servidor y motor de base de datos según equipos existentes y facilidad de mantenimiento.
- **ARQ-003 / Conectividad:** WiFi a router local aun sin Internet; evaluar modo punto de acceso del ESP32 cuando no haya router. Documentar recuperación de cortes.
- **ARQ-004 / Integración:** definir endpoints, versión, autenticación, formatos JSON, timestamps, estados, unidades y contrato de errores. No acoplar el expediente directamente al HTML de demostración del ESP32.
- **ARQ-005 / Propiedad de datos:** definir computadora/servidor responsable de almacenamiento, respaldos, acceso concurrente y restauración.
- **ARQ-006 / Políticas clínicas:** acordar rango de pacientes/edades, protocolos de referencia, permisos para revisar triaje y reglas para mediciones ausentes.
- **ARQ-007 / Operación:** definir alimentación eléctrica, carcasa, cableado, limpieza, control de infecciones, mantenimiento y reemplazo de sensores.

### 3.2 Contrato de mediciones — mínimo a diseñar

Cada medición aceptada debería tener: `id`, `device_id`, `measurement_session_id`, `patient_id` o vínculo explícito a la consulta en el programa, `sensor`, `type`, `value` (solo si válido), `unit`, `captured_at`, `received_at`, `quality_status`, `error_code`, `firmware_version` y `accepted_by` si requiere confirmación del operador.

**Reglas:** usar nombres y unidades estables; no enviar ceros como sinónimo de fallas; no almacenar valores de SpO₂ simulados; diferenciar muestra cruda, estimación, lectura válida y lectura confirmada. Evitar asociar mediciones al paciente equivocado cuando se cambia de ficha.

### 3.3 Modelo mínimo de información

| Entidad | Campos/relaciones esenciales |
|---|---|
| `Patient` | ID interno, tipo/número de documento normalizado y único según política, datos demográficos y contactos pertinentes. |
| `ClinicalHistory` | Antecedentes, alergias y notas clínicas controladas, vinculadas a `Patient`. |
| `Encounter` | ID, paciente, profesional, fecha/hora, estado, motivo, evaluación, diagnóstico y tratamiento. |
| `VitalMeasurement` | Consulta, sesión, tipo, valor/unidad, calidad, timestamp, origen y aceptación. |
| `TriageAssessment` | Consulta, reglas/protocolo y versión, prioridad sugerida, explicación, revisión profesional. |
| `User` / `Role` | Autenticación, permisos de recepción/enfermería/médico/administración. |
| `AuditEvent` | Actor, acción, entidad, momento y resultado, sin divulgar datos clínicos innecesarios. |
| `BackupRecord` | Fecha, medio, integridad, versión y restauración probada. |

Las cédulas identifican búsquedas pero se recomienda usar **ID interno** como clave primaria para las relaciones clínicas. Definir y documentar tratamiento de pacientes sin documento, duplicados, correcciones, retención y confidencialidad.

---

## 4. Grupo 1 — Desarrollo (puede avanzar en paralelo con Documentación)

Cada bloque deberá abrir o registrar sus tareas con identificador, responsable, dependencia, evidencia y criterios de aceptación.

### DEV-00 — Base de trabajo y decisiones técnicas [P0]

- [ ] `DEV-001` Incorporar el sketch original al repositorio **sin credenciales reales** y fijar versión de placas/librerías.
- [ ] `DEV-002` Elegir estructura de proyecto firmware/app, convenciones de commits y herramientas de prueba.
- [ ] `DEV-003` Documentar matriz ESP32–sensores–pines, alimentación y dependencias.
- [ ] `DEV-004` Resolver ARQ-001 a ARQ-007 con justificación breve.
- [ ] `DEV-005` Preparar datos ficticios y entorno de desarrollo separado de pacientes reales.

**Aceptación:** compilación reproducible, dependencias fijadas, arquitectura decidida, secretos fuera del control de versiones.

### DEV-01 — Sensores y firmware fiable [P0]

- [ ] `DEV-010` Validar DHT11 (temperatura/humedad ambientales) con tiempos de muestreo adecuados.
- [ ] `DEV-011` Validar DS18B20; errores `-127 °C`, desconexiones, precisión y método de contacto.
- [ ] `DEV-012` Detectar MAX30102 y probar LED IR/rojo y calidad de señal.
- [ ] `DEV-013` Corregir BPM, manejo de primeros latidos, promedios, ausencia de dedo y caducidad.
- [ ] `DEV-014` **Eliminar SpO₂ ficticio**. Implementar cálculo real o dejar `NO DISPONIBLE` hasta validación.
- [ ] `DEV-015` Implementar estados por sensor: `OK`, `SIN_CONTACTO`, `NO_DISPONIBLE`, `ERROR`, `CADUCADO`.
- [ ] `DEV-016` Evitar bloqueos de adquisición/servidor, incorporar reconexión y recuperación de errores.
- [ ] `DEV-017` Comparar mediciones con instrumentos de referencia y registrar limitaciones.

**Aceptación:** las lecturas inválidas nunca se muestran como normales; existe evidencia de estabilidad, precisión observada y errores controlados. No se declara capacidad clínica no validada.

### DEV-02 — Comunicación local y API [P1]

- [ ] `DEV-020` Definir topología LAN y modo de contingencia sin Internet.
- [ ] `DEV-021` Diseñar API versionada para identificación de equipo, estados y mediciones.
- [ ] `DEV-022` Implementar payload JSON con unidades, timestamps, versión y calidad.
- [ ] `DEV-023` Aplicar autenticación/control de acceso en el intercambio local.
- [ ] `DEV-024` Añadir manejo de pérdidas de paquetes, reintentos, desconexiones y duplicados.
- [ ] `DEV-025` Probar operación desconectada de Internet y reconexión de dispositivo.

**Aceptación:** cliente de prueba recibe datos con formato estable sin Internet, sin aceptar lecturas obsoletas o duplicadas.

### DEV-03 — Aplicación y registro de pacientes [P1]

- [ ] `DEV-030` Definir stack y construir interfaz local de navegación.
- [ ] `DEV-031` Implementar base de datos, esquema y migraciones.
- [ ] `DEV-032` Buscar pacientes por cédula con validación y normalización.
- [ ] `DEV-033` Registrar y editar pacientes, controlar duplicados y documentar excepciones.
- [ ] `DEV-034` Implementar perfiles, sesiones y permisos según rol.
- [ ] `DEV-035` Probar concurrencia si existen varios puestos de trabajo.

**Aceptación:** alta/búsqueda/edición funcionan con datos ficticios; integridad referencial; acceso por rol.

### DEV-04 — Historias clínicas y consultas [P1]

- [ ] `DEV-040` Diseñar expediente individual y antecedentes relevantes.
- [ ] `DEV-041` Implementar apertura, guardado, cierre y consulta histórica de visitas.
- [ ] `DEV-042` Registrar fecha, profesional, motivo, evaluación, diagnóstico y tratamiento.
- [ ] `DEV-043` Mostrar historial cronológico y tendencias solo con datos válidos.
- [ ] `DEV-044` Añadir trazabilidad de edición/corrección y reglas de conservación.

**Aceptación:** las visitas quedan correctamente vinculadas al paciente y no se pierden al reiniciar.

### DEV-05 — Integración física con expediente [P1]

- [ ] `DEV-050` Detectar conexión/disponibilidad del dispositivo en la aplicación.
- [ ] `DEV-051` Crear sesión de medición asociada a un paciente y consulta.
- [ ] `DEV-052` Presentar en pantalla calidad/estado, no solo números.
- [ ] `DEV-053` Confirmar o repetir lecturas antes de incorporarlas al expediente.
- [ ] `DEV-054` Guardar automáticamente **solo lecturas aceptadas y trazables**.
- [ ] `DEV-055` Habilitar registro manual identificado como tal y auditado ante falla de sensor.
- [ ] `DEV-056` Probar cambio de paciente, doble clic, cortes de red y datos retrasados.

**Aceptación:** ninguna medición se atribuye a un paciente equivocado; es posible auditar su origen.

### DEV-06 — Triaje asistido [P0 clínico / P1 implementación]

- [ ] `DEV-060` Acordar con el personal clínico el protocolo, población y categorías que se emplearán.
- [ ] `DEV-061` Especificar variables, edades, contexto, límites y situaciones no cubiertas.
- [ ] `DEV-062` Construir motor de reglas versionado; sin umbrales clínicos inventados.
- [ ] `DEV-063` Explicar razones de cada alerta y mostrar incertidumbre/calidad de las mediciones.
- [ ] `DEV-064` Permitir revisión, anulación justificada y prioridad final por profesional autorizado.
- [ ] `DEV-065` Probar casos límite, ausencia de valores y contradicciones con revisión clínica.
- [ ] `DEV-066` Incluir advertencia de que el sistema **no sustituye** evaluación médica.

**Aceptación:** reglas aprobadas por personal competente; pruebas sobre casos definidos; alertas que no convierten datos faltantes en «normal».

### DEV-07 — Seguridad, continuidad y despliegue [P0/P1]

- [ ] `DEV-070` Modelo de amenazas, permisos mínimos y política de contraseñas/sesiones.
- [ ] `DEV-071` Protección de datos en almacenamiento y transmisión local según arquitectura adoptada.
- [ ] `DEV-072` Registro de auditoría de accesos y cambios clínicos.
- [ ] `DEV-073` Copias de seguridad, verificación de integridad y restauración probada.
- [ ] `DEV-074` Ensayar fallos de energía, sensores, LAN y reinicio de base de datos.
- [ ] `DEV-075` Pruebas automatizadas y manuales de extremo a extremo.
- [ ] `DEV-076` Piloto supervisado con aprobación del centro y criterios de suspensión.
- [ ] `DEV-077` Validar requisitos de privacidad, ética y regulación sanitaria aplicables antes del uso real.

**Aceptación:** plan de recuperación comprobado, control de roles funcional, reporte de riesgos residuales y aprobación para el alcance real del piloto.

---

## 5. Grupo 2 — Documentación (independiente y simultáneo)

El equipo documental inicia ya la investigación, diagramación, definiciones y plantillas. **No necesita esperar al software terminado**; sí debe registrar las decisiones y resultados reales cuando aparezcan.

| ID | Paquete documental | Contenido / entrega | Estado |
|---|---|---|---|
| DOC-01 | Identidad y objetivos | Introducción, problema, justificación, objetivo general/específicos, beneficiarios, alcance y límites. | PENDIENTE |
| DOC-02 | Estado del arte | Antecedentes, sistemas de expediente, telemetría biomédica y atención primaria; bibliografía verificable. | PENDIENTE |
| DOC-03 | Fundamentos clínicos | Temperatura, BPM, SpO₂, artefactos, limitaciones y fuentes de referencia. | PENDIENTE |
| DOC-04 | Hardware | Inventario, fichas técnicas, conexión de pines, alimentación, montaje y precauciones. | PENDIENTE |
| DOC-05 | Arquitectura | Diagramas de bloques, red local, datos, flujo de uso y decisiones ARQ. | PENDIENTE |
| DOC-06 | Software | Módulos, stack acordado, API, formato de datos, almacenamiento y versiones. | PENDIENTE |
| DOC-07 | Experiencia de usuario | Flujogramas recepción–medición–consulta–historial, roles y pantallas previstas. | PENDIENTE |
| DOC-08 | Triaje | Investigación de protocolos, propuesta para revisión clínica, clasificación y límites. | PENDIENTE |
| DOC-09 | Seguridad | Confidencialidad, acceso, respaldos, riesgos, continuidad y disposiciones aplicables a verificar. | PENDIENTE |
| DOC-10 | Pruebas y resultados | Plan de validación, instrumentos de referencia, matriz de casos y resultados observados. | PENDIENTE |
| DOC-11 | Manuales y cierre | Manual de instalación/operación, mantenimiento, capacitación, anexos, presentación y conclusiones sustentadas. | PENDIENTE |

### Entregables documentales sugeridos

- `docs/01-alcance-y-objetivos.md`
- `docs/02-investigacion-y-fundamentos.md`
- `docs/03-arquitectura.md`
- `docs/04-hardware.md`
- `docs/05-software-y-api.md`
- `docs/06-flujos-y-pantallas.md`
- `docs/07-triaje-y-validacion-clinica.md`
- `docs/08-seguridad-y-datos.md`
- `docs/09-pruebas-y-resultados.md`
- `docs/10-manuales.md`
- `docs/11-informe-final.md`

Los nombres son **propuestos**, no archivos que ya existan. Incorporar referencias bibliográficas reales, fecha de consulta y licencia cuando corresponda.

### Sincronización mínima entre grupos

- Definir una reunión o revisión corta por hito, no una dependencia continua de aprobación.
- Documentación puede proponer diagramas y requisitos; Desarrollo decide junto con el equipo las decisiones implementables.
- Cambios en API, modelo de datos, protocolos o alcance se reflejan aquí y en el archivo especializado correspondiente.
- Reportes documentales deben etiquetar: `PROPUESTO`, `IMPLEMENTADO SIN VALIDAR`, `VERIFICADO TÉCNICAMENTE` o `VALIDADO CLÍNICAMENTE`.

---

## 6. Flujo operativo objetivo

1. **Recepción:** introducir cédula; buscar paciente o registrar nuevo perfil; validar identidad.
2. **Apertura de consulta:** crear visita con fecha/hora, operador y motivo, y seleccionar expediente activo.
3. **Toma de signos:** colocar sensores; esperar calidad suficiente; mostrar valores o causa de indisponibilidad.
4. **Confirmación:** profesional acepta/repite mediciones; se fija procedencia, instante y sesión.
5. **Triaje asistido:** motor presenta alertas y prioridad sugerida en los casos cubiertos por el protocolo; profesional revisa.
6. **Atención:** personal autorizado registra evaluación, diagnóstico y tratamiento.
7. **Cierre:** persistir consulta, mediciones, decisión de triaje y auditoría; actualizar historial.
8. **Visitas posteriores:** consultar antecedentes y evolución cronológica a partir de la cédula.

**Excepciones obligatorias:** paciente sin cédula; duplicado; equipo desconectado; ausencia de dedo; temperatura errónea; SpO₂ no disponible; fallo de electricidad; cambio de paciente a mitad de captura; dispositivo no validado; falta de autorización.

---

## 7. Hitos integrados y dependencias

| Hito | Desarrollo | Documentación | Salida verificable |
|---|---|---|---|
| M0 — Bases | DEV-00 | DOC-01, DOC-02, DOC-05 inicial | Alcance común y decisiones de arquitectura. |
| M1 — Sensores | DEV-01 | DOC-03, DOC-04, DOC-10 protocolo | Lecturas instrumentales y reportes de limitaciones. |
| M2 — Software local | DEV-02, DEV-03 | DOC-05, DOC-06, DOC-07 | LAN sin Internet, API y pacientes operativos. |
| M3 — Expedientes | DEV-04, DEV-05 | DOC-06, DOC-07, DOC-09 | Consulta y mediciones vinculadas sin errores de identidad. |
| M4 — Triaje | DEV-06 | DOC-03, DOC-08, DOC-10 | Protocolo revisado y pruebas de reglas clínicas. |
| M5 — Piloto | DEV-07 | DOC-09, DOC-10, DOC-11 | Evidencia de pruebas, seguridad y aprobación de piloto. |

**Dependencias duras:** no incorporar SpO₂ como dato real hasta medirlo/validarlo; no cerrar integración sin control de asociación al paciente; no activar triaje como apoyo clínico sin protocolo revisado; no usar datos reales sin mecanismos de protección acordados. El resto se puede avanzar en paralelo razonablemente.

### Orden de ejecución prioritario

1. **P0:** eliminar SpO₂ simulado; impedir datos falsos/caducados; decidir seguridad y arquitectura local.
2. **P1:** firmware estable y API; registro y expedientes locales en paralelo.
3. **P1:** integración, vinculación segura de mediciones y triaje bajo supervisión clínica.
4. **P1:** pruebas integrales, respaldos, recuperación y piloto controlado.
5. **P2:** gráficos avanzados, reportes ampliados, exportaciones y mejoras de experiencia.

---

## 8. Criterios de calidad y pruebas

### 8.1 Pruebas técnicas mínimas

- [ ] Compilación limpia del firmware desde cero con versiones documentadas.
- [ ] Sensor ausente/fallo devuelve un estado de error, no un número normal.
- [ ] Dedo retirado invalida BPM/SpO₂ hasta obtener nueva lectura fiable.
- [ ] Reinicio/corte WiFi no bloquea permanentemente el sistema.
- [ ] Operación sin Internet desde captura hasta consulta y recuperación del historial.
- [ ] Cédula inválida/duplicada se gestiona explícitamente.
- [ ] Consultas y mediciones se vinculan al paciente/sesión correctos.
- [ ] Dos sesiones concurrentes no mezclan registros, si hay varios puestos.
- [ ] Usuarios sin permisos no pueden consultar/modificar datos restringidos.
- [ ] Copia de seguridad se restaura con integridad comprobada.
- [ ] Casos normales, límite, anómalos y de dato ausente producen resultados de triaje esperados según protocolo aprobado.

### 8.2 Validación de sensores y triaje

Registrar para cada sensor: instrumento comparador, número/tipo de pruebas, colocación, condiciones, sesgo/error observado, repetibilidad, valores rechazados y limitaciones. **No publicar tolerancias clínicas o precisión definitiva sin evidencia.** Comparar SpO₂ con referencia apropiada y revisar condiciones que afectan lectura (movimiento, perfusión y colocación).

La evaluación de triaje necesita protocolo con autor/revisión clínica, población cubierta, ejemplos positivos/negativos, errores relevantes y procedimiento de intervención humana. La clasificación **no** debe tomar ausencia de señal como normalidad.

### 8.3 Definición de terminado (DoD)

Una tarea solo pasa a `COMPLETADO` cuando contiene:
1. Entregable disponible y localizado (archivo, pantalla, circuito o documento).
2. Evidencia enlazada (commit, prueba, captura sin datos privados, acta o resultado).
3. Criterios de aceptación explícitamente satisfechos.
4. Documentación ajustada al comportamiento real.
5. Para partes clínicas: revisión sanitaria competente y limitaciones declaradas.

Si falta cualquiera de estos puntos, queda `EN REVISIÓN` o `PENDIENTE`, nunca `COMPLETADO`.

---

## 9. Riesgos y acciones preventivas

| Riesgo | Impacto | Mitigación propuesta |
|---|---|---|
| SpO₂ ficticio o inexacto | Crítico: falsa seguridad médica | No mostrar cifras simuladas; validación instrumental antes del uso. |
| Temperatura periférica interpretada como central | Alto | Método de colocación/calibración; advertencia y comprobación de referencia. |
| Pulso erróneo por movimiento/sin contacto | Alto | Control de calidad, caducidad, repetición y mensajes de estado. |
| Triaje mal aplicado o sin contexto | Crítico | Protocolo validado, personal responsable y prioridad editable/auditable. |
| Paciente equivocado | Crítico | Sesiones explícitas, confirmación de identidad y pruebas de concurrencia. |
| Pérdida/exposición de historias clínicas | Crítico | Roles, cifrado apropiado, auditoría, backups y restauración probada. |
| Red local o alimentación inestable | Alto | Reconexión, estados sin conexión, guardado transaccional y procedimientos de contingencia. |
| Divergencia entre ambos grupos | Medio | Un solo plan, decisiones versionadas, revisión por hito y trazabilidad. |
| Declaraciones académicas sin evidencia | Alto | Etiquetas de estado, resultados medidos y referencias verificables. |

---

## 10. Tablero de seguimiento

El registro operativo por tarea debe seguir este formato:

| ID | Responsable | Prioridad | Estado | Dependencia | Evidencia |
|---|---|---|---|---|---|
| DEV-014 | Desarrollo | P0 | PENDIENTE | DEV-012 | — |
| DEV-031 | Desarrollo | P1 | PENDIENTE | ARQ-002 / ARQ-005 | — |
| DEV-060 | Desarrollo + revisión clínica | P0 | PENDIENTE | ARQ-006 | — |
| DOC-01 | Documentación | P1 | PENDIENTE | Ninguna | — |
| DOC-04 | Documentación | P1 | PENDIENTE | Inventario inicial de sensores | — |
| DOC-08 | Documentación + revisión clínica | P0 | PENDIENTE | Investigación de protocolo | — |

Los demás IDs definidos en las fases también empiezan en `PENDIENTE`; esta tabla es un **ejemplo de seguimiento**, no un inventario de trabajos completados.

### Registro de decisiones (ADR breve)

| Código | Decisión | Estado |
|---|---|---|
| ARQ-001 | Equipo único vs varios puestos | PENDIENTE |
| ARQ-002 | Stack aplicación y base de datos | PENDIENTE |
| ARQ-003 | LAN, router y contingencia | PENDIENTE |
| ARQ-004 | Contrato de API y seguridad | PENDIENTE |
| ARQ-005 | Repositorio maestro de datos | PENDIENTE |
| ARQ-006 | Protocolo de triaje y población | PENDIENTE |
| ARQ-007 | Montaje/uso seguro del dispositivo | PENDIENTE |

### Primera entrega esperada de cada grupo

**Desarrollo:** sketch saneado sin secretos ni SpO₂ simulado, primer diagnóstico de sensores, proyecto compilable y propuesta formal de arquitectura local/API.

**Documentación:** objetivo/alcance claros, bases teóricas con referencias, inventario de componentes, diagramas iniciales, propuesta de manuales y matriz de validación.

**Ambas entregas pueden avanzar a la vez.** Ninguna depende de la finalización de la otra.

---

## 11. Convenciones para siguientes actualizaciones

- Actualizar este plan cuando una tarea cambie de estado, se descubra un riesgo o se tome una decisión.
- Registrar en commits o documentos la evidencia que justifica `COMPLETADO`.
- Mantener un historial de modificaciones del plan.
- No prometer ni declarar certificación médica, precisión o cumplimiento normativo sin validación independiente.
- No incorporar datos personales ni secretos al repositorio, aun cuando el repositorio cambie a privado.
- Conservar este archivo como índice rector; anexos y documentación extensa van en `docs/` cuando existan.

### Historial del plan

| Fecha | Versión | Cambio |
|---|---|---|
| 2026-10-12 | 1.0 | Creación del plan maestro desde requisitos compartidos y sketch de referencia; se deja todo el trabajo como pendiente hasta obtener evidencia en el repositorio. |
| 2026-10-12 | 1.1 | Se incorpora estado v0.1 de firmware, API, interfaz local, SQLite, expedientes, seguridad inicial, pruebas CI y documentación, preservando pendientes físicos/clínicos. |
