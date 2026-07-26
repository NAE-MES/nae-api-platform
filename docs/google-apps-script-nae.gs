const NAE_API_URL = 'https://nae-plataforma.mes.gob.cu/api/v1/respuestas';
const NAE_API_TOKEN = 'TU_TOKEN_REAL';
const NAE_FORM_TITLE = 'Formulario V1 · Mapeo de estructuras de apoyo a los NAE';
const NAE_SURVEY_VERSION = 'mapeo_estructuras_v1';

function onFormSubmit(e) {
  if (!e || !e.namedValues) {
    throw new Error('Evento onFormSubmit no disponible');
  }

  const payload = {};
  Object.keys(e.namedValues).forEach(function (key) {
    const value = e.namedValues[key];
    payload[key] = Array.isArray(value) && value.length === 1 ? value[0] : value;
  });

  const body = {
    id_respuesta_origen: Utilities.getUuid(),
    formulario_origen: NAE_FORM_TITLE,
    fecha_respuesta: new Date().toISOString(),
    version_encuesta: detectSurveyVersion(payload),
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

function detectSurveyVersion(payload) {
  if (
    payload['0.1* Entidad a la que pertenece'] ||
    payload['0.4* Nivel de conocimiento sobre los NAE en el municipio'] ||
    payload['1.6* Tipo de entidad o estructura de apoyo'] ||
    hasKeyStartingWith(payload, '1.2* Municipio donde se ubica la entidad o estructura de apoyo')
  ) {
    return NAE_SURVEY_VERSION;
  }

  if (
    payload['0.5 Nivel de conocimiento sobre la realidad del municipio'] ||
    payload['3.4 Nivel de interés de los actores de gobierno en formación sobre NAE'] ||
    payload['4.1 Conoce la existencia de mecanismos de coordinación institucional']
  ) {
    return NAE_SURVEY_VERSION;
  }

  if (
    payload['0.4 Nivel de conocimiento sobre la realidad del municipio'] ||
    payload['4.1 Nivel de interés de los actores de gobierno en formación sobre NAE'] ||
    payload['5.1 Existencia de mecanismos de coordinación institucional']
  ) {
    return '1.1';
  }

  return NAE_SURVEY_VERSION;
}

function hasKeyStartingWith(payload, prefix) {
  return Object.keys(payload).some(function (key) {
    return key.indexOf(prefix) === 0;
  });
}
