"""HTTP, bounded polling, and durable download for the documented Legnext API."""

import os
import random
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

BASE = 'https://api.legnext.ai/api'
TERMINAL = {'completed', 'failed'}


class LegnextError(Exception):
    pass


def api_key():
    try:
        from agent.secret_scope import get_secret
    except ImportError:
        key = os.environ.get('LEGNEXT_API_KEY')
    else:
        key = get_secret('LEGNEXT_API_KEY')
    if not key:
        raise LegnextError('LEGNEXT_API_KEY отсутствует: укажите действующий ключ Legnext в профиле Hermes.')
    return key


def hermes_home():
    try:
        from hermes_constants import get_hermes_home
    except ImportError:
        return Path(os.environ.get('HERMES_HOME') or Path.home() / '.hermes')
    return Path(get_hermes_home())


def output_directory(config):
    configured = config('output_dir', '')
    path = Path(configured).expanduser() if configured else hermes_home() / 'legnext-output'
    path = path.resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _error(response):
    status = response.status_code
    messages = {
        400: 'HTTP 400: неверный запрос, несовместимые параметры или модерация; исправьте запрос, не повторяйте без изменений.',
        401: 'HTTP 401: ключ LEGNEXT_API_KEY отсутствует, недействителен или отозван.',
        402: 'HTTP 402: недостаточно средств/кредитов; пополните баланс Legnext и затем создайте новую задачу.',
        403: 'HTTP 403: аккаунт ограничен, модерация или суточный лимит ошибок; проверьте аккаунт.',
        404: 'HTTP 404: неизвестный или истёкший job_id (окно поиска — 3 суток).',
        429: 'HTTP 429: лимит параллельных задач; подождите (стандартный аккаунт — 6 задач).',
    }
    text = messages.get(status, f'HTTP {status}: ошибка Legnext; проверьте состояние сервиса и параметры запроса.')
    try:
        payload = response.json()
        detail = payload.get('message') or payload.get('error')
        if isinstance(detail, dict):
            detail = detail.get('message') or detail.get('code')
        if detail and status not in (401,):
            text += f' Детали: {str(detail)[:350]}'
    except (ValueError, TypeError, AttributeError):
        pass
    return LegnextError(text)


def request(method, endpoint, *, body=None, authenticated=False, submit=False):
    headers = {'x-api-key': api_key()} if authenticated else {}
    # A timed-out POST may have been accepted: never retry ambiguous submissions.
    attempts = 1 if submit else 4
    for attempt in range(attempts):
        try:
            response = httpx.request(method, BASE + endpoint, headers=headers, json=body, timeout=25, follow_redirects=False)
            if response.status_code >= 400:
                if response.status_code in (429,) or response.status_code >= 500:
                    if attempt + 1 < attempts:
                        time.sleep(min(8, 0.5 * (2 ** attempt)) + random.uniform(0, 0.4))
                        continue
                raise _error(response)
            return response.json()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            if attempt + 1 >= attempts:
                raise LegnextError('Сбой соединения с Legnext; для POST результат неизвестен — не повторяйте платный submit автоматически.') from exc
            time.sleep(min(8, 0.5 * (2 ** attempt)) + random.uniform(0, 0.4))
        except ValueError as exc:
            raise LegnextError('Legnext вернул невалидный JSON.') from exc
    raise LegnextError('Legnext недоступен после ограниченных повторов.')


def submit(endpoint, body):
    result = request('POST', '/v1/' + endpoint, body=body, authenticated=True, submit=True)
    if not isinstance(result, dict) or not result.get('job_id'):
        raise LegnextError('Legnext не вернул job_id; НЕ повторяйте POST вслепую: задача могла быть создана.')
    return result


def get_job(job_id):
    data = request('GET', '/v1/job/' + job_id)
    if not isinstance(data, dict):
        raise LegnextError('Неожиданный формат ответа о задаче Legnext.')
    return data


def poll(job, timeout, interval):
    started = time.monotonic()
    while job.get('status') not in TERMINAL:
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            return job, True
        time.sleep(min(interval, remaining))
        if time.monotonic() - started >= timeout:
            return job, True
        job = get_job(job['job_id'])
    return job, False


def download(job, config):
    output = job.get('output')
    if not isinstance(output, dict):
        raise LegnextError('Задача completed, но output пустой; проверьте mj_job позже или обратитесь в Legnext.')
    urls = output.get('image_urls')
    if not isinstance(urls, list) or not urls:
        urls = [output['image_url']] if output.get('image_url') else []
    if not urls:
        raise LegnextError('Задача completed, но output не содержит image_url/image_urls.')
    directory = output_directory(config)
    paths = []
    for index, url in enumerate(urls, 1):
        if not isinstance(url, str) or urlparse(url).scheme != 'https':
            raise LegnextError('Небезопасный или отсутствующий URL результата; скачивание отменено.')
        ext = Path(urlparse(url).path).suffix.lower()
        if not re.fullmatch(r'\.[a-z0-9]{1,6}', ext or ''):
            ext = '.png'
        task_type = re.sub(r'[^a-z0-9_-]', '', str(job.get('task_type') or 'image').lower()) or 'image'
        stem = f"{task_type}_{str(job['job_id'])[:8]}_{index}"
        with httpx.stream('GET', url, timeout=60, follow_redirects=True) as response:
            if response.status_code >= 400:
                raise LegnextError(f'Скачивание результата завершилось HTTP {response.status_code}; повторите mj_job пока ссылка действительна.')
            suffix = 0
            while True:
                target = directory / f'{stem}{"_" + str(suffix) if suffix else ""}{ext}'
                try:
                    with target.open('xb') as fh:
                        try:
                            for chunk in response.iter_bytes():
                                fh.write(chunk)
                        except Exception:
                            target.unlink(missing_ok=True)
                            raise
                    break
                except FileExistsError:
                    suffix += 1
        paths.append(str(target))
    return paths, urls


def result(job, config, *, download_media=True, elapsed=0, timed_out=False):
    job_id = job.get('job_id')
    status = job.get('status')
    if timed_out:
        return {'job_id': job_id, 'status': status, 'timed_out': True, 'note': 'задача продолжается на сервере, дождись через mj_job'}
    if status == 'failed':
        error = job.get('error') or {}
        return {'job_id': job_id, 'status': status, 'error': str(error.get('message') or error)[:500]}
    if status != 'completed':
        return {'job_id': job_id, 'status': status, 'note': 'Дождитесь завершения через mj_job; не отправляйте повторный submit.'}
    output = job.get('output') or {}
    if not isinstance(output, dict) or not (output.get('image_urls') or output.get('image_url')):
        return {'job_id': job_id, 'status': status, 'error': 'completed без результата: output пустой.'}
    urls = output.get('image_urls') or [output.get('image_url')]
    files = []
    if download_media:
        try:
            files, urls = download(job, config)
        except Exception as exc:
            return {'job_id': job_id, 'status': status, 'error': f'Не удалось сохранить результат: {exc}', 'image_urls': urls}
    usage = (job.get('meta') or {}).get('usage') or {}
    return {'job_id': job_id, 'status': status, 'task_type': job.get('task_type'), 'files': files,
            'image_urls': urls, 'seed': output.get('seed'), 'credits_consumed': usage.get('consume'),
            'elapsed_seconds': round(elapsed, 2), 'available_actions': output.get('available_actions')}
