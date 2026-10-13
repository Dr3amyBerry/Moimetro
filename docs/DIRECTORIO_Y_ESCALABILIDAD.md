# Directorio y escalabilidad de Moímetro

**Estado:** implementado en código; se requieren mediciones de rendimiento en las computadoras objetivo, especialmente Windows 7 SP1.

## Flujo de trabajo

- La pantalla inicial es el **directorio de pacientes**, con búsqueda por nombre, apellido y documento, filtro V/E/P/OTRO y botón para abrir expediente.
- El panel lateral contiene solo navegación. Registrar pacientes y gestionar usuarios usan pantallas separadas.
- El detalle de un paciente conserva las pestañas **Consultas / Datos del paciente / Consulta activa**.
- El personal administrativo dispone de un listado paginado de cuentas, sin contraseñas ni tokens en las respuestas.

## Controles para directorios amplios

| Área | Implementación |
|---|---|
| Pacientes | API `GET /api/patients/directory`, hasta 50 filas por llamada; UI solicita 25 |
| Historial | API `GET /api/encounters/directory`, hasta 50 visitas; UI solicita 15 |
| Personal | API `GET /api/admin/users`, hasta 50 usuarios; UI solicita 20 y exige administrador |
| Navegación | Paginación por cursor `id < before`, sin `OFFSET` creciente |
| Búsqueda | SQLite FTS5 con índice para nombres, apellidos, cédulas y acentos; consulta prefijada |
| Actualizaciones | Triggers de SQLite actualizan FTS5 al crear, editar nombre/documento o eliminar |
| Migración | Índice creado o reconstruido al iniciar si la base tenía versión anterior |
| Interfaz | Búsquedas con espera de 350 ms y descarte de respuestas antiguas |
| Datos | SQLite en carpeta de datos local; no se envían expedientes a servicios externos |

## Pruebas y limitaciones

Las pruebas automatizadas incluyen más de 200 registros ficticios, 63 consultas en un expediente, paginación sin duplicados, filtros por documento, búsqueda por apellido con acentos, migración de una base previa y autorización de cuentas. **Estas pruebas funcionales no sustituyen benchmarks con decenas o cientos de miles de expedientes.**

Pendiente: validar tiempos de búsqueda y memoria con 50 000 y 100 000 pacientes ficticios en Windows 7 SP1 (32/64 bits), medir ocupación del índice FTS y estrategias de mantenimiento y respaldos cifrados. No usar datos médicos reales hasta completar validación clínica y seguridad.
