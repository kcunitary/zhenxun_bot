from math import log
import imagehash
from nonebot import on_message
from nonebot.plugin import PluginMetadata
from nonebot_plugin_alconna import UniMsg
from nonebot_plugin_alconna.uniseg import Image
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_session import EventSession

from zhenxun.configs.config import Config
from zhenxun.configs.utils import PluginExtraData, RegisterConfig
from zhenxun.models.chat_history import ChatHistory
from zhenxun.models.pic_history import ChatPicHistory
from zhenxun.services.log import logger
from zhenxun.utils.enum import PluginType
from zhenxun.utils.http_utils import AsyncHttpx
from zhenxun.utils.image_utils import get_image

from urllib.parse import urlparse, parse_qs


__plugin_meta__ = PluginMetadata(
    name="消息存储",
    description="消息存储，被动存储群消息",
    usage="",
    extra=PluginExtraData(
        author="HibiKier",
        version="0.1",
        plugin_type=PluginType.HIDDEN,
        configs=[
            RegisterConfig(
                module="chat_history",
                key="FLAG",
                value=True,
                help="是否开启消息自从存储",
                default_value=True,
                type=bool,
            )
        ],
    ).dict(),
)


def rule(message: UniMsg) -> bool:
    return bool(Config.get_config("chat_history", "FLAG") and message)


chat_history = on_message(rule=rule, priority=1, block=False)


TEMP_LIST = []
TEMP_PIC_LIST = []


def get_url_hash(url):
    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        fileid = query_params.get("fileid", [None])[0]
        return fileid
    except Exception as e:
        logger.error(f"获取url hash错误", "chat_history", e=e)
        return None


@chat_history.handle()
async def _(message: UniMsg, session: EventSession):
    # group_id = session.id3 or session.id2
    group_id = session.id2
    # plain text handle
    TEMP_LIST.append(
        ChatHistory(
            user_id=session.id1,
            group_id=group_id,
            text=str(message),
            plain_text=message.extract_plain_text(),
            bot_id=session.bot_id,
            platform=session.platform,
        )
    )
    # pic handle

    if message.has(Image):
        msg_pics = message.get(Image)
        for pic in msg_pics:

            sub_type = pic.origin.data.get("subType", 0)
            if sub_type == 0:
                img = await get_image(pic.url)
                if img:
                    img_width, img_height = img.size if img else (0, 0)
                    img_hash = pic.origin.data.get("filename", "")
                    url_hash = get_url_hash(pic.url)
                    dhash = str(imagehash.dhash(img))
                    for i in range(4):
                        hash_segment = dhash[i * 4 : (i + 1) * 4]
                        record = ChatPicHistory(
                            user_id=session.id1,
                            group_id=group_id,
                            url=pic.url,
                            url_hash=url_hash,
                            img_hash_dhash_segment=hash_segment,
                            img_hash_dhash=dhash,
                            img_width=img_width,
                            img_height=img_height,
                            img_hash_md5=img_hash,
                            bot_id=session.bot_id,
                            platform=session.platform,
                            message_id=message.get_message_id(),
                        )
                        TEMP_PIC_LIST.append(record)


@scheduler.scheduled_job(
    "interval",
    minutes=1,
    #    minutes=1,
)
async def _():
    try:
        message_list = TEMP_LIST.copy()
        TEMP_LIST.clear()
        if message_list:
            await ChatHistory.bulk_create(message_list)

        message_list = TEMP_PIC_LIST.copy()
        TEMP_PIC_LIST.clear()
        if message_list:
            await ChatPicHistory.bulk_create(message_list)

        logger.debug(f"批量添加聊天记录 {len(message_list)} 条", "定时任务")
    except Exception as e:
        logger.error(f"定时批量添加聊天记录", "定时任务", e=e)


# @test.handle()
# async def _(event: MessageEvent):
#     print(await ChatHistory.get_user_msg(event.user_id, "private"))
#     print(await ChatHistory.get_user_msg_count(event.user_id, "private"))
#     print(await ChatHistory.get_user_msg(event.user_id, "group"))
#     print(await ChatHistory.get_user_msg_count(event.user_id, "group"))
#     print(await ChatHistory.get_group_msg(event.group_id))
#     print(await ChatHistory.get_group_msg_count(event.group_id))
