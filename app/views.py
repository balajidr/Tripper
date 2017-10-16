from app import app
from flask import render_template, request, redirect, url_for, flash, session
import argparse
import sys
import os
import json
import re
from oauth2client import tools
from oauth2client.tools import run_flow
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage
import gdata.contacts.client
import gdata.contacts.data
from sqlalchemy.engine import create_engine
from googleplaces import GooglePlaces
from random import randint


def dbconnect():
    engine = create_engine('mysql://dbusername:dbpassword@localhost:3306/dbname?charset=utf8')
    connection = engine.connect()
    return connection


def dbclose(connection):
    connection.close()
    return


@app.route('/')
@app.route('/index')
def index():
    session['loggedIn'] = False
    return render_template("index.html")


@app.route("/select",methods=['POST', 'GET'])
def select():
    session['contacts'] = []
    session['contactsdict'] = {}
    session['shortname'] = ''
    session['allphonenumbers'] = []
    connection = dbconnect()
    if request.method == 'POST':
        if request.form['submit'] == 'login':
            email = request.form['email']
            session['shortname'] = email.split('@')[0]
            password = request.form['password']
            phone = request.form['phone']
            values = [email,phone,password]
            result = connection.execute("SELECT email,phone,password from users")
            for row in result:
                if email in row['email']:
                    if row['email'] == email and row['phone'] == phone and row['password'] == password:
                        session["loggedIn"] = True
                        session['username'] = email
                        session['userphone'] = phone
                        check = connection.execute("SELECT group_id from groups WHERE username=%s",
                                                   [session['username']])
                        for raw in check:
                            if raw['group_id']:
                                session['group_id'] = raw['group_id']
                                dbclose(connection)
                                return render_template("myplan.html", username=session['shortname'])
                        dbclose(connection)
                        return render_template("select.html", username=session['shortname'])
                    elif row['email'] == email and row['password'] != password or row['phone'] != phone:
                        dbclose(connection)
                        flash("Invalid Details Provided")
                        return redirect(url_for('index'))

            connection.execute("INSERT into `users`(`email`,`phone`,`password`) VALUES (%s,%s,%s)", values)
            session["loggedIn"] = True
            session['username'] = email
            session['userphone'] = phone
            session['allphonenumbers'] = []
            dbclose(connection)
            return render_template("select.html", username=session['shortname'])


@app.route("/glogin", methods=['POST','GET'])
def glogin():

    session['contacts'] = []
    session['contactsdict'] = {}
    session['allphonenumbers'] = []
    session['shortname'] = ''

    G_CLIENT_ID = 'PASTE YOUR GOOGLE CLIENT_ID HERE'
    G_CLIENT_SECRET = 'PASTE YOUR GOOGLE CLIENT_SECRET HERE'

    def return_token():
        return get_oauth2_token()

    def disable_stout():
        o_stdout = sys.stdout
        o_file = open(os.devnull, 'w')
        sys.stdout = o_file
        return (o_stdout, o_file)

    def enable_stout(o_stdout, o_file):
        o_file.close()
        sys.stdout = o_stdout

    def get_oauth2_token():
        CLIENT_ID = G_CLIENT_ID
        CLIENT_SECRET = G_CLIENT_SECRET
        SCOPE = ['https://www.googleapis.com/auth/contacts.readonly', 'https://www.googleapis.com/auth/userinfo.email']
        REDIRECT_URI = 'http://localhost:8080/oauth2callback'

        o_stdout, o_file = disable_stout()

        flow = OAuth2WebServerFlow(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            scope=SCOPE,
            redirect_uri=REDIRECT_URI)

        parser = argparse.ArgumentParser(parents=[tools.argparser])
        flags = parser.parse_args()

        n = randint(1, 10000)
        session['filename'] = "creds"+str(n)+".json"

        storage = Storage(session['filename'])
        credentials = run_flow(flow, storage, flags)
        enable_stout(o_stdout, o_file)
        session['access_token'] = credentials.access_token

    return_token()
    dicta = json.load(open(session['filename']))
    username = dicta['id_token']['email']
    session['username'] = username
    session['shortname'] = username.split('@')[0]

    if request.method == 'POST':
        if request.form['glogin'] == 'glogin':
            gphone = request.form['phone2']
            connection = dbconnect()
            result = connection.execute("SELECT email,phone,password from users")
            for row in result:
                if username in row['email']:
                        if row['email'] == username and gphone != row['phone']:
                            session['loggedIn'] = False
                            flash("Email ID and Given Phone number doesnt match.")
                            dbclose(connection)
                            return redirect(url_for('index'))

                        elif row['email'] == username and gphone == row['phone']:
                            session["loggedIn"] = True
                            session["username"] = username
                            session['userphone'] = gphone
                            val = [session['username']]
                            check = connection.execute("SELECT group_id from groups WHERE username in (%s)", val)
                            for temp in check:
                                if temp['group_id']:
                                    session['group_id'] = temp['group_id']
                                    pval = session['group_id']
                                    users = []
                                    postlist = []
                                    fetch = connection.execute(
                                        'SELECT * FROM posts where group_id=%s ORDER BY time ASC', pval)
                                    for raw in fetch:
                                        users.append(raw['username'])
                                        postlist.append(raw['post'])
                                    temp = zip(users, postlist)
                                    dbclose(connection)
                                    return render_template("myplan.html", username=session['shortname'], temp=temp)

                            dbclose(connection)
                            return render_template("select.html", username=session['shortname'])

            values=[session['username'], gphone]
            connection.execute("INSERT into `users`(`email`,`phone`) VALUES (%s,%s)", values)
            session["loggedIn"] = True
            session["username"] = username
            session['userphone'] = gphone
            dbclose(connection)
            return render_template("select.html", username=session['shortname'])

    return render_template('select.html', username=session['shortname'])


@app.route('/mycontacts', methods=["POST","GET"])
def mycontacts():

      if request.method == "POST":
        if request.form['submit'] == 'addcon':
            pnum = request.form['pnum']
            if pnum in session['allphonenumbers']:
                flash("User is already in your list")
                return redirect(url_for("mycontacts"))

            connection = dbconnect()
            val = [pnum]
            fetch = connection.execute("SELECT email,phone from users where phone=%s", val)
            if fetch.rowcount == 0:
                flash("No Users with the given phone number")
                dbclose(connection)
                return redirect(url_for("mycontacts"))

            fetch = connection.execute("SELECT email,phone from users where phone=%s", val)
            for row in fetch:
                if row['email'] == session['username']:
                    flash("We feel Sorry for your Loneliness. But you can't add yourself to your friendlist :( ")
                    dbclose(connection)
                    return redirect(url_for("mycontacts"))

                else:
                    fetch = connection.execute("SELECT email,phone from users where phone=%s", val)
                    for row in fetch:
                        session['contacts'].append(row['email'])
                        session['contactsdict'][row['email']] = row['phone']
                        session['allphonenumbers'].insert(0, row['phone'])
                        dbclose(connection)
                    return render_template('select.html', contact=session['contacts'], numbers=session['contactsdict'], username=session['shortname'])
                
        elif request.form['submit'] == 'gcontacts':
            GOOGLE_CLIENT_ID = 'PASTE YOUR GOOGLE CLIENT_ID HERE'
            GOOGLE_CLIENT_SECRET = 'PASTE YOUR GOOGLE CLIENT_SECRET HERE'
            access_token = session['access_token']
            token = gdata.gauth.OAuth2Token(
                client_id=GOOGLE_CLIENT_ID,
                client_secret=GOOGLE_CLIENT_SECRET,
                scope='https://www.google.com/m8/feeds/contacts/default/full',
                user_agent='app.testing',
                access_token=access_token)

            mycontactsdict = {}
            mycontacts = []
            contact_client = gdata.contacts.client.ContactsClient()
            token.authorize(contact_client)

            feed = contact_client.GetContacts()
            for i, entry in enumerate(feed.entry):
                for phone in entry.phone_number:
                        if entry.title.text is None or entry.title.text in mycontacts:
                            continue
                        else:
                            mycontacts.append(entry.title.text)
                            mycontactsdict[entry.title.text] = phone.text
            next = feed.GetNextLink()
            while next:
                feed = None
                if next:
                    feed = contact_client.GetContacts(uri=next.href)
                for i, entry in enumerate(feed.entry):
                    for phone in entry.phone_number:
                        if entry.title.text is None or entry.title.text in mycontacts:
                            continue
                        else:
                            mycontacts.append(entry.title.text)
                            mycontactsdict[entry.title.text] = phone.text
                next = feed.GetNextLink()
            allpnumbers = []
            for each in mycontacts:
                one = mycontactsdict[each]
                one = one.encode('utf-8')
                one = re.sub('\W+', "", one)
                if one.startswith("91"):
                    one = one[len("91"):]
                    allpnumbers.append(one)
                    mycontactsdict[each] = str(one)
            session['allphonenumbers'] = allpnumbers
            session['contacts'].extend(mycontacts)
            session['contactsdict'].update(mycontactsdict)
            return render_template('select.html', contact=session['contacts'], numbers=session['contactsdict'], username=session['shortname'])

    return render_template('select.html', contact=session['contacts'], numbers=session['contactsdict'])


@app.route('/myplan', methods=['POST', 'GET'])
def myplan():

    if "loggedIn" not in session.keys():
        return redirect(url_for(index))

    if session["loggedIn"] != True:
        return redirect(url_for("index"))

    users = []
    postlist = []
    if request.method == "POST":
        if request.form['submit'] == 'plan':
            group_id = randint(1, 10000)
            session['group_id'] = group_id
            selected_users = request.form.getlist("tolistbox")
            selected_users1 = []
            for one in selected_users:
                one = str(one)
                one = re.sub('\W+', '', one)
                if one.startswith("91"):
                    one = one[len("91"):]
                selected_users1.insert(0,one)
            session['groupinfo'] = selected_users1
            connection = dbconnect()
            values = session['groupinfo']
            if session['groupinfo'] != []:
                for each in values:
                    res = connection.execute("SELECT email from users WHERE phone=%s", [each])
                    if res.rowcount == 0:
                        flash("Some of your Friends are not using Tripper :( Please ask them to register.")
                        dbclose(connection)
                        return redirect(url_for("mycontacts"))
                    else:
                        check = connection.execute("SELECT username from groups")
                        for raw in res:
                            for eachone in check:
                                if raw['email'] == eachone['username']:
                                    flash("One of your User is in another group :( ")
                                    dbclose(connection)
                                    return redirect(url_for("mycontacts"))
                        res = connection.execute("SELECT email from users WHERE phone=%s", [each])
                        for row in res:
                            va = [session['group_id'], row['email']]
                            connection.execute("INSERT into `groups`(`group_id`,`username`) VALUES(%s,%s)", va)
                values = [session['group_id'], session['username']]
                connection.execute("INSERT into `groups`(`group_id`,`username`) VALUES(%s,%s)", values)
                dbclose(connection)

        if request.form['submit'] == 'send':
                string = request.form['message']
                values = [session['group_id'], session['shortname'], string]
                connection = dbconnect()
                connection.execute('INSERT into  `posts`(`group_id`,`username`,`post`) VALUES (%s,%s,%s)', values)
                dbclose(connection)
    connection = dbconnect()
    values = [session['group_id']]
    fetch = connection.execute('SELECT * FROM posts where group_id=%s ORDER BY time ASC', values)
    for row in fetch:
        users.append(row['username'])
        postlist.append(row['post'])
    dbclose(connection)
    temp = zip(users, postlist)
    return render_template('myplan.html', username=session['shortname'], temp=temp)


@app.route('/myplan2', methods=['POST', 'GET'])
def myplan2():

    if "loggedIn" not in session.keys():
        return redirect(url_for(index))

    if not session["loggedIn"]:
        return redirect(url_for('index'))

    users = []
    postlist = []
    connection = dbconnect()
    values = [session['group_id']]
    fetch = connection.execute('SELECT * FROM posts where group_id=%s ORDER BY time ASC', values)
    for row in fetch:
        users.append(row['username'])
        postlist.append(row['post'])
    dbclose(connection)

    details = []
    if request.method == "POST":
        if request.form['submit'] == 'submit':
            location = request.form['place']
            keyword = request.form['search_string']
            type = request.form['type']
            radius = 4000
            API_KEY = 'PASTE YOUR GOOGLE PLACES API_KEY HERE'
            details = []
            google_places = GooglePlaces(API_KEY)
            page_token = ''
            query_result = google_places.nearby_search(
                location=location, keyword=keyword,
                radius=radius, pagetoken=page_token, type=[type])

            for place in query_result.places:
                place.get_details()
                if place.international_phone_number:
                    #print (
                     #place.name + ' ' + place.vicinity + '   rating :' + str(
                         #place.rating) + '  ' + place.international_phone_number)
                    details.insert(0, {'name': place.name, 'address': place.vicinity, 'rating': str(place.rating),
                                   'phone': place.international_phone_number, 'url': place.url})

            while query_result.has_next_page_token:
                 query_result = google_places.nearby_search(
                    location=location, keyword=keyword,
                    radius=radius, pagetoken=page_token, type=[type])

                 if query_result.has_next_page_token:
                         page_token = query_result.next_page_token
                 for place in query_result.places:
                    place.get_details()
                    if place.international_phone_number:
                        #print (place.name + ' ' + place.vicinity + '   rating :' + str(
                        #   place.rating) + '  ' + place.international_phone_number)
                        details.insert(0, {'name': place.name, 'address': place.vicinity, 'rating': str(place.rating),
                            'phone': place.international_phone_number, 'url': place.url})

    temp = zip(users, postlist)
    return render_template('myplan.html', username=session['shortname'], details=details, temp=temp)


@app.route('/goodbye')
def goodbye():
    session['loggedIn'] = False
    value = session['username']
    connection = dbconnect()
    connection.execute("DELETE from groups where username=%s", value)
    val = session['group_id']
    fetch = connection.execute("SELECT * from groups where group_id=%s", val)
    if fetch.rowcount == 0:
        connection.execute("DELETE from posts where group_id=%s", val)
    dbclose(connection)
    return render_template("goodbye.html", username=session['shortname'])


@app.route('/logout')
def logout():
    session['loggedIn'] = False
    try:
        os.remove(session['filename'])
    except OSError:
        pass
    return redirect(url_for("index"))
