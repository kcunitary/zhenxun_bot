from datetime import datetime, timedelta
from typing import Literal, Tuple

from tortoise import fields
from tortoise.functions import Count
from typing_extensions import Self

from zhenxun.services.db_context import Model


class ChatPicHistory(Model):

    id = fields.IntField(pk=True, generated=True, auto_increment=True)
    """自增id"""
    user_id = fields.CharField(255)
    """用户id"""
    group_id = fields.CharField(255, null=True)

    """群聊id"""
    url = fields.CharField(5000)
    """图片URL"""

    url_hash = fields.CharField(255, index=True)
    """URL哈希值"""

    img_width = fields.IntField()
    """图片宽度"""

    img_height = fields.IntField()
    """图片高度"""

    img_hash = fields.CharField(255, index=True)
    """图片哈希值"""

    create_time = fields.DatetimeField(auto_now_add=True)
    """创建时间"""
    bot_id = fields.CharField(255, null=True)
    """bot记录id"""
    platform = fields.CharField(255, null=True)
    """平台"""

    class Meta:
        table = "chat_pic_history"
        table_description = "聊天图片记录数据表"

    @classmethod
    async def get_images_by_user(cls, user_id: int, limit: int = 10):
        """根据用户ID获取图片信息

        参数:
            user_id: 用户ID
            limit: 获取数量
        """
        return await cls.filter(user_id=user_id).limit(limit).all()

    @classmethod
    async def get_images_by_group(cls, group_id: int, limit: int = 10):
        """根据群聊ID获取图片信息

        参数:
            group_id: 群聊ID
            limit: 获取数量
        """
        return await cls.filter(group_id=group_id).limit(limit).all()

    @classmethod
    async def get_image_by_message(cls, message_id: int):
        """根据消息ID获取图片信息

        参数:
            message_id: 消息ID
        """
        return await cls.filter(message_id=message_id).first()
