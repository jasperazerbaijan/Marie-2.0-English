import json
from io import BytesIO
from typing import Optional

from telegram import Message, Chat, Update, Bot
from telegram.error import BadRequest
from telegram.ext import CommandHandler, run_async

from tg_bot import dispatcher, LOGGER
from tg_bot.__main__ import DATA_IMPORT
from tg_bot.modules.helper_funcs.chat_status import user_admin


@run_async
@user_admin
def import_data(bot: Bot, update):
    msg = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    # TODO: allow uploading doc with command, not just as reply
    # only work with a doc
    if msg.reply_to_message and msg.reply_to_message.document:
        try:
            file_info = bot.get_file(msg.reply_to_message.document.file_id)
        except BadRequest:
            msg.reply_text("İdxal etməzdən əvvəl dosyanı özünüz kimi yükləməyə və yenidən yükləməyə çalışın.")
            return

        with BytesIO() as file:
            file_info.download(out=file)
            file.seek(0)
            data = json.load(file)

        # only import one group
        if len(data) > 1 and str(chat.id) not in data:
            msg.reply_text("Bu sənəddə burada birdən çox qrup var və heç kimin bu qrupla eyni çat kimliyi yoxdur "
                           "- nəyi idxal edəcəyimi necə seçim?")
            return

        # Select data source
        if str(chat.id) in data:
            data = data[str(chat.id)]['hashes']
        else:
            data = data[list(data.keys())[0]]['hashes']

        try:
            for mod in DATA_IMPORT:
                mod.__import_data__(str(chat.id), data)
        except Exception:
            msg.reply_text("Verilərinizi bərpa edərkən bir istisna meydana gəldi. Proses tam olmaya bilər. Əgər "
                           "bu mövzuda problem yaşayırsınız, ehtiyat sənədinizlə @JasperSupport mesajı göndərin."
                           "məsələ həll edilə bilər. Sahiblərim kömək etməkdən məmnun olarlar və hər səhv"
                           "bildirildi məni yaxşılaşdırır! Təşəkkürlər! :)")
            LOGGER.exception(" %s adı ilə %s üçün idxal edilmədi!", str(chat.id), str(chat.title))
            return

        # TODO: some of that link logic
        # NOTE: consider default permissions stuff?
        msg.reply_text("Yedəkləmə tamamilə idxal edildi. Xoş gəlmisiniz! :D")


@run_async
@user_admin
def export_data(bot: Bot, update: Update):
    msg = update.effective_message  # type: Optional[Message]
    msg.reply_text("")


__mod_name__ = "Yedəklə"

__help__ = """
* Yalnız admin: *
 - /import: Transferi çox sadə hala gətirərək mümkün qədər idxal etmək üçün bir qrup adamın ehtiyat sənədinə cavab verin! Qeyd \
telegram məhdudiyyətləri səbəbindən faylların / fotoların idxal edilə bilinmir.
 - /export: !!! Bu hələ bir əmr deyil, amma tezliklə gəlməlidir!
"""
IMPORT_HANDLER = CommandHandler("import", import_data)
EXPORT_HANDLER = CommandHandler("export", export_data)

dispatcher.add_handler(IMPORT_HANDLER)
# dispatcher.add_handler(EXPORT_HANDLER)
