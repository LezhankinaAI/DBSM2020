import requests
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
import pyodbc
from transliterate import translit
import json

GROUPID = 201084201

def show_clients_orders(cursor, vk, user_id):
    # Показать все заказы клиента
    message = 'Your orders:\n'
    cursor.execute(f'SELECT id FROM EA_client WHERE id = \'{user_id}\'')
    is_in_database = ''
    for i in cursor:
        is_in_database = i[0]
    if not is_in_database:
        vk.messages.send(peer_id=user_id, random_id=get_random_id(),
                         message='You don\'t have any orders')
    else:
        cursor.execute(f'SELECT * FROM EA_order WHERE client_id = {user_id}')
        ans = cursor.fetchall()
        if ans == []:
            vk.messages.send(peer_id=user_id, random_id=get_random_id(),
                             message='You don\'t have any orders')
        else:
            cursor.execute(f'SELECT c.name, o.order_id, fl.type, fl.color, fb.id_bouquet, fb.num_flowers FROM EA_client c '
                           f'JOIN EA_order o ON c.id = o.client_id '
                           f'JOIN EA_order_bouquet ob ON o.order_id = ob.id_order '
                           f'JOIN EA_flower_bouquet fb ON ob.id_bouquet = fb.id_bouquet '
                           f'JOIN EA_flower fl ON fb.id_flower = fl.id '
                           f'WHERE c.id = {user_id}'
                           f'ORDER BY o.order_id')
            ans = cursor.fetchall()
            message += 'Name: ' + str(ans[0][0])
            order = ''
            bouquet = ''
            i = 0
            cnt = 1
            while i != len(ans):
                if str(ans[i][1]) != order:
                    message += '\n'
                    cnt = 1
                    order = str(ans[i][1])
                    message += '\nOrder id: ' + order + '\n'
                if str(ans[i][3]) != bouquet:
                    bouquet = str(ans[i][4])
                    message += 'Flowers  in bouquet №' + str(cnt) + ':\n'
                    cnt += 1
                while i != len(ans) and str(ans[i][1] == order) and str(ans[i][4]) == bouquet:
                    message += '' + str(ans[i][2]) + ' ' + str(ans[i][3]) + ' (' + str(ans[i][5]) + ' pieces)\n'
                    i += 1
            vk.messages.send(peer_id=user_id, random_id=get_random_id(),
                             message=message)

def update_state(cursor, conn, user_id, state):
    cursor.execute(f'UPDATE EA_client SET state = \'{state}\' WHERE id = {user_id}')
    conn.commit()

def main():
    def main_menu(user_id):
        vk.messages.send(peer_id=user_id, random_id=get_random_id(), keyboard=functions_keyboard.get_keyboard(), message='Choose option')

    # Подключение к азуру
    connection_string = "Driver={ODBC Driver 17 for SQL Server};" \
                        "Server;" \
                        "Database;" \
                        "uid;pwd"
    conn = pyodbc.connect(connection_string)
    cursor = conn.cursor()

    # Получение апи
    vk_session = vk_api.VkApi(
        token='')
    longpoll = VkBotLongPoll(vk_session, GROUPID)
    vk = vk_session.get_api()

    # Главное меню
    functions_keyboard = VkKeyboard(one_time=True)
    functions_keyboard.add_button('Make an order', color=VkKeyboardColor.POSITIVE, payload={'type': 'make_order'})
    functions_keyboard.add_line()
    functions_keyboard.add_button('Flower price list', color=VkKeyboardColor.SECONDARY, payload={"type": "show_flower_prices"})
    functions_keyboard.add_button('Show flowers (for mobile)', color=VkKeyboardColor.SECONDARY, payload={"type": "show_flowers"})
    functions_keyboard.add_line()
    functions_keyboard.add_button('Order status', color=VkKeyboardColor.SECONDARY, payload={"type": "show_order_state"})
    functions_keyboard.add_button('My orders', color=VkKeyboardColor.SECONDARY, payload={"type": "show_my_orders"})
    # Список всех типов цветочков в базе и их цветов.
    # В формате {'Hrysanthemum': ['pink', 'white', 'yellow'], 'Hydrangea': ['blue', 'pink', 'white']}
    all_ftype = {}
    cursor.execute(f'SELECT DISTINCT type FROM EA_flower')
    for ft in cursor:
        all_ftype[ft[0]] = []
    for ft in all_ftype:
        cursor.execute(f'SELECT DISTINCT color FROM EA_flower WHERE type = \'{ft}\'')
        for i in cursor:
            all_ftype[f'{ft}'].append(i[0])


    # Слушаем действия пользователя
    for event in longpoll.listen():
        # Проверить есть ли клиент в базе. Если нет, то внести со статусом start
        user_id = event.message.from_id
        cursor.execute(f'SELECT id FROM EA_client WHERE id = \'{user_id}\'')
        is_in_database = ''
        for i in cursor:
            is_in_database = i[0]
        if not is_in_database:
            user_get = vk.users.get(user_ids=(user_id))[0]
            name = user_get['first_name'] + user_get['last_name']
            name = translit(name, "ru", reversed=True)
            name = ''.join(filter(str.isalnum, name))
            cursor.execute(f'INSERT INTO EA_client VALUES (NULL, NULL, \'{name}\', {user_id}, \'start\')')
            conn.commit()
        # Достаем состояние клиента
        cursor.execute(f'SELECT state FROM EA_client WHERE id = {user_id}')
        client_state = ''
        for i in cursor:
            client_state = i[0]

        # Смотрим в каком статусе сейчас клиент
        if client_state == 'start':
            vk.messages.send(peer_id=user_id, random_id=get_random_id(), message=f'Hello!\nI am happy to see you.\nHow can I help you?')
            update_state(cursor, conn, user_id, 'main_menu')
            main_menu(user_id)
        elif client_state == 'input_order_number':
            if not event.message.text.isdigit():
                vk.messages.send(peer_id=user_id, random_id=get_random_id(),
                                 message='This number is incorrect.')
                main_menu(user_id)
                update_state(cursor, conn, user_id, 'main_menu')
            else:
                order_number = event.message.text
                cursor.execute(f'SELECT order_status FROM EA_order '
                               f'JOIN EA_client ON EA_client.id = EA_order.client_id '
                               f'WHERE client_id = {user_id} AND order_id = {order_number}')
                status = ''
                for i in cursor:
                    status = i[0]
                if status == '':
                    vk.messages.send(peer_id=user_id, random_id=get_random_id(),
                                     message='There is no such order in the database')
                    main_menu(user_id)
                    update_state(cursor, conn, user_id, 'main_menu')
                else:
                    vk.messages.send(peer_id=user_id, random_id=get_random_id(),
                                     message=f'Status of your order: {status}')
                    main_menu(user_id)
                    update_state(cursor, conn, user_id, 'main_menu')
        elif client_state == 'checking_price':
            typef = str(event.message.text)
            types = []
            cursor.execute(f'SELECT DISTINCT type FROM EA_flower')
            for row in cursor:
                types.append(str(row[0]))
            if typef not in types:
                vk.messages.send(
                    peer_id=user_id,
                    random_id=get_random_id(),
                    message='The flower type is incorrect. Try again'
                )
                update_state(cursor, conn, user_id, 'main_menu')
                main_menu(user_id)
            else:
                cursor.execute(f'SELECT color, price, image, product FROM EA_flower '
                               f'WHERE type = \'{typef}\'')
                message = typef + ':\n\n'
                crsl = {"type": "carousel", "elements": []}
                for row in cursor:
                    photo = str(row[2])
                    text = typef + ' ' + str(row[0])
                    descr = str(row[1]) + '₽\n'
                    link = str(row[3])
                    crsl["elements"].append({"title": text, "description": descr,
                                             "photo_id": photo, "action": {"type": "open_photo"},
                                             "buttons": [
                                                 {"action": {"type": "open_link", "link": link, "label": "Buy"}}]})
                vk.messages.send(peer_id=user_id, random_id=get_random_id(),
                                 template=json.dumps(crsl), message=message)
                update_state(cursor, conn, user_id, 'main_menu')
                main_menu(user_id)
        elif client_state == 'main_menu':
            if event.message.text == 'My orders':
                show_clients_orders(cursor, vk, user_id)
                main_menu(user_id)
            elif event.message.text == 'Flower price list':
                message = 'Flower price list:\n\n'
                cursor.execute(f'SELECT type, color, price FROM EA_flower')
                for row in cursor:
                    message += str(row[0]) + ' ' + str(row[1]) + ', ' + str(row[2]) + '₽\n'
                vk.messages.send(peer_id=user_id, random_id=get_random_id(),
                                 message=message)
                main_menu(user_id)
            elif event.message.text == 'Show flowers (for mobile)':
                vk.messages.send(peer_id=user_id, random_id=get_random_id(), message='Enter the type of the flower from the list:')
                cursor.execute(f'SELECT DISTINCT type FROM EA_flower')
                message = ''
                for row in cursor:
                    message += str(row[0]) + '\n'
                vk.messages.send(peer_id=user_id, random_id=get_random_id(), message=message)
                update_state(cursor, conn, user_id, 'checking_price')
            elif event.message.text == 'Order status':
                vk.messages.send(peer_id=user_id, random_id=get_random_id(), message='Enter your order number:')
                update_state(cursor, conn, user_id, 'input_order_number')
            elif event.message.text == 'Make an order':
                # Add new order to DataBase for client
                order_id = 0
                cursor.execute('SELECT max(order_id) FROM EA_order')
                for i in cursor:
                    order_id = i[0] + 1
                bouquet_id = 0
                cursor.execute('SELECT max(id) FROM EA_bouquet')
                for i in cursor:
                    bouquet_id = i[0] + 1
                cursor.execute(f'INSERT INTO EA_order VALUES ({order_id}, '
                               f'\'making\', \'not paid\', \'2020-12-18\', 0, \'unknown\', \'pick up\', {user_id})')
                cursor.execute(f'INSERT INTO EA_bouquet VALUES ({bouquet_id}, 0, NULL)')
                cursor.execute(f'INSERT INTO EA_order_bouquet VALUES ({order_id}, {bouquet_id}, 1)')
                conn.commit()

                # Show keyboard
                update_state(cursor, conn, user_id, 'choose_ftype')
                flower_keyboard = VkKeyboard(one_time=True)
                i = 0
                for flower in all_ftype:
                    flower_keyboard.add_button(flower, color=VkKeyboardColor.SECONDARY)
                    if i != len(all_ftype)-1:
                        flower_keyboard.add_line()
                    i += 1
                vk.messages.send(peer_id=user_id, random_id=get_random_id(),
                                 keyboard=flower_keyboard.get_keyboard(),
                                 message='Choose flower to add')
            else:
                vk.messages.send(
                    peer_id=user_id,
                    random_id=get_random_id(),
                    keyboard=functions_keyboard.get_keyboard(),
                    message='There is no such option. Choose one of the suggested:'
                )
        elif client_state == 'choose_ftype':
            ftype = event.message.text
            if ftype not in all_ftype:
                flower_keyboard = VkKeyboard(one_time=True)
                for flower in all_ftype:
                    flower_keyboard.add_button(flower, color=VkKeyboardColor.SECONDARY)
                    if flower != list(all_ftype.keys())[-1]:
                        flower_keyboard.add_line()
                vk.messages.send(peer_id=user_id, random_id=get_random_id(),
                                 keyboard=flower_keyboard.get_keyboard(),
                                 message='There is no such flower. Choose flower to add:')
            else:
                cursor.execute(f'INSERT INTO EA_flower_bouquet '
                               f'VALUES ((SELECT max(id) FROM EA_flower WHERE type = \'{ftype}\'), '
                               f'        (SELECT max(id_bouquet) FROM EA_order_bouquet '
                               f'        WHERE id_order = (SELECT max(order_id) FROM EA_order '
                               f'                          WHERE client_id = {user_id})),'
                               f'        0)')
                conn.commit()
                fcolor_keyboard = VkKeyboard(one_time=True)
                for fcolor in all_ftype[f'{ftype}']:
                    if fcolor == 'null':
                        continue
                    fcolor_keyboard.add_button(fcolor, color=VkKeyboardColor.SECONDARY)
                    if fcolor != all_ftype[f'{ftype}'][-1]:
                        fcolor_keyboard.add_line()
                vk.messages.send(peer_id=user_id, random_id=get_random_id(),
                                 keyboard=fcolor_keyboard.get_keyboard(),
                                 message='Choose flower color:')
                update_state(cursor, conn, user_id, 'choose_fcolor')
        elif client_state == 'choose_fcolor':
            fcolor = event.message.text
            cursor.execute(f'SELECT EA_flower.type FROM EA_flower '
                           f'WHERE id = (SELECT id_flower FROM EA_flower_bouquet'
                           f'            WHERE id_bouquet = (SELECT max(id_bouquet) FROM EA_order_bouquet'
                           f'                                WHERE id_order = (SELECT max(order_id) FROM EA_order'
                           f'                                                  WHERE client_id = {user_id}))'
                           f'                                 AND num_flowers = 0)')
            ft = ''
            for i in cursor:
                ft = i[0]
            if fcolor not in all_ftype[f'{ft}']:
                fcolor_keyboard = VkKeyboard(one_time=True)
                for fc in all_ftype[f'{ft}']:
                    if fc == 'null':
                        continue
                    fcolor_keyboard.add_button(fc, color=VkKeyboardColor.SECONDARY)
                    if fc != all_ftype[f'{ft}'][-1]:
                        fcolor_keyboard.add_line()
                vk.messages.send(peer_id=user_id, random_id=get_random_id(),
                                 keyboard=fcolor_keyboard.get_keyboard(),
                                 message=f'This is no such {ft} color. Choose another color:')
            else:
                cursor.execute(f'SELECT DISTINCT in_stock FROM EA_flower WHERE type = \'{ft}\' AND color = \'{fcolor}\'')
                in_stock = 0
                for i in cursor:
                    in_stock = i[0]
                if not in_stock:
                    fcolor_keyboard = VkKeyboard(one_time=True)
                    for fc in all_ftype[f'{ft}']:
                        fcolor_keyboard.add_button(fc, color=VkKeyboardColor.SECONDARY)
                        if fc != all_ftype[f'{ft}'][-1]:
                            fcolor_keyboard.add_line()
                    vk.messages.send(peer_id=user_id, random_id=get_random_id(),
                                     keyboard=fcolor_keyboard.get_keyboard(),
                                     message=f'Sorry. There are not any {fcolor} {ft} in stock. Choose another color:')
                else:
                    cursor.execute(f'SELECT DISTINCT id FROM EA_flower WHERE type = \'{ft}\' AND color = \'{fcolor}\'')
                    color_id = 0
                    for i in cursor:
                        color_id = i[0]
                    cursor.execute(f'UPDATE EA_flower_bouquet SET id_flower = {color_id} '
                                   f'WHERE id_bouquet = (SELECT max(id_bouquet) FROM EA_order_bouquet '
                                   f'                    WHERE id_order = (SELECT max(order_id) FROM EA_order '
                                   f'                                      WHERE client_id = {user_id}))'
                                   f'AND num_flowers = 0')
                    conn.commit()
                    vk.messages.send(peer_id=user_id, random_id=get_random_id(), message=f'Enter count of {fcolor} {ft} (number from 1 to {in_stock})')
                    update_state(cursor,conn,user_id,'choose_fnum')
        elif client_state == 'choose_fnum':
            fnum = event.message.text
            if not fnum.isdigit() or int(fnum) < 1:
                vk.messages.send(peer_id=user_id, random_id=get_random_id(),
                                 message=f'This number is incorrect. Enter another one:')
            else:
                fnum = int(fnum)
                in_stock, ft, fc = 0, '', ''
                cursor.execute(f'SELECT EA_flower.type, color, in_stock FROM EA_flower '
                               f'WHERE id = (SELECT id_flower FROM EA_flower_bouquet '
                               f'            WHERE id_bouquet = (SELECT max(id_bouquet) FROM EA_order_bouquet '
                               f'                                WHERE id_order = (SELECT max(order_id) FROM EA_order'
                               f'                                                  WHERE client_id = {user_id})) '
                               f'            AND num_flowers = 0)')
                for i in cursor:
                    ft, fc, in_stock = i[0], i[1], i[2]
                if fnum > in_stock:
                    vk.messages.send(peer_id=user_id, random_id=get_random_id(),
                                     message=f'Sorry. We have not got this number of {fc} {ft}. Enter another number:')
                else:
                    cursor.execute(f'UPDATE EA_flower_bouquet SET num_flowers = {fnum} '
                                   f'WHERE id_bouquet = (SELECT max(id_bouquet) FROM EA_order_bouquet '
                                   f'                    WHERE id_order = (SELECT max(order_id) FROM EA_order '
                                   f'                                      WHERE client_id = {user_id})) '
                                   f'                    AND num_flowers = 0')
                    cursor.execute(f'UPDATE EA_flower SET in_stock = in_stock - {fnum} WHERE EA_flower.type = \'{ft}\' AND color = \'{fc}\' ')
                    fprice = 0
                    cursor.execute(f'SELECT DISTINCT price FROM EA_flower WHERE EA_flower.type=\'{ft}\' AND EA_flower.color=\'{fc}\'')
                    for i in cursor:
                        fprice = i[0]
                    cursor.execute(f'UPDATE EA_bouquet SET price = price + {fnum} * {fprice} '
                                   f'WHERE id = (SELECT max(id_bouquet) FROM EA_order_bouquet '
                                   f'            WHERE id_order = (SELECT max(order_id) FROM EA_order '
                                   f'                              WHERE client_id = {user_id}))')
                    conn.commit()
                    order = ''
                    # Здесь происходит вывод твоего текущего собираемого заказа. У меня неправильно сделан селект
                    # Надо сделать чтобы было еще деление по букетам. Сейчас он выбирает только один букет из заказа.
                    cursor.execute(f'SELECT ob.id_bouquet, id_flower, b.price AS bouquet_price, f.type, f.color, fb.num_flowers, f.price*fb.num_flowers FROM EA_order_bouquet AS ob '
                                   f'JOIN EA_bouquet AS b ON ob.id_bouquet=b.id '
                                   f'JOIN EA_flower_bouquet AS fb ON fb.id_bouquet=b.id '
                                   f'JOIN EA_flower AS f ON f.id=fb.id_flower '
                                   f'WHERE id_order = (SELECT max(order_id) FROM EA_order WHERE client_id = {user_id})'
                                   f'ORDER BY ob.id_bouquet')
                    bouquetid, nbouquet, order_sum = 0, 0, 0
                    for row in cursor:
                        if not nbouquet:
                            order += f'Bouquet №{nbouquet+1}\n'
                            bouquetid = row[0]
                            nbouquet += 2
                        elif bouquetid != row[0]:
                            order += f'Bouquet №{nbouquet}\n'
                            bouquetid = row[0]
                            nbouquet += 1
                        order += f'{row[3]} {row[4]} x{row[5]} ={row[6]}₽\n'
                        order_sum += row[6]
                    order += f'\nTotal {order_sum}₽\n'
                    update_state(cursor, conn, user_id, 'add_confirm_cancel')
                    add_conf_canc_keyboard = VkKeyboard(one_time=True)
                    add_conf_canc_keyboard.add_button('Confirm order', color=VkKeyboardColor.POSITIVE)
                    add_conf_canc_keyboard.add_line()
                    add_conf_canc_keyboard.add_button('Add more flowers', color=VkKeyboardColor.SECONDARY)
                    add_conf_canc_keyboard.add_line()
                    add_conf_canc_keyboard.add_button('Add more bouquet', color=VkKeyboardColor.SECONDARY)
                    add_conf_canc_keyboard.add_line()
                    add_conf_canc_keyboard.add_button('Cancel order', color=VkKeyboardColor.NEGATIVE)
                    vk.messages.send(
                        peer_id=user_id,
                        random_id=get_random_id(),
                        keyboard=add_conf_canc_keyboard.get_keyboard(),
                        message=f'Your order is\n{order}What do you want to do?'
                    )
        elif client_state == 'add_confirm_cancel':
            query = event.message.text
            if query == 'Confirm order':
                cursor.execute(f'UPDATE EA_order SET order_status = \'processing\' '
                               f'WHERE order_id = '
                               f'(SELECT DISTINCT id_order FROM EA_flower_bouquet '
                               f'JOIN EA_order_bouquet ON EA_order_bouquet.id_bouquet=EA_flower_bouquet.id_bouquet '
                               f'WHERE EA_flower_bouquet.id_bouquet = (SELECT max(id_bouquet) FROM EA_order_bouquet '
                               f'                                      WHERE id_order = (SELECT max(order_id) FROM EA_order '
                               f'                                                        WHERE client_id = {user_id})))')
                cursor.execute(f'UPDATE EA_order SET order_price = ('
                               f'   SELECT sum(EA_bouquet.price) FROM EA_order '
                               f'   JOIN EA_order_bouquet ON EA_order.order_id = EA_order_bouquet.id_order '
                               f'   JOIN EA_bouquet ON EA_order_bouquet.id_bouquet=EA_bouquet.id '
                               f'   WHERE id_order = (SELECT max(order_id) FROM EA_order WHERE client_id = {user_id})) '
                               f'WHERE order_id = (SELECT max(order_id) FROM EA_order WHERE client_id = {user_id})')
                conn.commit()
                vk.messages.send(
                    peer_id=user_id,
                    random_id=get_random_id(),
                    message=f'Thank you for order!\nOperator is going to contact you asap.'
                )
                update_state(cursor, conn, user_id, 'main_menu')
                main_menu(user_id)
                continue
            elif query == 'Add more flowers':
                update_state(cursor,conn,user_id,'choose_ftype')
                flower_keyboard = VkKeyboard(one_time=True)
                for flower in all_ftype:
                    flower_keyboard.add_button(flower, color=VkKeyboardColor.SECONDARY)
                    if flower != list(all_ftype.keys())[-1]:
                        flower_keyboard.add_line()
                vk.messages.send(peer_id=user_id, random_id=get_random_id(),
                                 keyboard=flower_keyboard.get_keyboard(),
                                 message='Choose flower to add:')
            elif query == 'Add more bouquet':
                # Добавляю новый букет в EA_order_bouquet, EA_bouquet, EA_flower_bouquet
                bouquet_id = 0
                cursor.execute('SELECT max(id) FROM EA_bouquet')
                for i in cursor:
                    bouquet_id = i[0] + 1
                order_id = 0
                cursor.execute(f'SELECT max(order_id) FROM EA_order WHERE client_id = {user_id}')
                for i in cursor:
                    order_id = i[0]
                bnum = 0
                cursor.execute(f'SELECT DISTINCT num_bouquets FROM EA_order_bouquet WHERE id_order = {order_id} ')
                for i in cursor:
                    bnum = i[0] + 1
                cursor.execute(f'UPDATE EA_order_bouquet SET num_bouquets = {bnum} WHERE id_order = {order_id}')
                cursor.execute(f'INSERT INTO EA_bouquet VALUES ({bouquet_id}, 0, NULL)')
                cursor.execute(f'INSERT INTO EA_order_bouquet VALUES ({order_id}, {bouquet_id}, {bnum})')
                conn.commit()
                # Показываю клавиатуру выбора цветка
                update_state(cursor, conn, user_id, 'choose_ftype')
                flower_keyboard = VkKeyboard(one_time=True)
                i = 0
                for flower in all_ftype:
                    flower_keyboard.add_button(flower, color=VkKeyboardColor.SECONDARY)
                    if i != len(all_ftype) - 1:
                        flower_keyboard.add_line()
                    i += 1
                vk.messages.send(peer_id=user_id, random_id=get_random_id(),
                                 keyboard=flower_keyboard.get_keyboard(),
                                 message='Choose flower to add')
            elif query == 'Cancel order':
                # Обратно добавить кол-во цветов в наличие
                cursor.execute(f'SELECT id_flower, fb.num_flowers FROM EA_order_bouquet AS ob '
                               f'JOIN EA_bouquet AS b ON ob.id_bouquet=b.id '
                               f'JOIN EA_flower_bouquet AS fb ON fb.id_bouquet=b.id '
                               f'JOIN EA_flower AS f ON f.id=fb.id_flower WHERE id_order = (SELECT max(order_id) FROM EA_order WHERE client_id = {user_id}) '
                               f'ORDER BY ob.id_bouquet')
                add_stock = cursor.fetchall()
                for r in add_stock:
                    cursor.execute(f'UPDATE EA_flower SET in_stock = in_stock + {r[1]} WHERE id = {r[0]}')
                    conn.commit()
                # Очистить максимальный заказ из всей БД (EA_order_bouquet, EA_flower_bouquet, EA_bouquet, EA_order)
                orderid = 0
                cursor.execute(f'SELECT max(order_id) FROM EA_order WHERE client_id={user_id}')
                for i in cursor:
                    orderid = i[0]
                bouquets = []
                cursor.execute(f'SELECT DISTINCT id_bouquet FROM EA_order_bouquet WHERE id_order = {orderid}')
                for i in cursor:
                    bouquets.append(i[0])
                cursor.execute(f'DELETE FROM EA_order_bouquet WHERE id_order = {orderid} '
                               f'DELETE FROM EA_order WHERE order_id = {orderid}')
                for b in bouquets:
                    cursor.execute(f'DELETE FROM EA_flower_bouquet WHERE id_bouquet = {b} '
                                   f'DELETE FROM EA_bouquet WHERE id = {b}')
                conn.commit()
                vk.messages.send(peer_id=user_id, random_id=get_random_id(), message=f'Okay, your order is canceled.')
                update_state(cursor,conn,user_id,'main_menu')
                main_menu(user_id)
                continue
            else:
                add_conf_canc_keyboard = VkKeyboard(one_time=True)
                add_conf_canc_keyboard.add_button('Confirm order', color=VkKeyboardColor.POSITIVE)
                add_conf_canc_keyboard.add_line()
                add_conf_canc_keyboard.add_button('Add more flowers', color=VkKeyboardColor.SECONDARY)
                add_conf_canc_keyboard.add_line()
                add_conf_canc_keyboard.add_button('Cancel order', color=VkKeyboardColor.NEGATIVE)
                vk.messages.send(
                    peer_id=user_id,
                    random_id=get_random_id(),
                    keyboard=add_conf_canc_keyboard.get_keyboard(),
                    message=f'You do not have this option. Choose one of these:'
                )

if __name__ == '__main__':
    try:
        main()
    except requests.exceptions.ReadTimeout:
        main()
    except Exception as err:
        print(err)
        exit(0)
