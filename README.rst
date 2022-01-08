##############################################################################
RAM - 基于规则的授权管理器
##############################################################################
******************************************************************************
前言
******************************************************************************
| 本项目将对 PyPI 上的发行版 `nonebot-plugin-rauthman <https://pypi.org/project/nonebot-plugin-rauthman/>`_ 来源进行 deprecate 的处理。
|

 由于本模块的性质，未来即使提交更新也仅对本仓库进行。

 正在使用的 PyPI 发行版来源也应择日改为使用本 Git 来源。

| 基于 `NoneBot2 <https://github.com/nonebot/nonebot2>`_。

******************************************************************************
Highlights
******************************************************************************
* 为 Matcher 或 MatcherGroup 配置一条或多条 Rule 来实现功能的授权管理

.. code:: python

 # MatcherGroup
 from nonebot.plugin import MatcherGroup

 from nonebot_plugin_rauthman import isInService

 workers = MatcherGroup(
     type="message", rule=isInService("module_name", 10)
 )  # Rule 自动套用到 MatcherGroup 下所有 Matcher
 worker_1 = workers.on_regex(...)
 worker_2 = workers.on_regex(...)
 worker_3 = workers.on_regex(...)
 worker_4 = workers.on_regex(...)
 worker_5 = workers.on_regex(...)
 worker_6 = workers.on_regex(...)

 ...
.. code:: python

 # Matcher
 from nonebot.plugin import on_command

 from nonebot_plugin_rauthman import isInService

 worker = on_command(
     "test", rule=isInService("module_name_A", 10) & isInService("module_name_B", 10)
 )  # 同时满足多个 Rule 才可触发

 ...

* 授权策略可选 ``根据可用功能`` 或 ``根据服务级别``
* 参数可完全自定义

.. code:: python

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
     permission: Permission = SUPERUSER
     policy: int = getattr(config, "ram_policy") or 0
     cmd: str = getattr(config, "ram_cmd") or "ram"
     add: str = getattr(config, "ram_add") or "-a"
     rm: str = getattr(config, "ram_rm") or "-r"
     show: str = getattr(config, "ram_show") or "-s"
     available: str = getattr(config, "ram_available") or "-v"

******************************************************************************
开始使用
******************************************************************************
==============================================================================
对于 PyPI 发行版来源
==============================================================================
| 建议使用 poetry
|

* 通过 poetry 添加到 NoneBot2 项目的 ``pyproject.toml``

.. code:: cmd

 poetry add nonebot-plugin-rauthman

* 也可以通过 pip 从 `PyPI <https://pypi.org/project/nonebot-plugin-rauthman/>`_ 安装

.. code:: cmd

 pip install nonebot-plugin-rauthman

* 参照下文在 NoneBot2 项目的环境文件 ``.env.*`` 中添加配置项

==============================================================================
对于 Git 来源
==============================================================================
| 自己看着办吧。

******************************************************************************
配置项
******************************************************************************
| 以下配置项皆为可选，即使不添加也可以直接使用默认值

.. code-block:: python

 # .env.prod
 savedata = Yuni/savedata  # 保存路径，相对路径，此处为保存至运行目录下的 "Yuni/savedata/" 下，默认为 ""
 ram_policy = 0  # 授权策略 0 为根据可用功能 1 为根据服务级别，默认为 0
 ram_cmd = ram  # 指令名，或者叫触发词，默认为 ram
 ram_add = -a  # 启用功能（根据可用功能），默认为 -a
 ram_rm = -r  # 禁用功能（根据可用功能），默认为 -r
 ram_show = -s  # 展示群功能状态（根据可用功能），默认为 -s
 ram_available = -v  # 展示全局可用功能（根据可用功能），默认为 -v

| 为需要管理的 ``on_*`` 事件设置规则授权，示例意为将一个 ``on_command`` 事件划入一个名为 ``module_name`` 的功能，同时设置功能级别 ``1``

.. code:: python

  from nonebot.plugin import on_command
  from nonebot_plugin_rauthman import isInService

  command = on_command('cmd', rule=isInService('module_name', 1))

| 这样，群聊必须被启用了该功能，或功能级别高于 ``1`` 才会进入事件处理（取决于当前应用的授权管理应用策略）

******************************************************************************
小白案例
******************************************************************************
| 以 PyPI 发行版来源为例，基于以下配置文件和事件响应器

.. code:: python

 # .env.prod
 ram_cmd = 功能  # 指令名，默认为 ram
 ram_add = 开启  # 启用功能（根据可用功能），默认为 -a
 ram_rm = 关闭  # 禁用功能（根据可用功能），默认为 -r
 ram_show = 查询  # 展示群功能状态（根据可用功能），默认为 -s
 ram_available = 全局查询  # 展示全局可用功能（根据可用功能），默认为 -v

.. code:: python

 from nonebot.plugin import on_notice

 from nonebot_plugin_rauthman import isInService
 notice = on_notice(rule=to_me() & isInService('戳一戳', 1))

| 使用过程 `预览图 <BotTest1.jpg>`_

******************************************************************************
常见问题
******************************************************************************
* 这个插件可以做到什么？
   | RAM 可以实现对不同群，不同功能的控制

* 提示群聊未注册是怎么回事？
   | 本地 JSON 文件中不存在该群群号，则会提示为群聊未注册
   | 进行一次授权变更操作即可生成，如 ``ram 0``

* 谁可以开启/关闭功能？
   | ``SUPERUSERS`` 在 ``.env.*`` 中定义，参考 `配置 <https://v2.nonebot.dev/docs/tutorial/configuration#env-%E6%96%87%E4%BB%B6-1>`_

* 批量对群进行授权修改？
   | 私聊 Bot 直接发送 ``ram`` 并根据提示操作

* 我设置了 ``ram_policy = 1``，怎么设置群 Level？
   | 例如在 Bot 所在群聊中发送 ``ram 10``
   | 这样这个群的 Level 就被设定成 ``10`` 默认的 Level 为 ``0``

     授权修改操作与当前授权策略无关

* 如果我希望在一个群中，管理员和群主可以修改开关/设置群 Level 我该怎么办？
   | 对源代码第 ``104`` 行进行修改

.. code:: python

 permission: Permission = SUPERUSER  # 参考 NoneBot2 文档 - 进阶 - 权限控制

******************************************************************************
特别感谢
******************************************************************************
* `Mrs4s / go-cqhttp <https://github.com/Mrs4s/go-cqhttp>`_
* `nonebot / nonebot2 <https://github.com/nonebot/nonebot2>`_
* `Sichongzou <https://github.com/Sichongzou>`_ 对 `README.md <README.md>`_ ``小白案例`` 和 ``常见问题`` 的贡献

******************************************************************************
优化建议
******************************************************************************
| 如有优化建议请积极提交 Issues 或 Pull requests
