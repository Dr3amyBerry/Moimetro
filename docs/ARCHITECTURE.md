# Arquitectura técnica Moímetro — versión inicial

> Estado: **implementada en código, pendiente de validación en hardware y entorno clínico**. Consultorio Popular Tipo III Las Cayenas.

## 1. Componentes

\`\`\`text
             ESP32 (datos de sensores)
         ┌──────────────────────────────┐
         │ DHT11 (ambiente) GPIO18      │
         │ DS18B20 GPIO4 (contacto)     │
         │ MAX30102 SDA21 SCL22 (pulso) │
         └──────────────┬───────────────┘
                        │ LAN WiFi / HTTP [prototipo, no seguro para pacientes]
                        │ X-Device-Key
         ┌──────────────▼───────────────┐
         │ FastAPI local (Python 3.11+) │
         │ Autenticación + permisos     │
         │ Pacientes + expedientes      │
         │ Sesiones + mediciones        │
         │ Auditoría y validación       │
         └──────────────┬───────────────┘
                        │ sqlite3 / WAL
         ┌──────────────▼───────────────┐
         │ Base SQLite local            │
         │ Pacientes / Consultas        │
         │ Antecedentes / Medidas       │
         │ Usuarios / Auditoría         │
         └──────────────────────────────┘
                        ▲
         Navegador PC (usuario con roles)
         HTML / CSS / JavaScript local
\`\`\`

Sin servidor en la nube, servicios de Google ni dependencias de Internet en operación. Las dependencias Python/Arduino se descargan durante la preparación, no durante el uso. El dispositivo debe estar en la **misma red de pruebas** que el PC.

## 2. Roles y permisos

| Actividad | Recepción | Enfermería | Médico | Admin |
|---|---|---|---|---|
| Buscar y registrar pacientes | Sí | Sí | Sí | Sí |
| Editar datos de contacto | Sí | Sí | Sí | Sí |
| Consultar antecedentes | Sí | Sí | Sí | Sí |
| Editar antecedentes médicos | No | No | Sí | Sí |
| Abrir consulta | Sí | Sí | Sí | Sí |
| Registrar/aceptar mediciones | No | Sí | Sí | Sí |
| Modificar diagnóstico/tratamiento | No | No | Sí | Sí |
| Cerrar consulta | No | No | Sí | Sí |
| Crear usuarios/ver auditoría | No | No | No | Sí |

Las políticas definitivas del consultorio requieren aprobación del responsable clínico y de privacidad.

## 3. Protocolo de captura

1. Un operador autorizado abre un expediente y una consulta.
2. Pulsa **Iniciar captura**; se crea \`capture_sessions.id\` asociado a \`encounter_id\` y \`device_id\`.
3. ESP32 consulta cada ~5 segundos \`GET /api/device/active-session\` con \`X-Device-Key\`. La respuesta **no incluye nombre ni cédula del paciente**.
4. ESP32 envía cada ~3 segundos \`POST /api/device/measurements\` con sesión y muestras.
5. El servidor valida sesión, dispositivo, tipo, estado y coherencia física. Las muestras válidas entran \`pending\`; las inválidas entran \`rejected\`. SpO₂ recibido del ESP32 se rechaza.
6. Enfermería/médico acepta o rechaza explícitamente las lecturas; su acción queda auditada.
7. Se detiene la sesión. El médico registra evaluación, diagnóstico y tratamiento y cierra la consulta.

Ejemplo de **telemetría de laboratorio** (solo valores ficticios):

\`\`\`json
{
  "session_id": "TOKEN_DE_SESION_GENERADO_POR_LA_API",
  "device_id": "esp32-01",
  "samples": [
    {"kind": "pulse_bpm", "quality": "ok", "value": 78},
    {"kind": "body_temp_c", "quality": "unavailable", "value": null},
    {"kind": "ambient_temp_c", "quality": "ok", "value": 24.1},
    {"kind": "humidity_pct", "quality": "ok", "value": 56}
  ]
}
\`\`\`

Campos básicos de \`measurements\`: \`encounter_id\`, \`capture_session_id\`, \`device_id\`, \`kind\`, \`value\`, \`unit\`, \`quality\`, \`origin\`, \`status\`, \`received_at\`, \`accepted_at\`, \`accepted_by\` y notas.

**Definición de calidad:** \`ok\` / \`no_contact\` / \`unavailable\` / \`error\` / \`stale\`. Los controles de rango del backend solo descartan corrupción manifiesta de datos; **NO** definen valores saludables o niveles de triaje.

## 4. Modelo de datos

- \`users\`: cuentas y roles, hash de contraseña; \`tokens\`: SHA-256 de tokens efímeros con expiración.
- \`patients\`: cédula (tipo, número), nombre, fecha de nacimiento y contacto. Índice único en documento.
- \`patient_histories\`: alergias, antecedentes y responsable/fecha de modificación.
- \`encounters\`: visitas \`open/closed\`, evaluación, diagnóstico y tratamiento; asociadas por ID interno del paciente.
- \`capture_sessions\`: máximo una sesión activa por dispositivo.
- \`measurements\`: lecturas por consulta, originadas en dispositivo o ingresadas manualmente, con estado.
- \`audit_events\`: actividad de usuario por recurso sin copiar notas clínicas al log.

Las cédulas sirven para buscar, **no** como clave primaria. No usar registros reales en las pruebas.

## 5. Decisiones tomadas y pendientes

| ID | Decisión / situación |
|---|---|
| ARQ-001 | **Provisional:** una computadora ejecuta API + SQLite; puede recibir navegadores de una LAN de laboratorio. Arquitectura multipuesto clínica aún no aprobada. |
| ARQ-002 | **Implementación:** Python 3.11+/FastAPI/SQLite y frontend sin framework; PlatformIO + Arduino ESP32. |
| ARQ-003 | **Implementación prototipo:** WiFi local y API HTTP; contingencia, TLS y red clínica pendientes. |
| ARQ-004 | **Implementado en código:** contrato JSON de muestras, dispositivos, sesiones y roles. Falta robustez ante carga/timing real. |
| ARQ-005 | **Implementación prototipo:** almacenamiento SQLite en equipo anfitrión y respaldo manual. Falta procedimiento de restauración probado y protección de datos en reposo. |
| ARQ-006 | **No aprobado:** clasificación clínica deshabilitada, protocolos de triaje pendientes. |
| ARQ-007 | **Pendiente:** diseño físico, seguridad eléctrica, higiene, carcasa y validación sensor-instrumento. |

## 6. Límites conocidos

- La autenticación opera sobre una red local; sin TLS, el tráfico HTTP no está cifrado.
- El firmware hace solicitudes HTTP breves que pueden interrumpir muestreo óptico; deben medirse consecuencias.
- El criterio IR para presencia del dedo no es un diagnóstico; requiere calibración.
- DS18B20 mide la temperatura local del sensor, no garantiza exactitud de temperatura central.
- No hay SpO₂ calculado en firmware, ni reglas automáticas de prioridad clínica.
- La UI almacena el token de usuario solo en memoria; recargar la página requiere nuevo inicio de sesión.
- No hay todavía pruebas de recuperación del equipo físico, apagones ni restauración completa.

Consulte [SEGURIDAD.md](SEGURIDAD.md) y [VALIDACION.md](VALIDACION.md) antes de cualquier prueba fuera del laboratorio.
