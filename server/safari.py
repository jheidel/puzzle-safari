#!/usr/bin/env python

import os
import urllib
import datetime
import hashlib

from google.appengine.api import users
from google.appengine.ext import ndb

import jinja2
import webapp2

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


def format_datetime(value):
    # Horrible hard-coded tz logic that doesn't respect DST.
    if value is None:
        return ''
    local = value - datetime.timedelta(hours=7)
    #return local.strftime('%Y-%m-%d %I:%M:%S %p')
    return local.strftime('%I:%M:%S %p')

JINJA_ENVIRONMENT.filters['pst'] = format_datetime



def universe_key():
    """Constructs a datastore universe key.

    Everything will be in the same entity group here, but that's fine because
    this isn't the real world and we won't have millions of QPS.
    """
    return ndb.Key('Safari', 'universe')


class User(ndb.Model):
    """Represents a signed in user."""
    identity = ndb.StringProperty(indexed=False)
    email = ndb.StringProperty(indexed=False)


class ActionItem(ndb.Model):
    """Represents a task to be completed."""
    creator = ndb.StructuredProperty(User)
    time_created = ndb.DateTimeProperty(auto_now_add=True)
    creator_note = ndb.StringProperty(indexed=False)

    completer = ndb.StructuredProperty(User)
    time_completed = ndb.DateTimeProperty()
    completer_note = ndb.StringProperty(indexed=False)

    building = ndb.IntegerProperty()
    time_required_sec = ndb.IntegerProperty()
    completed = ndb.BooleanProperty()


class DataPage(webapp2.RequestHandler):
    PAGE = 'index.html'

    def get(self):

        ai_query = ActionItem.query(
            ancestor=universe_key()).order(-ActionItem.time_created)

        ais = ai_query.fetch(1000)

        user = users.get_current_user()
        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        stats = {
            'total' : len(ais),
            'complete' : len([a for a in ais if a.completed]),
            'incomplete' : len([a for a in ais if not a.completed]),
        }

        hashacc = ','.join(format_datetime(a.time_created) + ':' + format_datetime(a.time_completed) for a in ais)
        m = hashlib.md5()
        m.update(hashacc)

        template_values = {
            'user': user,
            'action_items': ais,
            'url': url,
            'url_linktext': url_linktext,
            'stats': stats,
            'hash': m.hexdigest()[:8],
        }

        template = JINJA_ENVIRONMENT.get_template(self.PAGE)
        self.response.write(template.render(template_values))


class MainPage(DataPage):
    PAGE = 'index.html'


class ItemsPage(DataPage):
    PAGE = 'items.html'

class AjaxPage(DataPage):
    PAGE = 'ajax.html'


class ActionCreate(webapp2.RequestHandler):

    def post(self):
        new = ActionItem(parent=universe_key())

        if users.get_current_user():
            new.creator = User(
                    identity=users.get_current_user().user_id(),
                    email=users.get_current_user().email())

        new.creator_note = self.request.get('note')

        new.time_required_sec = 10 * 60
        new.building = int(self.request.get('building'))
        new.completed = False

        new.put()

        self.redirect('/')


class ActionComplete(webapp2.RequestHandler):

    def post(self):
        ai_key = ndb.Key(urlsafe=self.request.get('action_id'))
        ai = ai_key.get()

        if users.get_current_user():
            ai.completer = User(
                    identity=users.get_current_user().user_id(),
                    email=users.get_current_user().email())

        ai.completed = True
        ai.time_completed = datetime.datetime.now()
        ai.completer_note = self.request.get('completernote')
        ai.put()

        self.redirect('/')


app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/items', ItemsPage),
    ('/ajax', AjaxPage),
    ('/create', ActionCreate),
    ('/complete', ActionComplete),
], debug=True)
