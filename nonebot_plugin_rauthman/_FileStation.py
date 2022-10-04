"""
Author       : Lancercmd
Date         : 2021-12-07 15:34:10
LastEditors  : Lancercmd
LastEditTime : 2022-08-29 16:11:57
Description  : None
GitHub       : https://github.com/Lancercmd
"""
from __future__ import annotations

from datetime import datetime
from os import makedirs, remove, rename
from pathlib import Path
from re import sub
from sys import getsizeof
from tempfile import mkdtemp
from typing import Any, Iterator

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.base import BaseScheduler
from loguru import logger
from ujson import dump as dumpJson
from ujson import dumps as dumpJsonS
from ujson import load as loadJson
from ujson import loads as loadJsonS


class FileStation:
    """
    ##    FileStation - 对象化的通用文件读写管理器
    -     构造一个 FileStation 对象，然后简单和安全地实现对文件的读写。
    """

    superfetch: dict = {}
    """
    ###   Superfetch - FileStation 对象的超级缓存
    -     FileStation 通过 Superfetch 实现了一个简单的缓存功能。
    -     当 FileStation 对象被创建时，它会自动在 Superfetch 中查找缓存，如果找到了，就会直接使用缓存，否则就会自动调用 load() 方法来加载文件。
    -     当 `use_superfetch` 属性设置为 True 时，FileStation 对象会自动将缓存写入 Superfetch 中。
    """
    save_queue: set = set()
    """
    ###   Superfetch - 文件写入任务等待队列
    -     当 `use_superfetch` 属性设置为 True 时，save() 方法会将文件写入任务添加到等待队列中，由 AsyncIOScheduler 按顺序执行。
    -     当 `use_superfetch` 属性设置为 False 时，save() 方法会立即将文件写入磁盘，不会添加到等待队列中。
    """
    scheduler: BaseScheduler = AsyncIOScheduler()
    """
    ###   Superfetch - 定时任务调度器
    -     用于触发计划的文件写入任务。
    -     默认使用 AsyncIOScheduler 调度器。
    -     可以在构造 FileStation 对象时传入自定义的调度器。
    """
    scheduler_default: AsyncIOScheduler = AsyncIOScheduler()
    """
    ###   Superfetch - 默认定时任务调度器
    -     这是 FileStation 对象的默认定时任务调度器。
    -     目前没什么用处，除非你知道你在做什么，否则不要修改或使用这个属性。
    """
    _tempdir: Path = Path(mkdtemp())
    """
    ###   FileStation - 临时文件目录
    -     这是 FileStation 提供的一个临时文件目录，用于存放临时文件。
    """

    async def save_job(*args) -> None:
        """
        ###   Superfetch - 定时任务
        -     定时任务，每隔一分钟检查一次等待队列，如果有文件需要写入，就将其写入磁盘。
        -     如果等待队列中的文件已经写入磁盘，就将其从等待队列中移除。
        -     如果一次检查完成后，等待队列中还有文件，将通过警告日志输出剩余任务的数量。
        """
        _len = len(FileStation.save_queue)
        if _len:
            logger.opt(colors=True).warning(
                f"<y>FileStation</y> is now saving {_len} files."
            )
            while _len:
                success = FileStation(
                    list(FileStation.save_queue)[0], unsafe=True
                ).do_save()
                if success:
                    # logger.success(f"Saved {list(FileStation.save_queue)[0]}")
                    FileStation.save_queue.remove(list(FileStation.save_queue)[0])
                    _len -= 1
                else:
                    logger.warning(f"Failed to save {list(FileStation.save_queue)[0]}")
                    try:
                        _success = FileStation(
                            list(FileStation.save_queue)[1]
                        ).do_save()
                        if _success:
                            FileStation.save_queue.remove(
                                list(FileStation.save_queue)[1]
                            )
                            _len -= 1
                    except IndexError:
                        break
        if FileStation.save_queue:
            logger.warning(f"{len(FileStation.save_queue)} files not saved")
        else:
            logger.success("All files saved")

    def __init__(
        self,
        filepath: str | Path = None,
        module_name: Optional[str] = None,
        *,
        json_string: Optional[str] = None,
        use_superfetch: bool = False,
        scheduler: BaseScheduler = None,
        unsafe: bool = False,
    ) -> None:
        """
        ###   FileStation - 构造函数
        -     构造一个 FileStation 对象，然后简单和安全地实现对文件的读写。
        -     FileStation 对象的构建，按照以下顺序进行：
            -     优先从 Superfetch 中查找缓存，如果找到了，就直接使用缓存。
            -     如果提供了 json_string 参数，就直接使用 JSON 字符串来初始化 FileStation 对象。
            -     如果提供了 filepath 参数，就从文件中加载数据来初始化 FileStation 对象。
            -     如果 filepath 参数为 None 或者文件不存在，就创建一个空的 FileStation 对象。
            -     虽然 filepath 可以为 None，但是可能会导致一些问题，比如多次构造了空的 FileStation 对象，这样会导致数据丢失，因此生产环境中不要这么做。
            -     如果 filepath 不存在于 Superfech，将 FileStation 对象写入 Superfetch 中。
            -     如果提供了 `module_name` 参数，就在初始化 FileStation 对象时，自动将对应模块的数据填充到 self.data 中。
            -     如果将 unsafe 参数设置为 True，将使用旧方法来提取数据，即把 self.data 创建为 `self._data` 的引用。
            -     否则，将所有数据即 `self._data` 变换填充到 self.data 中。
        -     另外，如果提供了 scheduler 参数，就使用该参数指定的调度器来触发文件写入任务。
        -     否则，使用默认的 AsyncIOScheduler 调度器。

        ###   参数
        -     filepath: str  文件路径，默认为 None
        -     `module_name`: str  模块名称，默认为 None
        -     json_string: str  JSON 字符串，默认为 None
        -     `use_superfetch`: bool  是否使用 Superfetch，默认为 False
        -     scheduler: BaseScheduler  自定义定时任务调度器，默认为 None
        """
        if isinstance(filepath, Path):
            self._filepath = filepath.resolve()
        elif filepath is None:
            self._filepath = None
        else:
            self._filepath = Path(filepath).resolve()
        self._module_name = module_name
        self._json_string = json_string
        self._use_superfetch = use_superfetch
        self._unsafe = unsafe
        self.load()
        if scheduler:
            logger.warning(
                f"Switching scheduler from {FileStation.scheduler.__class__.__name__} to {scheduler.__class__.__name__}"
            )
            FileStation.scheduler = scheduler

    def load(self) -> dict:
        """
        ###   FileStation - 加载数据
        -     优先从 Superfetch 中查找缓存，如果找到了，就直接使用缓存。
        -     如果提供了 json_string 参数，就直接使用 JSON 字符串来初始化 FileStation 对象。
        -     如果提供了 filepath 参数，就从文件中加载数据来初始化 FileStation 对象。
        -     如果 filepath 参数为 None 或者文件不存在，就创建一个空的 FileStation 对象。
        -     虽然 filepath 可以为 None，但是可能会导致一些问题，比如多次构造了空的 FileStation 对象，这样会导致数据丢失，因此生产环境中不要这么做。
        -     如果 filepath 不存在于 Superfech，将 FileStation 对象写入 Superfetch 中。
        -     如果提供了 `module_name` 参数，就在初始化 FileStation 对象时，自动将对应模块的数据填充到 self.data 中。
        -     如果将 unsafe 参数设置为 True，将使用旧方法来提取数据，即直接把 self.data 创建为 `self._data` 的引用，以满足兼容性或性能用途。
        -     否则，将所有数据即 `self._data` 变换填充到 self.data 中。
        -     最后返回 self.data
        """
        self._data = {}
        methods = [
            self._load_from_superfetch,
            self._load_from_json_string,
            self._load_from_json_file,
        ]
        for method in methods:
            method()
            if self._is_not_empty():
                break
        self._do_superfetch()
        self._extract_data()
        return self.data

    def _do_superfetch(self) -> None:
        """
        ###   FileStation - 写入 Superfetch
        -     如果 filepath 不存在于 Superfech，将 FileStation 对象写入 Superfetch 中。
        """
        if not self._filepath in FileStation.superfetch:
            FileStation.superfetch[self._filepath] = self._data

    def _extract_data(self) -> None:
        """
        ###   FileStation - 提取数据
        -     如果提供了 `module_name` 参数，就在初始化 FileStation 对象时，自动将对应模块的数据填充到 self.data 中。
        -     如果将 unsafe 参数设置为 True，将使用旧方法来提取数据，即直接把 self.data 创建为 `self._data` 的引用，以满足兼容性或性能用途。
        -     否则，将所有数据即 `self._data` 变换填充到 self.data 中。
        """
        if self._module_name:
            self.data = self._data.get(self._module_name, {})
        elif self._unsafe:
            self.data = self._data
        else:
            self.data = loadJsonS(dumpJsonS(self._data))

    def _load_from_superfetch(self) -> None:
        """
        ###   FileStation - 从 Superfetch 中加载数据
        -     优先从 Superfetch 中查找缓存，如果找到了，就直接使用缓存。
        """
        if self._filepath in FileStation.superfetch:
            self._data = FileStation.superfetch[self._filepath]
            self._use_superfetch = True

    def _load_from_json_string(self) -> None:
        """
        ###   FileStation - 从 JSON 字符串中加载数据
        -     如果提供了 json_string 参数，就直接使用 JSON 字符串来初始化 FileStation 对象。
        """
        if self._json_string:
            try:
                self._data = loadJsonS(self._json_string)
            except Exception as e:
                logger.warning(e)
                self._data = {}

    def _load_from_json_file(self) -> None:
        """
        ###   FileStation - 从 JSON 文件中加载数据
        -     如果提供了 filepath 参数，就从文件中加载数据来初始化 FileStation 对象。
        -     如果 filepath 参数为 None 或者文件不存在，就创建一个空的 FileStation 对象。
        """
        if self._filepath:
            try:
                with open(self._filepath, "r", encoding="utf-8") as f:
                    self._data = loadJson(f)
            except FileNotFoundError:
                logger.warning(f"File {self._filepath} not found")
                self._data = {}

    def save(self, *, snapshot: bool = False) -> bool:
        """
        ###   FileStation - 保存数据
        -     仅提供了 filepath 参数时可用。
        -     当 snapshot 参数为 True 时，如果原文件存在，则会先用时间戳来重命名原文件。
        -     当 `use_superfetch` 参数为 True 或 filepath 存在于 Superfetch 时，将文件写入任务添加到等待队列中，由 AsyncIOScheduler 按顺序执行。
        -     当 `use_superfetch` 属性设置为 False 时，立即将文件写入磁盘，不会添加到等待队列中。
        """
        if self._filepath:
            self.sort()
            if snapshot:
                if Path(self._filepath).exists():
                    now = datetime.now().strftime(r"%Y%m%d-%H%M%S-%f")[:-3]
                    rename(self._filepath, f"{str(self._filepath)[:-5]}-{now}.json")
            if self._use_superfetch or self._filepath in FileStation.superfetch:
                FileStation.superfetch[self._filepath] = self._data
                FileStation.save_queue.add(self._filepath)
                return True
            else:
                return self.do_save_safe()
        else:
            logger.warning("Filepath is None")
            return False

    @staticmethod
    def check_dir(dir: str | Path) -> None:
        """
        ###   FileStation - 检查目录
        -     当目录结构不完整时，创建目录结构。

        ###   参数
        -     dir: str | Path  不含文件名的目录路径
        """
        if isinstance(dir, Path):
            dir.mkdir(parents=True, exist_ok=True)
        elif not Path(dir).exists():
            makedirs(dir, exist_ok=True)

    def _check_dir(self) -> None:
        """
        ###   FileStation - 检查目录
        -     当目录结构不完整时，创建目录结构。
        """
        _path = Path(self._filepath).parent
        _path.mkdir(parents=True, exist_ok=True)

    def do_save(self) -> bool:
        """
        ###   FileStation - 保存数据
        -     将数据覆盖写入到文件中。
        """
        try:
            self._check_dir()
            with open(self._filepath, "w", encoding="utf-8") as f:
                dumpJson(self._data, f, ensure_ascii=False, indent=4)
                return True
        except Exception as e:
            logger.warning(
                e
            ) if self._filepath in FileStation.superfetch else logger.error(e)
            return False

    def do_save_safe(self) -> None:
        """
        ###   FileStation - 保存数据
        -     将数据覆盖写入到副本中，然后删除原文件，再将副本重命名为原文件名。
        """
        try:
            self._check_dir()
            with open(f"{self._filepath}_safe", "w", encoding="utf-8") as f:
                dumpJson(self._data, f, ensure_ascii=False, indent=4)
            try:
                remove(self._filepath)
            except FileNotFoundError:
                pass
            rename(f"{self._filepath}_safe", self._filepath)
            return True
        except Exception as e:
            logger.warning(
                e
            ) if self._filepath in FileStation.superfetch else logger.error(e)
            return False

    def sort(self, **kwargs) -> None:
        """
        ###   FileStation - 排序
        -     将 self._data 按照指定的字段排序。

        ###   参数
        -     key: 排序的字段。
        -     reverse: 是否倒序。
        """
        methods = [
            self._sort_2,
            self._sort_1,
        ]
        for method in methods:
            try:
                method(**kwargs)
            except AttributeError:
                pass
            except TypeError:
                pass

    def sort_1(self, **kwargs) -> None:
        """
        ###   FileStation - 排序
        -     将 self.data 的一级字典按照指定的字段排序。

        ###   参数
        -     key: 排序的字段。
        -     reverse: 是否倒序。
        """
        self.data = {k: v for k, v in sorted(self.data.items(), **kwargs)}

    def _sort_1(self, **kwargs) -> None:
        """
        ###   FileStation - 排序
        -     将 self._data 的一级字典按照指定的字段排序。

        ###   参数
        -     key: 排序的字段。
        -     reverse: 是否倒序。
        """
        self.data = {k: v for k, v in sorted(self._data.items(), **kwargs)}

    def sort_2(self, **kwargs) -> None:
        """
        ###   FileStation - 排序
        -     将 self.data 的二级字典按照指定的字段排序。

        ###   参数
        -     key: 排序的字段。
        -     reverse: 是否倒序。
        """
        for k, v in self.data.items():
            self.data[k] = {k2: v2 for k2, v2 in sorted(v.items(), **kwargs)}

    def _sort_2(self, **kwargs) -> None:
        """
        ###   FileStation - 排序
        -     将 self._data 的二级字典按照指定的字段排序。

        ###   参数
        -     key: 排序的字段。
        -     reverse: 是否倒序。
        """
        for k, v in self._data.items():
            self._data[k] = {k2: v2 for k2, v2 in sorted(v.items(), **kwargs)}

    def sort_3(self, **kwargs) -> None:
        """
        ###   FileStation - 排序
        -     将 self.data 的三级字典按照指定的字段排序。

        ###   参数
        -     key: 排序的字段。
        -     reverse: 是否倒序。
        """
        for k, v in self.data.items():
            for k2, v2 in v.items():
                self.data[k][k2] = {k3: v3 for k3, v3 in sorted(v2.items(), **kwargs)}

    def _sort_3(self, **kwargs) -> None:
        """
        ###   FileStation - 排序
        -     将 self._data 的三级字典按照指定的字段排序。

        ###   参数
        -     key: 排序的字段。
        -     reverse: 是否倒序。
        """
        for k, v in self._data.items():
            for k2, v2 in v.items():
                self._data[k][k2] = {k3: v3 for k3, v3 in sorted(v2.items(), **kwargs)}

    def insert(self, key: str, value: Any) -> bool:
        """
        ###   FileStation - 插入数据
        -     将数据插入到 self.data 中，并返回 True。
        -     如果 key 已经存在，则输出警告日志，并返回 False。

        ###   参数
        -     key: 插入的字段。
        -     value: 插入的值。
        """
        if key not in self.data:
            self.data[key] = value
            return True
        else:
            logger.warning(f"'{key}' already exists")
            return False

    def _insert(self, key: str, value: Any) -> bool:
        """
        ###   FileStation - 插入数据
        -     将数据插入到 self._data 中，并返回 True。
        -     如果 key 已经存在，则输出警告日志，并返回 False。

        ###   参数
        -     key: 插入的字段。
        -     value: 插入的值。
        """
        if key not in self._data:
            self._data[key] = value
            return True
        else:
            logger.warning(f"'{key}' already exists")
            return False

    def update(self, key: str, value: Any) -> None:
        """
        ###   FileStation - 更新数据
        -     将数据更新到 self.data 中。

        ###   参数
        -     key: 更新的字段。
        -     value: 更新的值。
        """
        self.data[key] = value

    def _update(self, key: str, value: Any) -> None:
        """
        ###   FileStation - 更新数据
        -     将数据更新到 self._data 中。

        ###   参数
        -     key: 更新的字段。
        -     value: 更新的值。
        """
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """
        ###   FileStation - 获取数据
        -     获取 self.data 中的数据。

        ###   参数
        -     key: 获取的字段。
        -     default: 如果 key 不存在，则返回 default，默认为 None。
        """
        return self.data.get(key, default)

    def _get(self, key: str, default: Any = None) -> Any:
        """
        ###   FileStation - 获取数据
        -     获取 self._data 中的数据。

        ###   参数
        -     key: 获取的字段。
        -     default: 如果 key 不存在，则返回 default，默认为 None。
        """
        return self._data.get(key, default)

    def keys(self) -> Iterator[str]:
        """
        ###   FileStation - 获取所有字段
        -     获取 self.data 中所有字段。
        """
        return self.data.keys()

    def _keys(self) -> Iterator[str]:
        """
        ###   FileStation - 获取所有字段
        -     获取 self._data 中所有字段。
        """
        return self._data.keys()

    def values(self) -> Iterator[Any]:
        """
        ###   FileStation - 获取所有值
        -     获取 self.data 中所有值。
        """
        return self.data.values()

    def _values(self) -> Iterator[Any]:
        """
        ###   FileStation - 获取所有值
        -     获取 self._data 中所有值。
        """
        return self._data.values()

    def hash(self) -> int:
        """
        ###   FileStation - 获取哈希值
        -     获取 self.data 中所有值的哈希值。
        """
        return hash(f"{self.data}")

    def _hash(self) -> int:
        """
        ###   FileStation - 获取哈希值
        -     获取 self._data 中所有值的哈希值。
        """
        return hash(f"{self._data}")

    def len(self) -> int:
        """
        ###   FileStation - 获取长度
        -     获取 self.data 的字段数量。
        """
        return len(self.data)

    def _len(self) -> int:
        """
        ###   FileStation - 获取长度
        -     获取 self._data 的字段数量。
        """
        return len(self._data)

    def memory(self) -> int:
        """
        ###   FileStation - 获取内存占用
        -     获取 self.data 的内存占用。
        """
        return getsizeof(self.data)

    def _memory(self) -> int:
        """
        ###   FileStation - 获取内存占用
        -     获取 self._data 的内存占用。
        """
        return getsizeof(self._data)

    def reload(self, *, full: bool = False) -> None:
        """
        ###   FileStation - 重新加载数据
        -     重新加载 self.data 中的数据。
        ###   参数
        -     full: bool  是否重新加载所有数据，默认为 False。
        """
        if full:
            self.load()
        else:
            self._extract_data()

    def is_empty(self) -> bool:
        """
        ###   FileStation - 是否为空
        -     判断 self.data 是否为空，返回 True 或 False。
        """
        return self.len() == 0

    def _is_empty(self) -> bool:
        """
        ###   FileStation - 是否为空
        -     判断 self._data 是否为空，返回 True 或 False。
        """
        return self._len() == 0

    def is_not_empty(self) -> bool:
        """
        ###   FileStation - 是否不为空
        -     判断 self.data 是否不为空，返回 True 或 False。
        """
        return self.len() != 0

    def _is_not_empty(self) -> bool:
        """
        ###   FileStation - 是否不为空
        -     判断 self._data 是否不为空，返回 True 或 False。
        """
        return self._len() != 0

    def bool(self) -> bool:
        """
        ###   FileStation - 是否为空
        -     判断 self.data 是否为空，返回 True 或 False。
        """
        return self.len() != 0

    def _bool(self) -> bool:
        """
        ###   FileStation - 是否为空
        -     判断 self._data 是否为空，返回 True 或 False。
        """
        return self._len() != 0

    @staticmethod
    def start() -> None:
        """
        ###   FileStation - 启动 APScheduler
        -     启动 APScheduler。
        """
        FileStation.scheduler.start()

    @staticmethod
    def shutdown() -> None:
        """
        ###   FileStation - 停止 APScheduler
        -     停止 APScheduler。
        """
        FileStation.scheduler.shutdown()

    @staticmethod
    def stop() -> None:
        """
        ###   FileStation - 停止 APScheduler
        -     停止 APScheduler。
        """
        FileStation.scheduler.shutdown()

    @staticmethod
    def gettempdir(name: str = None) -> Path:
        """
        ###   FileStation - 获取临时目录
        -     获取临时目录。
        -     当提供 name 参数时，在临时目录下创建 name 目录并返回该目录，否则返回主目录。

        ###   参数
        -     name: str  子目录名称，默认为 None，即获取主目录。
        """
        _path = FileStation._tempdir
        if name:
            name = sub(r"[\\\/\:\*\?\"\<\>\|]", "", name)
        if name:
            _path = _path / name
        _path.mkdir(parents=True, exist_ok=True)
        return _path


if __name__ == "__main__":
    """
    ###   FileStation - 测试
    """
    from typing import Optional

    test_data = {"a": 1, "b": 2, "c": 3}
    test_data_2 = {"a": 1, "b": 2, "c": 3, "d": 4}
    test_data_3 = {"a": 10, "b": 2, "c": 3, "d": 4}
    test_filepath = "./test.json"

    def test_init() -> Optional[AssertionError]:
        """
        ###   FileStation - 测试初始化
        """
        fs = FileStation(test_filepath)
        assert fs._data == {}, fs._data
        logger.success(f"Memory usage: {fs.memory()} bytes")

    def test_save() -> Optional[AssertionError]:
        """
        ###   FileStation - 测试保存数据
        """
        fs = FileStation(test_filepath)
        fs._data = test_data
        assert fs.save() is True, fs._data
        logger.success(f"Memory usage: {fs.memory()} bytes")

    def test_load_from_json_string() -> Optional[AssertionError]:
        """
        ###   FileStation - 测试从 JSON 字符串加载数据
        """
        fs = FileStation(json_string=dumpJsonS(test_data))
        assert fs._data == test_data, fs._data
        logger.success(f"Memory usage: {fs.memory()} bytes")

    def test_load_from_json_file() -> Optional[AssertionError]:
        """
        ###   FileStation - 测试从 JSON 文件加载数据
        """
        fs = FileStation(test_filepath)
        assert fs._data == test_data, fs._data
        logger.success(f"Memory usage: {fs.memory()} bytes")

    def test_get() -> Optional[AssertionError]:
        """
        ###   FileStation - 测试获取数据
        """
        fs = FileStation(test_filepath)
        assert fs.get("a") == 1, fs.get("a")
        assert fs._data.get("a") == 1, fs._data.get("a")
        logger.success(f"Memory usage: {fs.memory()} bytes")

    def test_insert() -> Optional[AssertionError]:
        """
        ###   FileStation - 测试插入数据
        """
        fs = FileStation(test_filepath)
        assert fs.insert("d", 4), fs.insert("d", 4)
        assert fs.save() is True, fs._data
        assert fs._data == test_data_2, fs._data
        logger.success(f"Memory usage: {fs.memory()} bytes")

    def test_update() -> Optional[AssertionError]:
        """
        ###   FileStation - 测试更新数据
        """
        fs = FileStation(test_filepath)
        fs.update("a", 10)
        assert fs.save() is True, fs._data
        assert fs._data == test_data_3, fs._data
        logger.success(f"Memory usage: {fs.memory()} bytes")

    def test_keys() -> Optional[AssertionError]:
        """
        ###   FileStation - 测试获取所有键
        """
        fs = FileStation(test_filepath)
        assert fs.keys() == dict.keys(test_data_3), (fs.keys(), dict.keys(test_data_3))
        logger.success(f"Memory usage: {fs.memory()} bytes")

    def test_values() -> Optional[AssertionError]:
        """
        ###   FileStation - 测试获取所有值
        """
        fs = FileStation(test_filepath)
        assert tuple(fs.values()) == tuple(dict.values(test_data_3)), (
            tuple(fs.values()),
            tuple(dict.values(test_data_3)),
        )
        logger.success(f"Memory usage: {fs.memory()} bytes")

    def test_hash() -> Optional[AssertionError]:
        """
        ###   FileStation - 测试获取哈希值
        """
        fs = FileStation(test_filepath)
        assert fs.hash() == hash(f"{test_data_3}"), (fs.hash(), hash(f"{test_data_3}"))
        logger.success(f"Memory usage: {fs.memory()} bytes")

    def test_len() -> Optional[AssertionError]:
        """
        ###   FileStation - 测试获取长度
        """
        fs = FileStation(test_filepath)
        assert fs.len() == 4, fs.len()
        logger.success(f"Memory usage: {fs.memory()} bytes")

    def test_is_empty() -> Optional[AssertionError]:
        """
        ###   FileStation - 测试判断是否为空
        """
        fs = FileStation(test_filepath)
        assert fs.is_empty() is False, fs.is_empty()
        logger.success(f"Memory usage: {fs.memory()} bytes")

    def test_is_not_empty() -> Optional[AssertionError]:
        """
        ###   FileStation - 测试判断是否不为空
        """
        fs = FileStation(test_filepath)
        assert fs.is_not_empty() is True, fs.is_not_empty()
        logger.success(f"Memory usage: {fs.memory()} bytes")

    def test_bool() -> Optional[AssertionError]:
        """
        ###   FileStation - 测试判断是否为真
        """
        fs = FileStation(test_filepath)
        assert fs.bool() is True, fs.bool()
        logger.success(f"Memory usage: {fs.memory()} bytes")

    def vacuum() -> None:
        """
        ###   FileStation - 测试垃圾回收
        """
        try:
            remove(test_filepath)
        except FileNotFoundError:
            pass

    def test_all() -> Optional[AssertionError]:
        """
        ###   FileStation - 测试所有测试用例
        """
        vacuum()
        test_init()
        test_save()
        test_load_from_json_string()
        test_load_from_json_file()
        test_get()
        test_insert()
        test_update()
        test_keys()
        test_values()
        test_hash()
        test_len()
        test_is_empty()
        test_is_not_empty()
        test_bool()
        vacuum()
        logger.success("All test passed")

    test_all()
else:
    from sys import path as sys_path

    from nonebot import get_driver, require
    from nonebot.adapters import Bot

    FileStation.scheduler = require("nonebot_plugin_apscheduler").scheduler
    FileStation.scheduler.add_job(
        FileStation.save_job,
        "interval",
        minutes=5,
        misfire_grace_time=300,
        id="FileStation.save_job",
    )

    driver = get_driver()

    @driver.on_shutdown
    async def clear_queue() -> None:
        FileStation.shutdown()
        _len = len(FileStation.save_queue)
        if _len:
            logger.opt(colors=True).warning(
                f"<y>FileStation.save_queue</y> is not empty, waiting for {_len} files to be saved"
            )
            while _len:
                success = FileStation(
                    list(FileStation.save_queue)[0], unsafe=True
                ).do_save()
                if success:
                    # logger.success(f"Saved {list(FileStation.save_queue)[0]}")
                    FileStation.save_queue.remove(list(FileStation.save_queue)[0])
                    _len -= 1
                else:
                    logger.warning(f"Failed to save {list(FileStation.save_queue)[0]}")
                    try:
                        _success = FileStation(
                            list(FileStation.save_queue)[1]
                        ).do_save()
                        if _success:
                            FileStation.save_queue.remove(
                                list(FileStation.save_queue)[1]
                            )
                            _len -= 1
                    except IndexError:
                        break
            if FileStation.save_queue:
                logger.warning(f"{len(FileStation.save_queue)} files not saved")
            else:
                logger.success("All files saved")

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
        savedata = getattr(driver.config, "savedata", "")
        _path = Path(sys_path[0]) / savedata
        if _bot:
            _path = _path / _bot.type
        elif _type:
            _path = _path / _type
        if id:
            if flag == 0:
                _path = _path / "private" / f"{id}.json"
            elif flag == 1:
                _path = _path / "group" / f"{id}.json"
            else:
                raise ValueError("UnknownFlag")
        return str(_path.resolve())
