const NAE_API_URL = 'https://TU_DOMINIO_O_IP/api/v1/respuestas';
const NAE_API_TOKEN = 'NAE_LOCAL_DEV_2025';

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
    formulario_origen: 'Encuesta NAE v1.1',
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
  if (payload['0.4 Nivel de instrucción terminado']) {
    return '1.1';
  }
  if (payload['0.4 Nivel de conocimiento sobre la realidad del municipio']) {
    return '1.0';
  }
  return '1.0';
}
