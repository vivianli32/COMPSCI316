from flask import render_template, flash, redirect, session, url_for, request, g
from flask.ext.login import login_user, logout_user, current_user, login_required
from app import app, db, lm, oid, models
from .forms import LoginForm, EditForm, RatingsForm, MessagesForm, SearchForm
from .models import User, AreaOfInterests
from datetime import datetime
from config import MAX_SEARCH_RESULTS

@lm.user_loader
def load_user(id):
    return User.query.get(int(id))

@app.before_request
def before_request():
    g.user = current_user
    if g.user.is_authenticated():
        g.user.last_seen = datetime.utcnow()
        db.session.add(g.user)
        db.session.commit()
        g.search_form = SearchForm()

@app.route('/')
@app.route('/search', methods= ['GET'])
def search():
    form = SearchForm()
    if form.validate_on_submit():
        s=form.state.djata
        c=form.city.data
        a=form.activity.data
        query = [s, c, a]
    #if not form.validate_on_submit():
    #    return redirect(url_for('search'))
    return render_template('search.html', form=form)

#non whoosh search
@app.route('/search_results/', methods= ['POST'])
def search_results():
        s = request.form['state']
        c = request.form['city']
        a = request.form['activity']
        query = [s, c,a ]
        print (query)
        results = User.query.join(AreaOfInterests, (AreaOfInterests.user_id == User.id)).filter_by(state=s, city=c, area=a).all()
        print (results)
        return render_template('search_results.html',
                                query=query,
                                results=results)
        #2 will probably increase once we have more data
        #if too few queries show up, eliminate activity from the search and redo
        #if (len(tuples) < 2)
         #   flash('Your query returned very few results--sorry! Click here to reinitialize search with just the State and City you speficied.')
         #   modified = User.query.join(AreaOfInterests, AreaOfInterests.user_id == User.id).filter_by(s=AreaOfInterests,c=AreaOfInterests.city).all()
        #if (len(modified) <2)

#@app.route('/search_results/<query>')
#def search_results(s,c,a):
 #   results = AreaOfInterests.query.whoosh_search(s,c,a, fields=('state','city','activity'), MAX_SEARCH_RESULTS)       
 #   return render_template('search_results.html',
  #                          s=s,
  #                          c=c,
   #                         a=a,
   #                         results=results)




@app.route('/index')
@login_required
def index():
    user = g.user
    posts = [
        { 
            'author': { 'nickname': 'John' }, 
            'body': 'Beautiful day in Portland!' 
        },
        { 
            'author': { 'nickname': 'Susan' }, 
            'body': 'The Avengers movie was so cool!' 
        }
    ]
    return render_template('index.html',
        title = 'Home',
        user = user,
        posts = posts)

@app.route('/login', methods = ['GET', 'POST'])
@oid.loginhandler
def login():
    if g.user is not None and g.user.is_authenticated():
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        session['remember_me'] = form.remember_me.data
        return oid.try_login(form.openid.data, ask_for = ['nickname', 'email'])
    return render_template('login.html', 
        title = 'Sign In',
        form = form,
        providers = app.config['OPENID_PROVIDERS'])

@oid.after_login
def after_login(resp):
    if resp.email is None or resp.email == "":
        flash('Invalid login. Please try again.')
        return redirect(url_for('login'))
    user = User.query.filter_by(email = resp.email).first()
    if user is None:
        nickname = resp.nickname
        if nickname is None or nickname == "":
            nickname = resp.email.split('@')[0]
        nickname = User.make_unique_nickname(nickname)
        user = User(nickname = nickname, email = resp.email)
        db.session.add(user)
        db.session.commit()
        aoi=models.AreaOfInterests(user_id=user.id, country=' ',state=' ',city=' ',area=' ')
        db.session.add(aoi)
        db.session.commit()
    remember_me = False
    if 'remember_me' in session:
        remember_me = session['remember_me']
        session.pop('remember_me', None)
    login_user(user, remember = remember_me)
    return redirect(request.args.get('next') or url_for('index'))

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))
    
@app.route('/user/<nickname>', methods = ['GET', 'POST'])
@login_required
def user(nickname):
    user = User.query.filter_by(nickname = nickname).first()
    if user == None:
        flash('User ' + nickname + ' not found.')
        return redirect(url_for('index'))
    # posts = [
    #     { 'author': user, 'body': 'Test post #1' },
    #     { 'author': user, 'body': 'Test post #2' }
    # ]
    comments = user.get_comments().all()
    useraoi = user.get_aoi()
    #rating other users
    form = RatingsForm()
    if form.validate_on_submit():
        rating = models.Ratings(rater_id = g.user.id,
            rated_id = user.id,
            comment = form.comment.data, 
            rates= form.rates.data,
            timestamp = datetime.now())
        db.session.add(rating)
        db.session.commit()
        flash('Your post is now live!')
        return redirect(url_for('user', nickname=nickname))
    return render_template('user.html',
        user = user,
        comments = comments,  
        useraoi = useraoi,
        form = form,
        nickname = nickname)

@app.route('/edit', methods = ['GET', 'POST'])
@login_required
def edit():
    form = EditForm(g.user.nickname)
    guseraoi=g.user.get_aoi()
    if form.validate_on_submit():
        g.user.nickname = form.nickname.data
        g.user.firstname = form.firstname.data
        g.user.lastname = form.lastname.data
        g.user.phone = form.phone.data
        g.user.about_me = form.about_me.data
        guseraoi.country = form.country.data
        guseraoi.state = form.state.data
        guseraoi.city = form.city.data
        guseraoi.area = form.area.data
        db.session.add(g.user)
        db.session.commit()
        db.session.add(guseraoi)
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit'))
    elif request.method != "POST":
        form.nickname.data = g.user.nickname
        if form.about_me.data: 
            form.about_me.data = g.user.about_me
        if form.firstname.data: 
            form.firstname.data = g.user.firstname
        if form.lastname.data: 
            form.lastname.data = g.user.lastname
        if form.phone.data: 
            form.phone.data = g.user.phone
        if form.country.data: 
            form.country.data = guseraoi.country
        if form.state.data: 
            form.state.data = guseraoi.state
        if form.city.data: 
            form.city.data = guseraoi.city
        if form.area.data: 
            form.area.data = guseraoi.area
    return render_template('edit.html',
        form = form)

@app.route('/message/<nickname>', methods = ['GET', 'POST'])
@login_required
def sendMessage(nickname):
    #if browse his or her own profile
    if g.user.nickname == nickname:
        user = g.user
        messages = user.get_guser_messages().all()
        return render_template('gusermessage.html',
            messages = messages)
    else: 
    #if browse other's profile    
        user = User.query.filter_by(nickname = nickname).first()
        if user == None:
            flash('User ' + nickname + ' not found.')
            return redirect(url_for('index'))
        messages = user.get_user_messages(g.user).all()
        form = MessagesForm()
        if form.validate_on_submit():
            message = models.Messages(sender_id = g.user.id,
                receiver_id = user.id,
                text = form.text.data, 
                time = datetime.now())
            db.session.add(message)
            db.session.commit()
            flash('Your message is sending!')
            return redirect(url_for('user', nickname=nickname))
        return render_template('message.html',
            form = form,
            messages = messages)


@app.errorhandler(404)
def internal_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500 

#@app.route('/') 
    
