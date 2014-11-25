import logging
from time import sleep
from datetime import datetime, date, timedelta
import signal

from dialog import Dialog

from Connector import Connector
from Settings import Settings
from UserModel import UserModel


__version__ = "0.6"
__author__ = 'novikov'

# TODO Вынести в настройки
DELAY = 2
VISITS_LOG = 'visits.log'

dialog = Dialog(dialog='dialog')

# TODO Вынести формат, сделать его читаемым
logging.basicConfig(format='%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s',
                    level=logging.DEBUG,
                    filename='application.log')
connector = None
settings = None


def append_visit(operator: UserModel):
    with open(VISITS_LOG, mode='a') as visits:
        visits.write(datetime.now().strftime('%a, %d %B %Y, %H:%M:%S: Вошел {} ({}) \n').format(operator.name,
                                                                                                operator.get_access()))


def append_wrong_password(operator: UserModel):
    with open(VISITS_LOG, mode='a') as visits:
        visits.write(datetime.now().strftime('%a, %d %B %Y, %H:%M:%S: Неверный ввод пароля к аккаунту {} ({}) \n').
                     format(operator.name, operator.get_access()))


def append_wrong_id(card_id):
    with open(VISITS_LOG, mode='a') as visits:
        visits.write(datetime.now().strftime('%a, %d %B %Y, %H:%M:%S: Неверный ID карты: {} \n').
                     format(card_id))


def create_password(operator: UserModel):
    logging.info("Попытка смены пароля пользователем {} с правами доступа {}".format(
        operator.name,
        operator.get_access()))
    dialog.msgbox("Вам необходимо задать пароль учетной записи",
                  width=0,
                  height=0)
    code, password = dialog.passwordbox("Пароль:",
                                        width=0,
                                        height=0,
                                        title="Новый пароль",
                                        insecure=True)
    if code != dialog.OK:
        return False
    code, password_reply = dialog.passwordbox("Пароль:",
                                              width=0,
                                              height=0,
                                              title="Подтверждение пароля",
                                              insecure=True)
    if code != dialog.OK:
        return False
    if password_reply != password:
        code = dialog.yesno("Пароли не совпадают \n" +
                            "Повторить попытку?",
                            width=0,
                            height=0)
        if code == dialog.OK:
            create_password(operator)
        else:
            return False
    operator.update_password(password)
    connector.update_user(operator)
    logging.info("Пароль пользователя {} с правами доступа {} изменен".format(
        operator.name,
        operator.get_access()))
    return True


def show_user_info(operator: UserModel):
    info = ("Имя: {} \n" +
            "Уровень доступа: {} \n" +
            "Истекает: {} \n" +
            "Пароль: {}").format(
        operator.name,
        operator.get_access(),
        operator.expire,
        {
            True: 'установлен',
            False: 'отсутствует'
        }[operator.has_password()]
    )
    dialog.msgbox(info,
                  width=0,
                  height=0)


def add_user(operator: UserModel):
    dialog.set_background_title("Добавление пользователя")
    code, name = dialog.inputbox("Введите имя нового пользователя:",
                                 width=0,
                                 height=0,
                                 init="Иван Петров")
    if code != dialog.OK:
        return
    code, card_id = dialog.passwordbox("Приложите карту нового пользователя...",
                                       width=0,
                                       height=0)
    if code != dialog.OK:
        return
    if connector.get_user(card_id):
        dialog.msgbox("Ошибка: данная карта уже зарегестрирована",
                      width=0,
                      height=0)
        return
    choices = UserModel.LEVELS[:-1]
    if operator.access == UserModel.DEVELOPER:
        choices = UserModel.LEVELS
    code, tag = dialog.radiolist("Выберите уровень доступа:",
                                 width=0,
                                 height=0,
                                 choices=[(str(choices.index(x) + 1), x, choices.index(x) == 0) for x in choices])
    if code != dialog.OK:
        return
    access = int(tag) - 1
    code, raw_date = dialog.calendar("Введите дату окончания действия аккаунта:",
                                     width=0,
                                     height=0,
                                     day=1,
                                     month=1,
                                     year=2050)
    if code != dialog.OK:
        return
    expire = datetime(day=raw_date[0], month=raw_date[1], year=raw_date[2])
    user = UserModel(creator=operator.name,
                     card_id=card_id,
                     name=name,
                     access=access,
                     expire=expire)
    connector.add_user(user)
    dialog.set_background_title("Пользователь создан")
    show_user_info(user)


def add_guest(operator: UserModel):
    dialog.set_background_title("Добавление гостя")
    code, name = dialog.inputbox("Введите имя гостя:",
                                 width=0,
                                 height=0,
                                 init="Иван Петров")
    if code != dialog.OK:
        return
    code, card_id = dialog.passwordbox("Приложите карту гостя...",
                                       width=0,
                                       height=0)
    if code != dialog.OK:
        return
    if connector.get_user(card_id):
        dialog.msgbox("Ошибка: данная карта уже зарегестрирована",
                      width=0,
                      height=0)
        return
    access = UserModel.GUEST
    tomorrow = date.today() + timedelta(days=1)
    expire = datetime(tomorrow.year, tomorrow.month, tomorrow.day)
    user = UserModel(creator=operator.name,
                     card_id=card_id,
                     name=name,
                     access=access,
                     expire=expire)
    connector.add_user(user)
    dialog.set_background_title("Гость создан")
    show_user_info(user)


def show_visits_log(operator: UserModel):
    logging.info("Пользователь {} с правами доступа '{}' просматривает лог посещений".format(
        operator.name,
        operator.get_access()
    ))
    dialog.textbox(VISITS_LOG,
                   width=0,
                   height=0)


def create_settings():
    global settings
    dialog.msgbox("Будет создан файл настроек",
                  width=0,
                  height=0)
    code, db_values = dialog.form("Настройик базы данных",
                                  width=0,
                                  height=0,
                                  elements=[
                                      ("Хост:", 1, 1, 'localhost', 1, len("Коллекция:") + 2, 20, 20),
                                      ("Порт:", 2, 1, '27017', 2, len("Коллекция:") + 2, 20, 20),
                                      ("Логин:", 3, 1, '', 3, len("Коллекция:") + 2, 20, 20),
                                      ("База:", 4, 1, '', 4, len("Коллекция:") + 2, 20, 20),
                                      ("Коллекция:", 5, 1, '', 5, len("Коллекция:") + 2, 20, 20)
                                  ])
    if code != dialog.OK:
        return False
    settings.set_db_option(settings.DB_HOST, db_values[0])
    settings.set_db_option(settings.DB_PORT, db_values[1])
    settings.set_db_option(settings.DB_USER, db_values[2])
    settings.set_db_option(settings.DB_NAME, db_values[3])
    settings.set_db_option(settings.DB_COLLECTION, db_values[4])
    if settings.get_db_option(settings.DB_USER):
        code, password = dialog.passwordbox("Пароль пользователя {}".format(settings.get_db_option(settings.DB_USER)),
                                            width=0,
                                            height=0,
                                            insecure=True)
        if code != dialog.OK:
            return False
        settings.set_db_option(settings.DB_PASSWORD, password)

    settings.save()
    return True


def show_control_window(operator: UserModel, should_check=True):
    logging.info("Пользователь {} с правами доступа '{}' пытается получить доступ к консоли управления".format(
        operator.name,
        operator.get_access()
    ))
    dialog.set_background_title("Консоль управления")
    if should_check:
        if not operator.has_password():
            logging.info("Пользователь {} с правами доступа '{}' создает новый пароль".format(
                operator.name,
                operator.get_access()
            ))
            if not create_password(operator):
                return
        else:
            code, password = dialog.passwordbox("Пароль:",
                                                width=0,
                                                height=0,
                                                title="Подтверждение доступа",
                                                insecure=True)
            if code != dialog.OK:
                return
            if not operator.check_password(password):
                logging.info("Пользователь {} с правами доступа '{}' неверно ввел пароль".format(
                    operator.name,
                    operator.get_access()
                ))
                dialog.infobox("Неверное сочетание логина и пароля \n" +
                               "Запись добавлена в лог",
                               width=0,
                               height=0)
                append_wrong_password(operator)
                sleep(DELAY)
                return
    choices = ["Просмотр сведений об учетной записи"]
    if operator.access >= UserModel.COMMON:
        choices.extend(["Просмотр лога посещений", "Добавление гостя", "Изменение пароля"])
    if operator.access >= UserModel.PRIVILEGED:
        choices.extend(["Добавление пользователя", "Редактирование пользователей", "Режим открытого доступа"])
    if operator.access >= UserModel.DEVELOPER:
        choices.extend(["Просмотр системных логов", "Расширенные настройки"])
    code, tag = dialog.menu("Выберите действие",
                            choices=[('{}'.format(choices.index(x) + 1), x) for x in choices])
    if code != dialog.OK:
        return
    [
        lambda: show_user_info(operator),
        lambda: show_visits_log(operator),
        lambda: add_guest(operator),
        lambda: create_password(operator),
        lambda: add_user(operator)
    ][int(tag) - 1]()
    show_control_window(operator, False)


def standard_mode():
    dialog.set_background_title("Рабочий режим")
    while True:
        code, card_id = dialog.passwordbox("ID:",
                                           width=0,
                                           height=0,
                                           title="Приложите карту...")
        if code == dialog.OK:
            operator = connector.get_user(card_id)
            if not operator:
                dialog.infobox("Карта отклонена! \n" +
                               "Запись добавлена в лог",
                               width=0,
                               height=0)
                append_wrong_id(card_id)
                sleep(DELAY)
            else:
                code = dialog.pause("Авторизация успешна \n" +
                                    "Пользователь: {} \n".format(operator.name) +
                                    "Уровень доступа: {} \n".format(UserModel.LEVELS[operator.access]),
                                    seconds=5,
                                    title="ОК",
                                    extra_button=True,
                                    extra_label="Консоль")
                append_visit(operator)
                if code == dialog.EXTRA:
                    show_control_window(operator)
                # Opening the door
                pass
        if code == dialog.ESC:
            dialog.msgbox("Работа завершена",
                          width=0,
                          height=0)
            exit(0)


def main():
    global connector
    global settings
    dialog.msgbox("RFID контроллер \n" +
                  "Автор: Илья Новиков, КРБ-1-13",
                  width=0,
                  height=0)
    with open(VISITS_LOG, mode='a') as visits:
        visits.write(
            datetime.now().strftime('%a, %d %B %Y, %H:%M:%S: Приложение запущено, версия {} \n').format(__version__))
    logging.info("Приложение запущено, версия {}".format(__version__))
    connector = Connector()
    settings = Settings()
    if settings.is_first_run:
        if not create_settings():
            dialog.msgbox("Настройки не были сохранены, работа завершена")
            exit(0)

    standard_mode()


signals = [{'orig': signal.signal(signal.SIGINT, signal.SIG_IGN), 'signal': signal.SIGINT},
           {'orig': signal.signal(signal.SIGQUIT, signal.SIG_IGN), 'signal': signal.SIGQUIT},
           {'orig': signal.signal(signal.SIGTSTP, signal.SIG_IGN), 'signal': signal.SIGTSTP}]

main()

for s in signals:
    signal.signal(s['signal'], s['orig'])