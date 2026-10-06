# SILHO — Plataforma de prevención y seguimiento del riesgo metabólico

Documento de arquitectura (v1). Describe la información, el modelo de datos, los roles, los flujos y los módulos. Se implementa por fases sobre la base actual (FastAPI + PostgreSQL + React).

> Principio: **medición → interpretación → intervención → seguimiento → nueva medición → demostración de progreso.**
> El objetivo no es detectar solo resistencia a la insulina, sino identificar a tiempo el deterioro metabólico, antes de que evolucione a diabetes, obesidad, síndrome metabólico o enfermedad cardiovascular.

## 1. Principios de diseño

1. **Nada clínico queda fijo en el código de pantalla.** Rangos, criterios, pesos del score y reglas de alerta viven en una configuración versionada en el servidor, editable desde administración médica.
2. **Trazabilidad total.** Cada medición y cada cálculo guardan fecha y hora, profesional, fuente, unidad, valor, rango usado y versión del algoritmo y de la configuración. Así se pueden hacer después estadística e investigación.
3. **Lenguaje de riesgo, nunca de diagnóstico.** Ejemplos: «Resultado compatible con mayor riesgo», «Requiere valoración profesional». El diagnóstico lo establece el profesional.
4. **Humano en el circuito.** Planes de ejercicio y nutrición, textos de IA e indicaciones importantes se generan como borrador y el paciente no los ve hasta que un profesional los aprueba.
5. **El paciente ve respuestas, no tablas.** ¿Cómo estoy? ¿Qué aumenta mi riesgo? ¿Qué debo mejorar? ¿Estoy mejorando?
6. **Preparado para integraciones.** Toda medición tiene una «fuente» (manual, laboratorio, dispositivo, importación), de modo que wearables, básculas, glucómetros o CGM se añaden como fuentes nuevas sin cambiar el modelo.

## 2. Roles y permisos

| Rol | Puede |
|---|---|
| **Administrador** (nandoedwin2213@gmail.com) | Todo; gestiona usuarios, roles y la configuración clínica (rangos, criterios, pesos, alertas). |
| **Médico** | Historia clínica, resultados, tendencias, validar interpretaciones, objetivos, indicaciones, solicitar laboratorios, derivar a nutrición o fisioterapia, aprobar textos de IA. |
| **Fisioterapeuta** | Ver riesgo, antropometría, limitaciones, dolor y capacidad funcional; crear y editar el plan de ejercicio y las evaluaciones funcionales. |
| **Nutricionista** | Ver indicadores y hábitos; crear y editar el plan nutricional, asignar recetas, objetivos y evaluar adherencia. |
| **Paciente** | Su propio portal: ver su avance, responder la historia metabólica y los hábitos, registrar peso, cintura y adherencia, mensajes y citas. No edita resultados de laboratorio ni planes. |

El control de rol se hace **en el backend** (no solo ocultando botones). Los profesionales acceden a los pacientes que tienen asignados (equipo de cuidado). El administrador ve todos.

## 3. Modelo de datos

Las tablas existentes se reutilizan (`patients`, `vitals`, `lab_results`, `lab_test_components`, `users`) y se añaden las nuevas. En todas, `created_at`/`updated_at` y `recorded_by_user_id`.

| Entidad | Tabla | Contenido clave | Fase |
|---|---|---|---|
| Patient | `patients` (existente) | nombre, fecha de nacimiento, sexo, talla | — |
| ClinicalHistory + hábitos | `metabolic_profiles` | antecedentes (diabetes, prediabetes, HTA, dislipidemia, hígado graso, obesidad, ECV, diabetes familiar), hábitos (actividad min/semana, horas sentado, sueño, alcohol, tabaco, bebidas azucaradas, ultraprocesados, frutas/verduras), limitaciones musculoesqueléticas, dolor, objetivos | 1 |
| Anthropometry / VitalSigns | `vitals` (existente + `hip_circumference`) | peso, talla, cintura, cadera, PA, FC, glucosa capilar, fuente (`import_source`, `device_used`) | 1 |
| LaboratoryResults | `lab_results` + `lab_test_components` (existentes) | valor, unidad, rango del laboratorio, fecha | — |
| Configuración clínica | `metabolic_engine_configs` | versión, JSON de rangos por indicador (opcional por sexo), criterios de síndrome metabólico, pesos del score, bandas de riesgo, reglas de alerta, quién y cuándo | 1 |
| MetabolicIndices + MetabolicRiskAssessment | `metabolic_assessments` | fecha, versión de algoritmo y de configuración, entradas usadas (valor, unidad, fecha, fuente, id de origen), índices calculados con su nivel y rango usado, componentes del score, score, nivel de riesgo, síndrome metabólico, factores, alertas | 1 |
| Alerts | `metabolic_alerts` | regla, valor disparador, estado (abierta/revisada), profesional que la revisa | 3 |
| CareTeam | `care_team_members` | paciente, profesional, rol | 3 |
| ProfessionalNotes / indicaciones / derivaciones | `professional_notes` | tipo (nota, indicación, solicitud de laboratorio, derivación), texto, autor | 3 |
| FunctionalAssessment | `functional_assessments` | prueba (sit-to-stand 30 s, prensión, velocidad de marcha, caminata 6 min, IPAQ, Borg), valor, unidad | 4 |
| ExercisePlan | `exercise_plans` + `exercise_plan_items` | aeróbico (frecuencia, duración, intensidad, tipo), fuerza (días, grupos, series, repeticiones, progresión), movilidad, equilibrio, actividad diaria; estado borrador/aprobado; autor | 4 |
| NutritionPlan | `nutrition_plans` | objetivos, distribución, indicaciones, alergias/intolerancias, estado y aprobación | 4 |
| Recipes | `recipes` | nombre, foto, ingredientes, preparación, kcal, proteínas, carbohidratos, grasas, fibra, porciones, categoría, etiquetas metabólicas | 4 |
| PatientGoals | `patient_goals` | indicador, valor objetivo, fecha objetivo, autor | 4 |
| DailyActivity + Adherence | `adherence_entries` | fecha, tipo (ejercicio, nutrición, caminata, peso, cintura), cumplido, valor (p. ej. pasos), fuente | 4 |
| AIRecommendations | `ai_recommendations` | entrada usada, texto generado, modelo, estado (borrador/aprobado/rechazado), profesional que aprueba | 5 |

## 4. Motor de riesgo metabólico (Metabolic Risk Engine)

Servicio del backend (`app/services/metabolic_engine.py`), versión de algoritmo `1.x`.

1. **Recolección.** Para cada variable toma el valor más reciente de laboratorio (por nombre, abreviatura o nombre canónico, en español o inglés) y de signos vitales, con su fecha y fuente.
2. **Normalización de unidades.** Glucosa mmol/L→mg/dL; insulina pmol/L→µU/mL; lípidos mmol/L→mg/dL; HbA1c mmol/mol→%; creatinina µmol/L→mg/dL; ácido úrico µmol/L→mg/dL. Una unidad no reconocida no se usa y se informa.
3. **Índices.** Los que combinan varios análisis usan la **misma muestra** (mismo resultado de laboratorio):
   - HOMA-IR = glucosa × insulina / 405
   - QUICKI = 1 / (log₁₀ insulina + log₁₀ glucosa)
   - TyG = ln(TG × glucosa / 2)
   - TyG-IMC = TyG × IMC
   - METS-IR = ln(2·glucosa + TG) × IMC / ln(HDL)
   - TG/HDL; cintura/talla; cintura/cadera; IMC
4. **Clasificación.** Cada indicador se clasifica con los rangos de la configuración activa (bajo, normal, límite, elevado, muy elevado; rangos por sexo cuando corresponde). Se guarda el rango usado.
5. **Síndrome metabólico.** Criterios armonizados (IDF/AHA 2009, cintura para Latinoamérica 90/80 cm): cintura, TG ≥ 150, HDL < 40/50, PA ≥ 130/85, glucosa ≥ 100. Con ≥ 3 cumplidos el resultado es «compatible con síndrome metabólico (requiere valoración profesional)». Si faltan datos para decidir, «indeterminado». Los criterios son configurables.
6. **Score Metabólico FISAI (0–100).** Media ponderada de los componentes disponibles: cada nivel tiene un puntaje (normal 100, límite 65, elevado 35, muy elevado 10). Hay pesos configurables por componente (cintura, HOMA-IR, TyG, glucosa, HbA1c, TG/HDL, PA, IMC, actividad física, tabaco). Requiere una cobertura mínima de datos; si no, «datos insuficientes». Bandas: 80–100 favorable, 60–79 riesgo inicial, 40–59 moderado, 0–39 elevado. **Es un indicador interno de seguimiento, no una herramienta diagnóstica validada.** Se guardan todos los componentes para validarlo en el futuro.
7. **Factores.** Cada componente clasificado se convierte en una tarjeta «¿Qué está afectando tu metabolismo?», ordenada por gravedad.
8. **Alertas de seguridad.** Reglas configurables (p. ej. glucosa ≥ 250, HbA1c ≥ 9, PA ≥ 180/120, TG ≥ 500) → «Requiere valoración médica».
9. **Historial.** Cada evaluación con datos nuevos se guarda como instantánea (`metabolic_assessments`). De ahí salen la evolución, las comparativas (inicio, 30, 60 y 90 días, 6 y 12 meses) y «Por qué tu riesgo cambió» (diferencia por componente entre dos instantáneas).

## 5. Flujos principales

1. **Alta:** el administrador o el médico crea al paciente y su cuenta → el paciente completa la historia metabólica y los hábitos → el médico registra antropometría y laboratorio (plantilla «Panel de resistencia a la insulina»).
2. **Evaluación:** el motor calcula índices, score, factores y alertas → el médico revisa y valida la interpretación → deriva a nutrición o fisioterapia.
3. **Intervención:** el fisioterapeuta y el nutricionista crean los planes (borrador sugerido por reglas) → los aprueban → el paciente los ve en «Mi semana».
4. **Seguimiento:** el paciente marca la adherencia y registra peso y cintura → nuevos laboratorios → nueva evaluación → «Tu progreso» y «Por qué tu riesgo cambió».
5. **Supervisión:** el dashboard profesional muestra pacientes por nivel de riesgo y alertas (riesgo en aumento, sin actividad registrada en 7 días, HbA1c fuera de objetivo).

## 6. Portal del paciente (menú)

Inicio · Mi riesgo metabólico · Mis resultados · Mi evolución · Mi ejercicio · Mi nutrición · Mis recetas · Mi semana · Mis objetivos · Mis logros · Mensajes · Citas.

Cada indicador se muestra con una explicación sencilla, un semáforo y su tendencia, sin tablas de números.

## 7. Seguridad, privacidad e investigación

- Datos de salud bajo la LOPDP (Ecuador): consentimiento informado al alta, con casillas separadas para uso de IA externa e investigación.
- La IA recibe los datos sin identificación (sin nombre ni documento) y su salida queda como borrador hasta la aprobación.
- Exportación anonimizada para investigación (instantáneas con versión de algoritmo y de configuración); el uso científico requiere un comité de ética.
- Registro de actividad existente (`activity_log`) para auditoría.

## 8. Preparación para integraciones

- **Fuentes de datos:** `vitals.import_source` y `device_used` ya existen. Los wearables (Apple Health y Health Connect necesitan app móvil), básculas, glucómetros y CGM entran como nuevas fuentes del mismo modelo.
- **Laboratorios e historia clínica:** mapeo a FHIR Observation (código LOINC, valor, unidad, fecha y fuente ya están en `lab_test_components`).
- **Machine learning y análisis poblacional:** sobre `metabolic_assessments` (componentes y versiones).

## 9. Fases

| Fase | Contenido |
|---|---|
| 1 | Motor de riesgo, configuración clínica versionada, síndrome metabólico, score, factores, alertas, historia metabólica, cadera |
| 2 | Portal del paciente «Mi salud metabólica», evolución comparativa, «Tu progreso», «Por qué tu riesgo cambió» |
| 3 | Roles médico, fisioterapia y nutrición, equipo de cuidado, dashboard profesional, alertas gestionables, notas y derivaciones |
| 4 | Evaluación funcional y Metabolic Movement, Metabolic Nutrition, recetas, «Mi semana», adherencia |
| 5 | FISAI Metabolic AI (con aprobación profesional) y simulador «¿Qué pasaría si mejoro…?» |
| 6 | Integraciones (wearables, laboratorios, ML) |
