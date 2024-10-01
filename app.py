import logging
from flask import Flask, render_template, Response, jsonify
from datetime import datetime, timedelta
from flask_pymongo import PyMongo
from pytz import timezone, utc
import pandas as pd
import os

# Configuración del logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates")

db_name = 'OutageManager'
port = 27017
collection = 'alarm'
username = os.getenv('MONGO_USER')
password = os.getenv('MONGO_PASS')
hostmongodb = os.getenv('MONGODB_URI')

# Obtén el valor de DAYS_CLEARED_AGO, si no existe, usa 4 como valor por defecto
days_configMap = int(os.getenv('DAYS_CLEARED_AGO', 4))

# Verificar las variables de entorno
if username and password and hostmongodb:
    hostmongodb = hostmongodb.replace('${MONGO_USER}', username).replace('${MONGO_PASS}', password)
    logger.info("Variables de entorno de MongoDB definidas correctamente.")
else:
    logger.warning("Las variables de entorno MONGODB_URI, MONGO_USER o MONGO_PASS no están definidas.")

# Configuración de la conexión con MongoDB
app.config["MONGO_URI"] = hostmongodb
mongo = PyMongo(app)

# Definir la zona horaria Local (Buenos Aires)
buenos_aires_tz = timezone('America/Argentina/Buenos_Aires')
#days_ago = datetime.now(buenos_aires_tz) - timedelta(days=days_configMap)  # default 4

# Ruta principal que carga la página
@app.route('/')
def index():
    logger.info("Cargando la página viewAlarmsOUM.")
    return render_template('viewAlarmsOUM.html', days_configMap=days_configMap)

# Nueva ruta para obtener las alarmas en formato JSON
@app.route('/get_alarmas', methods=['GET'])
def get_alarmas():
    days_ago = datetime.now(buenos_aires_tz) - timedelta(days=days_configMap)  # default 4
    logger.info(f"Consultando alarmas desde {days_ago}.")

    cursor = mongo.db.alarm.find(
        {
            "$or": [
                { 
                    "alarmState": { "$in": ['RAISED', 'UPDATED', 'RETRY'] }                   
                },
                {
                    "alarmState": "CLEARED",
                    "alarmClearedTime": { "$gte": days_ago }
                }
            ]
        },
        {
            "_id": 0,
            "alarmId": 1,
            "alarmType": 1,
            "alarmState": 1,
            "clients": 1,
            "TypeNetworkElement": "$networkElement.type",
            "networkElementId": 1,
            "timeResolution": 1,
            "sourceSystemId": 1,
            "origenId": 1,
            "inicioOUM": "$omArrivalTimestamp",
            "alarmRaisedTime": 1,
            "alarmClearedTime": 1,
            "alarmReportingTime":1
        }
    ).sort("_id", -1)

    alarmas = []
    for alarma in cursor:
        if alarma.get('inicioOUM'):
            alarma['inicioOUM'] = alarma.get('inicioOUM').replace(tzinfo=utc).astimezone(buenos_aires_tz).strftime('%m-%d %H:%M:%S')
        else:
            alarma['inicioOUM'] = '-'

        if alarma.get('alarmRaisedTime'):
            alarma['alarmRaisedTime'] = alarma.get('alarmRaisedTime').replace(tzinfo=utc).astimezone(buenos_aires_tz).strftime('%m-%d %H:%M:%S')
        else:
            alarma['alarmRaisedTime'] = '-'

        if alarma.get('alarmClearedTime'):
            alarma['alarmClearedTime'] = alarma.get('alarmClearedTime').replace(tzinfo=utc).astimezone(buenos_aires_tz).strftime('%m-%d %H:%M:%S')
        else:
            alarma['alarmClearedTime'] = '-'

        if alarma.get('alarmReportingTime'):
            alarma['alarmReportingTime'] = alarma.get('alarmReportingTime').replace(tzinfo=utc).astimezone(buenos_aires_tz).strftime('%m-%d %H:%M:%S')
        else:
            alarma['alarmClearedTime'] = '-'

        if not alarma.get('timeResolution'):
            alarma['timeResolution'] = '-'     

#        if alarma.get('alarmState') in ["UPDATED", "RETRY"]:
#            logger.info('es   '+alarma.get('alarmState'))
#            alarma['alarmState'] = "RAISED"
#            logger.info('hacer '+alarma.get('alarmState'))
#        else:
#            #alarma['alarmState'] = alarma.get('alarmState')
#            logger.info('todo '+ alarma.get('alarmState'))


#        alarm_id = alarma.get('alarmId') or ''
#        origen_id = alarma.get('origenId') or ''
#
#        # Check if alarm_id is a substring of origen_id or vice versa
#        if alarm_id in origen_id or origen_id in alarm_id:
#            alarma['origenId'] = (alarma.get('sourceSystemId') or '') + ' ' + origen_id
#        else:
#            alarma['origenId'] = 'ICD ' + origen_id
            

        alarm_id = alarma.get('alarmId') or ''
        origen_id = alarma.get('origenId') or ''

        # Check if alarm_id is a substring of origen_id or vice versa
        if alarm_id in origen_id or origen_id in alarm_id:
            # Check the length of alarm_id to determine the prefix
            if len(alarm_id) == 24:
                alarma['origenId'] = 'FMS ' + origen_id
            elif len(alarm_id) == 10 or len(alarm_id) == 13:
                alarma['origenId'] = 'FMC ' + origen_id
            else:
                alarma['origenId'] = (alarma.get('sourceSystemId') or '') + ' ' + origen_id
        else:
            alarma['origenId'] = 'ICD ' + origen_id



        if alarma.get('sourceSystemId') in ['ICD']:
           alarma['alarmId'] = 'ICD ' + alarma.get('alarmId')
        else:   
           alarma['alarmId'] = alarma.get('sourceSystemId') + ' ' + alarma.get('alarmId')

        alarmas.append(alarma)

    logger.info(f"Se encontraron {len(alarmas)} alarmas.")
    return jsonify({"alarmas": alarmas})

# Ruta para exportar los datos
@app.route('/export/<format>')
def export_data(format):
    days_ago = datetime.now(buenos_aires_tz) - timedelta(days=days_configMap)  # default 4
    logger.info(f"Exportando alarmas en formato {format}.")

    cursor = mongo.db.alarm.find(
        {
            "$or": [
                { 
                    "alarmState": { "$in": ['RAISED', 'UPDATED', 'RETRY'] }
                },
                {
                    "alarmState": "CLEARED",
                    "alarmClearedTime": { "$gte": days_ago }
                }
            ]
        },
        {   "_id": 0,
            "alarmId": 1, "alarmState": 1, "alarmType": 1, 
            "inicioOUM": "$omArrivalTimestamp", "alarmRaisedTime": 1, "alarmReportingTime":1, "alarmClearedTime": 1,              
            "TypeNetworkElement": "$networkElement.type", "networkElementId": 1, "clients": 1,
            "timeResolution": 1, "sourceSystemId": 1, "origenId": 1            
        }
    ).sort("_id", -1)

    alarmas = list(cursor)

    # Reemplazar "UPDATED" y "RETRY" por "RAISED" en el estado de la alarma
    for alarma in alarmas:
        if alarma.get('alarmState') in ['UPDATED', 'RETRY']:
            alarma['alarmState'] = 'RAISED'

    df = pd.DataFrame(alarmas)

    # Reordenar las columnas
    df = df[['alarmId', 'alarmState', 'alarmType', 'inicioOUM', 'alarmRaisedTime', 'alarmReportingTime', 'alarmClearedTime', 
             'TypeNetworkElement', 'networkElementId', 'clients', 'timeResolution', 'sourceSystemId', 'origenId']]

    fecha_actual = datetime.now(buenos_aires_tz).strftime('%Y%m%d%H%M%S')

    if format == 'csv':
        csv_data = df.to_csv(index=False)
        logger.info("Exportación a CSV completa.")
        return Response(csv_data, mimetype="text/csv", headers={"Content-disposition": f"attachment; filename=SIA_alarmas_{fecha_actual}.csv"})
    elif format == 'excel':
        output = pd.ExcelWriter('/tmp/alarmas.xlsx', engine='xlsxwriter')
        df.to_excel(output, index=False)
        output.close()

        with open('/tmp/alarmas.xlsx', 'rb') as f:
            excel_data = f.read()
        logger.info("Exportación a Excel completa.")
        return Response(excel_data, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-disposition": f"attachment; filename=SIA_alarmas_{fecha_actual}.xlsx"})
    else:
        logger.warning("Formato de exportación no soportado.")
        return "Unsupported format. Please use 'csv' or 'excel'."

if __name__ == '__main__':
    port = os.environ.get('FLASK_PORT') or 8080
    logger.info(f"Iniciando la aplicación en el puerto {port}.")
    app.run(port=int(port), host='0.0.0.0')
