const NAE_API_URL = 'https://nae-plataforma.mes.gob.cu/api/v1/respuestas';
const NAE_API_TOKEN = 'TU_TOKEN_REAL';
const NAE_FORM_TITLE = 'Propuesta de ENCUESTA FINAL SOBRE ESPACIOS DE INTERCAMBIO ENTRE NAE Y OTROS ACTORES – VERSION GOOGLE FORMS';
const NAE_SURVEY_VERSION = '0';

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
