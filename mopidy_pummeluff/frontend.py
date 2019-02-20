# -*- coding: utf-8 -*-
'''
Python module for Mopidy Pummeluff frontend.
'''

from __future__ import absolute_import, unicode_literals, print_function

from threading import Thread, Event
from time import time
from logging import getLogger

import pykka
from mopidy import core

from .rfid_reader import RFIDReader, ReadError
from .cards import Card

LOGGER = getLogger(__name__)

LAST_UID = ''


class CardReader(Thread):
    '''
    Thread class which reads RFID cards from the RFID reader.
    '''
    latest = {}

    def __init__(self, core, stop_event):
        '''
        Class constructor.

        :param threading.Event stop_event: The stop event
        '''
        super(CardReader, self).__init__()
        self.core       = core
        self.stop_event = stop_event

    def run(self):
        '''
        Run RFID reading loop.
        '''
        reader    = RFIDReader()
        prev_time = time()
        prev_uid  = ''

        while not self.stop_event.is_set():
            reader.wait_for_tag()

            try:
                now = time()
                uid = reader.uid

                if now - prev_time > 1 or uid != prev_uid:
                    LOGGER.info('Card with UID %s read', uid)
                    self.handle_uid(uid)

                prev_time = now
                prev_uid  = uid

            except ReadError:
                pass

        reader.cleanup()

    def handle_uid(self, uid):
        '''
        Handle the scanned card / retreived UID.

        :param str uid: The UID
        '''
        card = Card(uid)

        if card.registered:
            LOGGER.info('Card is registered, triggering action')
            card.action(mopidy_core=self.core)
        else:
            LOGGER.info('Card is not registered, doing nothing')

        CardReader.latest = {
            'time': time(),
            'uid': card.uid,
            'card': str(card)
        }


class PummeluffFrontend(pykka.ThreadingActor, core.CoreListener):
    '''
    Pummeluff frontend which basically reads cards from the RFID reader.
    '''

    def __init__(self, config, core):
        super(PummeluffFrontend, self).__init__()
        self.core        = core
        self.stop_event  = Event()
        self.card_reader = CardReader(core=core, stop_event=self.stop_event)

    def on_start(self):
        '''
        Start card reader thread after the actor is started.
        '''
        self.card_reader.start()

    def on_stop(self):
        '''
        Stop card reader thread before the actor stops.
        '''
        self.stop_event.set()