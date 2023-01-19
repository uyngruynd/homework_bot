# Homework Bot

## Описание
Telegram-бот обращается к API сервиса Яндекс.Практикум и возвращает статус вашей домашней работы:  
 * взята ли ваша домашка на ревью
 * проверена ли она
 * а если проверена - то принял её ревьюер или вернул на доработку

Помимо статусов проверки домашки бот логирует свою работу и сообщает вам о важных проблемах сообщением в Telegram.

## Инструкция по установке

1. Установите необходимые зависимости: ```pip install requirements.txt```
2. Создайте и заполните .env-файл:
 * PRACTICUM_TOKEN = "<токен студента Яндекс.Практикума>"   
 * TELEGRAM_TOKEN = "<токен бота, возвращенный @BotFather при регистрации>"  
 * TELEGRAM_CHAT_ID = "<ID пользователя telegram>"
3. Запустите исполняемый файл: ```python3 homework.py```

## Системные требования

* Python 3.7
* python-telegram-bot 13.7

