import sys
import telegram
import time
import logging
import os
import requests
from http import HTTPStatus
from dotenv import load_dotenv
from exceptions import (
    SendMessageException,
    HomeworkStatusesException,
    VariableAvailabilityException)

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message) -> None:
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except SendMessageException:
        logger.error('Сбой при отправке сообщения в Telegram')
    else:
        logger.info(f'Отправлено сообщение {message}')


def get_api_answer(current_timestamp):
    """Возвращает ответ API приведенный к типу данных python."""
    logger.debug('Запущена функция get_api_answer()')
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params)
    except ConnectionError:
        logger.error(f'Эндпойнт {ENDPOINT} не доступен')
    except Exception:
        logger.error('Сбой при запросе к эндпоинту')
    else:
        if homework_statuses.status_code == HTTPStatus.OK:
            return homework_statuses.json()
        message = (f'Эндпоинт {ENDPOINT} недоступен. '
                   f'Код ответа API: {homework_statuses.status_code}')
        logger.error(message)
        raise Exception(message)


def check_response(response) -> list:
    """Проверяет ответ API на корректность."""
    logger.debug('Запущена функция check_response()')
    if not isinstance(response, dict):
        logger.error('Ответ API не соответствует ожиданиям')
        raise TypeError('В ответе API ожидается словарь')
    try:
        homeworks = response['homeworks']
    except KeyError as error:
        logger.error(f'Ключа {error} нет в словаре')
        raise error
    if isinstance(homeworks, list):
        return homeworks
    logger.error('Ответ API не соответствует ожиданиям')
    raise TypeError('Под ключем "homeworks" ожидается список')


def parse_status(homework) -> str:
    """Извлекает статус домашней работы."""
    logger.debug('Запущена функция parse_status()')

    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
    except KeyError as error:
        logger.error(f'Ключа {error} нет в словаре')
        raise error

    if homework_status in HOMEWORK_STATUSES.keys():
        verdict = HOMEWORK_STATUSES.get(homework_status)
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    message = 'Статус домашней работы не соответствует ожидаемому'
    logger.error(message)
    raise HomeworkStatusesException(message)


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют обязательные переменные окружения')
        raise VariableAvailabilityException('Ошибка переменных окружения')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    # current_timestamp = 2

    raised_error = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            if not response:
                raise Exception('Сбой при запросе к эндпоинту')
            check = check_response(response)
            if check:
                for homework in check:
                    message = parse_status(homework)
                    send_message(bot, message)
                    # print(parse_status(homework))
            else:
                logger.debug('Обновлений нет')

            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}, {error.__class__}'
            logger.error(message)
            new_error = str(error)
            if new_error != raised_error:
                send_message(bot, message)
                raised_error = str(error)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
