# Manual de usuario — Moímetro v0.1 (borrador)

> **Prototipo para capacitación técnica con datos ficticios.** Sin validación clínica. No debe usarse para decidir urgencias, diagnósticos ni tratamientos.

## Inicio del sistema

1. Instalar Python 3.11+ y las dependencias indicadas en [README](../README.md).
2. Crear el primer administrador con `python -m app.manage create-admin --username admin` (solo primera vez).
3. Abrir el servidor con `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
4. Abrir `http://127.0.0.1:8000` en el navegador de la computadora donde se ejecuta la aplicación.
5. Iniciar sesión. La cuenta administradora puede crear otras cuentas desde el panel de administración.

La aplicación funciona localmente sin Internet después de instalar sus dependencias. Los navegadores de otras computadoras solo deben conectarse cuando haya una arquitectura LAN segura aprobada.

## Recepción: identificar y registrar

- En **Pacientes**, buscar por cédula o nombre.
- Si existe, abrir la ficha haciendo clic en el resultado.
- Si es una persona nueva, completar tipo de documento, número, nombre, fecha de nacimiento y teléfono. El sistema rechaza un documento duplicado.
- Verificar la identidad antes de editar los datos. La cédula no se modifica desde la interfaz de edición; su corrección requiere un procedimiento administrativo específico aún pendiente.
- En **Datos personales**, modificar nombre, fecha o teléfono y guardar.

## Antecedentes y alergias

- La sección **Antecedentes y alergias** se muestra dentro del expediente.
- Solo un médico o administrador puede **guardar** antecedentes en esta versión; otros roles tienen acceso de lectura.
- No asumir que un campo vacío significa ausencia de alergias. Registrar solo información comprobada y autorizada.

## Abrir y cerrar una consulta

1. Seleccionar el paciente.
2. Escribir el motivo y pulsar **Abrir consulta**.
3. Revisar el historial de consultas y elegir la visita activa.
4. El médico completa **Evaluación**, **Diagnóstico** y **Tratamiento**; pulsa **Guardar evolución**.
5. Al finalizar las mediciones, detener la captura activa.
6. El médico cierra la consulta con **Cerrar consulta**. Una consulta cerrada deja de admitir nueva evolución o mediciones.

Las consultas anteriores se muestran en **Historial**, con fecha y estado.

## Medición con ESP32

- La persona con rol enfermería, médico o admin inicia una sesión desde **Captura de sensores**.
- El ESP32 autorizado consulta automáticamente qué sesión está activa (sin recibir la cédula ni el nombre del paciente).
- El dispositivo envía valores y estados de calidad. Los valores admisibles llegan como **Pendientes** y necesitan revisión humana.
- El operador comprueba identidad, colocación, coherencia y calidad, y pulsa **Aceptar** o **Rechazar** para cada lectura.
- Sin señal o con error, aparece **No disponible**; jamás interpretar un valor ausente como normal.
- Pulsar **Detener captura** antes de cerrar la consulta.

**SpO₂:** este firmware no calcula saturación de oxígeno. El servidor rechaza cualquier cifra enviada como SpO₂ desde el ESP32. Una medición ingresada manualmente desde instrumento externo debe detallar su procedencia y todavía requiere validación operativa.

## Registro manual

- En **Agregar medición manual**, elegir tipo, valor y notas identificando instrumento y contexto.
- La base almacena el origen como `manual`, distinto de `device`, y registra al profesional.
- El sistema aplica filtros de plausibilidad física, **no** rangos médicos de normalidad.

## Roles

| Función | Recepción | Enfermería | Médico | Administrador |
|---|---|---|---|---|
| Pacientes y consultas nuevas | Sí | Sí | Sí | Sí |
| Iniciar captura y registrar mediciones | No | Sí | Sí | Sí |
| Guardar antecedentes y evolución clínica | No | No | Sí | Sí |
| Cerrar consulta | No | No | Sí | Sí |
| Crear personal | No | No | No | Sí |

## Respaldos y mantenimiento

El personal técnico con acceso al equipo puede crear copias SQLite coherentes:

```bash
python -m app.manage backup --output ruta/segura/copia.sqlite3
python -m app.manage verify-backup --input ruta/segura/copia.sqlite3
```

**Las copias no están cifradas.** No introducir datos reales hasta resolver su custodia y protección. Restauración operativa aún requiere diseño y pruebas.

## Problemas frecuentes

| Situación | Qué revisar |
|---|---|
| La pantalla no abre | Que Uvicorn esté en ejecución; URL y puerto correctos. |
| No deja entrar | Usuario, contraseña y estado de cuenta; si hay muchos intentos, esperar cinco minutos. |
| ESP32 no aparece | SSID, IP de servidor, red local y coincidencia de las claves de dispositivo. |
| No hay mediciones | Sesión iniciada, sensor conectado, dedo colocado y firmware en ejecución. |
| Error de SpO₂ | Esperado: SpO₂ del firmware está deliberadamente deshabilitado. |
| No se puede cerrar la consulta | Detener primero la captura de esa visita. |
| No se puede editar | Revisar rol o si la consulta ya está cerrada. |

Documentación técnica: [Arquitectura](ARCHITECTURE.md), [Seguridad](SEGURIDAD.md), [Validación](VALIDACION.md) y [Roadmap](../PLAN_MAESTRO.md).
