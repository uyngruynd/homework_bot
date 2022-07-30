import logging
import os
import time
import requests

from logging import StreamHandler
from requests import HTTPError
from telegram import Bot
from dotenv import load_dotenv
from sys import stdout
from http import HTTPStatus

from exceptions import (IncorrectResponseException, UnknownStatusException,
                        TelegramAPIException)
from endpoints import ENDPOINT

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_RETRY_TIME: int = 600
ERROR_CACHE_LIFETIME: int = 60 * 60 * 24

HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
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
        error_message = f'Ошибка при отправке сообщения: {error}'
        logger.exception(error_message)
        raise TelegramAPIException(error_message)


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
        error_message = f'Ресурс {ENDPOINT} недоступен: {error}!'
        logger.exception(error_message)
        raise HTTPError(error_message)
    except Exception as error:
        error_message = f'Ошибка при запросе к API: {error}!'
        logger.exception(error_message)
        raise Exception(error_message)


def check_response(response):
    """
    Функция проверяет ответ API на корректность.
    Возвращает список домашних работ.
    """
    logger.debug('Проверка ответа сервиса на корректность.')

    if (isinstance(response, dict)
            and len(response) != 0
            and 'homeworks' in response
            and 'current_date' in response
            and isinstance(response.get('homeworks'), list)):
        return response.get('homeworks')
    else:
        error_message = 'Ответ API не соответствует ожидаемому!'
        logger.exception(error_message)
        raise IncorrectResponseException(error_message)


def parse_status(homework):
    """
    Функция возвращает подготовленную для отправки в Telegram строку.
    Строка должна содержать один из вердиктов словаря HOMEWORK_STATUSES.
    """
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status not in HOMEWORK_VERDICTS:
        error_message = (
            f'Получен неизвестный статус домашней работы: {homework_status}')
        logger.exception(error_message)
        raise UnknownStatusException(error_message)
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Функция проверяет доступность переменных окружения."""
    available = True
    params = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    if not all(params):
        available = False
        logger.critical(f'Отсутствует обязательная переменная окружения,'
                        f'Программа принудительно остановлена.'
                        )
    return available


def handle_error(bot, message):
    """Ф-я отправляет сообщение в телеграм, если оно еще не передавалось."""
    if type(message) == TelegramAPIException:
        return

    message = str(message)
    error = errors_occur.get(message)
    if not error:
        errors_occur[message] = int(time.time())
        send_message(bot, 'WARNING!: ' + message)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise SystemExit('Критическая ошибка, бот остановлен!')

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
        except Exception as error:
            handle_error(bot, error)
        finally:
            time.sleep(TELEGRAM_RETRY_TIME)


if __name__ == '__main__':
    main()
