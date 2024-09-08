from datetime import datetime, timedelta
from typing import Literal, Tuple

import pytz
from tortoise import fields
from tortoise.functions import Count
from typing_extensions import Self

from zhenxun.services.db_context import Model
from tortoise.models import Q


class ChatPicHistory(Model):

    id = fields.IntField(pk=True, generated=True, auto_increment=True)
    """自增id"""
    user_id = fields.CharField(255)
    """用户id"""
    group_id = fields.CharField(255, null=True, index=True)

    """群聊id"""
    url = fields.CharField(5000)
    """图片URL"""

    url_hash = fields.CharField(255, index=True)
    """URL哈希值"""

    img_width = fields.IntField()
    """图片宽度"""

    img_height = fields.IntField()
    """图片高度"""

    img_hash_md5 = fields.CharField(255, index=True)
    """图片MD5哈希值"""
    img_hash_dhash_segment = fields.CharField(255, index=True)
    """图片片断哈希值"""
    img_hash_dhash = fields.CharField(255, index=True)
    """图片DHASH哈希值"""

    create_time = fields.DatetimeField(auto_now_add=True)
    """创建时间"""
    bot_id = fields.CharField(255, null=True)
    """bot记录id"""
    platform = fields.CharField(255, null=True)
    """平台"""
    message_id = fields.CharField(255, null=True)
    """消息ID"""

    class Meta:
        table = "chat_pic_history"
        table_description = "聊天图片记录数据表"

    @classmethod
    async def get_images_by_full_hash(cls, gid: str, url_hash_v: str, img_hash_v: str):
        """根据用户ID获取图片信息

        参数:
            url_hash_v: URL哈希值
            img_hash_v: 图片MD5哈希值
        """

        mathed_records = await cls.filter(
            Q(group_id=gid) & (Q(url_hash=url_hash_v) | Q(img_hash_md5=img_hash_v))
        ).all()
        return mathed_records

    @classmethod
    async def get_images_by_dhash_segments(cls, gid: str, hashes: list[str]):
        """根据图片dhash片断查找记录

        参数:
            url_hash_v: URL哈希值
            img_hash_v: 图片MD5哈希值
        """

        mathed_records = await cls.filter(
            group_id=gid, img_hash_dhash_segment__in=hashes
        ).all()
        return mathed_records
