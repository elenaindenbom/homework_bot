import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (HomeworkStatusesException, SendMessageException,
                        VariableAvailabilityException)

load_dotenv()

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
        logging.info('Бот начал отправку сообщения в Telegramm')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception:
        raise SendMessageException('Сбой при отправке сообщения в Telegram')
    else:
        logging.info(f'Отправлено сообщение {message}')


def get_api_answer(current_timestamp):
    """Возвращает ответ API приведенный к типу данных python."""
    logging.debug('Запущена функция get_api_answer()')
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params)
    except Exception:
        raise Exception('Сбой при запросе к эндпоинту')
    else:
        if homework_statuses.status_code == HTTPStatus.OK:
            return homework_statuses.json()
        message = (f'Эндпоинт {ENDPOINT} недоступен. '
                   f'Код ответа API: {homework_statuses.status_code}')
        raise Exception(message)


def check_response(response) -> list:
    """Проверяет ответ API на корректность."""
    logging.debug('Запущена функция check_response()')
    if not isinstance(response, dict):
        raise TypeError('В ответе API ожидается словарь')
    try:
        homeworks = response['homeworks']
    except KeyError as error:
        raise KeyError(f'В словаре нет запрашиваемого ключа {error}')
    if isinstance(homeworks, list):
        return homeworks
    raise TypeError('Под ключем "homeworks" ожидается список')


def parse_status(homework) -> str:
    """Извлекает статус домашней работы."""
    logging.debug('Запущена функция parse_status()')

    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if (not homework_name) or (not homework_status):
        raise KeyError('В словаре нет запрашиваемого ключа')

    if homework_status in HOMEWORK_STATUSES.keys():
        verdict = HOMEWORK_STATUSES.get(homework_status)
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    message = 'Статус домашней работы не соответствует ожидаемому'
    raise HomeworkStatusesException(message)


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствуют обязательные переменные окружения')
        sys.exit('Ошибка переменных окружения. Работа программы прервана')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

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
            else:
                logging.debug('Обновлений нет')

            current_timestamp = int(time.time())

        except SendMessageException:
            logging.error('Сбой при отправке сообщения в Telegram')
        except Exception as error:
            message = f'Сбой в работе программы: {error}, {error.__class__}'
            logging.error(message)
            new_error = str(error)
            if new_error != raised_error:
                send_message(bot, message)
                raised_error = str(error)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format=(
            '%(asctime)s - %(levelname)s - %(message)s'
        ),
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    main()
