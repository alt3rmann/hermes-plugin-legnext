"""Hermes handlers: all boundaries return JSON, including validation and API errors."""

import json
import re
import time
import uuid

from . import client

_config_getter = lambda key, default=None: default


def configure(getter):
    global _config_getter
    _config_getter = getter


def config(key, default=None):
    return _config_getter(key, default)


def _timeout(args):
    value = args.get('timeout')
    if value is None:
        value = config('default_timeout', 600)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError('timeout должен быть положительным целым числом секунд.')
    return value


def _interval():
    value = float(config('poll_interval', 5.0))
    if not 0 < value <= 3600:
        raise ValueError('poll_interval должен быть между 0 и 3600 секундами.')
    return value


def _uuid(value):
    if not isinstance(value, str):
        raise ValueError('job_id должен быть UUID задачи.')
    try:
        uuid.UUID(value)
    except ValueError as exc:
        raise ValueError('job_id должен быть UUID задачи.') from exc
    return value


def _wait(value):
    if not isinstance(value, bool):
        raise ValueError('wait должен быть boolean.')
    return value


def _run(job, *, wait, timeout, download=True, start=None):
    start = start if start is not None else time.monotonic()
    if wait and job.get('status') not in client.TERMINAL:
        try:
            job, timed_out = client.poll(job, timeout, _interval())
        except Exception as exc:
            return {'job_id': job.get('job_id'), 'status': job.get('status'),
                    'error': str(exc) if isinstance(exc, client.LegnextError) else type(exc).__name__,
                    'note': 'Опрос прерван; задача может продолжаться на сервере. Возобновите через mj_job, не отправляйте submit снова.'}
        if timed_out:
            return client.result(job, config, timed_out=True)
    return client.result(job, config, download_media=download, elapsed=time.monotonic() - start)


def _handle(fn):
    try:
        return json.dumps(fn(), ensure_ascii=False)
    except Exception as exc:
        # Never include request headers, API keys or HTTP exception reprs.
        if isinstance(exc, (ValueError, client.LegnextError)):
            return json.dumps({'error': str(exc)}, ensure_ascii=False)
        return json.dumps({'error': f'Не удалось выполнить запрос Legnext: {type(exc).__name__}. Проверьте настройки и повторите безопасный запрос.'}, ensure_ascii=False)


def mj_imagine(args: dict, **kwargs) -> str:
    def run():
        prompt = args.get('prompt')
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError('prompt обязателен и должен быть непустой строкой.')
        text = prompt.strip()
        aspect = args.get('aspect_ratio')
        if aspect is not None and (not isinstance(aspect, str) or not re.fullmatch(r'\d+:\d+', aspect)):
            raise ValueError('aspect_ratio должен быть в формате 16:9.')
        if aspect and not re.search(r'--ar(?:\s|=|$)', text, re.I):
            text += f' --ar {aspect}'
        version = args.get('version')
        if version is not None and (not isinstance(version, str) or not re.fullmatch(r'(?:\d+(?:\.\d+)?|niji\s+\d+)', version.strip(), re.I)):
            raise ValueError('version должен быть номером версии (8.2) или niji 6.')
        if not re.search(r'--(?:v|niji)(?:\s|=|$)', text, re.I):
            version = version or config('default_version', '8.2')
            if version:
                if not re.fullmatch(r'(?:\d+(?:\.\d+)?|niji\s+\d+)', str(version).strip(), re.I):
                    raise ValueError('default_version должен быть номером версии или niji 6.')
                text += f' --{version.strip() if str(version).lower().startswith("niji ") else "v " + str(version).strip()}'
        if not 1 <= len(text) <= 8192:
            raise ValueError('text после добавления флагов должен содержать 1–8192 символов.')
        wait = _wait(args.get('wait', True))
        timeout = _timeout(args) if wait else 600
        start = time.monotonic()
        job = client.submit('diffusion', {'text': text})
        return _run(job, wait=wait, timeout=timeout, start=start)
    return _handle(run)


def mj_job(args: dict, **kwargs) -> str:
    def run():
        job_id = _uuid(args.get('job_id'))
        wait = _wait(args.get('wait', False))
        download = args.get('download', True)
        if not isinstance(download, bool):
            raise ValueError('download должен быть boolean.')
        timeout = _timeout(args) if wait else 600
        start = time.monotonic()
        job = client.get_job(job_id)
        return _run(job, wait=wait, timeout=timeout, download=download, start=start)
    return _handle(run)


def mj_action(args: dict, **kwargs) -> str:
    def run():
        action = args.get('action')
        if action not in ('upscale', 'variation', 'reroll'):
            raise ValueError('action должен быть upscale, variation или reroll.')
        job_id = _uuid(args.get('job_id'))
        body = {'jobId': job_id}
        if action != 'reroll':
            number = args.get('image_no')
            if isinstance(number, bool) or not isinstance(number, int) or not 0 <= number <= 23:
                raise ValueError('image_no обязателен для upscale/variation: индекс картинки в родительской задаче, 0-3 для обычной сетки (0-23 для --draft).')
            body['imageNo'] = number
            mode = args.get('mode')
            if mode is None:
                mode = 0
            if isinstance(mode, bool) or not isinstance(mode, int) or mode not in (0, 1):
                raise ValueError('mode должен быть 0 или 1: для upscale 0=subtle, 1=creative; для variation 0=subtle, 1=strong.')
            body['type'] = mode
        if args.get('remix_prompt') is not None:
            if action != 'variation' or not isinstance(args['remix_prompt'], str):
                raise ValueError('remix_prompt допустим только для variation и должен быть строкой.')
            body['remixPrompt'] = args['remix_prompt']
        wait = _wait(args.get('wait', True))
        timeout = _timeout(args) if wait else 600
        start = time.monotonic()
        job = client.submit(action, body)
        return _run(job, wait=wait, timeout=timeout, start=start)
    return _handle(run)


def mj_balance(args: dict, **kwargs) -> str:
    def run():
        client.api_key()
        payload = client.request('GET', '/account/balance', authenticated=True)
        if not isinstance(payload, dict) or payload.get('code') != 200 or not isinstance(payload.get('data'), dict):
            raise client.LegnextError('Неожиданный ответ account/balance; проверьте Legnext.')
        data = payload['data']
        return {key: data.get(key) for key in ('account_id', 'balance_usd', 'available_credits', 'available_points', 'low_balance_alert', 'updated_at')}
    return _handle(run)
