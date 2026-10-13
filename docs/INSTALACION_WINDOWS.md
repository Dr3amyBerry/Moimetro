# Instalación de Moímetro en Windows

**Estado:** mecanismo de empaquetado implementado. La compatibilidad con Windows 7 se debe comprobar físicamente en equipos x86/x64 con SP1 antes de declararla validada.

## Instalación para el usuario

1. Entrar a [**Releases → Moímetro v0.3.0 beta**](https://github.com/Dr3amyBerry/Moimetro/releases/tag/v0.3.0-beta.1) y descargar el instalador `.exe` correspondiente desde la sección **Assets**. No hace falta extraer ZIP.
2. Ejecutar el instalador con doble clic y continuar con el asistente en español. **No necesita instalar Python ni ejecutar comandos**.
3. Opcionalmente crear acceso directo en Escritorio. El instalador también añade el acceso en el menú Inicio.
4. Al abrir Moímetro, aparece el navegador de la computadora y, en el primer inicio, se solicita crear usuario administrador y contraseña (mínimo 12 caracteres).
5. Iniciar sesión y trabajar con pacientes **ficticios** hasta aprobar seguridad y validación clínica.

No se requiere conexión a Internet durante la ejecución de la aplicación una vez instalados los componentes. Se utiliza un **servidor local interno en 127.0.0.1:8765**, sin exponerlo a la LAN. Una ventana de control minimizada permite volver a abrir el programa y cerrarlo correctamente.

## Elegir instalador

| Equipo | Archivo previsto |
|---|---|
| Windows 7 SP1 de 32 bits y otros Windows de 32 bits | `Moimetro-Setup-legacy-x86.exe` |
| Windows 7 SP1 de 64 bits, o Windows 8 de 64 bits | `Moimetro-Setup-legacy-x64.exe` |
| Windows 8.1/10/11 de 64 bits | `Moimetro-Setup-modern-x64.exe` |

**Requisitos:** Windows 7 **SP1 como mínimo**, navegador compatible (Firefox, Chrome o Edge con JavaScript moderno) y los controladores/tarjetas de red del equipo funcionando. Internet Explorer no es compatible con esta interfaz. La compatibilidad efectiva en un PC físico depende de su hardware y de su navegador instalado. El instalador no trae un navegador adicional para mantener un paquete pequeño.

### Advertencia importante de privacidad

La distribución **legacy** se construye con **Python 3.8** y PyInstaller 5.13.2, porque son compatibles a nivel de herramientas con máquinas antiguas. Ambas versiones tienen soporte de seguridad descontinuado. **Windows 7 carece de actualizaciones de seguridad desde 2020.** Por ello, la versión legacy es **exclusivamente para desarrollo o demostraciones con datos ficticios**; no debe usarse para almacenar datos médicos reales.

Las distribuciones modernas usan Python 3.11 (y deben mantenerse actualizadas). **Moímetro en conjunto sigue siendo prototipo, sin autorización para expedientes clínicos reales ni triaje automático**.

## Persistencia y actualizaciones

- El ejecutable se instala por usuario en `%LOCALAPPDATA%\Programs\Moimetro`.
- La base de datos se guarda en `%LOCALAPPDATA%\Moimetro\data\moimetro.sqlite3`.
- Los respaldos y registros de inicio deben almacenarse de forma segura, no en la carpeta de instalación.
- Actualizar mediante otro instalador **no elimina la base**. Desinstalar quita el programa y sus accesos directos, pero deja la base del usuario intacta para evitar pérdidas accidentales.
- La aplicación enlaza únicamente con `127.0.0.1`; conectar el ESP32 mediante LAN exige una implementación de transporte seguro distinta, todavía pendiente. El instalador no habilita automáticamente acceso remoto.

## Compilar instaladores en GitHub

El workflow [`.github/workflows/windows-installer.yml`](../.github/workflows/windows-installer.yml) trabaja en Windows y genera **tres instaladores**:

- `legacy-x86`: Python 3.8, PyInstaller 5.13.2, Inno Setup 6.2.2.
- `legacy-x64`: mismos componentes, arquitectura x64.
- `modern-x64`: Python 3.11, PyInstaller 6.15.0 e Inno Setup 6.2.2.

Cada matriz ejecuta los tests del servidor y una comprobación de carga del ejecutable mediante `Moimetro.exe --self-test` antes de empaquetar el instalador. Se publican archivos de comprobación SHA-256. Los instaladores compilados se guardan como artefactos de Actions por 30 días.

**No equivale a una prueba de instalación en Windows 7.** Para cerrar esa validación todavía hay que instalar en máquinas o VM Windows 7 SP1 de 32 y 64 bits, comprobar apertura, almacenamiento, desinstalación/actualización, cierre del servidor, funcionamiento offline y trazabilidad sin datos clínicos reales.

## Solución de problemas

| Problema | Acción |
|---|---|
| El EXE no abre en Windows 7 | Verificar SP1, arquitectura del instalador y DLLs del sistema; registrar el error exacto y hacer prueba real en ese equipo |
| El navegador muestra una pantalla antigua o vacía | Instalar un navegador compatible con JavaScript moderno; Internet Explorer no funciona |
| El programa informa de puerto ocupado | Revisar si Moímetro ya se está ejecutando o si otro programa utiliza `127.0.0.1:8765` |
| No aparece asistente de administrador | Iniciar desde el acceso directo `Moímetro`; el token inicial es efímero y se entrega únicamente desde el launcher |
| Quiero conservar los expedientes al actualizar | No borrar `%LOCALAPPDATA%\Moimetro\data` y hacer respaldos cifrados antes de una migración futura |

## Limitaciones expresas

Este método facilita la instalación, pero no resuelve por sí mismo la obsolescencia de Windows 7, la seguridad de expedientes, el uso de navegadores viejos, la exactitud del sensor ni el despliegue clínico multipuesto. Para pacientes reales, la recomendación es actualizar a un sistema operativo con soporte de seguridad y completar los controles pendientes de seguridad y validación.
