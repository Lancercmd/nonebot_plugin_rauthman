"""
Author       : Lancercmd
Date         : 2021-12-17 09:45:45
LastEditors  : Lancercmd
LastEditTime : 2022-10-05 01:21:22
Description  : None
GitHub       : https://github.com/Lancercmd
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from functools import wraps
from pathlib import Path
from typing import Optional, Union

from nonebot import get_driver
from nonebot.adapters import Bot, Event, Message, MessageTemplate
from nonebot.adapters.onebot.v11 import (
    Adapter as OneBot_V11_Adapter,
    MessageEvent as OneBot_V11_MessageEvent,
    PrivateMessageEvent as OneBot_V11_PrivateMessageEvent,
    GroupMessageEvent as OneBot_V11_GroupMessageEvent,
    FriendAddNoticeEvent as OneBot_V11_FriendAddNoticeEvent,
    FriendRecallNoticeEvent as OneBot_V11_FriendRecallNoticeEvent,
    FriendRequestEvent as OneBot_V11_FriendRequestEvent,
    GroupAdminNoticeEvent as OneBot_V11_GroupAdminNoticeEvent,
    GroupBanNoticeEvent as OneBot_V11_GroupBanNoticeEvent,
    GroupDecreaseNoticeEvent as OneBot_V11_GroupDecreaseNoticeEvent,
    GroupIncreaseNoticeEvent as OneBot_V11_GroupIncreaseNoticeEvent,
    GroupRecallNoticeEvent as OneBot_V11_GroupRecallNoticeEvent,
    GroupRequestEvent as OneBot_V11_GroupRequestEvent,
    GroupUploadNoticeEvent as OneBot_V11_GroupUploadNoticeEvent,
    HeartbeatMetaEvent as OneBot_V11_HeartbeatMetaEvent,
    HonorNotifyEvent as OneBot_V11_HonorNotifyEvent,
    LifecycleMetaEvent as OneBot_V11_LifecycleMetaEvent,
    LuckyKingNotifyEvent as OneBot_V11_LuckyKingNotifyEvent,
    PokeNotifyEvent as OneBot_V11_PokeNotifyEvent,
)
from nonebot.exception import ActionFailed
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER, Permission
from nonebot.plugin import PluginMetadata, on_command
from nonebot.rule import Rule
from nonebot.typing import T_State
from nonebot.utils import logger_wrapper
from ujson import dumps as dumpJsonS
from ujson import loads as loadJsonS

from ._FileStation import FileStation, generate_savedata_path

log = logger_wrapper(Path(__file__).stem)
_config = get_driver().config


class Config:
    savedata: str = getattr(_config, "savedata", "") or ""
    ram_policy: int = getattr(_config, "ram_policy", 0) or 0
    ram_cmd: str = getattr(_config, "ram_cmd", "ram") or "ram"
    ram_add: str = getattr(_config, "ram_add", "-a") or "-a"
    ram_rm: str = getattr(_config, "ram_rm", "-r") or "-r"
    ram_show: str = getattr(_config, "ram_show", "-s") or "-s"
    ram_available: str = getattr(_config, "ram_available", "-v") or "-v"


config = Config()


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

    filepath: str = Path(generate_savedata_path()) / "global.json"
    permission: Permission = SUPERUSER
    policy: int = config.ram_policy
    cmd: str = config.ram_cmd
    add: str = config.ram_add
    rm: str = config.ram_rm
    show: str = config.ram_show
    available: str = config.ram_available


_opt = Options()


class RAM_Control(FileStation):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(_opt.filepath, RAM().module_name, *args, **kwargs)

    def load(self) -> dict:
        super().load()
        self.standardize()
        return self.data

    def reload(self, *, full: bool = False) -> None:
        super().reload(full=full)
        self.standardize()

    def standardize(self) -> None:
        if not self.check_keys():
            if not self._get("RAM"):
                log(
                    "WARNING",
                    "RAM data not exist. Try converting from legacy automatically.",
                )
                self.convert_from_legacy()
                self.save(snapshot=True)
            self.vacuum()
            log("SUCCESS", "Initialized: " + self._filepath.name)
        else:
            log("SUCCESS", "<g>Healthy</g>: " + self._filepath.name)
        for f in fields(RAM):
            setattr(self, f.name, self.get(f.name))

    def check_keys(self) -> bool:
        return sorted(list(self.keys())) == sorted([f.name for f in fields(RAM)])

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
            self.reload()

        return wrapper

    def convert_from_legacy(self) -> None:
        _path = Path(generate_savedata_path()) / "auth.json"
        _fs = FileStation(_path)
        if list(_fs._keys()) == list(RAM().cqhttp.keys()):
            log("INFO", "Converting from legacy...")
            _base = RAM()
            _base.cqhttp = _fs._data
            self.data = _base.__dict__
        else:
            log("WARNING", "Legacy data not vanilla, skip converting.")

    _compatible_adapters = {
        OneBot_V11_Adapter.get_name(): "onebot_v11",
    }

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
                cache = loadJsonS(dumpJsonS(services))
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


@worker.handle()
async def _(
    event: OneBot_V11_GroupMessageEvent,
    state: T_State,
    args: Message = CommandArg(),
) -> None:
    state["group_id"] = str(event.group_id)
    _plain_text = args.extract_plain_text()
    if _plain_text:
        state["services"] = _plain_text


@worker.handle()
async def _(
    event: OneBot_V11_MessageEvent,
    state: T_State,
    args: Message = CommandArg(),
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
async def _(event: Event, state: T_State) -> None:
    # fmt: off
    supported = isinstance(event, OneBot_V11_MessageEvent)
    # fmt: on
    if supported:
        state["add"] = _opt.add
        state["rm"] = _opt.rm
        state["show"] = _opt.show
        state["available"] = _opt.available
        state["prompt"] = "请输入需要操作的群号，并用空格隔开~"
    else:
        log("WARNING", f"Unsupported event {event.get_event_name()}")
        return


@worker.got("group_id", prompt=MessageTemplate("{prompt}"))
async def _(state: T_State) -> None:
    try:
        _input = str(state["group_id"])
        _group_id = _input.split(" ")
        group_ids = []
        for i in _group_id:
            if i.isdigit():
                group_ids.append(int(i))
            else:
                await worker.finish("Invalid input")
        if group_ids:
            state["group_ids"] = group_ids
        else:
            await worker.finish("Invalid input")
    except ActionFailed as e:
        log(
            "WARNING",
            f"ActionFailed {e.info['retcode']} {e.info['msg'].lower()} {e.info['wording']}",
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
    event: OneBot_V11_MessageEvent,
    state: T_State,
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
                            f"群 Level {prev} => " + str(state["services"])
                        )
                    else:
                        segments.append(
                            f"群 {group_id} Level {prev} => " + str(state["services"])
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
            log("WARNING", f"Invalid input: {_services}")
    except ActionFailed as e:
        log(
            "WARNING",
            f"ActionFailed {e.info['retcode']} {e.info['msg'].lower()} {e.info['wording']}",
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
            log("WARNING", "At least 1 space found in the service name")
            warning = True
        available.append(service)

    async def _check(bot: Bot, group_id: int) -> bool:
        if service and _opt.policy == 0:
            return _amc.check_universal(bot, group_id, service)
        elif level and _opt.policy == 1:
            return _amc.check_universal(bot, group_id) >= level
        else:
            log(
                "WARNING",
                "Failed while checking the service or level. Please check the configuration.",
            )
            return True

    async def _isInService(bot: Bot, event: Event) -> bool:
        if bot.type == OneBot_V11_Adapter.get_name():
            if isinstance(event, OneBot_V11_PrivateMessageEvent):
                return True
            elif isinstance(event, OneBot_V11_GroupMessageEvent):
                group_id = event.group_id
                return await _check(bot, group_id)
            elif isinstance(event, OneBot_V11_GroupUploadNoticeEvent):
                group_id = event.group_id
                return await _check(bot, group_id)
            elif isinstance(event, OneBot_V11_GroupAdminNoticeEvent):
                group_id = event.group_id
                return await _check(bot, group_id)
            elif isinstance(event, OneBot_V11_GroupDecreaseNoticeEvent):
                group_id = event.group_id
                return await _check(bot, group_id)
            elif isinstance(event, OneBot_V11_GroupIncreaseNoticeEvent):
                group_id = event.group_id
                return await _check(bot, group_id)
            elif isinstance(event, OneBot_V11_GroupBanNoticeEvent):
                group_id = event.group_id
                return await _check(bot, group_id)
            elif isinstance(event, OneBot_V11_FriendAddNoticeEvent):
                return True
            elif isinstance(event, OneBot_V11_GroupRecallNoticeEvent):
                group_id = event.group_id
                return await _check(bot, group_id)
            elif isinstance(event, OneBot_V11_FriendRecallNoticeEvent):
                return True
            elif isinstance(event, OneBot_V11_PokeNotifyEvent):
                group_id = event.group_id
                return await _check(bot, group_id)
            elif isinstance(event, OneBot_V11_LuckyKingNotifyEvent):
                group_id = event.group_id
                return await _check(bot, group_id)
            elif isinstance(event, OneBot_V11_HonorNotifyEvent):
                group_id = event.group_id
                return await _check(bot, group_id)
            elif isinstance(event, OneBot_V11_FriendRequestEvent):
                return True
            elif isinstance(event, OneBot_V11_GroupRequestEvent):
                group_id = event.group_id
                return await _check(bot, group_id)
            elif isinstance(event, OneBot_V11_LifecycleMetaEvent):
                return True
            elif isinstance(event, OneBot_V11_HeartbeatMetaEvent):
                return True

            else:
                log("WARNING", f"Unsupported event: {event.get_event_name()}")
                return True
        else:
            log("WARNING", f"Unsupported adapter: {bot.type}")
            return True

    return Rule(_isInService)


__plugin_meta__ = PluginMetadata(
    name="RAM - 基于规则的授权管理",
    description="为 Matcher 配置一条或多条 Rule 来实现功能的授权管理",
    usage=f"{config.ram_cmd} [{config.ram_add} <service>] [{config.ram_rm} <service>] [{config.ram_show}] [{config.ram_available}] [\d+]",
    extra={"author": "Lancercmd"},
)
