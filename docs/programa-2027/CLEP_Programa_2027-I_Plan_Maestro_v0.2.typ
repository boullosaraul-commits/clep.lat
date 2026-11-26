// CLEP 2027-I · Plan maestro de trabajo
// Versión 0.2 · 26 de noviembre de 2026
// Documento de trabajo interno. Las participaciones REDEFFIM no están confirmadas.

#set page(
  paper: "a4",
  margin: (top: 22mm, bottom: 24mm, left: 25mm, right: 25mm),
  numbering: "1",
)
#set text(font: "EB Garamond", size: 11pt, lang: "es")
#set par(justify: true, leading: 0.72em)
#set heading(numbering: "1.")
#set table(stroke: 0.4pt, inset: 5pt)


#let turq = rgb("#087F8C")
#let turq-dark = rgb("#075B63")
#let turq-pale = rgb("#E8F5F5")
#show heading.where(level: 1): it => block(
  above: 1.5em, below: 0.7em,
  text(fill: turq-dark, size: 17pt, weight: "bold", it)
)
#show heading.where(level: 2): it => block(
  above: 1.2em, below: 0.5em,
  text(fill: turq, size: 13pt, weight: "bold", it)
)
#show heading.where(level: 3): it => block(
  above: 1em, below: 0.35em,
  text(fill: turq-dark, size: 11.5pt, weight: "bold", it)
)

#let box(title, body) = block(
  breakable: false,
  fill: turq-pale,
  stroke: (left: 2.2pt + turq),
  inset: 9pt,
  radius: 2pt,
  width: 100%,
  [
    #text(fill: turq-dark, weight: "bold")[#title]
    #v(3pt)
    #body
  ]
)

#let status-fixed = [*Definido*]
#let status-prov = [*Provisional*]
#let status-open = [*Por confirmar*]

#align(center)[
  #v(22mm)
  #text(fill: turq-dark, size: 14pt, weight: "bold")[CLEP]
  #v(8mm)
  #text(size: 28pt, weight: "bold")[Programa 2027-I]
  #v(4mm)
  #text(size: 18pt, fill: turq-dark)[Dinero, demanda efectiva, acumulación y financiación:]
  #v(2mm)
  #text(size: 15pt)[de Keynes a Minsky]
  #v(15mm)
  #text(size: 16pt, weight: "bold")[Plan maestro de trabajo]
  #v(5mm)
  #text(size: 11pt)[Versión 0.2 · 26 de noviembre de 2026]
  #v(28mm)
  #box(
    [Estado del documento],
    [Documento de trabajo para revisión académica. El calendario ordinario, las colaboraciones externas y la distribución de algunas lecturas permanecen sujetos a revisión. Las efemérides de 1937, la estructura del círculo del _Treatise on Money_ y el arco intelectual general funcionan como anclas del programa.]
  )
  #v(24mm)
  #text(size: 9.5pt, fill: gray)[Colectivo Latinoamericano de Economía Pluralista]
]
#pagebreak()

= Propósito y estado del documento

Este plan maestro reúne en una sola arquitectura el trabajo preparado para CLEP durante el primer semestre de 2027. Su función no es anunciar actividades como si todas estuvieran confirmadas, sino conservar el objeto intelectual del programa, ordenar las lecturas, localizar las decisiones pendientes y permitir que cada sesión se prepare a partir de una secuencia común.

La pregunta articuladora es: *¿Cómo se relacionan la producción, la circulación monetaria, la distribución del ingreso, la inversión, la acumulación y la financiación en una economía capitalista?* Su formulación metodológica es: *¿cómo se construye una economía monetaria y cómo cambia la determinación macroeconómica cuando se modifican las relaciones, la temporalidad y las instituciones que forman parte del objeto?* El recorrido no se organiza como una sucesión de “escuelas”, sino como una serie de construcciones que pueden compararse por aquello que suponen, determinan y dejan abierto.

#box(
  [Regla de lectura],
  [
    Una identidad, una definición o una ecuación del modelo establece primero lo que se sigue de la construcción adoptada. No debe presentarse, sin supuestos adicionales, como evidencia de un mecanismo causal. La evidencia empírica cumple otra función: permite contrastar implicaciones observables, establecer regularidades o discriminar entre hipótesis cuando el diseño lo permite.
  ]
)

== Qué queda congelado en esta versión

- El círculo de lectura del _Treatise on Money_ ocupa cinco semanas, del 11 de enero al 14 de febrero de 2027.
- El arco intelectual de 2027-I es: *Treatise* → Keynes 1933 → _General Theory_ → recepción → Hicks/Kalecki → Steindl → Lerner → Minsky.
- Las efemérides de 1937 funcionan como anclas: Keynes y Kalecki en febrero; Hicks en abril; Keynes sobre la tasa de interés en junio.
- REDEFFIM se integra como interlocutor de problemas ya construidos por el seminario, no como ciclo paralelo.
- La reconstrucción sistemática de MMT y la aplicación a México y América Latina se reservan para una fase posterior, provisionalmente 2027-II.

== Qué permanece provisional

- Las fechas exactas de las sesiones ordinarias después del círculo del _Treatise_.
- Los nombres de investigadores de REDEFFIM. Los nombres incluidos más adelante expresan afinidades temáticas, no invitaciones cursadas ni participaciones confirmadas.
- La condición obligatoria, de contraste o de ampliación de algunas lecturas secundarias.
- La extensión del cierre intensivo de junio.

= Objetivo intelectual

Reconstruir y comparar distintas formas de construir una economía monetaria y la determinación macroeconómica —desde Keynes y la bifurcación Hicks/Kalecki hasta Lerner y Minsky— para distinguir qué resultados se siguen de cada construcción, qué supuestos adicionales requieren y qué cambia al introducir tiempo, instituciones monetarias, Estado, financiación, balances y compromisos futuros.

El objetivo no es obtener una síntesis doctrinal anticipada. El programa busca saber, en cada paso, *cuánto permite afirmar la construcción disponible* y qué dificultad concreta justifica introducir una nueva condición.

== Preguntas rectoras

1. ¿Qué objeto económico construye cada autor?
2. ¿Qué magnitudes son definidas, exógenas, endógenas o determinadas simultáneamente?
3. ¿Qué resultados se siguen de las relaciones adoptadas?
4. ¿Qué afirmaciones requieren comportamiento, temporalidad o instituciones adicionales?
5. ¿Qué parte de una interpretación está respaldada por evidencia y qué parte depende del cierre teórico?
6. ¿Qué dificultad de la construcción anterior hace necesario el paso siguiente?

= Método de trabajo

La unidad básica de exposición será:

$ "objeto" arrow.r "relaciones" arrow.r "resultado" arrow.r "dificultad" arrow.r "nueva condición" $

Se conservarán los elementos de una construcción mientras sean suficientes. Cuando aparezca una dificultad delimitada, se preguntará primero si puede resolverse modificando una condición ya disponible. Sólo cuando eso no sea suficiente se ampliará el objeto.

#box(
  [Distinción analítica],
  [
    $ "definición / identidad" != "resultado del modelo" != "regularidad empírica" != "mecanismo causal" $
  ]
)

== Reconstrucción antes de crítica

Una teoría será reconstruida primero en sus propios términos: objeto, supuestos, relaciones, cierre, resultados y temporalidad. Sólo después se introducirán dificultades internas, contraejemplos, explicaciones alternativas o supuestos adicionales. No se considerará refutada una construcción simplemente porque no responda a una pregunta perteneciente a otro objeto teórico.

== Ejemplo rector: ahorro e inversión

La igualdad

$ S equiv I $

puede formar parte de una identidad contable. No establece por sí sola una trayectoria causal. Una afirmación como

$ Delta I arrow.r Delta Y arrow.r Delta S $

requiere especificar relaciones de comportamiento, ajuste y cierre. Esta diferencia será utilizada recurrentemente para leer la _General Theory_, su recepción y las reconstrucciones posteriores.

== Interlocución con la crítica marxiana

En el _Treatise_, distinguir el medio de liquidación de la reproducción del circuito del capital dinerario (Marx, libro II, sección I). En Kalecki, confrontar la realización monetaria de los beneficios con los intercambios entre departamentos de los esquemas de reproducción (II, sección III). Registrar qué representa cada magnitud antes de comparar una identidad de gasto con el análisis de producción de plusvalor. En Steindl, contrastar la concentración y centralización del capital (I, sección sobre acumulación) con el desplazamiento de empresas y la distribución de fondos internos. El cap. XIV permite confrontar su lectura de la rentabilidad con el libro III, sección III. En Minsky, distinguir realización de mercancías y cumplimiento de obligaciones con vencimiento específico. Cada comparación debe identificar una diferencia que sobreviviría incluso si las magnitudes observadas coincidieran.

= Arquitectura general del programa

El recorrido comienza con el Keynes del _Treatise_, donde dinero, bancos, depósitos, ahorro, inversión y tasa bancaria forman parte del objeto desde el inicio. Después se estudia la formulación explícita de una “teoría monetaria de la producción” y la reconstrucción de la demanda efectiva en la _General Theory_.

A partir de ahí se abre una bifurcación. Hicks reconstruye la determinación macroeconómica mediante relaciones simultáneas; Kalecki desarrolla una determinación de beneficios, inversión y ciclo donde los rezagos y la secuencia temporal adquieren un papel estructural.

$ 
"Treatise" arrow.r "1933" arrow.r "General Theory" arrow.r "recepción"
$

$ 
"General Theory" arrow.r "Hicks" arrow.r "SI/LL" arrow.r "IS-LM"
$

$
"demanda efectiva" arrow.r "Kalecki" arrow.r "beneficios" arrow.r "inversión" arrow.r "ciclo"
$

Lerner introduce una línea distinta: finanzas funcionales, pleno empleo y dinero como criatura del Estado. El cruce Lerner–Kalecki permite distinguir la posibilidad macroeconómica de sostener el pleno empleo de sus condiciones políticas e institucionales.

Finalmente, Minsky amplía el objeto de la inversión. Financiar una inversión no sólo permite realizar un gasto: crea simultáneamente una estructura de activos, pasivos y compromisos futuros.

$ D_t^I arrow.r F_t arrow.r I_(t+tau) $

$ F_t arrow.r L_t arrow.r ("PC"_(t+1), dots, "PC"_(t+n)) $

$ A_t arrow.r ("CF"^e_(t+1), dots, "CF"^e_(t+n)) $

La comparación admite superávit, cobertura exacta o insuficiencia de caja:

$ "CF"_(t+s) ⋚ "PC"_(t+s) $

La validación ex post de una estructura financiera creada ex ante depende de la trayectoria macroeconómica futura.

= Prólogo: círculo de lectura del _Treatise on Money_

Duración: cinco semanas. Ventana de trabajo: *11 de enero–14 de febrero de 2027*. El círculo funciona como prólogo del programa semestral y evita reducir el _Treatise_ a una sola sesión introductoria.

#table(columns: (1.05fr, .8fr, 2.3fr, 1fr), stroke: none, inset: 4pt, fill: (x,y) => if y == 0 {rgb("#dcefed")},
table.header([*Domingo*],[*Capítulos*],[*Problema*],[*Páginas¹*]),
[17 enero],[1–3],[Dinero de cuenta, contratos y depósitos],[17–58],
[24 enero],[9–11],[Ingreso, ahorro y ecuaciones fundamentales],[125–166],
[31 enero],[13–15],[Tipo bancario, precios y circulación],[179–236],
[7 febrero],[25–27],[Reservas, actividad e inversión fija],[379–426],
[14 febrero],[31–33],[Instrumentos y límites de la gestión monetaria],[515–568])
¹ Paginación impresa del _Tratado sobre el dinero_, traducción de Esther Rabasco, Síntesis/Fundación ICO (2010). Son 244 páginas en quince capítulos.

*Horario de Ciudad de México.* Las primeras cuatro sesiones transcurren de 11:00 a 12:30. El 14 de febrero, de 11:00 a 13:05, con 35 minutos adicionales de balance. En total, 485 minutos sincrónicos. La preparación comienza el 11 de enero.

*Modalidad virtual.* Jitsi Meet para las reuniones y Google Classroom para calendario, materiales, preguntas y relatorías. La inscripción se organiza mediante Google Forms. El grupo de WhatsApp es optativo.

*Seguimiento.* Registrar asistencia y actividad académica por separado. Se contempla una constancia propia del colectivo con cuatro asistencias de cinco, participación y síntesis revisable de 500–800 palabras. La coordinación evaluará dificultades, relatorías y asistencia al cerrar el círculo.

== Semana 1 · 11–17 enero
*Capítulos 1–3 · Naturaleza del dinero*

Núcleo: unidad de cuenta, deudas, precios, contratos, medios de liquidación, papel del Estado y dinero bancario.

#box(
  [Pregunta],
  [¿Qué clase de objeto construye Keynes cuando parte de deudas y unidad de cuenta, en vez de partir de una mercancía utilizada como medio de intercambio?]
)

== Semana 2 · 18–24 enero
*Capítulos 9–11 · Ecuaciones fundamentales*

Núcleo: ingreso, ahorro, inversión, precios y beneficios. La sesión separará con cuidado las relaciones que se siguen de las definiciones de aquellas que pretenden describir un proceso económico.

#box(
  [Pregunta],
  [¿Qué resultados se siguen de las ecuaciones por construcción y cuáles requieren ya una interpretación del proceso económico?]
)

== Semana 3 · 25–31 enero
*Capítulos 13–15 · Mecanismo monetario*

Núcleo: circulación industrial y financiera, condiciones bancarias, inversión, precios de activos, decisiones empresariales y tasa bancaria.

Esquema de trabajo:

$ "condiciones bancarias" arrow.r "inversión" arrow.r "I-S" arrow.r "beneficios/pérdidas" arrow.r "producción y empleo" $

#box(
  [Pregunta],
  [¿Qué tiene que ocurrir entre una decisión bancaria y una modificación de la producción para que podamos hablar realmente de un mecanismo monetario?]
)

== Semana 4 · 1–7 febrero
*Capítulos 25–27 · Reservas, actividad e inversión*

Núcleo: bancos no reducidos a intermediarios pasivos, creación de depósitos, financiación y restricciones del sistema bancario.

#box(
  [Pregunta],
  [¿Qué determina la capacidad del sistema bancario para acomodar o restringir la expansión monetaria y qué relación guarda eso con la actividad económica?]
)

Durante esta misma semana se propone una segunda sesión, separada del círculo, dedicada al aniversario Keynes–Kalecki de 1937.

== Semana 5 · 8–14 febrero
*Capítulos 31–33 · Gestión del dinero*

Núcleo: bancos centrales, reservas, tasas de interés y objetivos de política monetaria.

#box(
  [Pregunta],
  [Después de todo el recorrido del _Treatise_, ¿qué puede controlar realmente una autoridad monetaria y mediante qué operaciones?]
)

= Tres anclas de 1937–2027

== Febrero · Keynes × Kalecki

En los números de febrero de 1937 se publicaron, en revistas distintas, dos textos que permiten observar dos construcciones contemporáneas de la macroeconomía:

- J. M. Keynes, “The General Theory of Employment”.
- Michał Kalecki, “A Theory of the Business Cycle”.

La actividad propuesta no presentará a Kalecki retrospectivamente como una derivación o “alternativa posterior” a Keynes.

#box(
  [Pregunta],
  [¿Qué problema construye cada autor y mediante qué relaciones intenta resolverlo?]
)

== Abril · Hicks

Noventa años de “Mr. Keynes and the ‘Classics’: A Suggested Interpretation”. La sesión distinguirá el artículo de 1937, las reconstrucciones SI/LL posteriores y el IS-LM de manual.

#box(
  [Pregunta],
  [¿Qué construyó Hicks en 1937 y cómo llegó esa construcción a representar a Keynes?]
)

== Junio · Keynes y la tasa de interés

Noventa años de “Alternative Theories of the Rate of Interest”. La lectura se reconstruirá como parte de una controversia y no como pieza aislada.

#box(
  [Pregunta],
  [¿Qué determina la tasa de interés y qué cambia cuando crédito, liquidez y decisiones financieras forman parte explícita del objeto?]
)

= Secuencia de sesiones

Las fichas siguientes establecen la operación intelectual de cada sesión. La distribución exacta de algunas lecturas podrá ajustarse sin modificar el arco general.

== Keynes 1933 · Economía monetaria de producción

*Lectura primaria:* Keynes, “A Monetary Theory of Production”.

Operación: identificar qué diferencia una economía monetaria de una economía de intercambio real cuando el dinero no es añadido después de determinar las magnitudes reales.

*Resultado buscado:* precisar qué debe significar que el dinero sea constitutivo de la determinación económica.

*Problema abierto:* pasar de la caracterización del objeto a una teoría de la producción y el empleo.

== _General Theory_ · Demanda efectiva

*Lectura primaria:* capítulos seleccionados de la _General Theory_, comenzando por el capítulo 3.

Operación: reconstruir la demanda efectiva como relación de determinación y distinguirla de una descripción meramente contable del gasto realizado.

*Problema abierto:* localizar el papel del ingreso, ahorro e inversión.

== _General Theory_ · $S equiv I$ y determinación del ingreso

Operación: separar identidad, comportamiento y ajuste. La sesión utilizará explícitamente la diferencia entre $S equiv I$ y una secuencia causal del tipo $Delta I arrow.r Delta Y arrow.r Delta S$.

*Resultado buscado:* mostrar que la compatibilidad contable restringe los resultados posibles sin determinar por sí sola el mecanismo que conduce a ellos.

== La _General Theory_ antes de IS-LM

*Lecturas centrales:* Lerner (1936) y Champernowne (1936). Harrod y Meade quedan como contraste.

#box(
  [Pregunta],
  [Antes de que existiera IS-LM, ¿qué identificaron lectores contemporáneos competentes como innovación analítica de la _General Theory_?]
)

== Hicks 1937 · Reconstrucción interna

Operación: identificar objeto, ecuaciones, cierre, variables exógenas y endógenas, variables determinadas y temporalidad. No se leerá todavía desde la crítica posterior.

*Resultado buscado:* establecer qué determina efectivamente el artículo y bajo qué condiciones.

== De SI/LL a IS-LM

*Lecturas de reconstrucción:* León León; Lizarazu Alanez; Lizarazu Alanez y Liquitaya Briceño.

Operación: seguir las transformaciones que separan el artículo histórico de Hicks del dispositivo pedagógico posterior.

== IS-LM moderno y Hicks 1980–81

*Lecturas:* Mitchell, Wray y Watts, cap. 28; Hicks, “‘IS-LM’: An Explanation”.

Operación: construir el sistema moderno

$ "IS"(Y,i)=0, quad "LM"(Y,i)=0 arrow.r (Y^ast,i^ast) $

y después alterar las condiciones de tiempo y expectativas para preguntar qué relaciones sobreviven.

== Kalecki · Beneficios y demanda efectiva

*Lecturas:* “Determinants of Profits” y “Determination of National Income”.

Operación: reconstruir las ecuaciones antes de atribuirles una dirección causal. Una relación simplificada como

$ P = I + C_k $

será tratada primero según su estatuto formal; después se preguntará qué comportamiento y qué cierre permiten interpretarla dinámicamente.

== Kalecki · Capital empresarial e inversión

*Lecturas:* “Entrepreneurial Capital and Investment” y “Determinants of Investment”.

Operación: distinguir decisiones de inversión de inversión realizada e identificar el papel del capital propio, el riesgo y las condiciones financieras.

$ D_t^I != I_t $

*Problema abierto:* la decisión y su realización ocurren en momentos distintos.

== Kalecki · Del equilibrio al ciclo

*Lectura:* “A Theory of the Business Cycle” y selecciones de _Theory of Economic Dynamics_.

Operación: comparar simultaneidad y secuencia temporal.

$ "Hicks: equilibrio simultáneo" != "Kalecki: relaciones con rezagos" $

#box(
  [Pregunta],
  [¿Qué resultados nuevos aparecen cuando la simultaneidad se sustituye por una estructura temporal explícita?]
)

== Tugan-Baranovski, Luxemburg y la genealogía de la demanda efectiva

*Lectura central:* Kalecki, “The Problem of Effective Demand with Tugan-Baranovski and Rosa Luxemburg”, con selecciones de Tugan-Baranovski.

Operación: reconstruir una genealogía alternativa sin convertirla en una línea evolutiva única:

$ "Marx" arrow.r "Tugan/Luxemburg" arrow.r "Kalecki" $

== Josef Steindl · De los beneficios retenidos a la decisión de ampliar capacidad

¿Qué hace una empresa con las ganancias que retiene cuando sus instalaciones ya permiten producir más de lo que vende? De Kalecki conservamos la distinción entre fondos internos, decisión de invertir y gasto realizado. Steindl introduce empresas con costes diferentes, mercados con distinta facilidad de entrada y un grado de utilización que puede apartarse persistentemente del deseado. Una reserva planeada de capacidad puede ser compatible con las ventas esperadas. El exceso indeseado exige explicar por qué las ventas quedaron por debajo de lo previsto y cómo responde la empresa.

En una industria con numerosos productores, la expansión de empresas con ventajas de coste puede desplazar a sus competidores. Cuando aumenta la concentración y resulta difícil ganar mercado mediante reducciones de precios, los márgenes pueden sostenerse mientras la utilización o el incentivo a invertir se debilitan. El resultado depende de la respuesta de precios, ventas e inversión. Un margen elevado por sí solo deja indeterminada la trayectoria de la acumulación.

*Ficha de trabajo.* Leer la distinción entre capacidad deseada y efectiva (cap. II), reconstruir el paso de la empresa a la industria (V) y seguir el argumento agregado sobre fondos y utilización (IX–X). En XIII comparar los casos de utilización constante y variable. En XIV contrastar la lectura de Marx con los pasajes del propio Marx. Producto: un cuadro que distinga escala, condición, resultado e indicio empírico. Para discriminar entre mecanismos, buscar series de márgenes, retención de beneficios, utilización e inversión y examinar diferencias sectoriales y de demanda.

*Salida hacia Lerner y Minsky.* Si la expansión privada pierde impulso, ¿qué condición permitiría sostener el empleo mediante gasto público? Y si una empresa financió capacidad que permanece ociosa, ¿qué ingresos validarán los pagos contratados? La primera pregunta exige precisar instrumentos fiscales e instituciones monetarias. La segunda exige incorporar balances y vencimientos.

*Distribución propuesta para deliberación.* Tras S15, dedicar el cierre de su discusión a la pregunta de Steindl y circular una ficha de lectura antes de Lerner. La conmemoración de junio conserva su objeto. Para participantes, proponer como contraste el apartado sobre márgenes y utilización (edición mexicana, pp. 172–174). Para coordinación, añadir la comparación de utilización constante y variable del cap. XIII. A 8–12 páginas por hora, las tres páginas adicionales representan 15–23 minutos de lectura, más el tiempo de anotación. Reservar 20 minutos dentro de S15 requiere verificar que alcance el tiempo para Tugan y Luxemburg. Si no alcanza, la ficha se discute de manera asincrónica.

*Alternativa intensiva.* Cuatro reuniones sobre competencia y márgenes, acumulación interna y oligopolización, capacidad e inversión, y teoría del estancamiento. Cuatro reuniones de 90 minutos sumarían seis horas sincrónicas más lecturas y preparación. Permitirían confrontar los capítulos empíricos VIII y XII con el modelo del XIII. Ubicarlas después de Kalecki exigiría conseguir tiempo adicional antes de Minsky, en semanas que ya incluyen una conmemoración o reuniones dobles. Su adopción requiere un calendario y responsables aceptados. El diseño integrado conserva todos los encuentros existentes.

== Lerner × Kalecki 1943 · Pleno empleo

*Lecturas:* Lerner, “Functional Finance and the Federal Debt”; Kalecki, “Political Aspects of Full Employment”.

Operación: distinguir dos preguntas.

- Lerner: ¿qué instrumentos y criterios hacen macroeconómicamente posible sostener el pleno empleo?
- Kalecki: ¿qué condiciones políticas y sociales permiten sostenerlo?

*Resultado buscado:* posibilidad macroeconómica y viabilidad político-institucional no son la misma proposición.

== Lerner 1947 + Knapp · Dinero y Estado

*Lecturas:* Lerner, “Money as a Creature of the State”; selección de Knapp, _The State Theory of Money_.

La sesión mantendrá separadas cuatro proposiciones: el Estado define o acepta una unidad monetaria; los impuestos pueden contribuir a generar demanda por la moneda; el emisor posee capacidades fiscales específicas; y la política fiscal puede regirse por un criterio funcional de pleno empleo. Ninguna de ellas será utilizada como demostración automática de las demás.

== Minsky · ¿Qué cambia cuando la inversión es financiada?

*Lecturas primarias:* _John Maynard Keynes_; “The Capital Development of the Economy and the Structure of Financial Institutions”.

Operación: ampliar el objeto de la inversión desde el gasto hacia la estructura financiera creada por su financiación.

$ D_t^I arrow.r F_t arrow.r I_(t+tau) $
$ F_t arrow.r L_t $
$ L_t arrow.r ("PC"_(t+1), dots, "PC"_(t+n)) $

#box(
  [Pregunta],
  [¿Qué información nueva necesitamos cuando una decisión de inversión crea compromisos de pago que sobreviven al momento del gasto?]
)

== Kalecki → Minsky · Beneficios y estructura financiera

*Lecturas:* Minsky, “The Relevance of Kalecki”; Piacentini, “Minsky after Kalecki”.

La transición no se formulará como si Minsky hubiera “descubierto” la financiación después de Kalecki. El objeto se reconstruirá como:

$ "Keynes: finance/funding" + "Kalecki: beneficios, fondos internos, riesgo" arrow.r "Minsky: estructura financiera de la inversión" $

== Minsky · Financiación y fragilidad

*Lecturas:* _Stabilizing an Unstable Economy_; Nikolaidi y Stockhammer como reconstrucción secundaria.

La pregunta central será la validación de compromisos:

$ "CF"_(t+s) ⋚ "PC"_(t+s) $

Los flujos futuros dependen de la trayectoria macroeconómica, por lo que la estructura financiera no puede evaluarse exclusivamente en el instante en que se contrata.

== Wray 2018 · Lerner, Minsky y balance

*Lectura:* Wray, “Functional Finance: A Comparison of the Evolution of the Positions of Hyman Minsky and Abba Lerner”.

Operación: utilizar el texto como reconstrucción comparativa, no como sustituto de las fuentes primarias.

#box(
  [Pregunta de cierre],
  [¿Qué problemas quedan efectivamente abiertos después de Keynes, Hicks, Kalecki, Lerner y Minsky, y cuáles de ellos justifican introducir en un segundo semestre dinero endógeno, SFC, MMT y las instituciones monetarias de México y América Latina?]
)

= Calendario maestro enero–junio

#table(
  columns: (20%, 50%, 30%),
  table.header([*Semana*], [*Núcleo CLEP*], [*Especial / colaboración*]),
  [11–17 ene.], [Treatise 1 · caps. 1–3], [#status-fixed],
  [18–24 ene.], [Treatise 2 · caps. 9–11], [#status-fixed],
  [25–31 ene.], [Treatise 3 · caps. 13–15], [#status-fixed],
  [1–7 feb.], [Treatise 4 · caps. 25–27], [Conmemoración propuesta],
  [8–14 feb.], [Treatise 5 · caps. 31–33], [#status-fixed],
  [15–21 feb.], [Keynes 1933], [REDEFFIM I · #status-open],
  [22–28 feb.], [GT · demanda efectiva], [#status-prov],
  [1–7 mar.], [GT · ahorro, inversión e ingreso], [#status-prov],
  [8–14 mar.], [Lerner + Champernowne], [#status-prov],
  [15–21 mar.], [Síntesis Keynes], [REDEFFIM II · #status-open],
  [22–28 mar.], [Keynes → Hicks], [#status-prov],
  [29 mar.–4 abr.], [Hicks 1937 · lectura], [#status-prov],
  [5–11 abr.], [Hicks 90], [REDEFFIM III · #status-open],
  [12–18 abr.], [Hicks · cierre y determinación], [#status-prov],
  [19–25 abr.], [SI/LL → IS-LM], [#status-prov],
  [26 abr.–2 may.], [IS-LM moderno + Hicks 1980–81], [#status-prov],
  [3–9 may.], [Kalecki · beneficios], [#status-prov],
  [10–16 may.], [Kalecki · inversión], [REDEFFIM IV · #status-open],
  [17–23 may.], [Kalecki · tiempo y ciclo], [#status-prov],
  [24–30 may.], [Tugan/Luxemburg → Kalecki; ficha de transición a Steindl], [#status-prov],
  [31 may.–6 jun.], [Keynes · tasa de interés 90], [REDEFFIM V · #status-open],
  [7–13 jun.], [Lerner × Kalecki 1943], [2.ª sesión: Lerner 1947 + Knapp · #status-prov],
  [14–20 jun.], [Minsky · financiación], [2.ª sesión: Kalecki → Minsky · #status-prov],
  [21–27 jun.], [Minsky · fragilidad], [2.ª sesión: Wray 2018 + balance · #status-prov],
)

El calendario distingue el prólogo de enero, el desarrollo principal de febrero a mayo y un cierre intensivo de CLEP en junio. Las semanas dobles significan dos reuniones separadas, no la compresión de dos problemas en una sola sesión.

= Vinculación académica

- *Observación académica.* Recibir el programa, materiales, convocatorias y resultados, sin compromiso de asistencia.
- *Participación abierta.* Incorporarse voluntariamente a los círculos de lectura y a la discusión de los textos elegidos.
- *Colaboración especializada.* Proponer una conferencia, comentar bibliografía, presentar una investigación o discutir un documento de trabajo en una mesa académica.

Cada modalidad admite una intervención puntual y preserva la independencia institucional y teórica de las personas participantes. La participación es a título elegido por cada persona y carece de obligación de permanencia.

*Vinculación académica* · Raúl Alberto Rivera Boullosa \
#link("mailto:boullosaraul@gmail.com")[boullosaraul\@gmail.com] · #link("https://clep.lat/participa/")[clep.lat/participa]

= REDEFFIM × CLEP

La posible interlocución con REDEFFIM se plantea como contraste con problemas que CLEP ya habrá construido. Los invitados no son incorporados para impartir introducciones generales a sus áreas, sino para mostrar cómo su investigación trata una pregunta alcanzada por el seminario.

#table(
  columns: (15%, 31%, 27%, 27%),
  [*Ventana*], [*Problema*], [*Perfil / candidatos preliminares*], [*Estado*],
  [Febrero], [¿Qué significa hoy economía monetaria de producción?], [Monika Meireles u otro perfil sugerido por la red], [#status-open],
  [Marzo], [¿Qué cambia cuando cambia la arquitectura institucional monetaria?], [César Duarte / historia y teoría monetaria], [#status-open],
  [Abril], [¿Qué construyó Hicks y cómo llegó a representar a Keynes?], [Daniel Mirón + César Duarte, formato mesa], [#status-open],
  [Mayo], [¿Cómo condiciona la estructura financiera a la inversión?], [Claudia Maya / Alejandro López Bolaños / Gregorio Vidal], [#status-open],
  [Junio], [¿Qué determina la tasa de interés y cómo conduce el problema hacia la fragilidad?], [Patricia Rodríguez López; posible articulación con Alicia Girón], [#status-open],
)

#box(
  [Nota de estado],
  [Los nombres anteriores son candidatos por afinidad temática. No representan invitaciones enviadas, aceptación ni programación confirmada. La coordinación de REDEFFIM podrá sugerir perfiles más adecuados.]
)

== Protocolo para cada invitación

CLEP preparará una hoja de una página con:

- el punto exacto del recorrido en que se encuentra el seminario;
- las lecturas ya realizadas;
- la construcción o relaciones disponibles;
- dos o tres preguntas abiertas;
- la función esperada de la intervención.

El criterio para una eventual invitación será: *no pedir una introducción general al tema*. La intervención deberá permitir comparar la construcción del seminario con investigación contemporánea y establecer qué cambia al introducir evidencia, instituciones o mecanismos adicionales.

= Bibliografía maestra

La exigencia se registra por selección. El Treatise se propone como obligatorio, los dos textos de febrero y el pasaje breve de Steindl como contraste para participantes. Las demás fuentes conservan la función indicada y su exigencia se acordará por ficha antes de la convocatoria.

Las etiquetas indican función dentro del programa:

[P] fuente primaria; [R] reconstrucción o contraste; [F] formalización; [A] ampliación; [E] aplicación empírica.

== Keynes y recepción

[P] Keynes, J. M. (1930). _A treatise on money_ (Vols. 1–2). Macmillan.

[P] Keynes, J. M. (1933). A monetary theory of production. In G. Clausing (Ed.), _Der Stand und die nächste Zukunft der Konjunkturforschung: Festschrift für Arthur Spiethoff_ (pp. 123–125). Duncker & Humblot.

[P] Keynes, J. M. (1936). _The general theory of employment, interest and money_. Macmillan.

[P] Keynes, J. M. (1937a). The general theory of employment. _The Quarterly Journal of Economics, 51_(2), 209–223. https://doi.org/10.2307/1882087

[P] Keynes, J. M. (1937b). Alternative theories of the rate of interest. _The Economic Journal, 47_(186), 241–252. https://doi.org/10.2307/2225525

[R] Champernowne, D. G. (1936). Unemployment, basic and monetary: The classical analysis and the Keynesian. _The Review of Economic Studies, 3_(3), 201–216. https://doi.org/10.2307/2967628

[R] Harrod, R. F. (1937). Mr. Keynes and traditional theory. _Econometrica, 5_(1), 74–86. https://doi.org/10.2307/1905402

[R] Lerner, A. P. (1936). Mr. Keynes’ “General theory of employment, interest and money.” _International Labour Review, 34_(4), 435–454.

[R] Meade, J. E. (1937). A simplified model of Mr. Keynes’ system. _The Review of Economic Studies, 4_(2), 98–107. https://doi.org/10.2307/2967607

== Hicks e IS-LM

[P] Hicks, J. R. (1937). Mr. Keynes and the “Classics”: A suggested interpretation. _Econometrica, 5_(2), 147–159. https://doi.org/10.2307/1907242

[P] Hicks, J. R. (1980–1981). “IS-LM”: An explanation. _Journal of Post Keynesian Economics, 3_(2), 139–154. https://doi.org/10.1080/01603477.1980.11489209

[R] León León, M. J. (1999). Los modelos keynesianos de Hicks: Evaluación y crítica. _Investigación Económica, 59_(229), 37–73.

[R] Liquitaya Briceño, J. D. (2000). Los libros de texto y la enseñanza del modelo IS-LM. _Denarius_, (2).

[R] Lizarazu Alanez, E. (2006). La macroeconomía IS-LM: Una retrospección teorética estilizada. _Investigación Económica, 65_(256), 103–129.

[R] Lizarazu Alanez, E., & Liquitaya Briceño, J. D. (2004). Una nueva valoración del modelo SI/LL de Hicks. _Denarius_, (9).

[R] Mitchell, W., Wray, L. R., & Watts, M. (2019). _Macroeconomics_. Red Globe Press. Cap. 28.

== Kalecki

[P] Kalecki, M. (1937a). A theory of the business cycle. _The Review of Economic Studies, 4_(2), 77–97. https://doi.org/10.2307/2967606

[P] Kalecki, M. (1937b). The principle of increasing risk. _Economica, 4_(16), 440–447. https://doi.org/10.2307/2626879

[P] Kalecki, M. (1943). Political aspects of full employment. _The Political Quarterly, 14_(4), 322–330. https://doi.org/10.1111/j.1467-923X.1943.tb01016.x

[P] Kalecki, M. (1954). _Theory of economic dynamics: An essay on cyclical and long-run changes in capitalist economy_. George Allen & Unwin.

[P] Kalecki, M. (1967). Zagadnienie realizacji u Tugana-Baranowskiego i Róży Luksemburg. _Ekonomista_, (2), 241–249. Versión inglesa en _Selected Essays_ (1971), cap. 13, pp. 146–155.

[A] Kalecki, M. (1968). Trend and business cycles reconsidered. _The Economic Journal, 78_(310), 263–276. https://doi.org/10.2307/2229463

[P] Kalecki, M. (1971). _Selected essays on the dynamics of the capitalist economy, 1933–1970_. Cambridge University Press.

[P] Kalecki, M. (1973). _Teoría de la dinámica económica: Ensayo sobre los movimientos cíclicos y a largo plazo de la economía capitalista_. Fondo de Cultura Económica.

== Steindl e interlocución marxiana

[P] Steindl, J. (1952). _Maturity and Stagnation in American Capitalism_. Basil Blackwell. Reimpresión con introducción nueva, Monthly Review Press, 1976. Edición española: _Madurez y estancamiento en el capitalismo norteamericano_, Siglo XXI, 1979, ISBN 968-23-0449-0.

[P] Marx, K. _El capital. Crítica de la economía política_, libros I, II y III (primeras ediciones alemanas, 1867, 1885 y 1894). Identificar la edición de trabajo en cada ficha. Los libros II y III fueron editados por Friedrich Engels.

== Guía de capítulos de Steindl

El original inglés (Oxford, Basil Blackwell, 1952) consta de dos partes. La reimpresión de Monthly Review Press (1976) añade una introducción. La traducción de Siglo XXI (México, 1979) incorpora esa introducción. El cuadro identifica todos los capítulos mediante descripciones abreviadas y señala su función docente. La numeración de capítulos permite trabajar entre idiomas. Las páginas citadas en las fichas corresponden exclusivamente a la edición indicada.

#table(columns: (10%, 50%, 40%), inset: 4pt,
table.header([*Cap.*],[*Contenido*],[*Uso en el seminario*]),
[I],[Teoría de la competencia imperfecta],[Crítica de las teorías de precios],
[II],[Concepto de capacidad excedente],[Distinguir reserva planeada y exceso],
[III],[Rigidez de precios],[Comparar respuestas al cambio de demanda],
[IV],[Diferencias de costes],[Heterogeneidad de las empresas],
[V],[Competencia dentro de una industria],[Contrastar entrada fácil y difícil],
[VI],[Costes de venta y competencia en calidad],[Vías de competencia distintas del precio],
[VII],[Competencia de capitales entre industrias],[Paso entre escalas],
[VIII],[Márgenes de beneficio en la manufactura estadounidense],[Contraste empírico por rama],
[IX],[Acumulación interna de fondos en el conjunto de la economía],[Márgenes, ahorro y utilización],
[X],[Consecuencias de la capacidad excedente indeseada],[Hipótesis de respuesta de la inversión],
[XI],[Sociedades por acciones y mercado de capitales],[Distribución y movilidad de fondos],
[XII],[Acumulación en Estados Unidos, 1869–1939],[Series, medición y punto de inflexión],
[XIII],[Teoría de la inversión a largo plazo],[Comparar dos hipótesis de utilización],
[XIV],[Marx y la acumulación del capital],[Rentabilidad, subconsumo y crisis])

Los capítulos I–VIII integran la parte sobre precios, costes y márgenes. IX–XIV componen la parte sobre acumulación. Para orientar una lectura en español: II comienza en p. 32; V en p. 70; IX en p. 155; XII en p. 214; XIII en p. 258; XIV en p. 301. El índice español cierra con las listas de cuadros y figuras. Los contrastes empíricos históricos se leerán atendiendo al periodo y a la unidad de observación.

== Lerner y Knapp

[P] Knapp, G. F. (1924). _The state theory of money_ (H. M. Lucas & J. Bonar, Trans.; Abridged ed.). Macmillan. (Original work published 1905).

[P] Lerner, A. P. (1943). Functional finance and the federal debt. _Social Research, 10_(1), 38–51.

[P] Lerner, A. P. (1947). Money as a creature of the state. _The American Economic Review, 37_(2), 312–317.

== Minsky

[P] Minsky, H. P. (1975). _John Maynard Keynes_. Columbia University Press.

[P] Minsky, H. P. (1986). _Stabilizing an unstable economy_. Yale University Press.

[P] Minsky, H. P. (1992). _The capital development of the economy and the structure of financial institutions_ (Working Paper No. 72). Levy Economics Institute of Bard College.

[P] Minsky, H. P. (2013). The relevance of Kalecki: The useable contribution. _PSL Quarterly Review, 66_(265), 95–106. https://doi.org/10.13133/2037-3643/10411

[P] Minsky, H. P. (2019). Los factores financieros en la teoría económica del capitalismo. _El Trimestre Económico, 86_(344), 1071–1092. https://doi.org/10.20430/ete.v86i344.889

== Reconstrucciones y formalizaciones Kalecki–Minsky

[F] Fazzari, S., Ferri, P., & Greenberg, E. (2008). Cash flow, investment, and Keynes–Minsky cycles. _Journal of Economic Behavior & Organization, 65_(3–4), 555–572. https://doi.org/10.1016/j.jebo.2005.11.007

[R] Nikolaidi, M., & Stockhammer, E. (2017). Minsky models: A structured survey. _Journal of Economic Surveys, 31_(5), 1304–1331. https://doi.org/10.1111/joes.12222

[R] Piacentini, P. M. (2021). Minsky after Kalecki: Real profits and financial structure. _Structural Change and Economic Dynamics, 59_, 416–426. https://doi.org/10.1016/j.strueco.2021.09.010

[F] Reissl, S. (2020). Minsky from the bottom up: Formalising the two-price model of investment in a simple agent-based framework. _Journal of Economic Behavior & Organization, 177_, 109–142. https://doi.org/10.1016/j.jebo.2020.06.012

[R] Mazzucato, M., & Wray, L. R. (2015). _Financing the capital development of the economy: A Keynes-Schumpeter-Minsky synthesis_ (Working Paper No. 837). Levy Economics Institute of Bard College.

[R] Wray, L. R. (2018). _Functional finance: A comparison of the evolution of the positions of Hyman Minsky and Abba Lerner_ (Working Paper No. 900). Levy Economics Institute of Bard College.

== Dossier de la controversia de 1937

[A] Ohlin, B. (1937). Some notes on the Stockholm theory of savings and investments II. _The Economic Journal, 47_(186), 221–240. https://doi.org/10.2307/2225524

[A] Lerner, A. P. (1937). Statics and dynamics in socialist economics. _The Economic Journal, 47_(186), 253–270. https://doi.org/10.2307/2225526

[A] Reddaway, W. B. (1937). Special obstacles to full employment in a wealthy community. _The Economic Journal, 47_(186), 297–307. https://doi.org/10.2307/2225529

[A] Ohlin, B., Robertson, D. H., & Hawtrey, R. G. (1937). Alternative theories of the rate of interest: Three rejoinders. _The Economic Journal, 47_(187), 423–443. https://doi.org/10.2307/2225356

= Fronteras del programa y 2027-II

El programa termina cuando la reconstrucción Keynes–Hicks–Kalecki–Steindl–Lerner–Minsky permite formular con precisión los problemas que requieren un objeto monetario e institucional más amplio. No se introducirán esos objetos antes de que la insuficiencia haya quedado localizada.

Quedan fuera del núcleo de 2027-I:

- reconstrucción sistemática de dinero endógeno;
- horizontalismo y circuitismo como bloques propios;
- modelos stock-flow consistent;
- Modern Monetary Theory como construcción completa;
- relaciones Tesoro–banco central;
- sistema de reservas y pagos aplicado a México;
- tipo de cambio y restricción externa;
- estructura productiva y restricciones reales;
- aplicación sistemática a México y América Latina.

Secuencia provisional para 2027-II:

$ "dinero endógeno" arrow.r "horizontalismo/circuitismo" arrow.r "SFC" arrow.r "MMT" arrow.r "México/América Latina" $

= Registro de decisiones

#table(
  columns: (18%, 48%, 34%),
  [*Fecha*], [*Decisión*], [*Estado / razón*],
  [31-oct-2026], [El _Treatise_ se trabaja en cinco sesiones y no se reduce a una introducción.], [Congelada],
  [31-oct-2026], [2027-I recorre Keynes → Hicks/Kalecki/Lerner → Minsky.], [Congelada],
  [31-oct-2026], [MMT + México/AL se desplazan a una segunda fase.], [Congelada · evita comprimir el primer semestre],
  [31-oct-2026], [Las efemérides de 1937 funcionan como anclas temporales.], [Congelada],
  [31-oct-2026], [REDEFFIM se integra en problemas del programa, no como ciclo paralelo.], [Congelada como criterio; invitados por confirmar],
  [31-oct-2026], [Las semanas dobles contienen reuniones separadas.], [Congelada],
)

= Seguimiento y devolución académica

Antes de cada encuentro, la coordinación registra edición, pasaje, exigencia, pregunta y tiempo presupuestado. Al cierre, la relatoría conserva argumento, supuesto en discusión, evidencia disponible y pregunta abierta. El contraste entre carga prevista y tiempo reportado orienta el siguiente ajuste. Asistencia, entrega de fichas y voluntad de colaborar se registran por separado.

Al finalizar cada bloque se prevén guías, reconstrucciones conceptuales y matemáticas, bibliografías y síntesis. Los grupos podrán desarrollar documentos de trabajo o materiales audiovisuales. La difusión de registros o aportaciones identificables requiere consentimiento. La continuidad se decidirá con base en preguntas abiertas, materiales terminados y disponibilidad de quienes acepten coordinar.

= Próximas operaciones

Para convertir la propuesta de distribución en compromisos colectivos, la coordinación documentará las siguientes operaciones pendientes:

1. clasificar cada lectura como obligatoria, contraste o ampliación;
2. estimar páginas y carga semanal;
3. cerrar una pregunta, un resultado esperado y una dificultad de salida para cada sesión;
4. preparar el memo institucional de una página para REDEFFIM.

#box(
  [Criterio de avance],
  [No añadir actividades hasta comprobar cuánto cabe realmente. El siguiente progreso del programa consiste en convertir la arquitectura existente en una secuencia de lectura ejecutable.]
)
