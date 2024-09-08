from asyncio import gather

import datetime
import enum
import random
from urllib.parse import parse_qs, urlparse

from cv2 import log
import imagehash
from nonebot import on_message
from nonebot.adapters import Event
from nonebot.plugin import PluginMetadata
from nonebot_plugin_alconna import Image as alcImg
from nonebot_plugin_alconna import UniMsg
from nonebot_plugin_session import EventSession
import pytz
from zhenxun.builtin_plugins.web_ui.base_model import User
from zhenxun.models.chat_history import ChatHistory
from zhenxun.models.pic_history import ChatPicHistory
from zhenxun.models.group_member_info import GroupInfoUser
from zhenxun.configs.config import BotConfig, Config
from zhenxun.configs.path_config import TEMP_PATH
from zhenxun.configs.utils import PluginExtraData, RegisterConfig, Task
from zhenxun.utils.common_utils import CommonUtils
from zhenxun.utils.enum import PluginType
from zhenxun.utils.image_utils import get_download_image_hash, get_image
from zhenxun.utils.message import MessageUtils
from zhenxun.utils.rules import ensure_group
from nonebot_plugin_alconna.uniseg import Image
from zhenxun.services.log import logger

__plugin_meta__ = PluginMetadata(
    name="火星警察",
    description="火星警察，在线出警！",
    usage="""
    usage：
        重复的图片和文字会被出警
        出警条件:
            大段的文字，大幅的图片是出警对象
            一分钟以内不出警
            重复次数超过5次视为表情不出警
    """.strip(),
    extra=PluginExtraData(
        author="kcunitary",
        version="0.1",
        menu_type="其他",
        plugin_type=PluginType.DEPENDANT,
        tasks=[Task(module="mars_police", name="火星警察")],
        configs=[
            RegisterConfig(
                key="IGNORE_LIMIT",
                value=10,
                help="重复多少次不出警",
                default_value=10,
                type=int,
            ),
            RegisterConfig(
                key="COOLDOWN",
                value=1,
                help="出警冷却时间",
                default_value=1,
                type=int,
            ),
            RegisterConfig(
                module="_task",
                key="DEFAULT_POLICE",
                value=True,
                help="被动 火星警察 进群默认开关状态",
                default_value=True,
                type=bool,
            ),
        ],
    ).dict(),
)

MIN_TEXT_LENGTH = 100

_matcher = on_message(rule=ensure_group, priority=999, block=False)
base_config = Config.get("mars_police")


async def _check_text(message_txt, gid):
    if len(message_txt) > MIN_TEXT_LENGTH:
        return await ChatHistory().get_message_by_text(gid, message_txt)
    else:
        return None


def formart_datetime(datetime):
    # 设置东八区（UTC+8）时区
    tz = pytz.timezone("Asia/Shanghai")

    # 将 UTC 时间转换为东八区时间
    local_time = datetime.replace(tzinfo=pytz.utc).astimezone(tz)

    # 格式化为字符串
    local_time_str = local_time.strftime("%Y-%m-%d %H:%M:%S")
    return datetime.strftime("%Y-%m-%d %H:%M:%S")


async def _check_and_get_message_info(records, gid, uid):
    match_records_message_count = len(set([r.message_id for r in records]))
    repeat_count = match_records_message_count
    if repeat_count > base_config.get("IGNORE_LIMIT", 10):
        logger.debug("Too many repeat messages, ignore")
        return None, None, None

    last_record = records[-1]

    past_time = datetime.datetime.now() - datetime.timedelta(  # type: ignore
        minutes=base_config.get("COOLDOWN", 1)
    )
    past_time = past_time.timestamp()
    last_time = last_record.create_time.timestamp()
    logger.debug(f"last_record.create_time: {last_time}, past_time: {past_time}")
    if last_time < past_time:
        logger.debug("In cooldown time, ignore")
        return None, None, None

    first_record = records[0]
    logger.debug(f"first_record.user_id: {first_record.user_id}, uid: {uid}")
    # if (first_record.user_id == uid) or (last_record.user_id == uid):
    #     return None, None, None

    first_uid = first_record.user_id
    logger.debug(f"first_uid: {first_uid}, gid: {gid}")

    first_user = await GroupInfoUser.get_or_none(user_id=first_uid, group_id=gid).only(
        "user_name"
    )
    first_uname = first_user.user_name if first_user else None
    logger.debug(f"first_uname: {first_uname}")
    first_time = first_record.create_time
    first_time_str = formart_datetime(first_time)

    return first_uname, first_time_str, repeat_count


async def text_handle(message, gid, uid):
    message_txt = message.extract_plain_text()
    match_records = await _check_text(message_txt, gid)
    if match_records:
        first_uname, first_time_str, repeat_count = await _check_and_get_message_info(
            match_records, gid, uid
        )
        if first_uname:
            message_to_send = f"火星消息警察,出警!\r\n这条消息最先由 {first_uname} 于 {first_time_str} 发送了! 已经发送过{repeat_count}次了！"
            await MessageUtils.build_message(message_to_send).finish(reply_to=True)


def split_string(s):
    return [s[i : i + 4] for i in range(0, len(s), 4)]


def hamming_distance_string(a, b):
    ai = int(a, 16)
    bi = int(b, 16)
    bins = bin(ai ^ bi)
    r = bins.count("1")
    return r


async def pic_handle(message, gid, uid):
    if message.has(Image):
        msg_pics = message.get(Image)
        messages_to_send = []
        for index, pic in enumerate(msg_pics):
            img_hash = pic.origin.data.get("filename", "")
            url_hash = get_url_hash(pic.url)
            match_records = await ChatPicHistory().get_images_by_full_hash(
                gid, url_hash, img_hash
            )
            if not match_records:
                img = await get_image(pic.url)
                if img:
                    pic_dhash = str(imagehash.dhash(img))
                    pic_dhash_segments = split_string(pic_dhash)
                    match_records = await ChatPicHistory().get_images_by_dhash_segments(
                        gid, pic_dhash_segments
                    )
                    match_dhashes = set(
                        [record.img_hash_dhash for record in match_records]
                    )
                    final_match_dhashes = []
                    for match_dhash in match_dhashes:
                        hamming_distance = hamming_distance_string(
                            pic_dhash, match_dhash
                        )
                        if hamming_distance < 4:
                            final_match_dhashes.append(match_dhash)
                    match_records = [
                        record
                        for record in match_records
                        if record.img_hash_dhash in final_match_dhashes
                    ]

            logger.debug(f"search img collections: {match_records}")
            if match_records:
                first_uname, first_time_str, repeat_count = (
                    await _check_and_get_message_info(match_records, gid, uid)
                )
                logger.debug(
                    f"repeated pic info:{first_uname} {first_time_str} {repeat_count}"
                )
                if first_uname:
                    message_to_send = f"第{index + 1}张图片最先由 {first_uname} 于 {first_time_str} 发送了! 已经发送过{repeat_count}次了！"
                    messages_to_send.append(message_to_send)
        logger.debug(f"messages_to_send: {messages_to_send}")
        if messages_to_send:
            pic_messages = "\r\n".join(messages_to_send)
            final_messages = f"火星消息警察,出警!\r\n{pic_messages}"
            await MessageUtils.build_message(final_messages).finish(reply_to=True)


def get_url_hash(url):
    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        fileid = query_params.get("fileid", [None])[0]
        return fileid
    except Exception as e:
        logger.error(f"获取url hash错误", "chat_history", e=e)
        return ""


@_matcher.handle()
async def _(message: UniMsg, event: Event, session: EventSession):
    group_id = session.id2 or ""
    user_id = session.id1 or ""
    tasks = [
        text_handle(message, group_id, user_id),
        pic_handle(message, group_id, user_id),
    ]
    await gather(*tasks)
