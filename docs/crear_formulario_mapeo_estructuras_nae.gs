/**
 * Crea el Google Form definitivo:
 * "Formulario V1 · Mapeo de estructuras de apoyo a los NAE"
 *
 * Decisiones de implementación:
 * 1. Se conservan la numeración, el texto y la obligatoriedad de la encuesta aprobada.
 * 2. Provincia y municipio se implementan mediante secciones, para impedir combinaciones incorrectas.
 * 3. La pregunta 1.3 permanece abierta, exactamente como fue aprobada.
 * 4. Las tablas de captura libre (3.2, 4.2 y 8.3) se representan mediante filas repetidas,
 *    porque Google Forms no admite tablas con campos de texto editables.
 * 5. La pregunta 8.2 se muestra únicamente cuando en 8.1 se responde "Sí".
 * 6. Se añaden textos de ayuda para separar por comas cuando una respuesta puede contener varios valores.
 *
 * Ejecute crearFormularioMapeoNAE() desde Google Apps Script.
 */

function crearFormularioMapeoNAE() {
  const form = FormApp.create('Formulario V1 · Mapeo de estructuras de apoyo a los NAE');

  form.setDescription(
    'FORMULARIO V1 DE MAPEO DE ESTRUCTURAS DE APOYO A LOS NAE\n\n' +
    'Proyecto “Apoyo a Nuevos Actores Económicos para una diversificación económica, innovativa y sostenible”\n\n' +
    'Versión integrada a partir de comentarios de revisión · Julio de 2026\n\n' +
    'Propósito del formulario\n\n' +
    'Identificar y caracterizar las estructuras de apoyo existentes para los Nuevos Actores Económicos (NAE) en el país. ' +
    'Se entiende por estructuras de apoyo aquellas instituciones, entidades, organizaciones, plataformas, iniciativas, espacios o personas expertas que ofrecen servicios de desarrollo empresarial, formación, asesoramiento, acompañamiento técnico, acceso a financiamiento, articulación, encadenamientos productivos u otros apoyos orientados al fortalecimiento de los NAE.\n\n' +
    'La información recopilada permitirá elaborar un diagnóstico nacional y territorial de capacidades, servicios, brechas, recursos e infraestructura de apoyo a los NAE. ' +
    'También servirá de base para un mapa digital interactivo y un directorio PDF offline donde los NAE puedan localizar quién ofrece qué servicio, en qué territorio y mediante qué canales de contacto.\n\n' +
    'Este formulario está dirigido a instituciones públicas, universidades, centros de formación, organizaciones territoriales, iniciativas no estatales, proyectos de desarrollo local, MIPYMES, trabajadores por cuenta propia, consultores/as, expertos/as, ONGs, redes de emprendedores y otros actores que presten o puedan prestar servicios de apoyo a los NAE a nivel municipal, provincial o nacional.\n\n' +
    'Tiempo estimado de llenado: 10–15 minutos. Los campos marcados con (*) son obligatorios.\n\n' +
    'Al completar este formulario, autoriza el uso de la información facilitada para fines de diagnóstico, mapeo, directorio y comunicación del proyecto NAE. ' +
    'Para consultas sobre el formulario, puede escribir a: denys.buedo@gmail.com.\n\n' +
    'NOTA: las preguntas señaladas con asterisco (*) son OBLIGATORIAS.'
  );

  form.setCollectEmail(false);
  form.setAllowResponseEdits(false);
  form.setShowLinkToRespondAgain(false);
  form.setProgressBar(true);
  form.setConfirmationMessage(
    '¡Agradecemos mucho su tiempo y contribución a este diagnóstico nacional de estructuras de apoyo a los NAE!'
  );

  const spreadsheet = SpreadsheetApp.create(
    'Respuestas · Formulario V1 · Mapeo de estructuras de apoyo a los NAE'
  );
  form.setDestination(FormApp.DestinationType.SPREADSHEET, spreadsheet.getId());

  // ---------------------------------------------------------------------------
  // BLOQUE 0 – INTRODUCCIÓN
  // ---------------------------------------------------------------------------
  form.addPageBreakItem().setTitle('Bloque 0 – Introducción');

  form.addTextItem()
    .setTitle('0.1* Entidad a la que pertenece')
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('0.2* Rol principal en la entidad')
    .setChoiceValues([
      'Dirección / coordinación',
      'Técnico/a',
      'Docente / formador/a',
      'Investigador/a',
      'Representante de MIPYME, TCP, cooperativa o PDL'
    ])
    .showOtherOption(true)
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('0.3* Municipio sobre el que responde')
    .setChoiceValues([
      'Municipio donde trabaja habitualmente',
      'Municipio donde la entidad presta servicios',
      'Municipio donde reside'
    ])
    .showOtherOption(true)
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('0.4* Nivel de conocimiento sobre los NAE en el municipio')
    .setChoiceValues(['Alto', 'Medio', 'Bajo'])
    .setRequired(true);

  form.addSectionHeaderItem()
    .setTitle('0.5* Datos de contacto directo para el mapa y el directorio')
    .setHelpText(
      'Indique datos que puedan publicarse o utilizarse para contactar con la estructura de apoyo.'
    );

  form.addTextItem()
    .setTitle('Dirección física exacta')
    .setHelpText('Si dispone de más de una dirección, sepárelas por comas.')
    .setRequired(true);

  form.addTextItem()
    .setTitle('Teléfono(s)')
    .setHelpText('Si dispone de más de un teléfono, sepárelos por comas. Ejemplo: +53 52123456, +53 72234567.')
    .setRequired(true);

  form.addTextItem()
    .setTitle('Correo electrónico')
    .setHelpText('Si dispone de más de un correo electrónico, sepárelos por comas.')
    .setRequired(true);

  form.addTextItem()
    .setTitle('Sitio web')
    .setHelpText('Si dispone de más de un sitio web, sepárelos por comas.')
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('Redes sociales')
    .setHelpText('Si dispone de varias redes sociales, sepárelas por comas. Indique el nombre de la red y el usuario o enlace.')
    .setRequired(true);

  form.addTextItem()
    .setTitle('Persona de contacto y cargo')
    .setHelpText('Si dispone de más de una persona de contacto, sepárelas por comas.')
    .setRequired(true);

  // ---------------------------------------------------------------------------
  // SECCIÓN 1 – PROVINCIA Y MUNICIPIO CON RAMIFICACIÓN
  // ---------------------------------------------------------------------------
  form.addPageBreakItem()
    .setTitle('Sección 1 – Identificación territorial, cobertura e institucional');

  const divisionPolitica = getDivisionPoliticaAdministrativa();

  const provinciaItem = form.addMultipleChoiceItem()
    .setTitle('1.1* Provincia')
    .setHelpText(
      'Seleccione la provincia. Al pulsar “Siguiente” se mostrarán únicamente sus municipios.'
    )
    .setRequired(true);

  const seccionesMunicipios = {};

  Object.keys(divisionPolitica).forEach(function(provincia) {
    const seccionMunicipio = form.addPageBreakItem()
      .setTitle('1.2 Municipio de ' + provincia);

    form.addListItem()
      .setTitle('1.2* Municipio donde se ubica la entidad o estructura de apoyo — ' + provincia)
      .setChoiceValues(divisionPolitica[provincia])
      .setRequired(true);

    seccionesMunicipios[provincia] = seccionMunicipio;
  });

  const continuacionSeccion1 = form.addPageBreakItem()
    .setTitle('Sección 1 – Identificación territorial, cobertura e institucional (continuación)');

  Object.keys(seccionesMunicipios).forEach(function(provincia) {
    seccionesMunicipios[provincia].setGoToPage(continuacionSeccion1);
  });

  provinciaItem.setChoices(
    Object.keys(divisionPolitica).map(function(provincia) {
      return provinciaItem.createChoice(provincia, seccionesMunicipios[provincia]);
    })
  );

  form.addParagraphTextItem()
    .setTitle('1.3* Municipios o territorios donde presta servicios a NAE')
    .setHelpText(
      'Incluya municipios atendidos actualmente y, si corresponde, territorios que podría atender en el futuro. Si son varios municipios o territorios, sepárelos por comas.'
    )
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('1.4* Cobertura principal de actuación')
    .setChoiceValues([
      'Municipal',
      'Provincial',
      'Regional / varios municipios o provincias',
      'Nacional',
      'Atención virtual sin límite territorial claro'
    ])
    .showOtherOption(true)
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('1.5* Modalidad principal de atención a NAE')
    .setChoiceValues([
      'Presencial',
      'Virtual',
      'Mixta presencial-virtual',
      'Atiende bajo demanda o por proyecto',
      'No presta servicios actualmente, pero podría hacerlo'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('1.6* Tipo de entidad o estructura de apoyo')
    .setChoiceValues([
      'Dirección de Desarrollo Municipal (DDM)',
      'Dirección de Desarrollo Territorial (DDT)',
      'Centro Universitario Municipal (CUM)',
      'Universidad o centro académico',
      'Centro de estudios o investigación',
      'Centro de capacitación',
      'Entidad tecnológica (Joven Club u otras)',
      'Organización empresarial o asociación económica',
      'Proyecto de Desarrollo Local (PDL)',
      'MIPYME que presta servicios a otros negocios (B2B)',
      'Trabajador/a por cuenta propia con servicios especializados',
      'ONG, organización social o red de emprendedores',
      'Entidad financiera, banco o programa de financiamiento',
      'Cooperativa',
      'Empresa estatal con servicios de apoyo'
    ])
    .showOtherOption(true)
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('1.7* ¿La entidad presta actualmente servicios de apoyo a NAE?')
    .setChoiceValues([
      'Sí, de forma regular',
      'Sí, de forma ocasional',
      'Ha participado en actividades puntuales',
      'No presta servicios actualmente, pero tiene capacidad o interés para hacerlo',
      'No aplica'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('1.8* Nivel de involucramiento en la prestación de servicios de apoyo a NAE')
    .setChoiceValues([
      'Alto: presta servicios de manera regular',
      'Medio: presta servicios ocasionales',
      'Bajo: ha participado en actividades puntuales',
      'Nulo: no presta servicios actualmente, pero podría hacerlo',
      'No aplica'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('1.9 Cantidad aproximada de NAE atendidos en los últimos 12 meses')
    .setChoiceValues(['0', '1–10', '11–30', '31–50', 'Más de 50', 'No sabe / no registra'])
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle('1.10 Desde cuándo presta servicios de apoyo a NAE')
    .setChoiceValues([
      'Menos de 1 año',
      '1–3 años',
      'Más de 3 años',
      'Solo por proyectos puntuales',
      'No aplica / no sabe'
    ])
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle('1.11 ¿Tiene capacidad para atender NAE de otros municipios o ampliar cobertura?')
    .setChoiceValues([
      'Sí, con capacidad actual',
      'Sí, pero requiere recursos adicionales',
      'Solo con apoyo externo o alianzas',
      'No',
      'No sabe'
    ])
    .setRequired(false);

  // ---------------------------------------------------------------------------
  // SECCIÓN 2 – SERVICIOS
  // ---------------------------------------------------------------------------
  form.addPageBreakItem().setTitle('Sección 2 – Servicios de apoyo a NAE');

  form.addCheckboxGridItem()
    .setTitle('2.1* Servicios que ofrece la entidad y servicios que necesita fortalecer')
    .setHelpText(
      'Marque “ofrece” si la entidad ya presta el servicio y “requiere fortalecer” si necesita mejorar capacidades para prestarlo.'
    )
    .setRows([
      'Gestión empresarial',
      'Asesoría legal o normativa',
      'Asesoría contable y financiera',
      'Acompañamiento para formalización',
      'Asistencia técnica productiva',
      'Mentoría empresarial',
      'Incubación, aceleración o acompañamiento intensivo',
      'Acceso a financiamiento o preparación para financiamiento',
      'Encadenamientos productivos y articulación con proveedores/clientes',
      'Comercialización y ventas',
      'Marketing, comunicación y posicionamiento',
      'Digitalización y competencias digitales',
      'Innovación y mejora de productos, servicios o procesos',
      'Exportación o comercio exterior',
      'Calidad, certificaciones o normas técnicas',
      'Formulación de proyectos',
      'Economía circular, economía social o sostenibilidad',
      'Género, inclusión, juventud u otros enfoques especializados'
    ])
    .setColumns(['Ofrece actualmente', 'Requiere fortalecer'])
    .setRequired(true);

  form.addSectionHeaderItem()
    .setTitle('Otro servicio')
    .setHelpText('Complete este bloque solamente si corresponde.');

  form.addTextItem().setTitle('2.1 Otro servicio: nombre').setRequired(false);
  form.addCheckboxItem()
    .setTitle('2.1 Otro servicio: situación')
    .setChoiceValues(['Ofrece actualmente', 'Requiere fortalecer'])
    .setRequired(false);

  form.addCheckboxItem()
    .setTitle('2.2* Tipo de NAE a los que presta o puede prestar apoyo')
    .setChoiceValues([
      'MIPYMES privadas',
      'MIPYMES estatales',
      'Cooperativas no agropecuarias',
      'Cooperativas agropecuarias',
      'Trabajadores/as por cuenta propia',
      'Proyectos de Desarrollo Local',
      'Empresas estatales',
      'Mujeres emprendedoras',
      'Jóvenes emprendedores/as'
    ])
    .showOtherOption(true)
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('2.3 Frecuencia habitual de los servicios')
    .setChoiceValues([
      'Semanal',
      'Mensual',
      'Trimestral',
      'Anual',
      'Bajo demanda',
      'Por proyectos puntuales',
      'No aplica'
    ])
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle('2.4 ¿Los servicios son gratuitos, de pago o mixtos?')
    .setChoiceValues([
      'Gratuitos',
      'De pago',
      'Mixtos',
      'Depende del proyecto o programa',
      'No aplica'
    ])
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle('2.5 ¿La entidad utiliza metodología, herramientas o protocolos propios para apoyar a los NAE?')
    .setChoiceValues([
      'Sí, metodología documentada',
      'Sí, pero no documentada',
      'Utiliza metodologías de terceros',
      'No cuenta con metodología específica',
      'No sabe'
    ])
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle('2.6 ¿Realiza seguimiento posterior a la atención o servicio prestado?')
    .setChoiceValues([
      'Sí, seguimiento sistemático',
      'Sí, seguimiento ocasional',
      'Solo en algunos programas o proyectos',
      'No realiza seguimiento',
      'No aplica'
    ])
    .setRequired(false);

  form.addParagraphTextItem()
    .setTitle('2.7 Servicios más demandados por los NAE')
    .setHelpText('Si desea indicar varios servicios, sepárelos por comas.')
    .setRequired(false);

  form.addParagraphTextItem()
    .setTitle('2.8 Servicios que funcionan mejor actualmente y por qué')
    .setHelpText('Si desea indicar varios servicios, sepárelos por comas.')
    .setRequired(false);

  form.addParagraphTextItem()
    .setTitle('2.9 Servicios que no existen o son insuficientes en el municipio')
    .setHelpText('Si desea indicar varios servicios, sepárelos por comas.')
    .setRequired(false);

  // ---------------------------------------------------------------------------
  // SECCIÓN 3 – RECURSOS E INFRAESTRUCTURA
  // ---------------------------------------------------------------------------
  form.addPageBreakItem()
    .setTitle('Sección 3 – Recursos, infraestructura y condiciones para actividades de apoyo');

  form.addMultipleChoiceItem()
    .setTitle('3.1* ¿La entidad dispone de espacios físicos para realizar actividades de apoyo a NAE?')
    .setChoiceValues([
      'Sí, adecuados para talleres, asesorías o reuniones',
      'Sí, pero requieren mejoras',
      'Espacios limitados o compartidos',
      'No dispone',
      'No aplica'
    ])
    .setRequired(true);

  form.addSectionHeaderItem()
    .setTitle('3.2* Relación de espacios disponibles o potenciales para formación, asesoría, reuniones o videoconferencias')
    .setHelpText(
      'Incluya espacios propios o aliados dentro del municipio que puedan apoyar actividades presenciales u online. ' +
      'Google Forms no permite una tabla con campos de texto; por ello se presentan cinco registros equivalentes a las cinco filas de la encuesta.'
    );

  for (let i = 1; i <= 5; i++) {
    form.addSectionHeaderItem().setTitle('3.2 Espacio ' + i);
    form.addTextItem().setTitle('3.2.' + i + '.1 Espacio').setRequired(i === 1);
    form.addTextItem().setTitle('3.2.' + i + '.2 Dirección / lugar').setRequired(i === 1);
    form.addTextItem().setTitle('3.2.' + i + '.3 Aforo aprox.').setRequired(i === 1);
    form.addTextItem().setTitle('3.2.' + i + '.4 Conectividad / tipo').setRequired(i === 1);
    form.addTextItem().setTitle('3.2.' + i + '.5 Energía alternativa').setRequired(i === 1);
    form.addTextItem().setTitle('3.2.' + i + '.6 Aire acondicionado').setRequired(i === 1);
    form.addTextItem().setTitle('3.2.' + i + '.7 Uso posible').setRequired(i === 1);
  }

  form.addMultipleChoiceItem()
    .setTitle('3.3* Disponibilidad de computadoras o recursos tecnológicos para acceso público o actividades con NAE')
    .setChoiceValues([
      'Alta: recursos suficientes y operativos',
      'Media: recursos disponibles con limitaciones',
      'Baja: pocos recursos o funcionamiento irregular',
      'Nula',
      'No sabe'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('3.4* Condiciones de conectividad')
    .setChoiceValues([
      'Buena y estable',
      'Aceptable, con limitaciones',
      'Limitada o inestable',
      'No cuenta con conectividad',
      'No sabe'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('3.5* Autonomía energética para sostener actividades presenciales u online')
    .setChoiceValues([
      'Sí, con sistemas alternativos suficientes',
      'Parcial o limitada',
      'No suele haber interrupciones relevantes',
      'No cuenta con autonomía energética',
      'No sabe'
    ])
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('3.6 Principales mejoras necesarias en infraestructura, conectividad o energía')
    .setHelpText('Si desea indicar varias mejoras, sepárelas por comas.')
    .setRequired(false);

  // ---------------------------------------------------------------------------
  // SECCIÓN 4 – EQUIPO Y CAPACIDADES
  // ---------------------------------------------------------------------------
  form.addPageBreakItem()
    .setTitle('Sección 4 – Equipo, capacidades técnicas y perfiles disponibles');

  form.addCheckboxItem()
    .setTitle('4.1* Capacidades técnicas con las que cuenta el equipo de la entidad para apoyar a los NAE')
    .setChoiceValues([
      'Gestión empresarial',
      'Contabilidad y finanzas',
      'Asesoría jurídica',
      'Marketing y ventas',
      'Digitalización',
      'Innovación',
      'Formulación de proyectos',
      'Acceso a financiamiento',
      'Encadenamientos productivos',
      'Comercio exterior',
      'Calidad, certificaciones o normas técnicas',
      'Género e inclusión',
      'Economía circular o sostenibilidad',
      'No cuenta con capacidades específicas'
    ])
    .showOtherOption(true)
    .setRequired(true);

  form.addSectionHeaderItem()
    .setTitle('4.2 Personas formadoras, mentoras o expertas disponibles para apoyar a NAE')
    .setHelpText(
      'Opcional. Indique perfiles con alta capacidad técnica y disponibilidad real, si los conoce. ' +
      'Si no identifica perfiles disponibles, deje estos campos en blanco.'
    );

  for (let i = 1; i <= 5; i++) {
    form.addTextItem()
      .setTitle('4.2 Perfil ' + i)
      .setRequired(false);
  }

  form.addCheckboxItem()
    .setTitle('4.3 Necesidades prioritarias de fortalecimiento del equipo')
    .setChoiceValues([
      'Formación de formadores',
      'Actualización normativa sobre NAE',
      'Herramientas de asesoría empresarial',
      'Gestión contable y financiera',
      'Digitalización',
      'Metodologías de mentoría o acompañamiento',
      'Seguimiento y medición de resultados',
      'Articulación interinstitucional'
    ])
    .showOtherOption(true)
    .setRequired(false);

  // ---------------------------------------------------------------------------
  // SECCIÓN 5 – DEMANDA Y BRECHAS
  // ---------------------------------------------------------------------------
  form.addPageBreakItem()
    .setTitle('Sección 5 – Demanda, brechas y pertinencia de los servicios');

  form.addCheckboxItem()
    .setTitle('5.1* Principales necesidades de los NAE en el municipio o territorio atendido')
    .setChoiceValues([
      'Información normativa y formalización',
      'Gestión empresarial',
      'Gestión financiera y contable',
      'Acceso a financiamiento',
      'Mercados y comercialización',
      'Encadenamientos productivos',
      'Digitalización',
      'Innovación',
      'Infraestructura y logística',
      'Calidad, registros o certificaciones',
      'Acompañamiento técnico sectorial'
    ])
    .showOtherOption(true)
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('5.2* Principal brecha del ecosistema de apoyo a NAE en el municipio')
    .setChoiceValues([
      'Infraestructura insuficiente',
      'Falta de servicios especializados',
      'Falta de formadores o expertos',
      'Débil coordinación institucional',
      'Recursos financieros insuficientes',
      'Baja conectividad o tecnología',
      'Falta de información actualizada sobre NAE',
      'Limitaciones regulatorias o administrativas'
    ])
    .showOtherOption(true)
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('5.3 ¿Qué actores o estructuras podrían liderar la respuesta a esa brecha?')
    .setHelpText('Si identifica varios actores o estructuras, sepárelos por comas.')
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle('5.4 Adecuación de los servicios existentes al contexto local de los NAE')
    .setChoiceValues([
      'Alta',
      'Media',
      'Baja',
      'No existen servicios suficientes',
      'No sabe'
    ])
    .setRequired(false);

  form.addParagraphTextItem()
    .setTitle('5.5 Comentarios sobre calidad, pertinencia o limitaciones de los servicios actuales')
    .setHelpText('Si desea indicar varios aspectos, sepárelos por comas.')
    .setRequired(false);

  // ---------------------------------------------------------------------------
  // SECCIÓN 6 – ARTICULACIÓN
  // ---------------------------------------------------------------------------
  form.addPageBreakItem()
    .setTitle('Sección 6 – Articulación institucional y redes de apoyo');

  form.addMultipleChoiceItem()
    .setTitle('6.1* ¿Existen mecanismos de coordinación institucional orientados al apoyo a NAE y estructuras de apoyo?')
    .setChoiceValues([
      'Sí, funcionan sistemáticamente',
      'Existen, pero con poca coordinación',
      'Se han intentado crear',
      'No existen',
      'No sabe'
    ])
    .setRequired(true);

  form.addCheckboxItem()
    .setTitle('6.2* Actores con los que coordina o podría coordinar su entidad para apoyar a los NAE')
    .setChoiceValues([
      'DDM',
      'DDT',
      'CUM',
      'Universidad',
      'ANEC',
      'Joven Club',
      'Centros de la Mujer / FMC',
      'MINCEX',
      'Bancos o entidades financieras',
      'PDL',
      'MIPYMES',
      'Cooperativas',
      'Organismos internacionales',
      'ONGs o redes de emprendedores',
      'Empresas estatales'
    ])
    .showOtherOption(true)
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('6.3 ¿Quién coordina actualmente esa articulación y cómo funciona?')
    .setHelpText('Si intervienen varios actores, sepárelos por comas.')
    .setRequired(false);

  form.addParagraphTextItem()
    .setTitle('6.4 Actividades conjuntas realizadas o previstas para apoyar a NAE')
    .setHelpText('Si son varias actividades, sepárelas por comas.')
    .setRequired(false);

  form.addMultipleChoiceItem()
    .setTitle('6.5 Nivel de articulación institucional alrededor de los servicios de apoyo a NAE')
    .setChoiceValues(['Alto', 'Medio', 'Bajo', 'Nulo', 'No sabe'])
    .setRequired(false);

  // ---------------------------------------------------------------------------
  // SECCIÓN 7 – LIMITACIONES Y SOSTENIBILIDAD
  // ---------------------------------------------------------------------------
  form.addPageBreakItem()
    .setTitle('Sección 7 – Limitaciones, sostenibilidad y actualización del mapeo');

  form.addCheckboxItem()
    .setTitle('7.1* Principales limitaciones que enfrenta la entidad para brindar servicios de apoyo a NAE')
    .setChoiceValues([
      'Falta de personal especializado',
      'Recursos financieros insuficientes',
      'Infraestructura limitada',
      'Conectividad o recursos tecnológicos insuficientes',
      'Falta de metodologías o herramientas',
      'Débil coordinación institucional',
      'Baja demanda o baja participación de NAE',
      'Limitaciones regulatorias o administrativas',
      'Falta de información actualizada sobre los NAE',
      'Falta de tiempo o sobrecarga operativa'
    ])
    .showOtherOption(true)
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('7.2* Capacidad de sostener los servicios en el tiempo')
    .setChoiceValues([
      'Alta: cuenta con recursos y organización estable',
      'Media: puede sostenerlos parcialmente',
      'Baja: depende de proyectos o apoyos externos',
      'Nula o muy limitada',
      'No sabe'
    ])
    .setRequired(true);

  form.addMultipleChoiceItem()
    .setTitle('7.3* Capacidad de mantener actualizada la información para el mapa/directorio')
    .setChoiceValues([
      'Sí, puede actualizar periódicamente',
      'Sí, si recibe una herramienta sencilla',
      'Solo con apoyo externo',
      'No tiene capacidad actual',
      'No sabe'
    ])
    .setRequired(true);

  form.addParagraphTextItem()
    .setTitle('7.4 Apoyos necesarios para mejorar la sostenibilidad de la estructura de apoyo')
    .setHelpText('Si requiere varios apoyos, sepárelos por comas.')
    .setRequired(false);

  // ---------------------------------------------------------------------------
  // SECCIÓN 8 – RAMIFICACIÓN DE 8.1 Y 8.2
  // ---------------------------------------------------------------------------
  const seccion8 = form.addPageBreakItem()
    .setTitle('Sección 8 – Servicios especializados, inclusión y recomendaciones');

  const programasEspecializadosItem = form.addMultipleChoiceItem()
    .setTitle('8.1 ¿Existen programas, centros, proyectos o servicios específicos para mujeres, jóvenes u otros grupos de NAE?')
    .setRequired(false);

  const seccionDescripcion8_2 = form.addPageBreakItem()
    .setTitle('8.2 Descripción de programas, centros, proyectos o servicios específicos');

  form.addParagraphTextItem()
    .setTitle('8.2 Si respondió “Sí”, describa cuáles son y quién los gestiona')
    .setHelpText('Si existen varios programas, centros, proyectos o servicios, sepárelos por comas.')
    .setRequired(true);

  const seccionRecomendaciones8_3 = form.addPageBreakItem()
    .setTitle('Sección 8 – Recomendaciones y observaciones finales');

  seccionDescripcion8_2.setGoToPage(seccionRecomendaciones8_3);

  programasEspecializadosItem.setChoices([
    programasEspecializadosItem.createChoice('Sí', seccionDescripcion8_2),
    programasEspecializadosItem.createChoice('No', seccionRecomendaciones8_3),
    programasEspecializadosItem.createChoice('No sabe', seccionRecomendaciones8_3)
  ]);

  form.addSectionHeaderItem()
    .setTitle('8.3 Recomiende otras estructuras de apoyo a NAE que conozca en el municipio o territorio')
    .setHelpText(
      'Opcional. Incluya nombre, tipo de servicio y datos de contacto si los tiene. ' +
      'Si no conoce otras estructuras de apoyo, deje estos campos en blanco.'
    );

  for (let i = 1; i <= 6; i++) {
    form.addSectionHeaderItem().setTitle('8.3 Estructura recomendada ' + i);
    form.addTextItem()
      .setTitle('8.3.' + i + '.1 Nombre de la estructura')
      .setRequired(false);
    form.addTextItem()
      .setTitle('8.3.' + i + '.2 Tipo de actor')
      .setRequired(false);
    form.addTextItem()
      .setTitle('8.3.' + i + '.3 Servicios que ofrece')
      .setRequired(false);
    form.addTextItem()
      .setTitle('8.3.' + i + '.4 Municipio / territorio')
      .setRequired(false);
    form.addTextItem()
      .setTitle('8.3.' + i + '.5 Contacto disponible')
      .setRequired(false);
  }

  form.addParagraphTextItem()
    .setTitle('8.4 Observaciones finales o información adicional relevante para el diagnóstico nacional')
    .setHelpText('Si desea indicar varios elementos, sepárelos por comas.')
    .setRequired(false);

  Logger.log('Formulario creado: ' + form.getEditUrl());
  Logger.log('Formulario para responder: ' + form.getPublishedUrl());
  Logger.log('Hoja de respuestas: ' + spreadsheet.getUrl());
}


/**
 * Catálogo de provincias y municipios de Cuba.
 * Se utiliza para la navegación dependiente provincia -> municipio.
 */
function getDivisionPoliticaAdministrativa() {
  return {
    'Pinar del Río': [
      'Sandino', 'Mantua', 'Minas de Matahambre', 'Viñales', 'La Palma',
      'Los Palacios', 'Consolación del Sur', 'Pinar del Río', 'San Luis',
      'San Juan y Martínez', 'Guane'
    ],
    'Artemisa': [
      'Bahía Honda', 'Mariel', 'Guanajay', 'Caimito', 'Bauta',
      'San Antonio de los Baños', 'Güira de Melena', 'Alquízar',
      'Artemisa', 'Candelaria', 'San Cristóbal'
    ],
    'La Habana': [
      'Playa', 'Plaza de la Revolución', 'Centro Habana', 'La Habana Vieja',
      'Regla', 'La Habana del Este', 'Guanabacoa', 'San Miguel del Padrón',
      'Diez de Octubre', 'Cerro', 'Marianao', 'La Lisa', 'Boyeros',
      'Arroyo Naranjo', 'Cotorro'
    ],
    'Mayabeque': [
      'Bejucal', 'San José de las Lajas', 'Jaruco', 'Santa Cruz del Norte',
      'Madruga', 'Nueva Paz', 'San Nicolás', 'Güines', 'Melena del Sur',
      'Batabanó', 'Quivicán'
    ],
    'Matanzas': [
      'Matanzas', 'Cárdenas', 'Martí', 'Colón', 'Perico', 'Jovellanos',
      'Pedro Betancourt', 'Limonar', 'Unión de Reyes', 'Ciénaga de Zapata',
      'Jagüey Grande', 'Calimete', 'Los Arabos'
    ],
    'Villa Clara': [
      'Corralillo', 'Quemado de Güines', 'Sagua la Grande', 'Encrucijada',
      'Camajuaní', 'Caibarién', 'Remedios', 'Placetas', 'Santa Clara',
      'Cifuentes', 'Santo Domingo', 'Ranchuelo', 'Manicaragua'
    ],
    'Cienfuegos': [
      'Aguada de Pasajeros', 'Rodas', 'Palmira', 'Lajas', 'Cruces',
      'Cumanayagua', 'Cienfuegos', 'Abreus'
    ],
    'Sancti Spíritus': [
      'Yaguajay', 'Jatibonico', 'Taguasco', 'Cabaiguán', 'Fomento',
      'Trinidad', 'Sancti Spíritus', 'La Sierpe'
    ],
    'Ciego de Ávila': [
      'Chambas', 'Morón', 'Bolivia', 'Primero de Enero', 'Ciro Redondo',
      'Florencia', 'Majagua', 'Ciego de Ávila', 'Venezuela', 'Baraguá'
    ],
    'Camagüey': [
      'Carlos Manuel de Céspedes', 'Esmeralda', 'Sierra de Cubitas', 'Minas',
      'Nuevitas', 'Guáimaro', 'Sibanicú', 'Camagüey', 'Florida',
      'Vertientes', 'Jimaguayú', 'Najasa', 'Santa Cruz del Sur'
    ],
    'Las Tunas': [
      'Manatí', 'Puerto Padre', 'Jesús Menéndez', 'Majibacoa',
      'Las Tunas', 'Jobabo', 'Colombia', 'Amancio'
    ],
    'Holguín': [
      'Gibara', 'Rafael Freyre', 'Banes', 'Antilla', 'Báguanos', 'Holguín',
      'Calixto García', 'Cacocum', 'Urbano Noris', 'Cueto', 'Mayarí',
      'Frank País', 'Sagua de Tánamo', 'Moa'
    ],
    'Granma': [
      'Río Cauto', 'Cauto Cristo', 'Jiguaní', 'Bayamo', 'Yara', 'Manzanillo',
      'Campechuela', 'Media Luna', 'Niquero', 'Pilón', 'Bartolomé Masó',
      'Buey Arriba', 'Guisa'
    ],
    'Santiago de Cuba': [
      'Contramaestre', 'Mella', 'San Luis', 'Segundo Frente',
      'Songo - La Maya', 'Santiago de Cuba', 'Palma Soriano',
      'Tercer Frente', 'Guamá'
    ],
    'Guantánamo': [
      'El Salvador', 'Manuel Tames', 'Yateras', 'Baracoa', 'Maisí', 'Imías',
      'San Antonio del Sur', 'Caimanera', 'Guantánamo', 'Niceto Pérez'
    ],
    'Isla de la Juventud': [
      'Isla de la Juventud'
    ]
  };
}
