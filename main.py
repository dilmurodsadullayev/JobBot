import asyncio
import html
import logging
import os # Fayl yo'lini tekshirish uchun
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, ReplyKeyboardRemove
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest


try:
    from vacancy_parser import VacancyParser, DEFAULT_ITEMS_PER_PAGE
except ImportError:
    logging.error("vacancy_parser modulini topib bo'lmadi. Fayl shu papkadami yoki DEFAULT_ITEMS_PER_PAGE eksport qilinganmi?")
    exit(1)

BOT_TOKEN = "7892017759:AAFICJrjmB2PN9G93LiNIiRsuBseDKRHujA" 
API_URL = "https://job.ubtuit.uz/api/v1/vacancies/"
TATU_UF_WEBSITE_URL = "https://ubtuit.uz/" # TATU UF sayti manzili
OBYEKTIVKA_FILE_PATH = "Obyektivka_namuna.docx" # Obyektivka faylining nomi (bot papkasida)

buttons_search_active = [
        [KeyboardButton(text="Ortga")],
    ]
skeyboard_active_search = ReplyKeyboardMarkup(keyboard=buttons_search_active, resize_keyboard=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
vacancy_parser: VacancyParser | None = None

class SearchState(StatesGroup):
    browsing = State()

def create_start_keyboard():
    buttons = [
        [KeyboardButton(text="Vakansiyalarni qidirish")],
        [
            KeyboardButton(text="TATU UF Asosiy sayti"),
            KeyboardButton(text="Obyektivka namunasini yuklab olish")
        ],
        [KeyboardButton(text="Bot haqida malumot")]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, input_field_placeholder="Menyudan tanlang:")
    return keyboard

def create_vacancy_navigation_keyboard(
    vacancies_on_page: list,
    current_page: int,
    total_pages: int
    ) -> InlineKeyboardMarkup | None:

    if not vacancies_on_page:
        return None

    builder = InlineKeyboardBuilder()

    for i, vacancy in enumerate(vacancies_on_page):
        position = vacancy.get('position', f'Noma’lum lavozim #{i+1}')
        callback_data = f"vacancy:{i}"

        if len(callback_data.encode('utf-8')) > 64:
            logging.warning(f"Callback data for vacancy exceeds 64 bytes, skipping button: {callback_data}")
            continue

        builder.row(InlineKeyboardButton(text=position, callback_data=callback_data))

    pagination_row = []
    if current_page > 1:
        pagination_row.append(
            InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"page:{current_page - 1}")
        )
    if current_page < total_pages:
        pagination_row.append(
            InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"page:{current_page + 1}")
        )

    if pagination_row:
        builder.row(*pagination_row)

    return builder.as_markup()


@dp.message(F.text == "Ortga", StateFilter('*'))
async def handle_back_button(message: types.Message, state: FSMContext):
    current_state_str = await state.get_state()
    logging.info(f"User {message.from_user.id} pressed 'Ortga'. Current state: {current_state_str}")
    await state.clear()
    logging.info(f"State cleared for user {message.from_user.id}. Returning to start menu.")
    keyboard = create_start_keyboard()
    user_name = html.escape(message.from_user.first_name)
    await message.answer(f"Salom {user_name}, TATU UF vakansiyalar Telegram Botiga xush kelibsiz!", reply_markup=keyboard)

@dp.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    await state.clear()
    keyboard = create_start_keyboard()
    user_name = html.escape(message.from_user.first_name)
    await message.answer(f"Salom {user_name}, TATU UF vakansiyalar Telegram Botiga xush kelibsiz!", reply_markup=keyboard)

# --- Yangi tugmalar uchun handlerlar ---
@dp.message(F.text == "TATU UF Asosiy sayti", StateFilter(None))
async def handle_website_button(message: types.Message):
    logging.info(f"User {message.from_user.id} requested TATU UF website link.")
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💻 Saytga o'tish", url=TATU_UF_WEBSITE_URL)]
        ]
    )
    await message.answer("Muhammad al-Xorazmiy nomidagi TATU Urganch filialining rasmiy veb-saytiga o'tish uchun quyidagi tugmani bosing:", reply_markup=keyboard)

@dp.message(F.text == "Obyektivka namunasini yuklab olish", StateFilter(None))
async def handle_obyektivka_button(message: types.Message):
    logging.info(f"User {message.from_user.id} requested obyektivka sample.")
    if os.path.exists(OBYEKTIVKA_FILE_PATH):
        try:
            await message.answer_chat_action(types.ChatAction.UPLOAD_DOCUMENT) # Fayl yuklanayotganini bildirish
            document = FSInputFile('', filename="Obyektivka_namuna.docx")
            await message.answer_document('Obyektivka_namuna.docx', caption="Obyektivka (Ma'lumotnoma) namunasi.")
            logging.info(f"Obyektivka sample sent to user {message.from_user.id}")
        except Exception as e:
            logging.error(f"Error sending obyektivka to {message.from_user.id}: {e}")
            await message.answer("📄 Faylni yuborishda xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring.")
    else:
        logging.warning(f"Obyektivka file not found at {OBYEKTIVKA_FILE_PATH}")
        await message.answer("📄 Kechirasiz, hozirda obyektivka namunasi mavjud emas. Iltimos, keyinroq qayta urinib ko'ring.")

@dp.message(F.text == "Bot haqida ma'lumot", StateFilter(None))
async def handle_about_bot_button(message: types.Message):
    logging.info(f"User {message.from_user.id} requested bot info.")

    # HTML teglarni minimal darajada ishlatamiz va matnni oldindan escape qilamiz
    # Bu yerda @username ni haqiqiy username bilan almashtiring yoki olib tashlang
    admin_contact = "@usman_niyazbekov" # Admin kontaktini o'zgartiring

    bot_title = "TATU UF Vakansiyalar Boti"
    description = (
        "Bu bot Muhammad al-Xorazmiy nomidagi Toshkent axborot texnologiyalari universiteti "
        "Urganch filialidagi (TATU UF) mavjud bo'sh ish o'rinlari (vakansiyalar) "
        "haqida ma'lumot olish uchun mo'ljallangan."
    )
    features_title = "Asosiy funksiyalari:"
    feature1 = "Vakansiyalarni qidirish va ko'rish"
    feature2 = "Obyektivka namunasini yuklab olish"
    feature3 = "TATU UF rasmiy saytiga o'tish"
    data_source = "Bot job.ubtuit.uz sayti ma'lumotlaridan foydalanadi."
    contact_info = f"Agar taklif yoki shikoyatlaringiz bo'lsa, {html.escape(admin_contact)} manziliga murojaat qilishingiz mumkin."

    # Matnni yig'amiz
    bot_info_text_parts = [
        f"<b>🤖 {html.escape(bot_title)}</b>",
        "", # Bo'sh qator
        html.escape(description),
        "",
        f"<b>{html.escape(features_title)}</b>",
        f"✅ {html.escape(feature1)}",
        f"📄 {html.escape(feature2)}",
        f"🌐 {html.escape(feature3)}",
        "",
        html.escape(data_source),
        html.escape(contact_info)
    ]
    bot_info_text = "\n".join(bot_info_text_parts)

    try:
        # parse_mode="HTML" bot obyektini yaratishda global o'rnatilgan bo'lsa,
        # bu yerda alohida ko'rsatish shart emas.
        await message.answer(bot_info_text)
        logging.info(f"Bot info sent to user {message.from_user.id}")
    except Exception as e:
        logging.error(f"Error sending bot info to {message.from_user.id}: {e}", exc_info=True)
        # Xatolik yuz berganda foydalanuvchiga oddiy xabar yuborish
        try:
            await message.answer("Bot haqida ma'lumotni ko'rsatishda texnik xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring.")
        except Exception as fallback_e:
            logging.error(f"Error sending fallback bot info error message: {fallback_e}")

# --- Vakansiya qidirish bilan bog'liq handlerlar ---
@dp.message(F.text == "Vakansiyalarni qidirish", StateFilter(None))
async def search_vacancies_handler(message: types.Message, state: FSMContext):
    global vacancy_parser
    if not vacancy_parser:
         logging.error("VacancyParser not initialized when trying to search.")
         await message.answer("Xatolik: Bot hali tayyor emas, birozdan so'ng urinib ko'ring.")
         return

    await message.answer("⏳ Vakansiyalar qidirilmoqda...", reply_markup=skeyboard_active_search) # Vakansiya qidirishda "Ortga" tugmasi
    current_page = 1

    try:
        vacancies_page_1, total_pages, total_items = await vacancy_parser.get_vacancies(
            query="",
            page=current_page
        )

        if vacancies_page_1 is None:
            await message.answer("❌ Vakansiyalarni olishda xatolik yuz berdi. API bilan muammo bo'lishi mumkin.", reply_markup=create_start_keyboard()) # Bosh menyuga qaytarish uchun klaviatura
            await state.clear()
            return

        if not vacancies_page_1:
            await message.answer("Hozircha aktiv vakansiyalar mavjud emas.", reply_markup=create_start_keyboard()) # Bosh menyuga qaytarish uchun klaviatura
            await state.clear()
            return

        await state.set_state(SearchState.browsing)
        await state.update_data(
            current_vacancies=vacancies_page_1,
            current_page=current_page,
            total_pages=total_pages,
            total_items=total_items
        )
        logging.info(f"Initial search: Found {total_items} items across {total_pages} pages. Displaying page 1.")

        keyboard = create_vacancy_navigation_keyboard(
            vacancies_on_page=vacancies_page_1,
            current_page=current_page,
            total_pages=total_pages
        )

        if keyboard:
            message_text = f"Topilgan vakansiyalar ({total_items} ta): Sahifa {current_page} / {total_pages}"
            await message.answer(message_text, reply_markup=keyboard)
        else:
             await message.answer("Vakansiyalarni ko'rsatishda kutilmagan muammo yuz berdi.", reply_markup=create_start_keyboard())
             await state.clear()


    except Exception as e:
        logging.exception("Vakansiyalarni qidirish handlerida kutilmagan xatolik!")
        await message.answer("Texnik xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring.", reply_markup=create_start_keyboard())
        await state.clear()


@dp.callback_query(SearchState.browsing, F.data.startswith("page:"))
async def pagination_handler(query: types.CallbackQuery, state: FSMContext):
    global vacancy_parser
    if not vacancy_parser:
        logging.error("VacancyParser not available during pagination.")
        await query.answer("Xatolik: Parser topilmadi.", show_alert=True)
        return

    try:
        target_page = int(query.data.split(":")[1])
    except (IndexError, ValueError):
        logging.warning(f"Could not parse page number from callback data: {query.data}")
        await query.answer("Xatolik: Sahifa raqami noto'g'ri.", show_alert=True)
        return

    await query.answer(f"⏳ {target_page}-sahifa yuklanmoqda...")

    try:
        new_vacancies, total_pages, total_items = await vacancy_parser.get_vacancies(
            query="",
            page=target_page
        )

        if new_vacancies is None:
            await query.message.edit_text("❌ Sahifani yuklashda xatolik yuz berdi.")
            return


        await state.update_data(
            current_vacancies=new_vacancies,
            current_page=target_page,
            total_pages=total_pages,
            total_items=total_items
        )
        logging.info(f"Pagination: User switched to page {target_page}. Total items: {total_items}, Total pages: {total_pages}.")

        new_keyboard = create_vacancy_navigation_keyboard(
            vacancies_on_page=new_vacancies,
            current_page=target_page,
            total_pages=total_pages
        )

        message_text = f"Topilgan vakansiyalar ({total_items} ta): Sahifa {target_page} / {total_pages}"

        if new_keyboard:
             await query.message.edit_text(message_text, reply_markup=new_keyboard)
        else:
             empty_page_text = f"{message_text}\n\nBu sahifada boshqa vakansiya yo'q."
             builder = InlineKeyboardBuilder()
             if target_page > 1:
                 builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"page:{target_page - 1}"))
             await query.message.edit_text(empty_page_text, reply_markup=builder.as_markup() if target_page > 1 else None)


    except TelegramBadRequest as e:
        if "message to edit not found" in str(e).lower() or \
           "message is not modified" in str(e).lower():
            logging.warning(f"Could not edit message for pagination (likely already deleted or same content): {e}")
            await query.answer("Xabar yangilanmadi (o'chirilgan yoki o'zgartirilmagan bo'lishi mumkin).", show_alert=False)
        else:
            logging.warning(f"Could not edit message for pagination (TelegramBadRequest): {e}")
            await query.answer("Xabar yangilanmadi (eskirgan bo'lishi mumkin).", show_alert=True)
    except Exception as e:
        logging.exception("Pagination handlerida kutilmagan xatolik!")
        try:
            await query.message.edit_text("Sahifani o'zgartirishda texnik xatolik yuz berdi.")
        except Exception:
            await query.answer("Sahifani o'zgartirishda xatolik.", show_alert=True)



@dp.callback_query(SearchState.browsing, F.data.startswith("vacancy:"))
async def vacancy_callback(query: types.CallbackQuery, state: FSMContext):
    await query.answer()

    try:
        relative_index = int(query.data.split(":")[1])
    except (IndexError, ValueError):
        logging.warning(f"Could not parse relative index from callback data: {query.data}")
        await query.message.edit_text("Noto'g'ri ma'lumot. Qaytadan urinib ko'ring.", reply_markup=None)
        return

    data = await state.get_data()
    current_vacancies = data.get('current_vacancies')
    current_page = data.get('current_page', 1)

    if not current_vacancies or not isinstance(current_vacancies, list):
        logging.warning("Vacancies list not found or invalid in state for detail view.")
        await query.message.edit_text("Vakansiyalar ro'yxati topilmadi (ma'lumot eskirgan bo'lishi mumkin). Qidiruvni qaytadan boshlang.", reply_markup=None)
        # await state.clear() # Bu yerda clear qilish shartmas, "Ortga" bosilsa tozalaydi.
        return

    if 0 <= relative_index < len(current_vacancies):
        vacancy = current_vacancies[relative_index]
        logging.info(f"Displaying details for vacancy index {relative_index} from page {current_page}")

        details = [
            f"<b>Lavozim:</b> {html.escape(vacancy.get('position', '<i>Noma’lum</i>'))}",
            f"<b>Bo'lim:</b> {html.escape(vacancy.get('department', '<i>Noma’lum</i>'))}",
            f"<b>Maosh:</b> {html.escape(vacancy.get('salary', '<i>Ko’rsatilmagan</i>'))}",
            f"<b>Talab qilinadigan tajriba:</b> {html.escape(vacancy.get('experience', '<i>Noma’lum</i>'))}",
            f"<b>Ish jadvali:</b> {html.escape(vacancy.get('work_schedule', '<i>Noma’lum</i>'))}",
            f"<b>Talablar:</b> {html.escape(vacancy.get('requirement', '<i>Noma’lum</i>'))}",
            f"<b>Ochilish vaqti:</b> {html.escape(vacancy.get('opening_time', '<i>Noma’lum</i>'))}",
            f"<b>Yopilish vaqti:</b> {html.escape(vacancy.get('end_time', '<i>Noma’lum</i>'))}",
            f"<b>Ushbu vakansiyaga</b> <a href='https://job.ubtuit.uz/job/{vacancy.get('id')}'>ARIZA BERISH</a>",
        ]
        message_text = "\n".join(filter(None, details))

        back_button_builder = InlineKeyboardBuilder()
        back_button_builder.row(
            InlineKeyboardButton(text="⬅️ Ro'yxatga qaytish", callback_data=f"page:{current_page}")
        )

        try:
            await query.message.edit_text(
                message_text,
                parse_mode="HTML",
                reply_markup=back_button_builder.as_markup(),
                disable_web_page_preview=True
            )
        except TelegramBadRequest as e:
             if "message to edit not found" in str(e).lower() or \
                "message is not modified" in str(e).lower():
                 logging.warning(f"Could not edit message for vacancy detail (likely already deleted or same content): {e}")
                 await query.answer("Xabarni yangilab bo'lmadi (o'chirilgan yoki o'zgartirilmagan).", show_alert=False)
             else:
                 logging.warning(f"Could not edit message for vacancy detail (TelegramBadRequest): {e}")
                 await query.answer("Xabarni yangilab bo'lmadi.", show_alert=True)
        except Exception as edit_err:
             logging.error(f"Could not edit message for vacancy detail: {edit_err}")
             await query.answer("Xabarni ko'rsatishda xatolik.", show_alert=True)


    else:
        logging.warning(f"Invalid relative index requested: {relative_index}. List size: {len(current_vacancies)} on page {current_page}")
        await query.message.edit_text("Tanlangan vakansiya joriy sahifada topilmadi (ro'yxat yangilangan bo'lishi mumkin). Qidiruvni qaytadan boshlang.", reply_markup=None)


async def main():
    global vacancy_parser
    vacancy_parser = VacancyParser(API_URL)

    logging.info("Bot ishga tushmoqda...")
    print("Bot is starting...")

    commands = [
        types.BotCommand(command="/start", description="Botni ishga tushirish / Bosh menyu")
    ]
    try:
        await bot.set_my_commands(commands)
        logging.info("Bot komandalari o'rnatildi.")
    except Exception as e:
        logging.error(f"Bot komandalarini o'rnatishda xatolik: {e}")

    try:
        await dp.start_polling(bot)
    finally:
        logging.info("Bot to'xtatilmoqda...")
        print("Bot is stopping...")
        await bot.session.close()
        if vacancy_parser:
            await vacancy_parser.close()
        logging.info("Bot to'xtatildi.")
        print("Bot stopped.")

if __name__ == "__main__":
    # Obyektivka fayli mavjudligini tekshirish (ixtiyoriy, ishga tushirishdan oldin)
    if not os.path.exists(OBYEKTIVKA_FILE_PATH):
        logging.warning(f"DIQQAT: Obyektivka fayli '{OBYEKTIVKA_FILE_PATH}' topilmadi. Fayl yuklash funksiyasi ishlamasligi mumkin.")
        print(f"WARNING: Obyektivka file '{OBYEKTIVKA_FILE_PATH}' not found. File upload feature might not work.")

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Dastur foydalanuvchi tomonidan to'xtatildi.")
    except Exception as e:
        logging.critical(f"Kritik xatolik main execution loopdan tashqarida: {e}", exc_info=True)
        print(f"CRITICAL ERROR outside main loop: {e}")