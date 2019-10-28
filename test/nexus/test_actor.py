
from unittest import TestCase
from test.test_utils import StoreDependentTestCase
from src.nexus.actor import Actor, RunManager, AsyncRunManager, Spike
from src.nexus.store import Limbo
from multiprocessing import Process
import numpy as np
from pyarrow.lib import ArrowIOError
import pickle
import pyarrow.plasma as plasma
import asyncio
from queue import Empty
import time
from typing import Awaitable, Callable
import traceback
from nexus.store import ObjectNotFoundError
import pickle


#TODO: write actor unittests

#setStore
class Actor_setStore(StoreDependentTestCase):
    def setUp(self):
        super(Actor_setStore, self).setUp()
        self.actor = Actor('test')
        self.limbo = Limbo()

    def test_setStore(self):
        limbo = self.limbo
        actor = self.actor
        actor.setStore(limbo.client)
        self.assertEqual(actor.client, limbo.client)

    def tearDown(self):
        super(Actor_setStore, self).tearDown()


# Nicole :
## setLinks

## setCommLinks

## setLinkIn

## setLinkOut


# Daniel :
## addLink

## getLinks

## setUp

## run


#changePriority
