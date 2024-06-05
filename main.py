from telegram import Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, JobQueue
import logging
import paho.mqtt.client as mqtt

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(_name_)

# Replace 'TOKEN' with your Bot's API token
bot = Bot('7436003581:AAHPWQyr08cgrr0Rfg-0fsAyO3olWn0KYZ4')
updater = Updater(bot=bot)

dispatcher = updater.dispatcher

chat_ids = set([1265101503, 1505104468])

# MQTT client setup
mqtt_client = mqtt.Client()
mqtt_client.connect("34.101.48.71", 1833)  # Replace with your MQTT broker IP and port

def start(update, context):
    chat_ids.add(update.effective_chat.id)
    context.bot.send_message(chat_id=update.effective_chat.id, text="Bot telah dimulai. Kirimkan data dari alat IoT Anda.")

def detect_fall(data):
    # Implement your fall detection logic here
    # This is a simple example, you might need to process the data and apply a suitable algorithm
    if data == "FALL_DETECTED":
        return True
    return False

def handle_message(update, context):
    chat_ids.add(update.effective_chat.id)
    message = update.message.text
    if detect_fall(message):
        for chat_id in chat_ids:
            context.bot.send_message(chat_id=chat_id, text="Jatuh terdeteksi!")

def send_message(context):
    job = context.job
    for chat_id in chat_ids:
        context.bot.send_message(chat_id=chat_id, text="Ini adalah pesan yang dikirim setiap 30 detik!")

def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    client.subscribe("your/topic")  # Replace with your topic

def on_message(client, userdata, msg):
    print(msg.topic+" "+str(msg.payload))
    if detect_fall(msg.payload.decode()):
        for chat_id in chat_ids:
            bot.send_message(chat_id=chat_id, text="Jatuh terdeteksi!")

# Set your MQTT handlers
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Start the MQTT client
mqtt_client.loop_start()

start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)

message_handler = MessageHandler(Filters.text & (~Filters.command), handle_message)
dispatcher.add_handler(message_handler)

# Add job to queue
job_queue = updater.job_queue
job_queue.run_repeating(send_message, interval=30, first=0)

# Start the Bot
updater.start_polling()

# Run the bot until the user presses Ctrl-C or the process receives SIGINT,
# SIGTERM or SIGABRT
updater.idle()