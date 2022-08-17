#!/usr/bin/env python
from datetime import datetime
from datetime import timedelta
import time
import requests
import mariadb
import os
from prettytable import PrettyTable

token = "nhT4TzFE5b0NO3YMiMUlXexfqJrK23CAyyHuQyDEdP3"
# token = "n"


def clear():
    # clears the screen on Linux system
    print("\033c")


def line_notify_message(line_token, msg):
    headers = {
        "Authorization": "Bearer " + line_token,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {'message': msg}
    try:
        r = requests.post("https://notify-api.line.me/api/notify", headers=headers, params=payload)
        return r.status_code
    except Exception as e:
        print(e)
        pass


def connect_to_mariadb():
    conn = mariadb.connect(
        user="root",
        password="jiou9618",
        host="localhost",
        port=3306,
        database="attendance"
    )
    return conn


def user_exists(conn, my_chip):
    cur = conn.cursor()
    sql = "SELECT userid FROM users WHERE chipno=?"
    par = (my_chip,)
    cur.execute(sql, par)
    if cur.fetchone():
        return bool(True)
    else:
        return bool(False)


def user_clocked(conn, my_chip):
    cur = conn.cursor()
    todays_date = datetime.now().strftime("%Y-%m-%d")
    sql = "SELECT userid FROM attendance INNER JOIN users USING(userid) WHERE clockout is NULL AND chipno=? AND " \
          "clockday =? "
    par = (my_chip, todays_date)
    cur.execute(sql, par)
    if cur.fetchone():
        return bool(True)
    else:
        return bool(False)


def user_at_work(conn, my_chip):
    cur = conn.cursor()
    sql = "SELECT userid FROM attendance INNER JOIN users USING(userid) WHERE chipno=? AND clockday=curdate()"
    par = (my_chip,)
    cur.execute(sql, par)
    if cur.fetchone():
        return bool(True)
    else:
        return bool(False)


def short_clock_in_time(conn, my_chip):
    cur = conn.cursor()
    todays_date = datetime.now().strftime("%Y-%m-%d")
    one_minutes_ago = datetime.now() - timedelta(minutes=1)
    sql = "SELECT clockin FROM attendance INNER JOIN users USING(userid) WHERE (clockout >= ? OR clockin >= ?) AND " \
          "chipno=? AND clockday =? "
    par = (one_minutes_ago.strftime("%H:%M"), one_minutes_ago.strftime("%H:%M"), my_chip, todays_date)
    cur.execute(sql, par)
    if cur.fetchone():
        return bool(True)
    else:
        return bool(False)


def attendance_come(conn, my_chip):
    if not short_clock_in_time(conn, my_chip):
        global token
        par = (my_chip,)
        come_time = datetime.now().strftime("%H:%M")
        today_8am = datetime.now().replace(hour=8, minute=0)
        todays_date = datetime.now().strftime("%Y-%m-%d")
        cur = conn.cursor()
        sql = "SELECT userid, name FROM users WHERE chipno = ?"
        cur.execute(sql, par)
        userid, name = cur.fetchone()
        sql = "INSERT INTO attendance(userid, username, clockday, clockin)" \
              "VALUES (?,?,?,?)"
        par = (userid, name, todays_date, come_time)
        cur.execute(sql, par)
        conn.commit()
        if today_8am < datetime.now():
            msg = name + " " + come_time + "上班"
            line_notify_message(token, msg)
    else:
        clear()
        print("已打卡了")


def attendance_go(conn, my_chip):
    if not short_clock_in_time(conn, my_chip):
        go_time = datetime.now().strftime("%H:%M")
        todays_date = datetime.now().strftime("%Y-%m-%d")

        # get userid and username from chip number
        cur = conn.cursor()
        sql = "SELECT userid, name FROM users WHERE chipno = ?"
        par = (my_chip,)
        cur.execute(sql, par)
        userid, name = cur.fetchone()

        sql = "UPDATE attendance SET clockout = ? WHERE userid = ? AND clockout is NULL AND clockday = ?"
        par = (go_time, userid, todays_date)
        cur.execute(sql, par)
        conn.commit()
        if datetime.now().replace(hour=17, minute=0) > datetime.now():
            msg = name + " " + go_time + "下班"
            line_notify_message(token, msg)
    else:
        clear()
        print("已打卡了")


def factory_notempty():
    conn = connect_to_mariadb()
    cur = conn.cursor()
    sql = "SELECT userid FROM attendance INNER JOIN users USING(userid) WHERE clockout is NULL AND clockday=curdate()"
    cur.execute(sql)
    if cur.fetchone():
        conn.close()
        return bool(True)
    else:
        conn.close()
        return bool(False)


def update_display():
    # clear display
    clear()

    # initiate Table
    mytable = PrettyTable()

    # connect to database and fetch data
    conn = connect_to_mariadb()
    cur = conn.cursor()
    sql = "SELECT name, chipno FROM users WHERE name <>'' ORDER BY name ASC"
    cur.execute(sql, )
    rows = cur.fetchall()

    # append to table row by row
    total_no_of_employees = len(rows)
    no_of_employees_work = 0
    for index, tuple in enumerate(rows):
        name = tuple[0]
        my_chip = tuple[1]
        if not user_at_work(conn, my_chip):
            mytable.add_row([name, "", ""])
        elif user_clocked(conn, my_chip):
            mytable.add_row(["", name + " " + clock_time(conn, my_chip, "in"), ""])
            no_of_employees_work = no_of_employees_work + 1
        else:
            mytable.add_row(["", "", name + " " + clock_time(conn, my_chip, "out")])
    conn.close()

    # set up field names of table and print table
    mytable.field_names = ["V1.1 人員: " + str(no_of_employees_work) + "/" + str(total_no_of_employees), "上班 \u263C",
                           "下班 \u263D"]
    mytable.align = "l"
    print(mytable)


def clock_time(conn, my_chip, in_out):
    cur = conn.cursor()
    if in_out == "in":
        sql = "SELECT clockin FROM attendance INNER JOIN users USING (userid) WHERE clockday = curdate() AND chipno = ? ORDER BY clockin DESC"
    else:
        sql = "SELECT clockout FROM attendance INNER JOIN users USING (userid) WHERE clockday = curdate() AND chipno = ? ORDER BY clockout DESC"
    par = (my_chip,)
    cur.execute(sql, par)
    clock_datetime = cur.fetchone()[0]
    return str(clock_datetime)


def reader():
    while True:
        my_chip = input()
        conn = connect_to_mariadb()
        if user_exists(conn, my_chip):
            if user_clocked(conn, my_chip):
                attendance_go(conn, my_chip)
            else:
                attendance_come(conn, my_chip)
        else:
            clear()
            print("沒有找到用戶" + str(my_chip))
            time.sleep(1.5)
        conn.close()
        update_display()

        # shutdown if last employee clocks out
        if not factory_notempty():
            print("關機")
            print(3)
            time.sleep(1)
            print(2)
            time.sleep(1)
            print(1)
            time.sleep(1)
            shutdown()


def shutdown():
    os.system("sudo shutdown -h now")


if __name__ == '__main__':
    update_display()
    reader()
