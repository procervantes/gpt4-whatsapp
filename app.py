from flask import Flask, request
import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from twilio.twiml.messaging_response import MessagingResponse

# Configura tu clave de OpenAI
openai.api_key = "TU_API_KEY_OPENAI"

# Configura acceso a Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
import json
import os
creds_dict = json.loads(os.environ['GOOGLE_CREDS'])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

client = gspread.authorize(creds)

# Abre tu hoja de cálculo
sheet = client.open("alumnos_gpt").sheet1

# Configurar Flask
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    from_number = request.values.get("From", "").replace("whatsapp:", "")

    # Buscar el número en la hoja
    try:
        records = sheet.get_all_records()
        user = next((r for r in records if r["numero_whatsapp"] == from_number), None)
        if not user:
            return respond("Número no registrado. Contacta al administrador para activar tu acceso.")

        # Verificar vigencia
        today = datetime.now().date()
        expiry = datetime.strptime(user["vencimiento"], "%Y-%m-%d").date()
        if today > expiry:
            return respond("Tu plan ha vencido. Renueva para seguir usando el servicio.")

        # Verificar si le quedan mensajes
        if user["mensajes_restantes"] <= 0:
            return respond("Has agotado los mensajes de tu plan. Puedes recargar cuando gustes.")

        # Llamar a GPT-4
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Eres un asistente académico que responde de forma clara y útil."},
                {"role": "user", "content": incoming_msg}
            ]
        )
        reply = response.choices[0].message["content"]

        # Descontar mensaje usado
        row_index = records.index(user) + 2  # suma 2 por encabezado
        sheet.update_cell(row_index, 3, user["mensajes_restantes"] - 1)

        return respond(reply)

    except Exception as e:
        return respond(f"Ocurrió un error: {str(e)}")

def respond(message):
    resp = MessagingResponse()
    msg = resp.message()
    msg.body(message)
    return str(resp)

if __name__ == "__main__":
    app.run()
