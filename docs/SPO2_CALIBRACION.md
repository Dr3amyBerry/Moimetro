# MAX30102 — SpO₂ experimental: algoritmo y calibración

**Estado: procesamiento óptico implementado; NO apto para diagnóstico ni historias clínicas.**

## Qué hace el firmware

- Adquiere los canales **rojo e infrarrojo** del MAX30102 desde el mismo par de muestras FIFO.
- Configura 100 muestras/s con promedio interno de 4, para **25 pares/s** efectivos.
- Mantiene una ventana acotada a 100 pares (4 segundos), recalculada cada 25 muestras (~1 segundo).
- Obtiene DC medio y AC pulsátil (RMS tras eliminar tendencia lineal) por canal.
- Calcula **R = (AC rojo/DC rojo) / (AC IR/DC IR)**.
- Descarta dedo ausente, amplitud pulsátil baja, saturación ADC, señales no correlacionadas, cambios bruscos e interrupciones de muestreo.
- Adquiere en tarea FreeRTOS separada para evitar bloqueos ópticos por HTTP.
- Muestra R y calidad por monitor serie (115200). Sin calibración: **SpO₂ = NO DISPONIBLE**.

Código: firmware/include/spo2_estimator.h y firmware/src/main.cpp.

## Por qué un R válido NO es un SpO₂ validado

R mide una relación óptica; **NO** es directamente un porcentaje de oxígeno.

Estimación matemática condicionada: **SpO₂ = a·R² + b·R + c**, con coeficientes calculados experimentalmente para **este conjunto físico** (sensor, encapsulado, LEDs y montaje). No se distribuye ninguna curva predeterminada: copiar coeficientes de otro producto no constituye calibración.

Para pruebas de banco, los cinco parámetros pueden declararse en el archivo local **no versionado** firmware/include/secrets.h:

    // SOLO LABORATORIO: sustituir con coeficientes y rango de R
    // realmente calibrados para ESTE ensamblaje, no de Internet.
    #define MOI_SPO2_LAB_A       (COEFICIENTE_A)
    #define MOI_SPO2_LAB_B       (COEFICIENTE_B)
    #define MOI_SPO2_LAB_C       (COEFICIENTE_C)
    #define MOI_SPO2_LAB_R_MIN   (R_MIN_CALIBRADO)
    #define MOI_SPO2_LAB_R_MAX   (R_MAX_CALIBRADO)

El bloque anterior **es un esquema**, no compila hasta sustituir todos los identificadores por valores numéricos obtenidos de la calibración. Sin esos parámetros, sólo muestra R y NO DISPONIBLE. Con coeficientes, cualquier porcentaje serial se etiqueta **SpO2_ESTIMACION_EXPERIMENTAL (NO USO CLINICO)**.

**Bloqueo de seguridad:** POST /api/device/measurements sigue rechazando cualquier spo2_pct del ESP32 (HTTP 422); ninguna estimación experimental entra en la historia médica. Los valores manuales de un **oxímetro externo identificado** utilizan un flujo separado y registran su origen.

## Pruebas y validación

Automatizadas: señales sintéticas conocidas, ausencia de pulso, pérdida de contacto, saturación ADC, deriva lineal, ruido entre canales, curva ficticia sólo para probar las operaciones matemáticas, y compilación ESP32.

Pendientes obligatorios:
1. Medir frecuencia real del FIFO y descartes por red en ESP32 físico.
2. Probar presión, movimiento, perfusión, tonos de piel y condiciones de luz (sin usar historias reales).
3. Calibrar y comparar contra referencias apropiadas mediante protocolo revisado por especialistas.
4. Determinar exactitud, límites y sesgos; una comparación puntual con un oxímetro comercial **no** valida este dispositivo.
5. Sólo después de aprobación técnica y clínica, diseñar API/interfaz para SpO₂ autorizado, con versión de calibración y evidencia.

Fuentes: [MAX30102 — Analog Devices](https://www.analog.com/en/products/MAX30102.html), [Guidelines for SpO₂ Measurement](https://www.analog.com/en/resources/technical-articles/guidelines-for-spo2-measurement--maxim-integrated.html), [SparkFun Example8_SPO2](https://github.com/sparkfun/SparkFun_MAX3010x_Sensor_Library/blob/master/examples/Example8_SPO2/Example8_SPO2.ino).

**Nota:** calidad de PPG por criterios de software no significa precisión clínica. En Windows 7 sólo usar datos ficticios.
