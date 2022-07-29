import logging
import os
import time
import requests

from logging import StreamHandler

import telegram.error
from requests import HTTPError
from telegram import Bot
from dotenv import load_dotenv
from sys import stdout
from http import HTTPStatus

from exceptions import IncorrectResponseException, UnknownStatusException

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME: int = 600
ERROR_CACHE_LIFETIME: int = 60 * 60 * 24
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

errors_occur = {}

formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(stream=stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Функция отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'Сообщение "{message}" успешно отправлено')
    except Exception as error:
        logger.exception(f'Ошибка при отправке сообщения: {error}')
        raise


def get_api_answer(current_timestamp):
    """Функция делает запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code == HTTPStatus.OK:
            return response.json()
        raise HTTPError()
    except (HTTPError, ConnectionRefusedError) as error:
        logger.exception(f'Ресурс {ENDPOINT} недоступен: {error}!')
        raise
    except Exception as error:
        logger.exception(f'Ошибка при запросе к API: {error}!')
        raise


def check_response(response):
    """
    Функция проверяет ответ API на корректность.
    Возвращает список домашних работ.
    """
    try:
        if (isinstance(response, dict) and
                len(response) != 0 and
                'homeworks' in response and
                'current_date' in response and
                isinstance(response.get('homeworks'), list)):
            return response.get('homeworks')
        else:
            raise IncorrectResponseException()
    except IncorrectResponseException:
        logger.exception('Ответ API не соответствует ожидаемому!')
        raise


def parse_status(homework):
    """
    Функция возвращает подготовленную для отправки в Telegram строку.
    Строка должна содержать один из вердиктов словаря HOMEWORK_STATUSES.
    """
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    try:
        verdict = HOMEWORK_STATUSES.get(homework_status)
        if verdict is None:
            raise UnknownStatusException()
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except UnknownStatusException:
        logger.exception(
            f'Получен неизвестный статус домашней работы: {homework_status}')
        raise


def check_tokens():
    """Функция проверяет доступность переменных окружения."""
    available = True
    params = {'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
              'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
              'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
              }
    not_valid = ['', None]
    for key, value in params.items():
        if value in not_valid:
            available = False
            logger.critical(f'Отсутствует обязательная переменная окружения:'
                            f'{key}! Программа принудительно остановлена.'
                            )
    return available


def handle_error(bot, message):
    """
    Функция отправляет сообщение в телеграм, если оно еще не передавалось.
    """

    if type(message) == telegram.error.BadRequest:
        return

    message = str(message)
    error = errors_occur.get(message)
    if not error:
        errors_occur[message] = int(time.time())
        send_message(bot, 'WARNING!: ' + message)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise SystemExit

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    cache_cleared = current_timestamp

    while True:
        try:
            if int(time.time()) - cache_cleared > ERROR_CACHE_LIFETIME:
                errors_occur.clear()

            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)

            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                logger.debug('Нет новых статусов')

            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)

        except Exception as error:
            handle_error(bot, error)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
