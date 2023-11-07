# -*- coding: utf-8 -*-
import os
import cv2
import requests
import numpy as np
from flask import Flask, request, Response
import time
import telebot
from datetime import datetime
from telebot import types
from flask_basicauth import BasicAuth
import threading  

app = Flask(__name__)

TOKEN = "6109882990:AAFzWkGPvUoUSEIuE1beXX2Z8z7Ht9itepo"
CHAT_ID = "1936815365"
bot = telebot.TeleBot(TOKEN)


video_writer = None
recording = False
video_filename = None
motion_detected = False
send_video_enabled = False
motion_detection_enabled = True
camera_url = 'https://0512-77-120-133-124.ngrok-free.app/video'


app.config['BASIC_AUTH_USERNAME'] = 'логин'
app.config['BASIC_AUTH_PASSWORD'] = 'пароль'
app.config['BASIC_AUTH_FORCE'] = True  
basic_auth = BasicAuth(app)


fgbg = cv2.createBackgroundSubtractorMOG2()
min_contour_area = 500

def start_video_recording():
    global video_writer, recording, video_filename
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')

    current_datetime = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    video_filename = 'video_{}.mp4'.format(current_datetime)
    video_writer = cv2.VideoWriter(video_filename, fourcc, 20.0, (1920, 1080))
    recording = True

def stop_video_recording():
    global video_writer, recording, video_filename
    if video_writer is not None:
        video_writer.release()
        print("Total frames recorded:", video_writer.get(cv2.CAP_PROP_FRAME_COUNT))
        video_writer = None
        recording = False
        send_video_to_telegram()  
        os.remove(video_filename) 
        video_filename = None

def send_video_to_telegram():
    global video_filename, send_video_enabled
    if send_video_enabled and video_filename is not None:
        url = 'https://api.telegram.org/bot{}/sendVideo'.format(TOKEN)
        files = {'video': (video_filename, open(video_filename, 'rb'))}
        data = {'chat_id': CHAT_ID}
        response = requests.post(url, data=data, files=files)
        if response.status_code == 200:
            print("Видео отправлено в Telegram")
        else:
            print("Не удалось отправить видео в Telegram")


def generate_frames():
    global recording, motion_detected, motion_detection_enabled

    capture = cv2.VideoCapture(camera_url)
    capture.set(3, 640)
    capture.set(4, 480)

    while True:
        ret, frame = capture.read()

        if not ret:
            break

        if motion_detection_enabled:
            fgmask = fgbg.apply(frame)
            fgmask = cv2.erode(fgmask, None, iterations=2)
            fgmask = cv2.dilate(fgmask, None, iterations=2)
            contours, _ = cv2.findContours(fgmask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            motion_detected = False

            for contour in contours:
                if cv2.contourArea(contour) > min_contour_area:
                    motion_detected = True
                    break

            if motion_detected:
                if not recording:
                    start_video_recording()
            else:
                if recording:
                    stop_video_recording()
                    send_video_to_telegram()

        if recording:
            video_writer.write(frame)

        ret, jpeg = cv2.imencode('.jpg', frame)
        frame_bytes = jpeg.tobytes()

        if motion_detection_enabled:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
            time.sleep(1) 
            
            
@bot.message_handler(commands=['start'])
def start(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    enable_video_button = types.KeyboardButton("Включить отправку видео")
    disable_video_button = types.KeyboardButton("Выключить отправку видео")
    change_login_button = types.KeyboardButton("Изменить логин")
    change_password_button = types.KeyboardButton("Изменить пароль")
    keyboard.add(change_login_button, change_password_button)

    chat_id = message.chat.id
    bot.send_message(chat_id, "Выберите действие:", reply_markup=keyboard)

    keyboard.add(enable_video_button)
    keyboard.add(disable_video_button)
    
    bot.send_message(message.chat.id, "Здравствуй, дорогой клиент! 😊 Я - ваш личный бот-ассистент. Я могу помочь вам с различными задачами и даже управлять функцией распознавания движения. Для начала, воспользуйтесь доступными командами или кнопкой на клавиатуре. 💼🚀 У нас есть уникальная функция распознавания движения, которая поможет вам защитить ваши бизнес-помещения от грабителей. 📹👀", reply_markup=keyboard)


@bot.message_handler(func=lambda message: message.text == "Изменить логин")
def change_login(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Введите новый логин:")
    bot.register_next_step_handler(message, process_new_login)

def process_new_login(message):
    chat_id = message.chat.id
    new_login = message.text
    app.config['BASIC_AUTH_USERNAME'] = new_login
    bot.send_message(chat_id, "Логин успешно изменен на {}".format(new_login))

@bot.message_handler(func=lambda message: message.text == "Изменить пароль")
def change_password(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Введите новый пароль:")
    bot.register_next_step_handler(message, process_new_password)

def process_new_password(message):
    chat_id = message.chat.id
    new_password = message.text
    app.config['BASIC_AUTH_PASSWORD'] = new_password
    bot.send_message(chat_id, "Пароль успешно изменен {}".format(new_password))


@bot.message_handler(func=lambda message: message.text == "Включить отправку видео")
def enable_send_video(message):
    global send_video_enabled
    send_video_enabled = True
    bot.reply_to(message, "Отправка видео включена")

@bot.message_handler(func=lambda message: message.text == "Выключить отправку видео")
def disable_send_video(message):
    global send_video_enabled
    send_video_enabled = False
    bot.reply_to(message, "Отправка видео выключена")

    stop_video_recording()

@app.route('/')
@basic_auth.required
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def run_server():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    server_thread = threading.Thread(target=run_server)
    server_thread.start()

    bot.polling()