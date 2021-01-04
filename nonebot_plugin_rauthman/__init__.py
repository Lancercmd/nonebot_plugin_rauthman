'''
Author       : Lancercmd
Date         : 2020-10-12 10:20:46
LastEditors  : Lancercmd
LastEditTime : 2021-01-04 17:05:52
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
from nonebot.adapters import Bot, Event
from nonebot.adapters.cqhttp.event import (GroupMessageEvent, MessageEvent,
                                           MetaEvent, NoticeEvent,
                                           RequestEvent)
from nonebot.exception import ActionFailed
from nonebot.permission import SUPERUSER
from nonebot.plugin import on_command
from nonebot.rule import Rule
from nonebot.typing import T_State

try:
    import ujson as json
except ImportError:
    import json

config = nonebot.get_driver().config


def checkDir(dir: str):
    if not path.exists(dir):
        os.makedirs(dir)


def dumpJson(dir: str, dict: dict):
    _dict = {}
    for i in sorted(list(dict.keys())):
        _dict[i] = dict[i]
    with open(dir, 'w', encoding='utf-8') as file:
        json.dump(_dict, file, ensure_ascii=False, indent=4)


def loadJson(dir: str, dict: dict = {}) -> dict:
    if path.exists(dir):
        with open(dir, 'r', encoding='utf-8') as file:
            return json.load(file)
    else:
        return deepcopy(dict)


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
        show = '-s' if not config.auth_show else config.auth_show
        available = '-av' if not config.auth_available else config.auth_available
    manager = on_command(options.command, permission=SUPERUSER, block=True)

    def set(group_id: int, services: Optional[list] = None, level: Optional[int] = None):
        data = loadJson(auth.authData)
        if not f'{group_id}' in data:
            data[f'{group_id}'] = {}
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
        checkDir(getSave())
        dumpJson(auth.authData, data)

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
        elif not 'level' in data[f'{group_id}']:
            return 0
        return data[f'{group_id}']['level']

    def show(group_id: int) -> Optional[dict]:
        data = loadJson(auth.authData)
        if not f'{group_id}' in data:
            return None
        status = {}
        for i in list(data[f'{group_id}'].keys()):
            status[i] = deepcopy(data[f'{group_id}'][i])
        return status if status else None

    @manager.handle()
    async def _(bot: Bot, event: Event, state: T_State):
        if isinstance(event, MessageEvent):
            if isinstance(event, GroupMessageEvent):
                if event.group_id:
                    state['group_id'] = f'{event.group_id}'
                    if event.get_plaintext():
                        state['services'] = event.get_plaintext()
        else:
            logger.warning('Not supported: rauthman')
            return

    @manager.got('group_id', prompt='请输入需要调整权限的群号，并用空格隔开~')
    async def _(bot: Bot, event: Event, state: T_State):
        if isinstance(event, MessageEvent):
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
                            logger.error(
                                f'ActionFailed | {e.info["msg"].lower()} | retcode = {e.info["retcode"]} | {e.info["wording"]}'
                            )
                            return
                else:
                    try:
                        await auth.manager.finish('Invalid input')
                    except ActionFailed as e:
                        logger.error(
                            f'ActionFailed | {e.info["msg"].lower()} | retcode = {e.info["retcode"]} | {e.info["wording"]}'
                        )
                        return
            if group_ids:
                state['group_ids'] = group_ids
            else:
                try:
                    await auth.manager.finish('Invalid input')
                except ActionFailed as e:
                    logger.error(
                        f'ActionFailed | {e.info["msg"].lower()} | retcode = {e.info["retcode"]} | {e.info["wording"]}'
                    )
                    return
        else:
            logger.warning('Not supported: rauthman')
            return

    @manager.got('services', prompt='请输入调整后的群级别，或 启用 / 禁用 的功能~')
    async def _(bot: Bot, event: Event, state: T_State):
        if isinstance(event, MessageEvent):
            services = state['services'].split(' ')
            if len(services) == 1:
                if services[0].isnumeric():
                    segments = []
                    for group_id in state['group_ids']:
                        prev = auth.check(group_id)
                        auth.set(group_id, level=int(services[0]))
                        if len(state['group_ids']) == 1:
                            segments.append(
                                f'群 Level {prev} => {event.get_plaintext()}'
                            )
                        else:
                            segments.append(
                                f'群 {group_id} Level {prev} => {event.get_plaintext()}'
                            )
                    try:
                        await auth.manager.finish('\n'.join(segments))
                    except ActionFailed as e:
                        logger.error(
                            f'ActionFailed | {e.info["msg"].lower()} | retcode = {e.info["retcode"]} | {e.info["wording"]}'
                        )
                        return
                elif services[0] == auth.options.show:
                    queue = []
                    for group_id in state['group_ids']:
                        status = auth.show(group_id)
                        if status:
                            keys = list(status.keys())
                            layout = []
                            _status = []
                            for i in keys:
                                if isinstance(status[i], list):
                                    _status.append(
                                        ' '.join(status[i]).replace(',', '')
                                    )
                                else:
                                    _status.append(status[i])
                            for i in range(len(keys)):
                                if keys[i] == 'enabled':
                                    layout.append(f'当前启用：{_status[i]}')
                                elif keys[i] == 'level':
                                    layout.append(f'功能级别：{_status[i]}')
                                else:
                                    layout.append(f'{keys[i]}: {_status[i]}')
                            queue.append(f'{group_id} ' + ' | '.join(layout))
                        if len(queue) > 9:
                            break
                    try:
                        await auth.manager.finish('\n'.join(queue))
                    except ActionFailed as e:
                        logger.error(
                            f'ActionFailed | {e.info["msg"].lower()} | retcode = {e.info["retcode"]} | {e.info["wording"]}'
                        )
                        return
                elif services[0] == auth.options.available:
                    try:
                        await auth.manager.finish(''.join(['全局可用：', ' '.join(available)]))
                    except ActionFailed as e:
                        logger.error(
                            f'ActionFailed | {e.info["msg"].lower()} | retcode = {e.info["retcode"]} | {e.info["wording"]}'
                        )
                        return
            elif services[0] == auth.options.add:
                for group_id in state['group_ids']:
                    auth.set(group_id, services)
                services.remove(auth.options.add)
                invalid = []
                for i in services:
                    if not i in available:
                        invalid.append(i)
                for i in invalid:
                    services.remove(i)
                message = []
                if services:
                    message.append(f'已启用：{" ".join(services)}')
                if invalid:
                    message.append(f'未找到：{" ".join(invalid)}')
                try:
                    await auth.manager.finish('\n'.join(message))
                except ActionFailed as e:
                    logger.error(
                        f'ActionFailed | {e.info["msg"].lower()} | retcode = {e.info["retcode"]} | {e.info["wording"]}'
                    )
                    return
            elif services[0] == auth.options.rm:
                for group_id in state['group_ids']:
                    auth.set(group_id, services)
                services.remove(auth.options.rm)
                invalid = []
                for i in services:
                    if not i in available:
                        invalid.append(i)
                for i in invalid:
                    services.remove(i)
                message = []
                if services:
                    message.append(f'已禁用：{" ".join(services)}')
                if invalid:
                    message.append(f'未找到：{" ".join(invalid)}')
                try:
                    await auth.manager.finish('\n'.join(message))
                except ActionFailed as e:
                    logger.error(
                        f'ActionFailed | {e.info["msg"].lower()} | retcode = {e.info["retcode"]} | {e.info["wording"]}'
                    )
                    return
        else:
            logger.warning('Not supported: rauthman')
            return


warning = False


def isInService(service: Optional[str] = None, level: Optional[int] = None) -> Rule:
    global warning
    if service and not service in available:
        if ' ' in service and not warning:
            logger.warning('At least 1 space found in the service name')
            warning = True
        available.append(service)

    async def _isInService(bot: Bot, event: Event, state: T_State) -> bool:
        if isinstance(event, MessageEvent):
            if isinstance(event, GroupMessageEvent):
                if service and auth.policy == 0:
                    return auth.check(event.group_id, service)
                elif level and auth.policy == 1:
                    return bool(auth.check(event.group_id) >= level)
            else:
                return True
        elif isinstance(event, NoticeEvent):
            if service and auth.policy == 0:
                return auth.check(event.group_id, service)
            elif level and auth.policy == 1:
                return bool(auth.check(event.group_id) >= level)
            else:
                return True
        elif isinstance(event, RequestEvent):
            if service and auth.policy == 0:
                return auth.check(event.group_id, service)
            elif level and auth.policy == 1:
                return bool(auth.check(event.group_id) >= level)
            else:
                return True
        elif isinstance(event, MetaEvent):
            if service and auth.policy == 0:
                return auth.check(event.group_id, service)
            elif level and auth.policy == 1:
                return bool(auth.check(event.group_id) >= level)
            else:
                return True
        else:
            return False
    return Rule(_isInService)


available = []
