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

  const body = buildBodyFromEvent(e);

  try {
    const content = sendBodyToNaeApi(body);
    clearPendingSubmission(body.id_respuesta_origen);
    Logger.log('Respuesta enviada correctamente: ' + content);
  } catch (error) {
    queuePendingSubmission(body, error);
    Logger.log('Respuesta pendiente por fallo de API: ' + body.id_respuesta_origen + ' - ' + error.message);
  }
}

function buildBodyFromEvent(e) {
  return {
    id_respuesta_origen: buildResponseId(e),
    formulario_origen: NAE_FORM_TITLE,
    fecha_respuesta: getSubmittedAt(e),
    version_encuesta: NAE_SURVEY_VERSION,
    payload: buildPayloadFromEvent(e)
  };
}

function buildBodyFromFormResponse(formResponse) {
  return {
    id_respuesta_origen: formResponse.getId(),
    formulario_origen: NAE_FORM_TITLE,
    fecha_respuesta: formResponse.getTimestamp().toISOString(),
    version_encuesta: NAE_SURVEY_VERSION,
    payload: buildPayloadFromFormResponse(formResponse)
  };
}

function sendBodyToNaeApi(body) {
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

  if (code === 409) {
    return 'Respuesta ya registrada en API: ' + body.id_respuesta_origen;
  }

  if (code < 200 || code >= 300) {
    throw new Error('NAE API respondió ' + code + ': ' + content);
  }

  return content;
}

function queuePendingSubmission(body, error) {
  const properties = PropertiesService.getScriptProperties();
  const key = pendingKey(body.id_respuesta_origen);
  const current = properties.getProperty(key);
  let attempts = 0;
  if (current) {
    try {
      attempts = JSON.parse(current).attempts || 0;
    } catch (ignored) {
      attempts = 0;
    }
  }

  properties.setProperty(key, JSON.stringify({
    body: body,
    attempts: attempts + 1,
    lastError: error && error.message ? error.message : String(error),
    updatedAt: new Date().toISOString()
  }));
}

function clearPendingSubmission(responseId) {
  PropertiesService.getScriptProperties().deleteProperty(pendingKey(responseId));
}

function pendingKey(responseId) {
  return 'NAE_PENDING_' + responseId;
}

function reenviarPendientesNae() {
  const properties = PropertiesService.getScriptProperties();
  const all = properties.getProperties();
  let sent = 0;
  let failed = 0;

  Object.keys(all).forEach(function (key) {
    if (key.indexOf('NAE_PENDING_') !== 0) {
      return;
    }

    const record = JSON.parse(all[key]);
    try {
      const content = sendBodyToNaeApi(record.body);
      properties.deleteProperty(key);
      sent += 1;
      Logger.log('Pendiente reenviado correctamente: ' + record.body.id_respuesta_origen + ' - ' + content);
    } catch (error) {
      failed += 1;
      record.attempts = (record.attempts || 0) + 1;
      record.lastError = error && error.message ? error.message : String(error);
      record.updatedAt = new Date().toISOString();
      properties.setProperty(key, JSON.stringify(record));
      Logger.log('Pendiente sigue fallando: ' + record.body.id_respuesta_origen + ' - ' + record.lastError);
    }
  });

  Logger.log('Reenvío de pendientes finalizado. Enviadas: ' + sent + '. Fallidas: ' + failed + '.');
}

function reenviarTodasLasRespuestasNae() {
  const form = FormApp.getActiveForm();
  const responses = form.getResponses();
  let sent = 0;
  let skipped = 0;
  let failed = 0;

  responses.forEach(function (formResponse) {
    const body = buildBodyFromFormResponse(formResponse);
    try {
      const content = sendBodyToNaeApi(body);
      clearPendingSubmission(body.id_respuesta_origen);
      sent += 1;
      Logger.log('Respuesta sincronizada: ' + body.id_respuesta_origen + ' - ' + content);
    } catch (error) {
      if (String(error.message || error).indexOf('409') >= 0) {
        skipped += 1;
        clearPendingSubmission(body.id_respuesta_origen);
        return;
      }
      failed += 1;
      queuePendingSubmission(body, error);
      Logger.log('No se pudo sincronizar: ' + body.id_respuesta_origen + ' - ' + error.message);
    }
  });

  Logger.log('Reenvío total finalizado. Enviadas: ' + sent + '. Ya existentes: ' + skipped + '. Fallidas: ' + failed + '.');
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
