import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram.error import BadRequest
from telegram.ext import run_async, CommandHandler, Filters
from telegram.utils.helpers import mention_html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, User, CallbackQuery

from tg_bot import dispatcher, BAN_STICKER, LOGGER
from tg_bot.modules.disable import DisableAbleCommandHandler
from tg_bot.modules.helper_funcs.chat_status import bot_admin, user_admin, is_user_ban_protected, can_restrict, \
    is_user_admin, is_user_in_chat, is_bot_admin
from tg_bot.modules.helper_funcs.extraction import extract_user_and_text
from tg_bot.modules.helper_funcs.string_handling import extract_time
from tg_bot.modules.log_channel import loggable
from tg_bot.modules.helper_funcs.filters import CustomFilters

RBAN_ERRORS = {
    "İstifadəçi söhbətin idarəedicisidir",
    "Çat boşdur",
    "Söhbət üzvünü məhdudlaşdırmaq / məhdudlaşdırmamaq üçün kifayət qədər hüquq yoxdur",
    "User_not_participant",
    "Peer_id_invalid",
    "Qrup çatı deaktivdir",
    "Əsas qrupdan salmaq üçün bir istifadəçiyə dəvətçi olmaq lazımdır",
    "Chat_admin_required",
    "Yalnız əsas qrupun yaradıcısı qrup idarəçilərinə təpik ata bilər",
    "Channel_private",
    "Söhbətdə deyil"
}

RUNBAN_ERRORS = {
    "İstifadəçi söhbətin idarəedicisidir",
    "Çat boşdur",
    "Söhbət üzvünü məhdudlaşdırmaq / məhdudlaşdırmamaq üçün kifayət qədər hüquq yoxdur",
    "User_not_participant",
    "Peer_id_invalid",
    "Qrup çatı deaktivdir",
    "Əsas qrupdan salmaq üçün bir istifadəçiyə dəvətçi olmaq lazımdır",
    "Chat_admin_required",
    "Yalnız əsas qrupun yaradıcısı qrup idarəçilərinə təpik ata bilər",
    "Channel_private",
    "Söhbətdə deyil"
}



@run_async
@bot_admin
@can_restrict
@user_admin
@loggable
def ban(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("Deyəsən bir istifadəçiyə istinad etmirsiniz.")
        return ""

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "İstifadəçi tapılmadı":
            message.reply_text("Görünür bu istifadəçini tapa bilmirəm")
            return ""
        else:
            raise

    if is_user_ban_protected(chat, user_id, member):
        message.reply_text("Kaş ki adminləri qadağan edə biləydim ... :)")
        return ""

    if user_id == bot.id:
        message.reply_text("Mən özümü ban etməyəcəm, dəli olmusan?")
        return ""

    log = "<b>{}:</b>" \
          "\n#Ban olunmuşlar" \
          "\n<b>Admin:</b> {}" \
          "\n<b>İstifadəçi:</b> {}".format(html.escape(chat.title), mention_html(user.id, user.first_name),
                                     mention_html(member.user.id, member.user.first_name))
    if reason:
        log += "\n<b>Səbəb:</b> {}".format(reason)

    try:
        chat.kick_member(user_id)
        bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
        keyboard = []
        reply = "{} Banned!".format(mention_html(member.user.id, member.user.first_name))
        message.reply_text(reply, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        return log

    except BadRequest as excp:
        if excp.message == "Cavab mesajı tapılmadı":
            # Do not reply
            message.reply_text('Ban olundu!', quote=False)
            return log
        else:
            LOGGER.warning(update)
            LOGGER.exception("ERROR  %s Səbəbiylə %s (%s) istifadəçi ban olunmadı %s", user_id, chat.title, chat.id,
                             excp.message)
            message.reply_text("Lənət olsun, o istifadəçini ban edə bilmirəm.")

    return ""


@run_async
@bot_admin
@can_restrict
@user_admin
@loggable
def temp_ban(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("Deyəsən bir istifadəçiyə istinad etmirsiniz.")
        return ""

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "İstifadəçi tapılmadı":
            message.reply_text("Görünür bu istifadəçini tapa bilmirəm")
            return ""
        else:
            raise

    if is_user_ban_protected(chat, user_id, member):
        message.reply_text("Kaş ki adminləri qadağan edə biləydim ... :)")
        return ""

    if user_id == bot.id:
        message.reply_text("Mən özümü ban etməyəcəm, dəli olmusan?")
        return ""

    if not reason:
        message.reply_text("Bu istifadəçini qadağan edəcək bir vaxt təyin etməmisiniz!")
        return ""

    split_reason = reason.split(None, 1)

    time_val = split_reason[0].lower()
    if len(split_reason) > 1:
        reason = split_reason[1]
    else:
        reason = ""

    bantime = extract_time(message, time_val)

    if not bantime:
        return ""

    log = "<b>{}:</b>" \
          "\n#Ban olunmuşlar(vaxt)" \
          "\n<b>Admin:</b> {}" \
          "\n<b>istifadəçi:</b> {}" \
          "\n<b>Vaxt:</b> {}".format(html.escape(chat.title), mention_html(user.id, user.first_name),
                                     mention_html(member.user.id, member.user.first_name), time_val)
    if reason:
        log += "\n<b>Səbəb:</b> {}".format(reason)

    try:
        chat.kick_member(user_id, until_date=bantime)
        bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
        message.reply_text("Ban olundu! Bu vaxta qədər: {}.".format(time_val))
        return log

    except BadRequest as excp:
        if excp.message == "Cavab mesajı tapılmadı":
            # Do not reply
            message.reply_text("Ban olundu! Bu vaxta qədər: {}.".format(time_val), quote=False)
            return log
        else:
            LOGGER.warning(update)
            LOGGER.exception("ERROR %s Səbəbiylə %s (%s) ban olunmadı %s", user_id, chat.title, chat.id,
                             excp.message)
            message.reply_text("Lənət olsun, ban edə bilmirəm.")

    return ""


@run_async
@bot_admin
@can_restrict
@user_admin
@loggable
def kick(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        return ""

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "İstifadəçi tapılmadı":
            message.reply_text("Görünür bu istifadəçini tapa bilmirəm")
            return ""
        else:
            raise

    if is_user_ban_protected(chat, user_id):
        message.reply_text("Kaş ki adminləri qadağan edə biləydim ... :)")
        return ""

    if user_id == bot.id:
        message.reply_text("Bəli bunu etməyəcəyəm :)")
        return ""

    res = chat.unban_member(user_id)  # unban on current user = kick
    if res:
        bot.send_sticker(chat.id, BAN_STICKER)  # banhammer marie sticker
        message.reply_text("Qovuldu!")
        log = "<b>{}:</b>" \
              "\n#Qovuldu" \
              "\n<b>Admin:</b> {}" \
              "\n<b>İstifadəçi:</b> {}".format(html.escape(chat.title),
                                         mention_html(user.id, user.first_name),
                                         mention_html(member.user.id, member.user.first_name))
        if reason:
            log += "\n<b>Səbəb:</b> {}".format(reason)

        return log

    else:
        message.reply_text("Lənət olsun, ban edə bilmirəm!")

    return ""


@run_async
@bot_admin
@can_restrict
def kickme(bot: Bot, update: Update):
    user_id = update.effective_message.from_user.id
    if is_user_admin(update.effective_chat, user_id):
        update.effective_message.reply_text("Kaş edə biləydim, amma adminsən :)")
        return

    res = update.effective_chat.unban_member(user_id)  # unban on current user = kick
    if res:
        update.effective_message.reply_text("Problem yoxdur.")
    else:
        update.effective_message.reply_text("Hə? Bacarmıram :/")


@run_async
@bot_admin
@can_restrict
@user_admin
@loggable
def unban(bot: Bot, update: Update, args: List[str]) -> str:
    message = update.effective_message  # type: Optional[Message]
    user = update.effective_user  # type: Optional[User]
    chat = update.effective_chat  # type: Optional[Chat]

    user_id, reason = extract_user_and_text(message, args)

    if not user_id:
        return ""

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "İstifadəçi tapılmadı":
            message.reply_text("Görünür bu istifadəçini tapa bilmirəm")
            return ""
        else:
            raise

    if user_id == bot.id:
        message.reply_text("Burda olmasaydım özümü necə açardım ...? :)")
        return ""

    if is_user_in_chat(chat, user_id):
        message.reply_text("Niyə artıq söhbətdə olan birini ləğv etməyə çalışırsınız?")
        return ""

    chat.unban_member(user_id)
    message.reply_text("Yaxşı icazə verdim, artıq qoşula bilər.")

    log = "<b>{}:</b>" \
          "\n#Bandan çıxanlar" \
          "\n<b>Admin:</b> {}" \
          "\n<b>İstifadəçi:</b> {}".format(html.escape(chat.title),
                                     mention_html(user.id, user.first_name),
                                     mention_html(member.user.id, member.user.first_name))
    if reason:
        log += "\n<b>Səbəb:</b> {}".format(reason)

    return log


@run_async
@bot_admin
def rban(bot: Bot, update: Update, args: List[str]):
    message = update.effective_message

    if not args:
        message.reply_text("Görünür, söhbət / istifadəçi haqqında danışmırsınız.")
        return

    user_id, chat_id = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("Deyəsən bir istifadəçiyə istinad etmirsiniz.")
        return
    elif not chat_id:
        message.reply_text("Deyəsən bir çata istinad etmirsiniz.")
        return

    try:
        chat = bot.get_chat(chat_id.split()[0])
    except BadRequest as excp:
        if excp.message == "Çat boşdur":
            message.reply_text("Söhbət tapılmadı! Etibarlı bir söhbət identifikatoru daxil etdiyinizə əmin olun və bu söhbətin bir hissəsiyəm.")
            return
        else:
            raise

    if chat.type == 'private':
        message.reply_text("Bağışlayın, amma bu xüsusi söhbətdir!")
        return

    if not is_bot_admin(chat, bot.id) or not chat.get_member(bot.id).can_restrict_members:
        message.reply_text("Oradakı insanları məhdudlaşdıra bilmərəm! Admin olduğuma və istifadəçiləri qadağan edə biləcəyimə əmin olun.")
        return

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "İstifadəçi tapılmadı":
            message.reply_text("Görünür bu istifadəçini tapa bilmirəm")
            return
        else:
            raise

    if is_user_ban_protected(chat, user_id, member):
        message.reply_text("Kaş ki adminləri qadağan edə biləydim ... :)")
        return

    if user_id == bot.id:
        message.reply_text("Mən özüm ban etməyəcəm, dəli olmusan?")
        return

    try:
        chat.kick_member(user_id)
        message.reply_text("Ban olundu!")
    except BadRequest as excp:
        if excp.message == "Cavab mesajı tapılmadı!":
            # Do not reply
            message.reply_text('Ban olundu!', quote=False)
        elif excp.message in RBAN_ERRORS:
            message.reply_text(excp.message)
        else:
            LOGGER.warning(update)
            LOGGER.exception("ERROR %s Səbəbiylə %s (%s) bandan çıxarıla bilmirəm %s", user_id, chat.title, chat.id,
                             excp.message)
            message.reply_text("Lənət olsun, bandan çıxara bilmirəm!")

@run_async
@bot_admin
def runban(bot: Bot, update: Update, args: List[str]):
    message = update.effective_message

    if not args:
        message.reply_text("Görünür, söhbət / istifadəçi haqqında danışmırsınız.")
        return

    user_id, chat_id = extract_user_and_text(message, args)

    if not user_id:
        message.reply_text("Deyəsən bir istifadəçiyə istinad etmirsiniz.")
        return
    elif not chat_id:
        message.reply_text("Deyəsən bir çata istinad etmirsiniz.")
        return

    try:
        chat = bot.get_chat(chat_id.split()[0])
    except BadRequest as excp:
        if excp.message == "Çat boşdur":
            message.reply_text("Söhbət tapılmadı! Etibarlı bir söhbət identifikatoru daxil etdiyinizə əmin olun və bu sohbetin bir hissəsiyəm.")
            return
        else:
            raise

    if chat.type == 'private':
        message.reply_text("Bağışlayın, amma bu xüsusi söhbətdir!")
        return

    if not is_bot_admin(chat, bot.id) or not chat.get_member(bot.id).can_restrict_members:
        message.reply_text("Oradakı insanları məhdudlaşdıra bilmərəm! Admin olduğuma və istifadəçiləri ləğv edə biləcəyimə əmin olun.")
        return

    try:
        member = chat.get_member(user_id)
    except BadRequest as excp:
        if excp.message == "İstifadəçi tapılmadı!":
            message.reply_text("Görünür bu istifadəçini orada tapa bilmirəm")
            return
        else:
            raise
            
    if is_user_in_chat(chat, user_id):
        message.reply_text("Niyə onsuz da bu söhbətdə olan birini uzaqdan açmağa çalışırsınız?")
        return

    if user_id == bot.id:
        message.reply_text("Mən özüm ban etməyəcəyəm, mən orada adminəm!")
        return

    try:
        chat.unban_member(user_id)
        message.reply_text("Yaxşı icazə verdim, qrupa qoşula bilər.")
    except BadRequest as excp:
        if excp.message == "Cavab mesajı tapılmadı":
            # Do not reply
            message.reply_text('Bandan çıxarıldı!', quote=False)
        elif excp.message in RUNBAN_ERRORS:
            message.reply_text(excp.message)
        else:
            LOGGER.warning(update)
            LOGGER.exception("ERROR %s Səbəbiylə %s (%s) bandan çıxarıla bilmədi %s", user_id, chat.title, chat.id,
                             excp.message)
            message.reply_text("Lənət olsun, bandan çıxara bilmədim!")


__help__ = """
 - /kickme: əmri verən istifadəçini qovur

*Yalnız Admin:*
 - /ban <userhandle>: ban etmək. (mesajına cavab yazmaqla, tağ ilə (Məsələn: /ban @username)) 
 - /tban <userhandle>: vaxt ilə ban etmək (mesajına cavab yazmaqla, tağ ilə (Məsələn: /tban @username 1m/h/d)). m = dəqiqə, h = saat, d = gün.
 - /unban <userhandle>:bandan çıxarmaq. (mesajına cavab yazmaqla, tağ ilə (Məsələn: /unban @username))
 - /kick <userhandle>: qovmaq. (mesajına cavab yazmaqla, tağ ilə (Məsələn: /kick @username))
"""

__mod_name__ = "Bans"

BAN_HANDLER = CommandHandler("ban", ban, pass_args=True, filters=Filters.group)
TEMPBAN_HANDLER = CommandHandler(["tban", "tempban"], temp_ban, pass_args=True, filters=Filters.group)
KICK_HANDLER = CommandHandler("kick", kick, pass_args=True, filters=Filters.group)
UNBAN_HANDLER = CommandHandler("unban", unban, pass_args=True, filters=Filters.group)
KICKME_HANDLER = DisableAbleCommandHandler("kickme", kickme, filters=Filters.group)
RBAN_HANDLER = CommandHandler("rban", rban, pass_args=True, filters=CustomFilters.sudo_filter)
RUNBAN_HANDLER = CommandHandler("runban", runban, pass_args=True, filters=CustomFilters.sudo_filter)

dispatcher.add_handler(BAN_HANDLER)
dispatcher.add_handler(TEMPBAN_HANDLER)
dispatcher.add_handler(KICK_HANDLER)
dispatcher.add_handler(UNBAN_HANDLER)
dispatcher.add_handler(KICKME_HANDLER)
dispatcher.add_handler(RBAN_HANDLER)
dispatcher.add_handler(RUNBAN_HANDLER)
