const NAE_API_URL = 'https://nae-plataforma.mes.gob.cu/api/v1/respuestas';
const NAE_API_TOKEN = 'TU_TOKEN_REAL';
const NAE_FORM_TITLE = 'Formulario V1 · Mapeo de estructuras de apoyo a los NAE';
const NAE_SURVEY_VERSION = 'mapeo_estructuras_v1';
const NAE_SERVICE_GRID_TITLE = '2.1* Servicios que ofrece la entidad y servicios que necesita fortalecer';
const NAE_SERVICE_GRID_ROWS = [
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
];

function onFormSubmit(e) {
  if (!e) {
    throw new Error('Evento onFormSubmit no disponible');
  }

  const payload = buildPayloadFromEvent(e);
  const body = {
    id_respuesta_origen: buildResponseId(e),
    formulario_origen: NAE_FORM_TITLE,
    fecha_respuesta: getSubmittedAt(e),
    version_encuesta: NAE_SURVEY_VERSION,
    payload: payload
  };

  const response = UrlFetchApp.fetch(NAE_API_URL, {
    method: 'post',
    contentType: 'application/json',
    headers: {
      Authorization: 'Bearer ' + NAE_API_TOKEN
    },
    payload: JSON.stringify(body),
    muteHttpExceptions: true
  });

  const code = response.getResponseCode();
  const content = response.getContentText();

  if (code < 200 || code >= 300) {
    throw new Error('NAE API respondió ' + code + ': ' + content);
  }

  Logger.log('Respuesta enviada correctamente: ' + content);
}

function buildPayloadFromEvent(e) {
  if (e.namedValues) {
    return buildPayloadFromNamedValues(e.namedValues);
  }

  if (e.response) {
    return buildPayloadFromFormResponse(e.response);
  }

  throw new Error('Evento onFormSubmit sin namedValues ni response. Revise el tipo de trigger instalado.');
}

function buildPayloadFromNamedValues(namedValues) {
  const payload = {};

  Object.keys(namedValues).forEach(function (key) {
    const values = namedValues[key];
    payload[key] = normalizeEventValue(values);
  });

  return payload;
}

function buildPayloadFromFormResponse(formResponse) {
  const payload = {};
  const itemResponses = formResponse.getItemResponses();

  itemResponses.forEach(function (itemResponse) {
    const item = itemResponse.getItem();
    const title = item.getTitle();
    const response = itemResponse.getResponse();

    if (title === NAE_SERVICE_GRID_TITLE && item.getType() === FormApp.ItemType.CHECKBOX_GRID) {
      const rows = item.asCheckboxGridItem().getRows() || NAE_SERVICE_GRID_ROWS;
      rows.forEach(function (rowTitle, index) {
        const rowResponse = Array.isArray(response) ? response[index] : '';
        payload[title + ' [' + rowTitle + ']'] = normalizeEventValue(rowResponse || '');
      });
      return;
    }

    payload[title] = normalizeEventValue(response);
  });

  payload['Timestamp'] = formResponse.getTimestamp().toISOString();
  return payload;
}

function normalizeEventValue(value) {
  if (Array.isArray(value)) {
    const cleaned = value
      .map(function (item) {
        return item === null || item === undefined ? '' : String(item).trim();
      })
      .filter(function (item) {
        return item !== '';
      });

    if (cleaned.length === 0) {
      return '';
    }

    return cleaned.length === 1 ? cleaned[0] : cleaned;
  }

  return value === null || value === undefined ? '' : String(value).trim();
}

function buildResponseId(e) {
  if (e.response && e.response.getId) {
    return e.response.getId();
  }

  if (e.range && e.range.getSheet) {
    const sheet = e.range.getSheet();
    const spreadsheet = sheet.getParent();
    return spreadsheet.getId() + ':' + sheet.getSheetId() + ':row:' + e.range.getRow();
  }

  return Utilities.getUuid();
}

function getSubmittedAt(e) {
  if (e.response && e.response.getTimestamp) {
    return e.response.getTimestamp().toISOString();
  }

  if (e.namedValues) {
    const timestamp = e.namedValues['Timestamp'] || e.namedValues['Marca temporal'];
    const value = normalizeEventValue(timestamp);
    if (value) {
      const parsed = new Date(value);
      if (!isNaN(parsed.getTime())) {
        return parsed.toISOString();
      }
    }
  }

  return new Date().toISOString();
}
