import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User
from telegram import ParseMode, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import MessageHandler, Filters, CommandHandler, run_async
from telegram.utils.helpers import mention_markdown, mention_html, escape_markdown

import tg_bot.modules.sql.welcome_sql as sql
from tg_bot import dispatcher, OWNER_ID, LOGGER
from tg_bot.modules.helper_funcs.chat_status import user_admin, can_delete
from tg_bot.modules.helper_funcs.misc import build_keyboard, revert_buttons
from tg_bot.modules.helper_funcs.msg_types import get_welcome_type
from tg_bot.modules.helper_funcs.string_handling import markdown_parser, \
    escape_invalid_curly_brackets
from tg_bot.modules.log_channel import loggable

VALID_WELCOME_FORMATTERS = ['first', 'last', 'fullname', 'username', 'id', 'count', 'chatname', 'mention']

ENUM_FUNC_MAP = {
    sql.Types.TEXT.value: dispatcher.bot.send_message,
    sql.Types.BUTTON_TEXT.value: dispatcher.bot.send_message,
    sql.Types.STICKER.value: dispatcher.bot.send_sticker,
    sql.Types.DOCUMENT.value: dispatcher.bot.send_document,
    sql.Types.PHOTO.value: dispatcher.bot.send_photo,
    sql.Types.AUDIO.value: dispatcher.bot.send_audio,
    sql.Types.VOICE.value: dispatcher.bot.send_voice,
    sql.Types.VIDEO.value: dispatcher.bot.send_video
}


# do not async
def send(update, message, keyboard, backup_message):
    try:
        msg = update.effective_message.reply_text(message, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    except IndexError:
        msg = update.effective_message.reply_text(markdown_parser(backup_message +
                                                                  "\nQeyd: Cari mesaj "
                                                                  "qeyd işarələri səbəbindən etibarsızdır. ola bilər"
                                                                  "istifadəçi adı səbəbiylə."),
                                                  parse_mode=ParseMode.MARKDOWN)
    except KeyError:
        msg = update.effective_message.reply_text(markdown_parser(backup_message +
                                                                  "\nQeyd: cari mesaj "
                                                                   "bəzi yerlər səhv olduğu üçün etibarsızdır"
                                                                   "buruq mötərizələr. Xahiş edirəm yeniləyin"),
                                                  parse_mode=ParseMode.MARKDOWN)
    except BadRequest as excp:
        if excp.message == "Button_url_invalid":
            msg = update.effective_message.reply_text(markdown_parser(backup_message +
                                                                      "\nQeyd: cari mesajın səhv URL'si var "
                                                                       "düymələrindən birində. Xahiş edirəm yeniləyin."),
                                                      parse_mode=ParseMode.MARKDOWN)
        elif excp.message == "Unsupported url protocol":
            msg = update.effective_message.reply_text(markdown_parser(backup_message +
                                                                      "\nQeyd: cari mesajın düymələri var "
                                                                       "tərəfindən dəstəklənməyən url protokollarından istifadə edin"
                                                                       "telegram. Zəhmət olmasa yeniləyin."),
                                                      parse_mode=ParseMode.MARKDOWN)
        elif excp.message == "Wrong url host":
            msg = update.effective_message.reply_text(markdown_parser(backup_message +
                                                                      "\nQeyd: cari mesajda səhv URL var. "
                                                                       "Xahiş edirəm yeniləyin."),
                                                      parse_mode=ParseMode.MARKDOWN)
            LOGGER.warning(message)
            LOGGER.warning(keyboard)
            LOGGER.exception("Təhlil edilə bilmədi! etibarsız url host səhvləri var")
        else:
            msg = update.effective_message.reply_text(markdown_parser(backup_message +
                                                                      "\nQeyd: Xüsusi mesaj göndərilərkən bir səhv meydana gəldi. Zəhmət olmasa yeniləyin."),
                                                      parse_mode=ParseMode.MARKDOWN)
            LOGGER.exception()

    return msg


@run_async
@user_admin
@loggable
def del_joined(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]

    if not args:
        del_pref = sql.get_del_pref(chat.id)
        if del_pref:
            update.effective_message.reply_text("Sohbet mesajlarına qatılan `user` i silməliyəm.")
        else:
            update.effective_message.reply_text("Hazırda köhnə qoşulmuş mesajları silmirəm.!")
        return ""

    if args[0].lower() in ("on", "yes"):
        sql.set_del_joined(str(chat.id), True)
        update.effective_message.reply_text("Köhnə qoşulmuş mesajları silməyə çalışacağam!")
        return "<b>{}:</b>" \
               "\n#CLEAN_SERVICE_MESSAGE" \
               "\n<b>Admin:</b> {}" \
               "\nQoşulma silməsini dəyişdirdi <code>Aktiv</code>.".format(html.escape(chat.title),
                                                                         mention_html(user.id, user.first_name))
    elif args[0].lower() in ("off", "no"):
        sql.set_del_joined(str(chat.id), False)
        update.effective_message.reply_text("Köhnə qoşulmuş mesajları silməyəcəyəm.")
        return "<b>{}:</b>" \
               "\n#CLEAN_SERVICE_MESSAGE" \
               "\n<b>Admin:</b> {}" \
               "\nQoşulmuş silməni dəyişdirdi <code>Deaktiv</code>.".format(html.escape(chat.title),
                                                                          mention_html(user.id, user.first_name))
    else:
        # idek what you're writing, say yes or no
        update.effective_message.reply_text("Yalnız 'on / yes' və ya 'off / no' kimi başa düşürəm!")
        return ""


@run_async
def delete_join(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    join = update.effective_message.new_chat_members
    if can_delete(chat, bot.id):
        del_join = sql.get_del_pref(chat.id)
        if del_join:
            update.message.delete()

@run_async
def new_member(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]

    should_welc, cust_welcome, welc_type = sql.get_welc_pref(chat.id)
    if should_welc:
        sent = None
        new_members = update.effective_message.new_chat_members
        for new_mem in new_members:
            # Give the owner a special welcome
            if new_mem.id == OWNER_ID:
                update.effective_message.reply_text("Usta evdədir, gəlin bu ziyafətə başlayaq! :)")
                continue

            # Don't welcome yourself
            elif new_mem.id == bot.id:
                continue

            else:
                # If welcome message is media, send with appropriate function
                if welc_type != sql.Types.TEXT and welc_type != sql.Types.BUTTON_TEXT:
                    ENUM_FUNC_MAP[welc_type](chat.id, cust_welcome)
                    return
                # else, move on
                first_name = new_mem.first_name or "Adsız şəxs"  # edge case of empty name - occurs for some bugs.

                if cust_welcome:
                    if new_mem.last_name:
                        fullname = "{} {}".format(first_name, new_mem.last_name)
                    else:
                        fullname = first_name
                    count = chat.get_members_count()
                    mention = mention_markdown(new_mem.id, escape_markdown(first_name))
                    if new_mem.username:
                        username = "@" + escape_markdown(new_mem.username)
                    else:
                        username = mention

                    valid_format = escape_invalid_curly_brackets(cust_welcome, VALID_WELCOME_FORMATTERS)
                    res = valid_format.format(first=escape_markdown(first_name),
                                              last=escape_markdown(new_mem.last_name or first_name),
                                              fullname=escape_markdown(fullname), username=username, mention=mention,
                                              count=count, chatname=escape_markdown(chat.title), id=new_mem.id)
                    buttons = sql.get_welc_buttons(chat.id)
                    keyb = build_keyboard(buttons)
                else:
                    res = sql.DEFAULT_WELCOME.format(first=first_name)
                    keyb = []

                keyboard = InlineKeyboardMarkup(keyb)

                sent = send(update, res, keyboard,
                            sql.DEFAULT_WELCOME.format(first=first_name))  # type: Optional[Message]
            delete_join(bot, update)

        prev_welc = sql.get_clean_pref(chat.id)
        if prev_welc:
            try:
                bot.delete_message(chat.id, prev_welc)
            except BadRequest as excp:
                pass

            if sent:
                sql.set_clean_welcome(chat.id, sent.message_id)


@run_async
def left_member(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    should_goodbye, cust_goodbye, goodbye_type = sql.get_gdbye_pref(chat.id)
    if should_goodbye:
        left_mem = update.effective_message.left_chat_member
        if left_mem:
            # Ignore bot being kicked
            if left_mem.id == bot.id:
                return

            # Give the owner a special goodbye
            if left_mem.id == OWNER_ID:
                update.effective_message.reply_text("RIP Master")
                return

            # if media goodbye, use appropriate function for it
            if goodbye_type != sql.Types.TEXT and goodbye_type != sql.Types.BUTTON_TEXT:
                ENUM_FUNC_MAP[goodbye_type](chat.id, cust_goodbye)
                return

            first_name = left_mem.first_name or "Adsız şəxs"  # edge case of empty name - occurs for some bugs.
            if cust_goodbye:
                if left_mem.last_name:
                    fullname = "{} {}".format(first_name, left_mem.last_name)
                else:
                    fullname = first_name
                count = chat.get_members_count()
                mention = mention_markdown(left_mem.id, first_name)
                if left_mem.username:
                    username = "@" + escape_markdown(left_mem.username)
                else:
                    username = mention

                valid_format = escape_invalid_curly_brackets(cust_goodbye, VALID_WELCOME_FORMATTERS)
                res = valid_format.format(first=escape_markdown(first_name),
                                          last=escape_markdown(left_mem.last_name or first_name),
                                          fullname=escape_markdown(fullname), username=username, mention=mention,
                                          count=count, chatname=escape_markdown(chat.title), id=left_mem.id)
                buttons = sql.get_gdbye_buttons(chat.id)
                keyb = build_keyboard(buttons)

            else:
                res = sql.DEFAULT_GOODBYE
                keyb = []

            keyboard = InlineKeyboardMarkup(keyb)

            send(update, res, keyboard, sql.DEFAULT_GOODBYE)
            delete_join(bot, update)


@run_async
@user_admin
def welcome(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]
    # if no args, show current replies.
    if len(args) == 0 or args[0].lower() == "noformat":
        noformat = args and args[0].lower() == "noformat"
        pref, welcome_m, welcome_type = sql.get_welc_pref(chat.id)
        update.effective_message.reply_text(
            "Bu söhbətin xoş qarşılama ayarı: `{}`.\n*Xoş gəldin mesajı olaraq "
            "(doldurulmur {{}}) :*".format(pref),
            parse_mode=ParseMode.MARKDOWN)

        if welcome_type == sql.Types.BUTTON_TEXT:
            buttons = sql.get_welc_buttons(chat.id)
            if noformat:
                welcome_m += revert_buttons(buttons)
                update.effective_message.reply_text(welcome_m)

            else:
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)

                send(update, welcome_m, keyboard, sql.DEFAULT_WELCOME)

        else:
            if noformat:
                ENUM_FUNC_MAP[welcome_type](chat.id, welcome_m)

            else:
                ENUM_FUNC_MAP[welcome_type](chat.id, welcome_m, parse_mode=ParseMode.MARKDOWN)

    elif len(args) >= 1:
        if args[0].lower() in ("on", "yes"):
            sql.set_welc_preference(str(chat.id), True)
            update.effective_message.reply_text("Mən nəzakətli olacağam!")

        elif args[0].lower() in ("off", "no"):
            sql.set_welc_preference(str(chat.id), False)
            update.effective_message.reply_text("Artıq salam söyləmirəm, çəkirəm.")

        else:
            # idek what you're writing, say yes or no
            update.effective_message.reply_text("Mən ancaq 'on/yes' və ya 'off/no' başa düşürəm!")


@run_async
@user_admin
def goodbye(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]

    if len(args) == 0 or args[0] == "noformat":
        noformat = args and args[0] == "noformat"
        pref, goodbye_m, goodbye_type = sql.get_gdbye_pref(chat.id)
        update.effective_message.reply_text(
            "Bu söhbətdə vida ayarı təyin edilmişdir: `{}`.\n*Sağollaşma ayarı olaraq "
            "(doldurulmur {{}}):*".format(pref),
            parse_mode=ParseMode.MARKDOWN)

        if goodbye_type == sql.Types.BUTTON_TEXT:
            buttons = sql.get_gdbye_buttons(chat.id)
            if noformat:
                goodbye_m += revert_buttons(buttons)
                update.effective_message.reply_text(goodbye_m)

            else:
                keyb = build_keyboard(buttons)
                keyboard = InlineKeyboardMarkup(keyb)

                send(update, goodbye_m, keyboard, sql.DEFAULT_GOODBYE)

        else:
            if noformat:
                ENUM_FUNC_MAP[goodbye_type](chat.id, goodbye_m)

            else:
                ENUM_FUNC_MAP[goodbye_type](chat.id, goodbye_m, parse_mode=ParseMode.MARKDOWN)

    elif len(args) >= 1:
        if args[0].lower() in ("on", "yes"):
            sql.set_gdbye_preference(str(chat.id), True)
            update.effective_message.reply_text("İnsanlar gedəndə üzr istəyirəm!")

        elif args[0].lower() in ("off", "no"):
            sql.set_gdbye_preference(str(chat.id), False)
            update.effective_message.reply_text("Onlar çıxdılar, mənim üçün öldülər.")

        else:
            # idek what you're writing, say yes or no
            update.effective_message.reply_text("Mən ancaq 'on/yes' və ya 'off/no' başa düşürəm!")


@run_async
@user_admin
@loggable
def set_welcome(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]

    text, data_type, content, buttons = get_welcome_type(msg)

    if data_type is None:
        msg.reply_text("Nə cavab verəcəyinizi müəyyənləşdirməmisiniz!")
        return ""

    sql.set_custom_welcome(chat.id, content or text, data_type, buttons)
    msg.reply_text("Xüsusi qarşılama mesajı uğurla quruldu!")

    return "<b>{}:</b>" \
           "\n#SET_WELCOME" \
           "\n<b>Admin:</b> {}" \
           "\nXoş gəldin ayarı.".format(html.escape(chat.title),
                                               mention_html(user.id, user.first_name))


@run_async
@user_admin
@loggable
def reset_welcome(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    sql.set_custom_welcome(chat.id, sql.DEFAULT_WELCOME, sql.Types.TEXT)
    update.effective_message.reply_text("Salamlama mesajını defolt vəziyyətinə qayıdın!")
    return "<b>{}:</b>" \
           "\n#RESET_WELCOME" \
           "\n<b>Admin:</b> {}" \
           "\nQarşılama mesajını standart olaraq sıfırlayın.".format(html.escape(chat.title),
                                                            mention_html(user.id, user.first_name))


@run_async
@user_admin
@loggable
def set_goodbye(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]
    text, data_type, content, buttons = get_welcome_type(msg)

    if data_type is None:
        msg.reply_text("Nə cavab verəcəyinizi müəyyənləşdirməmisiniz!")
        return ""

    sql.set_custom_gdbye(chat.id, content or text, data_type, buttons)
    msg.reply_text("Xüsusi vida mesajı müvəffəqiyyətlə quruldu!")
    return "<b>{}:</b>" \
           "\n#SET_GOODBYE" \
           "\n<b>Admin:</b> {}" \
           "\nSağollaşma ayarı.".format(html.escape(chat.title),
                                               mention_html(user.id, user.first_name))


@run_async
@user_admin
@loggable
def reset_goodbye(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    sql.set_custom_gdbye(chat.id, sql.DEFAULT_GOODBYE, sql.Types.TEXT)
    update.effective_message.reply_text("Əlvida mesajını müvəqqəti olaraq sıfırlayın!")
    return "<b>{}:</b>" \
           "\n#RESET_GOODBYE" \
           "\n<b>Admin:</b> {}" \
           "\nƏlvida mesajını sıfırlayın.".format(html.escape(chat.title),
                                                 mention_html(user.id, user.first_name))


@run_async
@user_admin
@loggable
def clean_welcome(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]

    if not args:
        clean_pref = sql.get_clean_pref(chat.id)
        if clean_pref:
            update.effective_message.reply_text("İki günə qədər salamlama mesajlarını silməyim lazımdır.")
        else:
            update.effective_message.reply_text("Hazırda köhnə salamlama mesajlarını silmirəm!")
        return ""

    if args[0].lower() in ("on", "yes"):
        sql.set_clean_welcome(str(chat.id), True)
        update.effective_message.reply_text("Köhnə salamlama mesajlarını silməyə çalışacağam!")
        return "<b>{}:</b>" \
               "\n#CLEAN_WELCOME" \
               "\n<b>Admin:</b> {}" \
               "\nTəmiz qarşılayır <code>Aktiv</code>.".format(html.escape(chat.title),
                                                                         mention_html(user.id, user.first_name))
    elif args[0].lower() in ("off", "no"):
        sql.set_clean_welcome(str(chat.id), False)
        update.effective_message.reply_text("Köhnə salamlama mesajlarını silməyəcəm.")
        return "<b>{}:</b>" \
               "\n#CLEAN_WELCOME" \
               "\n<b>Admin:</b> {}" \
               "\nTəmiz qarşılayır <code>Deaktiv</code>.".format(html.escape(chat.title),
                                                                          mention_html(user.id, user.first_name))
    else:
        # idek what you're writing, say yes or no
        update.effective_message.reply_text("Mən ancaq 'on/yes' və ya 'off/no' başa düşürəm!")
        return ""


WELC_HELP_TXT = "Qrupunuzun salamlama / veda mesajları bir çox yolla fərdiləşdirilə bilər. Mesajlarını istəyirsinizsə"  \
                "fərdi olaraq yaradılmaq üçün, standart qarşılama mesajı kimi, * bu * dəyişənlərdən istifadə edə bilərsiniz:\n" \
                " - `{{first}}`: bu istifadəçinin *first* adını əks etdirir\n" \
                " - `{{last}}`: bu istifadəçinin *last* göstərir. Əgər istifadəçi yoxdursa, *first* üçün standartdır " \
                ".\n" \
                " - `{{fullname}}`: bu istifadəçinin *full* adını əks etdirir. İstifadəçinin olmadığı təqdirdə *first*" \
                 "Soyad.\n" \
                " - `{{username}}`: bu istifadəçinin *username* təmsil edir. İstifadəçi adı olmadığı təqdirdə istifadəçinin adının *mention*" \
                "görə standartdır.\n" \
                " - `{{mention}}`: bu sadəcə bir istifadəçini *mentions* - onları adları ilə etiketləyir.\n" \
                " - `{{id}}`: bu istifadəçinin *id*\n" \
                " - `{{count}}`: bu istifadəçinin *member number*.\n" \
                " - `{{chatname}}`: bu istifadəçinin *current chat name* təmsil edir.\n" \
                "\nHər dəyişən dəyişdirilmək üçün '{{}}' ilə əhatə olunmalıdır.\n" \
                "Qarşılama mesajları da işarəni dəstəkləyir, beləliklə istənilən elementləri bold/italic/code/link əlaqələndirə bilərsiniz. " \
                "Düymələr də dəstəklənir, beləliklə xoş girişlərinizi bəzi gözəl giriş düymələri ilə möhtəşəm " \
                "göstərə bilərsiniz.\n" \
                "Qaydalarınızı bağlayan bir düyməni yaratmaq üçün bundan istifadə edin: `[Rules](buttonurl://t.me/{}?start=group_id)`. " \
                "Sadəcə / id vasitəsi ilə əldə edilə bilən qrup identifikatoru ilə `group_id` əvəz edin və yaxşısınız " \
                "Diqqət yetirin ki, qrup id-lərindən əvvəl adətən `-` işarəsi qoyulur; bu tələb olunur, buna görə " \
                "xahiş etmirəm.\n" \
                "Əgər özünüzü əyləndirirsinizsə, şəkilləri / gifləri / videoları / səsli mesajlarını " \
                "istədiyiniz mediaya cavab vermək və zəng etmək /setwelcome.".format(dispatcher.bot.username)


@run_async
@user_admin
def welcome_help(bot: Bot, update: Update):
    update.effective_message.reply_text(WELC_HELP_TXT, parse_mode=ParseMode.MARKDOWN)


# TODO: get welcome data from group butler snap
# def __import_data__(chat_id, data):
#     welcome = data.get('info', {}).get('rules')
#     welcome = welcome.replace('$username', '{username}')
#     welcome = welcome.replace('$name', '{fullname}')
#     welcome = welcome.replace('$id', '{id}')
#     welcome = welcome.replace('$title', '{chatname}')
#     welcome = welcome.replace('$surname', '{lastname}')
#     welcome = welcome.replace('$rules', '{rules}')
#     sql.set_custom_welcome(chat_id, welcome, sql.Types.TEXT)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    welcome_pref, _, _ = sql.get_welc_pref(chat_id)
    goodbye_pref, _, _ = sql.get_gdbye_pref(chat_id)
    return "Bu söhbətin xoş gəlmə tərzi seçilib `{}`.\n" \
           "Əlvida seçimidir `{}`.".format(welcome_pref, goodbye_pref)


__help__ = """
{}

* Yalnız admin: *
 - /welcome <on/off>: salamlama mesajlarını aktivləşdir / söndür.
 - /welcome: mövcud qarşılama parametrlərini göstərir.
 - /welcome noformat: formatlama olmadan mövcud qarşılama parametrlərini göstərir - xoş mesajlarınızı təkrar istifadə etmək üçün faydalıdır!
 - /goodbye -> eyni istifadə və arqlar / xoş gəldiniz.
 - /setwelcome <sometext>: xüsusi salamlama mesajı təyin edin. Medyaya cavab vermək üçün istifadə olunursa, bu mediadan istifadə edir.
 - /setgoodbye <sometext>: xüsusi bir vida mesajı təyin edin. Medyaya cavab vermək üçün istifadə olunursa, bu mediadan istifadə edir.
 - /resetwelcome: standart qarşılama mesajına yenidən qurun.
 - /resetgoodbye: standart vİda mesajına sıfırlayın.
 - /cleanwelcome <on/off>: Yeni üzvdə, söhbətə spam göndərməmək üçün əvvəlki salamlama mesajını silməyə çalışın.
 - /clearjoin <on/off>: kimsə qoşulduqda, *user* qrup mesajına qoşulduğunu silməyə çalışın.
 - /welcomehelp: xüsusi salamlama / vida mesajları üçün daha çox formatlama məlumatına baxın.

""".format(WELC_HELP_TXT)

__mod_name__ = "Salamlama/Sağollaşma"

NEW_MEM_HANDLER = MessageHandler(Filters.status_update.new_chat_members, new_member)
LEFT_MEM_HANDLER = MessageHandler(Filters.status_update.left_chat_member, left_member)
WELC_PREF_HANDLER = CommandHandler("welcome", welcome, pass_args=True, filters=Filters.group)
GOODBYE_PREF_HANDLER = CommandHandler("goodbye", goodbye, pass_args=True, filters=Filters.group)
SET_WELCOME = CommandHandler("setwelcome", set_welcome, filters=Filters.group)
SET_GOODBYE = CommandHandler("setgoodbye", set_goodbye, filters=Filters.group)
RESET_WELCOME = CommandHandler("resetwelcome", reset_welcome, filters=Filters.group)
RESET_GOODBYE = CommandHandler("resetgoodbye", reset_goodbye, filters=Filters.group)
CLEAN_WELCOME = CommandHandler("cleanwelcome", clean_welcome, pass_args=True, filters=Filters.group)
DEL_JOINED = CommandHandler("clearjoin", del_joined, pass_args=True, filters=Filters.group)
WELCOME_HELP = CommandHandler("welcomehelp", welcome_help)


dispatcher.add_handler(NEW_MEM_HANDLER)
dispatcher.add_handler(LEFT_MEM_HANDLER)
dispatcher.add_handler(WELC_PREF_HANDLER)
dispatcher.add_handler(GOODBYE_PREF_HANDLER)
dispatcher.add_handler(SET_WELCOME)
dispatcher.add_handler(SET_GOODBYE)
dispatcher.add_handler(RESET_WELCOME)
dispatcher.add_handler(RESET_GOODBYE)
dispatcher.add_handler(CLEAN_WELCOME)
dispatcher.add_handler(DEL_JOINED)
dispatcher.add_handler(WELCOME_HELP)
