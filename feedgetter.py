#! /usr/bin/env python
#-*- coding: utf-8 -*-

# pyAggr3g470r - A Web based news aggregator.
# Copyright (C) 2010  Cédric Bonhomme - http://cedricbonhomme.org/
#
# For more information : http://bitbucket.org/cedricbonhomme/pyaggr3g470r/
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

__author__ = "Cedric Bonhomme"
__version__ = "$Revision: 1.0 $"
__date__ = "$Date: 2010/09/02 $"
__copyright__ = "Copyright (c) Cedric Bonhomme"
__license__ = "GPLv3"

import os.path
import traceback
import sqlite3
import threading
import feedparser
from BeautifulSoup import BeautifulSoup

from datetime import datetime

import utils

feeds_list = []
list_of_threads = []


class FeedGetter(object):
    """
    """
    def __init__(self):
        """
        Initializes the base and variables.
        """
        # Create the base if not exists.
        utils.create_base()

        # mutex to protect the SQLite base
        self.locker = threading.Lock()

    def retrieve_feed(self):
        """
        Parse the file 'feeds.lst' and launch a thread for each RSS feed.
        """
        with open("./var/feed.lst") as f:
            for a_feed in f:
                # test if the URL is well formed
                for url_regexp in utils.url_finders:
                    if url_regexp.match(a_feed):
                        the_good_url = url_regexp.match(a_feed).group(0).replace("\n", "")
                        try:
                            # launch a new thread for the RSS feed
                            thread = threading.Thread(None, self.process, \
                                                None, (the_good_url,))
                            thread.start()
                            list_of_threads.append(thread)
                        except:
                            pass
                        break

        # wait for all threads are done
        for th in list_of_threads:
            th.join()

    def process(self, the_good_url):
        """Request the URL

        Executed in a thread.
        SQLite objects created in a thread can only be used in that same thread !
        """
        # Protect this part of code.
        self.locker.acquire()

        self.conn = sqlite3.connect(utils.sqlite_base, isolation_level = None)
        self.c = self.conn.cursor()

        if utils.detect_url_errors([the_good_url]) == []:
            # if ressource is available add the articles in the base.
            self.add_into_sqlite(the_good_url)

            self.conn.commit()
        self.c.close()

        # Release this part of code.
        self.locker.release()

    def add_into_sqlite(self, feed_link):
        """
        Add the articles of the feed 'a_feed' in the SQLite base.
        """
        a_feed = feedparser.parse(feed_link)
        if a_feed['entries'] == []:
            return
        try:
            feed_image = a_feed.feed.image.href
        except:
            feed_image = "/css/img/feed-icon-28x28.png"
        try:
            self.c.execute('insert into feeds values (?,?,?,?,?)', (\
                        utils.clear_string(a_feed.feed.title.encode('utf-8')), \
                        a_feed.feed.link.encode('utf-8'), \
                        feed_link, \
                        feed_image,
                        "0"))
        except sqlite3.IntegrityError:
                # feed already in the base
                pass
        for article in a_feed['entries']:
            description = ""
            try:
                # article content
                description = article.content[0].value
            except AttributeError:
                try:
                    # article description
                    description = article.description
                except Exception, e:
                    description = ""
            description = str(BeautifulSoup(description))
            article_title = str(BeautifulSoup(article.title))

            try:
            	post_date = datetime(*article.updated_parsed[:6])
            except:
                post_date = datetime(*article.published_parsed[:6])

            try:
                # try. Will only success if the article is not already in the data base
                self.c.execute('insert into articles values (?, ?, ?, ?, ?, ?, ?)', (\
                        post_date, \
                        article_title, \
                        article.link.encode('utf-8'), \
                        description, \
                        "0", \
                        feed_link, \
                        "0"))
                result = self.c.execute("SELECT mail from feeds WHERE feed_site_link='" + \
                                a_feed.feed.link.encode('utf-8') + "'").fetchall()
                if result[0][0] == "1":
                    # if subscribed to the current feed
                    # send the article by e-mail
                    try:
                        threading.Thread(None, utils.send_mail, None, (utils.mail_from, utils.mail_to, \
                                            a_feed.feed.title.encode('utf-8'), \
                                            article_title, description) \
                                        ).start()
                    except Exception, e:
                        # SMTP acces denied, to many SMTP connections, etc.
                        top = traceback.extract_stack()[-1]
                        print ", ".join([type(e).__name__, os.path.basename(top[0]), str(top[1])])
            except sqlite3.IntegrityError:
                # article already in the data base
                pass
            except Exception, e:
                # Missing information (updated_parsed, ...)
                top = traceback.extract_stack()[-1]
                print ", ".join([type(e).__name__, os.path.basename(top[0]), str(top[1]), str(traceback.extract_stack()[-2][3])])


if __name__ == "__main__":
    # Point of entry in execution mode
    feed_getter = FeedGetter()
    feed_getter.retrieve_feed()
