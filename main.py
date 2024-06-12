from typing import Final
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, filters, ContextTypes
import os
import pandas as pd
import paho.mqtt.client as mqtt

# Mendeklarasikan variabel konstan TOKEN dan BOT_USERNAME
TOKEN: Final = '7436003581:AAFS5Bs811Q-lqOXYZlWHqhd39_RO_80F0c'
BOT_USERNAME: Final = '@Falldetectionkelompok2_bot'

# Mendefinisikan konstanta untuk setiap tahap dalam percakapan
USERNAME, RELATIONSHIP, CONFIRM, EDIT, CONNECT, ACCOUNT = range(6)

# Mendeklarasikan detail koneksi MQTT
MQTT_BROKER = "34.101.48.71"  
MQTT_PORT = 1883
MQTT_TOPIC = "fall_detection_topic"  

# Menginisialisasi klien MQTT dan variabel global telegram_bot_context
mqtt_client = mqtt.Client()
telegram_bot_context = None
# Callback saat terhubung ke broker MQTT
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")
# Callback saat menerima pesan dari broker MQTT, mengirimkan pesan tersebut ke pengguna Telegram
def on_message(client, userdata, msg):
    message = msg.payload.decode()
    print(f"Received message: {message} on topic {msg.topic}")
    if telegram_bot_context:
        # Send the received MQTT message to the user via Telegram bot
        context = telegram_bot_context
        context.bot.send_message(chat_id=context.user_data['chat_id'], text=f"Received MQTT message: {message}")
# Fungsi untuk memulai koneksi dan loop MQTT
def start_mqtt():
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
# Fungsi untuk menghentikan loop MQTT
def stop_mqtt():
    mqtt_client.loop_stop()
# Fungsi untuk mempublikasikan pesan ke topik MQTT
def publish_mqtt_message(message):
    mqtt_client.publish(MQTT_TOPIC, message)
# Mengaitkan callback dan memulai koneksi MQTT
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Start MQTT connection
start_mqtt()

def save_to_excel(user_data):
    df = pd.DataFrame([user_data])
    directory = "C:\\fall-detect"  # Ubah ke direktori yang diinginkan

    if not os.path.exists(directory):
        os.makedirs(directory)

    file_path = os.path.join(directory, 'registrations.xlsx')

    try:
        if os.path.exists(file_path):
            with pd.ExcelWriter(file_path, mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
                if 'Sheet1' in writer.book.sheetnames:
                    start_row = writer.sheets['Sheet1'].max_row
                    df.to_excel(writer, index=False, header=False, startrow=start_row)
                else:
                    df.to_excel(writer, index=False, header=True)
        else:
            df.to_excel(file_path, index=False)
        print(f'File saved to {file_path}')
    except Exception as e:
        print(f'Error saving file: {e}')

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu_keyboard = [
        ["/subscribe", "/contactlist"],
        ["/connect", "/disconnect"],
        ["/myaccount"]
    ]
    await update.message.reply_text('Halo! Selamat datang di Bot Telegram Kami', reply_markup=ReplyKeyboardMarkup(menu_keyboard, one_time_keyboard=True))

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Username Anda?\n\nJika ingin membatalkan pendaftaran silahkan ketik /cancel')
    return USERNAME

async def username_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_username = update.message.text.strip()
    if not user_username.replace(" ", "").isalpha():
        await update.message.reply_text('Username tidak boleh mengandung simbol atau angka.')
        return USERNAME
    else:
        context.user_data['username'] = user_username
        if context.user_data.get('edit_mode'):
            context.user_data['edit_mode'] = False
            await show_confirmation(update, context)
            return CONFIRM
        reply_keyboard = [['Orang Tua', 'Saudara']]
        await update.message.reply_text(
            "Apa hubungan anda dengan buah hati?",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        )
        return RELATIONSHIP

async def relationship_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    relationship = update.message.text
    context.user_data['relationship'] = relationship
    if context.user_data.get('edit_mode'):
        context.user_data['edit_mode'] = False
        await show_confirmation(update, context)
        return CONFIRM
    await show_confirmation(update, context)
    return CONFIRM

async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    biodata = (f"--- Berikut Biodata Anda ---\n"
            f"Username Anda: {user_data['username']}\n"
            f"Hubungan: {user_data['relationship']}\n\n"
            "Apakah Anda ingin menyimpan biodata ini?")

    keyboard = [
        [InlineKeyboardButton("Setuju", callback_data='setuju')],
        [InlineKeyboardButton("Edit", callback_data='edit')],
        [InlineKeyboardButton("Batalkan", callback_data='batalkan')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(biodata, reply_markup=reply_markup)

async def confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'setuju':
        save_to_excel(context.user_data)
        await query.edit_message_text(text="Biodata Anda telah disimpan. Terima kasih! ")
        
        # Publish to MQTT topic
        publish_mqtt_message(f"New user registered: {context.user_data['username']} with relationship: {context.user_data['relationship']}")
        
        return ConversationHandler.END
    elif query.data == 'edit':
        keyboard = [
            [InlineKeyboardButton("Username Anda", callback_data='edit_username')],
            [InlineKeyboardButton("Hubungan", callback_data='edit_relationship')],
            [InlineKeyboardButton("Batal", callback_data='batal')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="Bagian mana yang ingin Anda edit?", reply_markup=reply_markup)
        return EDIT_CHOICE
    elif query.data == 'batalkan':
        await query.edit_message_text(text="Pendaftaran Anda telah dibatalkan.")
        return ConversationHandler.END

async def edit_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['edit_mode'] = True  # Set edit mode

    if query.data == 'edit_username':
        await query.edit_message_text(text="Username Anda?")
        return USERNAME
    elif query.data == 'edit_relationship':
        reply_keyboard = [['Saudara', 'Orang Tua']]
        await query.message.reply_text(
            text="Apa hubungan anda dengan buah hati?",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        )
        return RELATIONSHIP
    elif query.data == 'batal':
        await show_confirmation(query, context)  # Menampilkan kembali formulir konfirmasi
        return CONFIRM
    elif query.data == 'cancel':
        await query.edit_message_text(text="Pendaftaran Anda telah dibatalkan.")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Pendaftaran dibatalkan.', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global telegram_bot_context
    telegram_bot_context = context

    context.user_data['chat_id'] = update.message.chat_id
    mqtt_client.subscribe(MQTT_TOPIC)
    await update.message.reply_text("Terhubung ke MQTT. Anda akan mulai menerima pesan dari topik.")

async def disconnect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mqtt_client.unsubscribe(MQTT_TOPIC)
    await update.message.reply_text("Terputus dari MQTT. Anda tidak akan lagi menerima pesan dari topik.")

async def contactlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact_list = (
        'Daftar Kontak Darurat:\n'
        '<a href="Call:+0812-8008-6700">081280086700</a> - Ambulance Kota Malang\n'
        '<a href="Call:+0851-6169-0119">085161690119</a> - Ambulance Kota Batu\n'
        '<a href="tel:+03413906868">(0341) 3906868</a> - Ambulance Kabupaten Malang\n'
    )
    await update.message.reply_text(contact_list, parse_mode='HTML')

async def account_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data
    if not user_data:
        await update.message.reply_text("Anda belum terdaftar. Silakan daftar terlebih dahulu /subscribe.")
        return ConversationHandler.END
    
    biodata = (f"--- Detail Akun Anda ---\n"
            f"Username Anda: {user_data['username']}\n"
            f"Hubungan: {user_data['relationship']}\n\n"
            "Apakah Anda ingin mengedit detail akun Anda?")

    keyboard = [
        [InlineKeyboardButton("Username Anda", callback_data='edit_username')],
        [InlineKeyboardButton("Hubungan", callback_data='edit_relationship')],
        [InlineKeyboardButton("Kembali", callback_data='kembali')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(biodata, reply_markup=reply_markup)
    return ACCOUNT

async def account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['edit_mode'] = True  # Set edit mode

    if query.data == 'edit_username':
        await query.edit_message_text(text="Username Anda?")
        return USERNAME
    elif query.data == 'edit_relationship':
        reply_keyboard = [['Orang Tua', 'Saudara']]
        await query.message.reply_text(
            text="Apa hubungan anda?",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        )
        return RELATIONSHIP
    elif query.data == 'kembali':
        await account_command(query, context)  # Menampilkan kembali detail akun
        return ACCOUNT

if _name_ == '_main_':
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('subscribe', subscribe_command)],
        states={
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, username_received)],
            RELATIONSHIP: [MessageHandler(filters.TEXT & ~filters.COMMAND, relationship_received)],
            CONFIRM: [CallbackQueryHandler(confirm_handler)],
            EDIT_CHOICE: [CallbackQueryHandler(edit_choice_handler)],
            CONNECT: [CallbackQueryHandler(connect_handler)],
            ACCOUNT: [CallbackQueryHandler(account_handler)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('connect', connect_command))
    app.add_handler(CommandHandler('disconnect', disconnect_command))
    app.add_handler(CommandHandler('contactlist', contactlist_command))
    app.add_handler(CommandHandler('account', account_command))
    app.add_handler(conv_handler)

    print('Bot is polling...')
    app.run_polling(poll_interval=5)