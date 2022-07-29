import logging
import os
import time
import requests
import traceback

from logging import StreamHandler
from requests import HTTPError
from telegram import Bot
from dotenv import load_dotenv
from sys import stdout

from exceptions import IncorrectResponseException, UnknownStatusException

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME: int = 5  # 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

errors_occur = {'get_api_answer': 0,
                'check_response': 0,
                'parse_status': 0,
                'main': 0,
                }

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


def get_api_answer(current_timestamp, bot):
    """Функция делает запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        return response.json()
    except (HTTPError, ConnectionRefusedError) as error:
        handle_error(bot, f'Ресурс {ENDPOINT} недоступен: {error}!', )
    except Exception as error:
        handle_error(bot, f'Ошибка при запросе к API: {error}!')
    return {}


def check_response(response, bot):
    """
    Функция проверяет ответ API на корректность.
    Возвращает список домашних работ.
    """
    try:
        if isinstance(response, dict) and (
                'homeworks' in response and 'current_date' in response):
            return response.get('homeworks')
        else:
            raise IncorrectResponseException()
    except IncorrectResponseException:
        handle_error(bot, 'Ответ API не соответствует ожидаемому!')
        return []


def parse_status(homework, bot):
    """
    Функция возвращает подготовленную для отправки в Telegram строку.
    Строка должна содержать один из вердиктов словаря HOMEWORK_STATUSES.
    """
    name = homework.get('lesson_name')
    status = homework.get('status')
    try:
        verdict = HOMEWORK_STATUSES.get(status)
        if verdict is None:
            raise UnknownStatusException()
    except UnknownStatusException:
        verdict = '--статус неизвестен--'
        handle_error(bot,
                     f'Получен неизвестный статус домашней работы: {status}')
    return f'Изменился статус проверки работы "{name}". {verdict}'


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
    Функция обрабатывает ошибки уровня ERROR.
    Далее формирует лог и отправляет сообщение в телеграм,
    если оно не было отправлено ранее.
    """
    logger.exception(message)

    stack = traceback.extract_stack()
    prev_func_name = stack[-2].name
    error = errors_occur.get(prev_func_name)

    if error == 0:
        errors_occur[prev_func_name] = 1
        send_message(bot, 'WARNING: ' + message)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise SystemExit

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(current_timestamp, bot)
            homeworks = check_response(response, bot)

            if homeworks:
                message = parse_status(homeworks[0], bot)
                send_message(bot, message)
            else:
                logger.debug('Нет новых статусов')

            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)

        except Exception as error:
            handle_error(bot, f'Сбой в работе программы: {error}')
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
