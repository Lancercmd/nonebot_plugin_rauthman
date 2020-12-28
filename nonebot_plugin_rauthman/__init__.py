'''
Author       : Lancercmd
Date         : 2020-10-12 10:20:46
LastEditors  : Lancercmd
LastEditTime : 2020-12-28 11:16:04
Description  : None
GitHub       : https://github.com/Lancercmd
'''
import os
import sys
from copy import deepcopy
from os import path
from typing import Optional

import nonebot
from loguru import logger
from nonebot.adapters.cqhttp import Bot, Event
from nonebot.exception import ActionFailed
from nonebot.permission import SUPERUSER
from nonebot.plugin import on_command
from nonebot.rule import Rule

try:
    import ujson as json
except ImportError:
    import json

config = nonebot.get_driver().config


def checkDir(dir: str):
    if not path.exists(dir):
        os.makedirs(dir)


def dumpJson(dir: str, dict: dict):
    with open(dir, 'w', encoding='utf-8') as file:
        json.dump(dict, file, ensure_ascii=False, indent=4)


def loadJson(dir: str, dict: dict = {}) -> dict:
    if path.exists(dir):
        with open(dir, 'r', encoding='utf-8') as file:
            return json.load(file)
    else:
        return deepcopy(dict)


def updateJson(dir: str, dict: dict) -> dict:
    dumpJson(dir, dict)
    return loadJson(dir)


def getSave(id: int = None, flag: int = 0) -> str:
    if not id:
        return path.join(sys.path[0], config.savedata)
    elif flag == 0:
        return path.join(sys.path[0], config.savedata, 'private', f'{id}.json')
    elif flag == 1:
        return path.join(sys.path[0], config.savedata, 'group', f'{id}.json')


class auth:
    authData = path.join(getSave(), 'auth.json')
    policy = 0 if not config.auth_policy else config.auth_policy

    class options:
        command = 'auth' if not config.auth_command else config.auth_command
        add = '-a' if not config.auth_add else config.auth_add
        rm = '-rm' if not config.auth_rm else config.auth_rm
    manager = on_command(options.command, permission=SUPERUSER, block=True)

    def set(group_id: int, services: Optional[list] = None, level: Optional[int] = None):
        data = loadJson(auth.authData)
        if not f'{group_id}' in data:
            data[f'{group_id}'] = {}
            latest = {}
            for i in sorted(data.keys()):
                latest[i] = data[i]
            checkDir(path.dirname(auth.authData))
            data = updateJson(auth.authData, latest)
        if services:
            cache = deepcopy(services)
            if not 'enabled' in data[f'{group_id}']:
                data[f'{group_id}']['enabled'] = []
            if cache[0] == auth.options.add:
                cache.remove(auth.options.add)
                for service in cache:
                    if not service in data[f'{group_id}']['enabled']:
                        data[f'{group_id}']['enabled'].append(service)
            elif cache[0] == auth.options.rm:
                cache.remove(auth.options.rm)
                for service in cache:
                    if service in data[f'{group_id}']['enabled']:
                        data[f'{group_id}']['enabled'].remove(service)
            data[f'{group_id}']['enabled'].sort()
        else:
            data[f'{group_id}']['level'] = level
        latest = {}
        for i in sorted(data.keys()):
            latest[i] = data[i]
        checkDir(getSave())
        dumpJson(auth.authData, latest)

    def check(group_id: int, service: Optional[str] = None) -> int:
        data = loadJson(auth.authData)
        if not f'{group_id}' in data:
            return False
        if service:
            if not 'enabled' in data[f'{group_id}']:
                return False
            return bool(service in data[f'{group_id}']['enabled'])
        if not f'{group_id}' in data:
            return 0
        return data[f'{group_id}']['level']

    @manager.handle()
    async def _(bot: Bot, event: Event, state: dict):
        if event.group_id:
            state['group_id'] = f'{event.group_id}'
            if event.plain_text:
                state['services'] = f'{event.plain_text}'

    @manager.got('group_id', prompt='请输入需要调整权限的群号，并用空格隔开~')
    async def _(bot: Bot, event: Event, state: dict):
        input = state['group_id'].split(' ')
        group_ids = []
        for i in input:
            if i.isnumeric():
                if not i in group_ids and i != '1':
                    group_ids.append(int(i))
                else:
                    try:
                        await auth.manager.finish('请不要用此方式进行全局设置哦~')
                    except ActionFailed as e:
                        logger.error(f'ActionFailed retcode = {e.retcode}')
                        return
            else:
                try:
                    await auth.manager.finish('Invalid input')
                except ActionFailed as e:
                    logger.error(f'ActionFailed retcode = {e.retcode}')
                    return
        if group_ids:
            state['group_ids'] = group_ids
        else:
            try:
                await auth.manager.finish('Invalid input')
            except ActionFailed as e:
                logger.error(f'ActionFailed retcode = {e.retcode}')
                return

    @manager.got('services', prompt='请输入调整后的群级别，或 启用 / 禁用 的功能~')
    async def _(bot: Bot, event: Event, state: dict):
        services = state['services'].split(' ')
        if len(services) == 1:
            if services[0].isnumeric():
                segments = []
                for group_id in state['group_ids']:
                    prev = auth.check(group_id)
                    auth.set(group_id, level=int(services[0]))
                    if len(state['group_ids']) == 1:
                        segments.append(
                            f'群 Level {prev} => {event.plain_text}'
                        )
                    else:
                        segments.append(
                            f'群 {group_id} Level {prev} => {event.plain_text}'
                        )
                try:
                    await auth.manager.finish('\n'.join(segments))
                except ActionFailed as e:
                    logger.error(f'ActionFailed retcode = {e.retcode}')
                    return
        elif services[0] == auth.options.add:
            for group_id in state['group_ids']:
                auth.set(group_id, services)
            services.remove(auth.options.add)
            try:
                await auth.manager.finish(''.join(['已启用：', ' '.join(services)]))
            except ActionFailed as e:
                logger.error(f'ActionFailed retcode = {e.retcode}')
                return
        elif services[0] == auth.options.rm:
            for group_id in state['group_ids']:
                auth.set(group_id, services)
            services.remove(auth.options.rm)
            try:
                await auth.manager.finish(''.join(['已禁用：', ' '.join(services)]))
            except ActionFailed as e:
                logger.error(f'ActionFailed retcode = {e.retcode}')
                return


def isInService(service: Optional[str] = None, level: Optional[int] = None) -> Rule:
    _service = service
    _level = level

    async def _isInService(bot: Bot, event: Event, state: dict) -> bool:
        if event.group_id:
            if _service and auth.policy == 0:
                return auth.check(event.group_id, _service)
            elif _level and auth.policy == 1:
                return bool(auth.check(event.group_id) >= _level)
        else:
            return True
    return Rule(_isInService)
