# Seguridad y privacidad — estado y tareas pendientes

> **No autorizado para expedientes clínicos reales.** La existencia de contraseñas, logs y un equipo desconectado de Internet no basta para asegurar datos de salud.

## Controles ya presentes en el prototipo

- Cuentas de personal, contraseñas con PBKDF2-HMAC-SHA256 y sal aleatoria, longitud mínima 12.
- Tokens de sesión aleatorios, almacenados en forma de hash en SQLite, con expiración 8 horas y cierre de sesión.
- Roles para modificación de historiales, aceptación de mediciones, evolución médica y creación de usuarios.
- Clave específica del dispositivo con comparación resistente a filtrado temporal básico.
- Consultas SQL con parámetros y límites de datos mediante Pydantic.
- Auditoría de accesos a expedientes y operaciones principales, separada de notas clínicas.
- Base local no incluida en Git y credenciales del firmware omitidas por \`.gitignore\`.
- Rutas API sin CORS abierto; frontend servido desde el mismo origen.
- Cabeceras CSP, X-Frame-Options, X-Content-Type-Options y no-cache básico.
- CLI para copia SQLite coherente, \`PRAGMA integrity_check\` y rechazo de sobreescritura.

## Brechas importantes para un despliegue real

| Prioridad | Pendiente | Criterio de aceptación |
|---|---|---|
| P0 | **HTTPS/TLS** para clientes y dispositivos, incluyendo red WiFi aislada. | Capturas de tráfico sin credenciales ni expedientes legibles; certificados gestionados. |
| P0 | Protección de datos **en reposo** en PC y respaldos. | Cifrado de disco/base, control de permisos, custodia de claves. |
| P0 | Autorización y políticas de protección de información sanitaria aplicables al consultorio. | Responsable identificado, consentimiento/base jurídica, retención y accesos aprobados. |
| P0 | Protocolo de alta/baja de usuarios, recuperación de contraseñas y revocación de credenciales. | Pruebas y evidencia de administración de cuentas. |
| P1 | Seguridad y tratamiento de equipos compartidos/multipuesto. | Separación de roles y PCs, sesiones expiran, bloqueo automático. |
| P1 | Protección anti abuso persistente (actualmente rate-limit de login en memoria). | Bloqueo/auditoría robustos sin denegación inadvertida de servicio. |
| P1 | Respaldo externo cifrado y restauración real ensayada. | Procedimiento de recuperación probado con integridad referencial y objetivos RPO/RTO. |
| P1 | Actualizaciones y migraciones de esquema. | Restauración compatible con versiones y rollback probado. |
| P1 | Revisión de amenazas y seguridad de dependencias de Python y Arduino. | Inventario, vulnerabilidades documentadas y plan de actualización. |
| P1 | Controles de integridad/frescura/antirrepetición para paquetes ESP32. | Sesión unívoca, idempotencia, eventos duplicados descartados. |
| P1 | Registro de cambios clínicos con versión/autor anterior y motivo. | Trazabilidad de correcciones sin eliminación silenciosa. |

## Respaldo local

\`\`\`bash
python -m app.manage backup --output /ruta/segura/respaldo-2026-10-12.sqlite3
python -m app.manage verify-backup --input /ruta/segura/respaldo-2026-10-12.sqlite3
\`\`\`

**Precaución:** los respaldos actuales NO están cifrados. Solo hacerlos con datos ficticios o en ambiente protegido según política aprobada. \`verify-backup\` comprueba coherencia estructural, **no demuestra que el proceso de restauración funcione**. La operación de restauración deliberadamente no se automatizó sin procedimiento y controles humanos.

## Reglas para el equipo

1. No subir cédulas, contraseñas, claves del dispositivo, capturas con datos de pacientes ni bases SQLite al repositorio.
2. No exponer \`uvicorn --host 0.0.0.0\` fuera de una LAN de laboratorio aislada.
3. Cambiar de inmediato claves usadas por error en capturas o repositorios; ocultar el archivo no revoca credenciales publicadas.
4. Trabajar con pacientes **ficticios** hasta que exista revisión de privacidad, seguridad y validación clínica.
5. Mantener separadas las pruebas técnicas de la documentación de capacidades clínicas reales.
