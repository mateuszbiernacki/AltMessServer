from flask import Flask, jsonify, request
import secrets
import sqlite3
import datetime
import hashlib
import _smtp

PATH_TO_USERS_DATABASE = 'altmess.db'

app = Flask(__name__)
messages = {}

@app.route('/about')
def version():
    response = {
        'author': 'Mateusz Biernacki',
        'version': '0.1'
    }
    return jsonify(response)


@app.route('/test/random_token')
def test_token():
    response = {
        'token': secrets.token_hex(64)
    }
    return jsonify(response)


@app.route('/register', methods=['POST'])
def register():
    reg_query = "insert into users(login, password, email) values (?, ?, ?)"
    login = request.json["login"]
    password = hashlib.sha256(request.json["password"].encode()).hexdigest()
    mail = request.json["mail"]
    database_connection = sqlite3.connect(PATH_TO_USERS_DATABASE)
    cursor = database_connection.cursor()
    try:
        cursor.execute(reg_query, (login, password, mail))
    except sqlite3.IntegrityError as e:
        if 'login' in f'{e}':
            return jsonify({'r': 'Login is use.'})
        if 'mail' in f'{e}':
            return jsonify({'r': 'Mail is use.'})
        return jsonify({'r': 'Bad input data.'})
    database_connection.commit()
    database_connection.close()
    for login in logged_users:
        add_message(login, {'type': 'new', 'r': 'ok'})
    response = {
        'r': "ok"
    }
    return jsonify(response)


# u_id, token
logged_users = {}


@app.route('/login', methods=['POST'])
def log_in():
    query = 'select password from users where login=:login'
    try:
        login = request.json["login"]
        password = hashlib.sha256(request.json["password"].encode()).hexdigest()
        database_connection = sqlite3.connect(PATH_TO_USERS_DATABASE)
        cursor = database_connection.cursor()
        row = cursor.execute(query, {'login': login}).fetchone()
        if not row:
            return jsonify({'r': 'Wrong login.'})
        elif row[0] == password:
            token = secrets.token_hex(64)
            logged_users[login] = token
            database_connection.commit()
            database_connection.close()
            return jsonify({'r': 'ok', 'token': token})
        else:
            return jsonify({'r': 'Wrong password.'})
    except Exception as e:
        return jsonify({'r': f'{e}'})


@app.route('/logout', methods=['POST'])
def logout():
    try:
        login = request.json['login']
        token = request.json['token']
        if login not in logged_users:
            return jsonify({'r': 'Not logged.'})
        elif logged_users[login] == token:
            logged_users.pop(login)
            return jsonify({'r': 'ok.'})
        else:
            return jsonify({'r': 'Wrong token.'})
    except Exception as e:
        return jsonify({'r': f'{e}'})


@app.route('/list_of_users', methods=['POST'])
def get_list_of_users():
    try:
        login = request.json['login']
        token = request.json['token']
        if login not in logged_users:
            return jsonify({'r': 'Not logged.'})
        elif logged_users[login] == token:
            query = 'select login from users'
            db_con = sqlite3.connect(PATH_TO_USERS_DATABASE)
            cursor = db_con.cursor()
            rows = cursor.execute(query)
            if not rows:
                return jsonify({})
            response = []
            for row in rows:
                response.append(row[0])
            db_con.close()
            return jsonify({
                "r": 'ok',
                'users': response
            })
        else:
            return jsonify({'r': 'Wrong token.'})
    except Exception as e:
        return jsonify({'r': f'{e}'})


messages = {}


@app.route('/send_dm', methods=['POST'])
def send_dm():
    # try:
    login = request.json['login']
    token = request.json['token']
    to = request.json['to']
    content = request.json['content']
    db_con = sqlite3.connect(PATH_TO_USERS_DATABASE)
    cursor = db_con.cursor()
    if login not in logged_users:
        return jsonify({'r': 'Not logged.'})
    row = cursor.execute('select login from users where login=:login', {'login': to}).fetchone()
    if to not in row:
        return jsonify({'r': 'User not exist.'})
    elif logged_users[login] == token:
        uid_from = cursor.execute('select u_id from users where login=:login', {'login': login}).fetchone()[0]
        uid_to = cursor.execute('select u_id from users where login=:login', {'login': to}).fetchone()[0]
        query = 'insert into dms(u_id_from, u_id_to, content, date) values (?, ?, ?, ?)'
        cursor.execute(query, (uid_from, uid_to, content, datetime.datetime.now()))
        db_con.commit()
        db_con.close()
        add_message(to, {'type': 'dm', 'from': login})
        return jsonify({'r': 'ok'})
    else:
        return jsonify({'r': 'Wrong token.'})
    # except Exception as e:
    #     return jsonify({'r': f'{e}'})


@app.route('/create_group', methods=['POST'])
def create_group():
    try:
        login = request.json['login']
        token = request.json['token']
        group_name = request.json['group_name']
        db_con = sqlite3.connect(PATH_TO_USERS_DATABASE)
        cursor = db_con.cursor()
        if login not in logged_users:
            return jsonify({'r': 'Not logged.'})
        elif logged_users[login] == token:
            uid = cursor.execute('select u_id from users where login=:login', {'login': login}).fetchone()[0]
            query = 'insert into groups(group_name, creator_u_id) values (?, ?)'
            cursor.execute(query, (group_name, uid))
            query = 'select * from groups order by g_id desc'
            cursor.execute(query)
            data = cursor.fetchone()
            query = 'insert into groups_members(u_id, g_id) values (?, ?)'
            cursor.execute(query, (data[2], data[0]))
            db_con.commit()
            db_con.close()
            for login in logged_users:
                add_message(login, {'type': 'new', 'r': 'ok'})
            return jsonify({'r': 'ok'})
        else:
            return jsonify({'r': 'Wrong token.'})
    except Exception as e:
        return jsonify({'r': f'{e}'})


@app.route('/list_of_group', methods=['POST'])
def get_list_of_group():
    try:
        login = request.json['login']
        token = request.json['token']
        if login not in logged_users:
            return jsonify({'r': 'Not logged.'})
        elif logged_users[login] == token:
            query = 'select * from groups'
            db_con = sqlite3.connect(PATH_TO_USERS_DATABASE)
            cursor = db_con.cursor()
            rows = cursor.execute(query)
            if not rows:
                return jsonify({})
            all_groups = rows.fetchall()
            query = 'select g_id from groups_members where u_id=:u_id'
            rows = cursor.execute(query, {'u_id': get_uid(login)})
            groups = set()
            for row in rows:
                groups.add(row[0])
            groups_ids = list(groups)
            groups = []
            for group in all_groups:
                if group[0] in groups_ids:
                    groups.append(group)
            return jsonify({'r': 'ok',
                            'groups': groups})
        else:
            return jsonify({'r': 'Wrong token.'})
    except Exception as e:
        return jsonify({'r': f'{e}'})


@app.route('/invite_to_group', methods=['POST'])
def invite_to_group():
    try:
        login = request.json['login']
        token = request.json['token']
        gid = request.json['group_id']
        invitees = request.json['invitees']
        if login not in logged_users:
            return jsonify({'r': 'Not logged.'})
        elif logged_users[login] == token:
            uid = get_uid(login)
            db_con = sqlite3.connect(PATH_TO_USERS_DATABASE)
            cursor = db_con.cursor()
            if uid == cursor.execute('select creator_u_id from groups where g_id=:g_id', {'g_id': gid}).fetchone()[0] \
                    or cursor.execute('select * from groups_members where u_id=:u_id and g_id=:g_id', {
                'u_id': uid,
                'g_id': gid
            }).fetchone() is not None:

                users = []
                for usr in cursor.execute('select login from users').fetchall():
                    users.append(usr[0])
                if not users:
                    return jsonify({'r': '0 users'})
                if not set(invitees).issubset(set(users)):
                    return jsonify({'r': 'Wrong friend login.'})
                for member in invitees:
                    uid = cursor.execute('select u_id from users where login=:login', {'login': member}).fetchone()[0]
                    cursor.execute('insert into groups_members(u_id, g_id) values (?, ?)', (uid, gid))
            else:
                return jsonify({'r': 'Not in group.'})
            db_con.commit()
            db_con.close()
            return jsonify({'r': 'ok'})
        else:
            return jsonify({'r': 'Wrong token.'})
    except Exception as e:
        return jsonify({'r': f'{e}'})


@app.route('/list_of_group_members', methods=['POST'])
def get_list_of_group_members():
    try:
        login = request.json['login']
        token = request.json['token']
        gid = request.json['group_id']
        if login not in logged_users:
            return jsonify({'r': 'Not logged.'})
        elif logged_users[login] == token:
            query = 'select u_id from groups_members where g_id=:g_id'
            db_con = sqlite3.connect(PATH_TO_USERS_DATABASE)
            cursor = db_con.cursor()
            rows = cursor.execute(query, {'g_id': gid})
            if not rows:
                return jsonify({})
            logins = []
            for row in rows.fetchall():
                logins.append(get_login(row[0]))
            logins = set(logins)
            logins = list(logins)
            return jsonify(logins)
        else:
            return jsonify({'r': 'Wrong token.'})
    except Exception as e:
        return jsonify({'r': f'{e}'})


@app.route('/leave_group', methods=['POST'])
def leave_group():
    try:
        login = request.json['login']
        token = request.json['token']
        g_id = request.json['group_id']
        db_con = sqlite3.connect(PATH_TO_USERS_DATABASE)
        cursor = db_con.cursor()
        if login not in logged_users:
            return jsonify({'r': 'Not logged.'})
        elif logged_users[login] == token:
            uid = get_uid(login)
            query = 'delete from groups_members where u_id=:u_id and g_id=:g_id'
            cursor.execute(query, {
                'u_id': uid,
                'g_id': g_id
            })
            db_con.commit()
            db_con.close()
            return jsonify({'r': 'ok'})
        else:
            return jsonify({'r': 'Wrong token.'})
    except Exception as e:
        return jsonify({'r': f'{e}'})


@app.route('/send_gm', methods=['POST'])
def send_gm():
    try:
        login = request.json['login']
        token = request.json['token']
        g_id = request.json['group_id']
        content = request.json['content']
        db_con = sqlite3.connect(PATH_TO_USERS_DATABASE)
        cursor = db_con.cursor()
        if login not in logged_users:
            return jsonify({'r': 'Not logged.'})
        row = cursor.execute('select * from groups_members where u_id=:u_id and g_id=:g_id', {
            'g_id': g_id,
            'u_id': get_uid(login)
        }).fetchone()
        if not row:
            return jsonify({'r': 'Wrong group.'})
        elif logged_users[login] == token:
            uid_from = get_uid(login)
            query = 'insert into gms(u_id, g_id, content, date) values (?, ?, ?, ?)'
            cursor.execute(query, (uid_from, g_id, content, datetime.datetime.now()))
            query = 'select u_id from groups_members where g_id=:g_id'
            rows = cursor.execute(query, {'g_id': g_id})
            if not rows:
                return jsonify({})
            logins = []
            for row in rows.fetchall():
                logins.append(get_login(row[0]))
            logins = set(logins)
            logins = list(logins)
            logins.remove(login)
            for to in logins:
                add_message(to, {'type': 'gm', 'group': g_id, 'from': login})
            db_con.commit()
            db_con.close()
            return jsonify({'r': 'ok'})
        else:
            return jsonify({'r': 'Wrong token.'})
    except Exception as e:
        return jsonify({'r': f'{e}'})


@app.route('/get_dms', methods=['POST'])
def get_dms():
    try:
        login = request.json['login']
        token = request.json['token']
        friend = request.json['friend']
        db_con = sqlite3.connect(PATH_TO_USERS_DATABASE)
        cursor = db_con.cursor()
        if login not in logged_users:
            return jsonify({'r': 'Not logged.'})
        row = cursor.execute('select * from users where u_id=:u_id', {
            'u_id': get_uid(friend)
        }).fetchone()
        if not row:
            return jsonify({'r': 'Wrong friend login.'})
        elif logged_users[login] == token:
            uid = get_uid(login)

            friend_id = get_uid(friend)
            query = 'select u_id_from, content, date from dms where (u_id_from=:u_id1 and u_id_to=:u_id2) ' \
                    'or (u_id_from=:u_id2 and u_id_to=:u_id1)'
            rows = cursor.execute(query, {
                'u_id1': uid,
                'u_id2': friend_id
            })

            temp_history = rows.fetchall()
            history = []
            db_con.commit()
            db_con.close()
            for e in temp_history:
                tup = [get_login(e[0]), e[1], e[2]]
                history.append(tup)
            return jsonify({'r': 'ok', 'history': history})
        else:
            return jsonify({'r': 'Wrong token.'})
    except Exception as e:
        return jsonify({'r': f'{e}'})


@app.route('/get_gms', methods=['POST'])
def get_gms():
    try:
        login = request.json['login']
        token = request.json['token']
        g_id = request.json['group_id']
        db_con = sqlite3.connect(PATH_TO_USERS_DATABASE)
        cursor = db_con.cursor()
        if login not in logged_users:
            return jsonify({'r': 'Not logged.'})
        row = cursor.execute('select * from groups_members where u_id=:u_id and g_id=:g_id', {
            'u_id': get_uid(login),
            'g_id': g_id
        }).fetchone()
        if not row:
            return jsonify({'r': 'Wrong group.'})
        elif logged_users[login] == token:
            uid = get_uid(login)
            query = 'select u_id, content, date from gms where g_id=:g_id'
            rows = cursor.execute(query, {
                'g_id': g_id
            })
            temp_history = rows.fetchall()
            history = []
            db_con.commit()
            db_con.close()
            for e in temp_history:
                tup = [get_login(e[0]), e[1], e[2]]
                history.append(tup)
            return jsonify({'r': 'ok', 'history': history})
        else:
            return jsonify({'r': 'Wrong token.'})
    except Exception as e:
        return jsonify({'r': f'{e}'})


@app.route('/test_mail')
def test_mail():
    _smtp.send_email(to='mateuszbiernacki@icloud.com', subject='test', message='test')


codes_to_change_pass = {}


@app.route('/forgot_password', methods=['POST'])
def forgot_pass():
    query = 'select login from users where login=:login'
    try:
        login = request.json["login"]
        database_connection = sqlite3.connect(PATH_TO_USERS_DATABASE)
        cursor = database_connection.cursor()
        row = cursor.execute(query, {'login': login}).fetchone()
        if not row:
            return jsonify({'r': 'Wrong login.'})
        else:
            codes_to_change_pass[login] = secrets.token_hex(6)
            _smtp.send_email(to=cursor.execute('select email from users where login=:login', ({'login': login}))
                             .fetchone()[0], subject='Code to change password', message=codes_to_change_pass[login])
            return jsonify({'r': 'ok'})
    except Exception as e:
        return jsonify({'r': f'{e}'})


@app.route('/change_password', methods=['POST'])
def change_pass():
    query = 'select login from users where login=:login'
    try:
        login = request.json["login"]
        code = request.json['code']
        password = hashlib.sha256(request.json["new_password"].encode()).hexdigest()
        database_connection = sqlite3.connect(PATH_TO_USERS_DATABASE)
        cursor = database_connection.cursor()
        row = cursor.execute(query, {'login': login}).fetchone()
        if not row:
            return jsonify({'r': 'Wrong login.'})
        else:
            if login not in codes_to_change_pass:
                return jsonify({'r': 'Wrong code.'})
            elif code == codes_to_change_pass[login]:
                cursor.execute('update users set password=:password where login=:login', {
                    'password': password,
                    'login': login
                })
                database_connection.commit()
                database_connection.close()
                return jsonify({'r': 'ok'})
            else:
                return jsonify({'r': 'Wrong code.'})
    except Exception as e:
        return jsonify({'r': f'{e}'})


@app.route('/get_message', methods=['POST'])
def get_message_():
    try:
        login = request.json['login']
        token = request.json['token']
        if login not in logged_users:
            return jsonify({'r': 'Not logged.'})
        elif logged_users[login] == token:
            return jsonify({"mess": get_message(login),
                            "r": "ok"
                            })
        else:
            return jsonify({'r': 'Wrong token.'})
    except Exception as e:
        return jsonify({'r': f'{e}'})


@app.route('/list_of_created_group')
def list_of_created_group():
    try:
        login = request.json['login']
        token = request.json['token']
        if login not in logged_users:
            return jsonify({'r': 'Not logged.'})
        elif logged_users[login] == token:
            db_con = sqlite3.connect(PATH_TO_USERS_DATABASE)
            cursor = db_con.cursor()
            rows = cursor.execute('select * from groups where creator_u_id=:uid', {'uid': get_uid(login)})
            return jsonify({'r': 'ok', 'groups': rows.fetchall()})
        else:
            return jsonify({'r': 'Wrong token.'})
    except Exception as e:
        return jsonify({'r': f'{e}'})


def get_uid(login):
    db_con = sqlite3.connect(PATH_TO_USERS_DATABASE)
    cursor = db_con.cursor()
    return cursor.execute('select u_id from users where login=:login', {'login': login}).fetchone()[0]


def get_login(uid):
    db_con = sqlite3.connect(PATH_TO_USERS_DATABASE)
    cursor = db_con.cursor()
    return cursor.execute('select login from users where u_id=:u_id', {'u_id': uid}).fetchone()[0]


def add_message(login, content):
    if login not in messages:
        messages[login] = []
    messages[login].append(content)


def get_message(login):
    print(messages)
    if login not in messages or messages[login] == []:
        return {'type': 'cl'}
    else:
        return messages[login].pop()


if __name__ == '__main__':
    app.run(ssl_context=('cert.pem', 'key.pem'), port=443)
