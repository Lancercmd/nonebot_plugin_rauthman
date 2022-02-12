"""
Author       : Lancercmd
Date         : 2021-12-17 09:45:45
LastEditors  : Lancercmd
LastEditTime : 2022-02-12 18:24:21
Description  : None
GitHub       : https://github.com/Lancercmd
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from functools import wraps
from os.path import join
from pathlib import Path
from sys import path as sys_path
from typing import Optional, Union

from loguru import logger
from nonebot import get_driver
from nonebot.adapters import Bot, Event, Message, MessageTemplate
from nonebot.adapters.onebot.v11 import Adapter as OneBot_V11_Adapter
from nonebot.adapters.onebot.v11 import (
    FriendAddNoticeEvent,
    FriendRecallNoticeEvent,
    FriendRequestEvent,
    GroupMessageEvent,
    MessageEvent,
    MetaEvent,
    NoticeEvent,
    PrivateMessageEvent,
    RequestEvent,
)
from nonebot.exception import ActionFailed
from nonebot.params import CommandArg, State
from nonebot.permission import SUPERUSER, Permission
from nonebot.plugin import on_command
from nonebot.rule import Rule
from nonebot.typing import T_State

from ._FileStation import FileStation
from ._permission import onFocus

config = get_driver().config


def generate_savedata_path(
    id: int = None, *, flag: int = 0, _bot: Bot = None, _type: str = None
) -> str:
    """
    ###   说明
    -     获取指定个人或群聊 QQ 号的存档路径

    ###   参数
    -     id: int  指定全局，个人或群聊的 QQ 号，默认为全局
    -     flag: int  在个人或群聊间切换，默认为个人，可选值如下：
        -     0  个人
        -     1  群聊
    -     bot: Bot  当前 Bot 实例，优先于 type 默认为 None
    -     type: str  指定 adapter 类型，默认为 None
    """
    _path = join(sys_path[0], getattr(config, "savedata") or "")
    if _bot:
        _path = join(_path, _bot.type)
    elif _type:
        _path = join(_path, _type)
    if id:
        if flag == 0:
            _path = join(_path, "private", f"{id}.json")
        elif flag == 1:
            _path = join(_path, "group", f"{id}.json")
        else:
            raise ValueError("UnknownFlag")
    return _path


@dataclass
class RAM:
    """
    ##    RAM - 基于规则的授权管理
    -     为 Matcher 配置一条或多条 Rule 来实现功能的授权管理

    ###   当前已适配的 adapter 类型
    -     OneBot V11 (CQHTTP) （仅控制群聊）
    """

    module_name: str = "RAM"
    cqhttp: dict = field(default_factory=lambda: {"group": {}, "private": {}})
    onebot_v11: dict = field(default_factory=lambda: {"group": {}, "private": {}})


@dataclass
class Options:
    """
    ###   RAM - 配置项
    ###   参数
    -     cmd: str  指令名，或者叫触发词
    -     policy: int  授权策略，可选值如下：
        -     0  根据可用功能
        -     1  根据服务级别

    ###   参数 - 根据可用功能
    -     add: str  启用功能
    -     rm: str  禁用功能
    -     show: str  展示群功能状态
    -     available: str  展示全局可用功能
    """

    filepath: str = join(generate_savedata_path(), "global.json")
    permission: Permission = SUPERUSER
    policy: int = getattr(config, "ram_policy") or 0
    cmd: str = getattr(config, "ram_cmd") or "ram"
    add: str = getattr(config, "ram_add") or "-a"
    rm: str = getattr(config, "ram_rm") or "-r"
    show: str = getattr(config, "ram_show") or "-s"
    available: str = getattr(config, "ram_available") or "-v"


_opt = Options()


class RAM_Control(FileStation):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(_opt.filepath, RAM().module_name, *args, **kwargs)

    def load(self) -> dict:
        super().load()
        self.standardize()
        return self.data

    def reload(self, **kwargs) -> None:
        super().reload(**kwargs)
        self.standardize()

    def standardize(self) -> None:
        if not self.check_keys():
            if not self._get("RAM"):
                self.convert_from_legacy()
            self.vacuum()
        for key in RAM().__dataclass_fields__.keys():
            setattr(self, key, self.get(key))

    def check_keys(self) -> bool:
        return self.keys() == RAM().__dataclass_fields__.keys()

    def vacuum(self) -> None:
        _base = RAM()
        _base.cqhttp = self.get("cqhttp", RAM().cqhttp)
        _base.onebot_v11 = self.get("onebot_v11", RAM().onebot_v11)
        self.data = _base.__dict__

    def applicator(func) -> None:
        """
        Decorator as an instance method.

        Apply changes to the `self.data` dictionary.

        Then apply changes to the particular `module_name` dictionary in `self._data`.

        Finally, save the changes.
        """

        @wraps(func)
        def wrapper(self: RAM_Control, *args, **kwargs) -> None:
            func(self, *args, **kwargs)
            self._update(self._module_name, self.data)
            self.save()
            self.reload(full=True)

        return wrapper

    def convert_from_legacy(self) -> None:
        _path = Path(generate_savedata_path()) / "auth.json"
        _fs = FileStation(_path)
        if list(_fs._keys()) == list(RAM().cqhttp.keys()):
            _base = RAM()
            _base.cqhttp = _fs._data
            self.data = _base.__dict__

    _compatible_adapters = {OneBot_V11_Adapter.get_name(): "onebot_v11"}

    def _check_adapter(self, bot: Bot) -> bool:
        if bot.type in self._compatible_adapters:
            self._base = getattr(self, RAM_Control._compatible_adapters[bot.type])
            return True
        return False

    @applicator
    def set_universal(
        self: RAM_Control,
        bot: Bot,
        group_id: int,
        services: Optional[list[str]] = None,
        level: Optional[int] = None,
    ) -> None:
        if self._check_adapter(bot):
            _groups = self._base["group"]
            if not f"{group_id}" in _groups:
                _groups[f"{group_id}"] = {}
            _home = _groups[f"{group_id}"]
            if services:
                cache = deepcopy(services)
                if not "enabled" in _home:
                    _home["enabled"] = []
                if not "disabled" in _home:
                    _home["disabled"] = []
                _enabled = _home["enabled"]
                _disabled = _home["disabled"]
                if cache[0] == _opt.add:
                    cache.remove(_opt.add)
                    _valid = True
                    for service in cache:
                        if not service in available:
                            _valid = False
                    if _valid:
                        _enabled += cache
                        for service in _disabled:
                            if service in _enabled:
                                _disabled.remove(service)
                    if not _disabled:
                        del _home["disabled"]
                elif cache[0] == _opt.rm:
                    cache.remove(_opt.rm)
                    _valid = True
                    for service in cache:
                        if not service in available:
                            _valid = False
                    if _valid:
                        _disabled += cache
                        for service in _enabled:
                            if service in _disabled:
                                _enabled.remove(service)
                    if not _enabled:
                        del _home["enabled"]
                if "enabled" in _home:
                    _home["enabled"] = list(set(_enabled))
                    _home["enabled"].sort()
                if "disabled" in _home:
                    _home["disabled"] = list(set(_disabled))
                    _home["disabled"].sort()
            else:
                _home["level"] = level

    def check_universal(
        self: RAM_Control, bot: Bot, group_id: int, service: Optional[str] = None
    ) -> Union[bool, int]:
        if self._check_adapter(bot):
            _groups = self._base["group"]
            if not f"{group_id}" in _groups:
                return 0
            elif service:
                if not "enabled" in _groups[f"{group_id}"]:
                    return 0
                else:
                    return bool(service in _groups[f"{group_id}"]["enabled"])
            elif not "level" in _groups[f"{group_id}"]:
                return 0
            else:
                return _groups[f"{group_id}"]["level"]
        else:
            return 0

    def show_universal(self: RAM_Control, bot: Bot, group_id: int) -> dict:
        data = {}
        if self._check_adapter(bot):
            _groups = self._base["group"]
            if f"{group_id}" in _groups:
                for i in _groups[f"{group_id}"]:
                    data[i] = _groups[f"{group_id}"][i]
        return data


_amc = RAM_Control()
worker = on_command(_opt.cmd, permission=_opt.permission)


@worker.permission_updater
async def _(event: Event) -> Permission:
    return await onFocus(event)


@worker.handle()
async def _(
    event: GroupMessageEvent, state: T_State = State(), args: Message = CommandArg()
) -> None:
    state["group_id"] = str(event.group_id)
    _plain_text = args.extract_plain_text()
    if _plain_text:
        state["services"] = _plain_text


@worker.handle()
async def _(
    event: PrivateMessageEvent, state: T_State = State(), args: Message = CommandArg()
) -> None:
    actions = args.extract_plain_text().split(" ", 1)
    if len(actions) == 1:
        if actions[0] == _opt.available:
            state["group_id"] = "0"
            state["services"] = _opt.available
        elif actions[0] == _opt.show:
            state["services"] = _opt.show
    elif actions[0] == _opt.show:
        if actions[1].isdigit():
            state["group_id"] = actions[1]
        state["services"] = _opt.show


@worker.handle()
async def _(event: Event, state: T_State = State()) -> None:
    supported = isinstance(event, MessageEvent)
    if supported:
        state["add"] = _opt.add
        state["rm"] = _opt.rm
        state["show"] = _opt.show
        state["available"] = _opt.available
        state["prompt"] = "请输入需要操作的群号，并用空格隔开~"
    else:
        logger.warning("Not supported: RAM")
        return


@worker.got("group_id", prompt=MessageTemplate("{prompt}"))
async def _(event: MessageEvent, state: T_State = State()) -> None:
    try:
        _input = str(state["group_id"])
        _group_id = _input.split(" ")
        group_ids = []
        for i in _group_id:
            if i.isdigit():
                if not i in group_ids and i != "1":
                    group_ids.append(int(i))
                else:
                    await worker.finish("请不要用此方式进行全局设置哦~")
            else:
                await worker.finish("Invalid input")
        if group_ids:
            state["group_ids"] = group_ids
        else:
            await worker.finish("Invalid input")
    except ActionFailed as e:
        logger.warning(
            f"ActionFailed {e.info['retcode']} {e.info['msg'].lower()} {e.info['wording']}"
        )
        return
    state["prompt"] = "\n".join(
        [
            "请继续输入——",
            f"{state['add']} sv1 sv2 ... | 启用功能",
            f"{state['rm']} sv1 sv2 ... | 禁用功能",
            f"{state['show']} | 查看群功能状态",
            f"{state['available']} | 展示全局可用功能",
            "※ 设置群级别请直接发送数字",
        ]
    )


@worker.got("services", prompt=MessageTemplate("{prompt}"))
async def _(
    bot: Bot,
    event: MessageEvent,
    state: T_State = State(),
    args: Message = CommandArg(),
) -> None:
    try:
        _input = str(state["services"])
        _services = _input.split(" ")
        if len(_services) == 1:
            if _services[0].isdigit():
                if int(_services[0]) > 99999999999999999999:
                    await worker.finish(f"Level too large: {_services[0]}")
                segments = []
                for group_id in state["group_ids"]:
                    prev = _amc.check_universal(bot, group_id)
                    _amc.set_universal(bot, group_id, level=int(_services[0]))
                    if len(state["group_ids"]) == 1:
                        segments.append(
                            f"群 Level {prev} => {args.extract_plain_text()}"
                        )
                    else:
                        segments.append(
                            f"群 {group_id} Level {prev} => {args.extract_plain_text()}"
                        )
                await worker.finish("\n".join(segments))
            elif _services[0] == _opt.show:
                queue = []
                for group_id in state["group_ids"]:
                    status = _amc.show_universal(bot, group_id)
                    if status:
                        keys = list(status.keys())
                        layout = []
                        _status = []
                        for i in keys:
                            if isinstance(status[i], list):
                                _status.append(" ".join(status[i]).replace(",", ""))
                            else:
                                _status.append(status[i])
                        for i in range(len(keys)):
                            if keys[i] == "enabled":
                                if _status:
                                    layout.append(f"当前启用：{_status[i]}")
                                else:
                                    layout.append(f"当前启用：无")
                            elif keys[i] == "level":
                                layout.append(f"功能级别：{_status[i]}")
                            else:
                                layout.append(f"{keys[i]}: {_status[i]}")
                        queue.append(f"{group_id} " + " | ".join(layout))
                    else:
                        queue.append(f"{group_id} " + "群聊未注册")
                    if len(queue) > 9:
                        break
                await worker.finish("\n".join(queue))
            elif _services[0] == _opt.available:
                await worker.finish("".join(["全局可用：", " ".join(available)]))
            else:
                await worker.finish("Invalid input")
        elif _services[0] == _opt.add:
            for group_id in state["group_ids"]:
                _amc.set_universal(bot, group_id, _services)
            _services.remove(_opt.add)
            invalid = []
            for i in _services:
                if not i in available:
                    invalid.append(i)
            for i in invalid:
                _services.remove(i)
            message = []
            if _services:
                message.append(f"已启用：{' '.join(_services)}")
            if invalid:
                message.append(f"未找到：{' '.join(invalid)}")
            await worker.finish("\n".join(message))
        elif _services[0] == _opt.rm:
            for group_id in state["group_ids"]:
                _amc.set_universal(bot, group_id, _services)
            _services.remove(_opt.rm)
            invalid = []
            for i in _services:
                if not i in available:
                    invalid.append(i)
            for i in invalid:
                _services.remove(i)
            message = []
            if _services:
                message.append(f"已禁用：{' '.join(_services)}")
            if invalid:
                message.append(f"未找到：{' '.join(invalid)}")
            await worker.finish("\n".join(message))
        else:
            logger.warning(f"Invalid input: {_services}")
    except ActionFailed as e:
        logger.warning(
            f"ActionFailed {e.info['retcode']} {e.info['msg'].lower()} {e.info['wording']}"
        )


available = []
warning = False


def isInService(service: Optional[str] = None, level: Optional[int] = None) -> Rule:
    """
    ###   RAM - Rule
    -     为 Matcher 配置一条或多条 Rule 来实现功能的授权管理
    -     通过下列方法之一，判断对应功能是否可用
      -     功能是否对群聊启用
      -     群聊是否满足级别

    ###   参数
    -     service: str  功能名称
    -     level: int  功能级别
    """
    global warning
    if service and not service in available:
        if " " in service and not warning:
            logger.warning("At least 1 space found in the service name")
            warning = True
        available.append(service)

    async def _isInService(bot: Bot, event: Event) -> bool:
        if isinstance(event, MessageEvent):
            if isinstance(event, GroupMessageEvent):
                if service and _opt.policy == 0:
                    return _amc.check_universal(
                        bot, getattr(event, "group_id"), service
                    )
                elif level and _opt.policy == 1:
                    return (
                        _amc.check_universal(bot, getattr(event, "group_id")) >= level
                    )
            else:
                return True
        elif isinstance(event, NoticeEvent):
            if isinstance(event, FriendAddNoticeEvent) or isinstance(
                event, FriendRecallNoticeEvent
            ):
                return True
            elif service and _opt.policy == 0:
                return (
                    _amc.check_universal(bot, getattr(event, "group_id"), service)
                    if getattr(event, "group_id")
                    else False
                )
            elif level and _opt.policy == 1:
                return (
                    _amc.check_universal(bot, getattr(event, "group_id")) >= level
                    if getattr(event, "group_id")
                    else False
                )
        elif isinstance(event, RequestEvent):
            if isinstance(event, FriendRequestEvent):
                return True
            elif service and _opt.policy == 0:
                return (
                    _amc.check_universal(bot, getattr(event, "group_id"), service)
                    if getattr(event, "group_id")
                    else False
                )
            elif level and _opt.policy == 1:
                return (
                    _amc.check_universal(bot, getattr(event, "group_id")) >= level
                    if getattr(event, "group_id")
                    else False
                )
        elif isinstance(event, MetaEvent):
            return True
        else:
            logger.warning("Not supported: RAM")
            return True

    return Rule(_isInService)
