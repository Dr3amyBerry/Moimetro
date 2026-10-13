# Manual de usuario — Moímetro v0.1 (borrador)

> **Prototipo para capacitación técnica con datos ficticios.** Sin validación clínica. No debe usarse para decidir urgencias, diagnósticos ni tratamientos.

## Inicio del sistema (Windows)

1. Descargar el instalador para el equipo desde [Instaladores Windows](https://github.com/Dr3amyBerry/Moimetro/actions/workflows/windows-installer.yml).
2. Ejecutar el instalador .exe con doble clic. No necesita instalar Python.
3. Abrir Moímetro desde Inicio o el acceso directo del escritorio.
4. En el primer inicio, crear la cuenta de administrador con el asistente.
5. Iniciar sesión. El programa abre la interfaz en el navegador local.

También existe ejecución de desarrollo con Python/Uvicorn descrita en el [README](../README.md). El programa funciona sin Internet una vez instalado. Windows 7 SP1 y componentes sin soporte son solo para demostraciones ficticias; no usar pacientes reales. La conexión LAN del ESP32 aún requiere transporte seguro.

## Directorio de pacientes y recepción

- Al iniciar sesión se abre **Pacientes**, con tabla del registro más reciente al más antiguo.
- Buscar por nombre, apellido, cédula o filtrar el tipo de documento (V/E/P/OTRO). La búsqueda utiliza un índice de texto local.
- Usar **Siguiente** y **Anterior** para navegar por páginas de 25. No se cargan todos los expedientes a la vez.
- Pulsar **Abrir** para consultar una ficha y **Volver al directorio** para regresar.
- **Registrar paciente** abre una pantalla aparte. Se impiden documentos duplicados.
- Las pestañas del expediente son **Consultas**, **Datos del paciente** y **Consulta activa**.
- En **Datos del paciente**, modificar nombre, fecha o teléfono. La cédula no puede editarse desde la ficha; verificar identidad primero.
- El administrador dispone de la sección **Personal** para consultar usuarios paginados y crear cuentas.

## Antecedentes y alergias

- La sección **Antecedentes y alergias** se muestra en la pestaña **Datos del paciente** del expediente.
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

- La persona con rol enfermería, médico o admin inicia una sesión desde **Consulta activa → Mediciones**.
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
| La pantalla no abre | En el EXE, verificar el iniciador y el navegador; en desarrollo, Uvicorn y el puerto. |
| No deja entrar | Usuario, contraseña y estado de cuenta; si hay muchos intentos, esperar cinco minutos. |
| ESP32 no aparece | SSID, IP de servidor, red local y coincidencia de las claves de dispositivo. |
| No hay mediciones | Sesión iniciada, sensor conectado, dedo colocado y firmware en ejecución. |
| Error de SpO₂ | Esperado: SpO₂ del firmware está deliberadamente deshabilitado. |
| No se puede cerrar la consulta | Detener primero la captura de esa visita. |
| No se puede editar | Revisar rol o si la consulta ya está cerrada. |

Documentación técnica: [Arquitectura](ARCHITECTURE.md), [Seguridad](SEGURIDAD.md), [Validación](VALIDACION.md) y [Roadmap](../PLAN_MAESTRO.md).


## Seguridad de cuentas y registro de cambios

- Cada persona autorizada dispone de **Mi contraseña** en la barra superior. Debe indicar la clave actual y la nueva; al guardar deberá iniciar sesión otra vez. No se conserva la contraseña en el navegador.
- En **Personal**, el administrador pulsa **Administrar** junto a una cuenta para cambiar su rol, bloquear/reactivar el acceso o establecer una nueva contraseña. Las sesiones anteriores quedan revocadas. No es posible bloquear al último administrador.
- En **Datos del paciente**, el personal clínico autorizado ve **Historial de cambios**, con autor, fecha, motivo y campos modificados. Los valores originales se conservan para revisión administrativa, no se modifican las entradas antiguas.
- Al modificar datos, antecedentes o evolución clínica se puede registrar un motivo. No deben incluirse contraseñas ni secretos en estos textos.
- Los permisos se validan en el servidor: ocultar botones no reemplaza esa protección.

**Limitación:** el historial no significa que los expedientes estén cifrados. Los equipos Windows 7 son solo para pruebas con información ficticia hasta resolver los riesgos de seguridad y la validación clínica.


## Ventanas y paneles de tamaño fijo

- Las pestañas del expediente mantienen un área de trabajo de altura controlada. Desplácese dentro de ella cuando existan más datos; la página no se alarga con cada registro.
- **Ingresar medición manual** abre una ventana independiente. Guardar, **Cancelar**, la tecla **Esc** o pulsar fuera de la ventana la cierran sin mover las otras tarjetas.
- En **Personal**, los formularios de crear y editar usuarios también aparecen como ventanas sobre la tabla.
- Las lecturas se muestran de **25 en 25** mediante **Anterior / Siguiente**. Las consultas del historial también están paginadas.
- Los campos de texto y las tablas tienen altura máxima, con desplazamiento interno si su contenido no cabe. No se borra ni trunca el contenido guardado por esta limitación visual.
