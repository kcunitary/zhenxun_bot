import platform
from pathlib import Path
from dataclasses import dataclass

import psutil
import cpuinfo
import nonebot
from pydantic import BaseModel
from nonebot.utils import run_sync
from httpx import NetworkError, ConnectTimeout

from zhenxun.services.log import logger
from zhenxun.configs.config import BotConfig
from zhenxun.utils.http_utils import AsyncHttpx

BAIDU_URL = "https://www.baidu.com/"
GOOGLE_URL = "https://www.google.com/"

VERSION_FILE = Path() / "__version__"


@dataclass
class CPUInfo:
    core: int
    """CPU 物理核心数"""
    usage: float
    """CPU 占用百分比，取值范围(0,100]"""
    freq: float
    """CPU 的时钟速度（单位：GHz）"""

    @classmethod
    def get_cpu_info(cls):
        cpu_core = psutil.cpu_count(logical=False)
        cpu_usage = psutil.cpu_percent(interval=1)
        cpu_freq = round(psutil.cpu_freq().current / 1000, 2)

        return CPUInfo(core=cpu_core, usage=cpu_usage, freq=cpu_freq)


@dataclass
class RAMInfo:
    """RAM 信息（单位：GB）"""

    total: float
    """RAM 总量"""
    usage: float
    """当前 RAM 占用量/GB"""

    @classmethod
    def get_ram_info(cls):
        ram_total = round(psutil.virtual_memory().total / (1024**3), 2)
        ram_usage = round(psutil.virtual_memory().used / (1024**3), 2)

        return RAMInfo(total=ram_total, usage=ram_usage)


@dataclass
class SwapMemory:
    """Swap 信息（单位：GB）"""

    total: float
    """Swap 总量"""
    usage: float
    """当前 Swap 占用量/GB"""

    @classmethod
    def get_swap_info(cls):
        swap_total = round(psutil.swap_memory().total / (1024**3), 2)
        swap_usage = round(psutil.swap_memory().used / (1024**3), 2)

        return SwapMemory(total=swap_total, usage=swap_usage)


@dataclass
class DiskInfo:
    """硬盘信息"""

    total: float
    """硬盘总量"""
    usage: float
    """当前硬盘占用量/GB"""

    @classmethod
    def get_disk_info(cls):
        disk_total = round(psutil.disk_usage("/").total / (1024**3), 2)
        disk_usage = round(psutil.disk_usage("/").used / (1024**3), 2)

        return DiskInfo(total=disk_total, usage=disk_usage)


class SystemInfo(BaseModel):
    """系统信息"""

    cpu: CPUInfo
    """CPU信息"""
    ram: RAMInfo
    """RAM信息"""
    swap: SwapMemory
    """SWAP信息"""
    disk: DiskInfo
    """DISK信息"""

    def get_system_info(self):
        return {
            "cpu_info": f"{self.cpu.usage}% - {self.cpu.freq}Ghz [{self.cpu.core} core]",
            "cpu_process": psutil.cpu_percent(),
            "ram_info": f"{self.ram.usage} / {self.ram.total} GB",
            "ram_process": self.ram.usage / self.ram.total * 100,
            "swap_info": f"{self.swap.usage} / {self.swap.total} GB",
            "swap_process": self.swap.usage / self.swap.total * 100,
            "disk_info": f"{self.disk.usage} / {self.disk.total} GB",
            "disk_process": self.disk.usage / self.disk.total * 100,
        }


@run_sync
def __build_status() -> dict:
    """获取 `CPU` `RAM` `SWAP` `DISK` 信息"""
    cpu = CPUInfo.get_cpu_info()
    ram = RAMInfo.get_ram_info()
    swap = SwapMemory.get_swap_info()
    disk = DiskInfo.get_disk_info()

    return SystemInfo(cpu=cpu, ram=ram, swap=swap, disk=disk).get_system_info()


async def __get_network_info():
    """网络请求"""
    baidu, google = True, True
    try:
        await AsyncHttpx.get(BAIDU_URL, timeout=5)
    except Exception as e:
        logger.warning("自检：百度无法访问...", e=e)
        baidu = False
    try:
        await AsyncHttpx.get(GOOGLE_URL, timeout=5)
    except Exception as e:
        logger.warning("自检：谷歌无法访问...", e=e)
        google = False
    return baidu, google


def __get_version() -> str | None:
    """获取版本信息"""
    with open(VERSION_FILE, encoding="utf-8") as f:
        if text := f.read():
            text.split(":")[-1]
        return None


async def get_status_info() -> dict:
    """获取信息"""
    data = await __build_status()
    baidu, google = await __get_network_info()
    data["baidu"] = "#8CC265" if baidu else "red"
    data["google"] = "#8CC265" if google else "red"
    system = platform.uname()
    data["system"] = f"{system.system} {system.release}"
    data["version"] = __get_version()
    data["brand_raw"] = cpuinfo.get_cpu_info()["brand_raw"]
    data["plugin_count"] = len(nonebot.get_loaded_plugins())
    data["nickname"] = BotConfig.self_nickname
    return data