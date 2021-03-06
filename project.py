from flask import Flask, render_template, request, redirect, jsonify, \
    url_for, flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, BookStores, Items, User
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

app = Flask(__name__)

CLIENT_ID = json.loads(open('client_secrets.json', 'r').read())['web'
        ]['client_id']
APPLICATION_NAME = 'Book Store Application'

# Connect to Database and create database session

engine = create_engine('sqlite:///bookstore.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()


# Create anti-forgery state token

@app.route('/login')
def showLogin():
    state = ''.join(random.choice(string.ascii_uppercase
                    + string.digits) for x in xrange(32))
    login_session['state'] = state

    # return "The current session state is %s" % login_session['state']

    return render_template('login.html', STATE=state)


@app.route('/fbconnect', methods=['POST'])
def fbconnect():
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'
                                 ), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = request.data
    print 'access token received %s ' % access_token

    app_id = json.loads(open('fb_client_secrets.json', 'r'
                        ).read())['web']['app_id']
    app_secret = json.loads(open('fb_client_secrets.json', 'r'
                            ).read())['web']['app_secret']
    url = \
        'https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s' \
        % (app_id, app_secret, access_token)
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]

    # Use token to get user info from API

    userinfo_url = 'https://graph.facebook.com/v2.4/me'

    # strip expire tag from access token

    token = result.split('&')[0]

    url = 'https://graph.facebook.com/v2.4/me?%s&fields=name,id,email' \
        % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]

    # print "url sent for API access:%s"% url
    # print "API JSON result: %s" % result

    data = json.loads(result)
    login_session['provider'] = 'facebook'
    login_session['username'] = data['name']
    login_session['email'] = data['email']
    login_session['facebook_id'] = data['id']

    # The token must be stored in the login_session in order to properly logout, let's strip out the information before the equals sign in our token

    stored_token = token.split('=')[1]
    login_session['access_token'] = stored_token

    # Get user picture

    url = \
        'https://graph.facebook.com/v2.4/me/picture?%s&redirect=0&height=200&width=200' \
        % token
    h = httplib2.Http()
    result = h.request(url, 'GET')[1]
    data = json.loads(result)

    login_session['picture'] = data['data']['url']

    # see if user exists

    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']

    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += \
        ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '

    flash('Now logged in as %s' % login_session['username'])
    return output


@app.route('/fbdisconnect')
def fbdisconnect():
    facebook_id = login_session['facebook_id']

    # The access token must me included to successfully logout

    access_token = login_session['access_token']
    url = 'https://graph.facebook.com/%s/permissions?access_token=%s' \
        % (facebook_id, access_token)
    h = httplib2.Http()
    result = h.request(url, 'DELETE')[1]
    return 'you have been logged out'


@app.route('/gconnect', methods=['POST'])
def gconnect():

    # Validate state token

    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'
                                 ), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Obtain authorization code

    code = request.data

    try:

        # Upgrade the authorization code into a credentials object

        oauth_flow = flow_from_clientsecrets('client_secrets.json',
                scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = \
            make_response(json.dumps('Failed to upgrade the authorization code.'
                          ), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.

    access_token = credentials.access_token
    url = \
        'https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s' \
        % access_token
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1])

    # If there was an error in the access token info, abort.

    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.

    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = \
            make_response(json.dumps("Token's user ID doesn't match given user ID."
                          ), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.

    if result['issued_to'] != CLIENT_ID:
        response = \
            make_response(json.dumps("Token's client ID does not match app's."
                          ), 401)
        print "Token's client ID does not match app's."
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_credentials = login_session.get('credentials')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_credentials is not None and gplus_id == stored_gplus_id:
        response = \
            make_response(json.dumps('Current user is already connected.'
                          ), 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.

    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info

    userinfo_url = 'https://www.googleapis.com/oauth2/v1/userinfo'
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    # ADD PROVIDER TO LOGIN SESSION

    login_session['provider'] = 'google'

    # see if user exists, if it doesn't make a new one

    user_id = getUserID(data['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += \
        ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
    flash('you are now logged in as %s' % login_session['username'])
    print 'done!'
    return output


# User Helper Functions

def createUser(login_session):
    newUser = User(name=login_session['username'],
                   email=login_session['email'],
                   picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email'
            ]).one()
    return user.id


def getUserInfo(user_id):
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None


# DISCONNECT - Revoke a current user's token and reset their login_session

@app.route('/gdisconnect')
def gdisconnect():

    # Only disconnect a connected user.

    credentials = login_session.get('credentials')
    if credentials is None:
        response = \
            make_response(json.dumps('Current user not connected.'),
                          401)
        response.headers['Content-Type'] = 'application/json'
        return response
    access_token = credentials.access_token
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' \
        % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] != '200':

        # For whatever reason, the given token was invalid.

        response = \
            make_response(json.dumps('Failed to revoke token for given user.'
                          ), 400)
        response.headers['Content-Type'] = 'application/json'
        return response


# JSON APIs to view Book Store Information

@app.route('/store/<int:store_id>/item/JSON')
def storeItemJSON(store_id):
    store = \
        session.query(BookStores).filter_by(id=store_id).one()
    items = \
        session.query(Items).filter_by(store_id=store_id).all()
    return jsonify(Items=[i.serialize for i in items])


@app.route('/store/<int:store_id>/item/<int:item_id>/JSON')
def itemsJSON(store_id, item_id):
    item = session.query(Items).filter_by(id=item_id).one()
    return jsonify(item=item.serialize)


@app.route('/store/JSON')
def storeJSON():
    store = session.query(BookStores).all()
    return jsonify(stores=[r.serialize for r in store])


# Show all Stores

@app.route('/')
@app.route('/stores/')
def showStores():
    stores = session.query(BookStores).order_by(asc(BookStores.name))
    if 'username' not in login_session:
        return render_template('publicstores.html', stores=stores)
    else:
        return render_template('stores.html', stores=stores)


# Create a new Book Store

@app.route('/store/new/', methods=['GET', 'POST'])
def newStore():
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        newBookStore = BookStores(name=request.form['name'],
                                  user_id=login_session['user_id'])
        session.add(newBookStore)
        flash('New Book Store %s Successfully Created'
              % newBookStore.name)
        session.commit()
        return redirect(url_for('showStores'))
    else:
        return render_template('newStore.html')


# Edit a book store

@app.route('/store/<int:store_id>/edit/', methods=['GET', 'POST'])
def editStore(store_id):
    if 'username' not in login_session:
        return redirect('/login')
    edit_store = session.query(BookStores).filter_by(id=store_id).one()
    if edit_store.user_id != login_session['user_id']:
        return "<script>function myFunction() {alert('You are not authorized to edit this Book Store. Please create your own Book Store in order to edit.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        if request.form['name']:
            edit_store.name = request.form['name']
            flash('Book Store Successfully Edited %s' % edit_store.name)
            return redirect(url_for('showStores'))
    else:
        return render_template('editStore.html', store=edit_store)


# Delete a Store

@app.route('/store/<int:store_id>/delete/', methods=['GET', 'POST'])
def deleteStore(store_id):
    if 'username' not in login_session:
        return redirect('/login')
    storeToDelete = \
        session.query(BookStores).filter_by(id=store_id).one()
    if storeToDelete.user_id != login_session['user_id']:
        return "<script>function myFunction() {alert('You are not authorized to delete this Store. Please create your own Store in order to delete.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        items = session.query(Items).filter_by(store_id = store_id).all()
        for item in items:
            session.delete(item)
        session.commit()
        session.delete(storeToDelete)
        flash('%s Successfully Deleted' % storeToDelete.name)
        session.commit()
        return redirect(url_for('showStores'))
    else:
        return render_template('deletestore.html', store = storeToDelete)


# Show Book Store items

@app.route('/store/<int:store_id>/')
@app.route('/store/<int:store_id>/items/')
def showItems(store_id):
    store = session.query(BookStores).filter_by(id=store_id).one()
    creator = getUserInfo(store.user_id)
    items = session.query(Items).filter_by(store_id=store_id).all()
    if 'username' not in login_session or creator.id \
        != login_session['user_id']:
        return render_template('publicitem.html', items=items,
                               store=store, creator=creator)
    else:
        return render_template('item.html', items=items, store=store,
                               creator=creator)


# Create a new book item

@app.route('/store/<int:store_id>/item/new/', methods=['GET', 'POST'])
def newBook(store_id):
    if 'username' not in login_session:
        return redirect('/login')
    store = session.query(BookStores).filter_by(id=store_id).one()
    if login_session['user_id'] != store.user_id:
        return "<script>function myFunction() {alert('You are not authorized to books to this store. Please create your own store in order to add items.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        newItem = Items(
            name=request.form['name'],
            description=request.form['description'],
            price=request.form['price'],
            course=request.form['course'],
            store_id=store_id,
            user_id=store.user_id
            )
        session.add(newItem)
        session.commit()
        flash('New Book %s Successfully Created' % newItem.name)
        return redirect(url_for('showItems', store_id=store_id))
    else:
        return render_template('newbookitem.html', store_id=store_id)


# Edit a item

@app.route('/store/<int:store_id>/item/<int:item_id>/edit',
           methods=['GET', 'POST'])
def editBookItem(store_id, item_id):
    if 'username' not in login_session:
        return redirect('/login')
    editedItem = session.query(Items).filter_by(id=item_id).one()
    store = session.query(BookStores).filter_by(id=store_id).one()
    if login_session['user_id'] != store.user_id:
        return "<script>function myFunction() {alert('You are not authorized to edit items to this Store. Please create your own Store in order to edit items.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        if request.form['name']:
            editedItem.name = request.form['name']
        if request.form['description']:
            editedItem.description = request.form['description']
        if request.form['price']:
            editedItem.price = request.form['price']
        if request.form['course']:
            editedItem.course = request.form['course']
        session.add(editedItem)
        session.commit()
        flash('Item Successfully Edited')
        return redirect(url_for('showItems', store_id=store_id))
    else:
        return render_template('editbookitem.html', store_id=store_id,
                               item_id=item_id, item=editedItem)


# Delete a item

@app.route('/store/<int:store_id>/item/<int:item_id>/delete',
           methods=['GET', 'POST'])
def deleteItem(store_id, item_id):
    if 'username' not in login_session:
        return redirect('/login')
    store = session.query(BookStores).filter_by(id=store_id).one()
    itemToDelete = session.query(Items).filter_by(id=item_id).one()
    if login_session['user_id'] != store.user_id:
        return "<script>function myFunction() {alert('You are not authorized to delete items to this Store. Please create your own Store in order to delete items.');}</script><body onload='myFunction()''>"
    if request.method == 'POST':
        session.delete(itemToDelete)
        session.commit()
        flash('Item Successfully Deleted')
        return redirect(url_for('showItems', store_id=store_id))
    else:
        return render_template('deleteBookItem.html',
                               item=itemToDelete, store_id=store_id,
                               item_id=item_id)


# Disconnect based on provider

@app.route('/disconnect')
def disconnect():
    if 'provider' in login_session:
        if login_session['provider'] == 'google':
            gdisconnect()
            del login_session['gplus_id']

            # del login_session['credentials']

        if login_session['provider'] == 'facebook':
            fbdisconnect()
            del login_session['facebook_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']
        del login_session['user_id']
        del login_session['provider']
        flash('You have successfully been logged out.')
        return redirect(url_for('showStores'))
    else:
        flash('You were not logged in')
        return redirect(url_for('showStores'))

if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=5000)
