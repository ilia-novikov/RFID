#! /usr/bin/env python3

import logging
from time import sleep
from datetime import datetime, date, timedelta
import signal
from os import getuid, remove, path

from dialog import Dialog
from pymongo.errors import PyMongoError

from com.novikov.rfid.CardReader import CardReader
from com.novikov.rfid.DatabaseConnector import DatabaseConnector
from com.novikov.rfid.Settings import Settings
from com.novikov.rfid.UserModel import UserModel
from com.novikov.rfid.AccessLevel import AccessLevel
from com.novikov.rfid.VisitsLogger import VisitsLogger
from com.novikov.rfid import __version__


__author__ = 'Ilia Novikov'

APPLICATION_LOG = 'application.log'

"""

    Очистка логов
    Очистка БД
    Логи в БД (?)
    Специальный режим ведения логов

"""


class Main:
    def __init__(self):
        logging.basicConfig(format='%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s',
                            level=logging.DEBUG,
                            filename=APPLICATION_LOG)
        self.dialog = Dialog(dialog='dialog')
        self.visits_logger = VisitsLogger()
        with open(APPLICATION_LOG, mode='a') as log:
            log.write('-------------------------------------------------- \n')
        logging.info("Приложение запущено, версия {}".format(__version__))
        if getuid() != 0:
            logging.error("Попытка запуска без прав root")
            self.dialog.msgbox("Необходим запуск с правами root! \n" +
                               "Работа завершена",
                               width=0,
                               height=0)
            exit(0)
        self.settings = Settings()
        if self.settings.is_first_run:
            if not self.create_settings():
                logging.error("Ошибка при создании настроек приложения!")
                self.dialog.msgbox("Настройки не были сохранены! \n" +
                                   "Работа завершена",
                                   width=0,
                                   height=0)
                exit(0)
        try:
            credentials = None
            if self.settings.get_db_option(Settings.DB_USER):
                logging.info("Запрос пароля к БД")
                code, password = self.dialog.passwordbox(
                    "Пароль для доступа к БД".format(self.settings.get_db_option(Settings.DB_USER)),
                    width=0,
                    height=0,
                    insecure=True)
                if code != Dialog.OK:
                    logging.error("Пароль к БД не был введен!")
                    self.dialog.msgbox("Пароль к БД не введен! \n" +
                                       "Работа завершена",
                                       width=0,
                                       height=0)
                    exit(0)
                credentials = {
                    'user': self.settings.get_db_option(Settings.DB_USER),
                    'password': password
                }
            self.db = DatabaseConnector(self.settings.get_db_option(Settings.DB_HOST),
                                        int(self.settings.get_db_option(Settings.DB_PORT)),
                                        self.settings.get_db_option(Settings.DB_NAME),
                                        self.settings.get_db_option(Settings.DB_COLLECTION),
                                        credentials)
        except PyMongoError as e:
            logging.error("Ошибка входа с текущими настройками подключения к БД!")
            logging.error("Ошибка: {}".format(e))
            self.dialog.msgbox("Ошибка входа с текущими настройками подключения к БД \n" +
                               "Работа завершена",
                               width=0,
                               height=0)
            exit(0)
        if not self.db.has_users():
            logging.info("Пользователи не найдены, будет создан аккаунт разработчика")
            if not self.add_developer():
                logging.error("Ошибка при создании пользователя!")
                self.dialog.msgbox("Пользователь не был создан! \n" +
                                   "Работа завершена",
                                   width=0,
                                   height=0)
                exit(0)
        self.operator = None
        """ :type : UserModel """
        self.was_unlocked = False
        self.is_waiting_card = False
        CardReader(self).start()
        self.standard_mode()

    # region Создание пользователей

    def add_developer(self):
        self.dialog.set_background_title("Добавление разработчика")
        code, name = self.dialog.inputbox("Введите имя нового пользователя:",
                                          width=0,
                                          height=0,
                                          init="Иван Петров")
        if code != Dialog.OK:
            return False

        code, card_id = self.request_card("Приложите карту разработчика")
        if code != Dialog.OK:
            return False
        code, raw_date = self.dialog.calendar("Введите дату окончания действия аккаунта:",
                                              width=0,
                                              height=0,
                                              day=1,
                                              month=1,
                                              year=2020)
        if code != Dialog.OK:
            return False
        expire = datetime(day=raw_date[0], month=raw_date[1], year=raw_date[2])
        user = UserModel(creator=name,
                         card_id=card_id,
                         name=name,
                         access=AccessLevel.developer,
                         expire=expire)
        self.db.add_user(user)
        self.dialog.set_background_title("Пользователь создан")
        self.show_user_info(user)
        return True

    def add_user(self):
        self.dialog.set_background_title("Добавление пользователя")
        code, name = self.dialog.inputbox("Введите имя нового пользователя:",
                                          width=0,
                                          height=0,
                                          init="Иван Петров")
        if code != Dialog.OK:
            return
        code, card_id = self.request_card("Приложите карту нового пользователя...")
        if code != Dialog.OK:
            return
        if self.db.get_user(card_id):
            self.dialog.msgbox("Ошибка: данная карта уже зарегистрирована",
                               width=0,
                               height=0)
            return
        choices = [AccessLevel.guest, AccessLevel.common, AccessLevel.privileged]
        if self.operator.access == AccessLevel.developer:
            choices.append(AccessLevel.developer)
        code, tag = self.dialog.radiolist("Выберите уровень доступа:",
                                          width=0,
                                          height=0,
                                          choices=[(str(choices.index(x) + 1), str(x), choices.index(x) == 0) for x in
                                                   choices])
        if code != Dialog.OK:
            return
        access = AccessLevel(int(tag) - 1)
        code, raw_date = self.dialog.calendar("Введите дату окончания действия аккаунта:",
                                              width=0,
                                              height=0,
                                              day=1,
                                              month=1,
                                              year=2020)
        if code != Dialog.OK:
            return
        expire = datetime(day=raw_date[0], month=raw_date[1], year=raw_date[2])
        user = UserModel(creator=self.operator.name,
                         card_id=card_id,
                         name=name,
                         access=access,
                         expire=expire)
        self.db.add_user(user)
        self.dialog.set_background_title("Пользователь создан")
        self.show_user_info(user)

    def add_guest(self):
        self.dialog.set_background_title("Добавление гостя")
        code, name = self.dialog.inputbox("Введите имя гостя:",
                                          width=0,
                                          height=0,
                                          init="Иван Петров")
        if code != Dialog.OK:
            return
        code, card_id = self.request_card("Приложите карту гостя...")
        if code != Dialog.OK:
            return
        if self.db.get_user(card_id):
            self.dialog.msgbox("Ошибка: данная карта уже зарегистрирована",
                               width=0,
                               height=0)
            return
        access = AccessLevel.guest
        tomorrow = date.today() + timedelta(days=1)
        expire = datetime(tomorrow.year, tomorrow.month, tomorrow.day)
        user = UserModel(creator=self.operator.name,
                         card_id=card_id,
                         name=name,
                         access=access,
                         expire=expire)
        self.db.add_user(user)
        self.dialog.set_background_title("Гость создан")
        self.show_user_info(user)

    # endregion

    # region Работа с пользователями

    def create_settings(self):
        logging.info("Создание файла настроек")
        self.dialog.msgbox("Будет создан файл настроек",
                           width=0,
                           height=0)
        code, values = self.dialog.form("Настройка базы данных",
                                        width=0,
                                        height=0,
                                        elements=[
                                            ("Хост:", 1, 1, 'localhost', 1, len("Пользователь БД:") + 2, 20, 20),
                                            ("Порт:", 2, 1, '27017', 2, len("Пользователь БД:") + 2, 20, 20),
                                            ("Пользователь БД:", 3, 1, '', 3, len("Пользователь БД:") + 2, 20, 20),
                                            ("База:", 4, 1, 'rfid', 4, len("Пользователь БД:") + 2, 20, 20),
                                            ("Коллекция:", 5, 1, 'rlab', 5, len("Пользователь БД:") + 2, 20, 20)
                                        ])
        if code != Dialog.OK:
            return False
        self.settings.set_db_option(Settings.DB_HOST, values[0])
        self.settings.set_db_option(Settings.DB_PORT, values[1])
        self.settings.set_db_option(Settings.DB_USER, values[2])
        self.settings.set_db_option(Settings.DB_NAME, values[3])
        self.settings.set_db_option(Settings.DB_COLLECTION, values[4])
        if self.settings.get_db_option(Settings.DB_USER):
            code, password = self.dialog.passwordbox(
                "Пароль для доступа к БД",
                width=0,
                height=0,
                insecure=True)
            if code != Dialog.OK:
                return False
            DatabaseConnector.add_db_admin(
                self.settings.get_db_option(Settings.DB_HOST),
                int(self.settings.get_db_option(Settings.DB_PORT)),
                self.settings.get_db_option(Settings.DB_NAME),
                {
                    'user': self.settings.get_db_option(Settings.DB_USER),
                    'password': password
                })
        code, values = self.dialog.form("Задержка (в секундах)",
                                        width=0,
                                        height=0,
                                        elements=[
                                            ("При успехе:", 1, 1, '5', 1, len("При успехе:") + 2, 20, 20),
                                            ("При ошибке:", 2, 1, '2', 2, len("При успехе:") + 2, 20, 20)
                                        ])
        if code != Dialog.OK:
            return False
        self.settings.set_delay_option(Settings.DELAY_SUCCESS, values[0])
        self.settings.set_delay_option(Settings.DELAY_ERROR, values[1])
        code, value = self.dialog.inputbox("Путь к адаптеру UART",
                                           width=0,
                                           height=0)
        if code != Dialog.OK:
            return False
        self.settings.set_uart_path(value)
        self.settings.save()
        return True

    def create_password(self):
        logging.info("Попытка смены пароля пользователем {} с правами доступа {}".format(
            self.operator.name,
            str(self.operator.access)))
        self.dialog.msgbox("Вам необходимо задать пароль учетной записи",
                           width=0,
                           height=0)
        code, password = self.dialog.passwordbox("Пароль:",
                                                 width=0,
                                                 height=0,
                                                 title="Новый пароль",
                                                 insecure=True)
        if code != Dialog.OK:
            return False
        code, password_reply = self.dialog.passwordbox("Пароль:",
                                                       width=0,
                                                       height=0,
                                                       title="Подтверждение пароля",
                                                       insecure=True)
        if code != Dialog.OK:
            return False
        if password_reply != password:
            code = self.dialog.yesno("Пароли не совпадают \n" +
                                     "Повторить попытку?",
                                     width=0,
                                     height=0)
            if code == Dialog.OK:
                self.create_password()
            else:
                return False
        self.operator.update_password(password)
        self.db.update_user(self.operator)
        logging.info("Пароль пользователя {} с правами доступа {} изменен".format(
            self.operator.name,
            str(self.operator.access)))
        return True

    def show_user_info(self, user):
        info = ("Имя: {} \n" +
                "Уровень доступа: {} \n" +
                "Истекает: {} \n" +
                "Пароль: {}").format(
            user.name,
            str(user.access),
            user.expire,
            'установлен'
            if user.has_password() else
            'отсутствует')
        self.dialog.msgbox(info,
                           width=0,
                           height=0)

    def edit_all_users(self):
        users = self.db.get_all_users()
        code, tag = self.dialog.menu("Выберите пользователя",
                                     width=0,
                                     height=0,
                                     choices=[(str(users.index(x) + 1), x.name) for x in users])
        if code != Dialog.OK:
            return
        user = users[int(tag) - 1]
        toggle_active_message = "Заблокировать" if user.active else "Снять блокировку"
        actions = [
            {'name': "Просмотреть информацию", 'action': lambda x: self.show_user_info(x)},
            {'name': toggle_active_message, 'action': lambda x: self.toggle_user(x)},
            {'name': "Удалить пользователя", 'action': lambda x: self.delete_user(x)}
        ]
        code, tag = self.dialog.menu("Выберите действие",
                                     width=0,
                                     height=0,
                                     choices=[(str(actions.index(x) + 1), x['name']) for x in actions])
        if code != Dialog.OK:
            return
        actions[int(tag) - 1]['action'](user)
        self.edit_all_users()

    def delete_user(self, user: UserModel):
        code = self.dialog.yesno("Вы уверены?",
                                 width=0,
                                 height=0)
        if code == Dialog.OK:
            self.db.remove_user(user, self.operator.name)

    def toggle_user(self, user):
        if self.operator.access.value < user.access.value:
            self.dialog.msgbox("Недостаточно прав для блокировки {}. Необходим уровень доступа {}"
                               .format(user.name, AccessLevel.developer),
                               width=0,
                               height=0)
            return
        code = self.dialog.yesno("Вы уверены?",
                                 width=0,
                                 height=0)
        if code == Dialog.OK:
            user.active = not user.active
            self.db.update_user(user)

    # endregion

    # region Режимы работы

    def standard_mode(self):
        while True:
            self.dialog.set_background_title("Рабочий режим")

            code, card_id = self.request_card("Приложите карту...")
            if code == Dialog.OK:
                self.operator = self.db.get_user(card_id)
                if not self.operator:
                    self.visits_logger.wrong_id(card_id)
                    self.dialog.infobox("Карта отклонена! \n" +
                                        "Запись добавлена в лог",
                                        width=0,
                                        height=0)
                    sleep(self.settings.get_delay_option(Settings.DELAY_ERROR))
                elif not self.operator.active:
                    self.visits_logger.inactive_card(self.operator)
                    self.dialog.infobox("Карта заблокирована! \n" +
                                        "Запись добавлена в лог",
                                        width=0,
                                        height=0)
                    sleep(self.settings.get_delay_option(Settings.DELAY_ERROR))
                elif datetime.now() >= self.operator.expire:
                    self.visits_logger.inactive_card(self.operator)
                    self.dialog.infobox("Карта устарела! \n" +
                                        "Запись добавлена в лог",
                                        width=0,
                                        height=0)
                    sleep(self.settings.get_delay_option(Settings.DELAY_ERROR))
                else:
                    self.visits_logger.visit(self.operator)
                    code = self.dialog.pause("Авторизация успешна \n" +
                                             "Пользователь: {} \n".format(self.operator.name) +
                                             "Уровень доступа: {} \n".format(str(self.operator.access)),
                                             seconds=self.settings.get_delay_option(Settings.DELAY_SUCCESS),
                                             title="ОК",
                                             extra_button=True,
                                             extra_label="Консоль")
                    if code == Dialog.EXTRA:
                        self.show_control_window()
                    # Opening the door
                    pass
            if code == Dialog.ESC or code == Dialog.CANCEL:
                logging.info("Попытка завершить программу из основного режима")

    def lock_mode(self):
        self.dialog.set_background_title("Установлена блокировка")
        while True:
            code, card_id = self.request_card("Приложите карту повышенного доступа")
            if code == Dialog.OK:
                self.operator = self.db.get_user(card_id)
                if not self.operator:
                    self.dialog.infobox("Карта отклонена! \n" +
                                        "Запись добавлена в лог",
                                        width=0,
                                        height=0)
                    self.visits_logger.wrong_id(card_id)
                    sleep(self.settings.get_delay_option(Settings.DELAY_ERROR))
                elif not self.operator.active:
                    self.visits_logger.inactive_card(self.operator)
                    self.dialog.infobox("Карта заблокирована! \n" +
                                        "Запись добавлена в лог",
                                        width=0,
                                        height=0)
                    sleep(self.settings.get_delay_option(Settings.DELAY_ERROR))
                elif datetime.now() >= self.operator.expire:
                    self.visits_logger.inactive_card(self.operator)
                    self.dialog.infobox("Карта устарела! \n" +
                                        "Запись добавлена в лог",
                                        width=0,
                                        height=0)
                    sleep(self.settings.get_delay_option(Settings.DELAY_ERROR))
                elif self.operator.access.value <= AccessLevel.common.value:
                    self.dialog.infobox("Низкий уровень доступа! \n" +
                                        "Запись добавлена в лог",
                                        width=0,
                                        height=0)
                    self.visits_logger.wrong_access(self.operator)
                    sleep(self.settings.get_delay_option(Settings.DELAY_ERROR))
                else:
                    code = self.dialog.pause("Блокировка снята \n" +
                                             "Пользователь: {} \n".format(self.operator.name) +
                                             "Уровень доступа: {} \n".format(str(self.operator.access)),
                                             seconds=self.settings.get_delay_option(Settings.DELAY_SUCCESS),
                                             title="ОК",
                                             extra_button=True,
                                             extra_label="Консоль")
                    self.visits_logger.visit(self.operator)
                    if code == Dialog.EXTRA:
                        self.show_control_window()
                    # Opening the door
                    pass
                    return
            if code == Dialog.ESC or code == Dialog.CANCEL:
                logging.info("Попытка завершить программу из защищенного режима")

    def lock(self):
        code = self.dialog.yesno("Вы уверены? \n",
                                 width=0,
                                 height=0)
        if code != Dialog.OK:
            return
        self.lock_mode()
        self.was_unlocked = True

    # endregion

    def show_control_window(self, should_check=True):
        logging.info("Пользователь {} с правами доступа '{}' пытается получить доступ к консоли управления".format(
            self.operator.name,
            str(self.operator.access)
        ))
        self.dialog.set_background_title("Консоль управления")
        if should_check:
            if not self.operator.has_password():
                logging.info("Пользователь {} с правами доступа '{}' создает новый пароль".format(
                    self.operator.name,
                    str(self.operator.access)
                ))
                if not self.create_password():
                    return
            else:
                code, password = self.dialog.passwordbox("Пароль:",
                                                         width=0,
                                                         height=0,
                                                         title="Подтверждение доступа",
                                                         insecure=True)
                if code != Dialog.OK:
                    return
                if not self.operator.check_password(password):
                    logging.info("Пользователь {} с правами доступа '{}' неверно ввел пароль".format(
                        self.operator.name,
                        str(self.operator.access)
                    ))
                    self.dialog.infobox("Неверное сочетание логина и пароля \n" +
                                        "Запись добавлена в лог",
                                        width=0,
                                        height=0)
                    self.visits_logger.wrong_password(self.operator)
                    sleep(self.settings.get_delay_option(Settings.DELAY_ERROR))
                    return
        choices = ["Просмотр сведений об учетной записи"]
        if self.operator.access.value >= AccessLevel.common.value:
            choices.extend([
                "Просмотр лога посещений",
                "Добавление гостя",
                "Изменение пароля"])
        if self.operator.access.value >= AccessLevel.privileged.value:
            choices.extend([
                "Добавление пользователя",
                "Редактирование пользователей",
                "Закрыть помещение",
                "Очистка лога посещений"])
        if self.operator.access.value >= AccessLevel.developer.value:
            choices.extend([
                "Ограничение ведения логов",
                "Просмотр системного лога",
                "Очистка системного лога",
                "Очистка БД",
                "Завершение программы"])
        code, tag = self.dialog.menu("Выберите действие",
                                     choices=[('{}'.format(choices.index(x) + 1), x) for x in choices])
        if code != Dialog.OK:
            return
        [
            lambda: self.show_user_info(self.operator),
            lambda: self.show_visits_log(),
            lambda: self.add_guest(),
            lambda: self.create_password(),
            lambda: self.add_user(),
            lambda: self.edit_all_users(),
            lambda: self.lock(),
            lambda: self.clean_visits_log(),
            lambda: self.set_visit_log_limitations(),
            lambda: self.show_app_log(),
            lambda: self.clean_app_log(),
            lambda: self.clean_db(),
            lambda: self.exit()
        ][int(tag) - 1]()
        if not self.was_unlocked:
            self.show_control_window(False)
        else:
            self.was_unlocked = True
            return

    def show_app_log(self):
        logging.info("Пользователь {} с правами доступа '{}' просматривает лог приложения".format(
            self.operator.name,
            str(self.operator.access)
        ))
        if path.exists(APPLICATION_LOG):
            self.dialog.textbox(APPLICATION_LOG,
                                width=0,
                                height=0)

    def show_visits_log(self):
        logging.info("Пользователь {} с правами доступа '{}' просматривает лог посещений".format(
            self.operator.name,
            str(self.operator.access)
        ))
        if path.exists(VisitsLogger.VISITS_LOG):
            self.dialog.textbox(VisitsLogger.VISITS_LOG,
                                width=0,
                                height=0)

    def request_card(self, title, message=''):
        self.is_waiting_card = True
        code, card_id = self.dialog.passwordbox(message,
                                                width=0,
                                                height=0,
                                                title=title)
        self.is_waiting_card = False
        if not card_id:
            code = Dialog.ESC
        return code, card_id

    def exit(self):
        logging.info("Разработчик завершил выполнение программы: {}".format(self.operator.name))
        exit(0)

    def clean_db(self):
        logging.info("Попытка очистки БД пользователем {}".format(self.operator))
        code = self.dialog.yesno("Вы уверены? Операция очистки БД необратима! \n" +
                                 "Программа будет завершена после очистки БД",
                                 width=0,
                                 height=0)
        if code != Dialog.OK:
            return
        code, password = self.dialog.passwordbox("Пароль:",
                                                 width=0,
                                                 height=0,
                                                 title="Подтверждение доступа",
                                                 insecure=True)
        if code != Dialog.OK:
            return
        if not self.operator.check_password(password):
            logging.info("Пользователь {} с правами доступа '{}' неверно ввел пароль".format(
                self.operator.name,
                str(self.operator.access)
            ))
            self.dialog.infobox("Неверное сочетание логина и пароля \n" +
                                "Запись добавлена в лог",
                                width=0,
                                height=0)
            self.visits_logger.wrong_password(self.operator)
            sleep(self.settings.get_delay_option(Settings.DELAY_ERROR))
            return
        self.db.drop_collection()
        self.db.drop_db_user(self.settings.get_db_option(Settings.DB_USER))
        if path.exists(APPLICATION_LOG):
            remove(APPLICATION_LOG)
        if path.exists(VisitsLogger.VISITS_LOG):
            remove(VisitsLogger.VISITS_LOG)
        if path.exists(Settings.FILENAME):
            remove(Settings.FILENAME)
        exit(0)

    def set_visit_log_limitations(self):
        pass

    def clean_app_log(self):
        if not path.exists(APPLICATION_LOG):
            return
        code = self.dialog.yesno("Вы уверены? \n" +
                                 "Программа будет завершена после очистки лога",
                                 width=0,
                                 height=0)
        if code != Dialog.OK:
            return
        remove(APPLICATION_LOG)
        exit(0)

    def clean_visits_log(self):
        if not path.exists(VisitsLogger.VISITS_LOG):
            return
        code = self.dialog.yesno("Вы уверены?",
                                 width=0,
                                 height=0)
        if code != Dialog.OK:
            return
        remove(VisitsLogger.VISITS_LOG)
        if self.operator.access.value < AccessLevel.developer.value:
            logging.info("Пользователь {} очистил лог посещений".format(self.operator.name))


signals = [{'orig': signal.signal(signal.SIGINT, signal.SIG_IGN), 'signal': signal.SIGINT},
           {'orig': signal.signal(signal.SIGQUIT, signal.SIG_IGN), 'signal': signal.SIGQUIT},
           {'orig': signal.signal(signal.SIGTSTP, signal.SIG_IGN), 'signal': signal.SIGTSTP}]

Main()

for s in signals:
    signal.signal(s['signal'], s['orig'])