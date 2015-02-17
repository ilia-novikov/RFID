#! /usr/bin/env python3

import logging
import logging.handlers
import subprocess
from time import sleep
from datetime import datetime, date, timedelta
import signal
from os import getuid, remove, path
import sys

from dialog import Dialog
from pymongo.errors import PyMongoError

from com.novikov.rfid.CardReader import CardReader
from com.novikov.rfid.DatabaseConnector import DatabaseConnector
from com.novikov.rfid.SerialConnector import SerialConnector
from com.novikov.rfid.Settings import Settings
from com.novikov.rfid.UserModel import UserModel
from com.novikov.rfid.AccessLevel import AccessLevel
from com.novikov.rfid.VisitsLogger import VisitsLogger
from com.novikov.rfid import __version__


__author__ = 'Ilia Novikov'

APPLICATION_LOG = 'application.log'


class Main:
    def __init__(self):
        logging.basicConfig(format='%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s',
                            level=logging.DEBUG,
                            filename=APPLICATION_LOG)
        self.logger = logging.getLogger('logger')
        rotating_handler = logging.handlers.RotatingFileHandler(APPLICATION_LOG,
                                                                maxBytes=1024 * 1024 * 2,
                                                                backupCount=10)
        self.logger.addHandler(rotating_handler)
        self.dialog = Dialog(dialog='dialog')
        self.visits_logger = VisitsLogger()
        self.debug = 'debug' in sys.argv
        with open(APPLICATION_LOG, mode='a') as log:
            log.write('-------------------------------------------------- \n')
        self.logger.info("Приложение запущено, версия {}".format(__version__))
        if getuid() != 0:
            self.logger.error("Попытка запуска без прав root")
            self.dialog.msgbox("Необходим запуск с правами root! \n" +
                               "Работа завершена",
                               width=0,
                               height=0)
            exit(0)
        if self.debug:
            self.logger.info("Запуск в отладочном режиме")
        self.settings = Settings()
        if self.settings.is_first_run:
            if not self.create_settings():
                self.logger.error("Ошибка при создании настроек приложения!")
                self.dialog.msgbox("Настройки не были сохранены! \n" +
                                   "Работа завершена",
                                   width=0,
                                   height=0)
                exit(0)
        try:
            credentials = None
            if self.settings.get_db_option(Settings.DB_USER):
                self.logger.info("Запрос пароля к БД")
                code, password = self.dialog.passwordbox(
                    "Пароль для доступа к БД".format(self.settings.get_db_option(Settings.DB_USER)),
                    width=0,
                    height=0,
                    insecure=True)
                if code != Dialog.OK or not password:
                    self.logger.error("Пароль к БД не был введен!")
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
            self.logger.error("Ошибка входа с текущими настройками подключения к БД: {}".format(e))
            self.dialog.msgbox("Ошибка входа с текущими настройками подключения к БД \n" +
                               "Работа завершена",
                               width=0,
                               height=0)
            exit(0)
        self.is_waiting_card = False
        if not self.debug:
            self.card_reader = CardReader(self)
            self.card_reader.start()
        if not self.db.has_users():
            self.logger.info("Пользователи не найдены, будет создан аккаунт разработчика")
            if not self.add_developer():
                self.logger.error("Ошибка при создании пользователя!")
                self.dialog.msgbox("Пользователь не был создан! \n" +
                                   "Работа завершена",
                                   width=0,
                                   height=0)
                exit(0)
        if not self.db.has_any_developer():
            self.logger.info("Будет создан аккаунт разработчика")
            self.dialog.msgbox("Необходимо создать аккаунт разработчика из имеющегося аккаунта администратора")
            administrators = [x for x in self.db.get_all_users() if x.access == AccessLevel.administrator]
            code, tag = self.dialog.radiolist("Выберите аккаунт",
                                              choices=[(str(administrators.index(x) + 1),
                                                        x.name,
                                                        administrators.index(x) == 0)
                                                       for x in administrators],
                                              width=0,
                                              height=0)
            if code != Dialog.OK:
                self.logger.error("Ошибка при выборе разработчика!")
                self.dialog.msgbox("Разработчик не был выбран! \n" +
                                   "Работа завершена",
                                   width=0,
                                   height=0)
                exit(0)
            tag = int(tag) - 1
            user = administrators[tag]
            card_id = self.request_card("Подтвердите выбор картой пользователя {}...".format(
                user.name
            ))
            if card_id not in user.cards:
                self.logger.error("Ошибка при подтверждении разработчика!")
                self.dialog.msgbox("Выбор не был подтвержден! \n" +
                                   "Работа завершена",
                                   width=0,
                                   height=0)
                exit(0)
            user.access = AccessLevel.developer
            self.db.update_user(user)
            self.logger.info("Пользователь {} был выбран разработчиком")
            self.dialog.msgbox("Разработчик успешно выбран")
        self.operator = None
        """ :type : UserModel """
        self.serial = SerialConnector(self.settings.get_uart_path(), 9600)
        self.was_unlocked = False
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

        card_id = self.request_card("Приложите карту разработчика")
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
                         cards=[card_id],
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
        card_id = self.request_card("Приложите карту нового пользователя...")
        if self.db.get_user(card_id):
            self.dialog.msgbox("Ошибка: данная карта уже зарегистрирована",
                               width=0,
                               height=0)
            return
        choices = [AccessLevel.guest, AccessLevel.common]
        if self.operator.access.value >= AccessLevel.administrator.value:
            choices.append(AccessLevel.privileged)
            choices.append(AccessLevel.administrator)
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
                         cards=[card_id],
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
        card_id = self.request_card("Приложите карту гостя...")
        if self.db.get_user(card_id):
            self.dialog.msgbox("Ошибка: данная карта уже зарегистрирована",
                               width=0,
                               height=0)
            return
        access = AccessLevel.guest
        tomorrow = date.today() + timedelta(days=1)
        expire = datetime(tomorrow.year, tomorrow.month, tomorrow.day)
        user = UserModel(creator=self.operator.name,
                         cards=[card_id],
                         name=name,
                         access=access,
                         expire=expire)
        self.db.add_user(user)
        self.dialog.set_background_title("Гость создан")
        self.show_user_info(user)

    # endregion

    # region Работа с пользователями

    def create_settings(self):
        self.logger.info("Создание файла настроек")
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
        self.logger.info("Попытка смены пароля пользователем {} с правами доступа {}".format(
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
        self.logger.info("Пароль пользователя {} с правами доступа {} изменен".format(
            self.operator.name,
            str(self.operator.access)))
        return True

    def show_user_info(self, user):
        info = ("Имя: {} \n" +
                "Уровень доступа: {} \n" +
                "Привязано карт: {} \n" +
                "Истекает: {} \n" +
                "Пароль: {}").format(
            user.name,
            str(user.access),
            str(len(user.cards)),
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
        if user.access == AccessLevel.developer and user.cards != self.operator.cards:
            self.dialog.msgbox("Прямое редактирование пользователя запрещено",
                               width=0,
                               height=0)
            self.edit_all_users()
            return
        toggle_active_message = "Заблокировать" if user.active else "Снять блокировку"
        actions = [
            {'name': "Просмотреть информацию", 'action': lambda x: self.show_user_info(x)},
            {'name': "Изменить имя", 'action': lambda x: self.change_name(x)},
            {'name': "Изменить уровень доступа", 'action': lambda x: self.change_access_level(x)},
            {'name': "Карты", 'action': lambda x: self.list_cards(x)},
            {'name': "Добавить карту", 'action': lambda x: self.add_card(x)},
            {'name': "Удалить карту", 'action': lambda x: self.remove_card(x)},
            {'name': "Сбросить пароль", 'action': lambda x: self.reset_password(x)},
            {'name': "Объединить", 'action': lambda x: self.merge_user(x)},
            {'name': toggle_active_message, 'action': lambda x: self.toggle_user(x)},
            {'name': "Удалить пользователя", 'action': lambda x: self.delete_user(x)}
        ]
        code, tag = self.dialog.menu("Выберите действие",
                                     choices=[(str(actions.index(x) + 1), x['name']) for x in actions],
                                     width=0,
                                     height=0)
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
        code = self.dialog.yesno("Вы уверены?",
                                 width=0,
                                 height=0)
        if code == Dialog.OK:
            user.active = not user.active
            self.db.update_user(user)

    def reset_password(self, user: UserModel):
        code = self.dialog.yesno("Вы уверены?",
                                 width=0,
                                 height=0)
        if code != Dialog.OK:
            return
        self.logger.info("Пользователь {} с правами доступа {} сбросил пароль {} ({})".format(
            self.operator.name,
            str(self.operator.access),
            user.name,
            str(user.access)
        ))
        user.reset_password()
        self.db.update_user(user)
        self.dialog.msgbox("Пароль пользователя сброшен".format(
            user.name
        ))

    def remove_card(self, user: UserModel):
        if len(user.cards) == 1:
            self.dialog.msgbox("Невозможно удалить единственную карту",
                               width=0,
                               height=0)
            return
        code, tag = self.dialog.menu("Выберите карту",
                                     choices=[(str(user.cards.index(x) + 1), x) for x in user.cards],
                                     width=0,
                                     height=0)
        if code != Dialog.OK:
            return
        card = user.cards[int(tag) - 1]
        code = self.dialog.yesno("Отвязать карту {}?".format(card),
                                 width=0,
                                 height=0)
        if code != Dialog.OK:
            return
        self.logger.info("Пользователь {} с правами доступа {} отвязал карту {} пользователя {}".format(
            self.operator.name,
            str(self.operator.access),
            card,
            user.name
        ))
        user.cards.remove(card)
        self.db.update_user(user)
        self.dialog.msgbox("Карта отвязана",
                           width=0,
                           height=0)

    def add_card(self, user: UserModel):
        card_id = self.request_card("Приложите новую карту...")
        if self.db.get_user(card_id):
            self.dialog.msgbox("Ошибка: данная карта уже зарегистрирована",
                               width=0,
                               height=0)
            return
        self.logger.info("Пользователь {} с правами доступа {} привязал карту {} для пользователя {}".format(
            self.operator.name,
            str(self.operator.access),
            card_id,
            user.name
        ))
        user.cards.append(card_id)
        self.db.update_user(user)
        self.dialog.msgbox("Карта привязана",
                           width=0,
                           height=0)

    def list_cards(self, user: UserModel):
        self.dialog.menu("Карты пользователя",
                         choices=[(str(user.cards.index(x) + 1), x) for x in user.cards],
                         width=0,
                         height=0)

        # endregion

    def merge_user(self, user: UserModel):
        users = [x for x in self.db.get_all_users() if x.cards != user.cards]
        code, tag = self.dialog.radiolist("Выберите аккаунт",
                                          choices=[(str(users.index(x) + 1),
                                                    x.name,
                                                    users.index(x) == 0)
                                                   for x in users],
                                          width=0,
                                          height=0)
        if code != Dialog.OK:
            return
        tag = int(tag) - 1
        merged = users[tag]
        if user.access != merged.access:
            self.dialog.msgbox("Невозможно объединить пользователей с разным уровнем доступа!")
            return
        code, name = self.dialog.inputbox("Имя объединенного аккаунта",
                                          width=0,
                                          height=0)
        if code != Dialog.OK:
            return
        user.name = name
        user.cards.extend(merged.cards)
        self.db.update_user(user)
        self.db.remove_user(merged, self.operator.name)
        self.logger.info("Пользователь {} с правами доступа {} объединил {} и {}".format(
            self.operator.name,
            str(self.operator.access),
            user.name,
            merged.name
        ))

    # region Режимы работы

    def standard_mode(self):
        while True:
            self.serial.standard()
            self.dialog.set_background_title("Рабочий режим")
            card_id = self.request_card("Приложите карту...")
            self.operator = self.db.get_user(card_id)
            if not self.operator:
                self.serial.error()
                self.visits_logger.wrong_id(card_id)
                self.dialog.infobox("Карта отклонена! \n" +
                                    "Запись добавлена в лог",
                                    width=0,
                                    height=0)
                sleep(self.settings.get_delay_option(Settings.DELAY_ERROR))
            elif not self.operator.active:
                self.serial.error()
                self.visits_logger.inactive_card(self.operator)
                self.dialog.infobox("Карта заблокирована! \n" +
                                    "Запись добавлена в лог",
                                    width=0,
                                    height=0)
                sleep(self.settings.get_delay_option(Settings.DELAY_ERROR))
            elif datetime.now() >= self.operator.expire:
                self.serial.error()
                self.visits_logger.inactive_card(self.operator)
                self.dialog.infobox("Карта устарела! \n" +
                                    "Запись добавлена в лог",
                                    width=0,
                                    height=0)
                sleep(self.settings.get_delay_option(Settings.DELAY_ERROR))
            else:
                self.serial.open()
                self.visits_logger.visit(self.operator)
                code = self.dialog.pause("Авторизация успешна \n" +
                                         "Пользователь: {} \n".format(self.operator.name) +
                                         "Уровень доступа: {} \n".format(str(self.operator.access)),
                                         seconds=self.settings.get_delay_option(Settings.DELAY_SUCCESS),
                                         title="ОК",
                                         extra_button=True,
                                         extra_label="Консоль")
                if code == Dialog.EXTRA:
                    self.serial.maintenance()
                    self.show_control_window()

    def lock_mode(self):
        self.dialog.set_background_title("Установлена блокировка")
        while True:
            self.serial.lock()
            card_id = self.request_card("Приложите карту повышенного доступа")
            self.operator = self.db.get_user(card_id)
            if not self.operator:
                self.serial.error()
                self.dialog.infobox("Карта отклонена! \n" +
                                    "Запись добавлена в лог",
                                    width=0,
                                    height=0)
                self.visits_logger.wrong_id(card_id)
                sleep(self.settings.get_delay_option(Settings.DELAY_ERROR))
            elif not self.operator.active:
                self.serial.error()
                self.visits_logger.inactive_card(self.operator)
                self.dialog.infobox("Карта заблокирована! \n" +
                                    "Запись добавлена в лог",
                                    width=0,
                                    height=0)
                sleep(self.settings.get_delay_option(Settings.DELAY_ERROR))
            elif datetime.now() >= self.operator.expire:
                self.serial.error()
                self.visits_logger.inactive_card(self.operator)
                self.dialog.infobox("Карта устарела! \n" +
                                    "Запись добавлена в лог",
                                    width=0,
                                    height=0)
                sleep(self.settings.get_delay_option(Settings.DELAY_ERROR))
            elif self.operator.access.value <= AccessLevel.common.value:
                self.serial.error()
                self.dialog.infobox("Низкий уровень доступа! \n" +
                                    "Запись добавлена в лог",
                                    width=0,
                                    height=0)
                self.visits_logger.wrong_access(self.operator)
                sleep(self.settings.get_delay_option(Settings.DELAY_ERROR))
            else:
                self.serial.open()
                code = self.dialog.pause("Блокировка снята \n" +
                                         "Пользователь: {} \n".format(self.operator.name) +
                                         "Уровень доступа: {} \n".format(str(self.operator.access)),
                                         seconds=self.settings.get_delay_option(Settings.DELAY_SUCCESS),
                                         title="ОК",
                                         extra_button=True,
                                         extra_label="Консоль")
                self.visits_logger.visit(self.operator)
                if code == Dialog.EXTRA:
                    self.serial.maintenance()
                    self.show_control_window()
                return

    def lock(self):
        code = self.dialog.yesno("Вы уверены? \n",
                                 width=0,
                                 height=0)
        if code != Dialog.OK:
            return
        self.lock_mode()
        self.was_unlocked = True

    # endregion

    # region Консоль

    def show_control_window(self, should_check=True):
        self.logger.info("Пользователь {} с правами доступа '{}' пытается получить доступ к консоли управления".format(
            self.operator.name,
            str(self.operator.access)
        ))
        self.dialog.set_background_title("Консоль управления")
        if should_check:
            if not self.operator.has_password():
                self.logger.info("Пользователь {} с правами доступа '{}' создает новый пароль".format(
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
                    self.logger.info("Пользователь {} с правами доступа '{}' неверно ввел пароль".format(
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
        choices = [
            "Просмотр сведений об учетной записи",
            "Изменение пароля"]
        if self.operator.access.value >= AccessLevel.common.value:
            choices.extend([
                "Просмотр лога посещений",
                "Добавление гостя"])
        if self.operator.access.value >= AccessLevel.privileged.value:
            choices.extend([
                "Добавление пользователя",
                "Закрытие помещения"])
        if self.operator.access.value >= AccessLevel.administrator.value:
            choices.extend([
                "Редактирование пользователей",
                "Просмотр системного лога",
                "Очистка лога посещений"])

        if self.operator.access == AccessLevel.developer:
            choices.extend([
                "Просмотр ночного лога",
                "Очистка системного лога",
                "Очистка ночного лога",
                "Очистка настроек и БД",
                "Запуск командной оболочки",
                "Завершение программы"])
        code, tag = self.dialog.menu("Выберите действие",
                                     choices=[('{}'.format(choices.index(x) + 1), x) for x in choices])
        if code != Dialog.OK:
            return
        [
            lambda: self.show_user_info(self.operator),
            lambda: self.create_password(),
            lambda: self.show_visits_log(),
            lambda: self.add_guest(),
            lambda: self.add_user(),
            lambda: self.lock(),
            lambda: self.edit_all_users(),
            lambda: self.show_app_log(),
            lambda: self.clean_visits_log(),
            lambda: self.show_illegal_log(),
            lambda: self.clean_app_log(),
            lambda: self.clean_illegal_log(),
            lambda: self.clean_db(),
            lambda: self.run_bash(),
            lambda: self.exit()
        ][int(tag) - 1]()
        if not self.was_unlocked:
            self.show_control_window(False)
        else:
            self.was_unlocked = True
            return

    def show_app_log(self):
        self.logger.info("Пользователь {} с правами доступа '{}' просматривает лог приложения".format(
            self.operator.name,
            str(self.operator.access)
        ))
        if path.exists(APPLICATION_LOG):
            self.dialog.textbox(APPLICATION_LOG,
                                width=0,
                                height=0)

    def show_visits_log(self):
        self.logger.info("Пользователь {} с правами доступа '{}' просматривает лог посещений".format(
            self.operator.name,
            str(self.operator.access)
        ))
        if path.exists(VisitsLogger.VISITS_LOG):
            self.dialog.textbox(VisitsLogger.VISITS_LOG,
                                width=0,
                                height=0)

    def clean_db(self):
        self.logger.info("Попытка очистки БД пользователем {}".format(self.operator))
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
            self.logger.info("Пользователь {} с правами доступа '{}' неверно ввел пароль".format(
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
            self.logger.info("Пользователь {} очистил лог посещений".format(self.operator.name))

    # endregion

    def exit(self):
        self.logger.info("Разработчик завершил выполнение программы: {}".format(self.operator.name))
        exit(1)

    def request_card(self, title):
        if self.debug:
            code, result = None, None
            while not result or code != Dialog.OK:
                code, result = self.dialog.inputbox("Приложите карту (ОТЛАДКА)",
                                                    width=0,
                                                    height=0)
            return result
        self.is_waiting_card = True
        self.dialog.infobox(title,
                            width=0,
                            height=0)
        while not self.card_reader.card_id:
            self.dialog.infobox(title,
                                width=0,
                                height=0)
            sleep(100.0 / 1000.0)
        self.is_waiting_card = False
        card_id = self.card_reader.card_id
        self.card_reader.card_id = ''
        return card_id

    @staticmethod
    def run_bash():
        subprocess.call('bash')

    def change_name(self, user: UserModel):
        code, result = self.dialog.inputbox("Введите новое имя",
                                            width=0,
                                            height=0)
        if code != Dialog.OK or not result:
            return
        self.logger.info("Пользователь {} с уровнем доступа {} изменил имя {} на {}".format(
            self.operator.name,
            str(self.operator.access),
            user.name,
            result
        ))
        user.name = result
        self.db.update_user(user)
        self.dialog.msgbox("Имя было изменено",
                           width=0,
                           height=0)

    def change_access_level(self, user: UserModel):
        choices = [AccessLevel.guest, AccessLevel.common, AccessLevel.administrator]
        if self.operator.access == AccessLevel.developer:
            choices.append(AccessLevel.developer)
        code, tag = self.dialog.radiolist("Выберите уровень доступа:",
                                          width=0,
                                          height=0,
                                          choices=[(str(choices.index(x) + 1), str(x), user.access == x) for x in
                                                   choices])
        if code != Dialog.OK:
            return
        tag = int(tag) - 1
        if choices[tag] == user.access:
            self.dialog.msgbox("Уровень доступа не был изменен",
                               width=0,
                               height=0)
            return
        message = "Это действие расширит права пользователя!" \
            if user.access.value < choices[tag].value else \
            "Это действие урежет права пользователя!"
        message += "\nВы уверены?"
        code = self.dialog.yesno(message,
                                 width=0,
                                 height=0)
        if code != Dialog.OK:
            return
        self.logger.info("Пользователь {} с уровнем доступа {} изменил уровень доступа {} на {}".format(
            self.operator.name,
            str(self.operator.access),
            user.name,
            str(choices[tag])))
        user.access = choices[tag]
        self.db.update_user(user)
        self.dialog.msgbox("Уровень доступа был изменен",
                           width=0,
                           height=0)

    def clean_illegal_log(self):
        if not path.exists(VisitsLogger.ILLEGAL_LOG):
            return
        code = self.dialog.yesno("Вы уверены?",
                                 width=0,
                                 height=0)
        if code != Dialog.OK:
            return
        remove(VisitsLogger.ILLEGAL_LOG)

    def show_illegal_log(self):
        if path.exists(VisitsLogger.ILLEGAL_LOG):
            self.dialog.textbox(VisitsLogger.ILLEGAL_LOG,
                                width=0,
                                height=0)


signals = [{'orig': signal.signal(signal.SIGINT, signal.SIG_IGN), 'signal': signal.SIGINT},
           {'orig': signal.signal(signal.SIGQUIT, signal.SIG_IGN), 'signal': signal.SIGQUIT},
           {'orig': signal.signal(signal.SIGTSTP, signal.SIG_IGN), 'signal': signal.SIGTSTP}]

Main()

for s in signals:
    signal.signal(s['signal'], s['orig'])